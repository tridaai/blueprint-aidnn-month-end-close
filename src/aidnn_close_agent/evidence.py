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
"""

from __future__ import annotations

import json
from pathlib import Path

from . import guardrails
from .definitions import (
    DefinitionPack,
    bundled_pack_dir,
    load_definition_pack_version,
)
from .errors import EvidenceError
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
            raise EvidenceError(
                f"figure {where} on pack {pack.pack_id} carries "
                f"verifier verdict {figure.status!r}, not 'verified' — "
                "a signed pack should hold no other verdict"
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
    if document["variances"]:
        lines.append("")
        lines.append("VARIANCES ON THE SIGNED RECORD:")
        for variance in document["variances"]:
            lines.append(f"  {variance['code']}: {variance['detail']}")
    lines.append("")
    return "\n".join(lines) + "\n"
