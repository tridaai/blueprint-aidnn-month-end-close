"""Flux: the movement explains itself — decomposition
identities, materiality, the definition-change convention, and
the verifier's independent check, end to end through the
service plus the negative cases built the way the repo's other
independence tests build them."""

from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import flux as flux_module
from aidnn_close_agent import verifier as verifier_module
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    DEFINITION_CHANGED_METRICS,
    PERIOD,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    build_october_world,
)
from aidnn_close_agent.definitions import (
    DefinitionPack,
    load_definition_pack_version,
)
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.fx import D, RateTable
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.narrative import build_narrative
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import (
    Figure,
    FigureComparative,
    Journal,
    JournalLine,
    SourceBatch,
)
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


@pytest.fixture()
def october(store, signed_september, pack_v110):
    """October built over the restated September, unsigned.
    Returns (service, pack, signed September pack)."""
    _, signed = signed_september
    service = _service(store, pack_v110)
    service.receive_restatement(RESTATEMENT_BATCH_ID)
    world = build_october_world()
    run = service.create_run(PERIOD_OCTOBER)
    service.ingest(run.run_id, [b.batch_id for b in world.batches])
    return service, service.build_pack(run.run_id), signed


def _lines(entry, mode):
    lines = entry.by_entity if mode == "entity" else entry.by_account
    return {line.key: line for line in lines or []}


# -- the schedule itself ---------------------------------------------------


def test_first_close_has_no_flux(signed_september):
    _, signed = signed_september
    assert signed.flux is None
    assert signed.comparatives == []


def test_flux_covers_every_comparative_and_foots(october):
    _, pack, signed = october
    flux = pack.flux
    assert flux is not None
    assert flux.prior_period == PERIOD
    assert flux.prior_pack_id == signed.pack_id
    assert flux.prior_definition_pack_version == "1.0.0"
    assert flux.current_definition_pack_version == "1.1.0"
    assert flux.threshold_abs == "50000.00"
    assert flux.threshold_pct == "10.00"
    assert len(flux.entries) == len(pack.comparatives) == 25
    comparative_by_key = {
        (c.metric_id, c.entity_id): c for c in pack.comparatives}
    for entry in flux.entries:
        key = (entry.metric_id, entry.entity_id)
        comparative = comparative_by_key[key]
        # The entry explains the comparative's own movement and
        # cites the comparative's own prior figure.
        assert entry.movement == comparative.change
        assert entry.prior_value == comparative.prior_value
        assert entry.definition_changed == comparative.definition_changed
        assert entry.restated == comparative.restated
        entity_total = sum((D(l.amount) for l in entry.by_entity), D(0))
        assert entity_total == D(entry.movement), key
        if entry.by_account is not None:
            account_total = sum(
                (D(l.amount) for l in entry.by_account), D(0))
            assert account_total == D(entry.movement), key


def test_consolidated_revenue_decomposition_is_gold(october):
    _, pack, _ = october
    entry = next(e for e in pack.flux.entries
                 if e.metric_id == "consolidated_revenue")
    assert entry.movement == "115140.00"
    by_entity = _lines(entry, "entity")
    # HLE's contribution is its EUR movement converted at each
    # period's own rate: 647,000 @1.12 − 615,000 @1.10.
    assert by_entity["HLG"].amount == "12000.00"
    assert by_entity["HLD"].amount == "55000.00"
    assert by_entity["HLE"].amount == "48140.00"
    by_account = _lines(entry, "account")
    assert by_account["4000"].amount == "83400.00"
    assert by_account["4100"].amount == "31740.00"
    # Material entries order their drivers largest first.
    amounts = [abs(D(l.amount)) for l in entry.by_entity]
    assert amounts == sorted(amounts, reverse=True)


def test_plan_line_and_group_lines(october):
    _, pack, _ = october
    vs_plan = next(e for e in pack.flux.entries
                   if e.metric_id == "revenue_vs_plan")
    assert vs_plan.movement == "15140.00"
    plan_lines = [l for l in vs_plan.by_entity if l.kind == "plan"]
    assert len(plan_lines) == 1
    # The plan moved 1,750,000 → 1,850,000; the baseline's share
    # of the vs-plan movement is the negative of that move.
    assert plan_lines[0].amount == "-100000.00"

    pipeline = next(e for e in pack.flux.entries
                    if e.metric_id == "pipeline_open")
    assert pipeline.movement == "-250000.00"
    assert [l.kind for l in pipeline.by_entity] == ["group"]
    assert pipeline.by_account is None
    assert "no GL accounts" in pipeline.note

    eliminations = next(e for e in pack.flux.entries
                        if e.metric_id == "eliminations_total")
    assert [l.kind for l in eliminations.by_entity] == ["group"]
    assert eliminations.by_account is None
    assert "pairing" in eliminations.note


# -- materiality --------------------------------------------------------------


def test_materiality_flags_the_big_movers_not_the_quiet_ones(october):
    _, pack, _ = october
    by_key = {(e.metric_id, e.entity_id): e for e in pack.flux.entries}
    # The planted big mover, and the other large movements.
    assert by_key[("pipeline_open", None)].material
    assert by_key[("consolidated_revenue", None)].material
    assert by_key[("consolidated_operating_income", None)].material
    # Quiet figures stay unflagged — including small movements
    # and an exactly-zero one.
    assert not by_key[("cash", "HLD")].material       # −450.00, −0.33%
    assert not by_key[("revenue_ic", "HLG")].material  # 0.00
    assert not by_key[("consolidated_cash", None)].material  # 2.11%
    assert not by_key[("opex", "HLD")].material        # −3.41%


# -- the definition-change convention -----------------------------------------


def test_definition_changed_figures_carry_the_flag_and_the_note(october):
    _, pack, _ = october
    flagged = {e.metric_id for e in pack.flux.entries
               if e.definition_changed}
    assert flagged == DEFINITION_CHANGED_METRICS
    for entry in pack.flux.entries:
        assert "v1.0.0" in entry.basis and "v1.1.0" in entry.basis
        if entry.definition_changed:
            assert "definition change" in entry.note
            assert "not separated" in entry.note


def test_the_widened_account_shows_up_as_its_own_line(october):
    _, pack, _ = october
    opex_hlg = next(e for e in pack.flux.entries
                    if e.metric_id == "opex" and e.entity_id == "HLG")
    by_account = _lines(opex_hlg, "account")
    # Account 6400 (insurance) joined opex under v1.1.0; under
    # v1.0.0 it contributed nothing, so its whole October amount
    # is its movement — the definition change, visible as a line.
    assert by_account["6400"].amount == "6000.00"
    assert by_account["6100"].amount == "2000.00"
    assert opex_hlg.movement == "8000.00"


# -- the verifier's check -------------------------------------------------------


def _flux_inputs(store, signed, pack_v110, pack_def, october_pack):
    return dict(
        current_def=pack_v110,
        prior_def=pack_def,
        current_batches=build_october_world().batches,
        prior_batches=[store.get_batch(b)
                       for b in signed.source_versions.batches],
        figures=october_pack.figures,
        comparatives=october_pack.comparatives,
    )


def test_verify_flux_accepts_the_produced_schedule(
        store, signed_september, october, pack_def, pack_v110):
    _, september_signed = signed_september
    _, pack, _ = october
    inputs = _flux_inputs(store, september_signed, pack_v110, pack_def,
                          pack)
    assert verifier_module.verify_flux(pack.flux, **inputs) == []


def test_verify_flux_catches_a_corrupted_contribution(
        store, signed_september, october, pack_def, pack_v110):
    _, september_signed = signed_september
    _, pack, _ = october
    inputs = _flux_inputs(store, september_signed, pack_v110, pack_def,
                          pack)
    forged = pack.flux.model_copy(deep=True)
    entry = next(e for e in forged.entries
                 if e.metric_id == "consolidated_revenue")
    driver = next(l for l in entry.by_entity if l.key == "HLD")
    driver.amount = "999999.00"
    variances = verifier_module.verify_flux(forged, **inputs)
    assert variances and all(v.code == "FLUX_MISMATCH" for v in variances)
    assert any(v.metric_id == "consolidated_revenue" for v in variances)


def test_verify_flux_catches_a_wrong_movement_and_a_dropped_entry(
        store, signed_september, october, pack_def, pack_v110):
    _, september_signed = signed_september
    _, pack, _ = october
    inputs = _flux_inputs(store, september_signed, pack_v110, pack_def,
                          pack)

    forged = pack.flux.model_copy(deep=True)
    entry = next(e for e in forged.entries
                 if e.metric_id == "consolidated_cash")
    entry.movement = "1.00"
    codes = [v.code for v in verifier_module.verify_flux(forged, **inputs)]
    assert "FLUX_MISMATCH" in codes

    dropped = pack.flux.model_copy(deep=True)
    dropped.entries = [e for e in dropped.entries
                       if e.metric_id != "pipeline_open"]
    variances = verifier_module.verify_flux(dropped, **inputs)
    assert any(v.code == "FLUX_MISMATCH" and v.metric_id == "pipeline_open"
               for v in variances)

    tampered = pack.flux.model_copy(deep=True)
    tampered.threshold_abs = "1.00"
    variances = verifier_module.verify_flux(tampered, **inputs)
    assert any(v.code == "FLUX_MISMATCH" for v in variances)


# -- the rounding line, on a synthetic rate -------------------------------------


def _mini_pack() -> DefinitionPack:
    return DefinitionPack.model_validate({
        "pack_id": "mini-close", "version": "1.0.0",
        "reporting_currency": "USD",
        "entities": [{"entity_id": "E1", "name": "Euro Sub",
                      "currency": "EUR", "source_system": "Test"}],
        "metrics": [
            {"metric_id": "revenue_external", "label": "Revenue",
             "scope": "entity", "source": "gl",
             "measure": "credit_minus_debit",
             "accounts": ["4000", "4100"]},
            {"metric_id": "consolidated_revenue", "label": "Consol rev",
             "scope": "consolidated",
             "derived": {"op": "sum_converted", "of": "revenue_external"}},
        ],
        "plan": {},
    })


def _mini_batches(tag: str, sales: str, services: str) -> list[SourceBatch]:
    journal = Journal(
        journal_id=f"J-{tag}", entity_id="E1", date="2026-01-31",
        lines=[
            JournalLine(account="4000", credit=sales),
            JournalLine(account="4100", credit=services),
        ])
    return [
        SourceBatch(batch_id=f"B-{tag}-GL", kind="gl", entity_id="E1",
                    journals=[journal]),
        SourceBatch(batch_id=f"B-{tag}-FX", kind="fx",
                    rate_table=RateTable(version=1, rates={"EUR": "1.07"})),
    ]


def test_conversion_residue_lands_on_a_named_rounding_line():
    pack = _mini_pack()
    prior_batches = _mini_batches("P", "100.00", "100.00")
    current_batches = _mini_batches("C", "133.33", "133.33")
    # Whole converted at 1.07: 214.00 → 285.33; movement 71.33.
    # Cells converted per account: 107.00 → 142.66 each, so the
    # account lines foot to 71.32 and a cent of residue remains.
    figure = Figure(metric_id="consolidated_revenue", label="Consol rev",
                    scope="consolidated", value="285.33", currency="USD")
    comparative = FigureComparative(
        metric_id="consolidated_revenue", prior_value="214.00",
        prior_currency="USD", prior_pack_id="PACK-PRIOR",
        change="71.33", change_pct="33.33")
    schedule = flux_module.build_schedule(
        pack, pack, current_batches, prior_batches,
        [figure], [comparative], prior_period="2026-01",
        prior_pack_id="PACK-PRIOR")
    assert schedule is not None
    entry = schedule.entries[0]
    by_account = _lines(entry, "account")
    assert by_account["4000"].amount == "35.66"
    assert by_account["4100"].amount == "35.66"
    rounding = [l for l in entry.by_account if l.kind == "rounding"]
    assert len(rounding) == 1 and rounding[0].amount == "0.01"
    total = sum((D(l.amount) for l in entry.by_account), D(0))
    assert total == D(entry.movement) == D("71.33")
    # The by-entity split converts whole entity amounts, so it
    # foots with no residue and carries no rounding line.
    assert all(l.kind != "rounding" for l in entry.by_entity)
    # And the independent check agrees with the produced schedule.
    assert verifier_module.verify_flux(
        schedule, pack, pack, current_batches, prior_batches,
        [figure], [comparative]) == []


def test_schedule_degrades_to_absent_without_the_prior_definitions():
    pack = _mini_pack()
    assert flux_module.build_schedule(
        pack, None, _mini_batches("C", "1.00", "1.00"),
        _mini_batches("P", "1.00", "1.00"), [], []) is None
    assert flux_module.build_schedule(
        pack, pack, _mini_batches("C", "1.00", "1.00"), None,
        [], []) is None


# -- narrative and evidence ------------------------------------------------------


def test_narrative_quotes_only_tied_flux(october):
    _, pack, _ = october
    assert pack.narrative is not None
    assert "moved USD +115,140.00 (+6.41%)" in pack.narrative
    assert "largest contribution came from HLD" in pack.narrative

    forged = pack.flux.model_copy(deep=True)
    entry = next(e for e in forged.entries
                 if e.metric_id == "consolidated_revenue")
    entry.current_value = "1.00"
    figures = [f.model_copy(update={"status": "verified"})
               for f in pack.figures]
    with pytest.raises(ValueError):
        build_narrative(figures, pack.period, flux=forged)


def test_bundles_carry_the_flux_section(october):
    service, pack, _ = october
    service.acknowledge_restatement(
        pack.pack_id, CONTROLLER, "Reviewed the HLG payroll restatement.")
    _chain(service, pack.pack_id)
    signed = service.sign_off(pack.pack_id, "sign", CONTROLLER)
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    assert document["format"] == "aidnn-close-evidence/v1"
    assert record.json_key.endswith("evidence-v1.json")
    flux_doc = document["flux"]
    assert flux_doc is not None
    assert len(flux_doc["entries"]) == 25
    revenue = next(e for e in flux_doc["entries"]
                   if e["metric_id"] == "consolidated_revenue")
    assert revenue["movement"] == "115140.00"
    text, _ = service.evidence_download(signed.pack_id, "txt")
    assert "FLUX SCHEDULE" in text.decode("utf-8")


def test_september_bundle_states_no_flux(store, signed_september):
    service, signed = signed_september
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    document = json.loads(data)
    # A close that predates the flux schedule says so, in the
    # same v1 format — the record is history, not upgraded.
    assert document["flux"] is None
