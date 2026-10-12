"""Pre-close readiness: the close does not start on missing
sources; it says what is missing, by name.

The checklist (see :mod:`.guardrails`) has always gated a
build on *presence*: every entity's GL and AR, the group's FX
and CRM, ingested at whatever version arrived. Presence is the
floor, not the expectation. A real close knows more than that
before it starts — which delivery version each source is
supposed to be at, and whether the rate table it received can
actually convert the period's money — and it knows it as a
*record*: an expectation manifest a named controller wrote
for the period, not a constant in policy. This module is the
check that record makes possible:

- **Expected vs received, by name.** Each manifest entry is
  one source slot. The received side is the run's current
  batch for that slot. A slot that never filled is *missing*;
  a slot filled at a version other than the manifest's
  expected version is a version item — *short* below it,
  *ahead* above it. The rule is exact equality, because batch
  versions are per-batch content stamps: a delivery is a
  specific version, and any other version is a different
  delivery — below the expectation the close is starting on
  a superseded extract, above it the manifest predates the
  delivery and the governed remedy is to amend the manifest,
  not to pretend the expectation covered it.
- **The rate table is checked as coverage, not presence.**
  An FX batch can be present and still useless: no table at
  all on the batch, or a table with no rate for a currency
  the period's entities book in. Until now that surfaced late
  and unnamed — a ``KeyError`` inside the engine's conversion,
  mid-build. Readiness names it up front: the currencies the
  governing definition pack's entities book in (other than
  the reporting currency) against the received table.
- **The prior period is reported, not required.** A build
  requires nothing of the prior period: comparatives are
  defined over the prior period's *signed* pack and degrade
  to absent when there is none, by design, and carried items
  flow through signed packs only. So the report states the
  prior period's state — signed (pack cited), no prior close
  on record, or packs on record but none signed — as a named
  fact on the report, never as a failing item. Readiness
  enforces exactly what the build requires, no more.
- **The check is a pure read.** It reads the run, the store's
  batches, the manifest, and the pack records; it registers
  nothing and mutates nothing. What it produces is a report
  whose failing items are named in the words a waiver must
  use to cover them (see :class:`~.schemas.ReadinessWaiver`).

The manifests for the bundled periods are *derived* — from
the batches the closes actually used (see
:func:`derive_entries` and :mod:`.datasets`) — because the
seeded worlds' expectations are a fact about those worlds,
stated as data, not a requirement invented for them.
"""

from __future__ import annotations

from . import comparatives as comparatives_module
from .definitions import DefinitionPack
from .schemas import (
    CloseRun,
    ExpectationManifest,
    ManifestEntry,
    ReadinessEntry,
    ReadinessItem,
    ReadinessReport,
    ReadinessWaiver,
    SourceBatch,
)

FX_SLOT = "GROUP:fx"


def latest_manifest(store, period: str) -> ExpectationManifest | None:
    """The manifest governing ``period``: the highest version
    on record. Amendment is a new version naming the one it
    supersedes, so the latest version is the expectation in
    force; earlier versions stay on record as the chain."""
    manifests = store.list_manifests(period)
    if not manifests:
        return None
    return max(manifests, key=lambda m: m.version)


def waivers_for(store, period: str) -> list[ReadinessWaiver]:
    return store.list_waivers(period)


def waived_item_names(store, period: str) -> set[str]:
    """Every failing-item name any waiver on record for the
    period covers. Coverage is by exact name — the check's
    own words, figures included — re-derived at build time,
    so a waiver written for one failure never stretches to a
    different one that merely shares its slot."""
    names: set[str] = set()
    for waiver in store.list_waivers(period):
        names.update(waiver.items)
    return names


def derive_entries(batches: list[SourceBatch]) -> list[ManifestEntry]:
    """The expectation a set of deliveries implies: one entry
    per slot, at the version of the delivery the close ends
    on — the terminal batch of the slot's supersession chain
    within the set (a batch another batch in the set
    supersedes is not the delivery the close used). Used to
    seed the bundled periods' manifests from their worlds:
    the manifest records what a complete close for the period
    actually took, derived from the world, as data."""
    superseded = {b.supersedes for b in batches if b.supersedes}
    entries: list[ManifestEntry] = []
    for batch in sorted(batches, key=lambda b: b.batch_id):
        if batch.batch_id in superseded:
            continue  # an earlier delivery of the same slot
        scope = batch.entity_id if batch.entity_id else "GROUP"
        entries.append(ManifestEntry(
            slot=f"{scope}:{batch.kind}",
            kind=batch.kind,
            entity_id=batch.entity_id,
            expected_version=batch.version,
            expected_batch_id=batch.batch_id,
        ))
    return entries


def check_readiness(store, run: CloseRun, pack_def: DefinitionPack,
                    manifest: ExpectationManifest | None,
                    ) -> ReadinessReport:
    """Expected vs received for one run, in code. Pure: reads
    the store and the run, writes nothing.

    ``pack_def`` is the definition pack the build would run
    under (the service's selection for the period) — its
    entity currencies are the ones the rate table must cover.
    """
    prior_period = comparatives_module.previous_period(run.period)
    signed_prior = comparatives_module.find_signed_pack(
        store, prior_period)
    if signed_prior is not None:
        prior_state, prior_pack_id = "SIGNED", signed_prior.pack_id
    elif any(p.period == prior_period for p in store.list_packs()):
        prior_state, prior_pack_id = "PRIOR_UNSIGNED", None
    else:
        prior_state, prior_pack_id = "NO_PRIOR_CLOSE", None

    if manifest is None:
        return ReadinessReport(
            period=run.period, run_id=run.run_id,
            status="NO_MANIFEST",
            prior_period=prior_period, prior_state=prior_state,
            prior_pack_id=prior_pack_id,
        )

    entries: list[ReadinessEntry] = []
    items: list[ReadinessItem] = []
    for entry in manifest.entries:
        batch_id = run.current_batches.get(entry.slot)
        batch = store.get_batch(batch_id) if batch_id else None
        if batch is None:
            state = "missing"
            items.append(ReadinessItem(
                name=entry.slot, slot=entry.slot,
                detail=(
                    f"{entry.slot}: expected source not received — "
                    f"the manifest (v{manifest.version}, by "
                    f"{manifest.actor}) expects "
                    + (f"{entry.expected_batch_id} "
                       f"(v{entry.expected_version})"
                       if entry.expected_batch_id
                       else f"a {entry.kind} delivery"
                            + (f" at v{entry.expected_version}"
                               if entry.expected_version is not None
                               else ""))
                    + ", and nothing stands in the slot"
                ),
            ))
        elif entry.expected_version is None \
                or batch.version == entry.expected_version:
            state = "ok"
        else:
            state = "short" if batch.version < entry.expected_version \
                else "ahead"
            name = (f"{entry.slot} (received v{batch.version}, "
                    f"expected v{entry.expected_version})")
            direction = (
                "the delivery is short of the expected version — "
                "the close would start on a superseded extract"
                if state == "short" else
                "the delivery is ahead of the expected version — "
                "the manifest predates this delivery; amend the "
                "manifest to expect it, or waive the difference "
                "by name"
            )
            items.append(ReadinessItem(
                name=name, slot=entry.slot,
                detail=(
                    f"{entry.slot}: received {batch.batch_id} "
                    f"v{batch.version}, manifest v{manifest.version} "
                    f"expects v{entry.expected_version} — {direction}"
                ),
            ))
        entries.append(ReadinessEntry(
            slot=entry.slot, kind=entry.kind,
            entity_id=entry.entity_id,
            expected_version=entry.expected_version,
            expected_batch_id=entry.expected_batch_id,
            received_batch_id=batch.batch_id if batch else None,
            received_version=batch.version if batch else None,
            state=state,
        ))

    items.extend(_rate_items(store, run, pack_def))

    return ReadinessReport(
        period=run.period, run_id=run.run_id,
        manifest_id=manifest.manifest_id,
        manifest_version=manifest.version,
        status="NOT_READY" if items else "READY",
        entries=entries, items=items,
        prior_period=prior_period, prior_state=prior_state,
        prior_pack_id=prior_pack_id,
    )


def _rate_items(store, run: CloseRun,
                pack_def: DefinitionPack) -> list[ReadinessItem]:
    """The rate table's coverage, as failing items. Runs only
    when the FX slot is filled — an unfilled slot is already
    the manifest's missing item, and naming the rates too
    would report one gap twice."""
    batch_id = run.current_batches.get(FX_SLOT)
    if not batch_id:
        return []
    batch = store.get_batch(batch_id)
    if batch is None:
        return []
    if batch.rate_table is None:
        return [ReadinessItem(
            name="GROUP:fx (no rate table)", slot=FX_SLOT,
            detail=(
                f"GROUP:fx: received {batch.batch_id} v{batch.version}, "
                "which carries no rate table — the close has no "
                "rates to convert at"
            ),
        )]
    table = batch.rate_table
    needed = sorted(
        {e["currency"] for e in pack_def.entities}
        - {table.reporting_currency}
    )
    return [
        ReadinessItem(
            name=f"FX:{currency} (no rate in table v{table.version})",
            slot=FX_SLOT,
            detail=(
                f"FX:{currency}: the period's entities book in "
                f"{currency}, but rate table v{table.version} "
                f"(received on {batch.batch_id}) carries no rate "
                f"for it — conversions would fail inside the "
                f"build, unnamed"
            ),
        )
        for currency in needed if currency not in table.rates
    ]


def render_text(report: ReadinessReport) -> str:
    """The report as a controller reads it: one block, every
    failing item named, the prior period's state stated."""
    lines = [f"Readiness — period {report.period}, run {report.run_id}"]
    if report.status == "NO_MANIFEST":
        lines.append(
            "  NO MANIFEST: no expectation manifest governs this "
            "period — there is no stated expectation to check "
            "against, and the standing checklist alone gates "
            "the build."
        )
    else:
        lines.append(
            f"  Manifest: {report.manifest_id} "
            f"(v{report.manifest_version})"
        )
        for entry in report.entries:
            expected = (f"v{entry.expected_version}"
                        if entry.expected_version is not None
                        else "any version")
            received = (f"{entry.received_batch_id} "
                        f"v{entry.received_version}"
                        if entry.received_batch_id else "—")
            lines.append(
                f"  {entry.slot:<12} expected {expected:<4} "
                f"received {received:<16} {entry.state}"
            )
        if report.items:
            lines.append(f"  {report.status} — failing items:")
            for item in report.items:
                lines.append(f"    ✗ {item.name}")
                lines.append(f"      {item.detail}")
        else:
            lines.append(
                "  READY — every expected source received at its "
                "expected version; the rate table covers the "
                "period's currencies."
            )
    prior = {
        "SIGNED": f"signed (pack {report.prior_pack_id})",
        "NO_PRIOR_CLOSE": "no prior close on record",
        "PRIOR_UNSIGNED": "packs on record, none signed",
    }[report.prior_state]
    lines.append(
        f"  Prior period {report.prior_period}: {prior} "
        "(reported, never required)"
    )
    return "\n".join(lines) + "\n"
