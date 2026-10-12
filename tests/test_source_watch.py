"""The post-sign-off source watch: a signed period whose
inputs moved — named on read, answered by a controller's
acknowledgement or by the restatement road, never by the
watch itself."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import sourcewatch as watch_module
from aidnn_close_agent.api import create_app
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    MEMO_RESTATEMENT_BATCH_ID,
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    SECOND_RESTATEMENT_BATCH_ID,
    build_october_world,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import GateError
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison"
PREPARER = "Priya Nair"
REVIEWER = "Jonas Weber"


def _service(store, pack_def) -> CloseService:
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_def,
    )


def _chain(service, pack_id):
    service.prepare_pack(pack_id, PREPARER)
    service.review_pack(pack_id, REVIEWER,
                        "reviewed the pack and its record")


def _snapshot(store) -> str:
    parts = []
    for records in (
        store.list_batches(), store.list_runs(),
        store.list_packs(), store.list_bundles(),
        store.list_manifests(), store.list_waivers(),
        store.list_activations(), store.list_dry_runs(),
    ):
        parts.extend(r.model_dump_json() for r in records)
    return "\n".join(sorted(parts))


@pytest.fixture()
def store():
    return InMemoryCloseStore()


@pytest.fixture()
def pack_v110():
    pack = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack is not None
    return pack


@pytest.fixture()
def signed_september(store, world, pack_def):
    """September closed and signed under pack v1.0.0; returns
    (service, signed pack as it stood at sign-off)."""
    service = _service(store, pack_def)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    pack = service.build_pack(run.run_id)
    _chain(service, pack.pack_id)
    signed = service.sign_off(pack.pack_id, "sign", CONTROLLER,
                              "September close approved")
    return service, signed


def _item(report, slot, period=PERIOD):
    return next(i for i in report.items
                if i.period == period and i.slot == slot)


# -- the watch itself ---------------------------------------------------


def test_quiet_until_a_source_moves(signed_september):
    service, _ = signed_september
    assert service.source_watch().items == []
    assert service.source_watch(PERIOD).items == []


def test_movement_named_with_both_versions(signed_september):
    service, signed = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    report = service.source_watch()
    assert len(report.items) == 1
    item = report.items[0]
    assert item.period == PERIOD
    assert item.pack_id == signed.pack_id
    assert item.slot == "HLG:gl"
    assert item.signed_batch_id == "B-HLG-GL-v1"
    assert item.signed_version == 1
    assert item.tip_batch_id == RESTATEMENT_BATCH_ID
    assert item.tip_version == 2
    assert item.chain == [RESTATEMENT_BATCH_ID]
    assert item.landed_phase == "restatement"
    assert item.state == "OPEN"
    assert item.disposition is None
    assert "rebuilds nothing" in report.boundary


def test_watch_is_a_pure_read(signed_september):
    service, _ = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    before = _snapshot(service.store)
    first = service.source_watch()
    second = service.source_watch()
    assert first == second
    assert _snapshot(service.store) == before


def test_unsigned_period_raises_nothing(store, world, pack_def):
    service = _service(store, pack_def)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    service.build_pack(run.run_id)  # built, never signed
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    assert service.source_watch().items == []


def test_legacy_single_signature_pack_is_watched(signed_september):
    """A pack signed before the chain existed carries no
    chain acts; the watch keys on SIGNED_OFF, not on the
    chain, so its movements are watched like any other's."""
    service, signed = signed_september
    legacy = signed.model_copy(update={"signoff_chain": []})
    service.store.save_pack(legacy)
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    report = service.source_watch()
    assert len(report.items) == 1
    assert report.items[0].pack_id == signed.pack_id


def test_items_order_by_period_then_slot(signed_september):
    service, _ = signed_september
    service.receive_restatement(MEMO_RESTATEMENT_BATCH_ID)
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    report = service.source_watch()
    assert [i.slot for i in report.items] == ["HLE:gl", "HLG:gl"]


# -- the acknowledgement --------------------------------------------------


def test_acknowledgement_restatement_planned(signed_september):
    service, signed = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    record = service.acknowledge_source_movement(
        PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
        "RESTATEMENT_PLANNED", CONTROLLER,
        "September will be restated alongside October's close.")
    assert record.ack_id == f"SWK-{PERIOD}-1"
    assert record.pack_id == signed.pack_id
    assert record.signed_batch_id == "B-HLG-GL-v1"
    assert record.tip_batch_id == RESTATEMENT_BATCH_ID
    assert record.disposition == "RESTATEMENT_PLANNED"
    item = _item(service.source_watch(), "HLG:gl")
    assert item.state == "ACKNOWLEDGED"
    assert item.disposition == "RESTATEMENT_PLANNED"
    assert item.acknowledged_by == CONTROLLER
    assert item.acknowledgement_reason == \
        "September will be restated alongside October's close."
    assert watch_module.open_items(service.source_watch()) == []


def test_acknowledgement_no_action_stays_on_the_record(signed_september):
    service, _ = signed_september
    service.receive_restatement(MEMO_RESTATEMENT_BATCH_ID)
    service.acknowledge_source_movement(
        PERIOD, "HLE:gl", MEMO_RESTATEMENT_BATCH_ID, "NO_ACTION",
        CONTROLLER,
        "The re-delivery corrects one journal memo; every amount "
        "stands as booked, so no figure can move.")
    item = _item(service.source_watch(), "HLE:gl")
    assert item.state == "ACKNOWLEDGED"
    assert item.disposition == "NO_ACTION"
    text = watch_module.render_text(service.source_watch())
    assert "CONSIDERED — no action, on the record" in text
    assert "every amount stands as booked" in text


def test_acknowledgement_refusals_name_their_grounds(signed_september):
    service, _ = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)

    with pytest.raises(GateError, match="must name its controller"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
            "RESTATEMENT_PLANNED", "  ", "a reason")
    with pytest.raises(GateError, match="must carry a reason"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
            "RESTATEMENT_PLANNED", CONTROLLER, " ")
    with pytest.raises(GateError, match="RESTATEMENT_PLANNED or NO_ACTION"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
            "IGNORE", CONTROLLER, "a reason")
    with pytest.raises(GateError, match="no signed pack"):
        service.acknowledge_source_movement(
            PERIOD_OCTOBER, "HLG:gl", RESTATEMENT_BATCH_ID,
            "NO_ACTION", CONTROLLER, "a reason")
    with pytest.raises(GateError, match="carries no source in slot"):
        service.acknowledge_source_movement(
            PERIOD, "HLD:crm", RESTATEMENT_BATCH_ID,
            "NO_ACTION", CONTROLLER, "a reason")
    with pytest.raises(GateError, match="has not moved"):
        service.acknowledge_source_movement(
            PERIOD, "HLD:gl", "B-HLD-GL-v2",
            "NO_ACTION", CONTROLLER, "a reason")
    with pytest.raises(GateError, match="now ends at B-HLG-GL-v2"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", "B-HLG-GL-v9",
            "NO_ACTION", CONTROLLER, "a reason")

    service.acknowledge_source_movement(
        PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
        "RESTATEMENT_PLANNED", CONTROLLER, "restating with October")
    with pytest.raises(GateError, match="already acknowledged by"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
            "NO_ACTION", CONTROLLER, "changed my mind")


def test_acknowledgement_writes_only_the_acknowledgement(signed_september):
    service, signed = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    before = _snapshot(service.store)
    signed_before = signed.model_dump_json()
    service.acknowledge_source_movement(
        PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID, "NO_ACTION",
        CONTROLLER, "Verified against the re-extract: no figure moves.")
    assert _snapshot(service.store) == before
    assert service.get_pack(signed.pack_id).model_dump_json() == \
        signed_before


def test_chain_advancing_reopens_the_item(signed_september):
    service, _ = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    service.acknowledge_source_movement(
        PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID,
        "RESTATEMENT_PLANNED", CONTROLLER, "restating with October")
    service.receive_restatement(SECOND_RESTATEMENT_BATCH_ID)
    item = _item(service.source_watch(), "HLG:gl")
    assert item.state == "OPEN"
    assert item.tip_batch_id == SECOND_RESTATEMENT_BATCH_ID
    assert item.tip_version == 3
    assert item.chain == [RESTATEMENT_BATCH_ID,
                          SECOND_RESTATEMENT_BATCH_ID]
    record = service.acknowledge_source_movement(
        PERIOD, "HLG:gl", SECOND_RESTATEMENT_BATCH_ID, "NO_ACTION",
        CONTROLLER, "The second correction is also accepted as "
                    "booked; the restatement plan already covers it.")
    assert record.ack_id == f"SWK-{PERIOD}-2"
    assert _item(service.source_watch(), "HLG:gl").state == \
        "ACKNOWLEDGED"


# -- the restatement road answers -----------------------------------------


def _sign_october(store, september_service, pack_v110):
    service = _service(store, pack_v110)
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    service.acknowledge_restatement(
        pack.pack_id, CONTROLLER, "Reviewed with FP&A.")
    _chain(service, pack.pack_id)
    return service.sign_off(pack.pack_id, "sign", CONTROLLER,
                            "October close approved")


def test_restatement_road_answers_the_item(signed_september, pack_v110):
    service, signed = signed_september
    signed_before = signed.model_dump_json()
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    service.receive_restatement(SECOND_RESTATEMENT_BATCH_ID)
    service.receive_restatement(MEMO_RESTATEMENT_BATCH_ID)
    service.acknowledge_source_movement(
        PERIOD, "HLE:gl", MEMO_RESTATEMENT_BATCH_ID, "NO_ACTION",
        CONTROLLER, "Memo only; amounts as booked.")
    october = _sign_october(service.store, service, pack_v110)
    report = service.source_watch()
    hlg = _item(report, "HLG:gl")
    assert hlg.state == "ANSWERED"
    assert hlg.tip_batch_id == SECOND_RESTATEMENT_BATCH_ID
    assert hlg.answered_by_pack_id == october.pack_id
    hle = _item(report, "HLE:gl")
    assert hle.state == "ANSWERED"
    assert hle.answered_by_pack_id == october.pack_id
    # The NO_ACTION record stays quoted on the answered item.
    assert hle.disposition == "NO_ACTION"
    assert hle.acknowledged_by == CONTROLLER
    assert watch_module.open_items(report) == []
    # The signed September pack is byte-identical throughout.
    assert service.get_pack(signed.pack_id).model_dump_json() == \
        signed_before


def test_acknowledging_an_answered_item_refused(signed_september,
                                                pack_v110):
    service, _ = signed_september
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    _sign_october(service.store, service, pack_v110)
    with pytest.raises(GateError, match="already answered by"):
        service.acknowledge_source_movement(
            PERIOD, "HLG:gl", RESTATEMENT_BATCH_ID, "NO_ACTION",
            CONTROLLER, "late to the record")


# -- over HTTP --------------------------------------------------------------


def test_watch_over_http(signed_september):
    service, signed = signed_september
    client = TestClient(create_app(service))
    assert client.get("/source-watch").json()["items"] == []
    client.post("/sources/receive",
                json={"batch_id": RESTATEMENT_BATCH_ID})
    report = client.get("/source-watch").json()
    assert len(report["items"]) == 1
    assert report["items"][0]["slot"] == "HLG:gl"
    assert "rebuilds nothing" in report["boundary"]

    face = client.get(f"/packs/{signed.pack_id}/source-watch").json()
    assert face["open_count"] == 1
    assert face["period"] == PERIOD

    created = client.post("/source-watch/acknowledge", json={
        "period": PERIOD, "slot": "HLG:gl",
        "tip_batch_id": RESTATEMENT_BATCH_ID,
        "disposition": "RESTATEMENT_PLANNED",
        "actor": CONTROLLER, "reason": "restating with October"})
    assert created.status_code == 201
    again = client.post("/source-watch/acknowledge", json={
        "period": PERIOD, "slot": "HLG:gl",
        "tip_batch_id": RESTATEMENT_BATCH_ID,
        "disposition": "NO_ACTION",
        "actor": CONTROLLER, "reason": "changed my mind"})
    assert again.status_code == 409
    assert "already acknowledged" in again.json()["detail"]

    face = client.get(f"/packs/{signed.pack_id}/source-watch").json()
    assert face["open_count"] == 0
    # The pack record itself is never decorated.
    assert client.get(f"/packs/{signed.pack_id}").json() == \
        signed.model_dump()
