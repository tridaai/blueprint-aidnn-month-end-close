"""Rate provenance: the stamp, the recomputation basis, the flags.

A converted figure is only as trustworthy as the rate nobody
wrote down — so now the rate is written down: the table rides
the provenance stamp, the verifier recomputes at the stamped
table and names any other basis, and a comparative crossing a
rate move is flagged RATE_CHANGED exactly where the moved
currency flows.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import verifier as verifier_module
from aidnn_close_agent.datasets import (
    PERIOD,
    PERIOD_OCTOBER,
    RATE_CHANGED_METRICS,
    build_october_world,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.fx import RateTable, changed_currencies
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.marts import build_marts, slot_key
from aidnn_close_agent.service import CloseService

HONEST_OCTOBER_TABLE = RateTable(
    version=3, reporting_currency="USD", rates={"EUR": "1.12"})
EDITED_TABLE = RateTable(
    version=3, reporting_currency="USD", rates={"EUR": "1.15"})


def _current(world, phases=("initial", "late")):
    slots = {}
    for batch in world.batches:
        if batch.phase in phases:
            slots[slot_key(batch)] = batch
    return list(slots.values())


def _october(pack_def):
    world = build_october_world()
    batches = _current(world)
    marts = build_marts(batches, pack_def)
    figures = OfflineFinanceEngine().answer(pack_def, marts)
    return world, batches, figures


def _edited_batches(batches):
    """The same batch set with the FX table edited in place:
    same batch id, same version — different rates. The stamp
    discipline exists for exactly this."""
    return [
        batch.model_copy(update={"rate_table": EDITED_TABLE})
        if batch.kind == "fx" else batch
        for batch in batches
    ]


# -- the stamp -------------------------------------------------------


def test_marts_stamp_the_table_itself(world, pack_def):
    batches = _current(world)
    marts = build_marts(batches, pack_def)
    assert marts.source_versions.fx_version == 2
    assert marts.source_versions.fx_table is not None
    assert marts.source_versions.fx_table.version == 2
    assert marts.source_versions.fx_table.rates == {"EUR": "1.10"}
    figures = OfflineFinanceEngine().answer(pack_def, marts)
    # Every figure's provenance names the rate that produced it.
    assert all(
        f.source_versions.fx_table == marts.source_versions.fx_table
        for f in figures
    )


def test_changed_currencies_compares_rates_not_strings():
    before = RateTable(version=1, rates={"EUR": "1.10", "GBP": "1.27"})
    after = RateTable(version=2, rates={"EUR": "1.12", "GBP": "1.27"})
    # The unmoved currency is silent; the moved one is named.
    assert changed_currencies(before, after) == {"EUR": ("1.10", "1.12")}
    # "1.1" and "1.10" are the same rate written two ways.
    same = RateTable(version=2, rates={"EUR": "1.1", "GBP": "1.27"})
    assert changed_currencies(before, same) == {}
    # An absent stamp yields no changes — absence is not "unchanged".
    assert changed_currencies(None, after) == {}
    assert changed_currencies(before, None) == {}


# -- the verifier's basis --------------------------------------------


def test_verifier_recomputes_at_the_stamped_table():
    """The batch set's table is edited after the run: the
    figures (struck at 1.12, stamped 1.12) still reproduce —
    the verifier works at the stamp — and the edit is named."""
    pack_def = load_definition_pack_version("harborlight-close", "1.1.0")
    _, batches, figures = _october(pack_def)
    report = verifier_module.verify(pack_def, _edited_batches(batches),
                                    figures)
    codes = [v.code for v in report.variances]
    assert codes == ["RATE_TABLE_MISMATCH"]
    assert "1.12" in report.variances[0].detail
    assert "1.15" in report.variances[0].detail
    assert all(check.ok for check in report.checks)
    assert not report.passed


def test_verifier_names_a_figure_converted_off_stamp():
    """Figures computed at 1.15 but stamped 1.12: internally
    consistent arithmetic on the wrong basis. The break is
    named per figure as a rate break, not a figure mismatch."""
    pack_def = load_definition_pack_version("harborlight-close", "1.1.0")
    world = build_october_world()
    batches = _edited_batches(_current(world))
    marts = build_marts(batches, pack_def)
    figures = OfflineFinanceEngine().answer(pack_def, marts)
    lying = [
        figure.model_copy(update={
            "source_versions": figure.source_versions.model_copy(
                update={"fx_table": HONEST_OCTOBER_TABLE}),
        })
        for figure in figures
    ]
    report = verifier_module.verify(pack_def, batches, lying)
    codes = [v.code for v in report.variances]
    assert "FIGURE_MISMATCH" not in codes
    per_figure = {
        v.metric_id for v in report.variances
        if v.code == "RATE_TABLE_MISMATCH" and v.metric_id is not None
    }
    assert "consolidated_revenue" in per_figure
    assert "consolidated_cash" in per_figure
    # Entity figures convert nothing: they still verify, unnamed.
    assert all(
        check.ok for check in report.checks if check.entity_id is not None
    )
    assert not report.passed


def test_verifier_names_figures_that_disagree_on_the_stamp():
    pack_def = load_definition_pack_version("harborlight-close", "1.1.0")
    _, batches, figures = _october(pack_def)
    figures[0] = figures[0].model_copy(update={
        "source_versions": figures[0].source_versions.model_copy(
            update={"fx_table": RateTable(
                version=9, reporting_currency="USD",
                rates={"EUR": "9.99"})}),
    })
    report = verifier_module.verify(pack_def, batches, figures)
    named = [v for v in report.variances
             if v.code == "RATE_TABLE_MISMATCH"
             and "do not stamp one rate table" in v.detail]
    assert len(named) == 1
    assert not report.passed


def test_pre_stamp_figures_verify_as_before():
    """Figures carrying no table (stamped before tables rode
    the stamp) fall back to the batch set's table, unchanged."""
    pack_def = load_definition_pack_version("harborlight-close", "1.1.0")
    _, batches, figures = _october(pack_def)
    stripped = [
        figure.model_copy(update={
            "source_versions": figure.source_versions.model_copy(
                update={"fx_table": None}),
        })
        for figure in figures
    ]
    report = verifier_module.verify(pack_def, batches, stripped)
    assert report.variances == []
    assert report.passed


# -- the flags, end to end --------------------------------------------


def _october_service(service, world):
    """September signed through the conftest service (pack
    v1.0.0); October's service over the same store (v1.1.0)."""
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    signed_september = service.sign_off(
        service.build_pack(run.run_id).pack_id, "sign", "Mara Ellison")
    pack_v110 = load_definition_pack_version("harborlight-close", "1.1.0")
    store = service.store
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack_v110,
        checkpointer=MemorySaver(),
    )
    october = CloseService(
        pipeline=pipeline, store=store, connector=service.connector,
        objects=service.objects, pack_def=pack_v110,
    )
    october_world = build_october_world()
    october_run = october.create_run(PERIOD_OCTOBER)
    october.ingest(october_run.run_id,
                   [b.batch_id for b in october_world.batches])
    pack = october.build_pack(october_run.run_id)
    return october, signed_september, pack


def test_rate_flags_mark_exactly_the_figures_eur_flows_through(
        service, world):
    _, _, pack = _october_service(service, world)
    flagged = {
        c.metric_id for c in pack.comparatives if c.rate_changed
    }
    assert flagged == RATE_CHANGED_METRICS
    # No entity comparative is ever flagged — entity figures
    # stand in their own currency.
    assert not any(
        c.rate_changed for c in pack.comparatives if c.entity_id)
    # The flux schedule agrees, and its face states both tables.
    assert pack.flux is not None
    assert pack.flux.prior_fx_version == 2
    assert pack.flux.current_fx_version == 3
    assert {
        e.metric_id for e in pack.flux.entries if e.rate_changed
    } == RATE_CHANGED_METRICS
    for entry in pack.flux.entries:
        if entry.rate_changed:
            assert "rate changed" in entry.note
            assert "1.10" in entry.note and "1.12" in entry.note


def test_evidence_bundle_carries_rate_provenance(service, world):
    october, _, pack = _october_service(service, world)
    signed = october.sign_off(pack.pack_id, "sign", "Mara Ellison")
    october.generate_evidence(signed.pack_id)
    data, _ = october.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    assert document["fx"]["current"]["version"] == 3
    assert document["fx"]["current"]["rates"] == {"EUR": "1.12"}
    assert document["fx"]["prior"]["version"] == 2
    assert document["fx"]["prior"]["rates"] == {"EUR": "1.10"}
    assert document["fx"]["rate_changes"] == [
        {"currency": "EUR", "prior_rate": "1.10",
         "current_rate": "1.12"},
    ]
    text, _ = october.evidence_download(signed.pack_id, "txt")
    rendered = text.decode("utf-8")
    assert "RATE PROVENANCE" in rendered
    assert "RATE CHANGED: EUR: 1.10 (prior) → 1.12 (current)" in rendered


def test_evidence_for_a_pre_stamp_pack_reads_as_absent(service, world):
    """A signed pack whose stamps predate rate tables: the
    bundle says so, and reconstructs nothing."""
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    signed = service.sign_off(
        service.build_pack(run.run_id).pack_id, "sign", "Mara Ellison")
    stored = service.store.get_pack(signed.pack_id)
    figures = [
        figure.model_copy(update={
            "source_versions": figure.source_versions.model_copy(
                update={"fx_table": None}),
        })
        for figure in stored.figures
    ]
    service.store.save_pack(stored.model_copy(update={
        "figures": figures,
        "source_versions": stored.source_versions.model_copy(
            update={"fx_table": None}),
    }))
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    assert document["fx"]["current"] is None
    assert document["fx"]["rate_changes"] == []
    assert document["fx_version"] == 2  # the version stays on record
    text, _ = service.evidence_download(signed.pack_id, "txt")
    assert "predates rate stamping" in text.decode("utf-8")
