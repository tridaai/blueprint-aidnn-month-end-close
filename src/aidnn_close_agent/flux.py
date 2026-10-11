"""Flux: every material movement in the pack explains itself.

A board pack's comparatives say *that* a figure moved. The
flux schedule says *why* — or, more precisely, *where*: for
every figure with a comparative, the movement is decomposed
two ways, by entity and (where the definition's shape allows)
by account, and each decomposition foots exactly to the
movement it explains.

The disciplines are the pack's own, extended one step:

- **Same sources, same versions.** Each side of a movement is
  computed from that period's source batches — the current
  run's batches on one side, the batches stamped on the prior
  period's *signed* pack on the other — under that period's
  own definition-pack version. That is the convention the
  restatement recomputation already uses, and it is what makes
  the decomposed movement the movement the board pack presents:
  current figure minus the signed figure. A restated prior
  period does not leak into the decomposition, because the
  movement is against the signed record, restatement or not.
- **A definition change is named, never smoothed.** When the
  two periods ran under different definition versions for a
  figure, the entry carries the comparative's
  ``definition_changed`` flag and says, in its note, that each
  side stands on its own period's definitions — the movement
  therefore includes the definition change (a widened account
  set shows up as its own account line) and is not separated
  into "definition" and "trading" parts. Separating them would
  mean computing one period under the other's rule and
  presenting the counterfactual as fact.
- **The decomposition foots, exactly.** Contributions are
  Decimal sums end to end. Where conversion makes the parts
  and the whole round differently (an account cell converted
  per entity, against a figure converted per entity total),
  the residue lands on a named ``rounding`` line — never
  absorbed into a driver, never dropped.
- **Materiality is stated on the schedule.** A movement
  reaching either bar in :mod:`.policy` is material; material
  entries carry their drivers ordered largest first, so the
  board's eye lands where the money moved. Immaterial entries
  are computed and verified identically, but listed plainly.

This module is the *producer* of the schedule. The verifier's
check (:func:`verifier.verify_flux`) is a separate
implementation over the same sources and policy — the schedule
ships only when the two agree, line for line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import policy
from .definitions import DefinitionPack, MetricDefinition
from .fx import D, ZERO, RateTable, money, q
from .schemas import (
    Figure,
    FigureComparative,
    FigureFlux,
    FluxContribution,
    FluxSchedule,
    SourceBatch,
)


# -- one period, flattened ----------------------------------------------


@dataclass
class _Line:
    account: str
    debit: Decimal
    credit: Decimal
    ic_counterparty: str | None


@dataclass
class _Period:
    """One period's sources, flattened for decomposition:
    raw GL lines per entity (the pack's duplicate-journal rule
    applied — first copy stands), and the period's rate table."""

    lines: dict[str, list[_Line]] = field(default_factory=dict)
    rates: RateTable = field(default_factory=lambda: RateTable(version=0))
    crm_total: Decimal = ZERO

    @classmethod
    def from_batches(cls, batches: list[SourceBatch],
                     pack_def: DefinitionPack) -> "_Period":
        period = cls()
        for batch in sorted(batches, key=lambda b: b.batch_id):
            if batch.kind == "fx" and batch.rate_table is not None:
                period.rates = batch.rate_table
            elif batch.kind == "crm":
                for opp in batch.opportunities:
                    period.crm_total += D(opp.amount)
            elif batch.kind == "gl" and batch.entity_id:
                lines = period.lines.setdefault(batch.entity_id, [])
                seen: set[str] = set()
                for journal in batch.journals:
                    if pack_def.unique_journal_ids \
                            and journal.journal_id in seen:
                        continue  # later copies never count, per the pack
                    seen.add(journal.journal_id)
                    for line in journal.lines:
                        lines.append(_Line(
                            account=line.account,
                            debit=q(D(line.debit)),
                            credit=q(D(line.credit)),
                            ic_counterparty=line.ic_counterparty,
                        ))
        period.crm_total = q(period.crm_total)
        return period


def _measure(lines: list[_Line], metric: MetricDefinition,
             entity_id: str) -> Decimal:
    """One base GL metric in one entity, entity currency."""
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


def _measure_account(lines: list[_Line], metric: MetricDefinition,
                     account: str) -> Decimal:
    """One account's share of a base GL metric in one entity."""
    total = ZERO
    for line in lines:
        if line.account != account:
            continue
        if metric.exclude_ic and line.ic_counterparty:
            continue
        if metric.measure == "credit_minus_debit":
            total += line.credit - line.debit
        elif metric.measure == "debit_minus_credit":
            total += line.debit - line.credit
    return q(total)


def _currencies(pack_def: DefinitionPack) -> dict[str, str]:
    return {e["entity_id"]: e["currency"] for e in pack_def.entities}


# -- values and contribution shapes, per period ---------------------------


def _elimination_matched(pack_def: DefinitionPack, period: _Period,
                         elimination_id: str) -> Decimal:
    """The matched intercompany amount, converted — the same
    pairing rule the pack states: both legs converted, the
    lesser is what eliminates."""
    elim = next(e for e in pack_def.eliminations
                if e.elimination_id == elimination_id)
    currencies = _currencies(pack_def)
    revenue = cost = ZERO
    for entity_id, lines in period.lines.items():
        # Legs are totalled per entity in entity currency and
        # converted once — the package's one conversion rule.
        rev_e = sum((line.credit for line in lines
                     if line.ic_counterparty
                     and line.account == elim.revenue_account), ZERO)
        cost_e = sum((line.debit for line in lines
                      if line.ic_counterparty
                      and line.account == elim.cost_account), ZERO)
        revenue += period.rates.convert(q(rev_e), currencies[entity_id])
        cost += period.rates.convert(q(cost_e), currencies[entity_id])
    return min(q(revenue), q(cost))


def _value(pack_def: DefinitionPack, period: _Period, metric_id: str,
           entity_id: str | None) -> Decimal:
    """The figure's value in one period, under that period's
    definitions — the decomposition's own evaluation, from the
    period's batches."""
    metric = pack_def.metric(metric_id)
    if metric.derived is None:
        if metric.source == "crm":
            return period.crm_total
        return _measure(period.lines.get(entity_id or "", []), metric,
                        entity_id or "")
    derived = metric.derived
    assert derived is not None
    if derived.op == "sum_converted":
        base = pack_def.metric(derived.of or "")
        currencies = _currencies(pack_def)
        total = ZERO
        for entity in pack_def.entity_ids():
            amount = _measure(period.lines.get(entity, []), base, entity)
            total += period.rates.convert(amount, currencies[entity])
        return q(total)
    if derived.op in ("add", "subtract"):
        total = _value(pack_def, period, derived.args[0], None)
        for arg in derived.args[1:]:
            value = _value(pack_def, period, arg, None)
            total = total + value if derived.op == "add" else total - value
        return q(total)
    if derived.op == "vs_plan":
        return q(_value(pack_def, period, derived.of or "", None)
                 - D(pack_def.plan.get(derived.of or "", "0")))
    if derived.op == "elimination":
        return _elimination_matched(pack_def, period,
                                    derived.elimination_id or "")
    raise ValueError(f"unknown derived op {derived.op!r}")


# A contribution shape: ordered (key, kind, label, amount) lines
# whose amounts sum to the figure's value in that period.
_Shape = list[tuple[str, str, str, Decimal]]


def _entity_shape(pack_def: DefinitionPack, period: _Period,
                  metric_id: str, entity_id: str | None) -> _Shape:
    """The figure's value split by entity (reporting currency
    for consolidated figures; the entity's own currency for an
    entity figure, whose split is itself)."""
    metric = pack_def.metric(metric_id)
    if entity_id is not None:
        return [(entity_id, "entity", entity_id,
                 _value(pack_def, period, metric_id, entity_id))]
    if metric.derived is None:
        # A group base figure (the CRM pipeline): no entity
        # split exists in its definition — one group line.
        return [("", "group",
                 "group total — the definition carries no entity split",
                 _value(pack_def, period, metric_id, None))]
    derived = metric.derived
    assert derived is not None
    if derived.op == "sum_converted":
        base = pack_def.metric(derived.of or "")
        currencies = _currencies(pack_def)
        return [
            (entity, "entity", entity,
             period.rates.convert(
                 _measure(period.lines.get(entity, []), base, entity),
                 currencies[entity]))
            for entity in pack_def.entity_ids()
        ]
    if derived.op in ("add", "subtract"):
        merged: dict[str, tuple[str, str, Decimal]] = {}
        order: list[str] = []
        for index, arg in enumerate(derived.args):
            sign = Decimal(1) if index == 0 or derived.op == "add" \
                else Decimal(-1)
            for key, kind, label, amount in _entity_shape(
                    pack_def, period, arg, None):
                if key not in merged:
                    merged[key] = (kind, label, ZERO)
                    order.append(key)
                kind0, label0, total = merged[key]
                merged[key] = (kind0, label0, total + sign * amount)
        return [(key, merged[key][0], merged[key][1], q(merged[key][2]))
                for key in order]
    if derived.op == "vs_plan":
        shape = _entity_shape(pack_def, period, derived.of or "", None)
        plan = D(pack_def.plan.get(derived.of or "", "0"))
        return shape + [("", "plan",
                         f"plan baseline ({derived.of})", -plan)]
    if derived.op == "elimination":
        return [("", "group",
                 "intercompany pairing — matched at group level, "
                 "not attributable to one entity",
                 _value(pack_def, period, metric_id, None))]
    raise ValueError(f"unknown derived op {derived.op!r}")


def _account_shape(pack_def: DefinitionPack, period: _Period,
                   metric_id: str, entity_id: str | None,
                   ) -> _Shape | None:
    """The figure's value split by account, or ``None`` where
    the definition's shape allows no account split."""
    metric = pack_def.metric(metric_id)
    if metric.derived is None:
        if metric.source != "gl":
            return None  # a CRM figure has no GL accounts
        if entity_id is not None:
            lines = period.lines.get(entity_id, [])
            return [
                (account, "account", f"account {account}",
                 _measure_account(lines, metric, account))
                for account in metric.accounts
            ]
        return None  # a group-scope GL base metric does not exist
    derived = metric.derived
    assert derived is not None
    if derived.op == "sum_converted":
        base = pack_def.metric(derived.of or "")
        currencies = _currencies(pack_def)
        return [
            (account, "account", f"account {account}", q(sum(
                (period.rates.convert(
                    _measure_account(period.lines.get(entity, []), base,
                                     account),
                    currencies[entity])
                 for entity in pack_def.entity_ids()),
                ZERO,
            )))
            for account in base.accounts
        ]
    if derived.op in ("add", "subtract"):
        merged: dict[str, tuple[str, str, Decimal]] = {}
        order: list[str] = []
        for index, arg in enumerate(derived.args):
            shape = _account_shape(pack_def, period, arg, None)
            if shape is None:
                return None
            sign = Decimal(1) if index == 0 or derived.op == "add" \
                else Decimal(-1)
            for key, kind, label, amount in shape:
                if key not in merged:
                    merged[key] = (kind, label, ZERO)
                    order.append(key)
                kind0, label0, total = merged[key]
                merged[key] = (kind0, label0, total + sign * amount)
        return [(key, merged[key][0], merged[key][1], q(merged[key][2]))
                for key in order]
    if derived.op == "vs_plan":
        shape = _account_shape(pack_def, period, derived.of or "", None)
        if shape is None:
            return None
        plan = D(pack_def.plan.get(derived.of or "", "0"))
        return shape + [("", "plan",
                         f"plan baseline ({derived.of})", -plan)]
    # An elimination is a pairing of two legs under a min() —
    # its movement is not a sum of account movements.
    return None


# -- movement assembly -----------------------------------------------------


def _movement_lines(current: _Shape, prior: _Shape, movement: Decimal,
                    *, material: bool) -> list[FluxContribution]:
    """current − prior, key by key; the residue, if conversion
    made the parts and the whole round apart, lands on a named
    rounding line so the lines foot to ``movement`` exactly."""
    prior_by_key = {key: amount for key, _, _, amount in prior}
    lines: list[FluxContribution] = []
    seen: set[str] = set()
    for key, kind, label, amount in current:
        seen.add(key)
        delta = q(amount - prior_by_key.get(key, ZERO))
        lines.append(FluxContribution(
            key=key, kind=kind, label=label, amount=money(delta)))
    for key, kind, label, amount in prior:
        if key in seen:
            continue
        lines.append(FluxContribution(
            key=key, kind=kind, label=label, amount=money(q(-amount))))
    residue = q(movement - sum((D(line.amount) for line in lines), ZERO))
    if residue != ZERO:
        lines.append(FluxContribution(
            key="rounding", kind="rounding",
            label="rounding — conversion of parts vs whole",
            amount=money(residue)))
    if material:
        drivers = [line for line in lines if line.kind != "rounding"]
        tail = [line for line in lines if line.kind == "rounding"]
        drivers.sort(key=lambda line: -abs(D(line.amount)))
        lines = drivers + tail
    return lines


def is_material(movement: Decimal, movement_pct: str | None) -> bool:
    """The policy ruler: either bar makes a movement material.
    A zero movement is never material, however the bars sit."""
    if movement == ZERO:
        return False
    if abs(movement) >= D(policy.FLUX_MATERIAL_ABS):
        return True
    return movement_pct is not None \
        and abs(D(movement_pct)) >= D(policy.FLUX_MATERIAL_PCT)


def _no_account_note(pack_def: DefinitionPack, metric_id: str) -> str:
    metric = pack_def.metric(metric_id)
    if metric.derived is not None and metric.derived.op == "elimination":
        return ("no account decomposition: an elimination is a "
                "matched pairing of two intercompany legs — its "
                "movement is not a sum of account movements")
    return ("no account decomposition: a group-scope figure with "
            "no GL accounts feeding it")


def build_schedule(current_def: DefinitionPack,
                   prior_def: DefinitionPack | None,
                   current_batches: list[SourceBatch],
                   prior_batches: list[SourceBatch] | None,
                   figures: list[Figure],
                   comparatives: list[FigureComparative],
                   *, prior_period: str = "", prior_pack_id: str = "",
                   ) -> FluxSchedule | None:
    """The flux schedule for a pack, or ``None`` when it cannot
    be computed honestly: the prior period's definition version
    is not on disk, or a batch the signed pack stamps is missing
    from the store. Absent — never fabricated."""
    if prior_def is None or prior_batches is None or not comparatives:
        return None
    current_data = _Period.from_batches(current_batches, current_def)
    prior_data = _Period.from_batches(prior_batches, prior_def)
    figure_by_key = {(f.metric_id, f.entity_id): f for f in figures}
    entries: list[FigureFlux] = []
    for comparative in comparatives:
        if comparative.change is None:
            continue  # currencies differ: no single-currency movement
        figure = figure_by_key.get(
            (comparative.metric_id, comparative.entity_id))
        if figure is None:
            continue
        movement = D(comparative.change)
        material = is_material(movement, comparative.change_pct)
        by_entity = _movement_lines(
            _entity_shape(current_def, current_data,
                          comparative.metric_id, comparative.entity_id),
            _entity_shape(prior_def, prior_data,
                          comparative.metric_id, comparative.entity_id),
            movement, material=material,
        )
        account_current = _account_shape(
            current_def, current_data,
            comparative.metric_id, comparative.entity_id)
        account_prior = _account_shape(
            prior_def, prior_data,
            comparative.metric_id, comparative.entity_id)
        if account_current is None or account_prior is None:
            by_account = None
            note = _no_account_note(current_def, comparative.metric_id)
        else:
            by_account = _movement_lines(
                account_current, account_prior, movement,
                material=material)
            note = ""
        if comparative.definition_changed:
            note = (note + " " if note else "") + (
                f"definition changed between the pack versions "
                f"(prior v{prior_def.version}, current "
                f"v{current_def.version}): each side is computed "
                "under its own period's definitions, so this "
                "movement includes the definition change — named "
                "here, not separated out")
        entries.append(FigureFlux(
            metric_id=comparative.metric_id,
            entity_id=comparative.entity_id,
            currency=figure.currency,
            current_value=figure.value,
            prior_value=comparative.prior_value,
            movement=money(movement),
            movement_pct=comparative.change_pct,
            material=material,
            definition_changed=comparative.definition_changed,
            restated=comparative.restated,
            basis=(f"prior period under definition pack "
                   f"v{prior_def.version}; current under "
                   f"v{current_def.version}"),
            by_entity=by_entity,
            by_account=by_account,
            note=note,
        ))
    if not entries:
        return None
    return FluxSchedule(
        prior_period=prior_period,
        prior_pack_id=prior_pack_id,
        current_definition_pack_version=current_def.version,
        prior_definition_pack_version=prior_def.version,
        threshold_abs=policy.FLUX_MATERIAL_ABS,
        threshold_pct=policy.FLUX_MATERIAL_PCT,
        entries=entries,
    )
