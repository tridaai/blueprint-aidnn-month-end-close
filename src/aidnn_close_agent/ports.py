"""Ports: the seams a deployment is allowed to vary.

- :class:`FinanceEnginePort` — the analysis engine. In a live
  deployment this is **aidnn**: its connectors feed the governed
  marts, its agents answer the definition pack's questions, its
  plan-review step is where a human first sees the proposed
  analysis. aidnn publishes no public API (checked October 2026),
  so the port is the *integration contract* — the
  :mod:`.engine_aidnn` adapter documents the wire shape an FDE
  implements against the customer's aidnn workspace during
  deployment, and :mod:`.engine_offline` is the reference engine
  that implements the same contract over the bundled marts for
  tests, evals, and demos. The pipeline cannot tell which engine
  it is talking to; the verifier does not care either way.
- :class:`ConnectorPort` — one source system: given an entity and
  a source kind, deliver the current extract as a
  :class:`SourceBatch`. In this repo the connectors serve the
  synthetic world; in a deployment each is the customer's
  NetSuite / QuickBooks / Salesforce mirror.
- :class:`ObjectStorePort` — where raw extract bytes are
  archived: S3 (or any S3-compatible store) in production, an
  in-memory double in tests.

Port methods speak the schemas in :mod:`.schemas` — never vendor
types. Nothing about any engine's internals crosses these seams.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .definitions import DefinitionPack
from .marts import MartSet
from .schemas import Figure, SourceBatch


@runtime_checkable
class FinanceEnginePort(Protocol):
    """Answer the definition pack's questions over prepared marts.

    One call, one pack version in, one figure set out. The engine
    *proposes* — every figure it returns is marked ``proposed``
    until the independent verifier recomputes it from source.
    """

    name: str

    def answer(self, pack: DefinitionPack, marts: MartSet) -> list[Figure]:
        ...


@runtime_checkable
class ConnectorPort(Protocol):
    """Deliver source extracts. ``available`` lists the batches a
    deployment has staged; ``fetch`` returns one by id."""

    name: str

    def available(self) -> list[SourceBatch]:
        ...

    def fetch(self, batch_id: str) -> SourceBatch:
        ...


@runtime_checkable
class ObjectStorePort(Protocol):
    """Raw extract bytes, by key. ``put`` returns the key."""

    def put(self, key: str, data: bytes, content_type: str) -> str:
        ...

    def get(self, key: str) -> bytes:
        ...

    def exists(self, key: str) -> bool:
        ...


@dataclass
class PortHealth:
    ok: bool
    detail: str = ""
    checks: dict[str, str] = field(default_factory=dict)
