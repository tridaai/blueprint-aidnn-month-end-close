"""The close store: source batches, runs, board packs, the
evidence-bundle index, and the definition-governance records
(dry-runs and activations, migration ``0003``).

Two implementations of one small surface, because the deployment
gets PostgreSQL and the test suite gets a double with identical
behaviour:

- :class:`PostgresCloseStore` — the production store (JSONB
  payloads in ``source_batches`` / ``close_runs`` /
  ``board_packs`` / ``evidence_bundles`` /
  ``definition_governance``; migrations ``0001``–``0003``).
- :class:`InMemoryCloseStore` — the double. When it is live,
  ``/readiness`` says so: nothing persists past the process.

Batches are append-only in both: ingesting a superseding batch
never rewrites the batch it replaces — the run's slot map moves,
the evidence stays.
"""

from __future__ import annotations

import json
import threading

from .db import database_url, ensure_migrated
from .schemas import (
    BoardPack,
    CloseRun,
    DefinitionDryRun,
    EvidenceBundle,
    PackActivation,
    SourceBatch,
)


class InMemoryCloseStore:
    name = "memory"

    def __init__(self) -> None:
        self._batches: dict[str, SourceBatch] = {}
        self._runs: dict[str, CloseRun] = {}
        self._packs: dict[str, BoardPack] = {}
        self._bundles: dict[str, EvidenceBundle] = {}
        self._dry_runs: dict[str, DefinitionDryRun] = {}
        self._activations: dict[str, PackActivation] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    # -- batches ---------------------------------------------------
    def save_batch(self, batch: SourceBatch) -> SourceBatch:
        with self._lock:
            self._batches[batch.batch_id] = batch
        return batch

    def get_batch(self, batch_id: str) -> SourceBatch | None:
        return self._batches.get(batch_id)

    def list_batches(self) -> list[SourceBatch]:
        return list(self._batches.values())

    # -- runs --------------------------------------------------------
    def save_run(self, run: CloseRun) -> CloseRun:
        with self._lock:
            if run.run_id not in self._runs:
                self._order.append(run.run_id)
            self._runs[run.run_id] = run
        return run

    def get_run(self, run_id: str) -> CloseRun | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[CloseRun]:
        return [self._runs[rid] for rid in self._order]

    # -- packs -------------------------------------------------------
    def save_pack(self, pack: BoardPack) -> BoardPack:
        with self._lock:
            self._packs[pack.pack_id] = pack
        return pack

    def get_pack(self, pack_id: str) -> BoardPack | None:
        return self._packs.get(pack_id)

    def list_packs(self, run_id: str | None = None) -> list[BoardPack]:
        packs = list(self._packs.values())
        if run_id:
            packs = [p for p in packs if p.run_id == run_id]
        return packs

    # -- evidence bundles ----------------------------------------
    def save_bundle(self, bundle: EvidenceBundle) -> EvidenceBundle:
        with self._lock:
            self._bundles[bundle.bundle_id] = bundle
        return bundle

    def get_bundle(self, bundle_id: str) -> EvidenceBundle | None:
        return self._bundles.get(bundle_id)

    def list_bundles(self, pack_id: str | None = None) -> list[EvidenceBundle]:
        bundles = list(self._bundles.values())
        if pack_id:
            bundles = [b for b in bundles if b.pack_id == pack_id]
        return bundles

    # -- definition governance -------------------------------------
    def save_dry_run(self, record: DefinitionDryRun) -> DefinitionDryRun:
        with self._lock:
            self._dry_runs[record.dry_run_id] = record
        return record

    def get_dry_run(self, dry_run_id: str) -> DefinitionDryRun | None:
        return self._dry_runs.get(dry_run_id)

    def list_dry_runs(self) -> list[DefinitionDryRun]:
        return list(self._dry_runs.values())

    def save_activation(self, record: PackActivation) -> PackActivation:
        with self._lock:
            self._activations[record.activation_id] = record
        return record

    def list_activations(self) -> list[PackActivation]:
        return list(self._activations.values())


class PostgresCloseStore:
    name = "postgres"

    def __init__(self, url: str) -> None:
        ensure_migrated(url)
        self._url = url

    def _connect(self):
        from .db import connect

        return connect(self._url)

    # -- generic helpers (one JSONB table per aggregate) --------------
    def _save(self, table: str, id_column: str, row_id: str,
              model, extra: dict[str, object]) -> None:
        from psycopg.types.json import Jsonb

        columns = [id_column, *extra.keys(), "payload"]
        values = [row_id, *extra.values(),
                  Jsonb(json.loads(model.model_dump_json()))]
        assignments = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in columns if c != id_column
        )
        placeholders = ", ".join(["%s"] * len(columns))
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT ({id_column}) DO UPDATE SET {assignments}, "
                "updated_at = now()",
                values,
            )
            conn.commit()

    def _get(self, table: str, id_column: str, row_id: str, model_cls):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT payload FROM {table} WHERE {id_column} = %s", (row_id,)
            ).fetchone()
        return model_cls.model_validate(row["payload"]) if row else None

    def _list(self, table: str, model_cls, where: str = "", params: tuple = ()):
        query = f"SELECT payload FROM {table}"
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY seq"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [model_cls.model_validate(row["payload"]) for row in rows]

    # -- batches ---------------------------------------------------
    def save_batch(self, batch: SourceBatch) -> SourceBatch:
        self._save("source_batches", "batch_id", batch.batch_id, batch,
                   {"kind": batch.kind, "entity_id": batch.entity_id,
                    "version": batch.version})
        return batch

    def get_batch(self, batch_id: str) -> SourceBatch | None:
        return self._get("source_batches", "batch_id", batch_id, SourceBatch)

    def list_batches(self) -> list[SourceBatch]:
        return self._list("source_batches", SourceBatch)

    # -- runs --------------------------------------------------------
    def save_run(self, run: CloseRun) -> CloseRun:
        self._save("close_runs", "run_id", run.run_id, run,
                   {"period": run.period, "status": run.status})
        return run

    def get_run(self, run_id: str) -> CloseRun | None:
        return self._get("close_runs", "run_id", run_id, CloseRun)

    def list_runs(self) -> list[CloseRun]:
        return self._list("close_runs", CloseRun)

    # -- packs -------------------------------------------------------
    def save_pack(self, pack: BoardPack) -> BoardPack:
        self._save("board_packs", "pack_id", pack.pack_id, pack,
                   {"run_id": pack.run_id, "status": pack.status})
        return pack

    def get_pack(self, pack_id: str) -> BoardPack | None:
        return self._get("board_packs", "pack_id", pack_id, BoardPack)

    def list_packs(self, run_id: str | None = None) -> list[BoardPack]:
        if run_id:
            return self._list("board_packs", BoardPack, "run_id = %s", (run_id,))
        return self._list("board_packs", BoardPack)

    # -- evidence bundles ----------------------------------------
    def save_bundle(self, bundle: EvidenceBundle) -> EvidenceBundle:
        self._save("evidence_bundles", "bundle_id", bundle.bundle_id, bundle,
                   {"pack_id": bundle.pack_id, "period": bundle.period})
        return bundle

    def get_bundle(self, bundle_id: str) -> EvidenceBundle | None:
        return self._get("evidence_bundles", "bundle_id", bundle_id,
                         EvidenceBundle)

    def list_bundles(self, pack_id: str | None = None) -> list[EvidenceBundle]:
        if pack_id:
            return self._list("evidence_bundles", EvidenceBundle,
                              "pack_id = %s", (pack_id,))
        return self._list("evidence_bundles", EvidenceBundle)

    # -- definition governance -------------------------------------
    def save_dry_run(self, record: DefinitionDryRun) -> DefinitionDryRun:
        self._save("definition_governance", "record_id", record.dry_run_id,
                   record, {"kind": "dry_run",
                            "pack_id": record.report.pack_id,
                            "version": record.report.candidate_version})
        return record

    def get_dry_run(self, dry_run_id: str) -> DefinitionDryRun | None:
        return self._get("definition_governance", "record_id", dry_run_id,
                         DefinitionDryRun)

    def list_dry_runs(self) -> list[DefinitionDryRun]:
        return self._list("definition_governance", DefinitionDryRun,
                          "kind = %s", ("dry_run",))

    def save_activation(self, record: PackActivation) -> PackActivation:
        self._save("definition_governance", "record_id",
                   record.activation_id, record,
                   {"kind": "activation", "pack_id": record.pack_id,
                    "version": record.to_version})
        return record

    def list_activations(self) -> list[PackActivation]:
        return self._list("definition_governance", PackActivation,
                          "kind = %s", ("activation",))


def default_store() -> InMemoryCloseStore | PostgresCloseStore:
    """Postgres when DATABASE_URL is set, else the double."""
    url = database_url()
    if url:
        return PostgresCloseStore(url)
    return InMemoryCloseStore()
