"""Connectors: how source extracts reach the close.

One connector per source system in a deployment (NetSuite,
QuickBooks, Salesforce in the bundled world — aidnn's own
connector catalog covers the same systems, and in a live
deployment the FDE wires this layer to whichever side owns the
pull). The contract is small: a connector stages immutable
extract batches and delivers them by id. A corrected extract is
a *new batch* that supersedes the old one — connectors never
edit history, which is what makes pack staleness computable.

This repo's connector serves the synthetic world in
:mod:`.datasets`. Ingestion archives the raw bytes of every
fetched batch to object storage before it touches the store, so
the evidence chain — what arrived, when, with which content
hash — survives independently of the run records.
"""

from __future__ import annotations

from .datasets import build_world
from .errors import BatchNotFound
from .schemas import SourceBatch


class DatasetConnector:
    """The bundled connector: the synthetic Harborlight extracts."""

    name = "dataset"

    def __init__(self) -> None:
        self._world = build_world()
        self._by_id = {b.batch_id: b for b in self._world.batches}

    def available(self) -> list[SourceBatch]:
        return list(self._world.batches)

    def fetch(self, batch_id: str) -> SourceBatch:
        batch = self._by_id.get(batch_id)
        if batch is None:
            raise BatchNotFound(f"no staged batch {batch_id}")
        return batch
