"""Money, FX conversion, and rounding — one module, one policy.

A close fails quietly when every layer rounds its own way, so all
arithmetic in this package goes through here:

- **Amounts are :class:`~decimal.Decimal` end to end.** JSON
  carries them as strings, the store keeps them as strings, and
  no figure ever passes through a binary float. (The one exception
  is display formatting in the console, which receives the string
  form.) Totals cannot drift by a cent because there is no float
  to drift in.
- **Rounding is half-up to the currency's minor unit** (2 places
  for USD and EUR here), applied at exactly two moments: when a
  journal line enters the mart, and when an entity figure is
  converted to the reporting currency. Definition-pack formulas
  sum *already-rounded* components, so a consolidated total is
  the sum of the figures on the page — the tie-out a controller
  performs by eye holds by construction.
- **Rates are data, versioned like everything else.** A
  :class:`RateTable` comes from an FX source batch; a board pack
  stamps the rate-table version it used, and a revised rate table
  makes any pack built on the old one stale (the service enforces
  that — this module just makes the versions comparable).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def D(value: object) -> Decimal:
    """Parse an amount into a Decimal without passing float."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Floats are accepted only at the system boundary and are
        # read through their shortest repr, never their binary form.
        return Decimal(str(value))
    return Decimal(str(value))


def q(value: Decimal) -> Decimal:
    """Quantize to minor units, half-up — the package's one rule."""
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> str:
    """The canonical string form of an amount (2dp, no exponent)."""
    return format(q(value), "f")


class RateTable(BaseModel):
    """FX rates as data: ``rates[ccy]`` = units of the reporting
    currency per 1 unit of ``ccy``. The reporting currency itself
    is always 1 and need not be listed."""

    version: int
    reporting_currency: str = "USD"
    rates: dict[str, str] = Field(default_factory=dict)

    def rate(self, currency: str) -> Decimal:
        if currency == self.reporting_currency:
            return Decimal("1")
        raw = self.rates.get(currency)
        if raw is None:
            raise KeyError(f"no FX rate for {currency} in rate table v{self.version}")
        return D(raw)

    def convert(self, amount: Decimal, currency: str) -> Decimal:
        """Convert an amount into the reporting currency, rounded
        once, half-up — the package's one conversion rule."""
        return q(D(amount) * self.rate(currency))
