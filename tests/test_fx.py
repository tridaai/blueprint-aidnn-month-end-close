"""Money discipline: Decimal end to end, one rounding rule."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aidnn_close_agent.fx import D, RateTable, money, q


def test_amounts_parse_without_float():
    assert D("0.1") + D("0.2") == D("0.3")
    assert money(D("1234.5")) == "1234.50"


def test_rounding_is_half_up():
    assert q(D("1.005")) == D("1.01")
    assert q(D("1.004")) == D("1.00")
    assert q(D("-1.005")) == D("-1.01")


def test_conversion_rounds_once_at_the_figure():
    table = RateTable(version=1, rates={"EUR": "1.08"})
    # 615000 EUR at 1.08 — the phase-A consolidated revenue leg.
    assert table.convert(D("615000"), "EUR") == D("664200.00")
    # Reporting currency converts at 1.
    assert table.convert(D("42.10"), "USD") == D("42.10")


def test_missing_rate_is_an_error_not_a_guess():
    table = RateTable(version=1, rates={})
    with pytest.raises(KeyError):
        table.convert(D("1.00"), "EUR")


def test_long_sums_do_not_drift():
    total = sum((D("0.01") for _ in range(10000)), D("0"))
    assert total == D("100.00")
    assert Decimal("55000.00") * D("1.10") == D("60500.0000")
