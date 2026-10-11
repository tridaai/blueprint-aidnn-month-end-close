"""The close discipline, end to end through the service."""

from __future__ import annotations

import pytest

from aidnn_close_agent.errors import ChecklistIncomplete, GateError


def test_build_before_ingestion_is_refused(service):
    run = service.create_run("2026-09")
    with pytest.raises(ChecklistIncomplete) as excinfo:
        service.build_pack(run.run_id)
    assert "HLG:gl" in str(excinfo.value)
    assert "GROUP:fx" in str(excinfo.value)


def test_partial_ingestion_is_still_incomplete(service, world):
    run = service.create_run("2026-09")
    service.ingest(run.run_id, ["B-HLG-GL-v1", "B-HLG-AR-v1"])
    run = service.get_run(run.run_id)
    assert run.status == "COLLECTING"
    with pytest.raises(ChecklistIncomplete):
        service.build_pack(run.run_id)


def test_first_attempt_blocks_with_named_variances(service, run_ready, world):
    pack = service.build_pack(run_ready.run_id)
    assert pack.status == "BLOCKED"
    codes = sorted(v.code for v in pack.variances)
    assert codes == sorted(world.phase_a_variance_codes)
    # Every figure still carries its full provenance stamps.
    for figure in pack.figures:
        assert figure.definition_pack_version == "1.0.0"
        assert figure.source_versions.batches
    assert pack.source_versions.fx_version == 1
    # A blocked pack has no narrative — narrative input is
    # verified figures only, and these are hostage to variances.
    assert pack.narrative is None


def test_blocked_pack_cannot_be_signed(service, run_ready):
    pack = service.build_pack(run_ready.run_id)
    with pytest.raises(GateError):
        service.sign_off(pack.pack_id, "sign", "Mara Ellison")


def test_late_sources_make_the_first_pack_stale(service, run_ready, world):
    pack = service.build_pack(run_ready.run_id)
    service.ingest(run_ready.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    stale = service.get_pack(pack.pack_id)
    assert stale.status == "STALE"
    assert any(a["event"] == "marked_stale" for a in stale.audit)
    with pytest.raises(GateError):
        service.sign_off(pack.pack_id, "sign", "Mara Ellison")


def test_corrected_close_verifies_and_signs(service, run_corrected, world):
    pack = service.build_pack(run_corrected.run_id)
    assert pack.status == "AWAITING_CONTROLLER"
    assert pack.variances == []
    figures = {(f.metric_id, f.entity_id): f for f in pack.figures}
    for key, expected in world.gold_figures.items():
        metric_id, _, entity_id = key.partition("@")
        figure = figures[(metric_id, entity_id or None)]
        assert figure.value == expected, key
        assert figure.status == "verified"
    assert pack.narrative is not None
    assert "1,796,500.00" in pack.narrative
    assert pack.source_versions.fx_version == 2

    signed = service.sign_off(pack.pack_id, "sign", "Mara Ellison",
                              "variances cleared")
    assert signed.status == "SIGNED_OFF"
    assert signed.decision.actor == "Mara Ellison"
    run = service.get_run(run_corrected.run_id)
    assert run.status == "CLOSED"


def test_sign_off_must_name_the_controller(service, run_corrected):
    pack = service.build_pack(run_corrected.run_id)
    with pytest.raises(GateError):
        service.sign_off(pack.pack_id, "sign", "  ")


def test_return_path_records_the_reason(service, run_corrected):
    pack = service.build_pack(run_corrected.run_id)
    returned = service.sign_off(pack.pack_id, "return", "Mara Ellison",
                                "recheck the pipeline figure with FP&A")
    assert returned.status == "RETURNED"
    assert returned.decision.reason.startswith("recheck")
    run = service.get_run(run_corrected.run_id)
    assert run.status != "CLOSED"


def test_closed_run_refuses_late_ingestion(service, run_corrected, world):
    pack = service.build_pack(run_corrected.run_id)
    service.sign_off(pack.pack_id, "sign", "Mara Ellison")
    with pytest.raises(GateError):
        service.ingest(run_corrected.run_id, ["B-CRM-v1"])


def test_injection_flag_rides_the_run_and_changes_no_figure(
        service, run_ready, world):
    run = service.get_run(run_ready.run_id)
    assert any("INJECTION_MARKER" in f for f in run.injection_flags)
    pack = service.build_pack(run_ready.run_id)
    figures = {(f.metric_id, f.entity_id): f for f in pack.figures}
    # The rent figure is what the ledger says, memo notwithstanding.
    assert figures[("opex", "HLD")].value == "133250.00"


def test_second_run_of_same_period_gets_its_own_id(service):
    first = service.create_run("2026-09")
    second = service.create_run("2026-09")
    assert first.run_id != second.run_id
