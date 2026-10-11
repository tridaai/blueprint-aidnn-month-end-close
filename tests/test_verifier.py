"""The verifier: independence, and one named variance per trap."""

from __future__ import annotations

from aidnn_close_agent import verifier as verifier_module
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.marts import build_marts, slot_key
from aidnn_close_agent.schemas import Figure


def _current(world, phases):
    slots = {}
    for batch in world.batches:
        if batch.phase in phases:
            slots[slot_key(batch)] = batch
    return list(slots.values())


def _engine_figures(world, pack_def, phases):
    batches = _current(world, phases)
    marts = build_marts(batches, pack_def)
    return batches, OfflineFinanceEngine().answer(pack_def, marts)


def test_verifier_catches_each_planted_trap_by_name(world, pack_def):
    batches, figures = _engine_figures(world, pack_def, {"initial"})
    report = verifier_module.verify(pack_def, batches, figures)
    codes = sorted(v.code for v in report.variances)
    assert codes == sorted(world.phase_a_variance_codes)
    assert not report.passed


def test_verifier_agrees_with_engine_on_figures_even_when_blocked(
        world, pack_def):
    """Phase A figures foot to the (flawed) sources, so the
    figure checks pass; the block comes from the structural
    variances. Verification proves figures match sources — the
    tie-out family is what catches a mis-posted account."""
    batches, figures = _engine_figures(world, pack_def, {"initial"})
    report = verifier_module.verify(pack_def, batches, figures)
    assert len(report.checks) == 25
    assert all(c.ok for c in report.checks)


def test_verifier_passes_the_corrected_world(world, pack_def):
    batches, figures = _engine_figures(world, pack_def, {"initial", "late"})
    report = verifier_module.verify(pack_def, batches, figures)
    assert report.variances == []
    assert report.passed


def test_verifier_catches_a_tampered_figure(world, pack_def):
    batches, figures = _engine_figures(world, pack_def, {"initial", "late"})
    tampered = [
        f.model_copy(update={"value": "999999.99"})
        if (f.metric_id, f.entity_id) == ("consolidated_revenue", None) else f
        for f in figures
    ]
    report = verifier_module.verify(pack_def, batches, tampered)
    assert not report.passed
    mismatch = [v for v in report.variances if v.code == "FIGURE_MISMATCH"]
    assert len(mismatch) == 1
    assert "999999.99" in mismatch[0].detail
    assert "1796500.00" in mismatch[0].detail


def test_verifier_catches_a_missing_figure(world, pack_def):
    batches, figures = _engine_figures(world, pack_def, {"initial", "late"})
    dropped = [f for f in figures if f.metric_id != "consolidated_cash"]
    report = verifier_module.verify(pack_def, batches, dropped)
    assert not report.passed
    assert any(v.code == "FIGURE_MISMATCH" and v.metric_id == "consolidated_cash"
               for v in report.variances)


def test_verifier_reads_source_not_marts(world, pack_def):
    """Independence, pinned structurally: corrupt the marts'
    version of the world and the engine changes its answer —
    the verifier, reading batches, does not."""
    batches = _current(world, {"initial", "late"})
    marts = build_marts(batches, pack_def)
    for line in marts.gl_lines:
        if line.account == "4100" and line.entity_id == "HLE":
            from decimal import Decimal
            line.credit = Decimal("1.00")
    figures = OfflineFinanceEngine().answer(pack_def, marts)
    report = verifier_module.verify(pack_def, batches, figures)
    assert not report.passed
    assert any(v.code == "FIGURE_MISMATCH" and v.metric_id == "revenue_external"
               and v.entity_id == "HLE" for v in report.variances)


def test_figure_model_roundtrip():
    figure = Figure(metric_id="cash", label="Cash", scope="entity",
                    entity_id="HLG", value="196000.00", currency="USD")
    assert Figure.model_validate_json(figure.model_dump_json()) == figure
