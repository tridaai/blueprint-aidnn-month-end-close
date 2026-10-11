"""The reference engine: gold figures on the corrected world."""

from __future__ import annotations

from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.marts import build_marts, slot_key


def _current(world, phases):
    slots = {}
    for batch in world.batches:
        if batch.phase in phases:
            slots[slot_key(batch)] = batch
    return list(slots.values())


def _by_key(figures):
    return {(f.metric_id, f.entity_id): f for f in figures}


def test_engine_answers_every_defined_figure(world, pack_def):
    marts = build_marts(_current(world, {"initial", "late"}), pack_def)
    figures = OfflineFinanceEngine().answer(pack_def, marts)
    # 5 entity metrics × 3 entities + 1 group + 9 consolidated.
    assert len(figures) == 25
    assert all(f.status == "proposed" for f in figures)
    assert all(f.definition_pack_version == pack_def.version for f in figures)


def test_engine_matches_gold_on_the_corrected_world(world, pack_def):
    marts = build_marts(_current(world, {"initial", "late"}), pack_def)
    figures = _by_key(OfflineFinanceEngine().answer(pack_def, marts))
    for key, expected in world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure = figures[(metric_id, entity_id or None)]
        assert figure.value == expected, f"{key}: {figure.value} != {expected}"


def test_engine_eliminations_need_both_legs(world, pack_def):
    first = _by_key(OfflineFinanceEngine().answer(
        pack_def, build_marts(_current(world, {"initial"}), pack_def)))
    assert first[("eliminations_total", None)].value == "0.00"
    corrected = _by_key(OfflineFinanceEngine().answer(
        pack_def, build_marts(_current(world, {"initial", "late"}), pack_def)))
    assert corrected[("eliminations_total", None)].value == "55000.00"


def test_engine_consolidation_converts_per_entity(world, pack_def):
    """EUR converts once, at the entity figure, at the current
    rate: phase A converts HLE revenue at 1.08, phase B at 1.10."""
    first = _by_key(OfflineFinanceEngine().answer(
        pack_def, build_marts(_current(world, {"initial"}), pack_def)))
    # 120000 + 1000000 + 520000*1.08
    assert first[("consolidated_revenue", None)].value == "1681600.00"
    assert first[("revenue_external", "HLE")].value == "520000.00"
    assert first[("revenue_external", "HLE")].currency == "EUR"
