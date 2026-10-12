"""Figure drill-down: every figure opens into the lines it
stands on.

The evidence bundle lets an auditor pull the raw extracts and
re-perform the close. What it could not answer was the
per-figure question — *which journal lines, in which batches,
sum to this number?* This module is that answer, built as a
re-performance, not a report:

- **Sources only.** The drill walks the exact batches the pack
  stamps, at their stamped versions, under the definition-pack
  version the pack cites and the rate table the pack stamps
  (round 6's rule — conversions are judged at the stamp; a
  rate table edited later reprices no drill). It never reads
  the engine's figures (beyond the one value it must foot to),
  the marts, or the verifier's totals: it flattens and sums
  with its own code, applying the pack's data-quality rules on
  its own scan — a journal id repeated inside one extract
  counts once, its first copy, exactly as the close itself
  counted it.
- **Coverage follows the definition, honestly.** A base GL
  figure drills to its lines. A CRM figure drills to its
  records. An elimination drills to *both legs* — every
  intercompany line on each account, per entity, converted
  once per entity subtotal at the stamp — and the matched
  amount is the lesser leg, stated as the rule it is. A
  converted figure drills per entity: lines in entity
  currency, the entity subtotal, the stamped rate, the
  converted subtotal — conversion happens once, to the
  subtotal, because that is the close's own arithmetic; lines
  are never dressed with converted amounts the close never
  computed. A derived figure (``add`` / ``subtract`` /
  ``vs_plan``) drills as its own composition tree: the
  operands' drills nested under it with the operator named,
  and for ``vs_plan`` the plan baseline shown as a composition
  line of its own — authored data from the definition pack,
  labelled as such, never disguised as a source line.
- **The identity is the gate.** A drill is served only when
  its composition foots to the figure on the pack record,
  Decimal-exact. When it does not — a source record moved
  under the pack's stamps, or a figure that was never produced
  from them — the drill refuses with ``DRILL_MISMATCH`` naming
  the figure and both totals. A footing lie is the one output
  this module exists to never produce.
- **Any pack state may be drilled.** Blocked, awaiting,
  signed, returned, stale: the drill is computed from the
  pack's *stamps*, not from the run's current slot map, so it
  stays a true statement about the pack even after the world
  moved on — and the pack's state rides the drill, named on
  its face, the way the evidence idiom names state wherever
  an artifact could otherwise be misread. What refuses is
  only what would make the drill false: a figure the pack
  does not carry (:class:`DrillNotFound`), a stamped batch
  missing from the store or standing at another version, a
  definition version that cannot be resolved — and a base
  definition whose measure the close gives no line semantics
  (``sum_amount`` over GL lines: the measure belongs to CRM
  records, and neither the engine nor the verifier defines it
  over journal lines, so the drill will not invent one).

The drill is a pure function of the pack record, its stamped
sources, and its cited definitions: no timestamp, no stored
state of its own. That is what lets the evidence bundle cite
a drill by digest — regenerate the drill anywhere and the
digest either matches the bundle's or something moved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from .definitions import DefinitionPack, MetricDefinition
from .errors import DrillError, DrillMismatch, DrillNotFound
from .fx import D, ZERO, RateTable, money, q
from .schemas import (
    BoardPack,
    DrillLine,
    DrillNode,
    DrillRecord,
    FigureDrill,
    SourceBatch,
)


@dataclass
class _Line:
    """One flattened source line, this module's own scan."""

    entity_id: str
    batch_id: str
    batch_version: int
    journal_id: str
    journal_date: str
    line_index: int
    account: str
    debit: Decimal
    credit: Decimal
    ic_counterparty: str | None
    memo: str


def _stamped_batches(store, pack: BoardPack) -> list[SourceBatch]:
    """The pack's stamped batches, from the store, checked
    against the stamps: a drill computed from any other set
    would be a statement about a different close."""
    batches: list[SourceBatch] = []
    for batch_id in sorted(pack.source_versions.batches):
        stamped = pack.source_versions.batches[batch_id]
        batch = store.get_batch(batch_id)
        if batch is None:
            raise DrillError(
                f"pack {pack.pack_id} stamps source batch "
                f"{batch_id} (v{stamped}), which is missing from "
                "the store — the drill would be computed from "
                "something other than the sources the close "
                "consumed, so no drill is served"
            )
        if batch.version != stamped:
            raise DrillError(
                f"source batch {batch_id} stands in the store at "
                f"v{batch.version}, but pack {pack.pack_id} stamps "
                f"v{stamped} — the drill is computed at the "
                "stamped version or not at all"
            )
        batches.append(batch)
    return batches


def _flatten(batches: list[SourceBatch],
             pack_def: DefinitionPack) -> dict[str, list[_Line]]:
    """GL lines per entity, flattened by this module's own
    scan, in batch order. The pack's duplicate rule is applied
    here as the close applies it: a journal id repeated inside
    one extract counts once — the first copy stands, the later
    copies never reach a drill, exactly as they never reached
    a figure."""
    per_entity: dict[str, list[_Line]] = {}
    for batch in sorted(batches, key=lambda b: b.batch_id):
        if batch.kind != "gl" or not batch.entity_id:
            continue
        lines = per_entity.setdefault(batch.entity_id, [])
        seen: dict[str, int] = {}
        for journal in batch.journals:
            seen[journal.journal_id] = seen.get(journal.journal_id, 0) + 1
            if pack_def.unique_journal_ids and seen[journal.journal_id] > 1:
                continue  # later copies are void — the close's rule
            for index, line in enumerate(journal.lines):
                lines.append(_Line(
                    entity_id=batch.entity_id,
                    batch_id=batch.batch_id,
                    batch_version=batch.version,
                    journal_id=journal.journal_id,
                    journal_date=journal.date,
                    line_index=index,
                    account=line.account,
                    debit=q(D(line.debit)),
                    credit=q(D(line.credit)),
                    ic_counterparty=line.ic_counterparty,
                    memo=line.memo,
                ))
    return per_entity


def _contribution(line: _Line, metric: MetricDefinition) -> Decimal | None:
    """The line's signed contribution to a base GL metric, or
    ``None`` when the line does not feed the metric (account
    outside the definition's set, or an intercompany line the
    definition excludes). Only the two measures the close
    defines over journal lines reach here."""
    if line.account not in metric.accounts:
        return None
    if metric.exclude_ic and line.ic_counterparty:
        return None
    if metric.measure == "credit_minus_debit":
        return q(line.credit - line.debit)
    if metric.measure == "debit_minus_credit":
        return q(line.debit - line.credit)
    return None


class _Driller:
    """Builds drill nodes over one pack's stamped world."""

    def __init__(self, pack_def: DefinitionPack,
                 batches: list[SourceBatch], rates: RateTable) -> None:
        self.pack_def = pack_def
        self.batches = batches
        self.rates = rates
        self.currencies = {
            e["entity_id"]: e["currency"] for e in pack_def.entities
        }
        self.lines = _flatten(batches, pack_def)

    # -- base figures ------------------------------------------------

    def base_node(self, metric: MetricDefinition,
                  entity_id: str) -> DrillNode:
        if metric.measure not in ("credit_minus_debit",
                                  "debit_minus_credit"):
            raise DrillError(
                f"figure {metric.metric_id} for {entity_id} is a "
                f"base GL metric with measure {metric.measure!r}, "
                "which the close defines over CRM records, not "
                "journal lines — neither the engine nor the "
                "verifier gives it line semantics, so the drill "
                "refuses it rather than inventing a meaning"
            )
        currency = self.currencies[entity_id]
        lines: list[DrillLine] = []
        total = ZERO
        for line in self.lines.get(entity_id, []):
            contribution = _contribution(line, metric)
            if contribution is None:
                continue
            total += contribution
            lines.append(DrillLine(
                entity_id=line.entity_id,
                batch_id=line.batch_id,
                batch_version=line.batch_version,
                journal_id=line.journal_id,
                journal_date=line.journal_date,
                line_index=line.line_index,
                account=line.account,
                debit=money(line.debit),
                credit=money(line.credit),
                ic_counterparty=line.ic_counterparty,
                memo=line.memo,
                amount=money(contribution),
                currency=currency,
            ))
        measure_text = (
            "credit − debit" if metric.measure == "credit_minus_debit"
            else "debit − credit"
        )
        note = (
            f"{measure_text} over accounts "
            f"{', '.join(metric.accounts)}"
            + ("; intercompany-flagged lines excluded"
               if metric.exclude_ic else "")
        )
        return DrillNode(
            metric_id=metric.metric_id, label=metric.label,
            entity_id=entity_id, kind="base", currency=currency,
            value=money(q(total)), lines=lines, note=note,
        )

    def crm_node(self, metric: MetricDefinition) -> DrillNode:
        records: list[DrillRecord] = []
        total = ZERO
        for batch in sorted(self.batches, key=lambda b: b.batch_id):
            if batch.kind != "crm":
                continue
            for opp in batch.opportunities:
                total += D(opp.amount)
                records.append(DrillRecord(
                    batch_id=batch.batch_id,
                    batch_version=batch.version,
                    name=opp.name, stage=opp.stage,
                    amount=money(D(opp.amount)),
                    currency=self.pack_def.reporting_currency,
                ))
        return DrillNode(
            metric_id=metric.metric_id, label=metric.label,
            kind="base", currency=self.pack_def.reporting_currency,
            value=money(q(total)), records=records,
            note="the CRM extract's records, summed as stated — "
                 "a pipeline figure stands on records, not "
                 "journal lines",
        )

    # -- derived figures ----------------------------------------------

    def converted_node(self, metric: MetricDefinition) -> DrillNode:
        derived = metric.derived
        assert derived is not None and derived.of is not None
        base = self.pack_def.metric(derived.of)
        if base.derived is not None or base.scope != "entity" \
                or base.source != "gl":
            raise DrillError(
                f"figure {metric.metric_id} converts "
                f"{derived.of!r}, which is not an entity GL base "
                "metric — the close produces no such figure, so "
                "there is no honest drill for it"
            )
        children: list[DrillNode] = []
        total = ZERO
        for entity_id in self.pack_def.entity_ids():
            child = self.base_node(base, entity_id)
            currency = self.currencies[entity_id]
            rate_text = (
                "1" if currency == self.rates.reporting_currency
                else self.rates.rates.get(currency)
            )
            converted = self.rates.convert(D(child.value), currency)
            child.pre_conversion_value = child.value
            child.pre_conversion_currency = currency
            child.rate = rate_text
            child.value = money(converted)
            child.currency = self.pack_def.reporting_currency
            child.note += (
                f"; the entity subtotal converts once, at the "
                f"stamped rate ({currency} {rate_text}), into "
                f"{self.pack_def.reporting_currency} — lines are "
                "stated in entity currency and are not converted "
                "individually, because the close never converts "
                "them individually"
            )
            total += converted
            children.append(child)
        return DrillNode(
            metric_id=metric.metric_id, label=metric.label,
            kind="sum_converted",
            currency=self.pack_def.reporting_currency,
            value=money(q(total)), children=children,
            note=f"sum of {derived.of} per entity, each entity "
                 "subtotal converted once at the stamped rate "
                 "table",
        )

    def elimination_node(self, metric: MetricDefinition) -> DrillNode:
        derived = metric.derived
        assert derived is not None and derived.elimination_id is not None
        elim = next(
            e for e in self.pack_def.eliminations
            if e.elimination_id == derived.elimination_id
        )
        legs: list[DrillNode] = []
        for side, account, label in (
            ("revenue", elim.revenue_account, "revenue leg"),
            ("cost", elim.cost_account, "cost leg"),
        ):
            leg_children: list[DrillNode] = []
            leg_total = ZERO
            for entity_id in self.pack_def.entity_ids():
                currency = self.currencies[entity_id]
                lines: list[DrillLine] = []
                subtotal = ZERO
                for line in self.lines.get(entity_id, []):
                    if line.account != account \
                            or not line.ic_counterparty:
                        continue
                    amount = line.credit if side == "revenue" \
                        else line.debit
                    subtotal += amount
                    lines.append(DrillLine(
                        entity_id=line.entity_id,
                        batch_id=line.batch_id,
                        batch_version=line.batch_version,
                        journal_id=line.journal_id,
                        journal_date=line.journal_date,
                        line_index=line.line_index,
                        account=line.account,
                        debit=money(line.debit),
                        credit=money(line.credit),
                        ic_counterparty=line.ic_counterparty,
                        memo=line.memo,
                        amount=money(amount),
                        currency=currency,
                    ))
                if not lines:
                    continue
                rate_text = (
                    "1" if currency == self.rates.reporting_currency
                    else self.rates.rates.get(currency)
                )
                converted = self.rates.convert(q(subtotal), currency)
                leg_children.append(DrillNode(
                    metric_id=metric.metric_id, label=elim.label,
                    entity_id=entity_id, kind="base",
                    currency=self.pack_def.reporting_currency,
                    value=money(converted), lines=lines,
                    rate=rate_text,
                    pre_conversion_value=money(q(subtotal)),
                    pre_conversion_currency=currency,
                    note="intercompany-flagged lines only; the "
                         "entity subtotal converts once at the "
                         "stamped rate",
                ))
                leg_total += converted
            legs.append(DrillNode(
                metric_id=metric.metric_id,
                label=f"{elim.label} — {label}",
                kind="leg",
                currency=self.pack_def.reporting_currency,
                value=money(q(leg_total)), children=leg_children,
                note=f"account {account}, "
                     f"{'credits' if side == 'revenue' else 'debits'} "
                     "on intercompany-flagged lines, converted per "
                     "entity at the stamped rate",
            ))
        matched = min(D(legs[0].value), D(legs[1].value))
        return DrillNode(
            metric_id=metric.metric_id, label=metric.label,
            kind="elimination",
            currency=self.pack_def.reporting_currency,
            value=money(q(matched)), children=legs,
            note="the matched amount: the lesser of the two "
                 "converted legs. An excess on either leg "
                 "eliminates nothing — the verifier names it "
                 "UNMATCHED_IC_LEG, and the pair check names "
                 "which entities disagree",
        )

    def node_for(self, metric: MetricDefinition,
                 entity_id: str | None) -> DrillNode:
        if metric.derived is None:
            if metric.scope == "entity" and metric.source == "gl" \
                    and entity_id is not None:
                return self.base_node(metric, entity_id)
            if metric.scope == "group" and metric.source == "crm":
                return self.crm_node(metric)
            raise DrillError(
                f"figure {metric.metric_id} is a base metric of "
                f"shape scope={metric.scope!r} source="
                f"{metric.source!r}, which the close does not "
                "produce figures for — there is no drill to serve"
            )
        derived = metric.derived
        if entity_id is not None:
            raise DrillError(
                f"figure {metric.metric_id} is derived and "
                "consolidated; it carries no per-entity drill — "
                "drill it without an entity"
            )
        if derived.op == "sum_converted":
            return self.converted_node(metric)
        if derived.op == "elimination":
            return self.elimination_node(metric)
        if derived.op in ("add", "subtract"):
            children: list[DrillNode] = []
            total = ZERO
            for index, arg in enumerate(derived.args):
                child = self.node_for(self.pack_def.metric(arg), None)
                if derived.op == "subtract" and index > 0:
                    child.sign = -1
                total += child.sign * D(child.value)
                children.append(child)
            return DrillNode(
                metric_id=metric.metric_id, label=metric.label,
                kind=derived.op,
                currency=self.pack_def.reporting_currency,
                value=money(q(total)), children=children,
                note="a composition of other figures — the "
                     "operands' own drills, "
                     + ("added" if derived.op == "add"
                        else "the first less the rest")
                     + "; this figure stands on no lines of its own",
            )
        if derived.op == "vs_plan":
            assert derived.of is not None
            operand = self.node_for(self.pack_def.metric(derived.of),
                                    None)
            plan_amount = D(self.pack_def.plan.get(derived.of, "0"))
            plan_node = DrillNode(
                metric_id=derived.of,
                label=f"plan for {derived.of}",
                kind="plan",
                currency=self.pack_def.reporting_currency,
                value=money(-plan_amount),
                note="the plan baseline from the definition pack "
                     f"(v{self.pack_def.version}) — authored "
                     "data, shown as a composition line because "
                     "the figure stands on it; it is not a "
                     "source line and no source line is claimed "
                     "for it",
            )
            return DrillNode(
                metric_id=metric.metric_id, label=metric.label,
                kind="vs_plan",
                currency=self.pack_def.reporting_currency,
                value=money(q(D(operand.value) - plan_amount)),
                children=[operand, plan_node],
                note=f"{derived.of} less its plan baseline",
            )
        raise DrillError(
            f"figure {metric.metric_id} derives by op "
            f"{derived.op!r}, which the drill does not cover"
        )


def _line_count(node: DrillNode) -> int:
    return (
        len(node.lines) + len(node.records)
        + sum(_line_count(child) for child in node.children)
    )


def build_drill(store, pack: BoardPack, definitions: DefinitionPack,
                metric_id: str, entity_id: str | None) -> FigureDrill:
    """Re-perform one figure on a pack from its stamped
    sources, or refuse — by name — to serve a drill that
    would not be true."""
    figure = next(
        (f for f in pack.figures
         if f.metric_id == metric_id and f.entity_id == entity_id),
        None,
    )
    if figure is None:
        where = f"{metric_id} for {entity_id}" if entity_id \
            else metric_id
        raise DrillNotFound(
            f"pack {pack.pack_id} carries no figure {where} — "
            "a drill opens a figure on the pack, by its own "
            "identity"
        )
    try:
        metric = definitions.metric(metric_id)
    except StopIteration:
        raise DrillError(
            f"figure {metric_id} on pack {pack.pack_id} has no "
            f"definition entry in {definitions.pack_id} "
            f"v{definitions.version} — the rule that produced "
            "it cannot be reproduced, so no drill is served"
        ) from None
    batches = _stamped_batches(store, pack)

    # Conversions stand on the pack's stamp: the table the
    # figures carry, never a later table from the batch set.
    # A pack stamped before tables rode the stamp falls back
    # to its stamped FX batch's table — the verifier's own
    # fallback — and the drill says which basis it used.
    stamp = pack.source_versions.fx_table
    if stamp is not None:
        rates = stamp
        fx_basis = (
            f"the rate table stamped on the pack (v{stamp.version})"
        )
    else:
        fx_batch = next((b for b in batches if b.kind == "fx"), None)
        if fx_batch is not None and fx_batch.rate_table is not None:
            rates = fx_batch.rate_table
            fx_basis = (
                "the stamped FX batch's table (the pack predates "
                "rate stamping)"
            )
        else:
            rates = RateTable(
                version=0,
                reporting_currency=definitions.reporting_currency)
            fx_basis = "no rate table on the pack or its sources"

    driller = _Driller(definitions, batches, rates)
    root = driller.node_for(metric, entity_id)
    count = _line_count(root)
    drill = FigureDrill(
        pack_id=pack.pack_id, period=pack.period,
        pack_status=pack.status,
        metric_id=metric_id, entity_id=entity_id,
        label=figure.label, figure_value=figure.value,
        currency=figure.currency, composed_total=root.value,
        line_count=count,
        definition_pack_version=definitions.version,
        fx_version=rates.version, fx_basis=fx_basis,
        root=root,
    )
    if D(drill.composed_total) != D(figure.value):
        where = f"{metric_id} for {entity_id}" if entity_id \
            else metric_id
        raise DrillMismatch(
            f"DRILL_MISMATCH: figure {where} on pack "
            f"{pack.pack_id}: the lines in the pack's stamped "
            f"sources compose to {drill.composed_total} "
            f"{figure.currency}, but the pack records "
            f"{figure.value} — the drill refuses to present a "
            "composition that does not foot to the figure. A "
            "source record has moved under the pack's stamps, "
            "or the figure was not produced from them",
            composed_total=drill.composed_total,
            figure_value=figure.value,
            line_count=count,
        )
    return drill


def drill_digest(drill: FigureDrill) -> str:
    """The digest the evidence bundle cites for a drill:
    sha256 over the drill's canonical bytes — the bundle's
    own canonical form. A drill is a pure function of its
    inputs, so the digest is stable: re-perform the drill
    anywhere and it either reproduces this digest or
    something moved."""
    payload = (
        json.dumps(drill.model_dump(), indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_text(drill: FigureDrill) -> str:
    """A readable rendering of one drill — the composition
    tree with its lines, generated from the drill itself."""
    scope = drill.entity_id or drill.root.kind
    lines = [
        f"DRILL {drill.metric_id} · {scope} — {drill.label}",
        f"Pack {drill.pack_id} · period {drill.period} · status "
        f"{drill.pack_status} · definition pack "
        f"v{drill.definition_pack_version} · rates: "
        f"{drill.fx_basis}",
        f"Figure {drill.currency} {drill.figure_value} · "
        f"composed {drill.composed_total} · "
        f"{drill.line_count} source line(s)/record(s)",
        "",
    ]
    _render_node(drill.root, lines, 0)
    return "\n".join(lines) + "\n"


def _signed(value: str, sign: int) -> str:
    return f"-{value}" if sign < 0 and not value.startswith("-") \
        else value


def _render_node(node: DrillNode, out: list[str], depth: int) -> None:
    pad = "  " * depth
    scope = node.entity_id or node.kind
    header = (
        f"{pad}{node.metric_id} · {scope} · {node.currency} "
        f"{_signed(node.value, node.sign)}"
    )
    if node.pre_conversion_value is not None:
        header += (
            f" (from {node.pre_conversion_currency} "
            f"{node.pre_conversion_value} at rate {node.rate})"
        )
    out.append(header)
    if node.note:
        out.append(f"{pad}  {node.note}")
    for line in node.lines:
        out.append(
            f"{pad}  {line.batch_id} (v{line.batch_version}) · "
            f"{line.journal_id} · line {line.line_index} · "
            f"account {line.account} · debit {line.debit} · "
            f"credit {line.credit} · contributes "
            f"{line.currency} {line.amount}"
            + (f" · ic → {line.ic_counterparty}"
               if line.ic_counterparty else "")
        )
    for record in node.records:
        out.append(
            f"{pad}  {record.batch_id} (v{record.batch_version}) "
            f"· {record.name} · {record.currency} "
            f"{record.amount}"
        )
    for child in node.children:
        _render_node(child, out, depth + 1)
