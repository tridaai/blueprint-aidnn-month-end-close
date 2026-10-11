"""The independent verifier: every figure, recomputed from source.

The engine proposes; this module disposes. It is deliberately a
*separate implementation* of the definition pack's semantics:

- it reads **source batches directly** — never the marts the
  engine read, so a mart-construction bug cannot hide;
- it shares with the engine exactly one thing: the versioned
  definition pack (the *policy* — what revenue means here). Two
  implementations, one policy, is what makes agreement evidence;
- its data-quality scan is its own: duplicate journal ids, sub-
  ledger tie-outs, and intercompany leg pairing are checked here
  from raw records, not inherited from the mart builder's flags.

A figure the verifier cannot reproduce blocks the pack — a named
variance, never a silent pass. And honesty about limits: figures
that foot to a *wrong* source (a revenue entry posted to the
wrong account) recompute cleanly here; what catches those is the
tie-out family — independent subledger totals the GL must agree
with. The eval pack plants one of each, and the README says
which net catches which fish.

The module also carries the comparative check
(:func:`verify_comparatives`), whose source is not the batches
at all but the prior period's **signed pack record**: a
comparative must cite the signed figure exactly, because the
signed record — not a recompute over possibly-restated sources —
is what the board approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import policy
from .definitions import DefinitionPack, MetricDefinition
from .fx import D, ZERO, RateTable, money, q
from .schemas import (
    BoardPack,
    Figure,
    FigureComparative,
    FluxSchedule,
    SourceBatch,
    Variance,
)


@dataclass
class FigureCheck:
    metric_id: str
    entity_id: str | None
    engine_value: str | None
    verifier_value: str
    ok: bool


@dataclass
class VerificationReport:
    checks: list[FigureCheck] = field(default_factory=list)
    variances: list[Variance] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.variances and all(c.ok for c in self.checks)


@dataclass
class _RawLine:
    entity_id: str
    journal_id: str
    account: str
    debit: Decimal
    credit: Decimal
    ic_counterparty: str | None


def _entity_lines(batches: list[SourceBatch], pack: DefinitionPack,
                  variances: list[Variance]) -> dict[str, list[_RawLine]]:
    """Flatten the current GL batches into raw lines, applying
    the pack's data-quality rules on the verifier's own scan:
    a repeated journal id is named as a variance and its later
    copies excluded from recomputation (the first copy stands,
    exactly as the pack's rule states)."""
    per_entity: dict[str, list[_RawLine]] = {}
    for batch in sorted(batches, key=lambda b: b.batch_id):
        if batch.kind != "gl" or not batch.entity_id:
            continue
        lines = per_entity.setdefault(batch.entity_id, [])
        seen: dict[str, int] = {}
        for journal in batch.journals:
            seen[journal.journal_id] = seen.get(journal.journal_id, 0) + 1
            if pack.unique_journal_ids and seen[journal.journal_id] > 1:
                continue  # later copies never reach the recomputation
            for line in journal.lines:
                lines.append(_RawLine(
                    entity_id=batch.entity_id,
                    journal_id=journal.journal_id,
                    account=line.account,
                    debit=q(D(line.debit)),
                    credit=q(D(line.credit)),
                    ic_counterparty=line.ic_counterparty,
                ))
        if pack.unique_journal_ids:
            for journal_id, count in seen.items():
                if count > 1:
                    variances.append(Variance(
                        code="DUPLICATE_JOURNAL",
                        entity_id=batch.entity_id,
                        detail=(
                            f"journal {journal_id} appears {count} times in "
                            f"{batch.entity_id}'s GL extract ({batch.batch_id}); "
                            "the pack's rule makes a journal id unique per "
                            "entity, so the later copies are void — the pack "
                            "cannot pass until a corrected extract replaces it"
                        ),
                    ))
    return per_entity


def _sum(lines: list[_RawLine], metric: MetricDefinition) -> Decimal:
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


def _legs(lines_by_entity: dict[str, list[_RawLine]], account: str,
          side: str) -> dict[str, Decimal]:
    per_entity: dict[str, Decimal] = {}
    for entity_id, lines in lines_by_entity.items():
        for line in lines:
            if line.account == account and line.ic_counterparty:
                amount = line.credit if side == "credit" else line.debit
                per_entity[entity_id] = per_entity.get(entity_id, ZERO) + amount
    return per_entity


def verify(pack: DefinitionPack, batches: list[SourceBatch],
           engine_figures: list[Figure]) -> VerificationReport:
    """Recompute the pack's figures from source and compare.

    ``batches`` is the run's current set (one per slot). Returns
    the full report: a check per figure, and every variance the
    recomputation produced."""
    report = VerificationReport()
    variances = report.variances
    currencies = {e["entity_id"]: e["currency"] for e in pack.entities}
    entity_ids = pack.entity_ids()

    fx_batch = next((b for b in batches if b.kind == "fx"), None)
    rates: RateTable = fx_batch.rate_table if fx_batch and fx_batch.rate_table \
        else RateTable(version=0, reporting_currency=pack.reporting_currency)

    lines_by_entity = _entity_lines(batches, pack, variances)

    # --- eliminations: the legs must pair -------------------------
    matched_by_elim: dict[str, Decimal] = {}
    for elim in pack.eliminations:
        revenue = ZERO
        for entity_id, amount in _legs(lines_by_entity, elim.revenue_account,
                                       "credit").items():
            revenue += rates.convert(amount, currencies[entity_id])
        cost = ZERO
        for entity_id, amount in _legs(lines_by_entity, elim.cost_account,
                                       "debit").items():
            cost += rates.convert(amount, currencies[entity_id])
        revenue, cost = q(revenue), q(cost)
        matched_by_elim[elim.elimination_id] = min(revenue, cost)
        if revenue != cost:
            gap = abs(revenue - cost)
            variances.append(Variance(
                code="UNMATCHED_IC_LEG",
                detail=(
                    f"elimination {elim.elimination_id!r}: intercompany legs do "
                    f"not pair — revenue legs total {money(revenue)} "
                    f"{pack.reporting_currency} after conversion, cost legs "
                    f"total {money(cost)}; {money(gap)} has no counterpart "
                    "leg, so it cannot eliminate"
                ),
            ))

    # --- tie-outs: subledger vs GL ----------------------------------
    ar_by_entity = {
        billing.entity_id: billing
        for batch in batches if batch.kind == "ar"
        for billing in batch.ar_billings
    }
    for tie in pack.tie_outs:
        probe = MetricDefinition(
            metric_id=f"tie:{tie.tie_out_id}", label=tie.label, scope="entity",
            source="gl", measure="credit_minus_debit",
            accounts=tie.gl_accounts,
        )
        for entity_id in entity_ids:
            billing = ar_by_entity.get(entity_id)
            if billing is None:
                continue
            gl_total = _sum(lines_by_entity.get(entity_id, []), probe)
            if gl_total != q(D(billing.billings)):
                variances.append(Variance(
                    code="SUBLEDGER_TIE_OUT",
                    entity_id=entity_id,
                    detail=(
                        f"tie-out {tie.tie_out_id!r} fails for {entity_id}: "
                        f"the AR subledger reports billings of "
                        f"{money(D(billing.billings))} {billing.currency} but "
                        f"GL revenue accounts hold {money(gl_total)} — a gap "
                        f"of {money(abs(gl_total - D(billing.billings)))} that "
                        "is posted somewhere it does not belong, or not "
                        "posted at all"
                    ),
                ))

    # --- recompute every figure --------------------------------------
    values: dict[tuple[str, str | None], Decimal] = {}
    for metric in pack.metrics:
        if metric.derived is not None:
            continue
        if metric.scope == "entity":
            for entity_id in entity_ids:
                values[(metric.metric_id, entity_id)] = _sum(
                    lines_by_entity.get(entity_id, []), metric
                )
        elif metric.scope == "group" and metric.source == "crm":
            total = ZERO
            for batch in batches:
                if batch.kind == "crm":
                    for opp in batch.opportunities:
                        total += D(opp.amount)
            values[(metric.metric_id, None)] = q(total)

    pending = [m for m in pack.metrics if m.derived is not None]
    while pending:
        progressed = False
        for metric in list(pending):
            derived = metric.derived
            assert derived is not None
            if derived.op == "sum_converted":
                if not all((derived.of, e) in values for e in entity_ids):
                    continue
                total = ZERO
                for entity_id in entity_ids:
                    total += rates.convert(values[(derived.of, entity_id)],
                                           currencies[entity_id])
                values[(metric.metric_id, None)] = q(total)
            elif derived.op in ("add", "subtract"):
                if not all((a, None) in values for a in derived.args):
                    continue
                total = values[(derived.args[0], None)]
                for arg in derived.args[1:]:
                    total = total + values[(arg, None)] if derived.op == "add" \
                        else total - values[(arg, None)]
                values[(metric.metric_id, None)] = q(total)
            elif derived.op == "vs_plan":
                if (derived.of, None) not in values:
                    continue
                values[(metric.metric_id, None)] = q(
                    values[(derived.of, None)] - D(pack.plan.get(derived.of, "0"))
                )
            elif derived.op == "elimination":
                values[(metric.metric_id, None)] = matched_by_elim[
                    derived.elimination_id or ""
                ]
            pending.remove(metric)
            progressed = True
        if not progressed:
            raise ValueError("definition pack has an unresolvable derived metric")

    # --- compare ------------------------------------------------------
    engine_by_key = {
        (f.metric_id, f.entity_id): f for f in engine_figures
    }
    for metric in pack.metrics:
        keys = [(metric.metric_id, e) for e in entity_ids] \
            if metric.scope == "entity" else [(metric.metric_id, None)]
        for key in keys:
            verifier_value = values.get(key)
            if verifier_value is None:
                continue
            engine_figure = engine_by_key.pop(key, None)
            engine_value = engine_figure.value if engine_figure else None
            ok = engine_value is not None and D(engine_value) == verifier_value
            report.checks.append(FigureCheck(
                metric_id=key[0], entity_id=key[1],
                engine_value=engine_value,
                verifier_value=money(verifier_value), ok=ok,
            ))
            if not ok:
                where = f" for {key[1]}" if key[1] else ""
                if engine_value is None:
                    detail = (f"the engine returned no figure for "
                              f"{key[0]}{where}; the verifier recomputes "
                              f"{money(verifier_value)} from source")
                else:
                    detail = (f"figure {key[0]}{where}: the engine proposes "
                              f"{engine_value} but the verifier recomputes "
                              f"{money(verifier_value)} from source")
                variances.append(Variance(
                    code="FIGURE_MISMATCH", metric_id=key[0],
                    entity_id=key[1], detail=detail,
                ))
    for (metric_id, entity_id) in engine_by_key:
        variances.append(Variance(
            code="FIGURE_MISMATCH", metric_id=metric_id, entity_id=entity_id,
            detail=f"the engine returned a figure for {metric_id} that the "
                   "definition pack does not define",
        ))
    return report


# -- the flux check ---------------------------------------------------
#
# The flux schedule is a *claim*: that this decomposition of
# each movement is the decomposition the sources produce. The
# check below is a second implementation of the decomposition,
# written against this module's own figure machinery (never
# imported from the schedule's producer), and it compares the
# two line for line. It also checks the schedule against facts
# neither implementation computes: the entries must cover
# exactly the pack's comparatives, each movement must equal
# its comparative's change, each prior value must equal the
# signed figure the comparative cites, and each decomposition
# must foot to its own movement. A schedule that disagrees
# with the sources — or with itself — is a FLUX_MISMATCH and
# blocks the pack like any other variance.


class _FluxPeriod:
    """One period as the flux check reads it: raw lines per
    entity (this module's own flattening), the rate table, the
    CRM total."""

    def __init__(self, pack_def: DefinitionPack,
                 batches: list[SourceBatch]) -> None:
        self.pack_def = pack_def
        self.lines = _entity_lines(batches, pack_def, [])
        fx_batch = next((b for b in batches if b.kind == "fx"), None)
        self.rates: RateTable = (
            fx_batch.rate_table if fx_batch and fx_batch.rate_table
            else RateTable(version=0,
                           reporting_currency=pack_def.reporting_currency)
        )
        self.currencies = {e["entity_id"]: e["currency"]
                           for e in pack_def.entities}
        self.crm_total = ZERO
        for batch in batches:
            if batch.kind == "crm":
                for opp in batch.opportunities:
                    self.crm_total += D(opp.amount)
        self.crm_total = q(self.crm_total)

    def base(self, metric: MetricDefinition, entity_id: str) -> Decimal:
        return _sum(self.lines.get(entity_id, []), metric)

    def base_account(self, metric: MetricDefinition, entity_id: str,
                     account: str) -> Decimal:
        probe = MetricDefinition(
            metric_id=metric.metric_id, label=metric.label,
            scope=metric.scope, source=metric.source,
            measure=metric.measure, accounts=[account],
            exclude_ic=metric.exclude_ic,
        )
        return _sum(self.lines.get(entity_id, []), probe)

    def matched(self, elimination_id: str) -> Decimal:
        elim = next(e for e in self.pack_def.eliminations
                    if e.elimination_id == elimination_id)
        revenue = cost = ZERO
        for entity_id, amount in _legs(self.lines, elim.revenue_account,
                                       "credit").items():
            revenue += self.rates.convert(amount, self.currencies[entity_id])
        for entity_id, amount in _legs(self.lines, elim.cost_account,
                                       "debit").items():
            cost += self.rates.convert(amount, self.currencies[entity_id])
        return min(q(revenue), q(cost))

    def value(self, metric_id: str, entity_id: str | None) -> Decimal:
        metric = self.pack_def.metric(metric_id)
        if metric.derived is None:
            if metric.source == "crm":
                return self.crm_total
            return self.base(metric, entity_id or "")
        derived = metric.derived
        assert derived is not None
        if derived.op == "sum_converted":
            base = self.pack_def.metric(derived.of or "")
            total = ZERO
            for entity in self.pack_def.entity_ids():
                total += self.rates.convert(self.base(base, entity),
                                            self.currencies[entity])
            return q(total)
        if derived.op in ("add", "subtract"):
            total = self.value(derived.args[0], None)
            for arg in derived.args[1:]:
                value = self.value(arg, None)
                total = total + value if derived.op == "add" \
                    else total - value
            return q(total)
        if derived.op == "vs_plan":
            return q(self.value(derived.of or "", None)
                     - D(self.pack_def.plan.get(derived.of or "", "0")))
        if derived.op == "elimination":
            return self.matched(derived.elimination_id or "")
        raise ValueError(f"unknown derived op {derived.op!r}")

    def entity_shape(self, metric_id: str, entity_id: str | None,
                     ) -> list[tuple[str, str, Decimal]]:
        metric = self.pack_def.metric(metric_id)
        if entity_id is not None:
            return [(entity_id, "entity", self.value(metric_id, entity_id))]
        if metric.derived is None:
            return [("", "group", self.value(metric_id, None))]
        derived = metric.derived
        assert derived is not None
        if derived.op == "sum_converted":
            base = self.pack_def.metric(derived.of or "")
            return [
                (entity, "entity",
                 self.rates.convert(self.base(base, entity),
                                    self.currencies[entity]))
                for entity in self.pack_def.entity_ids()
            ]
        if derived.op in ("add", "subtract"):
            merged: dict[str, tuple[str, Decimal]] = {}
            order: list[str] = []
            for index, arg in enumerate(derived.args):
                sign = Decimal(1) if index == 0 or derived.op == "add" \
                    else Decimal(-1)
                for key, kind, amount in self.entity_shape(arg, None):
                    if key not in merged:
                        merged[key] = (kind, ZERO)
                        order.append(key)
                    kind0, total = merged[key]
                    merged[key] = (kind0, total + sign * amount)
            return [(key, merged[key][0], q(merged[key][1])) for key in order]
        if derived.op == "vs_plan":
            return self.entity_shape(derived.of or "", None) + [
                ("", "plan",
                 -D(self.pack_def.plan.get(derived.of or "", "0")))]
        if derived.op == "elimination":
            return [("", "group", self.value(metric_id, None))]
        raise ValueError(f"unknown derived op {derived.op!r}")

    def account_shape(self, metric_id: str, entity_id: str | None,
                      ) -> list[tuple[str, str, Decimal]] | None:
        metric = self.pack_def.metric(metric_id)
        if metric.derived is None:
            if metric.source != "gl" or entity_id is None:
                return None
            return [
                (account, "account",
                 self.base_account(metric, entity_id, account))
                for account in metric.accounts
            ]
        derived = metric.derived
        assert derived is not None
        if derived.op == "sum_converted":
            base = self.pack_def.metric(derived.of or "")
            return [
                (account, "account", q(sum(
                    (self.rates.convert(
                        self.base_account(base, entity, account),
                        self.currencies[entity])
                     for entity in self.pack_def.entity_ids()),
                    ZERO,
                )))
                for account in base.accounts
            ]
        if derived.op in ("add", "subtract"):
            merged: dict[str, tuple[str, Decimal]] = {}
            order: list[str] = []
            for index, arg in enumerate(derived.args):
                shape = self.account_shape(arg, None)
                if shape is None:
                    return None
                sign = Decimal(1) if index == 0 or derived.op == "add" \
                    else Decimal(-1)
                for key, kind, amount in shape:
                    if key not in merged:
                        merged[key] = (kind, ZERO)
                        order.append(key)
                    kind0, total = merged[key]
                    merged[key] = (kind0, total + sign * amount)
            return [(key, merged[key][0], q(merged[key][1])) for key in order]
        if derived.op == "vs_plan":
            shape = self.account_shape(derived.of or "", None)
            if shape is None:
                return None
            return shape + [
                ("", "plan",
                 -D(self.pack_def.plan.get(derived.of or "", "0")))]
        return None


def _flux_movement(current: list[tuple[str, str, Decimal]],
                   prior: list[tuple[str, str, Decimal]],
                   movement: Decimal) -> list[tuple[str, str, str]]:
    """current − prior per key, as comparable (key, kind,
    amount-string) lines, with the residue on a rounding line —
    the check's own assembly of what the schedule should say."""
    prior_by_key = {key: amount for key, _, amount in prior}
    lines: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for key, kind, amount in current:
        seen.add(key)
        lines.append((key, kind, money(q(amount - prior_by_key.get(
            key, ZERO)))))
    for key, kind, amount in prior:
        if key not in seen:
            lines.append((key, kind, money(q(-amount))))
    residue = q(movement - sum((D(amount) for _, _, amount in lines), ZERO))
    if residue != ZERO:
        lines.append(("rounding", "rounding", money(residue)))
    return sorted(lines)


def _schedule_lines(lines) -> list[tuple[str, str, str]]:
    return sorted((line.key, line.kind, line.amount) for line in lines)


def verify_flux(schedule: FluxSchedule,
                current_def: DefinitionPack,
                prior_def: DefinitionPack,
                current_batches: list[SourceBatch],
                prior_batches: list[SourceBatch],
                figures: list[Figure],
                comparatives: list[FigureComparative],
                ) -> list[Variance]:
    """Recompute the flux schedule from source and compare.

    The schedule under check was produced elsewhere; everything
    it claims is recomputed here from the two periods' batches
    under their own definition versions, and compared line for
    line. Returns FLUX_MISMATCH variances (empty = the schedule
    stands)."""
    variances: list[Variance] = []

    def fail(metric_id, entity_id, detail):
        variances.append(Variance(
            code="FLUX_MISMATCH", metric_id=metric_id,
            entity_id=entity_id, detail=detail))

    if schedule.threshold_abs != policy.FLUX_MATERIAL_ABS \
            or schedule.threshold_pct != policy.FLUX_MATERIAL_PCT:
        fail(None, None,
             "the flux schedule states materiality thresholds "
             f"({schedule.threshold_abs} / {schedule.threshold_pct}) "
             "that are not the policy's "
             f"({policy.FLUX_MATERIAL_ABS} / {policy.FLUX_MATERIAL_PCT})")

    current = _FluxPeriod(current_def, current_batches)
    prior = _FluxPeriod(prior_def, prior_batches)
    figure_by_key = {(f.metric_id, f.entity_id): f for f in figures}
    entries = {(e.metric_id, e.entity_id): e for e in schedule.entries}
    expected = {
        (c.metric_id, c.entity_id) for c in comparatives
        if c.change is not None
        and (c.metric_id, c.entity_id) in figure_by_key
    }
    for key in sorted(expected | set(entries), key=str):
        metric_id, entity_id = key
        where = f" for {entity_id}" if entity_id else ""
        entry = entries.get(key)
        comparative = next(
            (c for c in comparatives
             if (c.metric_id, c.entity_id) == key), None)
        if comparative is None:
            fail(metric_id, entity_id,
                 f"the flux schedule carries an entry for "
                 f"{metric_id}{where}, but the pack has no "
                 "comparative for it — flux explains comparatives, "
                 "it does not invent them")
            continue
        if entry is None:
            fail(metric_id, entity_id,
                 f"the flux schedule has no entry for {metric_id}{where}, "
                 "though the pack carries a comparative for it")
            continue
        figure = figure_by_key[key]
        current_value = current.value(metric_id, entity_id)
        prior_value = prior.value(metric_id, entity_id)
        if D(entry.current_value) != current_value \
                or D(entry.current_value) != D(figure.value):
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where} starts from current "
                 f"value {entry.current_value}, but the sources produce "
                 f"{money(current_value)} and the pack figure is "
                 f"{figure.value}")
        if D(entry.prior_value) != prior_value \
                or D(entry.prior_value) != D(comparative.prior_value):
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where} starts from prior "
                 f"value {entry.prior_value}, but the prior period's "
                 f"sources produce {money(prior_value)} and the "
                 f"comparative cites the signed {comparative.prior_value}")
        if D(entry.movement) != D(comparative.change or "0"):
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where} decomposes movement "
                 f"{entry.movement}, but the comparative's change is "
                 f"{comparative.change}")
        material = D(entry.movement) != ZERO and (
            abs(D(entry.movement)) >= D(schedule.threshold_abs)
            or (comparative.change_pct is not None
                and abs(D(comparative.change_pct))
                >= D(schedule.threshold_pct))
        )
        if entry.material != material:
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where} marks the movement "
                 f"{'material' if entry.material else 'immaterial'}, "
                 "but the schedule's own stated thresholds judge it "
                 f"{'material' if material else 'immaterial'}")
        if entry.definition_changed != comparative.definition_changed \
                or entry.restated != comparative.restated:
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where} carries flags that "
                 "disagree with its comparative")
        movement = D(comparative.change or "0")
        entity_lines = _flux_movement(
            current.entity_shape(metric_id, entity_id),
            prior.entity_shape(metric_id, entity_id), movement)
        if _schedule_lines(entry.by_entity) != entity_lines:
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where}: the by-entity "
                 "decomposition does not match the sources — the "
                 "schedule says "
                 f"{_schedule_lines(entry.by_entity)}, recomputation "
                 f"produces {entity_lines}")
        entity_sum = sum((D(line.amount) for line in entry.by_entity), ZERO)
        if q(entity_sum) != movement:
            fail(metric_id, entity_id,
                 f"flux for {metric_id}{where}: the by-entity lines "
                 f"sum to {money(entity_sum)}, not the movement "
                 f"{money(movement)} they claim to explain")
        account_current = current.account_shape(metric_id, entity_id)
        account_prior = prior.account_shape(metric_id, entity_id)
        if account_current is None or account_prior is None:
            if entry.by_account is not None:
                fail(metric_id, entity_id,
                     f"flux for {metric_id}{where} decomposes by "
                     "account, but the definition's shape allows no "
                     "account split for this figure")
        else:
            account_lines = _flux_movement(account_current, account_prior,
                                           movement)
            if entry.by_account is None:
                fail(metric_id, entity_id,
                     f"flux for {metric_id}{where} carries no "
                     "by-account decomposition, but the definition's "
                     "shape allows one and the sources produce it")
            elif _schedule_lines(entry.by_account) != account_lines:
                fail(metric_id, entity_id,
                     f"flux for {metric_id}{where}: the by-account "
                     "decomposition does not match the sources — "
                     f"the schedule says "
                     f"{_schedule_lines(entry.by_account)}, "
                     f"recomputation produces {account_lines}")
            elif q(sum((D(line.amount) for line in entry.by_account),
                       ZERO)) != movement:
                fail(metric_id, entity_id,
                     f"flux for {metric_id}{where}: the by-account "
                     "lines do not sum to the movement "
                     f"{money(movement)} they claim to explain")
    return variances


def verify_comparatives(comparatives: list[FigureComparative],
                        signed_pack: BoardPack) -> list[Variance]:
    """Check the comparative layer against the record it cites.

    A different discipline from :func:`verify`, deliberately: the
    figures under check here are not recomputed from source —
    last month's sources may have been restated since, and
    recomputing them would silently rewrite what the board
    approved. The check is citation-exactness: every comparative
    must equal, to the cent, the figure in the **signed pack
    record** it names. A comparative that cites a figure the
    signed pack does not hold, or holds at another value, is a
    ``COMPARATIVE_MISMATCH`` and blocks the pack: a board pack
    whose comparatives do not tie to the signed record is worse
    than one with no comparatives at all."""
    signed = {
        (f.metric_id, f.entity_id): f for f in signed_pack.figures
    }
    variances: list[Variance] = []
    for comp in comparatives:
        figure = signed.get((comp.metric_id, comp.entity_id))
        where = f" for {comp.entity_id}" if comp.entity_id else ""
        if figure is None:
            variances.append(Variance(
                code="COMPARATIVE_MISMATCH", metric_id=comp.metric_id,
                entity_id=comp.entity_id,
                detail=(
                    f"comparative for {comp.metric_id}{where} cites "
                    f"{signed_pack.pack_id}, but that signed pack holds "
                    "no such figure"
                ),
            ))
        elif D(figure.value) != D(comp.prior_value):
            variances.append(Variance(
                code="COMPARATIVE_MISMATCH", metric_id=comp.metric_id,
                entity_id=comp.entity_id,
                detail=(
                    f"comparative for {comp.metric_id}{where} shows "
                    f"{comp.prior_value} as the prior-period figure, but "
                    f"the signed pack {signed_pack.pack_id} records "
                    f"{figure.value} — comparatives cite the signed "
                    "record exactly, or they do not ship"
                ),
            ))
    return variances
