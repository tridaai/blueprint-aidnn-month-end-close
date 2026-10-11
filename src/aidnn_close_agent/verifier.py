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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .definitions import DefinitionPack, MetricDefinition
from .fx import D, ZERO, RateTable, money, q
from .schemas import Figure, SourceBatch, Variance


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
