"""The offline reference engine: the port, over the local marts.

This is the engine the tests, evals, and demo run — a complete,
deterministic implementation of :class:`FinanceEnginePort` over
the governed marts. It exists so the deployment layer around
the engine (definitions, verification, gates, staleness) can be
proven end to end without a live aidnn workspace, and so a
deployment has a reference for what the engine's answers should
look like on data it already knows.

It *proposes*: every figure leaves marked ``proposed``. Nothing
here decides whether a figure is right — that is the verifier's
separate job, from source.
"""

from __future__ import annotations

from decimal import Decimal

from .definitions import DefinitionPack, MetricDefinition
from .fx import D, ZERO, money, q
from .marts import MartLine, MartSet
from .schemas import Entity, Figure


def _measure(lines: list[MartLine], metric: MetricDefinition) -> Decimal:
    """One base GL metric over mart lines, in entity currency."""
    accounts = set(metric.accounts)
    total = ZERO
    for line in lines:
        if line.account not in accounts:
            continue
        if metric.exclude_ic and line.ic_counterparty:
            continue
        if metric.measure == "credit_minus_debit":
            total += line.credit - line.debit
        elif metric.measure == "debit_minus_credit":
            total += line.debit - line.credit
    return q(total)


def _ic_legs(marts: MartSet, account: str, side: str) -> dict[str, Decimal]:
    """Intercompany legs on one account, per entity, entity
    currency: the revenue side sums credits, the cost side debits.
    Only IC-flagged lines are legs — an unflagged line on the
    account is ordinary business, not an elimination candidate."""
    per_entity: dict[str, Decimal] = {}
    for line in marts.gl():
        if line.account != account or not line.ic_counterparty:
            continue
        amount = line.credit if side == "credit" else line.debit
        per_entity[line.entity_id] = per_entity.get(line.entity_id, ZERO) + amount
    return per_entity


def _converted_total(per_entity: dict[str, Decimal], marts: MartSet,
                     entities: dict[str, Entity]) -> Decimal:
    total = ZERO
    for entity_id, amount in per_entity.items():
        total += marts.rate_table.convert(amount, entities[entity_id].currency)
    return q(total)


def elimination_matched(pack: DefinitionPack, marts: MartSet,
                        elimination_id: str) -> Decimal:
    """The matched (eliminable) amount for one elimination, in
    the reporting currency: the lesser of the two converted leg
    totals. An unmatched excess eliminates nothing — the
    verifier names it instead."""
    elim = next(e for e in pack.eliminations if e.elimination_id == elimination_id)
    entities = {e["entity_id"]: Entity.model_validate(e) for e in pack.entities}
    revenue = _converted_total(_ic_legs(marts, elim.revenue_account, "credit"),
                               marts, entities)
    cost = _converted_total(_ic_legs(marts, elim.cost_account, "debit"),
                            marts, entities)
    return min(revenue, cost)


class OfflineFinanceEngine:
    """Reference FinanceEnginePort over the bundled marts."""

    name = "offline"

    def answer(self, pack: DefinitionPack, marts: MartSet) -> list[Figure]:
        entities = [Entity.model_validate(e) for e in pack.entities]
        by_id = {e.entity_id: e for e in entities}
        values: dict[tuple[str, str | None], Decimal] = {}
        figures: dict[tuple[str, str | None], Figure] = {}

        def stamp(metric: MetricDefinition, entity_id: str | None,
                  value: Decimal, currency: str) -> None:
            key = (metric.metric_id, entity_id)
            values[key] = q(value)
            figures[key] = Figure(
                metric_id=metric.metric_id,
                label=metric.label,
                scope=metric.scope,
                entity_id=entity_id,
                value=money(value),
                currency=currency,
                status="proposed",
                definition_pack_version=pack.version,
                source_versions=marts.source_versions,
            )

        # Base metrics: entity scope over GL lines, group over CRM.
        for metric in pack.metrics:
            if metric.derived is not None:
                continue
            if metric.scope == "entity":
                for entity in entities:
                    stamp(metric, entity.entity_id,
                          _measure(marts.gl(entity.entity_id), metric),
                          entity.currency)
            elif metric.scope == "group" and metric.source == "crm":
                total = sum((D(o.amount) for o in marts.opportunities), ZERO)
                stamp(metric, None, total, pack.reporting_currency)

        # Derived metrics, resolved in dependency order.
        pending = [m for m in pack.metrics if m.derived is not None]
        while pending:
            progressed = False
            for metric in list(pending):
                derived = metric.derived
                assert derived is not None
                if derived.op == "sum_converted":
                    if not all((derived.of, e.entity_id) in values for e in entities):
                        continue
                    total = ZERO
                    for entity in entities:
                        total += marts.rate_table.convert(
                            values[(derived.of, entity.entity_id)], entity.currency
                        )
                    stamp(metric, None, total, pack.reporting_currency)
                elif derived.op in ("add", "subtract"):
                    if not all((a, None) in values for a in derived.args):
                        continue
                    total = values[(derived.args[0], None)]
                    for arg in derived.args[1:]:
                        total = total + values[(arg, None)] if derived.op == "add" \
                            else total - values[(arg, None)]
                    stamp(metric, None, total, pack.reporting_currency)
                elif derived.op == "vs_plan":
                    if (derived.of, None) not in values:
                        continue
                    plan_amount = D(pack.plan.get(derived.of, "0"))
                    stamp(metric, None, values[(derived.of, None)] - plan_amount,
                          pack.reporting_currency)
                elif derived.op == "elimination":
                    stamp(metric, None,
                          elimination_matched(pack, marts, derived.elimination_id or ""),
                          pack.reporting_currency)
                pending.remove(metric)
                progressed = True
            if not progressed:
                raise ValueError("definition pack has an unresolvable derived metric")

        by_id  # (kept for parity with the verifier's shape)
        ordered: list[Figure] = []
        for metric in pack.metrics:
            if metric.scope == "entity":
                for entity in entities:
                    ordered.append(figures[(metric.metric_id, entity.entity_id)])
            else:
                ordered.append(figures[(metric.metric_id, None)])
        return ordered
