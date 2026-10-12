"""Figure drill-down: every figure opens into the exact
lines it stands on.

Pins, by layer:

- the base drill — a figure's lines are the planted lines, in
  the batches the pack stamps (the corrected extracts, at
  their versions), and they compose to the figure exactly;
- the duplicate rule — on the blocked first pack, the
  duplicated journal counts once, on the drill's own scan;
- pack states — blocked and stale packs drill on their own
  stamps, with the state named on the drill;
- coverage by definition kind — an elimination drills to
  both legs, a converted figure converts once per entity at
  the stamped rate, a derived figure composes from its
  operands' drills and stands on no lines of its own, a
  ``vs_plan`` figure shows the plan as authored data, a CRM
  figure drills to its records;
- the identity — a source line tampered under the pack's
  stamps raises DRILL_MISMATCH naming the figure; a rate
  table edited in the batches reprices nothing (the stamp
  is the basis);
- the refusals — a figure the pack does not carry, a stamped
  batch gone from the store, a measure with no line
  semantics;
- the bundle — the drills section cites every figure's
  re-performed drill by digest, and digests match fresh
  drills against the same pack;
- the surfaces — the API serves the drill and maps the
  refusals honestly.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent.api import create_app
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import PERIOD, build_world
from aidnn_close_agent.definitions import (
    DefinitionPack,
    MetricDefinition,
    load_definition_pack,
)
from aidnn_close_agent.drill import build_drill, drill_digest
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import (
    DrillError,
    DrillMismatch,
    DrillNotFound,
)
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison"


def _close_september(service, world):
    """Drive September through both attempts; returns
    (first pack — stale by the end, signed pack)."""
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    second = service.build_pack(run.run_id)
    signed = service.sign_off(second.pack_id, "sign", CONTROLLER,
                              "figures verified; variances cleared")
    return service.get_pack(first.pack_id), signed


@pytest.fixture()
def closed(service, world):
    return _close_september(service, world)


def _all_lines(node):
    out = list(node.lines)
    for child in node.children:
        out.extend(_all_lines(child))
    return out


# -- the base drill ------------------------------------------------------


def test_base_figure_drills_to_its_planted_lines(service, closed):
    _, signed = closed
    drill = service.figure_drill(signed.pack_id, "revenue_external", "HLE")
    assert drill.pack_status == "SIGNED_OFF"
    assert drill.composed_total == drill.figure_value == "615000.00"
    assert drill.line_count == 2
    lines = drill.root.lines
    assert [(l.batch_id, l.batch_version, l.journal_id, l.account,
             l.amount) for l in lines] == [
        ("B-HLE-GL-v2", 2, "J-E2", "4000", "520000.00"),
        ("B-HLE-GL-v2", 2, "J-E3", "4100", "95000.00"),
    ]
    # The lines are the corrected extract's lines: the drill
    # reads the pack's stamps, not the first attempt's.
    assert all(l.currency == "EUR" for l in lines)


def test_every_figure_on_the_signed_pack_drills_and_foots(
        service, closed, world):
    _, signed = closed
    assert len(signed.figures) == 25
    for figure in signed.figures:
        drill = service.figure_drill(
            signed.pack_id, figure.metric_id, figure.entity_id)
        assert drill.composed_total == figure.value, figure.metric_id
        key = figure.metric_id + (
            f"@{figure.entity_id}" if figure.entity_id else "")
        assert drill.figure_value == world.gold_figures[key]


def test_drill_is_deterministic_and_digestible(service, closed):
    _, signed = closed
    one = service.figure_drill(signed.pack_id, "consolidated_revenue")
    two = service.figure_drill(signed.pack_id, "consolidated_revenue")
    assert one.model_dump_json() == two.model_dump_json()
    assert drill_digest(one) == drill_digest(two)


# -- states: blocked and stale packs drill on their own stamps ------------


def test_blocked_pack_drills_and_the_duplicate_counts_once(
        service, world):
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    assert first.status == "BLOCKED"
    drill = service.figure_drill(first.pack_id, "opex", "HLD")
    assert drill.pack_status == "BLOCKED"
    # J-D9 (payroll 12,750 on 6100) stands in the extract
    # twice; the drill counts its first copy only, like the
    # close did — so the composition foots to the figure the
    # blocked pack records.
    journals = [l.journal_id for l in drill.root.lines]
    assert journals.count("J-D9") == 1
    assert drill.composed_total == drill.figure_value == "133250.00"


def test_stale_pack_drills_on_its_own_stamps(service, closed):
    first, _ = closed
    assert first.status == "STALE"
    drill = service.figure_drill(first.pack_id, "opex", "HLE")
    assert drill.pack_status == "STALE"
    # The first attempt's figure: the mis-posted €95,000
    # services billing sat on payroll (6100) in v1, and the
    # drill re-performs exactly that, from B-HLE-GL-v1 at the
    # v1 rate table the pack stamps.
    assert drill.composed_total == drill.figure_value == "195000.00"
    assert {l.batch_id for l in drill.root.lines} == {"B-HLE-GL-v1"}
    assert drill.fx_version == 1


# -- coverage by definition kind ------------------------------------------


def test_elimination_drills_to_both_legs(service, closed):
    _, signed = closed
    drill = service.figure_drill(signed.pack_id, "eliminations_total")
    assert drill.composed_total == "55000.00"
    assert drill.root.kind == "elimination"
    revenue_leg, cost_leg = drill.root.children
    assert revenue_leg.value == cost_leg.value == "55000.00"
    rev_lines = _all_lines(revenue_leg)
    cost_lines = _all_lines(cost_leg)
    assert [(l.journal_id, l.account, l.amount, l.ic_counterparty)
            for l in rev_lines] == [
        ("J-D8", "4200", "55000.00", "HLE")]
    assert [(l.journal_id, l.account, l.amount, l.ic_counterparty)
            for l in cost_lines] == [
        ("J-E7", "5000", "50000.00", "HLD")]
    # The EUR leg converts once, at the stamped rate.
    cost_entity = cost_leg.children[0]
    assert cost_entity.pre_conversion_value == "50000.00"
    assert cost_entity.pre_conversion_currency == "EUR"
    assert cost_entity.rate == "1.10"
    assert cost_entity.value == "55000.00"


def test_converted_figure_converts_once_per_entity_at_the_stamp(
        service, closed):
    _, signed = closed
    drill = service.figure_drill(signed.pack_id, "consolidated_revenue")
    assert drill.root.kind == "sum_converted"
    assert drill.fx_version == 2
    by_entity = {c.entity_id: c for c in drill.root.children}
    hle = by_entity["HLE"]
    assert hle.pre_conversion_value == "615000.00"
    assert hle.pre_conversion_currency == "EUR"
    assert hle.rate == "1.10"
    assert hle.value == "676500.00"
    # Lines are stated in entity currency and carry no
    # converted amounts of their own — the close converts the
    # subtotal, never the line.
    assert all(l.currency == "EUR" for l in hle.lines)
    assert drill.composed_total == "1796500.00"


def test_derived_figure_composes_and_stands_on_no_lines(service, closed):
    _, signed = closed
    drill = service.figure_drill(
        signed.pack_id, "consolidated_operating_income")
    assert drill.root.kind == "subtract"
    assert drill.root.lines == [] and drill.root.records == []
    assert [c.metric_id for c in drill.root.children] == [
        "consolidated_revenue", "consolidated_cogs",
        "consolidated_opex"]
    assert [c.sign for c in drill.root.children] == [1, -1, -1]
    assert drill.composed_total == "783250.00"
    # The operands' own drills are the composition — the
    # leaves of the tree are source lines, all the way down.
    assert drill.line_count > 0
    assert all(l.amount for l in _all_lines(drill.root))


def test_vs_plan_shows_the_plan_as_authored_data(service, closed):
    _, signed = closed
    drill = service.figure_drill(signed.pack_id, "revenue_vs_plan")
    assert drill.root.kind == "vs_plan"
    operand, plan = drill.root.children
    assert operand.metric_id == "consolidated_revenue"
    assert plan.kind == "plan"
    assert plan.value == "-1750000.00"
    assert plan.lines == [] and plan.records == []
    assert "authored data" in plan.note
    assert drill.composed_total == "46500.00"


def test_crm_figure_drills_to_its_records(service, closed):
    _, signed = closed
    drill = service.figure_drill(signed.pack_id, "pipeline_open")
    assert drill.root.lines == []
    assert [(r.batch_id, r.amount) for r in drill.root.records] == [
        ("B-CRM-v1", "900000.00"),
        ("B-CRM-v1", "850000.00"),
        ("B-CRM-v1", "550000.00"),
    ]
    assert drill.composed_total == "2300000.00"


def test_excluded_intercompany_lines_stay_out_of_the_drill(
        service, closed):
    _, signed = closed
    # cogs_external excludes IC-flagged lines: HLE's €50,000
    # intercompany purchase sits on account 5000 but is not
    # external COGS, and the drill must not show it there.
    drill = service.figure_drill(signed.pack_id, "cogs_external", "HLE")
    assert [(l.journal_id, l.amount) for l in drill.root.lines] == [
        ("J-E4", "260000.00")]
    assert drill.composed_total == "260000.00"


# -- the identity ----------------------------------------------------------


def test_tampered_source_line_raises_drill_mismatch(service, closed):
    _, signed = closed
    batch = service.store.get_batch("B-HLE-GL-v2")
    journals = []
    for journal in batch.journals:
        if journal.journal_id == "J-E2":
            journal = journal.model_copy(update={"lines": [
                line.model_copy(update={"credit": "521000.00"})
                if line.account == "4000" else line
                for line in journal.lines
            ]})
        journals.append(journal)
    service.store.save_batch(batch.model_copy(
        update={"journals": journals}))
    with pytest.raises(DrillMismatch) as raised:
        service.figure_drill(signed.pack_id, "revenue_external", "HLE")
    message = str(raised.value)
    assert "DRILL_MISMATCH" in message
    assert "revenue_external" in message and "HLE" in message
    assert raised.value.composed_total == "616000.00"
    assert raised.value.figure_value == "615000.00"
    # And a figure the tamper does not touch still foots:
    # the mismatch is per figure, not a fog over the pack.
    drill = service.figure_drill(signed.pack_id, "revenue_external", "HLD")
    assert drill.composed_total == "1000000.00"


def test_edited_batch_rate_table_does_not_reprice_the_drill(
        service, closed):
    _, signed = closed
    batch = service.store.get_batch("B-FX-v2")
    edited = batch.model_copy(update={
        "rate_table": batch.rate_table.model_copy(
            update={"rates": {"EUR": "1.15"}}),
    })
    service.store.save_batch(edited)
    drill = service.figure_drill(signed.pack_id, "consolidated_revenue")
    # The drill converts at the pack's stamp (1.10), like the
    # verifier: the edited batch table reprices nothing.
    assert drill.composed_total == "1796500.00"
    assert drill.fx_basis.startswith("the rate table stamped on the pack")


# -- the refusals ------------------------------------------------------------


def test_figure_the_pack_does_not_carry_is_a_named_miss(service, closed):
    _, signed = closed
    with pytest.raises(DrillNotFound):
        service.figure_drill(signed.pack_id, "revenue_external", "NOPE")
    with pytest.raises(DrillNotFound):
        service.figure_drill(signed.pack_id, "no_such_metric")


def test_missing_stamped_batch_refuses_the_drill(service, closed):
    _, signed = closed
    store = service.store
    batch = store._batches.pop("B-HLE-GL-v2")
    try:
        with pytest.raises(DrillError) as raised:
            service.figure_drill(signed.pack_id, "revenue_external",
                                 "HLE")
        assert "B-HLE-GL-v2" in str(raised.value)
        assert "missing from the store" in str(raised.value)
    finally:
        store._batches["B-HLE-GL-v2"] = batch


def test_measure_without_line_semantics_is_refused_by_name(
        service, pack_def):
    """A base GL metric measured ``sum_amount`` — the measure
    the close defines over CRM records — has no honest drill:
    neither the engine nor the verifier sums GL lines that
    way, and the drill will not invent a meaning for it."""
    bad = MetricDefinition(
        metric_id="gl_sum", label="GL sum", scope="entity",
        source="gl", measure="sum_amount", accounts=["4000"])
    pack = pack_def.model_copy(update={
        "metrics": pack_def.metrics + [bad]})
    store = InMemoryCloseStore()
    pipeline = PackPipeline(
        engine=OfflineFinanceEngine(), store=store, pack=pack,
        checkpointer=MemorySaver(),
    )
    svc = CloseService(
        pipeline=pipeline, store=store, connector=DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack)
    world = build_world()
    run = svc.create_run(PERIOD)
    svc.ingest(run.run_id, [b.batch_id for b in world.batches])
    built = svc.build_pack(run.run_id)
    assert any(f.metric_id == "gl_sum" and f.entity_id == "HLE"
               for f in built.figures)
    with pytest.raises(DrillError) as raised:
        build_drill(store, built, pack, "gl_sum", "HLE")
    assert "sum_amount" in str(raised.value)


# -- the bundle ----------------------------------------------------------------


def test_bundle_cites_every_drill_by_digest(service, closed):
    _, signed = closed
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    section = document["drills"]
    assert len(section) == 25
    assert all(not entry["mismatch"] for entry in section)
    by_key = {(e["metric_id"], e["entity_id"]): e for e in section}
    for figure in signed.figures:
        entry = by_key[(figure.metric_id, figure.entity_id)]
        drill = service.figure_drill(
            signed.pack_id, figure.metric_id, figure.entity_id)
        assert entry["digest"] == drill_digest(drill)
        assert entry["composed_total"] == figure.value
        assert entry["line_count"] == drill.line_count


def test_bundle_records_a_mismatch_when_sources_move_after_signing(
        service, closed):
    _, signed = closed
    record = service.generate_evidence(signed.pack_id)
    batch = service.store.get_batch("B-HLG-GL-v1")
    journals = [
        journal.model_copy(update={"lines": [
            line.model_copy(update={"debit": "46000.00"})
            if line.account == "6100" else line
            for line in journal.lines
        ]}) if journal.journal_id == "J-H3" else journal
        for journal in batch.journals
    ]
    service.store.save_batch(batch.model_copy(
        update={"journals": journals}))
    moved = service.generate_evidence(signed.pack_id)
    assert moved.sha256 != record.sha256
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    by_key = {(e["metric_id"], e["entity_id"]): e
              for e in document["drills"]}
    opex = by_key[("opex", "HLG")]
    assert opex["mismatch"] is True
    assert opex["digest"] is None
    assert opex["figure_value"] == "54000.00"
    assert opex["composed_total"] == "55000.00"
    # The rest of the pack still cites footing drills.
    assert by_key[("revenue_external", "HLE")]["mismatch"] is False


# -- the HTTP surface ----------------------------------------------------------


def test_api_serves_the_drill_and_maps_refusals(service, closed):
    _, signed = closed
    client = TestClient(create_app(service))
    ok = client.get(
        f"/packs/{signed.pack_id}/figures/revenue_external/drill",
        params={"entity": "HLE"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["composed_total"] == "615000.00"
    assert body["pack_status"] == "SIGNED_OFF"
    assert len(body["root"]["lines"]) == 2

    missing = client.get(
        f"/packs/{signed.pack_id}/figures/revenue_external/drill",
        params={"entity": "NOPE"})
    assert missing.status_code == 404

    no_pack = client.get("/packs/PACK-NOPE/figures/cash/drill")
    assert no_pack.status_code == 404
