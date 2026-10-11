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


def test_demo_run_endpoint_tells_the_whole_story(client):
    out = client.post("/demo/run").json()
    assert out["first_pack"]["status"] == "STALE"  # superseded by the rebuild
    codes = sorted(v["code"] for v in out["first_pack"]["variances"])
    assert codes == ["DUPLICATE_JOURNAL", "SUBLEDGER_TIE_OUT",
                     "UNMATCHED_IC_LEG"]
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
    signed = client.post(f"/packs/{pack_id}/sign-off",
                         json={"decision": "sign", "actor": "Mara Ellison"})
    assert signed.status_code == 200
    assert signed.json()["status"] == "SIGNED_OFF"
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
