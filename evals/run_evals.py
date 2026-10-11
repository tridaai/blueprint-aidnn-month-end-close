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

Both signed packs then generate their **audit evidence
bundles** — the projection an external auditor re-performs
from. Its gates:

- **bundle complete** — the September bundle carries all 25
  figures with the definition entry reproduced from the pack
  version and the recorded verifier verdict, the full source
  manifest (every stamped batch, at its version, with its
  recorded hash), and the sign-off record with the checklist
  state at signing;
- **byte-identical regeneration** — the same pack regenerates
  the same bytes and the same record;
- **digest matches** — the record's SHA-256 is the digest of
  the stored bundle bytes;
- **generation refused for the blocked pack** — evidence for
  an unsigned close is a false artifact and is refused with
  the state named;
- **the restated pack's bundle** — October's bundle carries
  the comparatives with their signed-pack citations, the
  restatement's affected figures, and the acknowledgement.

October's pack also carries the **flux schedule** — every
comparative figure's movement decomposed by entity and by
account. Its gates:

- **flux identities** — every entry's by-entity lines sum to
  its movement exactly, and its by-account lines do too where
  the definition allows an account split (Decimal-exact);
- **flux materiality** — the schedule flags the planted big
  mover (the pipeline drop) and the large revenue movement,
  and leaves the quiet figures unflagged;
- **flux in the bundle** — October's evidence bundle carries
  the schedule's 25 entries; September's bundle, from a close
  that predates the schedule, states ``flux: null``.

A live-engine run (EVAL_LIVE=1, FINANCE_ENGINE=aidnn with a
workspace configured) is reported, never gated — it measures
the deployment's engine, not this code.
"""

from __future__ import annotations

import hashlib
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
from aidnn_close_agent.errors import EvidenceError, GateError  # noqa: E402
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

    # -- gate: no evidence bundle for an unsigned close ----------------
    # Attempted now, while the first pack stands BLOCKED: an
    # auditor bundle for it would be a false artifact.
    blocked_evidence_refused = False
    try:
        service.generate_evidence(first.pack_id)
    except EvidenceError as exc:
        blocked_evidence_refused = "BLOCKED" in str(exc)

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

    evidence = _evaluate_evidence(service, signed)
    results.update(evidence["results"])

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
        "evidence bundle complete": evidence["gates"]["complete"],
        "evidence regenerates byte-identical":
            evidence["gates"]["byte_identical"],
        "evidence digest matches stored bytes":
            evidence["gates"]["digest_matches"],
        "evidence refused for the blocked pack": blocked_evidence_refused,
        **october["gates"],
    }
    results["gate_passed"] = all(results["gates"].values())
    return results


def _evaluate_evidence(service, signed) -> dict:
    """The audit evidence bundle for September's signed pack:
    complete, digest-true, and byte-identical on regeneration."""
    out: dict = {"results": {}, "gates": {
        "complete": False, "byte_identical": False,
        "digest_matches": False}}
    if signed is None:
        return out
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)

    pack_figures = {(f.metric_id, f.entity_id): f for f in signed.figures}
    figures_ok = len(document["figures"]) == len(pack_figures) == 25 \
        and all(
            entry["value"]
            == pack_figures[(entry["metric_id"], entry["entity_id"])].value
            and entry["verifier_verdict"] == "verified"
            and entry["definition"] == service.pack_def.metric(
                entry["metric_id"]).model_dump()
            for entry in document["figures"]
        )
    manifest = {m["batch_id"]: m for m in document["source_manifest"]}
    manifest_ok = set(manifest) == set(signed.source_versions.batches) \
        and all(
            m["sha256"]
            and m["sha256"] == service.store.get_batch(m["batch_id"]).sha256
            and m["version"] == signed.source_versions.batches[m["batch_id"]]
            for m in manifest.values()
        )
    sign_off_ok = (
        document["sign_off"]["actor"] == "Eval Controller"
        and document["sign_off"]["run_status"] == "CLOSED"
        and document["sign_off"]["missing_sources"] == []
    )
    out["gates"]["complete"] = figures_ok and manifest_ok and sign_off_ok
    out["gates"]["digest_matches"] = \
        hashlib.sha256(data).hexdigest() == record.sha256

    again = service.generate_evidence(signed.pack_id)
    again_data, _ = service.evidence_download(signed.pack_id, "json")
    out["gates"]["byte_identical"] = (
        again.sha256 == record.sha256 and again_data == data
        and again.generated_at == record.generated_at
    )
    out["results"]["evidence_figures"] = len(document["figures"])
    out["results"]["evidence_manifest"] = len(document["source_manifest"])
    out["results"]["evidence_sha256"] = record.sha256
    return out


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
            "restated bundle carries restatement + acknowledgement": False,
            "flux identities hold for every comparative figure": False,
            "flux materiality flags the big movers": False,
            "flux definition-changed figures flagged": False,
            "restated bundle carries the flux schedule": False,
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

    flux = pack.flux
    out["gates"]["flux identities hold for every comparative figure"] = (
        flux is not None and len(flux.entries) == 25 and all(
            sum((Decimal(line.amount) for line in e.by_entity), Decimal(0))
            == Decimal(e.movement)
            and (e.by_account is None or sum(
                (Decimal(line.amount) for line in e.by_account),
                Decimal(0)) == Decimal(e.movement))
            for e in flux.entries
        )
    )
    if flux is not None:
        flux_by_key = {(e.metric_id, e.entity_id): e for e in flux.entries}
        out["results"]["flux_material_entries"] = sum(
            1 for e in flux.entries if e.material)
        out["gates"]["flux materiality flags the big movers"] = (
            flux_by_key[("pipeline_open", None)].material
            and flux_by_key[("consolidated_revenue", None)].material
            and not flux_by_key[("cash", "HLD")].material
            and not flux_by_key[("revenue_ic", "HLG")].material
        )
        out["gates"]["flux definition-changed figures flagged"] = (
            {e.metric_id for e in flux.entries if e.definition_changed}
            == DEFINITION_CHANGED_METRICS
            and all("definition change" in e.note
                    for e in flux.entries if e.definition_changed)
        )

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
    signed_october = None
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

    # -- gate: the restated pack's evidence bundle --------------------
    bundle_ok = False
    if signed_october is not None:
        record = service.generate_evidence(signed_october.pack_id)
        data, _ = service.evidence_download(signed_october.pack_id, "json")
        document = json.loads(data)
        affected = {}
        if document["restatement"] is not None:
            affected = {
                (f"{f['metric_id']}@{f['entity_id']}" if f["entity_id"]
                 else f["metric_id"]):
                    (f["signed_value"], f["recomputed_value"])
                for f in document["restatement"]["affected_figures"]
            }
        bundle_ok = (
            affected == RESTATEMENT_AFFECTED
            and document["restatement_acknowledgement"] is not None
            and document["restatement_acknowledgement"]["actor"]
            == "Eval Controller"
            and len(document["comparatives"]) == 25
            and {c["prior_pack_id"] for c in document["comparatives"]}
            == {signed_september.pack_id}
            and hashlib.sha256(data).hexdigest() == record.sha256
        )
        out["results"]["october_evidence_sha256"] = record.sha256
    out["gates"][
        "restated bundle carries restatement + acknowledgement"
    ] = bundle_ok

    flux_bundle_ok = False
    if signed_october is not None:
        october_data, _ = service.evidence_download(
            signed_october.pack_id, "json")
        october_doc = json.loads(october_data)
        service.generate_evidence(signed_september.pack_id)
        september_data, _ = service.evidence_download(
            signed_september.pack_id, "json")
        september_doc = json.loads(september_data)
        revenue = next(
            (e for e in (october_doc["flux"] or {}).get("entries", [])
             if e["metric_id"] == "consolidated_revenue"), None)
        flux_bundle_ok = (
            october_doc["flux"] is not None
            and len(october_doc["flux"]["entries"]) == 25
            and revenue is not None
            and revenue["movement"] == "115140.00"
            and september_doc["flux"] is None
        )
    out["gates"]["restated bundle carries the flux schedule"] = \
        flux_bundle_ok
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
