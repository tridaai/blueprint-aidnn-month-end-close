"""Marts: normalization, the duplicate rule, fenced memos, stamps."""

from __future__ import annotations

from aidnn_close_agent.marts import build_marts, slot_key


def _current(world, phases):
    batches = []
    slots = {}
    for batch in world.batches:
        if batch.phase in phases:
            slots[slot_key(batch)] = batch
    return list(slots.values())


def test_duplicate_journal_is_voided_not_summed(world, pack_def):
    marts = build_marts(_current(world, {"initial"}), pack_def)
    assert marts.voided_journals == ["HLD:J-D9"]
    hld_payroll = [
        ln for ln in marts.gl("HLD")
        if ln.journal_id == "J-D9" and ln.account == "6100"
    ]
    # One live copy reaches the aggregates; the voided copy is
    # present in the mart (flagged), never summed.
    assert len(hld_payroll) == 1
    assert any(ln.voided and ln.journal_id == "J-D9" for ln in marts.gl_lines)


def test_corrected_extract_leaves_no_voided_journals(world, pack_def):
    marts = build_marts(_current(world, {"initial", "late"}), pack_def)
    assert marts.voided_journals == []


def test_injection_memo_is_fenced_in_the_mart(world, pack_def):
    marts = build_marts(_current(world, {"initial"}), pack_def)
    assert any("INJECTION_MARKER" in f for f in marts.injection_flags)
    rent = next(ln for ln in marts.gl("HLD") if ln.journal_id == "J-D6")
    assert "ignore previous" not in rent.memo.lower()
    assert "fenced by injection screen" in rent.memo


def test_mart_version_moves_when_a_source_version_moves(world, pack_def):
    first = build_marts(_current(world, {"initial"}), pack_def)
    second = build_marts(_current(world, {"initial", "late"}), pack_def)
    assert first.mart_version != second.mart_version
    assert first.source_versions.fx_version == 1
    assert second.source_versions.fx_version == 2


def test_amounts_are_decimal_and_rounded(world, pack_def):
    from decimal import Decimal

    marts = build_marts(_current(world, {"initial", "late"}), pack_def)
    for line in marts.gl_lines:
        assert isinstance(line.debit, Decimal)
        assert line.debit == line.debit.quantize(Decimal("0.01"))
    cash = sum((ln.net for ln in marts.gl("HLE") if ln.account == "1000"))
    assert str(cash) == "40000.00"
