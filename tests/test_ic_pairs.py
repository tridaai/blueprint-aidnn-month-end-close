"""Intercompany agreement: the pairs, paired by counterparty.

The aggregate check the verifier always had can say the legs do
not net; these tests pin the pair-level check that says *which*
pair, by how much, and in which direction — a disagreement
named with both figures, a one-sided booking named as its own
class, and the masking case the aggregate cannot see at all
(a leg flagged to the wrong counterparty, invisible in the
pooled totals). End to end: the staged October disagreement
blocks its pack, flags exactly the consolidated figures
standing on the pair, and leaves every entity figure as booked.
"""

from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import verifier as verifier_module
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    IC_VARIANT_BATCH_ID,
    IC_VARIANT_FLAGGED,
    IC_VARIANT_PAIR,
    PERIOD,
    PERIOD_OCTOBER,
    build_october_world,
    october_ic_variant_batch,
)
from aidnn_close_agent.definitions import load_definition_pack_version
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.errors import GateError
from aidnn_close_agent.fx import RateTable
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.marts import build_marts, slot_key
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import Journal, JournalLine, SourceBatch
from aidnn_close_agent.service import CloseService
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison"


def _current(world, phases):
    slots = {}
    for batch in world.batches:
        if batch.phase in phases:
            slots[slot_key(batch)] = batch
    return list(slots.values())


def _engine_figures(pack_def, batches):
    marts = build_marts(batches, pack_def)
    return OfflineFinanceEngine().answer(pack_def, marts)


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


# -- the verifier's pair check, on the September world --------------------


def test_phase_a_pair_is_one_sided_by_name(world, pack_def):
    batches = _current(world, {"initial"})
    report = verifier_module.verify(
        pack_def, batches, _engine_figures(pack_def, batches))
    assert len(report.ic_pairs) == 1
    pair = report.ic_pairs[0]
    assert pair.elimination_id == "ic_sales"
    assert (pair.seller_id, pair.buyer_id) == ("HLD", "HLE")
    assert pair.verdict == "ONE_SIDED"
    assert pair.missing_side == "cost"
    assert pair.seller_amount == "55000.00"
    assert pair.seller_currency == "USD"
    assert pair.buyer_amount is None
    assert pair.difference is None
    one_sided = [v for v in report.variances if v.code == "IC_ONE_SIDED"]
    assert len(one_sided) == 1
    assert "55000.00" in one_sided[0].detail
    assert "booking conversation" in one_sided[0].detail
    # The aggregate check still fires at its own grain, and the
    # one-sided pair is not lumped in with amount disagreement.
    assert any(v.code == "UNMATCHED_IC_LEG" for v in report.variances)
    assert not any(v.code == "IC_DISAGREEMENT" for v in report.variances)
    assert not report.passed


def test_corrected_pair_agrees_and_is_silent(world, pack_def):
    batches = _current(world, {"initial", "late"})
    report = verifier_module.verify(
        pack_def, batches, _engine_figures(pack_def, batches))
    assert len(report.ic_pairs) == 1
    pair = report.ic_pairs[0]
    assert pair.verdict == "AGREED"
    assert pair.seller_amount == "55000.00"  # USD, as HLD stated it
    assert pair.buyer_amount == "50000.00"   # EUR, as HLE stated it
    assert pair.buyer_amount_basis == "55000.00"  # at the close's 1.10
    assert pair.fx_rate == "1.1"
    assert pair.difference == "0.00"
    assert not any(v.code.startswith("IC_") for v in report.variances)
    assert report.passed


def test_wrong_counterparty_is_two_one_sided_pairs(pack_def):
    """The masking case: HLE books its cost leg against HLG
    instead of HLD. The pooled totals still pair — the
    aggregate check is silent — but no actual pair mirrors, and
    the pair check names both halves of the failure."""
    def gl(entity, journal_id, lines):
        return SourceBatch(
            batch_id=f"X-{entity}-GL", kind="gl", entity_id=entity,
            journals=[Journal(journal_id=journal_id, entity_id=entity,
                              date="2026-09-30", lines=lines)],
        )

    def line(account, debit="0.00", credit="0.00", ic=None):
        return JournalLine(account=account, debit=debit, credit=credit,
                           ic_counterparty=ic)

    batches = [
        gl("HLD", "J-X1", [line("4200", credit="1000.00", ic="HLE")]),
        gl("HLE", "J-X2", [line("5000", debit="1000.00", ic="HLG")]),
        SourceBatch(batch_id="X-FX", kind="fx",
                    rate_table=RateTable(version=1,
                                         reporting_currency="USD",
                                         rates={"EUR": "1.00"})),
    ]
    report = verifier_module.verify(
        pack_def, batches, _engine_figures(pack_def, batches))
    # The aggregate is fooled: converted totals pair exactly.
    assert not any(v.code == "UNMATCHED_IC_LEG" for v in report.variances)
    pairs = {(p.seller_id, p.buyer_id): p for p in report.ic_pairs}
    assert set(pairs) == {("HLD", "HLE"), ("HLG", "HLE")}
    assert pairs[("HLD", "HLE")].verdict == "ONE_SIDED"
    assert pairs[("HLD", "HLE")].missing_side == "cost"
    assert pairs[("HLG", "HLE")].verdict == "ONE_SIDED"
    assert pairs[("HLG", "HLE")].missing_side == "revenue"
    assert sum(1 for v in report.variances if v.code == "IC_ONE_SIDED") == 2
    assert not report.passed


def test_flagged_metrics_are_the_derived_closure(pack_def):
    assert verifier_module.ic_flagged_metrics(pack_def, {"ic_sales"}) == {
        "eliminations_total", "consolidated_ic_revenue",
        "consolidated_gross_revenue",
    }
    assert verifier_module.ic_flagged_metrics(pack_def, set()) == set()


# -- the staged October disagreement, end to end --------------------------


class _VariantConnector:
    """The dataset connector with October's HLE extract swapped
    for the staged variant — the eval-staging idiom: a variant
    of the world behind the same port."""

    name = "dataset-ic-variant"

    def __init__(self, base: DatasetConnector) -> None:
        self._base = base

    def available(self):
        return self._base.available()

    def fetch(self, batch_id: str):
        if batch_id == IC_VARIANT_BATCH_ID:
            return october_ic_variant_batch()
        return self._base.fetch(batch_id)


@pytest.fixture()
def variant_october(pack_v110):
    store = InMemoryCloseStore()
    service = _service(store, pack_v110,
                       connector=_VariantConnector(DatasetConnector()))
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    return service, service.build_pack(run.run_id), world


def test_variant_blocks_with_both_figures_named(variant_october):
    _, pack, _ = variant_october
    assert pack.status == "BLOCKED"
    disagreements = [v for v in pack.variances
                     if v.code == "IC_DISAGREEMENT"]
    assert len(disagreements) == 1
    detail = disagreements[0].detail
    for figure in ("61600.00", "54500.00", "61040.00", "560.00"):
        assert figure in detail
    assert "booking conversation" in detail
    # The aggregate check names the same break at its own grain.
    assert any(v.code == "UNMATCHED_IC_LEG" for v in pack.variances)


def test_variant_pair_record_is_the_stated_gold(variant_october):
    _, pack, _ = variant_october
    assert len(pack.ic_pairs) == 1
    pair = pack.ic_pairs[0]
    for field_name, expected in IC_VARIANT_PAIR.items():
        assert getattr(pair, field_name) == expected, field_name
    assert pair.missing_side is None
    # The elimination still eliminates the matched amount — the
    # lesser side — computed, verified, and flagged as disputed.
    figures = {(f.metric_id, f.entity_id): f for f in pack.figures}
    assert figures[("eliminations_total", None)].value == "61040.00"


def test_variant_flags_exactly_the_consolidated_figures_on_the_pair(
        variant_october):
    _, pack, world = variant_october
    flagged = {f.metric_id for f in pack.figures if f.ic_disagreement}
    assert flagged == IC_VARIANT_FLAGGED
    assert all(f.entity_id is None for f in pack.figures
               if f.ic_disagreement)
    # Entity packs stand as booked: every entity figure equals
    # its October gold, undisputed flag and all.
    for key, expected in world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        if not entity_id:
            continue
        figure = next(f for f in pack.figures
                      if f.metric_id == metric_id
                      and f.entity_id == entity_id)
        assert figure.value == expected, key
        assert not figure.ic_disagreement


def test_variant_pack_refuses_sign_off(variant_october):
    service, pack, _ = variant_october
    with pytest.raises(GateError):
        service.sign_off(pack.pack_id, "sign", CONTROLLER)


# -- agreed pairs on signed packs, and in their bundles -------------------


def test_signed_september_carries_the_agreed_pair(service, world):
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    pack = service.build_pack(run.run_id)
    signed = service.sign_off(pack.pack_id, "sign", CONTROLLER)
    assert len(signed.ic_pairs) == 1
    assert signed.ic_pairs[0].verdict == "AGREED"
    assert not any(f.ic_disagreement for f in signed.figures)

    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    section = document["intercompany"]
    assert len(section) == 1
    assert section[0]["verdict"] == "AGREED"
    assert section[0]["seller_amount"] == "55000.00"
    assert section[0]["buyer_amount"] == "50000.00"
    text, _ = service.evidence_download(signed.pack_id, "txt")
    assert "INTERCOMPANY AGREEMENT" in text.decode("utf-8")
    assert record.figure_count == 25
