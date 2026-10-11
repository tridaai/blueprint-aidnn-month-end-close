"""Definition change governance: measure the change before
it governs, and make governing it a recorded act.

Definition packs are this close's constitution — versioned
JSON, a closed op set, every figure traceable to the version
that defined it. Until now a new version could simply *appear*
in the registry and the next close would run under it: the
``DEFINITION_CHANGED`` flags (round 2) reported the change
after it had already governed a close. This module is the
front door that was missing:

- **Impact first, computed.** A dry-run takes a candidate
  version and a period with a SIGNED pack, and recomputes
  that period twice from its stamped sources — once under the
  version the pack cites, once under the candidate, both at
  the rate table the signed pack stamps (the round-6 rule:
  the stamp is the basis). The change list — figures moved,
  added, dropped, variance families whose membership changes,
  each moved figure judged against the close's standing
  materiality ruler — is arithmetic, not assertion. The
  report carries no timestamp, so its digest is stable: the
  same inputs recompute to the same report, byte for byte.
- **Activation is a record.** A candidate governs future
  periods only through a named activation: actor, reason,
  the period it governs from, and the dry-run (id + digest)
  whose impact justified it. Activating without a dry-run on
  record is refused — the impact must exist before the act.
  Activating into an already-signed period is refused — a
  signed period's pack keeps its cited version forever.
- **Selection is a rule, printed.** Which version governs a
  period is computed from the activation records (the latest
  activation whose from-period has arrived; otherwise the
  deployment's wired default), and the answer is recorded on
  the run and stamped on the pack. The first pack governed
  by a new version states the change on its face.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import comparatives as comparatives_module
from . import verifier as verifier_module
from .definitions import (
    DefinitionPack,
    bundled_pack_dir,
    load_definition_pack,
    load_definition_pack_version,
)
from .errors import GateError
from .flux import is_material
from .fx import D, money, q
from .marts import build_marts
from .schemas import (
    BaselineDiscrepancy,
    BoardPack,
    DefinitionChange,
    DryRunFigure,
    DryRunReport,
    FigureDelta,
    PackActivation,
)


def registry_versions(pack_id: str,
                      search_dirs: list[Path] | None = None,
                      ) -> list[DefinitionPack]:
    """Every version of ``pack_id`` the registry holds, oldest
    first. The registry is the versioned pack files on disk —
    the same lookup the comparative layer uses to find a prior
    period's version."""
    dirs = search_dirs if search_dirs is not None else [bundled_pack_dir()]
    found: dict[str, DefinitionPack] = {}
    for directory in dirs:
        if not directory or not Path(directory).is_dir():
            continue
        for path in sorted(Path(directory).glob("*.json")):
            try:
                candidate = load_definition_pack(path)
            except Exception:
                continue  # an unparseable file is not a pack version
            if candidate.pack_id == pack_id:
                found.setdefault(candidate.version, candidate)
    return [found[v] for v in sorted(found, key=_version_key)]


def _version_key(version: str) -> tuple:
    parts = []
    for piece in version.replace("-", ".").split("."):
        parts.append((0, int(piece), "") if piece.isdigit()
                     else (1, 0, piece))
    return tuple(parts)


def load_version(pack_id: str, version: str,
                 search_dirs: list[Path] | None = None,
                 ) -> DefinitionPack | None:
    return load_definition_pack_version(pack_id, version, search_dirs)


# -- the dry-run ---------------------------------------------------


def compute_dry_run(store, signed: BoardPack, base_pack: DefinitionPack,
                    candidate_pack: DefinitionPack, engine) -> DryRunReport:
    """Recompute the signed period under both definition
    versions, from its stamped sources, and diff the results.

    Both sides run the deployment's engine over marts built
    from the *same* stamped batches, with conversions pinned
    to the rate table the signed pack stamps — the verifier
    then recomputes each side from source at that stamp, and
    the values compared are the verifier's, never the signed
    pack's recorded figures and never the engine's proposals.
    """
    batches = []
    for batch_id in signed.source_versions.batches:
        batch = store.get_batch(batch_id)
        if batch is None:
            raise GateError(
                f"cannot dry-run over signed pack {signed.pack_id}: "
                f"stamped source batch {batch_id} is missing from "
                "the store — the impact would be computed from "
                "something other than the sources the close "
                "actually consumed"
            )
        batches.append(batch)
    stamp = signed.source_versions.fx_table

    def side(pack_def: DefinitionPack):
        marts = build_marts(batches, pack_def)
        if stamp is not None:
            # Round 6's rule, applied to a recomputation: the
            # signed pack's stamped table is the basis. If the
            # batch set's table has been tampered with since,
            # the verifier names RATE_TABLE_MISMATCH on both
            # sides alike — and reprices neither.
            marts.rate_table = stamp
            marts.source_versions.fx_table = stamp
        figures = engine.answer(pack_def, marts)
        report = verifier_module.verify(pack_def, batches, figures)
        values = {
            (c.metric_id, c.entity_id): c.verifier_value
            for c in report.checks
        }
        currencies = {
            (f.metric_id, f.entity_id): f.currency for f in figures
        }
        families = sorted({v.code for v in report.variances})
        return values, currencies, families, report

    base_values, base_cur, base_families, base_report = side(base_pack)
    cand_values, cand_cur, cand_families, _ = side(candidate_pack)

    signed_by_key = {(f.metric_id, f.entity_id): f for f in signed.figures}
    discrepancies: list[BaselineDiscrepancy] = []
    for check in base_report.checks:
        figure = signed_by_key.get((check.metric_id, check.entity_id))
        if figure is not None and figure.value != check.verifier_value:
            discrepancies.append(BaselineDiscrepancy(
                metric_id=check.metric_id, entity_id=check.entity_id,
                signed_value=figure.value,
                recomputed_value=check.verifier_value,
            ))

    moved: list[FigureDelta] = []
    added: list[DryRunFigure] = []
    dropped: list[DryRunFigure] = []
    keys = sorted(
        set(base_values) | set(cand_values),
        key=lambda k: (k[0], k[1] or ""),
    )
    for key in keys:
        metric_id, entity_id = key
        in_base, in_cand = key in base_values, key in cand_values
        currency = cand_cur.get(key) or base_cur.get(key) or ""
        if in_base and in_cand:
            old, new = D(base_values[key]), D(cand_values[key])
            if old == new:
                continue
            delta = q(new - old)
            delta_pct = None
            if old != 0:
                delta_pct = money(q(delta / old * 100))
            signed_figure = signed_by_key.get(key)
            moved.append(FigureDelta(
                metric_id=metric_id, entity_id=entity_id,
                currency=currency,
                signed_pack_value=signed_figure.value
                if signed_figure is not None else base_values[key],
                base_value=base_values[key],
                candidate_value=cand_values[key],
                delta=money(delta), delta_pct=delta_pct,
                material=is_material(delta, delta_pct),
            ))
        elif in_cand:
            added.append(DryRunFigure(
                metric_id=metric_id, entity_id=entity_id,
                currency=currency, value=cand_values[key]))
        else:
            dropped.append(DryRunFigure(
                metric_id=metric_id, entity_id=entity_id,
                currency=currency, value=base_values[key]))

    return DryRunReport(
        pack_id=candidate_pack.pack_id,
        base_version=base_pack.version,
        candidate_version=candidate_pack.version,
        reference_period=signed.period,
        reference_pack_id=signed.pack_id,
        changed_metrics=sorted(
            comparatives_module.changed_metric_ids(base_pack,
                                                   candidate_pack)),
        moved=moved, added=added, dropped=dropped,
        variance_families_base=base_families,
        variance_families_candidate=cand_families,
        families_added=sorted(set(cand_families) - set(base_families)),
        families_removed=sorted(set(base_families) - set(cand_families)),
        baseline_discrepancies=sorted(
            discrepancies, key=lambda d: (d.metric_id, d.entity_id or "")),
    )


def report_digest(report: DryRunReport) -> str:
    """The digest an activation cites: sha256 over the
    report's canonical bytes — the same canonical form the
    evidence bundle uses (sorted keys, two-space indent, one
    trailing newline). The report is a pure function of its
    inputs, so the digest is stable across recomputation."""
    payload = (
        json.dumps(report.model_dump(), indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dry_run_id_for(pack_id: str, candidate_version: str,
                   reference_pack_id: str) -> str:
    return f"DRY-{pack_id}-v{candidate_version}-over-{reference_pack_id}"


# -- activation + selection -----------------------------------------


def governing_activation(activations: list[PackActivation],
                         period: str) -> PackActivation | None:
    """The activation governing ``period``: among the acts
    whose from-period has arrived, the one for the latest
    from-period; a later-recorded act for the same from-period
    supersedes the earlier (and the superseded never governs).
    """
    superseded = {a.supersedes for a in activations if a.supersedes}
    eligible = [
        (index, a) for index, a in enumerate(activations)
        if a.from_period <= period and a.activation_id not in superseded
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda pair: (pair[1].from_period, pair[0]))[1]


def governing_version(activations: list[PackActivation], period: str,
                      default_version: str) -> str:
    """The version governing ``period``: the governing
    activation's version, or the deployment's wired default
    when no activation has arrived for the period."""
    activation = governing_activation(activations, period)
    return activation.to_version if activation is not None \
        else default_version


def prepare_change_statement(store, period: str,
                             selected_pack: DefinitionPack,
                             activation: PackActivation | None,
                             ) -> DefinitionChange | None:
    """The pack-face statement for the first pack governed by
    a newly activated version — or ``None`` when this period's
    version is the one its prior period signed under (no
    change to state), or when no activation governs (the
    deployment simply runs its wired pack, as it always has).
    """
    if activation is None:
        return None
    prior = comparatives_module.find_signed_pack(
        store, comparatives_module.previous_period(period))
    if prior is not None \
            and prior.definition_pack_version == selected_pack.version:
        return None
    dry_run = store.get_dry_run(activation.dry_run_id)
    if dry_run is None:
        return None  # the activation's evidence is gone; the
        # bundle's completeness check will name that gap on a
        # signed pack — the statement is not fabricated here
    report = dry_run.report
    return DefinitionChange(
        from_version=prior.definition_pack_version
        if prior is not None else activation.from_version,
        to_version=selected_pack.version,
        from_period=activation.from_period,
        activation_id=activation.activation_id,
        actor=activation.actor,
        reason=activation.reason,
        dry_run_id=activation.dry_run_id,
        dry_run_digest=activation.dry_run_digest,
        moved_count=len(report.moved),
        added_count=len(report.added),
        dropped_count=len(report.dropped),
        material_count=report.material_count,
    )
