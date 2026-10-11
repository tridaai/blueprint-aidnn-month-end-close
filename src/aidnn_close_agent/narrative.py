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
from .schemas import Figure, FluxSchedule


def _fmt(figure: Figure) -> str:
    return f"{figure.currency} {D(figure.value):,.2f}"


def build_narrative(figures: list[Figure], period: str,
                    flux: FluxSchedule | None = None) -> str:
    """Compose the pack narrative from verified figures only.

    When a flux schedule is supplied it has already passed the
    verifier's independent recomputation (the pipeline only
    builds a narrative for a pack that passed), and this
    function adds its own tie-out before quoting it: every
    flux entry's current value must equal the verified figure
    it explains. A movement the narrative names is therefore a
    movement that foots to a verified figure — the round-1 rule
    applied to the flux layer unchanged."""
    unverified = [f.metric_id for f in figures if f.status != "verified"]
    if unverified:
        raise ValueError(
            "narrative input must be verified figures only; got unverified: "
            + ", ".join(sorted(set(unverified)))
        )
    if flux is not None:
        verified_values = {
            (f.metric_id, f.entity_id): f.value for f in figures
        }
        for entry in flux.entries:
            figure_value = verified_values.get(
                (entry.metric_id, entry.entity_id))
            if figure_value is None or D(entry.current_value) != D(figure_value):
                raise ValueError(
                    "narrative flux input must tie to verified figures; "
                    f"{entry.metric_id} starts from {entry.current_value}, "
                    f"the verified figure is {figure_value}"
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
    if flux is not None:
        material = [e for e in flux.entries if e.material]
        material.sort(key=lambda e: -abs(D(e.movement)))
        for entry in material[:3]:
            figure = next(
                (f for f in figures
                 if (f.metric_id, f.entity_id)
                 == (entry.metric_id, entry.entity_id)),
                None,
            )
            if figure is None:
                continue
            scope = f" ({entry.entity_id})" if entry.entity_id else ""
            pct = f" ({D(entry.movement_pct):+,.2f}%)" \
                if entry.movement_pct is not None else ""
            drivers = [
                line for line in entry.by_entity
                if line.kind == "entity" and D(line.amount) != 0
            ]
            driver_text = ""
            if drivers:
                top = max(drivers, key=lambda line: abs(D(line.amount)))
                driver_text = (
                    f" The largest contribution came from {top.key}, "
                    f"{entry.currency} {D(top.amount):+,.2f}."
                )
            lines.append(
                f"{figure.label}{scope} moved "
                f"{entry.currency} {D(entry.movement):+,.2f}{pct} "
                f"against {flux.prior_period}.{driver_text}"
            )
    return "\n".join(lines)
