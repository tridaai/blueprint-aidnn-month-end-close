"""Pre-close readiness: the expectation manifest, the check,
the build gate, and the waiver.

The pinned rules, in order:

- the manifests for the bundled periods are *derived* from
  the batches the closes actually used — September's signed
  close stood on the corrected extracts, so its manifest
  expects HLD:gl, HLE:gl, and GROUP:fx at v2 and everything
  else at v1; October and November closed on first deliveries
  throughout;
- a manifest is a record: named author, a note, append-only
  amendment by new version;
- the check is a pure read — expected vs received by slot,
  version equality exact (short below, ahead above), the
  rate table checked as coverage of the period's currencies;
- the prior period's state is reported (signed / no prior
  close / packs but none signed), never required;
- the build refuses uncovered failures by name; a waiver
  covers exactly the items it names — no blanket waivers,
  no items the check is not failing on, no waivers for a
  signed period;
- a pack built under a manifest states the readiness on its
  face; its evidence bundle carries the manifest and the
  waiver records it cites, and refuses when a citation does
  not stand.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import readiness as readiness_module
from aidnn_close_agent.api import create_app
from aidnn_close_agent.datasets import (
    PERIOD,
    PERIOD_NOVEMBER,
    PERIOD_OCTOBER,
    build_manifest_entries,
    build_november_world,
    build_october_world,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import EvidenceError, GateError, ReadinessError
from aidnn_close_agent.fx import RateTable
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import (
    CloseRun,
    ManifestEntry,
    SourceBatch,
)
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

ACTOR = "Test Controller"
NOTE = ("Derived from the batches the period's close "
        "actually used — see datasets.build_manifest_entries.")
SHORT_ITEMS = [
    "GROUP:fx (received v1, expected v2)",
    "HLD:gl (received v1, expected v2)",
    "HLE:gl (received v1, expected v2)",
]


class _WorldConnector:
    """Serves one staged world's batches by id."""

    name = "world"

    def __init__(self, world) -> None:
        self._batches = {b.batch_id: b for b in world.batches}

    def available(self):
        return list(self._batches.values())

    def fetch(self, batch_id: str):
        return self._batches[batch_id]


def _service_v110(store, connector) -> CloseService:
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=connector,
        objects=InMemoryObjectStore(), pack_def=pack_v110,
    )


def _record_derived(service, period, actor=ACTOR):
    return service.record_manifest(
        period, build_manifest_entries(period), actor, NOTE)


def _store_snapshot(store) -> str:
    parts = []
    for records in (
        store.list_batches(), store.list_runs(), store.list_packs(),
        store.list_bundles(), store.list_manifests(),
        store.list_waivers(), store.list_activations(),
        store.list_dry_runs(),
    ):
        parts.extend(r.model_dump_json() for r in records)
    return "\n".join(sorted(parts))


# -- the derivation ---------------------------------------------------


def test_derived_manifests_match_the_worlds():
    september = {e.slot: (e.expected_version, e.expected_batch_id)
                 for e in build_manifest_entries(PERIOD)}
    assert september == {
        "HLG:gl": (1, "B-HLG-GL-v1"), "HLG:ar": (1, "B-HLG-AR-v1"),
        "HLD:gl": (2, "B-HLD-GL-v2"), "HLD:ar": (1, "B-HLD-AR-v1"),
        "HLE:gl": (2, "B-HLE-GL-v2"), "HLE:ar": (1, "B-HLE-AR-v1"),
        "GROUP:fx": (2, "B-FX-v2"), "GROUP:crm": (1, "B-CRM-v1"),
    }
    for period, prefix in ((PERIOD_OCTOBER, "O-"),
                           (PERIOD_NOVEMBER, "N-")):
        entries = {e.slot: (e.expected_version, e.expected_batch_id)
                   for e in build_manifest_entries(period)}
        assert len(entries) == 8
        assert all(v == 1 for v, _ in entries.values())
        assert all(b.startswith(prefix)
                   for _, b in entries.values())


# -- the manifest record ----------------------------------------------


def test_manifest_recording_and_amendment_chain(service):
    first = _record_derived(service, PERIOD)
    assert first.manifest_id == "MAN-2026-09-1"
    assert first.version == 1 and first.supersedes is None
    entries = build_manifest_entries(PERIOD)
    for entry in entries:
        if entry.slot == "HLE:ar":
            entry.expected_version = 2
    second = service.record_manifest(PERIOD, entries, ACTOR,
                                     "HLE re-issues AR at v2.")
    assert second.manifest_id == "MAN-2026-09-2"
    assert second.version == 2
    assert second.supersedes == "MAN-2026-09-1"
    assert readiness_module.latest_manifest(
        service.store, PERIOD).manifest_id == "MAN-2026-09-2"
    # The superseded version stays on record, citable.
    assert service.store.get_manifest("MAN-2026-09-1") is not None


def test_manifest_refusals_name_their_grounds(service):
    entries = build_manifest_entries(PERIOD)
    with pytest.raises(GateError, match="must name its author"):
        service.record_manifest(PERIOD, entries, "", NOTE)
    with pytest.raises(GateError, match="must carry a note"):
        service.record_manifest(PERIOD, entries, ACTOR, "")
    with pytest.raises(GateError, match="expects nothing"):
        service.record_manifest(PERIOD, [], ACTOR, NOTE)
    with pytest.raises(GateError, match="twice"):
        service.record_manifest(
            PERIOD, entries + [entries[0]], ACTOR, NOTE)
    wrong_slot = ManifestEntry(slot="HLG:ar", kind="gl",
                               entity_id="HLG", expected_version=1)
    with pytest.raises(GateError, match="derived, never restated"):
        service.record_manifest(PERIOD, [wrong_slot], ACTOR, NOTE)
    zero = ManifestEntry(slot="HLG:gl", kind="gl", entity_id="HLG",
                         expected_version=0)
    with pytest.raises(GateError, match="start at 1"):
        service.record_manifest(PERIOD, [zero], ACTOR, NOTE)


# -- the check ----------------------------------------------------------


def test_no_manifest_reads_as_no_manifest(service, run_ready):
    report = service.readiness(run_ready.run_id)
    assert report.status == "NO_MANIFEST"
    assert report.manifest_id is None and report.items == []
    assert report.prior_period == "2026-08"
    assert report.prior_state == "NO_PRIOR_CLOSE"


def test_readiness_complete_and_stated_on_the_pack(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches])
    report = service.readiness(run.run_id)
    assert report.status == "READY"
    assert report.manifest_id == "MAN-2026-09-1"
    assert report.manifest_version == 1
    assert all(e.state == "ok" for e in report.entries)
    assert len(report.entries) == 8
    pack = service.build_pack(run.run_id)
    assert pack.readiness is not None
    assert pack.readiness.status == "COMPLETE"
    assert pack.readiness.manifest_id == "MAN-2026-09-1"
    assert pack.readiness.expected_count == 8
    assert pack.readiness.waived_items == []
    stated = [a for a in pack.audit if a["event"] == "readiness_stated"]
    assert len(stated) == 1
    assert "readiness complete under manifest MAN-2026-09-1" \
        in stated[0]["detail"]


def test_readiness_is_a_pure_read(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    before = _store_snapshot(service.store)
    report = service.readiness(run.run_id)
    assert report.status == "NOT_READY"
    assert _store_snapshot(service.store) == before


def test_missing_batch_named(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id, [
        b.batch_id for b in world.batches
        if b.batch_id != "B-HLG-AR-v1"
    ])
    report = service.readiness(run.run_id)
    missing = [e for e in report.entries if e.state == "missing"]
    assert [e.slot for e in missing] == ["HLG:ar"]
    assert "HLG:ar" in [i.name for i in report.items]
    detail = next(i.detail for i in report.items if i.name == "HLG:ar")
    assert "expected source not received" in detail


def test_version_shortfalls_named_and_build_refused(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    report = service.readiness(run.run_id)
    assert report.status == "NOT_READY"
    assert sorted(i.name for i in report.items) == SHORT_ITEMS
    states = {e.slot: e.state for e in report.entries}
    assert states["HLD:gl"] == "short"
    assert states["HLE:gl"] == "short"
    assert states["GROUP:fx"] == "short"
    with pytest.raises(ReadinessError) as excinfo:
        service.build_pack(run.run_id)
    for name in SHORT_ITEMS:
        assert name in str(excinfo.value)
    assert "MAN-2026-09-1" in str(excinfo.value)


def _fabricated_check(batches, entries, pack_def):
    """The pure check over hand-built records: the states no
    seeded world produces (ahead-of-manifest deliveries, rate
    tables with holes) exist only as fabricated records."""
    from aidnn_close_agent.schemas import ExpectationManifest
    store = InMemoryCloseStore()
    for batch in batches:
        store.save_batch(batch)
    run = CloseRun(
        run_id="RUN-TEST", period="2026-09",
        current_batches={
            (b.entity_id or "GROUP") + ":" + b.kind: b.batch_id
            for b in batches
        },
    )
    record = ExpectationManifest(
        manifest_id="MAN-2026-09-1", period="2026-09", version=1,
        actor=ACTOR, note=NOTE, entries=entries)
    return readiness_module.check_readiness(store, run, pack_def, record)


def test_version_ahead_is_a_different_delivery(pack_def):
    batch = SourceBatch(batch_id="B-HLG-GL-v2", kind="gl",
                        entity_id="HLG", version=2)
    entry = ManifestEntry(slot="HLG:gl", kind="gl", entity_id="HLG",
                          expected_version=1,
                          expected_batch_id="B-HLG-GL-v1")
    report = _fabricated_check([batch], [entry], pack_def)
    assert report.entries[0].state == "ahead"
    assert [i.name for i in report.items] == [
        "HLG:gl (received v2, expected v1)"]
    assert "amend the manifest" in report.items[0].detail


def test_rate_table_gaps_named(pack_def):
    gl = SourceBatch(batch_id="B-HLE-GL-v1", kind="gl",
                     entity_id="HLE", version=1)
    entry_gl = ManifestEntry(slot="HLE:gl", kind="gl",
                             entity_id="HLE", expected_version=1)
    entry_fx = ManifestEntry(slot="GROUP:fx", kind="fx",
                             expected_version=1)
    no_table = SourceBatch(batch_id="B-FX-v1", kind="fx", version=1,
                           rate_table=None)
    report = _fabricated_check([gl, no_table], [entry_gl, entry_fx],
                               pack_def)
    assert [i.name for i in report.items] == ["GROUP:fx (no rate table)"]
    thin = SourceBatch(
        batch_id="B-FX-v9", kind="fx", version=1,
        rate_table=RateTable(version=9, reporting_currency="USD",
                              rates={}))
    report = _fabricated_check([gl, thin], [entry_gl, entry_fx],
                               pack_def)
    assert [i.name for i in report.items] == [
        "FX:EUR (no rate in table v9)"]


# -- prior period state: reported, never required -----------------------


def test_prior_period_states(service, world, pack_def):
    run = service.create_run(PERIOD)
    assert service.readiness(run.run_id).prior_state == "NO_PRIOR_CLOSE"
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    assert first.status == "BLOCKED"  # unsigned packs on record
    store = service.store
    october = _service_v110(store, service.connector)
    october_world = build_october_world()
    orun = october.create_run(PERIOD_OCTOBER)
    report = october.readiness(orun.run_id)
    assert report.prior_state == "PRIOR_UNSIGNED"
    assert report.prior_pack_id is None

    # Sign September, and the state names the signed pack.
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    second = service.build_pack(run.run_id)
    signed = service.sign_off(second.pack_id, "sign", ACTOR)
    report = october.readiness(orun.run_id)
    assert report.prior_state == "SIGNED"
    assert report.prior_pack_id == signed.pack_id
    # …and it never blocks a build: October builds comparative.
    october.ingest(orun.run_id,
                   [b.batch_id for b in october_world.batches])
    pack = october.build_pack(orun.run_id)
    assert pack.comparatives  # the citation exists; nothing was required


# -- the waiver ---------------------------------------------------------


def _short_september(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    return run


def test_waiver_discipline(service, world):
    run = _short_september(service, world)
    with pytest.raises(GateError, match="must name its controller"):
        service.record_waiver(PERIOD, SHORT_ITEMS, "", "reason")
    with pytest.raises(GateError, match="must carry a reason"):
        service.record_waiver(PERIOD, SHORT_ITEMS, ACTOR, "")
    with pytest.raises(GateError, match="blanket waiver"):
        service.record_waiver(PERIOD, [], ACTOR, "just build it")
    with pytest.raises(GateError, match="not a failing item"):
        service.record_waiver(PERIOD, ["GROUP:crm"], ACTOR,
                              "the CRM extract is late")
    waiver = service.record_waiver(
        PERIOD, SHORT_ITEMS, ACTOR,
        "The v1 extracts are the period's opening position; "
        "the corrected deliveries are confirmed in flight.")
    assert waiver.waiver_id == "WVR-2026-09-1"
    assert waiver.items == SHORT_ITEMS

    pack = service.build_pack(run.run_id)
    assert pack.status == "BLOCKED"  # the planted traps stand
    assert pack.readiness is not None
    assert pack.readiness.status == "WAIVED"
    assert pack.readiness.waived_items == SHORT_ITEMS
    assert len(pack.readiness.waivers) == 1
    citation = pack.readiness.waivers[0]
    assert citation.waiver_id == "WVR-2026-09-1"
    assert citation.actor == ACTOR
    assert "opening position" in citation.reason

    # The corrected deliveries land; the rebuild starts complete.
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    rebuilt = service.build_pack(run.run_id)
    assert rebuilt.readiness is not None
    assert rebuilt.readiness.status == "COMPLETE"


def test_waiver_needs_a_run_and_a_manifest(service, world):
    _record_derived(service, PERIOD_OCTOBER)
    with pytest.raises(GateError, match="no close run exists"):
        service.record_waiver(PERIOD_OCTOBER, ["HLE:ar"], ACTOR,
                              "no run yet")
    run = service.create_run(PERIOD_NOVEMBER)
    with pytest.raises(GateError, match="no manifest governs"):
        service.record_waiver(PERIOD_NOVEMBER, ["HLE:ar"], ACTOR,
                              "nothing governs November")


def test_waiver_for_another_failure_does_not_unblock(service):
    store = service.store
    october = _service_v110(store, _WorldConnector(build_october_world()))
    _record_derived(october, PERIOD_OCTOBER)
    world = build_october_world()
    run1 = october.create_run(PERIOD_OCTOBER)
    october.ingest(run1.run_id, [
        b.batch_id for b in world.batches if b.kind != "crm"])
    october.record_waiver(PERIOD_OCTOBER, ["GROUP:crm"], ACTOR,
                          "The pipeline extract is a weekly file; "
                          "this month's is confirmed in flight.")
    entries = build_manifest_entries(PERIOD_OCTOBER)
    for entry in entries:
        if entry.slot == "HLE:ar":
            entry.expected_version = 2
    october.record_manifest(PERIOD_OCTOBER, entries, ACTOR,
                            "HLE re-issues its AR extract at v2.")
    run2 = october.create_run(PERIOD_OCTOBER)
    october.ingest(run2.run_id, [b.batch_id for b in world.batches])
    with pytest.raises(ReadinessError) as excinfo:
        october.build_pack(run2.run_id)
    assert "HLE:ar (received v1, expected v2)" in str(excinfo.value)
    assert "GROUP:crm" not in str(excinfo.value)


def test_waiver_refused_once_the_period_is_signed(service, world):
    run = service.create_run(PERIOD)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    signed = service.sign_off(pack.pack_id, "sign", ACTOR)
    _record_derived(service, PERIOD)
    with pytest.raises(GateError, match="already signed"):
        service.record_waiver(PERIOD, ["HLE:ar"], ACTOR,
                              "too late, on purpose")
    # Recording governance after the fact moves nothing signed.
    assert service.get_pack(pack.pack_id).model_dump_json() \
        == signed.model_dump_json()


def test_waived_build_signs_and_the_bundle_carries_it(service):
    store = InMemoryCloseStore()
    october = _service_v110(store, _WorldConnector(build_october_world()))
    _record_derived(october, PERIOD_OCTOBER)
    entries = build_manifest_entries(PERIOD_OCTOBER)
    for entry in entries:
        if entry.slot == "HLE:ar":
            entry.expected_version = 2
    october.record_manifest(PERIOD_OCTOBER, entries, ACTOR,
                            "HLE re-issues its AR extract at v2 "
                            "after the subledger fix.")
    world = build_october_world()
    run = october.create_run(PERIOD_OCTOBER)
    october.ingest(run.run_id, [b.batch_id for b in world.batches])
    report = october.readiness(run.run_id)
    assert [i.name for i in report.items] == [
        "HLE:ar (received v1, expected v2)"]
    october.record_waiver(
        PERIOD_OCTOBER, ["HLE:ar (received v1, expected v2)"],
        ACTOR,
        "HLE's v1 extract is the corrected subledger's own "
        "output, re-issued under the old version by their "
        "connector; the content is the v2 content.")
    pack = october.build_pack(run.run_id)
    assert pack.status == "AWAITING_CONTROLLER"
    assert pack.readiness is not None
    assert pack.readiness.status == "WAIVED"
    assert pack.readiness.manifest_version == 2
    signed = october.sign_off(pack.pack_id, "sign", ACTOR)
    assert signed.status == "SIGNED_OFF"

    october.generate_evidence(pack.pack_id)
    data, _ = october.evidence_download(pack.pack_id, "json")
    import json
    document = json.loads(data)
    section = document["readiness"]
    assert section["statement"]["status"] == "WAIVED"
    assert section["statement"]["waived_items"] == [
        "HLE:ar (received v1, expected v2)"]
    assert section["manifest"]["manifest_id"] == "MAN-2026-10-2"
    assert len(section["waivers"]) == 1
    assert section["waivers"][0]["actor"] == ACTOR
    assert "re-issued under the old version" \
        in section["waivers"][0]["reason"]
    text, _ = october.evidence_download(pack.pack_id, "txt")
    assert "READINESS — WAIVED" in text.decode("utf-8")

    # A citation that no longer stands refuses the bundle.
    del store._waivers["WVR-2026-10-1"]
    with pytest.raises(EvidenceError, match="WVR-2026-10-1"):
        october.generate_evidence(pack.pack_id)


def test_complete_builds_bundle_states_readiness(service, world):
    _record_derived(service, PERIOD)
    run = service.create_run(PERIOD)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    signed = service.sign_off(pack.pack_id, "sign", ACTOR)
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    import json
    document = json.loads(data)
    assert document["readiness"]["statement"]["status"] == "COMPLETE"
    assert document["readiness"]["manifest"]["manifest_id"] \
        == "MAN-2026-09-1"
    assert document["readiness"]["waivers"] == []
    text, _ = service.evidence_download(signed.pack_id, "txt")
    assert "READINESS — COMPLETE" in text.decode("utf-8")


def test_unmanifested_pack_projects_readiness_null(service, world):
    run = service.create_run(PERIOD)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    assert pack.readiness is None
    signed = service.sign_off(pack.pack_id, "sign", ACTOR)
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    import json
    assert json.loads(data)["readiness"] is None


# -- the HTTP surface ----------------------------------------------------


def test_readiness_over_http(service, world):
    client = TestClient(create_app(service))
    _record_derived(service, PERIOD)
    run = client.post("/runs", json={"period": PERIOD}).json()
    client.post(f"/runs/{run['run_id']}/ingest", json={
        "batch_ids": [b.batch_id
                      for b in world.batches_in_phase("initial")]})
    report = client.get(f"/runs/{run['run_id']}/readiness").json()
    assert report["status"] == "NOT_READY"
    assert sorted(i["name"] for i in report["items"]) == SHORT_ITEMS
    refused = client.post(f"/runs/{run['run_id']}/packs")
    assert refused.status_code == 409
    assert "readiness" in refused.json()["detail"]
    waiver = client.post("/waivers", json={
        "period": PERIOD, "items": SHORT_ITEMS, "actor": ACTOR,
        "reason": "Opening position; corrections in flight."})
    assert waiver.status_code == 201
    built = client.post(f"/runs/{run['run_id']}/packs")
    assert built.status_code == 201
    assert built.json()["readiness"]["status"] == "WAIVED"
    manifests = client.get("/manifests", params={"period": PERIOD}).json()
    assert [m["manifest_id"] for m in manifests] == ["MAN-2026-09-1"]
