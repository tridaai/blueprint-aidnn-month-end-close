"""The store: identical behaviour from the double; the Postgres
implementation is exercised where a database is configured."""

from __future__ import annotations

import os

import pytest

from aidnn_close_agent.datasets import build_world
from aidnn_close_agent.schemas import CloseRun
from aidnn_close_agent.store import InMemoryCloseStore, PostgresCloseStore


def test_memory_store_round_trips(world):
    store = InMemoryCloseStore()
    batch = world.batches[0]
    store.save_batch(batch)
    assert store.get_batch(batch.batch_id) == batch
    run = CloseRun(run_id="RUN-1", period="2026-09")
    store.save_run(run)
    assert store.list_runs() == [run]
    assert store.get_run("nope") is None
    assert store.list_packs(run_id="RUN-1") == []


def test_batches_are_append_only_by_id(world):
    store = InMemoryCloseStore()
    v1 = world.batch("B-HLD-GL-v1")
    v2 = world.batch("B-HLD-GL-v2")
    store.save_batch(v1)
    store.save_batch(v2)
    assert store.get_batch("B-HLD-GL-v1") == v1  # history is not rewritten
    assert store.get_batch("B-HLD-GL-v2") == v2


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Postgres store test needs TEST_DATABASE_URL",
)
def test_postgres_store_round_trips(world):
    store = PostgresCloseStore(os.environ["TEST_DATABASE_URL"])
    batch = world.batches[0]
    store.save_batch(batch)
    assert store.get_batch(batch.batch_id) == batch
    run = CloseRun(run_id="RUN-PG-TEST", period="2026-09")
    store.save_run(run)
    assert store.get_run("RUN-PG-TEST") == run
