"""The service facade: runs, ingestion, pack builds, sign-off.

The API, CLI, demo, and evals all drive the same service, so the
behaviour a test pins is the behaviour the console shows. The
service owns the close discipline the graph does not:

- **the checklist is a gate** — a pack builds only when every
  required source for the period is ingested at its current
  version (:class:`ChecklistIncomplete` otherwise);
- **ingestion moves the world forward** — a superseding batch
  takes its slot, the raw bytes are archived, and every unsigned
  pack built from the old slot set is marked STALE in the same
  step. A stale or blocked pack can never be signed: sign-off
  re-checks the pack's source stamps against the run's current
  ones, so the rule holds even if a marking step were missed;
- **sign-off names its human** — anonymous decisions do not
  exist, and only an AWAITING_CONTROLLER pack can receive one.

Nothing here posts to a ledger, files a return, or moves money:
the signed pack is the end of the line, by design.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.types import Command

from . import guardrails
from .definitions import DefinitionPack
from .errors import (
    BatchNotFound,
    ChecklistIncomplete,
    GateError,
    PackNotFound,
    RunNotFound,
)
from .graph import PackPipeline
from .marts import build_marts, slot_key
from .ports import ConnectorPort, ObjectStorePort
from .schemas import BoardPack, CloseRun

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CloseService:
    def __init__(self, pipeline: PackPipeline, store, connector: ConnectorPort,
                 objects: ObjectStorePort, pack_def: DefinitionPack) -> None:
        self.pipeline = pipeline
        self.store = store
        self.connector = connector
        self.objects = objects
        self.pack_def = pack_def

    # -- runs ---------------------------------------------------------

    def create_run(self, period: str) -> CloseRun:
        base = f"RUN-{period}"
        run_id, suffix = base, 2
        while self.store.get_run(run_id) is not None:
            run_id = f"{base}-{suffix}"
            suffix += 1
        run = CloseRun(
            run_id=run_id, period=period,
            checklist={eid: {} for eid in self.pack_def.entity_ids()},
            audit=[{"event": "run_created", "at": _now()}],
            created_at=_now(), updated_at=_now(),
        )
        return self.store.save_run(run)

    def get_run(self, run_id: str) -> CloseRun:
        run = self.store.get_run(run_id)
        if run is None:
            raise RunNotFound(f"no close run {run_id}")
        return run

    def list_runs(self) -> list[CloseRun]:
        return self.store.list_runs()

    def missing(self, run: CloseRun) -> list[str]:
        return guardrails.missing_sources(run, self.pack_def.entity_ids())

    # -- ingestion -----------------------------------------------------

    def ingest(self, run_id: str, batch_ids: list[str]) -> CloseRun:
        run = self.get_run(run_id)
        if run.status == "CLOSED":
            raise GateError(
                f"run {run_id} is closed (a pack was signed); "
                "late sources belong to a new run, not this one"
            )
        for batch_id in batch_ids:
            batch = self.connector.fetch(batch_id)  # BatchNotFound propagates
            # Archive the raw evidence before anything else uses it.
            key = f"extracts/{run.period}/{batch.batch_id}.json"
            self.objects.put(key, batch.model_dump_json().encode("utf-8"),
                             "application/json")
            self.store.save_batch(batch)
            slot = slot_key(batch)
            previous = run.current_batches.get(slot)
            run.current_batches[slot] = batch.batch_id
            if batch.entity_id:
                run.checklist.setdefault(batch.entity_id, {})[batch.kind] = \
                    batch.version
            else:
                run.group_checklist[batch.kind] = batch.version
            if batch.batch_id not in run.ingested_batch_ids:
                run.ingested_batch_ids.append(batch.batch_id)
            for journal in batch.journals:
                flags, _ = guardrails.screen_injection(journal.memo)
                run.injection_flags.extend(
                    f"{batch.entity_id}/{journal.journal_id}: {f}" for f in flags
                )
                for line in journal.lines:
                    line_flags, _ = guardrails.screen_injection(line.memo)
                    run.injection_flags.extend(
                        f"{batch.entity_id}/{journal.journal_id}: {f}"
                        for f in line_flags
                    )
            run.audit.append({
                "event": "ingested", "at": _now(),
                "detail": f"{batch.batch_id} ({batch.kind}"
                          f"{' ' + batch.entity_id if batch.entity_id else ''} "
                          f"v{batch.version})"
                          + (f" supersedes {previous}" if previous else ""),
            })
        run.status = "READY" if not self.missing(run) else "COLLECTING"
        run.updated_at = _now()
        self.store.save_run(run)
        self._mark_stale_packs(run)
        return run

    def _mark_stale_packs(self, run: CloseRun) -> None:
        """Any unsigned pack whose source stamps no longer match
        the run's current batches is stale — marked in the same
        step that moved the sources, never discovered later."""
        for pack in self.store.list_packs(run_id=run.run_id):
            if pack.status in ("SIGNED_OFF", "RETURNED", "STALE"):
                continue
            if pack.source_versions.batches != self._current_versions(run):
                pack.status = "STALE"
                pack.audit.append({
                    "event": "marked_stale", "at": _now(),
                    "detail": "a source extract or rate table superseded "
                              "the versions this pack was built from",
                })
                pack.updated_at = _now()
                self.store.save_pack(pack)

    def _current_versions(self, run: CloseRun) -> dict[str, int]:
        versions: dict[str, int] = {}
        for batch_id in run.current_batches.values():
            batch = self.store.get_batch(batch_id)
            if batch is not None:
                versions[batch.batch_id] = batch.version
        return versions

    def _current_batches(self, run: CloseRun) -> list:
        batches = []
        for batch_id in run.current_batches.values():
            batch = self.store.get_batch(batch_id)
            if batch is None:
                raise BatchNotFound(
                    f"run {run.run_id} references uningested batch {batch_id}"
                )
            batches.append(batch)
        return batches

    # -- pack build ------------------------------------------------------

    def build_pack(self, run_id: str) -> BoardPack:
        run = self.get_run(run_id)
        missing = self.missing(run)
        if missing:
            raise ChecklistIncomplete(
                f"run {run_id} cannot build a pack; still waiting for: "
                + ", ".join(missing)
            )
        batches = self._current_batches(run)
        marts = build_marts(batches, self.pack_def)
        pack_id = f"PACK-{run.run_id}-{len(run.pack_ids) + 1}"
        self.pipeline.contexts[pack_id] = {"marts": marts, "batches": batches}
        config = {"configurable": {"thread_id": pack_id}}
        state = {"run_id": run.run_id, "pack_id": pack_id, "period": run.period}
        self.pipeline.graph.invoke(state, config=config)
        run.pack_ids.append(pack_id)
        run.updated_at = _now()
        self.store.save_run(run)
        return self.get_pack(pack_id)

    def get_pack(self, pack_id: str) -> BoardPack:
        pack = self.store.get_pack(pack_id)
        if pack is None:
            raise PackNotFound(f"no board pack {pack_id}")
        return pack

    def list_packs(self, run_id: str | None = None) -> list[BoardPack]:
        return self.store.list_packs(run_id=run_id)

    # -- the gate ---------------------------------------------------------

    def sign_off(self, pack_id: str, decision: str, actor: str,
                 reason: str = "") -> BoardPack:
        if decision not in ("sign", "return"):
            raise GateError(f"decision must be 'sign' or 'return', got {decision!r}")
        if not actor or not actor.strip():
            raise GateError("a sign-off must name its controller")
        pack = self.get_pack(pack_id)
        if pack.status != "AWAITING_CONTROLLER":
            raise GateError(
                f"pack {pack_id} is {pack.status}; only AWAITING_CONTROLLER "
                "packs can be signed — a blocked pack is fixed by fixing its "
                "sources, a stale pack by rebuilding it"
            )
        run = self.get_run(pack.run_id)
        if pack.source_versions.batches != self._current_versions(run):
            raise GateError(
                f"pack {pack_id} was built from superseded sources; "
                "rebuild it before signing"
            )
        config = {"configurable": {"thread_id": pack_id}}
        self.pipeline.graph.invoke(
            Command(resume={"decision": decision, "actor": actor,
                            "reason": reason}),
            config=config,
        )
        return self.get_pack(pack_id)
