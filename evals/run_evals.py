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

from aidnn_close_agent.datasets import PERIOD, build_world  # noqa: E402
from aidnn_close_agent.demo import build_demo_service  # noqa: E402
from aidnn_close_agent.errors import GateError  # noqa: E402
from aidnn_close_agent.fx import D  # noqa: E402


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
    if second.status == "AWAITING_CONTROLLER":
        signed = service.sign_off(second.pack_id, "sign", "Eval Controller")
        sign_gate = signed.status == "SIGNED_OFF" \
            and service.get_run(run.run_id).status == "CLOSED"
    results["phase_b_status"] = second.status

    results["gates"] = {
        "planted traps named + blocked": trap_gate,
        "blocked pack refuses sign-off": blocked_refused,
        "superseded pack goes stale": stale_gate,
        "gold figures exact": all(gold_checks.values()),
        "traceability == 1.0": results["traceability"] == 1.0,
        "consolidation ties hold": all(ties.values()),
        "verified pack signs + run closes": sign_gate,
    }
    results["gate_passed"] = all(results["gates"].values())
    return results


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
