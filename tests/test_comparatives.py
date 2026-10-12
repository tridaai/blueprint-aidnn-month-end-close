"""The second month: comparatives, definition discipline, and
the restatement gate — end to end through the service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import comparatives as comp
from aidnn_close_agent import verifier as verifier_module
from aidnn_close_agent.api import create_app
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    DEFINITION_CHANGED_METRICS,
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_AFFECTED,
    RESTATEMENT_BATCH_ID,
    build_october_world,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import GateError
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import FigureComparative
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


def _service(store, pack_def) -> CloseService:
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_def,
        checkpointer=MemorySaver(),
    )
    return CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack_def,
    )


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


def _october_pack(store, pack_v110, *, restate: bool):
    service = _service(store, pack_v110)
    if restate:
        service.receive_restatement(RESTATEMENT_BATCH_ID)
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    return service, service.build_pack(run.run_id)


# -- period arithmetic and the registry -------------------------------


def test_previous_period_walks_the_calendar():
    assert comp.previous_period("2026-10") == "2026-09"
    assert comp.previous_period("2026-01") == "2025-12"


def test_pack_versions_coexist_in_the_registry(pack_def, pack_v110):
    assert pack_def.version == "1.0.0"
    assert pack_v110.version == "1.1.0"
    assert load_definition_pack_version("harborlight-close", "9.9.9") is None


def test_changed_metric_ids_names_the_definition_change(pack_def, pack_v110):
    assert comp.changed_metric_ids(pack_def, pack_v110) == \
        DEFINITION_CHANGED_METRICS


# -- the first close has nothing to compare against --------------------


def test_first_close_has_no_comparatives(signed_september):
    _, signed = signed_september
    assert signed.comparatives == []
    assert signed.restatement is None


# -- October: figures, comparatives, flags ------------------------------


def test_october_figures_verify_against_gold(store, signed_september,
                                             pack_v110):
    _, october = _october_pack(store, pack_v110, restate=True)
    assert october.status == "AWAITING_CONTROLLER"
    figures = {(f.metric_id, f.entity_id): f for f in october.figures}
    for key, expected in build_october_world().gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure = figures[(metric_id, entity_id or None)]
        assert figure.value == expected, key
        assert figure.status == "verified"
        assert figure.definition_pack_version == "1.1.0"
    # The month's own sources are clean: the only variance is
    # the restatement hold on the signature.
    assert [v.code for v in october.variances] == ["RESTATED_PRIOR_PERIOD"]


def test_comparatives_cite_the_signed_pack_exactly(store, signed_september,
                                                   pack_v110):
    _, signed = signed_september
    _, october = _october_pack(store, pack_v110, restate=True)
    assert len(october.comparatives) == len(signed.figures) == 25
    signed_by_key = {(f.metric_id, f.entity_id): f for f in signed.figures}
    for comparative in october.comparatives:
        key = (comparative.metric_id, comparative.entity_id)
        # The cited value IS the signed figure — string for string.
        assert comparative.prior_value == signed_by_key[key].value
        assert comparative.prior_pack_id == signed.pack_id
        assert comparative.prior_definition_pack_version == "1.0.0"
    by_key = {(c.metric_id, c.entity_id): c for c in october.comparatives}
    revenue = by_key[("consolidated_revenue", None)]
    assert revenue.change == "115140.00"
    assert revenue.change_pct == "6.41"
    assert by_key[("opex", "HLD")].change == "-4550.00"
    # A zero prior makes the % meaningless, and the pack says so
    # by carrying None rather than a invented number.
    assert by_key[("revenue_ic", "HLG")].change_pct is None


def test_definition_changed_flags_ride_the_comparatives(
        store, signed_september, pack_v110):
    _, october = _october_pack(store, pack_v110, restate=True)
    flagged = {c.metric_id for c in october.comparatives
               if c.definition_changed}
    assert flagged == DEFINITION_CHANGED_METRICS


# -- the restatement ------------------------------------------------------


def test_restatement_is_detected_and_named(store, signed_september,
                                           pack_v110):
    _, signed = signed_september
    _, october = _october_pack(store, pack_v110, restate=True)
    report = october.restatement
    assert report is not None
    assert report.prior_period == PERIOD
    assert report.prior_pack_id == signed.pack_id
    assert report.restated_batch_ids == [RESTATEMENT_BATCH_ID]
    affected = {
        (f"{f.metric_id}@{f.entity_id}" if f.entity_id else f.metric_id):
            (f.signed_value, f.recomputed_value)
        for f in report.affected_figures
    }
    assert affected == RESTATEMENT_AFFECTED
    # The variance names signed vs recomputed for the figures.
    variance = october.variances[0]
    assert "54000.00" in variance.detail and "61000.00" in variance.detail
    # And the comparatives of the moved figures are flagged —
    # while still showing the SIGNED values.
    restated = {(c.metric_id, c.entity_id) for c in october.comparatives
                if c.restated}
    assert restated == {
        ("opex", "HLG"), ("cash", "HLG"), ("consolidated_opex", None),
        ("consolidated_operating_income", None), ("consolidated_cash", None),
    }


def test_without_a_restatement_there_is_no_hold(store, signed_september,
                                               pack_v110):
    service, october = _october_pack(store, pack_v110, restate=False)
    assert october.restatement is None
    assert october.variances == []
    assert len(october.comparatives) == 25
    _chain(service, october.pack_id)
    signed = service.sign_off(october.pack_id, "sign", CONTROLLER)
    assert signed.status == "SIGNED_OFF"


def test_sign_off_is_refused_until_the_restatement_is_acknowledged(
        store, signed_september, pack_v110):
    service, october = _october_pack(store, pack_v110, restate=True)
    with pytest.raises(GateError) as excinfo:
        service.sign_off(october.pack_id, "sign", CONTROLLER)
    assert "unacknowledged restatement" in str(excinfo.value)

    with pytest.raises(GateError):
        service.acknowledge_restatement(october.pack_id, "  ", "a note")
    with pytest.raises(GateError):
        service.acknowledge_restatement(october.pack_id, CONTROLLER, "  ")

    acked = service.acknowledge_restatement(
        october.pack_id, CONTROLLER,
        "Reviewed the HLG payroll restatement with FP&A.")
    assert acked.restatement_acknowledgement.actor == CONTROLLER
    assert any(a["event"] == "restatement_acknowledged" for a in acked.audit)
    with pytest.raises(GateError):
        service.acknowledge_restatement(october.pack_id, CONTROLLER,
                                        "twice is not a thing")

    _chain(service, october.pack_id)
    signed = service.sign_off(october.pack_id, "sign", CONTROLLER)
    assert signed.status == "SIGNED_OFF"
    # The variance and the acknowledgement stay on the record.
    assert [v.code for v in signed.variances] == ["RESTATED_PRIOR_PERIOD"]
    assert signed.restatement_acknowledgement is not None


def test_the_signed_prior_pack_never_changes(store, signed_september,
                                             pack_v110):
    service, signed = signed_september
    at_sign_off = signed.model_dump_json()
    service, october = _october_pack(store, pack_v110, restate=True)
    assert store.get_pack(signed.pack_id).model_dump_json() == at_sign_off
    service.acknowledge_restatement(october.pack_id, CONTROLLER,
                                    "seen and reviewed")
    _chain(service, october.pack_id)
    service.sign_off(october.pack_id, "sign", CONTROLLER)
    assert store.get_pack(signed.pack_id).model_dump_json() == at_sign_off


# -- the comparative check itself -----------------------------------------


def test_verify_comparatives_demands_citation_exactness(signed_september):
    _, signed = signed_september
    figure = signed.figures[0]
    good = FigureComparative(
        metric_id=figure.metric_id, entity_id=figure.entity_id,
        prior_value=figure.value, prior_currency=figure.currency,
        prior_pack_id=signed.pack_id)
    assert verifier_module.verify_comparatives([good], signed) == []

    forged = good.model_copy(update={"prior_value": "1.00"})
    variances = verifier_module.verify_comparatives([forged], signed)
    assert [v.code for v in variances] == ["COMPARATIVE_MISMATCH"]
    assert figure.value in variances[0].detail

    ghost = good.model_copy(update={"metric_id": "not_a_metric"})
    variances = verifier_module.verify_comparatives([ghost], signed)
    assert [v.code for v in variances] == ["COMPARATIVE_MISMATCH"]


# -- over HTTP --------------------------------------------------------------


def test_restatement_flow_over_http(store, signed_september, pack_v110):
    _, signed = signed_september
    service = _service(store, pack_v110)
    client = TestClient(create_app(service))

    received = client.post("/sources/receive",
                           json={"batch_id": RESTATEMENT_BATCH_ID})
    assert received.status_code == 200
    assert received.json()["phase"] == "restatement"
    assert client.post("/sources/receive",
                       json={"batch_id": "B-NOPE"}).status_code == 404

    run = client.post("/runs", json={"period": PERIOD_OCTOBER}).json()
    october_ids = [b["batch_id"] for b in client.get("/world/batches").json()
                   if b["batch_id"].startswith("O-")]
    client.post(f"/runs/{run['run_id']}/ingest",
                json={"batch_ids": october_ids})
    pack = client.post(f"/runs/{run['run_id']}/packs").json()
    assert pack["status"] == "AWAITING_CONTROLLER"
    assert len(pack["comparatives"]) == 25
    assert pack["restatement"]["affected_figures"]

    refused = client.post(f"/packs/{pack['pack_id']}/sign-off",
                          json={"decision": "sign", "actor": CONTROLLER})
    assert refused.status_code == 409
    assert "unacknowledged restatement" in refused.json()["detail"]

    acked = client.post(
        f"/packs/{pack['pack_id']}/acknowledge-restatement",
        json={"actor": CONTROLLER, "note": "Reviewed with FP&A."})
    assert acked.status_code == 200
    assert acked.json()["restatement_acknowledgement"]["actor"] == CONTROLLER

    prepared = client.post(f"/packs/{pack['pack_id']}/prepare",
                           json={"actor": PREPARER})
    assert prepared.status_code == 200
    reviewed = client.post(
        f"/packs/{pack['pack_id']}/review",
        json={"actor": REVIEWER,
              "note": "reviewed the comparatives and the restatement"})
    assert reviewed.status_code == 200
    signed_october = client.post(
        f"/packs/{pack['pack_id']}/sign-off",
        json={"decision": "sign", "actor": CONTROLLER})
    assert signed_october.status_code == 200
    assert signed_october.json()["status"] == "SIGNED_OFF"
    # September's record over HTTP is the record that was signed.
    assert client.get(f"/packs/{signed.pack_id}").json() == \
        signed.model_dump()
