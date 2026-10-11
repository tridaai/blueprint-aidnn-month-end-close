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
"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver

from .config import definition_pack_path
from .connectors import DatasetConnector
from .datasets import (
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    build_october_world,
    build_world,
)
from .definitions import load_definition_pack, load_definition_pack_version
from .engine_offline import OfflineFinanceEngine
from .errors import GateError
from .graph import PackPipeline
from .object_store import InMemoryObjectStore
from .service import CloseService
from .store import InMemoryCloseStore

CONTROLLER = "Mara Ellison (Group Controller)"


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
    for figure in pack.figures:
        scope = figure.entity_id or figure.scope
        mark = "✓" if figure.status == "verified" else "·"
        print(f"  {mark} {figure.metric_id:<32} {scope:<14} "
              f"{figure.currency} {figure.value:>14}  [{figure.status}]")


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
    signed = service.sign_off(second.pack_id, "sign", CONTROLLER,
                               "figures verified; variances cleared")
    print(f"\n{signed.pack_id} → {signed.status} by {CONTROLLER}.")
    print("Nothing was posted to any ledger. The signed pack is the record.")
    _print_evidence(service, signed)

    _run_october(service)
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


def _run_october(september_service: CloseService) -> None:
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
    print(f"The deployment upgrades the definition pack to v{pack_v110.version} "
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
    signed = service.sign_off(acked.pack_id, "sign", CONTROLLER,
                              "comparatives tie to the signed September "
                              "pack; restatement acknowledged")
    print(f"{signed.pack_id} → {signed.status}. September's signed pack "
          "is byte-for-byte the record it was.")
    record = service.generate_evidence(signed.pack_id)
    print(f"Its evidence bundle {record.bundle_id} carries the "
          f"comparatives, the restatement, and the acknowledgement: "
          f"{record.figure_count} figures, sha256 {record.sha256}")


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
