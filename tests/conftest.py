from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent.config import definition_pack_path
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import PERIOD, build_world
from aidnn_close_agent.definitions import load_definition_pack
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore


@pytest.fixture()
def pack_def():
    return load_definition_pack(definition_pack_path())


@pytest.fixture()
def world():
    return build_world()


@pytest.fixture()
def service(pack_def) -> CloseService:
    store = InMemoryCloseStore()
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_def,
    )


@pytest.fixture()
def run_ready(service, world):
    """A run with the initial extracts ingested, ready to build."""
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    return service.get_run(run.run_id)


@pytest.fixture()
def run_corrected(service, world, run_ready):
    """The same run after the late extracts land."""
    service.ingest(run_ready.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    return service.get_run(run_ready.run_id)
