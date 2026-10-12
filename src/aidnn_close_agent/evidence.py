"""The audit evidence pack: one artifact an external auditor
can re-perform from.

When the auditors arrive, "the system verified it" is not
evidence. What is evidence is a bundle a third party can work
from without trusting the system that produced it: every figure
with the definition that defines it and the verdict the verifier
recorded, the manifest of the exact source extracts the close
consumed (with the content hashes recorded at ingestion), the
comparatives and the signed pack they cite, the restatement and
its acknowledgement, and the sign-off record with the checklist
state the signature froze.

The bundle is a **projection, not a computation**. Assembly here
reads stored records — the pack, its run, its source batches,
the definition pack at the version the pack stamps, the signed
prior pack a comparative cites — and arranges them. It computes
nothing about the figures themselves: a bundle figure equals
the pack figure because it *is* the pack figure, copied. Two
disciplines keep the artifact honest:

- **Generation is gated.** A bundle exists only for a
  ``SIGNED_OFF`` pack. Generating one for a blocked, awaiting,
  returned, or stale pack is refused with the state named — an
  auditor bundle for an unsigned close would be a false
  artifact.
- **Completeness is checked, not assumed.** Before anything is
  written, every figure must have its definition entry and a
  ``verified`` verdict, every stamped source batch must be in
  the store at the stamped version with its recorded hash, the
  run must be CLOSED with nothing missing (the checklist state
  a signature freezes — a closed run refuses ingestion, so the
  state read back *is* the state at signing), and every
  comparative's cited pack must stand in the store as signed.
  Any gap refuses generation, naming the gap; a partial bundle
  is never written.

The bytes are canonical: fixed key order, lists sorted by the
keys an auditor would sort them by, and no wall-clock field
anywhere in the document — generation metadata (when, and the
digest) lives on the bundle *record* in the store, so the same
pack regenerates byte-identical bytes forever.

The flux schedule (round 4) joins this bundle as a section
**under the same v1 format**, and the precedent is the bundle's
own: the comparative layer joined v1 the same way in round 2,
because the format version names the bundle's schema family —
a projection whose sections mirror the layers the pack itself
carries — not a per-section changelog. A pack signed before
flux existed carries ``flux: null`` forever (a signed pack is
never edited), so its bundle says exactly that: this close
predates the flux schedule. Bundles already generated are
stored bytes beside their records and are never rewritten;
what changes is only what a *new* generation projects from a
pack that carries a schedule.

The intercompany agreement check (round 5) joins the same
way, as ``intercompany``: every pair the verifier paired, both
stated figures, the basis comparison, and the verdict — the
evidence that the eliminations in the figures net real,
mirrored trades and not fictions. A pack whose record carries
no pairs (signed before the check existed, or a close with no
intercompany legs to pair) projects ``intercompany: null``.
Since a disagreement blocks sign-off, a signed pack's section
shows agreed pairs; the disagreements live on the blocked
packs that never earn a bundle, named in their variances.

Rate provenance (round 6) joins as ``fx``: the rate table this
pack stamps — the table itself, not only its version — the
table the cited prior pack stamps, and the rates that differ
between them, so an auditor re-performing a comparative can
see the basis it was converted on and where that basis moved.
A pack stamped before tables rode the stamp projects
``fx.current: null``: the bundle says the rates are not on
record rather than reconstructing them from batches the close
may not have used.

Variance disposition (round 7) joins as ``dispositions`` and
``opening_items``, under the same rule as every section
before it: a bundle for a pack signed under disposition
*lists* the acceptances — a bundle that omitted them would
present accepted breaks as clean passes, the one falsehood
this artifact exists to prevent. The completeness discipline
bends exactly there and nowhere else: a figure may stand in
the bundle with a verdict other than ``verified`` only when
the mismatch it carries is a variance on the pack and a
disposition on the pack's face covers that exact variance —
the number is shown with its true verdict and the named
acceptance that carried it, never quietly upgraded. A pack
that signed clean projects both sections as ``null``.

Definition governance (round 8) joins as
``definition_change``: when the signed pack was the first
governed by a newly activated definition-pack version, the
bundle carries the change statement from its face, the
activation record it cites, and the dry-run report whose
digest the activation relied on — the evidence that the
ruler was changed by a named act, with its impact computed
beforehand, not swapped silently between closes. The cited
records must stand in the store and the dry-run's digest
must match the citation, or generation refuses with the gap
named. A pack with no change on its face projects
``definition_change: null`` — the close ran under the version
its predecessor signed under, and there is nothing to cite.

Figure drill-down (round 9) joins as ``drills``: for every
figure, the drill re-performed at assembly time from the
pack's stamped sources — its composed total, its source-line
count, and a digest of the full drill. The bundle cites
drills by digest rather than embedding every line: the lines
are the extracts' own content, already manifested above by
hash, and the full drill is one call away against the same
pack, reproducible byte for byte — a reader who re-performs
it checks the digest and holds the same artifact. There is
no absence case: a signed pack's stamps and sources persist
by construction, so every signed pack's section is populated.
The one entry that is not a footing drill is a mismatch —
when a source record has moved under a signed pack's stamps
since signing, the figure's entry records the break (the
composition the sources now produce, against the figure the
board signed) instead of a digest: the bundle names it,
exactly as it names a dispositioned figure's true verdict,
and never papers over it with a clean citation.

Pre-close readiness (round 10) joins as ``readiness``: the
statement from the signed pack's face (the manifest it ran
under, complete or waived), the manifest record it cites,
and — for a close that started short-handed — the waiver
records that licensed it, quoted whole: an auditor must see
that the close ran under waiver, which items were missing,
and who allowed it and why. The cited manifest must stand
in the store at the cited version, and every cited waiver
must stand with the actor, reason, and items the citation
quotes, or generation refuses with the gap named. A pack
built for a period no manifest governed projects
``readiness: null`` — the close ran under the standing
checklist alone, and there is nothing to cite.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import dispositions as dispositions_module
from . import drill as drill_module
from . import guardrails
from .definitions import (
    DefinitionPack,
    bundled_pack_dir,
    load_definition_pack_version,
)
from .errors import DrillError, DrillMismatch, EvidenceError
from .fx import changed_currencies
from .schemas import BoardPack

BUNDLE_FORMAT = "aidnn-close-evidence/v1"


def bundle_id_for(pack_id: str) -> str:
    return f"EVB-{pack_id}"


def bundle_keys(pack: BoardPack) -> tuple[str, str]:
    base = f"evidence/{pack.period}/{pack.pack_id}/evidence-v1"
    return f"{base}.json", f"{base}.txt"


def resolve_definitions(service, pack: BoardPack) -> DefinitionPack:
    """The definition pack at the version the pack stamps.

    The service's live pack wins when it *is* that version (the
    usual case, and the only source for a deployment whose pack
    file lives outside the bundled registry). Otherwise the
    versioned registry is consulted — the same lookup the
    comparative layer uses to recompute a prior period under
    its own definitions. An unresolvable version is a refusal,
    never a substitution: reproducing definitions from the
    wrong version would fabricate the evidence."""
    live = service.pack_def
    if live.pack_id == pack.definition_pack_id \
            and live.version == pack.definition_pack_version:
        return live
    dirs: list[Path] = list(service.pack_dirs or [])
    bundled = bundled_pack_dir()
    if bundled not in dirs:
        dirs.append(bundled)
    found = load_definition_pack_version(
        pack.definition_pack_id, pack.definition_pack_version, dirs
    )
    if found is None:
        raise EvidenceError(
            f"pack {pack.pack_id} was built under definition pack "
            f"{pack.definition_pack_id} v{pack.definition_pack_version}, "
            "which is not available in this deployment — figure "
            "definitions cannot be reproduced, so no bundle is generated"
        )
    return found


def assemble_bundle(service, pack: BoardPack) -> dict:
    """Assemble the bundle document for a signed pack, or refuse.

    Pure projection: reads the store and the definition pack,
    returns the document as plain data. Writes nothing — the
    service owns the writing, so a refusal here leaves no trace.
    """
    if pack.status != "SIGNED_OFF":
        raise EvidenceError(
            f"pack {pack.pack_id} is {pack.status}; an evidence bundle "
            "is generated only for a SIGNED_OFF pack — an auditor "
            "bundle for an unsigned close would be a false artifact"
        )
    if pack.decision is None or pack.decision.decision != "sign":
        raise EvidenceError(
            f"pack {pack.pack_id} is SIGNED_OFF but carries no sign "
            "decision on the record — the sign-off evidence is missing"
        )
    definitions = resolve_definitions(service, pack)
    defined = {m.metric_id: m for m in definitions.metrics}

    figures: list[dict] = []
    for figure in sorted(
        pack.figures, key=lambda f: (f.metric_id, f.entity_id or "")
    ):
        where = f"{figure.metric_id}@{figure.entity_id}" \
            if figure.entity_id else figure.metric_id
        definition = defined.get(figure.metric_id)
        if definition is None:
            raise EvidenceError(
                f"figure {where} on pack {pack.pack_id} has no "
                f"definition entry in {definitions.pack_id} "
                f"v{definitions.version} — the bundle would carry a "
                "number without the rule that produced it"
            )
        if figure.status != "verified":
            # The one honest exception: a pack signed under
            # disposition may carry a figure whose mismatch is
            # itself a variance on the pack, accepted exactly
            # as computed by a disposition on the pack's face.
            # The figure then stands with its true verdict and
            # its named acceptance — never upgraded, never
            # unexplained. Any other non-verified verdict is
            # the refusal it has always been.
            explained = any(
                variance.metric_id == figure.metric_id
                and variance.entity_id == figure.entity_id
                and any(
                    dispositions_module.disposition_covers(
                        disposition, pack, variance)
                    for disposition in pack.dispositions
                )
                for variance in pack.variances
            )
            if not explained:
                raise EvidenceError(
                    f"figure {where} on pack {pack.pack_id} carries "
                    f"verifier verdict {figure.status!r}, not "
                    "'verified', and no disposition on the pack's "
                    "face covers the variance that names it — a "
                    "signed pack holds no unexplained verdict"
                )
        figures.append({
            "metric_id": figure.metric_id,
            "label": figure.label,
            "scope": figure.scope,
            "entity_id": figure.entity_id,
            "value": figure.value,
            "currency": figure.currency,
            "verifier_verdict": figure.status,
            "definition_pack_version": figure.definition_pack_version,
            "source_versions": figure.source_versions.model_dump(),
            "definition": definition.model_dump(),
        })

    manifest: list[dict] = []
    for batch_id in sorted(pack.source_versions.batches):
        stamped = pack.source_versions.batches[batch_id]
        batch = service.store.get_batch(batch_id)
        if batch is None:
            raise EvidenceError(
                f"source batch {batch_id} is stamped on pack "
                f"{pack.pack_id} (v{stamped}) but is missing from the "
                "store — the manifest would be incomplete"
            )
        if batch.version != stamped:
            raise EvidenceError(
                f"source batch {batch_id} is stored at v{batch.version} "
                f"but pack {pack.pack_id} stamps v{stamped}"
            )
        if not batch.sha256:
            raise EvidenceError(
                f"source batch {batch_id} carries no recorded content "
                "hash — the manifest cannot name the exact bytes the "
                "close consumed"
            )
        manifest.append({
            "batch_id": batch.batch_id,
            "kind": batch.kind,
            "entity_id": batch.entity_id,
            "version": batch.version,
            "sha256": batch.sha256,
            "supersedes": batch.supersedes,
            "phase": batch.phase,
        })

    # Figure drills: every figure re-performed from the
    # stamped sources (the manifest above has already proven
    # those sources stand at their stamped versions), cited
    # by digest — the full lines are one drill call away
    # against the same pack and reproduce byte for byte. A
    # figure whose sources no longer compose to it (a record
    # moved under the signed pack's stamps) is recorded as
    # the mismatch it is, never as a footing citation.
    drills: list[dict] = []
    for figure in sorted(
        pack.figures, key=lambda f: (f.metric_id, f.entity_id or "")
    ):
        entry: dict = {
            "metric_id": figure.metric_id,
            "entity_id": figure.entity_id,
            "figure_value": figure.value,
        }
        try:
            drill = drill_module.build_drill(
                service.store, pack, definitions,
                figure.metric_id, figure.entity_id)
        except DrillMismatch as exc:
            entry.update({
                "composed_total": exc.composed_total,
                "line_count": exc.line_count,
                "digest": None,
                "mismatch": True,
            })
        except DrillError as exc:
            raise EvidenceError(
                f"the drill for figure {figure.metric_id} on "
                f"pack {pack.pack_id} cannot be performed: {exc}"
            ) from exc
        else:
            entry.update({
                "composed_total": drill.composed_total,
                "line_count": drill.line_count,
                "digest": drill_module.drill_digest(drill),
                "mismatch": False,
            })
        drills.append(entry)

    run = service.store.get_run(pack.run_id)
    if run is None:
        raise EvidenceError(
            f"run {pack.run_id} for pack {pack.pack_id} is missing "
            "from the store — the checklist state at signing cannot "
            "be evidenced"
        )
    if run.status != "CLOSED":
        raise EvidenceError(
            f"run {pack.run_id} is {run.status}, not CLOSED — a "
            "signed pack's run closes at signing and refuses "
            "ingestion thereafter, so its checklist is the state "
            "the signature froze; this run's is still moving"
        )
    missing = guardrails.missing_sources(run, definitions.entity_ids())
    if missing:
        raise EvidenceError(
            f"run {pack.run_id} closed with sources still missing: "
            + ", ".join(missing)
        )

    comparatives: list[dict] = []
    cited_packs: dict[str, BoardPack] = {}
    for comparative in sorted(
        pack.comparatives, key=lambda c: (c.metric_id, c.entity_id or "")
    ):
        cited = service.store.get_pack(comparative.prior_pack_id)
        if cited is None or cited.status != "SIGNED_OFF":
            raise EvidenceError(
                f"a comparative on pack {pack.pack_id} cites signed "
                f"pack {comparative.prior_pack_id}, which does not "
                "stand in the store as a signed pack"
            )
        cited_packs[cited.pack_id] = cited
        comparatives.append(comparative.model_dump())

    # Rate provenance: this pack's stamped table, the cited
    # prior pack's stamped table, and the rates that moved
    # between them — projected from the records, like everything
    # else here. A missing stamp projects as null, never as a
    # table reconstructed from the batches in the store.
    current_table = pack.source_versions.fx_table
    prior_table = None
    if pack.comparatives:
        cited_prior = cited_packs.get(pack.comparatives[0].prior_pack_id)
        if cited_prior is not None:
            prior_table = cited_prior.source_versions.fx_table
    fx_section = {
        "current": current_table.model_dump()
        if current_table is not None else None,
        "prior": prior_table.model_dump()
        if prior_table is not None else None,
        "rate_changes": [
            {"currency": currency, "prior_rate": before,
             "current_rate": after}
            for currency, (before, after)
            in changed_currencies(prior_table, current_table).items()
        ],
    }

    if pack.restatement is not None \
            and pack.restatement_acknowledgement is None:
        raise EvidenceError(
            f"pack {pack.pack_id} carries an unacknowledged "
            "restatement — sign-off refuses that state, so a signed "
            "pack should never present it"
        )

    # Every acceptance on the signed pack's face must answer
    # for a variance on the pack: an acceptance covering
    # nothing would be decoration on the record, and the
    # bundle refuses to carry it as evidence.
    for disposition in pack.dispositions:
        if not any(
            dispositions_module.disposition_covers(
                disposition, pack, variance)
            for variance in pack.variances
        ):
            raise EvidenceError(
                f"disposition {disposition.disposition_id} on pack "
                f"{pack.pack_id} covers no variance on the pack — "
                "an acceptance on the face that answers for no "
                "computed break is not evidence"
            )

    # The definition change on the pack's face must cite
    # records that stand: the activation that made the version
    # govern, and the dry-run whose digest the activation (and
    # the statement) relied on. A citation that cannot be
    # resolved is a gap, named like every other gap here.
    definition_change_section = None
    if pack.definition_change is not None:
        statement = pack.definition_change
        activation = next(
            (a for a in service.store.list_activations()
             if a.activation_id == statement.activation_id), None)
        if activation is None:
            raise EvidenceError(
                f"pack {pack.pack_id} states a definition change "
                f"under activation {statement.activation_id}, "
                "which does not stand in the store — the act "
                "that changed the ruler cannot be evidenced"
            )
        dry_run = service.store.get_dry_run(statement.dry_run_id)
        if dry_run is None:
            raise EvidenceError(
                f"pack {pack.pack_id} cites dry-run "
                f"{statement.dry_run_id}, which does not stand "
                "in the store — the impact the activation "
                "relied on cannot be evidenced"
            )
        if dry_run.digest != statement.dry_run_digest \
                or activation.dry_run_digest != dry_run.digest:
            raise EvidenceError(
                f"dry-run {dry_run.dry_run_id} stands in the "
                f"store with digest {dry_run.digest}, but the "
                f"pack cites {statement.dry_run_digest} — the "
                "impact on record is not the impact the "
                "activation relied on"
            )
        definition_change_section = {
            "statement": statement.model_dump(),
            "activation": activation.model_dump(),
            "dry_run": {
                "dry_run_id": dry_run.dry_run_id,
                "digest": dry_run.digest,
                "computed_at": dry_run.computed_at,
                "report": dry_run.report.model_dump(),
            },
        }

    # The readiness statement on the pack's face must cite
    # records that stand: the manifest that governed the
    # build, at the version the statement cites, and every
    # waiver the statement quotes — actor, reason, and the
    # items it covered. A citation that cannot be resolved,
    # or resolves to a different record, is a gap, named like
    # every other gap here.
    readiness_section = None
    if pack.readiness is not None:
        statement = pack.readiness
        manifest_record = service.store.get_manifest(
            statement.manifest_id)
        if manifest_record is None:
            raise EvidenceError(
                f"pack {pack.pack_id} states readiness under "
                f"manifest {statement.manifest_id}, which does "
                "not stand in the store — the expectation the "
                "close ran against cannot be evidenced"
            )
        if manifest_record.version != statement.manifest_version \
                or manifest_record.period != pack.period:
            raise EvidenceError(
                f"pack {pack.pack_id} cites manifest "
                f"{statement.manifest_id} "
                f"v{statement.manifest_version} for period "
                f"{pack.period}, but the record standing under "
                f"that id is v{manifest_record.version} for "
                f"{manifest_record.period} — the statement "
                "and the record disagree"
            )
        waiver_records = []
        for citation in statement.waivers:
            record = service.store.get_waiver(citation.waiver_id)
            if record is None:
                raise EvidenceError(
                    f"pack {pack.pack_id} was built under "
                    f"waiver {citation.waiver_id}, which does "
                    "not stand in the store — the licence the "
                    "close started under cannot be evidenced"
                )
            if record.actor != citation.actor \
                    or record.reason != citation.reason \
                    or not set(citation.items) <= set(record.items):
                raise EvidenceError(
                    f"waiver {record.waiver_id} stands in the "
                    f"store with actor {record.actor!r} and "
                    f"items {record.items}, but pack "
                    f"{pack.pack_id} cites it as "
                    f"{citation.actor!r} covering "
                    f"{citation.items} — the citation and the "
                    "record disagree"
                )
            waiver_records.append(record.model_dump())
        readiness_section = {
            "statement": statement.model_dump(),
            "manifest": manifest_record.model_dump(),
            "waivers": waiver_records,
        }

    return {
        "format": BUNDLE_FORMAT,
        "pack": {
            "pack_id": pack.pack_id,
            "run_id": pack.run_id,
            "period": pack.period,
            "status": pack.status,
            "definition_pack_id": pack.definition_pack_id,
            "definition_pack_version": pack.definition_pack_version,
            "mart_version": pack.mart_version,
            "created_at": pack.created_at,
        },
        "sign_off": {
            "decision": pack.decision.decision,
            "actor": pack.decision.actor,
            "reason": pack.decision.reason,
            "at": pack.decision.at,
            "run_id": run.run_id,
            "run_status": run.status,
            "checklist": run.checklist,
            "group_checklist": run.group_checklist,
            "missing_sources": missing,
        },
        "figures": figures,
        "drills": drills,
        "source_manifest": manifest,
        "fx_version": current_table.version
        if current_table is not None
        else pack.source_versions.fx_version,
        "fx": fx_section,
        "comparatives": comparatives,
        "flux": pack.flux.model_dump() if pack.flux is not None else None,
        "intercompany": [p.model_dump() for p in pack.ic_pairs]
        if pack.ic_pairs else None,
        "restatement": pack.restatement.model_dump()
        if pack.restatement is not None else None,
        "restatement_acknowledgement":
            pack.restatement_acknowledgement.model_dump()
            if pack.restatement_acknowledgement is not None else None,
        "dispositions": [d.model_dump() for d in pack.dispositions]
        if pack.dispositions else None,
        "opening_items": [i.model_dump() for i in pack.opening_items]
        if pack.opening_items else None,
        "definition_change": definition_change_section,
        "readiness": readiness_section,
        "variances": [v.model_dump() for v in pack.variances],
    }


def canonical_json(document: dict) -> bytes:
    """The bundle as bytes: canonical key order, two-space
    indent, one trailing newline. A pure function of the
    document — the same pack always yields the same bytes."""
    return (
        json.dumps(document, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _definition_summary(definition: dict) -> str:
    derived = definition.get("derived")
    if derived:
        parts = [derived["op"]]
        if derived.get("of"):
            parts.append(f"of {derived['of']}")
        if derived.get("args"):
            parts.append("over " + ", ".join(derived["args"]))
        if derived.get("elimination_id"):
            parts.append(f"elimination {derived['elimination_id']}")
        return "derived: " + " ".join(parts)
    summary = (
        f"{definition.get('source')} · {definition.get('measure')} · "
        f"accounts {', '.join(definition.get('accounts') or []) or '—'}"
    )
    if definition.get("exclude_ic"):
        summary += " · intercompany lines excluded"
    return summary


def render_text(document: dict) -> str:
    """The readable rendering of the same assembly — generated
    from the document, never assembled separately, so the two
    renderings cannot drift."""
    pack = document["pack"]
    sign_off = document["sign_off"]
    lines: list[str] = []
    lines.append("AUDIT EVIDENCE PACK")
    lines.append(
        f"Board pack {pack['pack_id']} · period {pack['period']} · "
        f"run {pack['run_id']} · status {pack['status']}"
    )
    lines.append(
        f"Definition pack {pack['definition_pack_id']} "
        f"v{pack['definition_pack_version']} · mart version "
        f"{pack['mart_version']} · FX table v{document['fx_version']}"
    )
    lines.append("")
    lines.append(
        f"SIGN-OFF: {sign_off['decision']} by {sign_off['actor']} "
        f"at {sign_off['at']}"
        + (f" — {sign_off['reason']}" if sign_off["reason"] else "")
    )
    lines.append(
        f"Run {sign_off['run_id']} closed at signing; checklist "
        "complete (no missing sources):"
    )
    for entity_id in sorted(sign_off["checklist"]):
        kinds = sign_off["checklist"][entity_id]
        detail = ", ".join(
            f"{kind} v{kinds[kind]}" for kind in sorted(kinds)
        )
        lines.append(f"  {entity_id}: {detail}")
    group = sign_off["group_checklist"]
    if group:
        detail = ", ".join(
            f"{kind} v{group[kind]}" for kind in sorted(group)
        )
        lines.append(f"  GROUP: {detail}")
    lines.append("")
    lines.append(f"FIGURES ({len(document['figures'])}) — value, "
                 "definition, verifier verdict:")
    for figure in document["figures"]:
        scope = figure["entity_id"] or figure["scope"]
        lines.append(
            f"  {figure['metric_id']} · {scope} · "
            f"{figure['currency']} {figure['value']} · "
            f"verdict: {figure['verifier_verdict']}"
        )
        lines.append(
            f"    definition ({figure['definition_pack_version']}): "
            f"{_definition_summary(figure['definition'])}"
        )
    drills = document.get("drills") or []
    if drills:
        lines.append("")
        lines.append(
            f"FIGURE DRILLS ({len(drills)}) — every figure "
            "re-performed from its stamped sources; the digest "
            "is of the full drill (every line), and the drill "
            "itself is reproducible against the pack:")
        for entry in drills:
            scope = entry["entity_id"] or "consolidated"
            if entry["mismatch"]:
                lines.append(
                    f"  {entry['metric_id']} · {scope} · "
                    f"MISMATCH: the stamped sources now compose "
                    f"to {entry['composed_total']}, but the "
                    f"signed figure records "
                    f"{entry['figure_value']} — a source record "
                    "moved under the signed pack's stamps")
            else:
                lines.append(
                    f"  {entry['metric_id']} · {scope} · composed "
                    f"{entry['composed_total']} = figure "
                    f"{entry['figure_value']} · "
                    f"{entry['line_count']} line(s) · drill "
                    f"sha256 {entry['digest']}")
    lines.append("")
    lines.append(f"SOURCE MANIFEST ({len(document['source_manifest'])}) "
                 "— the extracts the close consumed, hashes as "
                 "recorded at ingestion:")
    for batch in document["source_manifest"]:
        scope = batch["entity_id"] or "GROUP"
        lines.append(
            f"  {batch['batch_id']} · {batch['kind']} · {scope} · "
            f"v{batch['version']} · sha256 {batch['sha256']}"
            + (f" · supersedes {batch['supersedes']}"
               if batch["supersedes"] else "")
            + (f" · phase {batch['phase']}"
               if batch["phase"] != "initial" else "")
        )
    fx = document.get("fx") or {}
    lines.append("")
    lines.append("RATE PROVENANCE — the rate tables the closes "
                 "converted on, as stamped on their packs:")

    def _table_line(label: str, table) -> str:
        if table is None:
            return (f"  {label}: no rate table on the stamp — the "
                    "pack predates rate stamping, and its rates "
                    "are not reconstructed here")
        rates = ", ".join(
            f"{currency} {table['rates'][currency]}"
            for currency in sorted(table["rates"])
        ) or "no foreign rates"
        return f"  {label}: rate table v{table['version']} ({rates})"

    lines.append(_table_line("this pack", fx.get("current")))
    if document["comparatives"]:
        lines.append(_table_line("prior pack", fx.get("prior")))
    for change in fx.get("rate_changes") or []:
        lines.append(
            f"  RATE CHANGED: {change['currency']}: "
            f"{change['prior_rate'] or 'absent'} (prior) → "
            f"{change['current_rate'] or 'absent'} (current) — "
            "consolidated comparatives converting this currency "
            "are flagged rate changed, not decomposed"
        )
    if document["comparatives"]:
        lines.append("")
        lines.append(f"COMPARATIVES ({len(document['comparatives'])}) "
                     "— prior period, as signed:")
        for comparative in document["comparatives"]:
            scope = comparative["entity_id"] or "consolidated"
            flags = []
            if comparative["definition_changed"]:
                flags.append("definition changed")
            if comparative.get("rate_changed"):
                flags.append("rate changed")
            if comparative["restated"]:
                flags.append("restated")
            change = comparative["change"]
            change_text = "—" if change is None else change
            if comparative["change_pct"] is not None:
                change_text += f" ({comparative['change_pct']}%)"
            lines.append(
                f"  {comparative['metric_id']} · {scope} · prior "
                f"{comparative['prior_currency']} "
                f"{comparative['prior_value']} (signed pack "
                f"{comparative['prior_pack_id']}, definition pack "
                f"v{comparative['prior_definition_pack_version']}) · "
                f"change {change_text}"
                + (f" · {' · '.join(flags)}" if flags else "")
            )
    flux = document.get("flux")
    if flux is not None:
        lines.append("")
        fx_text = ""
        if flux.get("prior_fx_version") is not None \
                and flux.get("current_fx_version") is not None:
            fx_text = (f"; rate tables: prior "
                       f"v{flux['prior_fx_version']} → current "
                       f"v{flux['current_fx_version']}")
        lines.append(
            f"FLUX SCHEDULE — every movement decomposed; materiality "
            f"bars: |movement| ≥ {flux['threshold_abs']} or "
            f"|change| ≥ {flux['threshold_pct']}% (prior period "
            f"{flux['prior_period']}, signed pack "
            f"{flux['prior_pack_id']}; definitions: prior "
            f"v{flux['prior_definition_pack_version']} → current "
            f"v{flux['current_definition_pack_version']}{fx_text}):"
        )
        for entry in flux["entries"]:
            scope = entry["entity_id"] or "consolidated"
            pct = entry["movement_pct"]
            pct_text = f" ({pct}%)" if pct is not None else ""
            flags = []
            if entry["material"]:
                flags.append("MATERIAL")
            if entry["definition_changed"]:
                flags.append("definition changed")
            if entry.get("rate_changed"):
                flags.append("rate changed")
            if entry["restated"]:
                flags.append("restated")
            lines.append(
                f"  {entry['metric_id']} · {scope} · moved "
                f"{entry['currency']} {entry['movement']}{pct_text}"
                + (f" · {' · '.join(flags)}" if flags else "")
            )
            for driver in entry["by_entity"]:
                lines.append(
                    f"    by entity · {driver['label']}: "
                    f"{driver['amount']}"
                )
            if entry["by_account"] is not None:
                for driver in entry["by_account"]:
                    lines.append(
                        f"    by account · {driver['label']}: "
                        f"{driver['amount']}"
                    )
            if entry["note"]:
                lines.append(f"    note: {entry['note']}")
    intercompany = document.get("intercompany")
    if intercompany is not None:
        lines.append("")
        lines.append(
            f"INTERCOMPANY AGREEMENT ({len(intercompany)}) — every "
            "pair the verifier paired, both figures as stated in "
            "each entity's own books, the buyer's figure expressed "
            "in the seller's (basis) currency at the close's rate "
            "table, and the verdict:")
        for pair in intercompany:
            revenue = (
                f"{pair['seller_currency']} {pair['seller_amount']}"
                if pair["seller_amount"] is not None
                else "none booked")
            cost = (
                f"{pair['buyer_currency']} {pair['buyer_amount']}"
                if pair["buyer_amount"] is not None
                else "none booked")
            basis = (
                f" = {pair['basis_currency']} "
                f"{pair['buyer_amount_basis']}"
                + (f" at {pair['fx_rate']}"
                   if pair["fx_rate"] is not None else "")
                if pair["buyer_amount_basis"] is not None else "")
            difference = (
                f" · difference {pair['basis_currency']} "
                f"{pair['difference']}"
                if pair["difference"] is not None else "")
            verdict = pair["verdict"]
            if pair["missing_side"] is not None:
                verdict += f" (no {pair['missing_side']} leg)"
            lines.append(
                f"  {pair['elimination_id']} · {pair['seller_id']} → "
                f"{pair['buyer_id']} · revenue leg (account "
                f"{pair['revenue_account']}) {revenue} · cost leg "
                f"(account {pair['cost_account']}) {cost}{basis}"
                f"{difference} · {verdict}"
            )
    if document["restatement"] is not None:
        restatement = document["restatement"]
        lines.append("")
        lines.append(
            f"RESTATED PRIOR PERIOD — {restatement['prior_period']}, "
            f"signed pack {restatement['prior_pack_id']}, restated by "
            f"{', '.join(restatement['restated_batch_ids'])}:"
        )
        for affected in restatement["affected_figures"]:
            scope = affected["entity_id"] or "consolidated"
            lines.append(
                f"  {affected['metric_id']} · {scope} · signed "
                f"{affected['currency']} {affected['signed_value']} → "
                f"restated sources produce {affected['recomputed_value']}"
            )
        acknowledgement = document["restatement_acknowledgement"]
        if acknowledgement is not None:
            lines.append(
                f"  Acknowledged by {acknowledgement['actor']} at "
                f"{acknowledgement['at']} — {acknowledgement['note']}"
            )
    opening_items = document.get("opening_items")
    if opening_items is not None:
        lines.append("")
        lines.append(
            f"OPENING ITEMS ({len(opening_items)}) — breaks "
            "carried in from the prior signed pack, re-tested "
            "against this period's sources:")
        for item in opening_items:
            subject = f" ({item['subject']})" if item["subject"] else ""
            lines.append(
                f"  {item['code']}{subject} · first accepted in "
                f"{item['origin_period']} (pack "
                f"{item['origin_pack_id']}) by "
                f"{item['dispositioned_by']} — {item['reason']} · "
                f"carry {item['carry_number']} · retest: "
                f"{item['retest']}"
            )
            if item["current_detail"]:
                lines.append(
                    f"    this period: {item['current_detail']}")
    dispositions = document.get("dispositions")
    if dispositions is not None:
        lines.append("")
        lines.append(
            f"DISPOSITIONS ({len(dispositions)}) — blocking "
            "variances accepted on the record by a named "
            "controller; the variances stand as computed, below:")
        for disposition in dispositions:
            subject = (f" ({disposition['subject']})"
                       if disposition["subject"] else "")
            origin = (
                f" · first accepted in "
                f"{disposition['origin_period']} (pack "
                f"{disposition['origin_pack_id']})"
                if disposition["carry_number"] > 1 else "")
            lines.append(
                f"  {disposition['disposition_id']} · "
                f"{disposition['code']}{subject} · "
                f"{disposition['decision']} by "
                f"{disposition['actor']} at {disposition['at']} — "
                f"{disposition['reason']} · carry "
                f"{disposition['carry_number']}{origin}"
                + (f" · supersedes {disposition['supersedes']}"
                   if disposition["supersedes"] else "")
            )
    definition_change = document.get("definition_change")
    if definition_change is not None:
        statement = definition_change["statement"]
        activation = definition_change["activation"]
        report = definition_change["dry_run"]["report"]
        lines.append("")
        lines.append(
            f"DEFINITION CHANGE — this pack is the first "
            f"governed by definition pack v{statement['to_version']} "
            f"(prior closes signed under v{statement['from_version']}):")
        lines.append(
            f"  Activated by {activation['actor']} at "
            f"{activation['at']}, governing from "
            f"{activation['from_period']} — {activation['reason']}")
        lines.append(
            f"  Impact first: dry-run "
            f"{definition_change['dry_run']['dry_run_id']} over "
            f"signed period {report['reference_period']} (pack "
            f"{report['reference_pack_id']}), digest "
            f"{definition_change['dry_run']['digest']} — "
            f"{len(report['moved'])} figure(s) moved, "
            f"{len(report['added'])} added, "
            f"{len(report['dropped'])} dropped, "
            f"{statement['material_count']} material by the "
            "close's flux ruler")
        for delta in report["moved"]:
            scope = delta["entity_id"] or "consolidated"
            lines.append(
                f"    would move · {delta['metric_id']} · {scope} · "
                f"{delta['currency']} {delta['base_value']} → "
                f"{delta['candidate_value']} "
                f"(Δ {delta['delta']})")
        for figure in report["added"]:
            scope = figure["entity_id"] or "consolidated"
            lines.append(
                f"    would add · {figure['metric_id']} · {scope} · "
                f"{figure['currency']} {figure['value']}")
        for figure in report["dropped"]:
            scope = figure["entity_id"] or "consolidated"
            lines.append(
                f"    would drop · {figure['metric_id']} · {scope} · "
                f"{figure['currency']} {figure['value']}")
    readiness = document.get("readiness")
    if readiness is not None:
        statement = readiness["statement"]
        manifest = readiness["manifest"]
        lines.append("")
        if statement["status"] == "WAIVED":
            lines.append(
                f"READINESS — WAIVED: this close started "
                f"short-handed under manifest "
                f"{statement['manifest_id']} "
                f"(v{statement['manifest_version']}, by "
                f"{manifest['actor']} — {manifest['note']}):")
            for name in statement["waived_items"]:
                lines.append(f"  ✗ {name}")
            for waiver in readiness["waivers"]:
                lines.append(
                    f"  Waived by {waiver['actor']} at "
                    f"{waiver['at']} ({waiver['waiver_id']}) — "
                    f"{waiver['reason']} · covering: "
                    + ", ".join(waiver["items"]))
        else:
            lines.append(
                f"READINESS — COMPLETE: every expected source "
                f"was received at its expected version under "
                f"manifest {statement['manifest_id']} "
                f"(v{statement['manifest_version']}, by "
                f"{manifest['actor']} — {manifest['note']})")
    if document["variances"]:
        lines.append("")
        lines.append("VARIANCES ON THE SIGNED RECORD:")
        for variance in document["variances"]:
            lines.append(f"  {variance['code']}: {variance['detail']}")
    lines.append("")
    return "\n".join(lines) + "\n"
