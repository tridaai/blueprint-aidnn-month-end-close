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

A seventh act exercises **figure drill-down** — every figure
opens into the exact lines it stands on. Its gates:

- **every figure re-performs** — all 25 figures on both
  signed packs drill from their stamped sources and compose
  to the recorded values exactly, and the bundles cite each
  drill by a digest a fresh drill reproduces;
- **the lines are the planted lines** — September's external
  revenue for HLE is exactly the two corrected-extract lines;
  the elimination shows both legs with the EUR leg converted
  at the stamped 1.10; the converted figure converts once per
  entity at the stamp; derived figures compose from their
  operands' drills and stand on no lines of their own, with
  the plan shown as authored data;
- **state is no barrier, and no excuse** — the blocked first
  pack drills with the duplicate journal counted once, and
  the stale pack drills on its own v1 stamps after the world
  moved;
- **the identity bites** — on a fresh store, a source line
  edited under a signed pack's stamps raises DRILL_MISMATCH
  naming the figure, while an FX batch edited in place
  reprices no drill: conversions stand on the stamp.

An eighth act exercises **pre-close readiness** — the close
does not start on missing sources; it says what is missing,
by name. Its gates:

- **complete passes, cited** — September corrected and
  October complete both report READY under their derived
  manifests, and the rebuilt September pack states COMPLETE
  with the manifest cited on its face;
- **failures named** — September on its opening deliveries
  fails on exactly the three version items the derivation
  implies; an October run staged short two extracts fails on
  exactly those two slots;
- **the gate and the override** — the build refuses while
  unready, naming the items; blanket waivers and waivers
  naming non-failing items are refused, as is a waiver for
  a signed period; a waiver covering exactly the amended
  expectation's short item lets October build, and the
  pack's face and its evidence bundle carry the waiver —
  while a waiver on record for a different item unblocks
  nothing;
- **the check is a pure read** — the store is byte-identical
  across it, and the September pack signed in the act is
  byte-identical at the end of everything. The prior
  period's signed state is reported by the check, never
  required — the build defines comparatives over the signed
  record and degrades to absent by design, so there is no
  prior-period gate to stage.

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
from aidnn_close_agent import drill as drill_module  # noqa: E402
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
from aidnn_close_agent import comparatives as comparatives_module  # noqa: E402
from aidnn_close_agent.demo import build_demo_service  # noqa: E402
from aidnn_close_agent.engine_offline import OfflineFinanceEngine  # noqa: E402
from aidnn_close_agent.errors import (  # noqa: E402
    DrillMismatch,
    EvidenceError,
    GateError,
)
from aidnn_close_agent.fx import D, RateTable  # noqa: E402
from aidnn_close_agent.graph import PackPipeline  # noqa: E402
from aidnn_close_agent.object_store import InMemoryObjectStore  # noqa: E402
from aidnn_close_agent.service import CloseService  # noqa: E402
from aidnn_close_agent.store import InMemoryCloseStore  # noqa: E402


def _figures(pack) -> dict:
    return {(f.metric_id, f.entity_id): f for f in pack.figures}


PREPARER = "Eval Preparer"
REVIEWER = "Eval Reviewer"


def _chain(service, pack_id):
    """Walk a pack through the sign-off chain's first two
    acts, so the controller's signature can stand: a named
    preparer states the pack is ready, a named reviewer —
    a different person — states they reviewed it."""
    service.prepare_pack(pack_id, PREPARER)
    service.review_pack(pack_id, REVIEWER,
                        "reviewed the pack's variances, "
                        "dispositions, and readiness statement")


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

    # -- act seven staging: the blocked pack's drill, taken
    # while it stands blocked (the stale drill follows below) --
    blocked_drill = service.figure_drill(first.pack_id, "opex", "HLD")

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
    stale_drill = service.figure_drill(first_after.pack_id, "opex", "HLE")

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
        _chain(service, second.pack_id)
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

    drills = _evaluate_drills(service, signed, blocked_drill,
                              stale_drill)
    results.update(drills["results"])

    drill_tamper = _evaluate_drill_tamper()
    results.update(drill_tamper["results"])

    readiness = _evaluate_readiness()
    results.update(readiness["results"])

    chain = _evaluate_chain()
    results.update(chain["results"])

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
        "evidence bundle cites every drill by digest":
            evidence["gates"]["drills"],
        "rate table stamped on the signed pack": stamp_gate,
        **october["gates"],
        **ic_variant["gates"],
        **rate_checks["gates"],
        **dispositions["gates"],
        **governance["gates"],
        **drills["gates"],
        **drill_tamper["gates"],
        **readiness["gates"],
        **chain["gates"],
    }
    results["gate_passed"] = all(results["gates"].values())
    return results


def _evaluate_evidence(service, signed) -> dict:
    """The audit evidence bundle for September's signed pack:
    complete, digest-true, and byte-identical on regeneration."""
    out: dict = {"results": {}, "gates": {
        "complete": False, "byte_identical": False,
        "digest_matches": False, "ic_pairs": False,
        "drills": False}}
    if signed is None:
        return out
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)

    drill_entries = document.get("drills") or []
    fresh = {
        (e["metric_id"], e["entity_id"]): service.figure_drill(
            signed.pack_id, e["metric_id"], e["entity_id"])
        for e in drill_entries
    }
    out["gates"]["drills"] = (
        len(drill_entries) == 25
        and all(not e["mismatch"] for e in drill_entries)
        and all(
            e["digest"] == drill_module.drill_digest(
                fresh[(e["metric_id"], e["entity_id"])])
            and e["composed_total"]
            == fresh[(e["metric_id"], e["entity_id"])].composed_total
            and e["line_count"]
            == fresh[(e["metric_id"], e["entity_id"])].line_count
            for e in drill_entries
        )
    )
    out["results"]["evidence_drills"] = len(drill_entries)

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
            "drill: october figures foot to their lines": False,
            "drill: october bundle cites every drill by digest": False,
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
        _chain(service, pack.pack_id)
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

    # -- act seven: October's figures drill too --------------------
    october_drills_ok = False
    october_bundle_drills_ok = False
    if signed_october is not None:
        october_drills_ok = all(
            service.figure_drill(
                signed_october.pack_id, f.metric_id, f.entity_id
            ).composed_total == f.value
            for f in signed_october.figures
        )
        entries = october_doc.get("drills") or []
        october_bundle_drills_ok = (
            len(entries) == 25
            and all(not e["mismatch"] for e in entries)
            and all(
                e["digest"] == drill_module.drill_digest(
                    service.figure_drill(
                        signed_october.pack_id, e["metric_id"],
                        e["entity_id"]))
                for e in entries
            )
        )
    out["gates"]["drill: october figures foot to their lines"] = \
        october_drills_ok
    out["gates"]["drill: october bundle cites every drill by digest"] = \
        october_bundle_drills_ok
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
        _chain(service, presented.pack_id)
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
        _chain(november, nov_presented.pack_id)
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
    _chain(september, rebuilt.pack_id)
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
    _chain(october, oct_pack.pack_id)
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
        _chain(november, nov_pack.pack_id)
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


def _evaluate_drills(service, signed, blocked_drill,
                     stale_drill) -> dict:
    """Act seven (September side): every figure on the signed
    pack re-performs to its lines; the planted compositions
    are checked by kind; the blocked and stale drills —
    computed in the main flow, while those packs stood in
    those states — foot on their own stamps."""
    out: dict = {"results": {}, "gates": {}}
    if signed is None:
        out["gates"] = {
            "drill: every september figure foots to its lines":
                False,
            "drill: base figure lines are the planted lines":
                False,
            "drill: elimination shows both legs at the stamp":
                False,
            "drill: converted figure converts once per entity "
            "at the stamp": False,
            "drill: derived figures compose, on no lines of "
            "their own": False,
            "drill: blocked and stale packs drill on their "
            "own stamps": False,
        }
        return out

    out["gates"]["drill: every september figure foots to its lines"] = \
        all(
            service.figure_drill(
                signed.pack_id, f.metric_id, f.entity_id
            ).composed_total == f.value
            for f in signed.figures
        )

    base = service.figure_drill(
        signed.pack_id, "revenue_external", "HLE")
    out["gates"]["drill: base figure lines are the planted lines"] = (
        [(l.batch_id, l.batch_version, l.journal_id, l.account,
          l.amount) for l in base.root.lines]
        == [("B-HLE-GL-v2", 2, "J-E2", "4000", "520000.00"),
            ("B-HLE-GL-v2", 2, "J-E3", "4100", "95000.00")]
        and base.composed_total == "615000.00"
    )

    elim = service.figure_drill(signed.pack_id, "eliminations_total")
    revenue_leg, cost_leg = elim.root.children
    cost_entity = cost_leg.children[0]
    out["gates"]["drill: elimination shows both legs at the stamp"] = (
        elim.composed_total == "55000.00"
        and revenue_leg.value == cost_leg.value == "55000.00"
        and cost_entity.pre_conversion_value == "50000.00"
        and cost_entity.rate == "1.10"
        and cost_entity.value == "55000.00"
    )

    converted = service.figure_drill(
        signed.pack_id, "consolidated_revenue")
    hle = next(c for c in converted.root.children
               if c.entity_id == "HLE")
    out["gates"]["drill: converted figure converts once per entity "
               "at the stamp"] = (
        converted.root.kind == "sum_converted"
        and hle.pre_conversion_value == "615000.00"
        and hle.rate == "1.10"
        and hle.value == "676500.00"
        and converted.composed_total == "1796500.00"
    )

    income = service.figure_drill(
        signed.pack_id, "consolidated_operating_income")
    vs_plan = service.figure_drill(signed.pack_id, "revenue_vs_plan")
    plan_node = vs_plan.root.children[1]
    out["gates"]["drill: derived figures compose, on no lines of "
               "their own"] = (
        income.root.lines == [] and income.root.records == []
        and [c.sign for c in income.root.children] == [1, -1, -1]
        and income.composed_total == "783250.00"
        and plan_node.kind == "plan"
        and plan_node.value == "-1750000.00"
        and plan_node.lines == []
        and vs_plan.composed_total == "46500.00"
    )

    out["gates"]["drill: blocked and stale packs drill on their "
               "own stamps"] = (
        blocked_drill.pack_status == "BLOCKED"
        and blocked_drill.composed_total
        == blocked_drill.figure_value == "133250.00"
        and sum(1 for l in blocked_drill.root.lines
                if l.journal_id == "J-D9") == 1
        and stale_drill.pack_status == "STALE"
        and stale_drill.composed_total
        == stale_drill.figure_value == "195000.00"
        and {l.batch_id for l in stale_drill.root.lines}
        == {"B-HLE-GL-v1"}
        and stale_drill.fx_version == 1
    )
    out["results"]["drill_signed_line_counts"] = {
        f.metric_id + (f"@{f.entity_id}" if f.entity_id else ""):
            service.figure_drill(
                signed.pack_id, f.metric_id, f.entity_id).line_count
        for f in signed.figures
    }
    return out


def _evaluate_drill_tamper() -> dict:
    """Act seven (the identity): September closes and signs on
    a fresh store; then a source line is edited under the
    signed pack's stamps, and an FX batch is edited in place.
    The first must raise DRILL_MISMATCH naming the figure;
    the second must reprice nothing — the drill converts at
    the stamp, like the verifier."""
    out: dict = {"results": {}, "gates": {
        "drill: tampered source line raises DRILL_MISMATCH "
        "naming the figure": False,
        "drill: edited rate table reprices no drill (the "
        "stamp is the basis)": False,
    }}

    def _signed_september():
        service = build_demo_service()
        world = build_world()
        run = service.create_run(PERIOD)
        service.ingest(
            run.run_id,
            [b.batch_id for b in world.batches_in_phase("initial")])
        service.build_pack(run.run_id)
        service.ingest(
            run.run_id,
            [b.batch_id for b in world.batches_in_phase("late")])
        second = service.build_pack(run.run_id)
        _chain(service, second.pack_id)
        return service, service.sign_off(
            second.pack_id, "sign", "Eval Controller")

    service, signed = _signed_september()
    batch = service.store.get_batch("B-HLE-GL-v2")
    journals = []
    for journal in batch.journals:
        if journal.journal_id == "J-E2":
            journal = journal.model_copy(update={"lines": [
                line.model_copy(update={"credit": "521000.00"})
                if line.account == "4000" else line
                for line in journal.lines
            ]})
        journals.append(journal)
    service.store.save_batch(batch.model_copy(
        update={"journals": journals}))
    try:
        service.figure_drill(signed.pack_id, "revenue_external", "HLE")
        mismatch = None
    except DrillMismatch as exc:
        mismatch = exc
    out["gates"][
        "drill: tampered source line raises DRILL_MISMATCH "
        "naming the figure"] = (
        mismatch is not None
        and "DRILL_MISMATCH" in str(mismatch)
        and "revenue_external" in str(mismatch)
        and mismatch.composed_total == "616000.00"
        and mismatch.figure_value == "615000.00"
    )
    out["results"]["drill_mismatch"] = (
        str(mismatch) if mismatch is not None else None)

    service, signed = _signed_september()
    fx_batch = service.store.get_batch("B-FX-v2")
    service.store.save_batch(fx_batch.model_copy(update={
        "rate_table": fx_batch.rate_table.model_copy(
            update={"rates": {"EUR": "1.15"}}),
    }))
    drill = service.figure_drill(signed.pack_id, "consolidated_revenue")
    out["gates"][
        "drill: edited rate table reprices no drill (the "
        "stamp is the basis)"] = (
        drill.composed_total == "1796500.00"
        and drill.fx_version == 2
    )
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


def _evaluate_readiness() -> dict:
    """Act eight: pre-close readiness — the expectation
    manifest, the check, the build gate, and the waiver.

    The gates, in the order the act walks them:

    - ``readiness: complete period passes, manifest cited`` —
      September, fully corrected, reports READY under its
      derived manifest and the rebuilt pack states COMPLETE
      with the manifest cited; October, fully delivered,
      reports READY under its own;
    - ``readiness: missing and short items named`` —
      September on its opening deliveries fails on exactly
      the three version items the derivation implies (the
      corrected extracts and the revised rate table at v2),
      and an October run staged short two extracts fails on
      exactly those two slots, by name;
    - ``readiness: build refused while unready, items
      named`` — the build for the unready September run is
      refused with the failing items in the refusal;
    - ``readiness: waiver refusals name their grounds`` — a
      blanket waiver is refused, a waiver naming an item the
      check is not failing on is refused by name, and a
      waiver for an already-signed period is refused;
    - ``readiness: waived build states the waiver; bundle
      carries it`` — October, its manifest amended to expect
      HLE's AR at v2 with only v1 delivered, builds under a
      waiver covering exactly that item; the pack's face
      states the waiver (item, actor, reason) and the signed
      pack's evidence bundle carries the manifest and the
      waiver record;
    - ``readiness: another item's waiver does not unblock`` —
      a waiver on record for a different item (October's CRM
      slot) leaves the version-short build refused, naming
      the uncovered item;
    - ``readiness: the check is a pure read`` — the store is
      byte-identical across a readiness check;
    - ``readiness: signed packs byte-identical`` — the
      September pack signed in this act is byte-identical
      after every manifest, waiver, refusal, and October
      build that follows.
    """

    from aidnn_close_agent import readiness as readiness_module
    from aidnn_close_agent.datasets import (
        PERIOD,
        PERIOD_OCTOBER,
        build_manifest_entries,
        build_october_world,
        build_world,
    )
    from aidnn_close_agent.errors import GateError, ReadinessError

    gates: dict[str, bool] = {}
    actor = "Eval Controller"
    note = ("Derived from the batches the period's close "
            "actually used.")
    short_items = [
        "GROUP:fx (received v1, expected v2)",
        "HLD:gl (received v1, expected v2)",
        "HLE:gl (received v1, expected v2)",
    ]

    def snapshot(store) -> str:
        parts = []
        for records in (
            store.list_batches(), store.list_runs(),
            store.list_packs(), store.list_bundles(),
            store.list_manifests(), store.list_waivers(),
            store.list_activations(), store.list_dry_runs(),
        ):
            parts.extend(r.model_dump_json() for r in records)
        return "\n".join(sorted(parts))

    september = build_demo_service()
    store = september.store
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    october = CloseService(
        pipeline=PackPipeline(
            engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
            checkpointer=MemorySaver()),
        store=store, connector=september.connector,
        objects=september.objects, pack_def=pack_v110,
    )
    september_world = build_world()
    october_world = build_october_world()

    september.record_manifest(
        PERIOD, build_manifest_entries(PERIOD), actor, note)
    october.record_manifest(
        PERIOD_OCTOBER, build_manifest_entries(PERIOD_OCTOBER),
        actor, note)

    # September on its opening deliveries: three version
    # items, named; the check a pure read; the build refused.
    run_opening = september.create_run(PERIOD)
    september.ingest(run_opening.run_id, [
        b.batch_id for b in september_world.batches_in_phase("initial")])
    before = snapshot(store)
    report = september.readiness(run_opening.run_id)
    gates["readiness: the check is a pure read"] = (
        snapshot(store) == before)
    september_items = sorted(i.name for i in report.items)
    refusal = ""
    try:
        september.build_pack(run_opening.run_id)
    except ReadinessError as exc:
        refusal = str(exc)
    gates["readiness: build refused while unready, items named"] = (
        bool(refusal)
        and all(name in refusal for name in short_items))

    # The waiver refusals: blanket, and an item not failing.
    blanket_refused = not_failing_refused = False
    try:
        september.record_waiver(PERIOD, [], actor, "just build it")
    except GateError:
        blanket_refused = True
    try:
        september.record_waiver(PERIOD, ["GROUP:crm"], actor,
                                "the CRM extract is late")
    except GateError:
        not_failing_refused = True

    # Waived, the opening build proceeds — and states it.
    september.record_waiver(
        PERIOD, short_items, actor,
        "The v1 extracts are the period's opening position; "
        "the corrected deliveries are confirmed in flight.")
    blocked = september.build_pack(run_opening.run_id)
    waived_face = (
        blocked.status == "BLOCKED"
        and blocked.readiness is not None
        and blocked.readiness.status == "WAIVED"
        and blocked.readiness.waived_items == short_items)

    # The corrected deliveries land; the rebuild is complete,
    # states it, and signs.
    september.ingest(run_opening.run_id, [
        b.batch_id for b in september_world.batches_in_phase("late")])
    rebuilt = september.build_pack(run_opening.run_id)
    _chain(september, rebuilt.pack_id)
    september_signed = september.sign_off(
        rebuilt.pack_id, "sign", actor)
    september_signed_json = september.get_pack(
        september_signed.pack_id).model_dump_json()

    # A waiver for a signed period is refused — history needs
    # no licence.
    signed_refused = False
    try:
        september.record_waiver(PERIOD, short_items, actor, "too late")
    except GateError:
        signed_refused = True
    gates["readiness: waiver refusals name their grounds"] = (
        blanket_refused and not_failing_refused and signed_refused)

    # October staged short two extracts names exactly those.
    run_missing = october.create_run(PERIOD_OCTOBER)
    october.ingest(run_missing.run_id, [
        b.batch_id for b in october_world.batches
        if b.batch_id not in ("O-HLE-AR-v1", "O-CRM-v1")])
    missing_report = october.readiness(run_missing.run_id)
    gates["readiness: missing and short items named"] = (
        september_items == short_items
        and sorted(i.name for i in missing_report.items)
        == ["GROUP:crm", "HLE:ar"])

    # A waiver for the CRM slot — valid against the short run,
    # and no use at all to a different failure.
    october.record_waiver(
        PERIOD_OCTOBER, ["GROUP:crm"], actor,
        "The pipeline extract is a weekly file; this month's "
        "is confirmed in flight.")

    # October complete under its manifest.
    run_full = october.create_run(PERIOD_OCTOBER)
    october.ingest(run_full.run_id,
                   [b.batch_id for b in october_world.batches])
    full_report = october.readiness(run_full.run_id)
    gates["readiness: complete period passes, manifest cited"] = (
        full_report.status == "READY"
        and full_report.manifest_id == "MAN-2026-10-1"
        and rebuilt.readiness is not None
        and rebuilt.readiness.status == "COMPLETE"
        and rebuilt.readiness.manifest_id == "MAN-2026-09-1")

    # The manifest is amended: HLE's AR is expected at v2.
    entries = build_manifest_entries(PERIOD_OCTOBER)
    for entry in entries:
        if entry.slot == "HLE:ar":
            entry.expected_version = 2
    october.record_manifest(
        PERIOD_OCTOBER, entries, actor,
        "HLE re-issues its AR extract at v2 after the "
        "subledger fix.")
    version_item = "HLE:ar (received v1, expected v2)"
    refusal = ""
    try:
        october.build_pack(run_full.run_id)
    except ReadinessError as exc:
        refusal = str(exc)
    gates["readiness: another item's waiver does not unblock"] = (
        version_item in refusal and "GROUP:crm" not in refusal)

    # Waived exactly, the build proceeds and states it; the
    # signed pack's bundle carries the records.
    october.record_waiver(
        PERIOD_OCTOBER, [version_item], actor,
        "HLE's v1 extract is the corrected subledger's own "
        "output, re-issued under the old version by their "
        "connector; the content is the v2 content.")
    pack = october.build_pack(run_full.run_id)
    face = pack.readiness
    _chain(october, pack.pack_id)
    october.sign_off(pack.pack_id, "sign", actor)
    october.generate_evidence(pack.pack_id)
    data, _content_type = october.evidence_download(
        pack.pack_id, "json")
    document = json.loads(data)
    section = document.get("readiness") or {}
    statement = section.get("statement") or {}
    gates["readiness: waived build states the waiver; bundle carries it"] = (
        waived_face
        and face is not None
        and face.status == "WAIVED"
        and face.manifest_id == "MAN-2026-10-2"
        and face.waived_items == [version_item]
        and len(face.waivers) == 1
        and face.waivers[0].actor == actor
        and statement.get("status") == "WAIVED"
        and (section.get("manifest") or {}).get("version") == 2
        and len(section.get("waivers") or []) == 1
        and (section["waivers"][0]).get("items") == [version_item])

    gates["readiness: signed packs byte-identical"] = (
        september.get_pack(september_signed.pack_id).model_dump_json()
        == september_signed_json)

    return {"results": {}, "gates": gates}


def _evaluate_chain() -> dict:
    """Act nine: the sign-off chain. A pack is signed by
    three ordered acts — a named preparer states it is
    ready, a named reviewer states they reviewed it, a
    controller signs — three different people, or the acts
    are refused by name. The blocking discipline bites at
    the chain's first step: a blocked pack cannot even be
    prepared. The preparer may withdraw a pack before the
    chain completes; after the signature, nobody may. The
    controller's act is the signature downstream has always
    keyed on, and a pack signed before the chain existed
    states its single legacy signature honestly."""
    out: dict = {"results": {}, "gates": {}}
    gates = out["gates"]
    controller = "Eval Controller"

    def refused(fn) -> str:
        try:
            fn()
        except GateError as exc:
            return str(exc)
        return ""

    service = build_demo_service()
    world = build_world()
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    blocked = service.build_pack(run.run_id)

    # The blocking check bites at step one: preparation
    # itself is refused on a blocked pack, by name.
    gates["chain: blocked pack cannot be prepared "
          "(blocking bites at step one)"] = (
        blocked.status == "BLOCKED"
        and "is BLOCKED" in refused(
            lambda: service.prepare_pack(blocked.pack_id, PREPARER)))

    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    pack = service.build_pack(run.run_id)

    # Order: review before preparation, and a signature
    # before review, are refused by name.
    gates["chain: review before preparation refused"] = (
        "has not been prepared" in refused(
            lambda: service.review_pack(pack.pack_id, REVIEWER,
                                        "reviewed it")))
    gates["chain: sign before preparation refused"] = (
        "has not been prepared" in refused(
            lambda: service.sign_off(pack.pack_id, "sign", controller)))
    service.prepare_pack(pack.pack_id, PREPARER)
    gates["chain: sign before review refused"] = (
        "has not been reviewed" in refused(
            lambda: service.sign_off(pack.pack_id, "sign", controller)))

    # Segregation: the same person in two roles, refused
    # by name at each step.
    gates["chain: preparer cannot review their own pack"] = (
        "cannot also review" in refused(
            lambda: service.review_pack(pack.pack_id, PREPARER,
                                        "reviewed it")))
    service.review_pack(pack.pack_id, REVIEWER,
                        "reviewed the variances, the dispositions, "
                        "and the readiness statement")
    gates["chain: neither earlier hand can sign"] = (
        "already stands on" in refused(
            lambda: service.sign_off(pack.pack_id, "sign", PREPARER))
        and "already stands on" in refused(
            lambda: service.sign_off(pack.pack_id, "sign", REVIEWER)))

    # Withdrawal: only the preparer, only before the chain
    # completes — then the close is rebuilt and signs.
    gates["chain: withdrawal by another hand refused"] = (
        "only its preparer" in refused(
            lambda: service.withdraw_pack(pack.pack_id, REVIEWER,
                                          "not mine to take back")))
    withdrawn = service.withdraw_pack(
        pack.pack_id, PREPARER,
        "the pack was built against a stale extract; rebuild")
    gates["chain: withdrawal recorded; pack out of the chain"] = (
        withdrawn.status == "WITHDRAWN"
        and withdrawn.withdrawal is not None
        and withdrawn.withdrawal.actor == PREPARER
        and "is WITHDRAWN" in refused(
            lambda: service.sign_off(withdrawn.pack_id, "sign",
                                     controller)))
    rebuilt = service.build_pack(run.run_id)
    _chain(service, rebuilt.pack_id)
    signed = service.sign_off(rebuilt.pack_id, "sign", controller)
    signed_json = service.get_pack(signed.pack_id).model_dump_json()

    # The full chain signs, and downstream reads the
    # signature exactly as it did when signing was one act:
    # the signed pack is findable, October builds its
    # comparatives over it, the run is closed.
    store = service.store
    pack_v110 = load_definition_pack_version("harborlight-close",
                                             "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    october = CloseService(
        pipeline=pipeline, store=store, connector=service.connector,
        objects=service.objects, pack_def=pack_v110,
    )
    october_world = build_october_world()
    oct_run = october.create_run(PERIOD_OCTOBER)
    october.ingest(oct_run.run_id,
                   [b.batch_id for b in october_world.batches])
    october_pack = october.build_pack(oct_run.run_id)
    found = comparatives_module.find_signed_pack(store, PERIOD)
    gates["chain: full chain signs; downstream reads work "
          "as before"] = (
        signed.status == "SIGNED_OFF"
        and [a.role for a in signed.signoff_chain] == [
            "preparer", "reviewer"]
        and signed.decision.actor == controller
        and service.get_run(run.run_id).status == "CLOSED"
        and found is not None and found.pack_id == signed.pack_id
        and len(october_pack.comparatives) == 25)
    gates["chain: signed pack byte-identical after later "
          "builds"] = (
        store.get_pack(signed.pack_id).model_dump_json()
        == signed_json)

    # The bundle carries the whole chain.
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    chain_section = (document.get("sign_off") or {}).get("chain")
    raw_text, _ = service.evidence_download(signed.pack_id, "txt")
    gates["chain: bundle carries all three acts"] = (
        chain_section is not None
        and [a["role"] for a in chain_section] == [
            "preparer", "reviewer"]
        and chain_section[0]["actor"] == PREPARER
        and chain_section[1]["actor"] == REVIEWER
        and chain_section[1]["variances_count"] == 0
        and "chain · reviewer" in raw_text.decode("utf-8"))

    # After the signature there is no withdrawal.
    gates["chain: withdrawal after signature refused"] = (
        "cannot be withdrawn" in refused(
            lambda: service.withdraw_pack(signed.pack_id, PREPARER,
                                          "too late")))

    # A legacy record — a signature with no chain on it,
    # the shape pre-chain code wrote — bundles with the
    # absence stated and no acts invented.
    legacy = service.get_pack(signed.pack_id)
    legacy.signoff_chain = []
    store.save_pack(legacy)
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    raw_text, _ = service.evidence_download(signed.pack_id, "txt")
    gates["chain: legacy bundle states its single signature, "
          "no invented acts"] = (
        (document.get("sign_off") or {}).get("chain") is None
        and document["sign_off"]["actor"] == controller
        and "signed under the single-act sign-off"
        in raw_text.decode("utf-8"))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
