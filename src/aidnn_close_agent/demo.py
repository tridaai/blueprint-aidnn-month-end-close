"""The traced demo: Harborlight's September close, both attempts
— then October, the comparative month.

Attempt one runs on the extracts as they first arrive — and the
verifier stops it cold: a duplicated journal, an intercompany
leg with no counterpart, an AR tie-out gap where a services
billing was posted to payroll. Then the corrected extracts land
late, the first pack goes stale by its stamps, and the rebuilt
pack verifies figure for figure against source — where a named
controller signs it. Nothing posts anywhere; the signed pack is
the end of the line.

The second act is October. September's HLG extract is restated
after sign-off (a payroll accrual was understated); October
closes under definition pack v1.1.0, which widened operating
expenses. October's pack presents every figure against
September's *signed* figures, flags the comparisons that cross
the definition change, detects the restatement by name — and
its signature is held until the controller acknowledges the
restatement on the record.

October's pack also carries the flux schedule: every figure's
movement against September decomposed by entity and by account,
footing exactly, with the material movements' drivers named —
each side computed under its own period's definition version,
and the whole schedule recomputed independently by the
verifier before the pack may pass.

Each signed pack then generates its audit evidence bundle —
the projection an external auditor re-performs from: figures
with their definitions and verdicts, the source manifest with
its recorded hashes, comparatives, flux, restatement, sign-off.

The third act is October once more, on a fresh store, with one
staged break: HLE books its intercompany purchase €500 light.
The pair disagrees, the pack blocks, and fixing the books is
not the only honest exit — the controller accepts the break
in writing (a disposition), the rebuilt pack is presented
for sign-off with the acceptance on its face and the variance
standing word for word, and the signed pack carries the item
into November as an opening item that must clear there.

The fourth act changes the ruler itself. A candidate pack
v1.2.0 would take insurance premiums out of operating
expenses and give them their own line. Nobody edits the ruler
mid-measurement: the candidate's impact is first computed as
a dry-run over the signed October close — every figure
recomputed under both versions from October's stamped
sources — and only then does a named activation make it
govern November. November's run is created on a service still
wired to v1.1.0, and the selection rule, not the wiring,
puts v1.2.0 in charge; the pack states the change on its
face, and its evidence bundle cites the act and the impact
behind it.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver

from .config import definition_pack_path
from .connectors import DatasetConnector
from .datasets import (
    IC_VARIANT_BATCH_ID,
    PERIOD,
    PERIOD_NOVEMBER,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    build_november_world,
    build_october_world,
    build_world,
    october_ic_variant_batch,
)
from .definitions import load_definition_pack, load_definition_pack_version
from .engine_offline import OfflineFinanceEngine
from .errors import GateError
from .graph import PackPipeline
from .object_store import InMemoryObjectStore
from .service import CloseService
from .store import InMemoryCloseStore

CONTROLLER = "Mara Ellison (Group Controller)"
PREPARER = "Priya Nair (Senior Accountant)"
REVIEWER = "Jonas Weber (Reporting Manager)"


def _sign_via_chain(service, pack, reason: str = ""):
    """Walk a pack through the sign-off chain — preparation,
    review, signature, three acts by three people — and
    return the signed pack, printing the chain as it forms."""
    service.prepare_pack(pack.pack_id, PREPARER,
                         "figures tied out; the pack is ready")
    print(f"  chain · preparer: {PREPARER} states {pack.pack_id} "
          "is ready")
    service.review_pack(
        pack.pack_id, REVIEWER,
        "reviewed the variances, the dispositions on the face, "
        "and the readiness statement")
    print(f"  chain · reviewer: {REVIEWER} states they reviewed it")
    return service.sign_off(pack.pack_id, "sign", CONTROLLER, reason)


def build_demo_service() -> CloseService:
    store = InMemoryCloseStore()
    pack_def = load_definition_pack(definition_pack_path())
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_def,
    )


def _print_pack(pack, heading: str) -> None:
    print(f"\n{heading} — {pack.pack_id}: {pack.status}")
    for variance in pack.variances:
        print(f"  ✗ {variance.code}: {variance.detail}")
    for pair in pack.ic_pairs:
        seller = (f"{pair.seller_currency} {pair.seller_amount}"
                  if pair.seller_amount is not None else "none booked")
        buyer = (f"{pair.buyer_currency} {pair.buyer_amount}"
                 if pair.buyer_amount is not None else "none booked")
        print(f"  ⇄ IC pair {pair.seller_id} → {pair.buyer_id} "
              f"({pair.elimination_id}): {pair.seller_id} books {seller}, "
              f"{pair.buyer_id} books {buyer} — {pair.verdict}")
    for figure in pack.figures:
        scope = figure.entity_id or figure.scope
        mark = "✓" if figure.status == "verified" else "·"
        flag = "  [IC disputed]" if figure.ic_disagreement else ""
        print(f"  {mark} {figure.metric_id:<32} {scope:<14} "
              f"{figure.currency} {figure.value:>14}  [{figure.status}]"
              f"{flag}")


def run_demo() -> CloseService:
    world = build_world()
    service = build_demo_service()

    print("Trida Blueprint — aidnn Month-End Close, Deployed (offline engine)")
    print(f"Harborlight Group · period {PERIOD} · definition pack "
          f"{service.pack_def.pack_id} v{service.pack_def.version}")

    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    print(f"\nIngested the initial extracts; run {run.run_id} is READY.")
    first = service.build_pack(run.run_id)
    _print_pack(first, "First attempt")
    print("\nThe verifier blocked the pack — no sign-off is possible. "
          "The corrections arrive late:")
    for batch in world.batches_in_phase("late"):
        print(f"  · {batch.batch_id} supersedes {batch.supersedes}")
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    first_after = service.get_pack(first.pack_id)
    print(f"First pack is now {first_after.status} (its source stamps moved).")

    second = service.build_pack(run.run_id)
    _print_pack(second, "Rebuilt attempt")
    if second.narrative:
        print("\nNarrative (from verified figures only):")
        for line in second.narrative.splitlines():
            print(f"  {line}")
    print("\nThe signature is a chain, not a click:")
    signed = _sign_via_chain(service, second,
                             "figures verified; variances cleared")
    print(f"\n{signed.pack_id} → {signed.status} by {CONTROLLER}.")
    print("Nothing was posted to any ledger. The signed pack is the record.")
    _print_evidence(service, signed)

    october_service = _run_october(service)
    _run_disposition_act()
    _run_governance_act(october_service)
    return service


def _print_evidence(service: CloseService, signed) -> None:
    """Generate the signed pack's audit evidence bundle and show
    what an auditor receives: the digest, the counts, and one
    figure's full evidence entry."""
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    print(f"\nAudit evidence bundle {record.bundle_id}: "
          f"{record.figure_count} figures with definitions and "
          f"verdicts, {record.manifest_count} source extracts in "
          f"the manifest.\n  stored at {record.json_key}\n"
          f"  sha256 {record.sha256}")
    figure = next(
        f for f in document["figures"]
        if f["metric_id"] == "consolidated_revenue"
    )
    print("  one figure's evidence entry:")
    print(json.dumps(figure, indent=2).replace("\n", "\n  "))


def _run_october(september_service: CloseService) -> CloseService:
    """Act two, over the same store: the restatement lands, the
    definition pack is upgraded, and October closes comparative."""
    store = september_service.store
    print("\n" + "=" * 72)
    print("October: the comparative month")
    batch = september_service.receive_restatement(RESTATEMENT_BATCH_ID)
    print(f"\nA corrected September extract lands after sign-off: "
          f"{batch.batch_id} supersedes {batch.supersedes}. The signed "
          "September pack is not touched — history is not edited.")

    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack_v110 is not None
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    service = CloseService(
        pipeline=pipeline, store=store,
        connector=september_service.connector,
        objects=september_service.objects, pack_def=pack_v110,
    )
    print(f"October's close runs under definition pack v{pack_v110.version} "
          "(operating expenses now include insurance, account 6400).")

    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    _print_pack(pack, "October attempt")

    print(f"\nComparatives — every figure against September's signed pack "
          f"({pack.comparatives[0].prior_pack_id if pack.comparatives else '—'}):")
    current = {(f.metric_id, f.entity_id): f for f in pack.figures}
    for comp in pack.comparatives:
        figure = current[(comp.metric_id, comp.entity_id)]
        flags = []
        if comp.definition_changed:
            flags.append("DEFINITION CHANGED")
        if comp.restated:
            flags.append("RESTATED PRIOR")
        scope = comp.entity_id or "consolidated"
        if comp.change is None:
            change = "—"
        elif comp.change_pct is None:
            change = comp.change  # prior was zero; a % would mislead
        else:
            change = f"{comp.change} ({comp.change_pct}%)"
        print(f"  {comp.metric_id:<32} {scope:<12} "
              f"{figure.currency} {figure.value:>12} vs signed "
              f"{comp.prior_value:>12}  Δ {change:<22} "
              f"{' · '.join(flags)}")

    if pack.flux is not None:
        print(f"\nFlux — the material movements, decomposed (bars: "
              f"|movement| ≥ {pack.flux.threshold_abs} or |change| ≥ "
              f"{pack.flux.threshold_pct}%):")
        for entry in pack.flux.entries:
            if not entry.material:
                continue
            scope = entry.entity_id or "consolidated"
            drivers = "; ".join(
                f"{line.label} {line.amount}"
                for line in entry.by_entity if line.kind != "rounding"
            )
            print(f"  {entry.metric_id:<32} {scope:<12} "
                  f"Δ {entry.movement:>12}  ← {drivers}")

    if pack.restatement is not None:
        print("\nThe restatement, as the pack names it:")
        for affected in pack.restatement.affected_figures:
            scope = affected.entity_id or "consolidated"
            print(f"  ✗ {affected.metric_id:<32} {scope:<12} signed "
                  f"{affected.signed_value:>12} → restated sources "
                  f"produce {affected.recomputed_value:>12}")
    try:
        service.sign_off(pack.pack_id, "sign", CONTROLLER)
        print("\nUNEXPECTED: the pack signed over an unacknowledged "
              "restatement.")
    except GateError as exc:
        print(f"\nSign-off refused: {exc}")
    acked = service.acknowledge_restatement(
        pack.pack_id, CONTROLLER,
        "Reviewed the HLG payroll restatement with FP&A; September's "
        "comparatives stand as signed, the restated figures are noted "
        "for the audit file.",
    )
    print(f"Restatement acknowledged by {CONTROLLER} — the variance "
          "stays on the pack record.")
    signed = _sign_via_chain(service, acked,
                             "comparatives tie to the signed September "
                             "pack; restatement acknowledged")
    print(f"{signed.pack_id} → {signed.status}. September's signed pack "
          "is byte-for-byte the record it was.")
    record = service.generate_evidence(signed.pack_id)
    print(f"Its evidence bundle {record.bundle_id} carries the "
          f"comparatives, the restatement, and the acknowledgement: "
          f"{record.figure_count} figures, sha256 {record.sha256}")
    return service


class _VariantConnector:
    """The dataset connector with October's HLE extract swapped
    for the staged intercompany variant — the same staging the
    tests and evals use, behind the same port."""

    name = "dataset-ic-variant"

    def __init__(self, base: DatasetConnector) -> None:
        self._base = base

    def available(self):
        return self._base.available()

    def fetch(self, batch_id: str):
        if batch_id == IC_VARIANT_BATCH_ID:
            return october_ic_variant_batch()
        return self._base.fetch(batch_id)


def _run_disposition_act() -> None:
    """Act three, on a fresh store: October with the staged
    intercompany understatement — blocked, dispositioned,
    presented, signed, and carried."""
    print("\n" + "=" * 72)
    print("October, once more: the break a controller accepts")
    store = InMemoryCloseStore()
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack_v110 is not None
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
    _print_pack(blocked, "The staged October attempt")
    print("\nOne break, named by two checks: HLE booked its "
          "intercompany purchase at €54,500 against HLD's $61,600 "
          "sale — the pair disagrees by $560.00, so the legs do "
          "not pair either. Every figure still verifies. The "
          "books could be fixed and the pack rebuilt; the "
          "controller takes the second honest exit instead:")
    reason_pair = (
        "HLE's €500 understatement is a known booking error in "
        "their October close, confirmed with HLE's controller; "
        "immaterial to the group. Accepted for October and "
        "carried — it must clear in November's close."
    )
    reason_leg = (
        "The unmatched leg is the same HLE understatement seen "
        "from the elimination side; accepted with it, on the "
        "same terms, and carried with it."
    )
    service.record_disposition(
        blocked.pack_id, code="IC_DISAGREEMENT", actor=CONTROLLER,
        reason=reason_pair)
    service.record_disposition(
        blocked.pack_id, code="UNMATCHED_IC_LEG", actor=CONTROLLER,
        reason=reason_leg)
    print(f"  · IC_DISAGREEMENT accepted and carried by {CONTROLLER}")
    print(f"  · UNMATCHED_IC_LEG accepted and carried by {CONTROLLER}")
    print("The blocked pack itself does not move — it stays "
          "BLOCKED, its variances word for word. The rebuild is "
          "what gets presented:")
    presented = service.build_pack(run.run_id)
    print(f"\n{presented.pack_id}: {presented.status} — the "
          "verifier's verdict stands on it unchanged:")
    for variance in presented.variances:
        print(f"  ✗ {variance.code}: {variance.detail}")
    print("…and the acceptances ride its face:")
    for disposition in presented.dispositions:
        print(f"  ✓ {disposition.disposition_id} · "
              f"{disposition.code} · {disposition.decision} by "
              f"{disposition.actor} — {disposition.reason}")
    signed = _sign_via_chain(
        service, presented,
        "figures verified; the intercompany break is accepted "
        "on the record and carried to November")
    print(f"\n{signed.pack_id} → {signed.status}. The signed "
          "pack lists what was accepted next to the variances "
          "themselves — and both acceptances now open November "
          "as named items: re-tested against November's sources, "
          "blocking again if the break is still there.")
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    print(f"Its evidence bundle {record.bundle_id} carries the "
          f"{len(document['dispositions'])} dispositions beside "
          f"the variances they answer for — sha256 {record.sha256}")


class _WorldConnector:
    """Serves one staged world's batches — November's route
    into act four (the dataset connector stages September,
    October, and the restatement only)."""

    name = "world"

    def __init__(self, world) -> None:
        self._batches = {b.batch_id: b for b in world.batches}

    def available(self):
        return list(self._batches.values())

    def fetch(self, batch_id: str):
        return self._batches[batch_id]


def _run_governance_act(october_service: CloseService) -> None:
    """Act four, over the main store: a definition change,
    governed — impact computed first, then a named activation,
    then a November close the selection rule puts under the
    new version."""
    print("\n" + "=" * 72)
    print("A new ruler, governed: definition pack v1.2.0")
    service = october_service
    store = service.store
    reason = (
        "Insurance premiums are a board line of their own now; "
        "they leave operating expenses and stand separately "
        "from November. Operating income does not move — the "
        "split is presentation, measured before it governs."
    )
    print("\nA candidate pack v1.2.0 sits in the registry: "
          "account 6400 (insurance) leaves operating expenses "
          "for its own metric. Activating it on sight is "
          "refused — the impact must exist first:")
    try:
        service.activate_definition_pack(
            "1.2.0", PERIOD_NOVEMBER, CONTROLLER, reason)
        print("UNEXPECTED: the activation went through without "
              "a dry-run.")
    except GateError as exc:
        print(f"  ✗ {exc}")
    record = service.dry_run_definition_change("1.2.0")
    report = record.report
    print(f"\nDry-run {record.dry_run_id} — v{report.candidate_version} "
          f"measured over signed {report.reference_period} (pack "
          f"{report.reference_pack_id}, signed under "
          f"v{report.base_version}); digest {record.digest[:16]}…")
    print(f"  Definitions changed: {', '.join(report.changed_metrics)}")
    for delta in report.moved:
        scope = delta.entity_id or "consolidated"
        print(f"  → {delta.metric_id:<32} {scope:<12} "
              f"{delta.currency} {delta.base_value:>12} → "
              f"{delta.candidate_value:>12}  (Δ {delta.delta})")
    for figure in report.added:
        scope = figure.entity_id or "consolidated"
        print(f"  + {figure.metric_id:<32} {scope:<12} "
              f"{figure.currency} {figure.value:>12}  (new figure)")
    print(f"  Dropped figures: {len(report.dropped)} · variance "
          f"families unchanged: "
          f"{report.variance_families_candidate == report.variance_families_base}"
          f" · material moves: {report.material_count}")
    activation = service.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, CONTROLLER, reason)
    print(f"\n{activation.activation_id}: {CONTROLLER} activates "
          f"v{activation.to_version} from {activation.from_period}, "
          f"citing dry-run {activation.dry_run_id}. Signed periods "
          "are untouched — September still cites v1.0.0, October "
          "v1.1.0, forever.")
    november_world = build_november_world("55000.00")
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack_v110 is not None
    november = CloseService(
        pipeline=PackPipeline(
            engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
            checkpointer=MemorySaver()),
        store=store, connector=_WorldConnector(november_world),
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )
    run = november.create_run(PERIOD_NOVEMBER)
    print(f"\nNovember's run is created on a service still wired "
          f"to v{pack_v110.version} — and the selection rule "
          f"assigns v{run.definition_pack_version} "
          f"({run.audit[-1]['detail']}).")
    november.ingest(run.run_id,
                    [b.batch_id for b in november_world.batches])
    pack = november.build_pack(run.run_id)
    _print_pack(pack, "November attempt")
    change = pack.definition_change
    if change is not None:
        print(f"\nThe pack states the change on its face: first "
              f"pack governed by v{change.to_version} (activation "
              f"{change.activation_id} by {change.actor}); the "
              f"dry-run behind it found {change.moved_count} "
              f"figures moved, {change.added_count} added, "
              f"{change.dropped_count} dropped.")
    signed = _sign_via_chain(november, pack,
                             "first close under v1.2.0; the "
                             "change is governed and stated")
    print(f"{signed.pack_id} → {signed.status}.")
    record = november.generate_evidence(signed.pack_id)
    data, _ = november.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    section = document["definition_change"]
    print(f"Its evidence bundle {record.bundle_id} carries the "
          f"definition change: the activation by "
          f"{section['activation']['actor']} and the dry-run "
          f"(digest {section['dry_run']['digest'][:16]}…) it "
          f"relied on — sha256 {record.sha256}")


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
