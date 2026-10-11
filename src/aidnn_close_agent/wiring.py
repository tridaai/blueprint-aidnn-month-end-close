"""Wiring: build the service from the environment, honestly.

Selection rules, in order:

- ``FINANCE_ENGINE=aidnn`` → the aidnn adapter, pointed at
  ``AIDNN_WORKSPACE_URL``. A missing URL fails startup with
  :class:`EngineNotConfigured` — aidnn publishes no public API
  and there is no default endpoint; the service never silently
  serves the offline engine's answers under aidnn's name.
- ``FINANCE_ENGINE=offline`` (or unset) → the reference engine
  over the local marts: labelled, deterministic, and what the
  tests, evals, and demo run.

The definition pack comes from ``DEFINITION_PACK`` when set,
else the bundled Harborlight pack — a customer deployment
carries its own pack file, versioned the same way.
"""

from __future__ import annotations

from .checkpoints import default_checkpointer
from .config import definition_pack_path, env_str, finance_engine
from .connectors import DatasetConnector
from .definitions import load_definition_pack
from .engine_aidnn import AidnnEngineAdapter
from .engine_offline import OfflineFinanceEngine
from .errors import EngineNotConfigured
from .graph import PackPipeline
from .object_store import default_object_store
from .service import CloseService
from .store import default_store


def build_engine():
    backend = finance_engine()
    if backend == "aidnn":
        return AidnnEngineAdapter(
            workspace_url=env_str("AIDNN_WORKSPACE_URL"),
            api_token=env_str("AIDNN_API_TOKEN"),
            timeout_seconds=float(env_str("AIDNN_TIMEOUT_SECONDS", "120") or "120"),
        )
    if backend == "offline":
        return OfflineFinanceEngine()
    raise EngineNotConfigured(
        f"unknown FINANCE_ENGINE {backend!r} — expected 'aidnn' or 'offline'"
    )


def build_service() -> CloseService:
    store = default_store()
    pack_def = load_definition_pack(definition_pack_path())
    pipeline = PackPipeline(
        engine=build_engine(),
        store=store,
        pack=pack_def,
        checkpointer=default_checkpointer(),
    )
    return CloseService(
        pipeline=pipeline,
        store=store,
        connector=DatasetConnector(),
        objects=default_object_store(),
        pack_def=pack_def,
    )
