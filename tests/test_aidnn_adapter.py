"""The aidnn adapter: an honest contract, tested over a stub.

aidnn publishes no public API, so these tests pin the
*blueprint's contract* — the wire shape the FDE implements
against the customer's deployed workspace — and the failure
posture: unconfigured means refuse, unreachable means say so,
and the offline engine's answers are never served in aidnn's
place.
"""

from __future__ import annotations

import httpx
import pytest

from aidnn_close_agent.engine_aidnn import AidnnEngineAdapter
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import EngineNotConfigured, EngineUnavailable
from aidnn_close_agent.marts import build_marts, slot_key

WORKSPACE = "https://aidnn-workspace.internal.example"


def _marts(world, pack_def):
    slots = {}
    for batch in world.batches:
        slots[slot_key(batch)] = batch
    return build_marts(list(slots.values()), pack_def)


def test_unconfigured_adapter_refuses_to_start():
    with pytest.raises(EngineNotConfigured) as excinfo:
        AidnnEngineAdapter(workspace_url=None)
    assert "no public API" in str(excinfo.value)


def _transport(figures):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"figures": figures})
    return httpx.MockTransport(handler)


def test_adapter_maps_the_contract_response(world, pack_def):
    marts = _marts(world, pack_def)
    expected = OfflineFinanceEngine().answer(pack_def, marts)
    payload = [
        {"metric_id": f.metric_id, "label": f.label, "scope": f.scope,
         "entity_id": f.entity_id, "value": f.value, "currency": f.currency}
        for f in expected
    ]
    adapter = AidnnEngineAdapter(WORKSPACE, "test-token",
                                 transport=_transport(payload))
    figures = adapter.answer(pack_def, marts)
    assert len(figures) == len(expected)
    assert all(f.status == "proposed" for f in figures)
    by_key = {(f.metric_id, f.entity_id): f for f in figures}
    assert by_key[("consolidated_revenue", None)].value == "1796500.00"


def test_adapter_surfaces_http_failure(world, pack_def):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="workspace unavailable")

    adapter = AidnnEngineAdapter(WORKSPACE, "test-token",
                                 transport=httpx.MockTransport(handler))
    with pytest.raises(EngineUnavailable):
        adapter.answer(pack_def, _marts(world, pack_def))


def test_adapter_surfaces_network_failure(world, pack_def):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns", request=request)

    adapter = AidnnEngineAdapter(WORKSPACE, "test-token",
                                 transport=httpx.MockTransport(handler))
    with pytest.raises(EngineUnavailable):
        adapter.answer(pack_def, _marts(world, pack_def))


def test_wiring_aidnn_without_workspace_fails_loudly(monkeypatch):
    from aidnn_close_agent.wiring import build_engine

    monkeypatch.setenv("FINANCE_ENGINE", "aidnn")
    monkeypatch.delenv("AIDNN_WORKSPACE_URL", raising=False)
    with pytest.raises(EngineNotConfigured):
        build_engine()
