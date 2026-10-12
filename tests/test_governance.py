"""Round 8 — definition change governance.

The pins, in order: the registry holds every shipped
version; the selection rule is a pure computation over the
activation records (supersession, from-period reach, the
deployment default); a dry-run over signed October reproduces
the hand-computed change list from sources — never from the
signed pack's figures, so a tampered signed figure shows up
as a baseline discrepancy instead of poisoning the impact,
and a tampered batch rate table reprices neither side
(both compute at the signed pack's stamped table); variance-
family changes are computed, shown on fabricated signed
packs whose variance sets differ under the candidate; the
activation's refusals each name their ground; a signed
period's pack is byte-untouched by everything governance
does; November, created on a v1.1.0-wired service, is
selected onto v1.2.0 by rule, states the change on its face,
and cites the act and the dry-run in its evidence bundle.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from aidnn_close_agent import governance
from aidnn_close_agent.config import definition_pack_path
from aidnn_close_agent.connectors import DatasetConnector
from aidnn_close_agent.datasets import (
    PERIOD,
    PERIOD_NOVEMBER,
    PERIOD_OCTOBER,
    RESTATEMENT_BATCH_ID,
    V120_CHANGED_METRICS,
    V120_DRY_RUN_ADDED,
    V120_DRY_RUN_MOVED,
    V120_NOVEMBER_FIGURES,
    build_november_world,
    build_october_world,
    build_world,
)
from aidnn_close_agent.definitions import (
    DefinitionPack,
    load_definition_pack,
    load_definition_pack_version,
)
from aidnn_close_agent.engine_offline import OfflineFinanceEngine
from aidnn_close_agent.evidence import EvidenceError
from aidnn_close_agent.graph import PackPipeline
from aidnn_close_agent.object_store import InMemoryObjectStore
from aidnn_close_agent.schemas import PackActivation
from aidnn_close_agent.service import CloseService, GateError
from aidnn_close_agent.store import InMemoryCloseStore

CONTROLLER = "Mara Ellison (Group Controller)"
REASON = (
    "Insurance premiums are a board line of their own from "
    "November; they leave operating expenses and stand "
    "separately. Measured first, per the dry-run."
)


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


@pytest.fixture()
def pack_v100():
    return load_definition_pack(definition_pack_path())


@pytest.fixture()
def pack_v110():
    pack = load_definition_pack_version("harborlight-close", "1.1.0")
    assert pack is not None
    return pack


@pytest.fixture()
def pack_v120():
    pack = load_definition_pack_version("harborlight-close", "1.2.0")
    assert pack is not None
    return pack


class _WorldConnector:
    """Serves one staged world's batches — November's route in."""

    name = "world"

    def __init__(self, world) -> None:
        self._batches = {b.batch_id: b for b in world.batches}

    def available(self):
        return list(self._batches.values())

    def fetch(self, batch_id: str):
        return self._batches[batch_id]


def _service(store, pack, connector=None) -> CloseService:
    return CloseService(
        pipeline=PackPipeline(
            engine=OfflineFinanceEngine(), store=store, pack=pack,
            checkpointer=MemorySaver()),
        store=store, connector=connector or DatasetConnector(),
        objects=InMemoryObjectStore(), pack_def=pack,
    )


@pytest.fixture()
def signed_two_months(pack_v100, pack_v110):
    """September signed under v1.0.0, October signed under
    v1.1.0 (restatement acknowledged) — the world a candidate
    is measured against. Returns (store, october_service,
    september_pack, october_pack)."""
    store = InMemoryCloseStore()
    september = _service(store, pack_v100)
    world = build_world()
    run = september.create_run(PERIOD)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches_in_phase("initial")])
    september.build_pack(run.run_id)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches_in_phase("late")])
    rebuilt = september.build_pack(run.run_id)
    _chain(september, rebuilt.pack_id)
    signed_september = september.sign_off(rebuilt.pack_id, "sign",
                                          CONTROLLER)
    assert signed_september.status == "SIGNED_OFF"
    september.receive_restatement(RESTATEMENT_BATCH_ID)
    october = _service(store, pack_v110)
    october_world = build_october_world()
    oct_run = october.create_run(PERIOD_OCTOBER)
    october.ingest(oct_run.run_id,
                   [b.batch_id for b in october_world.batches])
    oct_pack = october.build_pack(oct_run.run_id)
    october.acknowledge_restatement(
        oct_pack.pack_id, CONTROLLER,
        "September restatement reviewed; comparatives stand as signed.")
    _chain(october, oct_pack.pack_id)
    signed_october = october.sign_off(oct_pack.pack_id, "sign", CONTROLLER)
    assert signed_october.status == "SIGNED_OFF"
    return store, october, signed_september, signed_october


# ---------------------------------------------------------------------------
# The registry and the selection rule
# ---------------------------------------------------------------------------

def test_registry_holds_every_shipped_version(pack_v120):
    versions = [p.version for p in
                governance.registry_versions("harborlight-close")]
    assert versions == ["1.0.0", "1.1.0", "1.2.0"]
    assert pack_v120.pack_id == "harborlight-close"


def _activation(n: int, from_period: str, to_version: str) -> PackActivation:
    return PackActivation(
        activation_id=f"ACT-harborlight-close-{n}",
        pack_id="harborlight-close", from_version="1.0.0",
        to_version=to_version, from_period=from_period,
        dry_run_id="DRY-x", dry_run_digest="d" * 64,
        actor="A", reason="R", at="2026-10-01T00:00:00+00:00",
    )


def test_selection_rule_is_computed_from_the_records():
    assert governance.governing_version([], "2026-11", "1.1.0") == "1.1.0"
    acts = [_activation(1, "2026-11", "1.2.0")]
    # Before the from-period the prior version still governs.
    assert governance.governing_version(acts, "2026-10", "1.1.0") == "1.1.0"
    assert governance.governing_version(acts, "2026-11", "1.1.0") == "1.2.0"
    assert governance.governing_version(acts, "2027-03", "1.1.0") == "1.2.0"
    # A later act for the same from-period supersedes the first.
    acts.append(_activation(2, "2026-11", "1.1.0"))
    assert governance.governing_version(acts, "2026-11", "1.0.0") == "1.1.0"
    # A later from-period takes over only from its own period.
    acts.append(_activation(3, "2027-01", "1.2.0"))
    assert governance.governing_version(acts, "2026-12", "1.0.0") == "1.1.0"
    assert governance.governing_version(acts, "2027-01", "1.0.0") == "1.2.0"


def test_create_run_records_the_selected_version(pack_v110):
    store = InMemoryCloseStore()
    service = _service(store, pack_v110)
    run = service.create_run(PERIOD_OCTOBER)
    assert run.definition_pack_version == "1.1.0"
    assert "deployment default" in run.audit[-1]["detail"]


# ---------------------------------------------------------------------------
# The dry-run
# ---------------------------------------------------------------------------

def test_dry_run_reproduces_the_hand_computed_change(
    signed_two_months,
):
    store, service, _, signed_october = signed_two_months
    record = service.dry_run_definition_change("1.2.0")
    report = record.report
    assert report.reference_pack_id == signed_october.pack_id
    assert report.reference_period == PERIOD_OCTOBER
    assert report.base_version == "1.1.0"
    moved = {(d.metric_id, d.entity_id):
             (d.base_value, d.candidate_value, d.delta)
             for d in report.moved}
    assert moved == V120_DRY_RUN_MOVED
    assert {(f.metric_id, f.entity_id): f.value
            for f in report.added} == V120_DRY_RUN_ADDED
    assert report.dropped == []
    assert set(report.changed_metrics) == V120_CHANGED_METRICS
    assert report.material_count == 0
    assert report.baseline_discrepancies == []
    # Every moved figure's baseline also equals the signed
    # figure: the signed pack reproduces from its own sources.
    assert all(d.signed_pack_value == d.base_value for d in report.moved)


def test_dry_run_is_byte_stable_and_inert(signed_two_months):
    store, service, signed_september, signed_october = signed_two_months
    september_json = store.get_pack(
        signed_september.pack_id).model_dump_json()
    october_json = store.get_pack(
        signed_october.pack_id).model_dump_json()
    first = service.dry_run_definition_change("1.2.0")
    second = service.dry_run_definition_change("1.2.0")
    assert first.dry_run_id == second.dry_run_id
    assert first.digest == second.digest
    assert first.computed_at == second.computed_at
    assert store.list_activations() == []
    assert store.get_pack(signed_september.pack_id).model_dump_json() \
        == september_json
    assert store.get_pack(signed_october.pack_id).model_dump_json() \
        == october_json


def test_dry_run_refusals_name_their_grounds(signed_two_months, pack_v110):
    store, service, _, _ = signed_two_months
    with pytest.raises(GateError, match="not in the registry"):
        service.dry_run_definition_change("9.9.9")
    with pytest.raises(GateError, match="has no signed pack"):
        service.dry_run_definition_change("1.2.0", "2027-05")
    empty = _service(InMemoryCloseStore(), pack_v110)
    with pytest.raises(GateError, match="no signed pack on record"):
        empty.dry_run_definition_change("1.2.0")


def test_dry_run_reads_sources_not_the_signed_figures(
    signed_two_months,
):
    """A tampered signed figure cannot poison the impact: the
    change list still computes from sources, and the tamper
    surfaces as a baseline discrepancy."""
    store, service, _, signed_october = signed_two_months
    pack = store.get_pack(signed_october.pack_id)
    for figure in pack.figures:
        if figure.metric_id == "opex" and figure.entity_id == "HLG":
            figure.value = "999999.00"
    store.save_pack(pack)
    report = service.dry_run_definition_change("1.2.0").report
    assert len(report.baseline_discrepancies) == 1
    discrepancy = report.baseline_discrepancies[0]
    assert discrepancy.metric_id == "opex"
    assert discrepancy.signed_value == "999999.00"
    assert discrepancy.recomputed_value == "62000.00"
    moved = {(d.metric_id, d.entity_id): d for d in report.moved}
    assert moved[("opex", "HLG")].base_value == "62000.00"
    assert moved[("opex", "HLG")].signed_pack_value == "999999.00"


def test_dry_run_pins_both_sides_to_the_stamped_rate_table(
    signed_two_months,
):
    """Round 6's discipline: the dry-run computes at the
    signed pack's stamped rates. A tampered batch rate table
    reprices neither side — it surfaces as a RATE_TABLE_
    MISMATCH family on both, and the deltas do not move."""
    store, service, _, signed_october = signed_two_months
    assert signed_october.source_versions.fx_table is not None
    for batch in store.list_batches():
        if batch.kind == "fx" and batch.rate_table is not None:
            tampered = batch.model_copy(deep=True)
            tampered.rate_table.rates["EUR"] = "1.15"
            store.save_batch(tampered)
    report = service.dry_run_definition_change("1.2.0").report
    moved = {(d.metric_id, d.entity_id):
             (d.base_value, d.candidate_value) for d in report.moved}
    gold = {(k): (v[0], v[1]) for k, v in V120_DRY_RUN_MOVED.items()}
    assert moved == gold
    assert report.variance_families_base == ["RATE_TABLE_MISMATCH"]
    assert report.variance_families_candidate == ["RATE_TABLE_MISMATCH"]
    assert report.families_added == [] and report.families_removed == []


def test_family_changes_are_computed_not_asserted(pack_v100, pack_v110):
    """Two fabricated signed packs whose variance sets
    genuinely differ under the candidate: dropping the
    journal-uniqueness check clears DUPLICATE_JOURNAL;
    breaking the AR tie-out's account set raises
    SUBLEDGER_TIE_OUT. Neither family appears by assertion —
    each side is verified from sources."""
    # (a) September phase A, signed as it stands (blocked).
    store = InMemoryCloseStore()
    september = _service(store, pack_v100)
    world = build_world()
    run = september.create_run(PERIOD)
    september.ingest(run.run_id,
                     [b.batch_id for b in world.batches_in_phase("initial")])
    blocked = september.build_pack(run.run_id)
    assert blocked.status == "BLOCKED"
    scratch = InMemoryCloseStore()
    for batch in world.batches_in_phase("initial"):
        scratch.save_batch(batch)
    scratch.save_pack(blocked.model_copy(update={"status": "SIGNED_OFF"}))
    relaxed = DefinitionPack.model_validate({
        **pack_v100.model_dump(),
        "unique_journal_ids": False,
    })
    report = governance.compute_dry_run(
        scratch, blocked.model_copy(update={"status": "SIGNED_OFF"}),
        pack_v100, relaxed, OfflineFinanceEngine())
    assert "DUPLICATE_JOURNAL" in report.variance_families_base
    assert report.families_removed == ["DUPLICATE_JOURNAL"]
    assert report.families_added == []

    # (b) October, signed clean; the candidate breaks the
    # accounts-receivable tie-out's account set.
    store2 = InMemoryCloseStore()
    september2 = _service(store2, pack_v100)
    run = september2.create_run(PERIOD)
    september2.ingest(run.run_id,
                      [b.batch_id for b in world.batches_in_phase("initial")])
    september2.build_pack(run.run_id)
    september2.ingest(run.run_id,
                      [b.batch_id for b in world.batches_in_phase("late")])
    rebuilt = september2.build_pack(run.run_id)
    _chain(september2, rebuilt.pack_id)
    september2.sign_off(rebuilt.pack_id, "sign", CONTROLLER)
    october2 = _service(store2, pack_v110)
    october_world = build_october_world()
    oct_run = october2.create_run(PERIOD_OCTOBER)
    october2.ingest(oct_run.run_id,
                    [b.batch_id for b in october_world.batches])
    october2.build_pack(oct_run.run_id)
    scratch2 = InMemoryCloseStore()
    signed_october = store2.get_pack(oct_run.pack_ids[-1])
    for batch_id in signed_october.source_versions.batches:
        scratch2.save_batch(store2.get_batch(batch_id))
    scratch2.save_pack(signed_october)
    broken = DefinitionPack.model_validate({
        **pack_v110.model_dump(),
        "tie_outs": [
            {**pack_v110.tie_outs[0].model_dump(),
             "gl_accounts": ["4000"]},
            *[t.model_dump() for t in pack_v110.tie_outs[1:]],
        ],
    })
    report = governance.compute_dry_run(
        scratch2, signed_october, pack_v110, broken,
        OfflineFinanceEngine())
    assert report.variance_families_base == []
    assert report.families_added == ["SUBLEDGER_TIE_OUT"]


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

def test_activation_without_a_dry_run_is_refused(signed_two_months):
    _, service, _, _ = signed_two_months
    with pytest.raises(GateError, match="no dry-run on record"):
        service.activate_definition_pack(
            "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)


def test_activation_refusals_name_their_grounds(signed_two_months):
    _, service, _, _ = signed_two_months
    service.dry_run_definition_change("1.2.0")
    with pytest.raises(GateError, match="must name its actor"):
        service.activate_definition_pack(
            "1.2.0", PERIOD_NOVEMBER, "", REASON)
    with pytest.raises(GateError, match="must carry a reason"):
        service.activate_definition_pack(
            "1.2.0", PERIOD_NOVEMBER, CONTROLLER, "")
    with pytest.raises(GateError, match="already signed"):
        service.activate_definition_pack(
            "1.2.0", PERIOD_OCTOBER, CONTROLLER, REASON)
    with pytest.raises(GateError, match="already governs"):
        service.activate_definition_pack(
            "1.1.0", PERIOD_NOVEMBER, CONTROLLER, REASON)
    with pytest.raises(GateError, match="not in the registry"):
        service.activate_definition_pack(
            "9.9.9", PERIOD_NOVEMBER, CONTROLLER, REASON)


def test_activation_record_cites_the_dry_run(signed_two_months):
    _, service, _, _ = signed_two_months
    record = service.dry_run_definition_change("1.2.0")
    activation = service.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)
    assert activation.dry_run_id == record.dry_run_id
    assert activation.dry_run_digest == record.digest
    assert activation.from_version == "1.1.0"
    assert activation.to_version == "1.2.0"
    assert activation.from_period == PERIOD_NOVEMBER
    assert activation.supersedes is None
    with pytest.raises(GateError, match="already governs"):
        service.activate_definition_pack(
            "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)


def test_activation_can_be_superseded_at_the_same_from_period(
    signed_two_months,
):
    _, service, _, _ = signed_two_months
    service.dry_run_definition_change("1.2.0")
    first = service.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)
    service.dry_run_definition_change("1.1.0")
    second = service.activate_definition_pack(
        "1.1.0", PERIOD_NOVEMBER, CONTROLLER,
        "The board presentation is deferred a month; v1.1.0 "
        "governs November after all.")
    assert second.supersedes == first.activation_id
    assert second.from_version == "1.2.0"
    state = service.definition_state(PERIOD_NOVEMBER)
    assert state["governing"]["version"] == "1.1.0"
    assert state["governing"]["activation_id"] == second.activation_id


# ---------------------------------------------------------------------------
# The change rides the packs
# ---------------------------------------------------------------------------

def _november_pack(signed_two_months):
    store, service, _, _ = signed_two_months
    service.dry_run_definition_change("1.2.0")
    activation = service.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)
    november_world = build_november_world("55000.00")
    november = _service(store, signed_two_months[1].pack_def,
                        connector=_WorldConnector(november_world))
    run = november.create_run(PERIOD_NOVEMBER)
    november.ingest(run.run_id,
                    [b.batch_id for b in november_world.batches])
    pack = november.build_pack(run.run_id)
    return store, november, activation, run, pack


def test_next_period_is_selected_and_states_the_change(
    signed_two_months, pack_v110, pack_v120,
):
    store, november, activation, run, pack = _november_pack(
        signed_two_months)
    # The service was wired to v1.1.0; the rule, not the
    # wiring, put v1.2.0 in charge of November.
    assert november.pack_def.version == "1.1.0"
    assert run.definition_pack_version == "1.2.0"
    assert pack.definition_pack_version == "1.2.0"
    change = pack.definition_change
    assert change is not None
    assert change.from_version == "1.1.0"
    assert change.to_version == "1.2.0"
    assert change.from_period == PERIOD_NOVEMBER
    assert change.activation_id == activation.activation_id
    assert change.actor == CONTROLLER
    assert change.reason == REASON
    assert (change.moved_count, change.added_count,
            change.dropped_count, change.material_count) == (4, 4, 0, 0)
    figures = {(f.metric_id, f.entity_id): f.value for f in pack.figures}
    for key, expected in V120_NOVEMBER_FIGURES.items():
        assert figures[key] == expected
    # A second governed period states no change: once November
    # has signed under v1.2.0, the version did not change
    # under December — the statement is honestly absent.
    _chain(november, pack.pack_id)
    november.sign_off(pack.pack_id, "sign", CONTROLLER)
    assert governance.prepare_change_statement(
        store, "2026-12", pack_v120, activation) is None


def test_signed_periods_never_change_their_pack(signed_two_months):
    store, _, signed_september, signed_october = signed_two_months
    september_json = store.get_pack(
        signed_september.pack_id).model_dump_json()
    october_json = store.get_pack(
        signed_october.pack_id).model_dump_json()
    _november_pack(signed_two_months)
    assert store.get_pack(signed_september.pack_id).model_dump_json() \
        == september_json
    assert store.get_pack(signed_october.pack_id).model_dump_json() \
        == october_json
    assert signed_september.definition_pack_version == "1.0.0"
    assert signed_october.definition_pack_version == "1.1.0"


def test_bundle_carries_the_governance(signed_two_months):
    import json

    store, november, activation, _, pack = _november_pack(
        signed_two_months)
    _chain(november, pack.pack_id)
    signed = november.sign_off(pack.pack_id, "sign", CONTROLLER)
    november.generate_evidence(signed.pack_id)
    data, _ = november.evidence_download(signed.pack_id, "json")
    section = json.loads(data)["definition_change"]
    assert section["activation"]["activation_id"] \
        == activation.activation_id
    assert section["activation"]["to_version"] == "1.2.0"
    assert section["dry_run"]["digest"] == activation.dry_run_digest
    assert len(section["dry_run"]["report"]["moved"]) == 4
    raw, _ = november.evidence_download(signed.pack_id, "txt")
    text = raw.decode("utf-8")
    assert "DEFINITION CHANGE" in text
    assert "v1.2.0" in text


def test_bundle_refuses_when_the_cited_records_do_not_stand(
    signed_two_months, pack_v110,
):
    """The bundle's completeness rule extends to governance:
    a pack whose cited activation or dry-run is missing from
    the store cannot be evidenced."""
    store, november, _, _, pack = _november_pack(signed_two_months)
    _chain(november, pack.pack_id)
    signed = november.sign_off(pack.pack_id, "sign", CONTROLLER)
    bare = InMemoryCloseStore()
    for batch in store.list_batches():
        bare.save_batch(batch)
    bare.save_run(store.get_run(pack.run_id))
    bare.save_pack(signed)
    orphan = _service(bare, pack_v110)
    with pytest.raises(EvidenceError, match="does not stand"):
        orphan.generate_evidence(signed.pack_id)


def test_pre_governance_packs_project_an_honest_null(
    signed_two_months,
):
    import json

    _, service, signed_september, _ = signed_two_months
    service.generate_evidence(signed_september.pack_id)
    data, _ = service.evidence_download(signed_september.pack_id, "json")
    assert json.loads(data)["definition_change"] is None


# ---------------------------------------------------------------------------
# Store and API surfaces
# ---------------------------------------------------------------------------

def test_governance_records_round_trip_the_store(signed_two_months):
    store, service, _, _ = signed_two_months
    record = service.dry_run_definition_change("1.2.0")
    activation = service.activate_definition_pack(
        "1.2.0", PERIOD_NOVEMBER, CONTROLLER, REASON)
    assert store.get_dry_run(record.dry_run_id).digest == record.digest
    assert [a.activation_id for a in store.list_activations()] == [
        activation.activation_id]
    assert [r.dry_run_id for r in store.list_dry_runs()] == [
        record.dry_run_id]


def test_api_surfaces_the_governance_state(pack_v110):
    from fastapi.testclient import TestClient

    from aidnn_close_agent.api import create_app

    service = _service(InMemoryCloseStore(), pack_v110)
    client = TestClient(create_app(service))
    state = client.get("/definitions").json()
    assert state["registry_versions"] == ["1.0.0", "1.1.0", "1.2.0"]
    assert state["default_version"] == "1.1.0"
    assert state["activations"] == []
    scoped = client.get("/definitions", params={"period": "2026-11"}).json()
    assert scoped["governing"]["version"] == "1.1.0"
    assert scoped["governing"]["source"] == "deployment default"
    refused = client.post("/definitions/dry-run",
                          json={"candidate_version": "1.2.0"})
    assert refused.status_code == 409
    assert "no signed pack" in refused.json()["detail"]
    refused = client.post("/definitions/activate", json={
        "version": "1.2.0", "from_period": "2026-11",
        "actor": CONTROLLER, "reason": REASON})
    assert refused.status_code == 409
    assert "no dry-run on record" in refused.json()["detail"]
