"""The golden close eval pack: Harborlight's September, measured.

Runs the synthetic close through the real service on the offline
engine and compares against gold that is true by construction
(datasets.py plants the cases and states the expected figures
as literals; it never opines about them afterwards).

Gates (a failure exits non-zero):

- **traceability == 100%** — every figure in the signed pack
  carries its definition-pack version and source-batch stamps,
  and every one was reproduced from source by the verifier;
- **gold figures** — the corrected close's 25 figures equal the
  gold close-question answers exactly (Decimal-exact);
- **planted traps, named** — the first attempt's pack is BLOCKED
  with exactly the planted variance codes: DUPLICATE_JOURNAL,
  UNMATCHED_IC_LEG, SUBLEDGER_TIE_OUT;
- **staleness** — the first pack is STALE once the late extracts
  land, and cannot be signed;
- **consolidation ties** — the consolidated figures tie to the
  entity figures through the pack's own identities, in the eval's
  independent arithmetic;
- **gate discipline** — a blocked pack refuses sign-off; the
  verified pack accepts a named controller's sign-off.

The second act closes **October** over the same store, under
definition pack v1.1.0, after September's HLG extract is
restated post-sign-off. Its gates:

- **october gold figures** — October's 25 figures equal its
  gold answers exactly, under the new pack version;
- **comparatives tie to the signed pack** — every one of the
  25 comparatives equals the signed September figure it cites,
  string for string;
- **definition changes flagged** — the comparatives crossing
  the v1.0.0 → v1.1.0 definition change (and only those) carry
  the flag;
- **restatement named** — the pack carries a
  ``RESTATED_PRIOR_PERIOD`` variance whose affected figures
  equal the planted gold (signed vs recomputed);
- **the signature is held, then released** — sign-off refuses
  while the restatement is unacknowledged and succeeds after
  a named acknowledgement;
- **history untouched** — the signed September pack is
  byte-identical at the end of everything.

A live-engine run (EVAL_LIVE=1, FINANCE_ENGINE=aidnn with a
workspace configured) is reported, never gated — it measures
the deployment's engine, not this code.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from aidnn_close_agent.datasets import (  # noqa: E402
    DEFINITION_CHANGED_METRICS,
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_AFFECTED,
    RESTATEMENT_BATCH_ID,
    build_october_world,
    build_world,
)
from aidnn_close_agent.definitions import (  # noqa: E402
    load_definition_pack_version,
)
from aidnn_close_agent.demo import build_demo_service  # noqa: E402
from aidnn_close_agent.engine_offline import OfflineFinanceEngine  # noqa: E402
from aidnn_close_agent.errors import GateError  # noqa: E402
from aidnn_close_agent.fx import D  # noqa: E402
from aidnn_close_agent.graph import PackPipeline  # noqa: E402
from aidnn_close_agent.service import CloseService  # noqa: E402


def _figures(pack) -> dict:
    return {(f.metric_id, f.entity_id): f for f in pack.figures}


def evaluate() -> dict:
    world = build_world()
    service = build_demo_service()
    results: dict = {"backend": "offline", "period": PERIOD}

    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)

    # -- gate: the planted traps, named -------------------------------
    codes = sorted(v.code for v in first.variances)
    results["phase_a_status"] = first.status
    results["phase_a_variance_codes"] = codes
    trap_gate = first.status == "BLOCKED" and codes == sorted(
        world.phase_a_variance_codes
    )

    blocked_refused = False
    try:
        service.sign_off(first.pack_id, "sign", "Eval Controller")
    except GateError:
        blocked_refused = True

    # -- the late extracts land -----------------------------------------
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    first_after = service.get_pack(first.pack_id)
    stale_gate = first_after.status == "STALE"

    second = service.build_pack(run.run_id)
    figures = _figures(second)

    # -- gate: gold close questions, exact answers ----------------------
    gold_checks = {}
    for key, expected in world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure = figures.get((metric_id, entity_id or None))
        gold_checks[key] = bool(figure) and figure.value == expected
    results["gold_questions"] = len(gold_checks)
    results["gold_passed"] = sum(gold_checks.values())
    results["gold_failures"] = [k for k, ok in gold_checks.items() if not ok]

    # -- gate: traceability 100% ------------------------------------------
    traced = [
        f for f in second.figures
        if f.definition_pack_version and f.source_versions.batches
        and f.status == "verified"
    ]
    results["traceability"] = (
        len(traced) / len(second.figures) if second.figures else 0.0
    )

    # -- gate: consolidation ties, in the eval's own arithmetic -----------
    def val(metric_id, entity_id=None):
        return D(figures[(metric_id, entity_id)].value)

    ties = {
        "consolidated_revenue == sum of entity revenues converted at 1.10":
            val("consolidated_revenue")
            == val("revenue_external", "HLG") + val("revenue_external", "HLD")
            + val("revenue_external", "HLE") * Decimal("1.10"),
        "gross == external + intercompany":
            val("consolidated_gross_revenue")
            == val("consolidated_revenue") + val("consolidated_ic_revenue"),
        "eliminations == paired intercompany revenue":
            val("eliminations_total") == val("consolidated_ic_revenue"),
        "operating income identity":
            val("consolidated_operating_income")
            == val("consolidated_revenue") - val("consolidated_cogs")
            - val("consolidated_opex"),
        "consolidated cash ties":
            val("consolidated_cash")
            == val("cash", "HLG") + val("cash", "HLD")
            + val("cash", "HLE") * Decimal("1.10"),
    }
    results["consolidation_ties"] = ties

    # -- gate: the verified pack signs; the run closes ----------------------
    sign_gate = False
    signed = None
    if second.status == "AWAITING_CONTROLLER":
        signed = service.sign_off(second.pack_id, "sign", "Eval Controller")
        sign_gate = signed.status == "SIGNED_OFF" \
            and service.get_run(run.run_id).status == "CLOSED"
    results["phase_b_status"] = second.status

    october = _evaluate_october(service, signed)
    results.update(october["results"])

    results["gates"] = {
        "planted traps named + blocked": trap_gate,
        "blocked pack refuses sign-off": blocked_refused,
        "superseded pack goes stale": stale_gate,
        "gold figures exact": all(gold_checks.values()),
        "traceability == 1.0": results["traceability"] == 1.0,
        "consolidation ties hold": all(ties.values()),
        "verified pack signs + run closes": sign_gate,
        **october["gates"],
    }
    results["gate_passed"] = all(results["gates"].values())
    return results


def _evaluate_october(september_service, signed_september) -> dict:
    """Act two: October closes comparative over the same store,
    under pack v1.1.0, with September restated after sign-off."""
    out: dict = {"results": {}, "gates": {}}
    if signed_september is None:
        out["gates"] = {
            "october gold figures exact": False,
            "comparatives tie to the signed pack": False,
            "definition changes flagged": False,
            "restatement named with gold figures": False,
            "unacknowledged restatement holds the signature": False,
            "acknowledged restatement signs": False,
            "signed prior pack byte-identical": False,
        }
        return out

    store = september_service.store
    signed_json_at_sign_off = signed_september.model_dump_json()

    september_service.receive_restatement(RESTATEMENT_BATCH_ID)
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    service = CloseService(
        pipeline=pipeline, store=store,
        connector=september_service.connector,
        objects=september_service.objects, pack_def=pack_v110,
    )
    october_world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in october_world.batches])
    pack = service.build_pack(run.run_id)
    figures = _figures(pack)

    gold_checks = {}
    for key, expected in october_world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure = figures.get((metric_id, entity_id or None))
        gold_checks[key] = bool(figure) and figure.value == expected
    out["results"]["october_gold_passed"] = sum(gold_checks.values())
    out["results"]["october_gold_questions"] = len(gold_checks)
    out["gates"]["october gold figures exact"] = all(gold_checks.values())

    signed_by_key = {
        (f.metric_id, f.entity_id): f for f in signed_september.figures
    }
    ties_ok = len(pack.comparatives) == len(signed_september.figures) \
        and all(
            c.prior_value == signed_by_key[(c.metric_id, c.entity_id)].value
            and c.prior_pack_id == signed_september.pack_id
            for c in pack.comparatives
        )
    out["gates"]["comparatives tie to the signed pack"] = ties_ok

    flagged = {c.metric_id for c in pack.comparatives if c.definition_changed}
    out["gates"]["definition changes flagged"] = \
        flagged == DEFINITION_CHANGED_METRICS

    affected = {}
    if pack.restatement is not None:
        affected = {
            (f"{f.metric_id}@{f.entity_id}" if f.entity_id else f.metric_id):
                (f.signed_value, f.recomputed_value)
            for f in pack.restatement.affected_figures
        }
    out["results"]["restatement_affected"] = {
        k: list(v) for k, v in affected.items()
    }
    out["gates"]["restatement named with gold figures"] = (
        affected == RESTATEMENT_AFFECTED
        and [v.code for v in pack.variances] == ["RESTATED_PRIOR_PERIOD"]
        and pack.restatement is not None
        and pack.restatement.restated_batch_ids == [RESTATEMENT_BATCH_ID]
    )

    refused = False
    try:
        service.sign_off(pack.pack_id, "sign", "Eval Controller")
    except GateError:
        refused = True
    out["gates"]["unacknowledged restatement holds the signature"] = refused

    signs = False
    if refused:
        service.acknowledge_restatement(
            pack.pack_id, "Eval Controller",
            "September restatement reviewed; comparatives stand as signed.")
        signed_october = service.sign_off(pack.pack_id, "sign",
                                          "Eval Controller")
        signs = signed_october.status == "SIGNED_OFF" \
            and signed_october.restatement_acknowledgement is not None \
            and [v.code for v in signed_october.variances] == [
                "RESTATED_PRIOR_PERIOD"]
    out["gates"]["acknowledged restatement signs"] = signs

    out["gates"]["signed prior pack byte-identical"] = (
        store.get_pack(signed_september.pack_id).model_dump_json()
        == signed_json_at_sign_off
    )
    out["results"]["october_status"] = pack.status
    return out


def main() -> int:
    results = evaluate()
    out_paths = [
        Path(__file__).resolve().parent / "results.json",
        Path(__file__).resolve().parents[1] / "src" / "aidnn_close_agent"
        / "data" / "eval_results.json",
    ]
    for path in out_paths:
        path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    if os.environ.get("EVAL_LIVE") == "1":
        print("\nEVAL_LIVE=1: a live aidnn run is reported-not-gated; "
              "it requires a deployed workspace (AIDNN_WORKSPACE_URL) "
              "and is not attempted by this runner in the offline "
              "gate environment.")
    print("\nGATE:", "PASS" if results["gate_passed"] else "FAIL")
    return 0 if results["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
