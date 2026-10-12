"""Variance disposition: the second honest exit from a block.

The staged October intercompany disagreement is the proving
ground — one break named by two checks — and November is where
the carry is re-tested. These tests pin the discipline:

- a disposition is a record (named controller, written reason,
  append-only, superseding never editing), and it moves neither
  the variance nor the verifier's verdict;
- only blocking variances are dispositionable, on a BLOCKED
  pack — the restatement variance is refused by name (the
  acknowledgement governs it), and a flag that is not a
  variance has nothing to accept;
- coverage is exact: one un-dispositioned blocker still
  refuses the signature, and a break that returns with
  different figures is not the break that was accepted;
- the signed pack carries its dispositions on its face, the
  evidence bundle lists them, and the next period opens them
  as named items — cleared, still present (blocking again,
  second carry counted), or mutated.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import dispositions as dispositions_module
from aidnn_close_agent import evidence as evidence_module
from aidnn_close_agent.api import create_app
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    IC_VARIANT_BATCH_ID,
    PERIOD,
    PERIOD_NOVEMBER,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    build_november_world,
    build_october_world,
    build_world,
    october_ic_variant_batch,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import EvidenceError, GateError
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import Disposition, Variance
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison (Group Controller)"
REASON_PAIR = (
    "HLE's EUR 500 understatement is a known booking error in "
    "their close, confirmed with HLE's controller; immaterial "
    "to the group. Accepted for this period and carried — it "
    "must clear in the next close."
)
REASON_LEG = (
    "The unmatched leg is the same understatement seen from "
    "the elimination side; accepted with it, on the same terms."
)


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


def _service(store, pack_def, connector=None) -> CloseService:
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store,
        connector=connector or DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_def,
    )


@pytest.fixture()
def pack_v110():
    pack = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack is not None
    return pack


class _VariantConnector:
    name = "dataset-ic-variant"

    def __init__(self, base: DatasetConnector) -> None:
        self._base = base

    def available(self):
        return self._base.available()

    def fetch(self, batch_id: str):
        if batch_id == IC_VARIANT_BATCH_ID:
            return october_ic_variant_batch()
        return self._base.fetch(batch_id)


class _WorldConnector:
    """Serves one staged world's batches — November's route in."""

    name = "world"

    def __init__(self, world) -> None:
        self._batches = {b.batch_id: b for b in world.batches}

    def available(self):
        return list(self._batches)

    def fetch(self, batch_id: str):
        return self._batches[batch_id]


@pytest.fixture()
def variant_october(pack_v110):
    """The staged October disagreement: a BLOCKED pack whose
    only breaks are the pair disagreement and its unmatched
    leg, every figure verified."""
    store = InMemoryCloseStore()
    service = _service(store, pack_v110,
                       connector=_VariantConnector(DatasetConnector()))
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    pack = service.build_pack(run.run_id)
    assert pack.status == "BLOCKED"
    assert {v.code for v in pack.variances} == {
        "IC_DISAGREEMENT", "UNMATCHED_IC_LEG"}
    assert all(f.status == "verified" for f in pack.figures)
    return service, run, pack


def _disposition_both(service, pack) -> None:
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER, reason=REASON_PAIR)
    service.record_disposition(pack.pack_id, code="UNMATCHED_IC_LEG",
                               actor=CONTROLLER, reason=REASON_LEG)


def _signed_october_with_carry(pack_v110):
    """October's variant close, dispositioned and signed, in a
    store November can build on."""
    store = InMemoryCloseStore()
    service = _service(store, pack_v110,
                       connector=_VariantConnector(DatasetConnector()))
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    blocked = service.build_pack(run.run_id)
    _disposition_both(service, blocked)
    presented = service.build_pack(run.run_id)
    _chain(service, presented.pack_id)
    signed = service.sign_off(presented.pack_id, "sign", CONTROLLER,
                              "accepted on the record")
    return store, blocked, signed


def _november_pack(store, pack_v110, ic_purchase: str):
    world = build_november_world(ic_purchase)
    service = _service(store, pack_v110, connector=_WorldConnector(world))
    run = service.create_run(PERIOD_NOVEMBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    return service, run, service.build_pack(run.run_id)


# -- the record itself -------------------------------------------------------


def test_disposition_requires_a_named_controller_and_a_reason(
        variant_october):
    service, _, pack = variant_october
    with pytest.raises(GateError, match="must name its controller"):
        service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                                   actor="  ", reason=REASON_PAIR)
    with pytest.raises(GateError, match="must carry a reason"):
        service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                                   actor=CONTROLLER, reason="")


def test_disposition_only_on_a_blocked_pack(service, run_corrected):
    awaiting = service.build_pack(run_corrected.run_id)
    _chain(service, awaiting.pack_id)
    pack = service.sign_off(awaiting.pack_id, "sign", CONTROLLER,
                            "verified")
    assert pack.status == "SIGNED_OFF"
    with pytest.raises(GateError, match="is SIGNED_OFF"):
        service.record_disposition(pack.pack_id, code="DUPLICATE_JOURNAL",
                                   actor=CONTROLLER, reason="too late")


def test_a_flag_is_not_a_variance_and_cannot_be_dispositioned(
        variant_october):
    service, _, pack = variant_october
    # DEFINITION_CHANGED and RATE_CHANGED are comparison flags,
    # not variances: there is no break to accept, and the
    # refusal says so in the taxonomy's own terms.
    for code in ("DEFINITION_CHANGED", "RATE_CHANGED"):
        with pytest.raises(GateError,
                           match="carries no blocking variance"):
            service.record_disposition(pack.pack_id, code=code,
                                       actor=CONTROLLER,
                                       reason="accept the flag")
    with pytest.raises(GateError, match="carries no blocking variance"):
        service.record_disposition(pack.pack_id, code="SUBLEDGER_TIE_OUT",
                                   entity_id="HLG", actor=CONTROLLER,
                                   reason="not on this pack")


def test_restatement_variance_is_refused_by_name(pack_v110):
    """A BLOCKED pack that also carries a restatement: the
    restatement variance is not dispositionable — the
    acknowledgement is its governance, and the refusal names
    that instead of treating it as a break to accept."""
    store = InMemoryCloseStore()
    pack_v100 = load_definition_pack_version("harborlight-close", "1.0.0")
    assert pack_v100 is not None
    september = _service(store, pack_v100)
    world = build_world()
    run = september.create_run(PERIOD)
    september.ingest(run.run_id, [b.batch_id for b in world.batches
                                  if b.phase == "initial"])
    september.build_pack(run.run_id)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches
                      if b.phase == "late"])
    awaiting = september.build_pack(run.run_id)
    _chain(september, awaiting.pack_id)
    september.sign_off(awaiting.pack_id, "sign", CONTROLLER, "verified")
    september.receive_restatement(RESTATEMENT_BATCH_ID)
    october = _service(store, pack_v110,
                       connector=_VariantConnector(DatasetConnector()))
    oct_world = build_october_world()
    oct_run = october.create_run(PERIOD_OCTOBER)
    october.ingest(oct_run.run_id, [b.batch_id for b in oct_world.batches])
    pack = october.build_pack(oct_run.run_id)
    assert pack.status == "BLOCKED"
    assert "RESTATED_PRIOR_PERIOD" in [v.code for v in pack.variances]
    with pytest.raises(GateError,
                       match="governed by the restatement acknowledgement"):
        october.record_disposition(pack.pack_id,
                                   code="RESTATED_PRIOR_PERIOD",
                                   actor=CONTROLLER,
                                   reason="accept the restatement")


def test_recording_changes_neither_the_variance_nor_the_verdict(
        variant_october):
    service, _, pack = variant_october
    before = pack.model_dump()
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER, reason=REASON_PAIR)
    after = service.get_pack(pack.pack_id)
    assert after.status == "BLOCKED"
    assert after.variances == before["variances"] or [
        v.model_dump() for v in after.variances] == before["variances"]
    assert [f.model_dump() for f in after.figures] == before["figures"]
    record = after.dispositions[0]
    assert record.decision == "ACCEPTED_CARRY"
    assert record.actor == CONTROLLER and record.reason == REASON_PAIR
    assert record.at  # timestamped in the record's time idiom
    assert record.carry_number == 1
    assert record.origin_period == PERIOD_OCTOBER
    assert record.origin_pack_id == pack.pack_id
    assert record.subject == "ic_sales:HLD->HLE"
    assert record.detail == next(
        v.detail for v in after.variances
        if v.code == "IC_DISAGREEMENT")
    assert any(e["event"] == "variance_dispositioned"
               for e in after.audit)


def test_changing_an_acceptance_supersedes_never_edits(variant_october):
    service, _, pack = variant_october
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER, reason="first reading")
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER,
                               reason="confirmed with HLE; final reading")
    records = [d for d in service.get_pack(pack.pack_id).dispositions
               if d.code == "IC_DISAGREEMENT"]
    assert len(records) == 2
    assert records[0].reason == "first reading"  # untouched
    assert records[1].supersedes == records[0].disposition_id
    governing = dispositions_module.governing_dispositions(
        service.store, pack.run_id)
    assert [d.disposition_id for d in governing
            if d.code == "IC_DISAGREEMENT"] == [records[1].disposition_id]


# -- the sign-off consequence --------------------------------------------------


def test_one_undispositioned_blocker_still_refuses(variant_october):
    service, run, pack = variant_october
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER, reason=REASON_PAIR)
    rebuilt = service.build_pack(run.run_id)
    assert rebuilt.status == "BLOCKED"
    assert rebuilt.dispositions == []
    with pytest.raises(GateError, match="is BLOCKED"):
        service.sign_off(rebuilt.pack_id, "sign", CONTROLLER,
                         "one is still open")


def test_full_coverage_presents_and_the_face_carries_the_acceptances(
        variant_october):
    service, run, pack = variant_october
    _disposition_both(service, pack)
    presented = service.build_pack(run.run_id)
    assert presented.status == "AWAITING_CONTROLLER"
    # The verdict is unchanged: the same variances, word for
    # word, stand on the presented pack.
    assert [(v.code, v.detail) for v in presented.variances] == [
        (v.code, v.detail) for v in pack.variances]
    assert len(presented.dispositions) == 2
    assert {d.code for d in presented.dispositions} == {
        "IC_DISAGREEMENT", "UNMATCHED_IC_LEG"}
    assert all(d.actor == CONTROLLER for d in presented.dispositions)
    assert any(e["event"] == "presented_under_disposition"
               for e in presented.audit)
    _chain(service, presented.pack_id)
    signed = service.sign_off(presented.pack_id, "sign", CONTROLLER,
                              "accepted on the record")
    assert signed.status == "SIGNED_OFF"
    assert len(signed.dispositions) == 2  # on the signed face
    assert [v.code for v in signed.variances] == [
        "UNMATCHED_IC_LEG", "IC_DISAGREEMENT"]


def test_evidence_bundle_lists_the_dispositions(variant_october):
    service, run, pack = variant_october
    _disposition_both(service, pack)
    presented = service.build_pack(run.run_id)
    _chain(service, presented.pack_id)
    signed = service.sign_off(presented.pack_id, "sign", CONTROLLER,
                              "accepted on the record")
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = evidence_module.json.loads(data)
    assert document["dispositions"] is not None
    assert len(document["dispositions"]) == 2
    assert {d["actor"] for d in document["dispositions"]} == {CONTROLLER}
    raw, _ = service.evidence_download(signed.pack_id, "txt")
    text = raw.decode()
    assert "DISPOSITIONS (2)" in text
    assert REASON_PAIR[:40] in text


# -- the carry -----------------------------------------------------------------


def test_carried_break_still_present_blocks_again_and_counts_carry_two(
        pack_v110):
    store, october_blocked, signed_october = \
        _signed_october_with_carry(pack_v110)
    service, run, pack = _november_pack(store, pack_v110, "54500.00")
    assert pack.status == "BLOCKED"
    assert len(pack.opening_items) == 2
    face_ids = {d.disposition_id for d in signed_october.dispositions}
    for item in pack.opening_items:
        assert item.retest == "STILL_PRESENT"
        assert item.origin_period == PERIOD_OCTOBER
        # Origin names where the break was first accepted — the
        # blocked pack the record was written on, whose
        # acceptance the signed pack then carried on its face.
        assert item.origin_pack_id == october_blocked.pack_id
        assert item.disposition_id in face_ids
        assert item.dispositioned_by == CONTROLLER
        assert item.carry_number == 1
    reasons = {item.code: item.reason for item in pack.opening_items}
    assert reasons["IC_DISAGREEMENT"] == REASON_PAIR  # quoted
    # Accepted again: the new records state the second carry.
    _disposition_both(service, pack)
    records = service.get_pack(pack.pack_id).dispositions
    assert len(records) == 2
    for record in records:
        assert record.carry_number == 2
        assert record.origin_period == PERIOD_OCTOBER
        assert record.origin_pack_id in {
            d.origin_pack_id for d in signed_october.dispositions}
    presented = service.build_pack(run.run_id)
    assert presented.status == "AWAITING_CONTROLLER"
    assert all(d.carry_number == 2 for d in presented.dispositions)
    _chain(service, presented.pack_id)
    signed = service.sign_off(presented.pack_id, "sign", CONTROLLER,
                              "second carry, on the record")
    assert signed.status == "SIGNED_OFF"
    assert len(signed.opening_items) == 2  # the face remembers


def test_carried_break_cleared_by_events_opens_and_closes(pack_v110):
    store, _, _ = _signed_october_with_carry(pack_v110)
    service, run, pack = _november_pack(store, pack_v110, "55000.00")
    assert pack.status == "AWAITING_CONTROLLER"
    assert len(pack.opening_items) == 2
    assert all(item.retest == "CLEARED" for item in pack.opening_items)
    assert pack.dispositions == []  # nothing accepted, nothing carried on
    _chain(service, pack.pack_id)
    signed = service.sign_off(pack.pack_id, "sign", CONTROLLER,
                              "the carried break cleared itself")
    assert signed.status == "SIGNED_OFF"


def test_carried_break_mutated_is_a_new_break(pack_v110):
    store, _, _ = _signed_october_with_carry(pack_v110)
    service, run, pack = _november_pack(store, pack_v110, "54000.00")
    assert pack.status == "BLOCKED"
    assert len(pack.opening_items) == 2
    assert all(item.retest == "MUTATED" for item in pack.opening_items)
    assert all(item.current_detail and "1120.00" in item.current_detail
               for item in pack.opening_items)
    # The October acceptance does not reach across runs: the
    # mutated break needs its own acceptance, which inherits
    # the lineage and counts the second carry.
    service.record_disposition(pack.pack_id, code="IC_DISAGREEMENT",
                               actor=CONTROLLER,
                               reason="the same error, larger")
    record = service.get_pack(pack.pack_id).dispositions[0]
    assert record.carry_number == 2
    assert record.origin_period == PERIOD_OCTOBER
    assert "1120.00" in record.detail


# -- the evidence rule, bent exactly once --------------------------------------


def test_a_dispositioned_mismatch_stands_in_the_bundle_unexplained_ones_refuse(
        service, run_corrected):
    """A signed pack whose figure carries a mismatch verdict:
    the bundle refuses it — unless a disposition on the pack's
    face covers that exact variance, in which case the figure
    stands with its true verdict and its named acceptance."""
    awaiting = service.build_pack(run_corrected.run_id)
    _chain(service, awaiting.pack_id)
    signed = service.sign_off(awaiting.pack_id, "sign", CONTROLLER,
                              "verified")
    doctored = signed.model_copy(deep=True)
    figure = doctored.figures[0]
    figure.status = "mismatch"
    variance = Variance(
        code="FIGURE_MISMATCH", entity_id=figure.entity_id,
        metric_id=figure.metric_id,
        detail=f"figure {figure.metric_id} for {figure.entity_id}: "
               "engine reported the mart figure, the verifier "
               "recomputed a different one",
    )
    doctored.variances = [*doctored.variances, variance]
    service.store.save_pack(doctored)
    with pytest.raises(EvidenceError, match="no disposition"):
        service.generate_evidence(doctored.pack_id)
    doctored.dispositions = [Disposition(
        disposition_id="DISP-TEST-1", pack_id=doctored.pack_id,
        run_id=doctored.run_id, period=doctored.period,
        code="FIGURE_MISMATCH", entity_id=figure.entity_id,
        metric_id=figure.metric_id, detail=variance.detail,
        actor=CONTROLLER, reason="accepted on the record",
        at="2026-10-05T09:00:00+00:00",
        origin_period=doctored.period, origin_pack_id=doctored.pack_id,
    )]
    service.store.save_pack(doctored)
    service.generate_evidence(doctored.pack_id)
    data, _ = service.evidence_download(doctored.pack_id, "json")
    document = evidence_module.json.loads(data)
    entry = next(f for f in document["figures"]
                 if f["metric_id"] == figure.metric_id
                 and f["entity_id"] == figure.entity_id)
    assert entry["verifier_verdict"] == "mismatch"  # never upgraded
    assert document["dispositions"][0]["disposition_id"] == "DISP-TEST-1"


# -- the HTTP surface ------------------------------------------------------------


def test_disposition_endpoint_records_and_refuses(service, world):
    client = TestClient(create_app(service))
    run = client.post("/runs", json={"period": PERIOD}).json()
    client.post(f"/runs/{run['run_id']}/ingest",
                json={"batch_ids": [b.batch_id for b in world.batches
                                    if b.phase == "initial"]})
    pack = client.post(f"/runs/{run['run_id']}/packs").json()
    assert pack["status"] == "BLOCKED"
    refused = client.post(f"/packs/{pack['pack_id']}/dispositions",
                          json={"code": "DUPLICATE_JOURNAL",
                                "entity_id": "HLD",
                                "actor": CONTROLLER, "reason": ""})
    assert refused.status_code == 409
    assert "must carry a reason" in refused.json()["detail"]
    recorded = client.post(f"/packs/{pack['pack_id']}/dispositions",
                           json={"code": "DUPLICATE_JOURNAL",
                                 "entity_id": "HLD",
                                 "actor": CONTROLLER,
                                 "reason": "the duplicate is a re-sent "
                                           "extract, since withdrawn"})
    assert recorded.status_code == 200
    body = recorded.json()
    assert body["status"] == "BLOCKED"  # the pack does not move
    assert body["dispositions"][0]["decision"] == "ACCEPTED_CARRY"
    assert body["dispositions"][0]["subject"] == "J-D9"
