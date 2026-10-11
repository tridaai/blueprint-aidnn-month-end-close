"""The traced demo: Harborlight's September close, both attempts.

Attempt one runs on the extracts as they first arrive — and the
verifier stops it cold: a duplicated journal, an intercompany
leg with no counterpart, an AR tie-out gap where a services
billing was posted to payroll. Then the corrected extracts land
late, the first pack goes stale by its stamps, and the rebuilt
pack verifies figure for figure against source — where a named
controller signs it. Nothing posts anywhere; the signed pack is
the end of the line.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from .config import definition_pack_path
from .connectors import DatasetConnector
from .datasets import PERIOD, build_world
from .definitions import load_definition_pack
from .engine_offline import OfflineFinanceEngine
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
    return service


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
