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

Both packs also carry the **intercompany agreement check** —
every IC pair keyed by counterparty, seller's stated figure
against buyer's. Its gates:

- **pairs enumerated completely** — September's first attempt
  names its planted one-sided pair (``IC_ONE_SIDED``, the leg
  HLE never booked); both signed packs carry exactly the one
  HLD → HLE pair, ``AGREED``, with the stated figures exact
  (September $55,000 against €50,000 at 1.10; October $61,600
  against €55,000 at 1.12), no IC variance, no figure flagged;
- **ic in the bundles** — both evidence bundles carry the
  intercompany section with the agreed pair;
- **the staged disagreement** — a variant October extract
  (HLE books the purchase at €54,500) closes on a fresh store:
  the pack is BLOCKED by exactly one ``IC_DISAGREEMENT``
  naming both figures and the $560.00 difference, the pair
  record equals the planted gold, exactly the consolidated
  figures standing on the pair are flagged, every entity
  figure still equals its gold, and sign-off is refused.

Both closes also carry **rate provenance** — the rate table
itself on every figure's stamp, not just its version. Its
gates:

- **the stamp is the table** — September's signed pack and
  every figure on it stamp rate table v2 (EUR 1.10); October's
  pack stamps v3 (EUR 1.12);
- **rate changes flagged exactly** — October's comparatives
  flag RATE_CHANGED on exactly the consolidated figures whose
  derivation converts EUR money (``RATE_CHANGED_METRICS``,
  enumerated by hand — including ``consolidated_ic_revenue``
  and ``pipeline_open`` staying unflagged, because no EUR flows
  through their conversions), and never on an entity figure;
  the flux schedule states both table versions on its face
  and its entries' flags agree;
- **provenance in the bundle** — October's bundle carries both
  stamped tables and the EUR change (1.10 → 1.12) by name;
- **the verifier's basis** — a staged fourth act replays
  October's figures against an FX batch edited in place
  (EUR 1.15 under the same batch id and version): the
  verifier names RATE_TABLE_MISMATCH and still reproduces
  every figure at the stamped table. Figures re-stamped with
  a table they were not computed at are named per figure —
  converted off-stamp — with no FIGURE_MISMATCH blurring the
  break.

A fifth act exercises **variance disposition** — the second
honest exit from a block. The staged October disagreement
closes on a fresh store; the controller accepts both of its
blocking variances in writing; the rebuild is presented and
signed with the acceptances on its face; and November (the
same trading one month on, the break still booked) opens the
carried items. Its gates:

- **disposition requires a named controller and a reason** —
  both refusals raised, each naming its ground;
- **a non-blocking flag cannot be dispositioned** —
  ``DEFINITION_CHANGED`` is a comparison flag, not a variance,
  and the refusal says there is no blocking variance by that
  name to accept;
- **one undispositioned blocker still refuses** — with only
  one of the two variances accepted, the rebuild stays
  BLOCKED and sign-off is refused;
- **all dispositioned: the pack presents and signs** — every
  blocking variance covered, the rebuild reaches the gate and
  a named controller signs it;
- **the verifier's verdict is unchanged by disposition** —
  the signed pack's variances are the blocked pack's, code
  and detail word for word, and its figures identical;
- **dispositions on the signed face and in the bundle** —
  the signed pack lists both acceptances with actor and
  reason, and its evidence bundle carries the dispositions
  section beside the variances;
- **the carried item opens the next period, retested** —
  November's pack opens both items with their origin
  (period, pack, controller, reason quoted), the retest
  verdict is STILL_PRESENT, and the pack blocks again;
- **the second carry is counted** — accepted again in
  November, the new records and the signed face state
  carry 2 with the October origin.

A sixth act exercises **definition change governance** —
the front door a new definition-pack version must walk
through. September and October close and sign canonically on
a fresh store; a candidate v1.2.0 (insurance leaves operating
expenses for its own line) is measured, activated, and put in
charge of November. Its gates:

- **activation without a dry-run refused by name** — the
  impact must exist before the act;
- **the dry-run reproduces the hand-computed change list** —
  the moved figures with their old → new values and deltas,
  the added figures, no drops, no material move, no variance
  family change, no baseline discrepancy: gold stated as
  literals in datasets, derived from the journals by hand;
- **the dry-run is byte-stable and inert** — recomputation
  returns the same record and digest, and neither the
  dry-run nor the activation alters a signed pack by a byte;
- **activation refusals name their grounds** — an unnamed
  actor, a missing reason, a signed from-period, and the
  already-governing version are each refused in words;
- **the next period selects the activated version** — a
  November run created on a service still wired to v1.1.0
  records v1.2.0, builds under it, and its figures are the
  candidate's figures (the October gold with the split
  applied);
- **the first governed pack states the change** — version
  from → to, the activation, and the dry-run headline counts
  ride the pack's face;
- **the bundle carries the governance** — November's
  evidence bundle cites the activation and the dry-run with
  its digest; September's bundle, from a close with no
  change to state, projects ``definition_change: null``.

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

from aidnn_close_agent.connectors import DatasetConnector  # noqa: E402
from aidnn_close_agent import verifier as verifier_module  # noqa: E402
from aidnn_close_agent.datasets import (  # noqa: E402
    DEFINITION_CHANGED_METRICS,
    IC_VARIANT_BATCH_ID,
    IC_VARIANT_FLAGGED,
    IC_VARIANT_PAIR,
    PERIOD,
    PERIOD_NOVEMBER,
    PERIOD_OCTOBER,
    RATE_CHANGED_METRICS,
    RESTATEMENT_AFFECTED,
    RESTATEMENT_BATCH_ID,
    V120_CHANGED_METRICS,
    V120_DRY_RUN_ADDED,
    V120_DRY_RUN_MOVED,
    V120_NOVEMBER_FIGURES,
    build_november_world,
    build_october_world,
    build_world,
    october_ic_variant_batch,
)
from aidnn_close_agent.definitions import (  # noqa: E402
    load_definition_pack_version,
)
from aidnn_close_agent.demo import build_demo_service  # noqa: E402
from aidnn_close_agent.engine_offline import OfflineFinanceEngine  # noqa: E402
from aidnn_close_agent.errors import EvidenceError, GateError  # noqa: E402
from aidnn_close_agent.fx import D, RateTable  # noqa: E402
from aidnn_close_agent.graph import PackPipeline  # noqa: E402
from aidnn_close_agent.object_store import InMemoryObjectStore  # noqa: E402
from aidnn_close_agent.service import CloseService  # noqa: E402
from aidnn_close_agent.store import InMemoryCloseStore  # noqa: E402


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

    # -- gate: the stamp is the table itself -------------------------
    stamp_gate = signed is not None \
        and signed.source_versions.fx_table is not None \
        and signed.source_versions.fx_table.version == 2 \
        and signed.source_versions.fx_table.rates == {"EUR": "1.10"} \
        and all(
            f.source_versions.fx_table == signed.source_versions.fx_table
            for f in signed.figures
        )
    results["signed_stamp"] = (
        signed.source_versions.fx_table.model_dump()
        if signed is not None
        and signed.source_versions.fx_table is not None else None)

    evidence = _evaluate_evidence(service, signed)
    results.update(evidence["results"])

    october = _evaluate_october(service, signed)
    results.update(october["results"])

    ic_variant = _evaluate_ic_variant()
    results.update(ic_variant["results"])

    rate_checks = _evaluate_rate_checks()
    results.update(rate_checks["results"])

    dispositions = _evaluate_dispositions()
    results.update(dispositions["results"])

    governance = _evaluate_governance()
    results.update(governance["results"])

    first_pair_ok = (
        len(first.ic_pairs) == 1
        and first.ic_pairs[0].verdict == "ONE_SIDED"
        and first.ic_pairs[0].missing_side == "cost"
        and first.ic_pairs[0].seller_amount == "55000.00"
        and first.ic_pairs[0].buyer_amount is None
    )
    signed_pair_ok = signed is not None and (
        len(signed.ic_pairs) == 1
        and signed.ic_pairs[0].verdict == "AGREED"
        and signed.ic_pairs[0].seller_amount == "55000.00"
        and signed.ic_pairs[0].buyer_amount == "50000.00"
        and signed.ic_pairs[0].buyer_amount_basis == "55000.00"
        and signed.ic_pairs[0].difference == "0.00"
        and not any(f.ic_disagreement for f in signed.figures)
    )
    results["ic_signed_pair"] = (
        signed.ic_pairs[0].model_dump()
        if signed is not None and len(signed.ic_pairs) == 1 else None)

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
        "ic one-sided pair named in the first attempt": first_pair_ok,
        "ic agreed pair silent on the signed pack": signed_pair_ok,
        "evidence bundle carries the ic pairs":
            evidence["gates"]["ic_pairs"],
        "rate table stamped on the signed pack": stamp_gate,
        **october["gates"],
        **ic_variant["gates"],
        **rate_checks["gates"],
        **dispositions["gates"],
        **governance["gates"],
    }
    results["gate_passed"] = all(results["gates"].values())
    return results


def _evaluate_evidence(service, signed) -> dict:
    """The audit evidence bundle for September's signed pack:
    complete, digest-true, and byte-identical on regeneration."""
    out: dict = {"results": {}, "gates": {
        "complete": False, "byte_identical": False,
        "digest_matches": False, "ic_pairs": False}}
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

    section = document.get("intercompany") or []
    out["gates"]["ic_pairs"] = (
        len(section) == 1
        and section[0]["verdict"] == "AGREED"
        and section[0]["seller_id"] == "HLD"
        and section[0]["buyer_id"] == "HLE"
        and section[0]["seller_amount"] == "55000.00"
        and section[0]["buyer_amount"] == "50000.00"
        and section[0]["buyer_amount_basis"] == "55000.00"
        and section[0]["difference"] == "0.00"
    )

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
            "ic pair agrees in october": False,
            "october bundle carries the ic pairs": False,
            "rate changes flagged exactly": False,
            "flux states both rate tables": False,
            "october bundle carries rate provenance": False,
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

    oct_pair = pack.ic_pairs[0] if len(pack.ic_pairs) == 1 else None
    out["gates"]["ic pair agrees in october"] = (
        oct_pair is not None
        and oct_pair.verdict == "AGREED"
        and oct_pair.seller_amount == "61600.00"
        and oct_pair.buyer_amount == "55000.00"
        and oct_pair.buyer_amount_basis == "61600.00"
        and oct_pair.difference == "0.00"
        and not any(f.ic_disagreement for f in pack.figures)
    )
    out["results"]["ic_october_pair"] = (
        oct_pair.model_dump() if oct_pair is not None else None)

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

    rate_flagged = {
        c.metric_id for c in pack.comparatives if c.rate_changed
    }
    out["results"]["rate_changed_metrics"] = sorted(rate_flagged)
    out["gates"]["rate changes flagged exactly"] = (
        rate_flagged == RATE_CHANGED_METRICS
        and not any(
            c.rate_changed for c in pack.comparatives if c.entity_id)
    )

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
        out["gates"]["flux states both rate tables"] = (
            flux.prior_fx_version == 2 and flux.current_fx_version == 3
            and {e.metric_id for e in flux.entries if e.rate_changed}
            == RATE_CHANGED_METRICS
            and all("rate changed" in e.note
                    for e in flux.entries if e.rate_changed)
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

    ic_bundle_ok = False
    if signed_october is not None:
        def _section(doc):
            section = doc.get("intercompany") or []
            return section[0] if len(section) == 1 else None

        oct_section = _section(october_doc)
        sep_section = _section(september_doc)
        ic_bundle_ok = (
            oct_section is not None
            and oct_section["verdict"] == "AGREED"
            and oct_section["seller_amount"] == "61600.00"
            and oct_section["buyer_amount"] == "55000.00"
            and sep_section is not None
            and sep_section["verdict"] == "AGREED"
        )
    out["gates"]["october bundle carries the ic pairs"] = ic_bundle_ok

    fx_bundle_ok = False
    if signed_october is not None:
        fx = october_doc.get("fx") or {}
        current = fx.get("current") or {}
        prior = fx.get("prior") or {}
        fx_bundle_ok = (
            current.get("version") == 3
            and current.get("rates") == {"EUR": "1.12"}
            and prior.get("version") == 2
            and prior.get("rates") == {"EUR": "1.10"}
            and fx.get("rate_changes") == [
                {"currency": "EUR", "prior_rate": "1.10",
                 "current_rate": "1.12"}]
        )
    out["gates"]["october bundle carries rate provenance"] = fx_bundle_ok
    out["results"]["october_status"] = pack.status
    return out


class _VariantConnector:
    """The dataset connector with October's HLE extract swapped
    for the staged intercompany variant — the same staging the
    tests use, behind the same port."""

    name = "dataset-ic-variant"

    def __init__(self, base: DatasetConnector) -> None:
        self._base = base

    def available(self):
        return self._base.available()

    def fetch(self, batch_id: str):
        if batch_id == IC_VARIANT_BATCH_ID:
            return october_ic_variant_batch()
        return self._base.fetch(batch_id)


def _evaluate_ic_variant() -> dict:
    """Act three: October again, on a fresh store, with HLE's
    intercompany purchase understated by €500 — the pair must
    disagree by $560.00 on the close's basis, block the pack,
    flag exactly the consolidated figures standing on it, and
    leave every entity figure at its gold."""
    out: dict = {"results": {}, "gates": {
        "ic disagreement blocks with both figures": False,
        "ic pair record equals the planted gold": False,
        "ic flags mark exactly the consolidated figures on the pair":
            False,
    }}
    store = InMemoryCloseStore()
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    service = CloseService(
        pipeline=pipeline, store=store,
        connector=_VariantConnector(DatasetConnector()),
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)

    disagreements = [v for v in pack.variances
                     if v.code == "IC_DISAGREEMENT"]
    detail = disagreements[0].detail if len(disagreements) == 1 else ""
    refused = False
    try:
        service.sign_off(pack.pack_id, "sign", "Eval Controller")
    except GateError:
        refused = True
    out["gates"]["ic disagreement blocks with both figures"] = (
        pack.status == "BLOCKED"
        and len(disagreements) == 1
        and all(figure in detail for figure in
                ("61600.00", "54500.00", "61040.00", "560.00"))
        and refused
    )

    pair = pack.ic_pairs[0] if len(pack.ic_pairs) == 1 else None
    out["gates"]["ic pair record equals the planted gold"] = (
        pair is not None
        and all(getattr(pair, name) == expected
                for name, expected in IC_VARIANT_PAIR.items())
        and pair.missing_side is None
    )
    out["results"]["ic_variant_pair"] = (
        pair.model_dump() if pair is not None else None)
    out["results"]["ic_variant_status"] = pack.status

    flagged = {f.metric_id for f in pack.figures if f.ic_disagreement}
    entity_gold_ok = True
    for key, expected in world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        if not entity_id:
            continue
        figure = next((f for f in pack.figures
                       if f.metric_id == metric_id
                       and f.entity_id == entity_id), None)
        entity_gold_ok = entity_gold_ok and figure is not None \
            and figure.value == expected and not figure.ic_disagreement
    out["gates"][
        "ic flags mark exactly the consolidated figures on the pair"
    ] = flagged == IC_VARIANT_FLAGGED and entity_gold_ok
    return out


def _evaluate_rate_checks() -> dict:
    """Act four: the verifier's basis. October closes clean on
    a fresh store; its figures are then replayed against a
    batch set whose FX table was edited in place — same batch
    id, same table version, EUR at 1.15 instead of the stamped
    1.12 — and against a dishonest re-stamp. Both breaks must
    be named as rate breaks, and the honest figures must still
    reproduce at the table they stamp."""
    out: dict = {"results": {}, "gates": {
        "edited rate table named, figures reproduce at the stamp":
            False,
        "figure converted off-stamp named per figure": False,
    }}
    store = InMemoryCloseStore()
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    service = CloseService(
        pipeline=pipeline, store=store,
        connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    if pack.status != "AWAITING_CONTROLLER":
        return out
    batches = [store.get_batch(bid) for bid in pack.source_versions.batches]

    edited = [
        batch.model_copy(update={"rate_table": RateTable(
            version=3, reporting_currency="USD", rates={"EUR": "1.15"})})
        if batch.kind == "fx" else batch
        for batch in batches
    ]
    report = verifier_module.verify(pack_v110, edited, pack.figures)
    out["gates"]["edited rate table named, figures reproduce at the stamp"] = (
        [v.code for v in report.variances] == ["RATE_TABLE_MISMATCH"]
        and all(check.ok for check in report.checks)
        and not report.passed
    )
    out["results"]["rate_edited_variance"] = (
        report.variances[0].detail if report.variances else None)

    restamped = [
        figure.model_copy(update={
            "source_versions": figure.source_versions.model_copy(
                update={"fx_table": RateTable(
                    version=3, reporting_currency="USD",
                    rates={"EUR": "1.10"})}),
        })
        for figure in pack.figures
    ]
    report = verifier_module.verify(pack_v110, batches, restamped)
    codes = [v.code for v in report.variances]
    per_figure = {
        v.metric_id for v in report.variances
        if v.code == "RATE_TABLE_MISMATCH" and v.metric_id is not None
    }
    out["gates"]["figure converted off-stamp named per figure"] = (
        "FIGURE_MISMATCH" not in codes
        and "consolidated_revenue" in per_figure
        and "consolidated_cash" in per_figure
        and not report.passed
    )
    out["results"]["rate_offstamp_figures"] = sorted(per_figure)
    return out


class _WorldConnector:
    """Serves one staged world's batches — November's route
    into act five."""

    name = "world"

    def __init__(self, world) -> None:
        self._batches = {b.batch_id: b for b in world.batches}

    def available(self):
        return list(self._batches)

    def fetch(self, batch_id: str):
        return self._batches[batch_id]


def _evaluate_dispositions() -> dict:
    """Act five: variance disposition. The staged October
    disagreement is accepted in writing by a named controller,
    the rebuild signs with the acceptances on its face and the
    verifier's verdict word-for-word unchanged, and November
    opens the carried items — still present, blocking again,
    accepted a second time with the count stated."""
    controller = "Eval Controller"
    reason_pair = (
        "HLE's EUR 500 understatement is a known booking error "
        "in their close, confirmed with HLE's controller; "
        "immaterial to the group. Accepted for October and "
        "carried — it must clear in November's close."
    )
    reason_leg = (
        "The unmatched leg is the same understatement seen from "
        "the elimination side; accepted with it, on the same terms."
    )
    gates = {
        "disposition requires a named controller and a reason": False,
        "a non-blocking flag cannot be dispositioned": False,
        "one undispositioned blocker still refuses sign-off": False,
        "all dispositioned: the pack presents and signs": False,
        "the verifier's verdict is unchanged by disposition": False,
        "dispositions on the signed face and in the bundle": False,
        "carried item opens next period, retested still present": False,
        "second carry counted on the face": False,
    }
    out: dict = {"results": {}, "gates": gates}
    store = InMemoryCloseStore()
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    service = CloseService(
        pipeline=pipeline, store=store,
        connector=_VariantConnector(DatasetConnector()),
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    blocked = service.build_pack(run.run_id)
    if blocked.status != "BLOCKED":
        return out
    blocked_variances = [(v.code, v.detail) for v in blocked.variances]
    blocked_figures = [(f.metric_id, f.entity_id, f.value, f.status)
                         for f in blocked.figures]

    refusals = []
    for kwargs in ({"actor": "", "reason": reason_pair},
                   {"actor": controller, "reason": ""}):
        try:
            service.record_disposition(blocked.pack_id,
                                       code="IC_DISAGREEMENT", **kwargs)
        except GateError as exc:
            refusals.append(str(exc))
    gates["disposition requires a named controller and a reason"] = (
        len(refusals) == 2
        and "must name its controller" in refusals[0]
        and "must carry a reason" in refusals[1]
    )
    try:
        service.record_disposition(blocked.pack_id,
                                   code="DEFINITION_CHANGED",
                                   actor=controller,
                                   reason="accept the flag")
        flag_refused = ""
    except GateError as exc:
        flag_refused = str(exc)
    gates["a non-blocking flag cannot be dispositioned"] = \
        "carries no blocking variance DEFINITION_CHANGED" in flag_refused

    service.record_disposition(blocked.pack_id, code="IC_DISAGREEMENT",
                               actor=controller, reason=reason_pair)
    partial = service.build_pack(run.run_id)
    sign_refused = False
    try:
        service.sign_off(partial.pack_id, "sign", controller)
    except GateError:
        sign_refused = True
    gates["one undispositioned blocker still refuses sign-off"] = (
        partial.status == "BLOCKED" and sign_refused)

    service.record_disposition(blocked.pack_id, code="UNMATCHED_IC_LEG",
                               actor=controller, reason=reason_leg)
    presented = service.build_pack(run.run_id)
    signed = None
    if presented.status == "AWAITING_CONTROLLER":
        signed = service.sign_off(presented.pack_id, "sign", controller,
                                  "accepted on the record")
    gates["all dispositioned: the pack presents and signs"] = (
        signed is not None and signed.status == "SIGNED_OFF")
    if signed is None:
        return out
    gates["the verifier's verdict is unchanged by disposition"] = (
        [(v.code, v.detail) for v in signed.variances] == blocked_variances
        and [(f.metric_id, f.entity_id, f.value, f.status)
             for f in signed.figures] == blocked_figures
    )
    out["results"]["dispositioned_variances"] = [
        v.code for v in signed.variances]
    out["results"]["signed_dispositions"] = [
        d.model_dump() for d in signed.dispositions]

    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    gates["dispositions on the signed face and in the bundle"] = (
        len(signed.dispositions) == 2
        and all(d.actor == controller and d.reason
                for d in signed.dispositions)
        and document["dispositions"] is not None
        and len(document["dispositions"]) == 2
        and {d["code"] for d in document["dispositions"]}
        == {"IC_DISAGREEMENT", "UNMATCHED_IC_LEG"}
    )

    november_world = build_november_world("54500.00")
    november = CloseService(
        pipeline=PackPipeline(
            engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
            checkpointer=MemorySaver()),
        store=store, connector=_WorldConnector(november_world),
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )
    nov_run = november.create_run(PERIOD_NOVEMBER)
    november.ingest(nov_run.run_id,
                    [b.batch_id for b in november_world.batches])
    nov_pack = november.build_pack(nov_run.run_id)
    items = nov_pack.opening_items
    gates["carried item opens next period, retested still present"] = (
        nov_pack.status == "BLOCKED"
        and len(items) == 2
        and all(item.retest == "STILL_PRESENT" for item in items)
        and all(item.origin_period == PERIOD_OCTOBER for item in items)
        and all(item.dispositioned_by == controller for item in items)
        and {item.code: item.reason for item in items}.get(
            "IC_DISAGREEMENT") == reason_pair
    )
    out["results"]["november_opening_items"] = [
        item.model_dump() for item in items]

    november.record_disposition(nov_pack.pack_id, code="IC_DISAGREEMENT",
                                actor=controller, reason=reason_pair)
    november.record_disposition(nov_pack.pack_id, code="UNMATCHED_IC_LEG",
                                actor=controller, reason=reason_leg)
    nov_presented = november.build_pack(nov_run.run_id)
    nov_signed = None
    if nov_presented.status == "AWAITING_CONTROLLER":
        nov_signed = november.sign_off(nov_presented.pack_id, "sign",
                                       controller, "second carry")
    gates["second carry counted on the face"] = (
        nov_signed is not None
        and len(nov_signed.dispositions) == 2
        and all(d.carry_number == 2 for d in nov_signed.dispositions)
        and all(d.origin_period == PERIOD_OCTOBER
                for d in nov_signed.dispositions)
    )
    out["results"]["november_second_carry"] = (
        [d.model_dump() for d in nov_signed.dispositions]
        if nov_signed is not None else [])
    return out


def _evaluate_governance() -> dict:
    """Act six: definition change governance. September and
    October close and sign canonically on a fresh store; the
    v1.2.0 candidate (insurance out of opex, onto its own
    line) is dry-run over signed October, activated from
    November by a named controller, and November — created on
    a service still wired to v1.1.0 — is selected onto it by
    rule, states the change on its face, and cites the act and
    the impact in its evidence bundle."""
    controller = "Eval Controller"
    reason = (
        "Insurance premiums are reported to the board on their "
        "own line from November; they leave operating expenses "
        "and stand separately. Measured first, per the dry-run."
    )
    gates = {
        "governance: activation without a dry-run refused by name":
            False,
        "governance: dry-run reproduces the hand-computed change list":
            False,
        "governance: dry-run byte-stable; signed packs untouched":
            False,
        "governance: activation refusals name their grounds": False,
        "governance: next period selects the activated version":
            False,
        "governance: first governed pack states the change": False,
        "governance: bundle carries the activation and the dry-run":
            False,
    }
    out: dict = {"results": {}, "gates": gates}
    store = InMemoryCloseStore()
    pack_v100 = load_definition_pack_version("harborlight-close", "1.0.0")
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")

    def _service(pack, connector=None):
        return CloseService(
            pipeline=PackPipeline(
                engine=OfflineFinanceEngine(), store=store, pack=pack,
                checkpointer=MemorySaver()),
            store=store, connector=connector or DatasetConnector(),
            objects=InMemoryObjectStore(), pack_def=pack,
        )

    september = _service(pack_v100)
    world = build_world()
    run = september.create_run(PERIOD)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches_in_phase("initial")])
    september.build_pack(run.run_id)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches_in_phase("late")])
    rebuilt = september.build_pack(run.run_id)
    signed_september = september.sign_off(rebuilt.pack_id, "sign",
                                          controller)
    if signed_september.status != "SIGNED_OFF":
        return out

    september.receive_restatement(RESTATEMENT_BATCH_ID)
    october = _service(pack_v110)
    october_world = build_october_world()
    oct_run = october.create_run(PERIOD_OCTOBER)
    october.ingest(oct_run.run_id,
                   [b.batch_id for b in october_world.batches])
    oct_pack = october.build_pack(oct_run.run_id)
    october.acknowledge_restatement(
        oct_pack.pack_id, controller,
        "September restatement reviewed; comparatives stand as signed.")
    signed_october = october.sign_off(oct_pack.pack_id, "sign", controller)
    if signed_october.status != "SIGNED_OFF":
        return out
    september_json = store.get_pack(
        signed_september.pack_id).model_dump_json()
    october_json = store.get_pack(signed_october.pack_id).model_dump_json()

    # -- the act may not precede its evidence ---------------------
    refused = ""
    try:
        october.activate_definition_pack("1.2.0", PERIOD_NOVEMBER,
                                         controller, reason)
    except GateError as exc:
        refused = str(exc)
    gates["governance: activation without a dry-run refused by name"] = \
        "no dry-run on record" in refused

    # -- the dry-run, against hand-computed gold -------------------
    record = october.dry_run_definition_change("1.2.0")
    report = record.report
    moved = {
        (d.metric_id, d.entity_id):
            (d.base_value, d.candidate_value, d.delta)
        for d in report.moved
    }
    added = {(f.metric_id, f.entity_id): f.value for f in report.added}
    gates["governance: dry-run reproduces the hand-computed change list"] = (
        moved == V120_DRY_RUN_MOVED
        and added == V120_DRY_RUN_ADDED
        and report.dropped == []
        and set(report.changed_metrics) == V120_CHANGED_METRICS
        and report.material_count == 0
        and not any(d.material for d in report.moved)
        and report.variance_families_base == []
        and report.variance_families_candidate == []
        and report.baseline_discrepancies == []
        and report.reference_pack_id == signed_october.pack_id
        and report.base_version == "1.1.0"
        and all(d.signed_pack_value == d.base_value for d in report.moved)
    )
    out["results"]["governance_dry_run"] = record.model_dump()

    # -- the dry-run is a record, not a ritual ----------------------
    again = october.dry_run_definition_change("1.2.0")
    gates["governance: dry-run byte-stable; signed packs untouched"] = (
        again.dry_run_id == record.dry_run_id
        and again.digest == record.digest
        and again.computed_at == record.computed_at
        and store.list_activations() == []
        and store.get_pack(signed_september.pack_id).model_dump_json()
        == september_json
        and store.get_pack(signed_october.pack_id).model_dump_json()
        == october_json
    )

    # -- the activation's refusals, each naming its ground ----------
    refusals = {}
    for name, kwargs in {
        "actor": {"version": "1.2.0", "from_period": PERIOD_NOVEMBER,
                  "actor": "", "reason": reason},
        "reason": {"version": "1.2.0", "from_period": PERIOD_NOVEMBER,
                   "actor": controller, "reason": ""},
        "signed": {"version": "1.2.0", "from_period": PERIOD_OCTOBER,
                   "actor": controller, "reason": reason},
        "active": {"version": "1.1.0", "from_period": PERIOD_NOVEMBER,
                   "actor": controller, "reason": reason},
    }.items():
        try:
            october.activate_definition_pack(**kwargs)
            refusals[name] = ""
        except GateError as exc:
            refusals[name] = str(exc)
    gates["governance: activation refusals name their grounds"] = (
        "must name its actor" in refusals["actor"]
        and "must carry a reason" in refusals["reason"]
        and "already signed" in refusals["signed"]
        and "already governs" in refusals["active"]
    )

    activation = october.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, controller, reason)
    out["results"]["governance_activation"] = activation.model_dump()
    history_untouched = (
        store.get_pack(signed_september.pack_id).model_dump_json()
        == september_json
        and store.get_pack(signed_october.pack_id).model_dump_json()
        == october_json
        and signed_september.definition_pack_version == "1.0.0"
        and signed_october.definition_pack_version == "1.1.0"
    )

    # -- November: selected by rule, not by wiring -------------------
    november_world = build_november_world("55000.00")
    november = _service(pack_v110, connector=_WorldConnector(november_world))
    nov_run = november.create_run(PERIOD_NOVEMBER)
    november.ingest(nov_run.run_id,
                    [b.batch_id for b in november_world.batches])
    nov_pack = november.build_pack(nov_run.run_id)
    nov_figures = {(f.metric_id, f.entity_id): f.value
                   for f in nov_pack.figures}
    figures_ok = all(
        nov_figures.get(key) == expected
        for key, expected in V120_NOVEMBER_FIGURES.items()
    )
    for key, expected in october_world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure_key = (metric_id, entity_id or None)
        if figure_key in V120_NOVEMBER_FIGURES:
            continue
        figures_ok = figures_ok and nov_figures.get(figure_key) == expected
    gates["governance: next period selects the activated version"] = (
        nov_run.definition_pack_version == "1.2.0"
        and nov_pack.definition_pack_version == "1.2.0"
        and figures_ok
        and history_untouched
    )
    out["results"]["governance_november_pack"] = nov_pack.pack_id

    change = nov_pack.definition_change
    gates["governance: first governed pack states the change"] = (
        change is not None
        and change.from_version == "1.1.0"
        and change.to_version == "1.2.0"
        and change.from_period == PERIOD_NOVEMBER
        and change.activation_id == activation.activation_id
        and change.actor == controller
        and change.reason == reason
        and change.dry_run_id == record.dry_run_id
        and change.dry_run_digest == record.digest
        and (change.moved_count, change.added_count,
             change.dropped_count, change.material_count) == (4, 4, 0, 0)
    )

    signed_november = None
    if nov_pack.status == "AWAITING_CONTROLLER":
        signed_november = november.sign_off(
            nov_pack.pack_id, "sign", controller,
            "first close under v1.2.0")
    bundle_ok = False
    september_bundle_ok = False
    if signed_november is not None:
        november.generate_evidence(signed_november.pack_id)
        data, _ = november.evidence_download(signed_november.pack_id,
                                             "json")
        document = json.loads(data)
        section = document.get("definition_change") or {}
        section_activation = section.get("activation") or {}
        section_run = section.get("dry_run") or {}
        bundle_ok = (
            section_activation.get("activation_id")
            == activation.activation_id
            and section_activation.get("to_version") == "1.2.0"
            and section_activation.get("actor") == controller
            and section_run.get("dry_run_id") == record.dry_run_id
            and section_run.get("digest") == record.digest
            and len((section_run.get("report") or {}).get("moved", [])) == 4
        )
        september.generate_evidence(signed_september.pack_id)
        sept_data, _ = september.evidence_download(
            signed_september.pack_id, "json")
        september_bundle_ok = \
            json.loads(sept_data)["definition_change"] is None
    gates["governance: bundle carries the activation and the dry-run"] = \
        bundle_ok and september_bundle_ok
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
