"""The narrative's input discipline is the guardrail."""

from __future__ import annotations

import pytest

from aidnn_close_agent.narrative import build_narrative
from aidnn_close_agent.schemas import Figure


def _figure(metric_id, value, status="verified", entity_id=None,
            currency="USD", scope="consolidated"):
    return Figure(metric_id=metric_id, label=metric_id, scope=scope,
                  entity_id=entity_id, value=value, currency=currency,
                  status=status)


def test_narrative_composes_from_verified_figures():
    figures = [
        _figure("consolidated_revenue", "1796500.00"),
        _figure("revenue_vs_plan", "46500.00"),
        _figure("consolidated_operating_income", "783250.00"),
        _figure("consolidated_cash", "376750.00"),
        _figure("eliminations_total", "55000.00"),
        _figure("pipeline_open", "2300000.00", scope="group"),
        _figure("revenue_external", "615000.00", entity_id="HLE",
                currency="EUR", scope="entity"),
    ]
    text = build_narrative(figures, "2026-09")
    assert "1,796,500.00" in text
    assert "783,250.00" in text
    assert "HLE EUR 615,000.00" in text


def test_narrative_refuses_proposed_figures():
    figures = [_figure("consolidated_revenue", "1.00", status="proposed")]
    with pytest.raises(ValueError):
        build_narrative(figures, "2026-09")


def test_narrative_refuses_mismatched_figures():
    figures = [_figure("consolidated_revenue", "1.00", status="mismatch")]
    with pytest.raises(ValueError):
        build_narrative(figures, "2026-09")
