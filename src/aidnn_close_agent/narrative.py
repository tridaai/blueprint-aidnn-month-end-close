"""The board-pack narrative: words only from verified numbers.

The narrative is the one place free text is produced, so its
input discipline is the guardrail: :func:`build_narrative`
accepts **only figures whose status is ``verified``** and raises
on anything else. An unverified figure cannot enter the
narrative's input — not by policy, by construction: in a blocked
pack there is no narrative at all, and in a signed pack every
number the narrative names is a number the verifier recomputed
from source. The composition itself is deterministic text
assembly over those figures; in a deployment the same verified
figure set is what an engine's drafting step would be handed —
never the raw memos, never the unverified draft.
"""

from __future__ import annotations

from .fx import D
from .schemas import Figure


def _fmt(figure: Figure) -> str:
    return f"{figure.currency} {D(figure.value):,.2f}"


def build_narrative(figures: list[Figure], period: str) -> str:
    """Compose the pack narrative from verified figures only."""
    unverified = [f.metric_id for f in figures if f.status != "verified"]
    if unverified:
        raise ValueError(
            "narrative input must be verified figures only; got unverified: "
            + ", ".join(sorted(set(unverified)))
        )
    by_id = {f.metric_id: f for f in figures if f.entity_id is None}
    by_entity = {
        (f.metric_id, f.entity_id): f for f in figures if f.entity_id is not None
    }

    lines = [f"Month-end close — {period}. All figures verified against source."]
    revenue = by_id.get("consolidated_revenue")
    if revenue is not None:
        lines.append(
            f"Consolidated external revenue was {_fmt(revenue)}"
            + (
                f", {D(by_id['revenue_vs_plan'].value):+,.2f} against plan."
                if "revenue_vs_plan" in by_id else "."
            )
        )
    entity_bits = []
    for (metric_id, entity_id), figure in sorted(by_entity.items()):
        if metric_id == "revenue_external":
            entity_bits.append(f"{entity_id} {_fmt(figure)}")
    if entity_bits:
        lines.append("External revenue by entity: " + "; ".join(entity_bits) + ".")
    eliminations = by_id.get("eliminations_total")
    if eliminations is not None and D(eliminations.value) != 0:
        lines.append(
            f"Intercompany eliminations of {_fmt(eliminations)} were applied "
            "after both legs were verified present and paired."
        )
    income = by_id.get("consolidated_operating_income")
    if income is not None:
        lines.append(f"Consolidated operating income was {_fmt(income)}.")
    cash = by_id.get("consolidated_cash")
    if cash is not None:
        lines.append(f"The group closed the month with cash of {_fmt(cash)}.")
    pipeline = by_id.get("pipeline_open")
    if pipeline is not None:
        lines.append(f"Open sales pipeline at close: {_fmt(pipeline)}.")
    return "\n".join(lines)
