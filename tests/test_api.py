"""The HTTP surface: thin, honest, and the same service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aidnn_close_agent.api import create_app


@pytest.fixture()
def client(service):
    return TestClient(create_app(service))


def test_health_and_readiness_name_the_wiring(client):
    assert client.get("/health").json() == {"status": "ok"}
    readiness = client.get("/readiness").json()
    assert readiness["finance_engine"] == "offline"
    assert readiness["store"] == "memory"
    assert "harborlight-close v1.0.0" in readiness["definition_pack"]
    assert client.get("/readiness").headers["X-Request-ID"]


def test_console_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "aidnn Month-End Close" in response.text
    assert "View all blueprints" in response.text


def test_build_before_ingestion_is_a_409(client):
    run = client.post("/runs", json={"period": "2026-09"}).json()
    response = client.post(f"/runs/{run['run_id']}/packs")
    assert response.status_code == 409
    assert "still waiting for" in response.json()["detail"]


@pytest.mark.parametrize("period", ["Sept 2026", "2026-13", "2026-9", ""])
def test_a_malformed_period_is_a_422_not_a_crash(client, period):
    # A run on a malformed period used to be accepted, and every
    # later step's month arithmetic (a waiver's readiness check,
    # comparatives) then failed with a 500.
    assert client.post("/runs", json={"period": period}).status_code == 422
    waiver = client.post("/waivers", json={
        "period": period, "items": ["x"], "actor": "Mara Ellison",
        "reason": "r"})
    assert waiver.status_code == 422


def test_demo_run_endpoint_tells_the_whole_story(client):
    out = client.post("/demo/run").json()
    assert out["first_pack"]["status"] == "STALE"  # superseded by the rebuild
    codes = sorted(v["code"] for v in out["first_pack"]["variances"])
    assert codes == ["DUPLICATE_JOURNAL", "IC_ONE_SIDED",
                     "SUBLEDGER_TIE_OUT", "UNMATCHED_IC_LEG"]
    second = out["second_pack"]
    assert second["status"] == "AWAITING_CONTROLLER"
    assert second["variances"] == []
    assert second["narrative"]


def test_sign_off_over_http(client):
    out = client.post("/demo/run").json()
    pack_id = out["second_pack"]["pack_id"]
    anonymous = client.post(f"/packs/{pack_id}/sign-off",
                            json={"decision": "sign", "actor": ""})
    assert anonymous.status_code == 409
    # The signature is the chain's third act: with no
    # preparation on the pack, it is refused by name.
    unprepared = client.post(
        f"/packs/{pack_id}/sign-off",
        json={"decision": "sign", "actor": "Mara Ellison"})
    assert unprepared.status_code == 409
    assert "has not been prepared" in unprepared.json()["detail"]
    prepared = client.post(f"/packs/{pack_id}/prepare",
                           json={"actor": "Priya Nair"})
    assert prepared.status_code == 200
    # The preparer cannot review their own preparation.
    own_review = client.post(
        f"/packs/{pack_id}/review",
        json={"actor": "Priya Nair", "note": "looked at it"})
    assert own_review.status_code == 409
    reviewed = client.post(
        f"/packs/{pack_id}/review",
        json={"actor": "Jonas Weber",
              "note": "reviewed the variances and the figures"})
    assert reviewed.status_code == 200
    signed = client.post(f"/packs/{pack_id}/sign-off",
                         json={"decision": "sign", "actor": "Mara Ellison"})
    assert signed.status_code == 200
    assert signed.json()["status"] == "SIGNED_OFF"
    chain = signed.json()["signoff_chain"]
    assert [a["role"] for a in chain] == ["preparer", "reviewer"]
    # A second decision on a signed pack is refused.
    again = client.post(f"/packs/{pack_id}/sign-off",
                        json={"decision": "sign", "actor": "Mara Ellison"})
    assert again.status_code == 409


def test_world_batches_are_listed(client):
    batches = client.get("/world/batches").json()
    ids = {b["batch_id"] for b in batches}
    assert "B-HLE-GL-v2" in ids
    late = [b for b in batches if b["phase"] == "late"]
    assert {b["batch_id"] for b in late} == {
        "B-HLD-GL-v2", "B-HLE-GL-v2", "B-FX-v2",
    }
