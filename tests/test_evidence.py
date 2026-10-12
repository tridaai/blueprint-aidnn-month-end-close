"""The audit evidence pack: gated generation, completeness
checks, byte-identical regeneration — end to end through the
service, plus the HTTP surface."""

from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent.api import create_app
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_AFFECTED,
    RESTATEMENT_BATCH_ID,
    build_october_world,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import BundleNotFound, EvidenceError
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import EvidenceBundle
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison"


PREPARER = "Priya Nair"
REVIEWER = "Jonas Weber"


def _chain(service, pack_id):
    """Walk a pack through preparation and review, so the
    controller's signature — the chain's third act — can
    stand. The two earlier hands are neither file's
    controller."""
    service.prepare_pack(pack_id, PREPARER)
    service.review_pack(pack_id, REVIEWER,
                        "reviewed the pack's variances, "
                        "dispositions, and readiness statement")


def _service(store, pack_def, objects=None) -> CloseService:
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=objects or InMemoryObjectStore(), pack_def=pack_def,
    )


def _close_september(service, world):
    """Drive September to a signed pack; returns
    (stale first pack, signed pack)."""
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    second = service.build_pack(run.run_id)
    _chain(service, second.pack_id)
    signed = service.sign_off(second.pack_id, "sign", CONTROLLER,
                              "figures verified; variances cleared")
    return service.get_pack(first.pack_id), signed


@pytest.fixture()
def signed_september(service, world):
    return _close_september(service, world)


def _document(service, record) -> dict:
    data, _ = service.evidence_download(record.pack_id, "json")
    return json.loads(data)


# -- the bundle itself ---------------------------------------------------


def test_bundle_is_a_complete_projection_of_the_signed_pack(
        service, pack_def, signed_september):
    _, signed = signed_september
    record = service.generate_evidence(signed.pack_id)
    assert record.pack_id == signed.pack_id
    assert record.period == signed.period
    assert record.figure_count == 25
    assert record.json_key == \
        f"evidence/{signed.period}/{signed.pack_id}/evidence-v1.json"
    assert record.text_key.endswith("evidence-v1.txt")

    document = _document(service, record)
    assert document["format"] == "aidnn-close-evidence/v1"
    identity = document["pack"]
    assert identity["pack_id"] == signed.pack_id
    assert identity["definition_pack_id"] == signed.definition_pack_id
    assert identity["definition_pack_version"] == "1.0.0"
    assert identity["mart_version"] == signed.mart_version

    # Every figure: the pack's value, the pack's verdict, and
    # the definition entry reproduced from the pack version.
    pack_figures = {(f.metric_id, f.entity_id): f for f in signed.figures}
    assert len(document["figures"]) == len(pack_figures) == 25
    for entry in document["figures"]:
        figure = pack_figures[(entry["metric_id"], entry["entity_id"])]
        assert entry["value"] == figure.value
        assert entry["currency"] == figure.currency
        assert entry["verifier_verdict"] == figure.status == "verified"
        assert entry["definition"] == \
            pack_def.metric(entry["metric_id"]).model_dump()

    # The manifest is exactly the batches the pack stamps, at
    # the stamped versions, with the hashes the store recorded.
    manifest = {m["batch_id"]: m for m in document["source_manifest"]}
    assert set(manifest) == set(signed.source_versions.batches)
    for batch_id, entry in manifest.items():
        batch = service.store.get_batch(batch_id)
        assert entry["version"] == signed.source_versions.batches[batch_id]
        assert entry["sha256"] == batch.sha256 != ""
        assert entry["kind"] == batch.kind
        assert entry["entity_id"] == batch.entity_id
    assert document["fx_version"] == signed.source_versions.fx_version

    # The sign-off section: the controller, and the checklist
    # state the signature froze.
    sign_off = document["sign_off"]
    run = service.get_run(signed.run_id)
    assert sign_off["actor"] == CONTROLLER
    assert sign_off["decision"] == "sign"
    assert sign_off["at"] == signed.decision.at
    assert sign_off["run_status"] == "CLOSED"
    assert sign_off["checklist"] == run.checklist
    assert sign_off["group_checklist"] == run.group_checklist
    assert sign_off["missing_sources"] == []
    # September is a first close: nothing comparative to carry.
    assert document["comparatives"] == []
    assert document["restatement"] is None


def test_regeneration_is_byte_identical(service, world, signed_september):
    _, signed = signed_september
    first = service.generate_evidence(signed.pack_id)
    first_bytes, _ = service.evidence_download(signed.pack_id, "json")
    again = service.generate_evidence(signed.pack_id)
    again_bytes, _ = service.evidence_download(signed.pack_id, "json")
    assert again == first  # same record, not a quiet rewrite
    assert again_bytes == first_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == first.sha256

    # A fresh service over the same store and object store —
    # the restart case — projects the identical bytes.
    store, objects = service.store, service.objects
    fresh = _service(store, service.pack_def, objects)
    record = fresh.generate_evidence(signed.pack_id)
    assert record.sha256 == first.sha256
    assert fresh.evidence_download(signed.pack_id, "json")[0] == first_bytes


def test_digest_matches_the_stored_bytes(service, signed_september):
    _, signed = signed_september
    record = service.generate_evidence(signed.pack_id)
    stored = service.objects.get(record.json_key)
    assert hashlib.sha256(stored).hexdigest() == record.sha256
    text = service.objects.get(record.text_key).decode("utf-8")
    assert "AUDIT EVIDENCE PACK" in text
    assert signed.pack_id in text
    assert "consolidated_revenue" in text
    # The text rendering is the same assembly: the manifest's
    # recorded hashes appear in it verbatim.
    document = json.loads(stored)
    first_batch = document["source_manifest"][0]
    assert first_batch["sha256"] in text


# -- the generation gate ---------------------------------------------------


def test_generation_refused_for_a_blocked_pack(service, world):
    run = service.create_run("2026-09")
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    blocked = service.build_pack(run.run_id)
    assert blocked.status == "BLOCKED"
    with pytest.raises(EvidenceError) as excinfo:
        service.generate_evidence(blocked.pack_id)
    assert "BLOCKED" in str(excinfo.value)
    # The refusal wrote nothing: no record, no objects.
    assert service.store.list_bundles() == []
    key = f"evidence/2026-09/{blocked.pack_id}/evidence-v1.json"
    assert not service.objects.exists(key)


def test_generation_refused_for_awaiting_and_stale_packs(service, world):
    run = service.create_run("2026-09")
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    awaiting = service.build_pack(run.run_id)
    assert service.get_pack(first.pack_id).status == "STALE"
    with pytest.raises(EvidenceError) as stale_exc:
        service.generate_evidence(first.pack_id)
    assert "STALE" in str(stale_exc.value)
    with pytest.raises(EvidenceError) as awaiting_exc:
        service.generate_evidence(awaiting.pack_id)
    assert "AWAITING_CONTROLLER" in str(awaiting_exc.value)
    assert service.store.list_bundles() == []


# -- the completeness self-check -------------------------------------------


def test_a_missing_source_batch_refuses_and_names_it(
        service, signed_september):
    _, signed = signed_september
    batch_id = sorted(signed.source_versions.batches)[0]
    # Simulate a partially-stored world: the batch record is gone.
    service.store._batches.pop(batch_id)
    with pytest.raises(EvidenceError) as excinfo:
        service.generate_evidence(signed.pack_id)
    assert batch_id in str(excinfo.value)
    assert service.store.list_bundles() == []


def test_an_unresolvable_definition_version_refuses(
        service, signed_september):
    _, signed = signed_september
    tampered = signed.model_copy(
        update={"definition_pack_version": "9.9.9"})
    service.store.save_pack(tampered)
    with pytest.raises(EvidenceError) as excinfo:
        service.generate_evidence(signed.pack_id)
    assert "9.9.9" in str(excinfo.value)


def test_an_unverified_figure_refuses(service, signed_september):
    _, signed = signed_september
    figures = [f.model_copy() for f in signed.figures]
    figures[0].status = "proposed"
    service.store.save_pack(signed.model_copy(update={"figures": figures}))
    with pytest.raises(EvidenceError) as excinfo:
        service.generate_evidence(signed.pack_id)
    assert figures[0].metric_id in str(excinfo.value)
    assert "verified" in str(excinfo.value)


def test_get_evidence_before_generation_is_a_named_miss(
        service, signed_september):
    _, signed = signed_september
    with pytest.raises(BundleNotFound):
        service.get_evidence(signed.pack_id)
    with pytest.raises(BundleNotFound):
        service.evidence_download(signed.pack_id, "json")


# -- the second month's bundle ----------------------------------------------


@pytest.fixture()
def pack_v110():
    pack = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack is not None
    return pack


def test_october_bundle_carries_comparatives_restatement_and_ack(
        service, world, pack_v110):
    store, objects = service.store, service.objects
    _, september = _close_september(service, world)

    october_service = _service(store, pack_v110, objects)
    october_service.receive_restatement(RESTATEMENT_BATCH_ID)
    october_world = build_october_world()
    run = october_service.create_run(PERIOD_OCTOBER)
    october_service.ingest(run.run_id,
                           [b.batch_id for b in october_world.batches])
    pack = october_service.build_pack(run.run_id)
    october_service.acknowledge_restatement(
        pack.pack_id, CONTROLLER, "Reviewed the HLG payroll restatement.")
    _chain(october_service, pack.pack_id)
    signed_october = october_service.sign_off(pack.pack_id, "sign",
                                              CONTROLLER)

    record = october_service.generate_evidence(signed_october.pack_id)
    document = _document(october_service, record)
    assert document["pack"]["definition_pack_version"] == "1.1.0"
    assert len(document["figures"]) == 25
    # Definitions were reproduced from v1.1.0: opex now reads
    # account 6400 (insurance), the account the upgrade added.
    opex = next(f for f in document["figures"]
                if f["metric_id"] == "opex" and f["entity_id"] == "HLG")
    assert "6400" in opex["definition"]["accounts"]

    # The comparative layer rides the bundle, citations intact.
    assert len(document["comparatives"]) == 25
    assert {c["prior_pack_id"] for c in document["comparatives"]} == \
        {september.pack_id}
    # The restatement and its acknowledgement are on the record.
    restatement = document["restatement"]
    assert restatement is not None
    affected = {
        (f"{f['metric_id']}@{f['entity_id']}" if f["entity_id"]
         else f["metric_id"]): (f["signed_value"], f["recomputed_value"])
        for f in restatement["affected_figures"]
    }
    assert affected == RESTATEMENT_AFFECTED
    acknowledgement = document["restatement_acknowledgement"]
    assert acknowledgement["actor"] == CONTROLLER
    assert [v["code"] for v in document["variances"]] == \
        ["RESTATED_PRIOR_PERIOD"]

    # September's bundle, generated through the October service,
    # resolves v1.0.0 from the registry and projects the same
    # bytes the September service would.
    september_record = october_service.generate_evidence(september.pack_id)
    september_bytes, _ = october_service.evidence_download(
        september.pack_id, "json")
    assert hashlib.sha256(september_bytes).hexdigest() == \
        september_record.sha256
    september_document = json.loads(september_bytes)
    assert september_document["pack"]["definition_pack_version"] == "1.0.0"


# -- the store surface --------------------------------------------------------


def test_bundle_records_round_trip_the_store():
    store = InMemoryCloseStore()
    record = EvidenceBundle(
        bundle_id="EVB-PACK-1", pack_id="PACK-1", run_id="RUN-1",
        period="2026-09", json_key="evidence/2026-09/PACK-1/evidence-v1.json",
        text_key="evidence/2026-09/PACK-1/evidence-v1.txt",
        sha256="ab12", figure_count=25, manifest_count=8,
        generated_at="2026-10-01T00:00:00+00:00",
    )
    store.save_bundle(record)
    assert store.get_bundle("EVB-PACK-1") == record
    assert store.list_bundles(pack_id="PACK-1") == [record]
    assert store.list_bundles(pack_id="PACK-2") == []
    assert store.get_bundle("nope") is None


# -- over HTTP ------------------------------------------------------------------


def test_evidence_over_http(service, world):
    client = TestClient(create_app(service))
    out = client.post("/demo/run").json()
    pack_id = out["second_pack"]["pack_id"]

    # Nothing generated yet: the record read is a 404.
    assert client.get(f"/packs/{pack_id}/evidence").status_code == 404

    prepared = client.post(f"/packs/{pack_id}/prepare",
                           json={"actor": PREPARER})
    assert prepared.status_code == 200
    reviewed = client.post(
        f"/packs/{pack_id}/review",
        json={"actor": REVIEWER,
              "note": "reviewed the variances and the figures"})
    assert reviewed.status_code == 200
    signed = client.post(f"/packs/{pack_id}/sign-off",
                         json={"decision": "sign", "actor": CONTROLLER})
    assert signed.status_code == 200

    created = client.post(f"/packs/{pack_id}/evidence")
    assert created.status_code == 201
    record = created.json()
    assert record["pack_id"] == pack_id
    assert record["figure_count"] == 25

    fetched = client.get(f"/packs/{pack_id}/evidence")
    assert fetched.status_code == 200
    assert fetched.json() == record

    download = client.get(f"/packs/{pack_id}/evidence/download",
                          params={"format": "json"})
    assert download.status_code == 200
    assert hashlib.sha256(download.content).hexdigest() == record["sha256"]
    text = client.get(f"/packs/{pack_id}/evidence/download",
                      params={"format": "txt"})
    assert text.status_code == 200
    assert "AUDIT EVIDENCE PACK" in text.text
    assert client.get(f"/packs/{pack_id}/evidence/download",
                      params={"format": "yaml"}).status_code == 404

    # The stale first pack is refused, state named.
    first_id = out["first_pack"]["pack_id"]
    refused = client.post(f"/packs/{first_id}/evidence")
    assert refused.status_code == 409
    assert "STALE" in refused.json()["detail"]
