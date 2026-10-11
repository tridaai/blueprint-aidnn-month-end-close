"""Comparatives and restatement: the second month's discipline.

A first close proves a pack against its sources. Every close
after that is comparative — the board reads this month against
last month — and comparatives have their own failure modes,
which this module exists to keep named:

- **Comparatives cite the signed record.** The prior-period
  column is copied from the prior period's SIGNED pack — the
  figures the board approved — with the pack id and definition
  version cited per figure. It is never a fresh recompute over
  last month's sources: those sources may have been corrected
  since, and silently presenting the corrected number as "last
  month" rewrites history the board acted on.
- **A restatement is detected, named, and gated.** If batches
  received since sign-off supersede the ones the signed pack
  was built from, the prior period is recomputed under *its
  own* definition-pack version over the restated sources, and
  every signed figure that no longer reproduces is listed —
  signed value vs recomputed value — in a
  ``RESTATED_PRIOR_PERIOD`` variance. The signed pack is never
  altered. The new pack cannot be signed until a named
  controller acknowledges the restatement; the variance and the
  acknowledgement both stay on the pack record permanently.
- **Definition changes are flagged, not smoothed over.** When
  the new period runs under a newer definition-pack version, a
  comparative whose metric — or anything it derives from, or
  its plan baseline — was redefined is flagged
  ``DEFINITION_CHANGED`` with both versions named. Comparing
  across a silent definition change is how two honest numbers
  produce one dishonest column.

Preparation happens in the service at build time (it needs the
store: the signed pack, the received batches, the pack
registry); attachment happens in the pipeline's verify step,
where the new pack's figures exist. The comparative check
itself lives in :mod:`.verifier`, reading the signed pack
record — the one place in the system where the "source" is a
record, not an extract, and that is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import verifier as verifier_module
from .definitions import (
    DefinitionPack,
    bundled_pack_dir,
    load_definition_pack_version,
)
from .fx import D, money, q
from .schemas import (
    BoardPack,
    FigureComparative,
    RestatedFigure,
    RestatementReport,
    Variance,
)


def previous_period(period: str) -> str:
    """The calendar month before a ``YYYY-MM`` period."""
    year, _, month = period.partition("-")
    y, m = int(year), int(month)
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


def find_signed_pack(store, period: str) -> BoardPack | None:
    """The signed pack of record for a period, if one exists.

    Signed packs are history — a period has at most one that
    closed its run. If duplicates ever appeared, the latest by
    creation is the record (and the eval pack's byte-identity
    gate would have questions)."""
    candidates = [
        p for p in store.list_packs()
        if p.period == period and p.status == "SIGNED_OFF"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.created_at, p.pack_id))


def changed_metric_ids(old: DefinitionPack, new: DefinitionPack) -> set[str]:
    """Metrics whose meaning differs between two pack versions.

    A metric counts as changed when its own definition differs,
    when an elimination it reads was redefined, when a ``vs_plan``
    metric's plan baseline moved — or when anything it derives
    from (transitively) changed. Comparing a figure across any
    of those without naming it is the silent error this set
    exists to prevent."""
    old_by_id = {m.metric_id: m for m in old.metrics}
    new_by_id = {m.metric_id: m for m in new.metrics}
    changed: set[str] = set()
    for metric_id in old_by_id.keys() & new_by_id.keys():
        if old_by_id[metric_id].model_dump() != new_by_id[metric_id].model_dump():
            changed.add(metric_id)
    old_elims = {e.elimination_id: e for e in old.eliminations}
    new_elims = {e.elimination_id: e for e in new.eliminations}
    for metric_id, metric in new_by_id.items():
        derived = metric.derived
        if derived is None:
            continue
        if derived.op == "vs_plan" and derived.of:
            if old.plan.get(derived.of) != new.plan.get(derived.of):
                changed.add(metric_id)
        if derived.op == "elimination" and derived.elimination_id:
            before = old_elims.get(derived.elimination_id)
            after = new_elims.get(derived.elimination_id)
            if before is None or after is None \
                    or before.model_dump() != after.model_dump():
                changed.add(metric_id)
    # Transitive closure: a derived metric inherits the change of
    # anything it reads.
    progressed = True
    while progressed:
        progressed = False
        for metric_id, metric in new_by_id.items():
            if metric_id in changed or metric.derived is None:
                continue
            refs = list(metric.derived.args)
            if metric.derived.of:
                refs.append(metric.derived.of)
            if any(ref in changed for ref in refs):
                changed.add(metric_id)
                progressed = True
    return changed


@dataclass
class ComparativeContext:
    """Everything the verify step needs about the prior period,
    prepared by the service before the build runs."""

    prior_pack: BoardPack
    prior_pack_def: DefinitionPack | None  # None: version not on disk
    definition_changed: set[str] = field(default_factory=set)
    restatement: RestatementReport | None = None
    # The batches the signed pack was built from, exactly as
    # stamped on it — the flux schedule decomposes the prior
    # side from these, NOT from the store's current versions of
    # the period's slots: a restated batch supersedes in the
    # store, but the movement the board reads is against the
    # signed record, so the decomposition reads what the signed
    # record read. ``None`` when a stamped batch is missing from
    # the store (flux then degrades to absent, never guessed).
    prior_batches: list | None = None


def _detect_restatement(store, signed: BoardPack,
                        prior_def: DefinitionPack | None,
                        ) -> RestatementReport | None:
    """Has anything received since sign-off superseded the
    batches the signed pack was built from? If so, recompute
    the prior period under its own definitions over the
    restated sources and name every figure that moved."""
    stamped_ids = list(signed.source_versions.batches.keys())
    by_supersedes = {}
    for batch in store.list_batches():
        if batch.supersedes:
            by_supersedes[batch.supersedes] = batch
    swapped: dict[str, object] = {}
    restated_ids: list[str] = []
    for batch_id in stamped_ids:
        current = store.get_batch(batch_id)
        if current is None:
            continue
        terminal = current
        while terminal.batch_id in by_supersedes:
            nxt = by_supersedes[terminal.batch_id]
            if nxt.batch_id == terminal.batch_id:
                break
            terminal = nxt
            restated_ids.append(terminal.batch_id)
        swapped[batch_id] = terminal
    if not restated_ids:
        return None
    affected: list[RestatedFigure] = []
    if prior_def is not None:
        batches = [swapped[b] for b in stamped_ids if b in swapped]
        report = verifier_module.verify(prior_def, batches, signed.figures)
        signed_by_key = {
            (f.metric_id, f.entity_id): f for f in signed.figures
        }
        for check in report.checks:
            if check.ok:
                continue
            figure = signed_by_key.get((check.metric_id, check.entity_id))
            affected.append(RestatedFigure(
                metric_id=check.metric_id,
                entity_id=check.entity_id,
                signed_value=check.engine_value or "",
                recomputed_value=check.verifier_value,
                currency=figure.currency if figure else "",
            ))
    return RestatementReport(
        prior_period=signed.period,
        prior_pack_id=signed.pack_id,
        restated_batch_ids=sorted(set(restated_ids)),
        affected_figures=affected,
    )


def prepare_comparatives(store, current_pack: DefinitionPack, period: str,
                         pack_dirs: list[Path] | None = None,
                         ) -> ComparativeContext | None:
    """Assemble the prior-period context for a build, or ``None``
    when the prior period has no signed pack (a first close —
    comparatives simply do not exist yet)."""
    prior = find_signed_pack(store, previous_period(period))
    if prior is None:
        return None
    dirs = pack_dirs if pack_dirs is not None else [bundled_pack_dir()]
    prior_def = load_definition_pack_version(
        prior.definition_pack_id, prior.definition_pack_version, dirs
    )
    changed = (
        changed_metric_ids(prior_def, current_pack)
        if prior_def is not None else set()
    )
    prior_batches = []
    for batch_id in prior.source_versions.batches:
        batch = store.get_batch(batch_id)
        if batch is None:
            prior_batches = None
            break
        prior_batches.append(batch)
    return ComparativeContext(
        prior_pack=prior,
        prior_pack_def=prior_def,
        definition_changed=changed,
        restatement=_detect_restatement(store, prior, prior_def),
        prior_batches=prior_batches,
    )


def restatement_variance(report: RestatementReport) -> Variance:
    """The named variance a restatement raises on the new pack."""
    parts = []
    for figure in report.affected_figures:
        where = f" for {figure.entity_id}" if figure.entity_id else ""
        parts.append(
            f"{figure.metric_id}{where}: signed {figure.signed_value} "
            f"{figure.currency}, restated sources now produce "
            f"{figure.recomputed_value}"
        )
    detail = (
        f"the {report.prior_period} sources behind signed pack "
        f"{report.prior_pack_id} were restated after sign-off "
        f"({', '.join(report.restated_batch_ids)}); the signed pack "
        "stands as approved, and its comparatives still cite it — "
        "but these signed figures no longer reproduce from the "
        "restated sources: " + ("; ".join(parts) if parts else
                                 "(affected figures not recomputed: the "
                                 "prior definition-pack version is not on "
                                 "disk)")
        + ". A controller must acknowledge this restatement before "
          "this pack can be signed."
    )
    return Variance(code="RESTATED_PRIOR_PERIOD", detail=detail)


def attach_comparatives(pack: BoardPack, ctx: ComparativeContext,
                        ) -> list[Variance]:
    """Build the pack's comparative layer from its figures and
    the signed prior pack, and check it against the record it
    cites. Mutates ``pack``; returns any COMPARATIVE_MISMATCH
    variances (which block the pack like any other)."""
    signed = ctx.prior_pack
    signed_by_key = {(f.metric_id, f.entity_id): f for f in signed.figures}
    restated_keys = set()
    if ctx.restatement is not None:
        restated_keys = {
            (f.metric_id, f.entity_id) for f in ctx.restatement.affected_figures
        }
        pack.restatement = ctx.restatement
    comparatives: list[FigureComparative] = []
    for figure in pack.figures:
        prior_figure = signed_by_key.get((figure.metric_id, figure.entity_id))
        if prior_figure is None:
            continue  # a metric born this period has no comparative
        change = change_pct = None
        if figure.currency == prior_figure.currency:
            delta = q(D(figure.value) - D(prior_figure.value))
            change = money(delta)
            if D(prior_figure.value) != 0:
                change_pct = money(q(delta / D(prior_figure.value) * 100))
        comparatives.append(FigureComparative(
            metric_id=figure.metric_id,
            entity_id=figure.entity_id,
            prior_value=prior_figure.value,
            prior_currency=prior_figure.currency,
            prior_pack_id=signed.pack_id,
            prior_definition_pack_version=(
                prior_figure.definition_pack_version
                or signed.definition_pack_version
            ),
            definition_changed=figure.metric_id in ctx.definition_changed,
            restated=(figure.metric_id, figure.entity_id) in restated_keys,
            change=change,
            change_pct=change_pct,
        ))
    pack.comparatives = comparatives
    return verifier_module.verify_comparatives(comparatives, signed)
