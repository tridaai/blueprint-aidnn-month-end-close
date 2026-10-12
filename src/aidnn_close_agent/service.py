"""The service facade: runs, ingestion, pack builds, sign-off.

The API, CLI, demo, and evals all drive the same service, so the
behaviour a test pins is the behaviour the console shows. The
service owns the close discipline the graph does not:

- **the checklist is a gate** — a pack builds only when every
  required source for the period is ingested at its current
  version (:class:`ChecklistIncomplete` otherwise);
- **ingestion moves the world forward** — a superseding batch
  takes its slot, the raw bytes are archived, and every unsigned
  pack built from the old slot set is marked STALE in the same
  step. A stale or blocked pack can never be signed: sign-off
  re-checks the pack's source stamps against the run's current
  ones, so the rule holds even if a marking step were missed;
- **sign-off names its human** — anonymous decisions do not
  exist, and only an AWAITING_CONTROLLER pack can receive one;
- **the signature is a chain's third act** — a named
  preparer states a pack is ready and a named reviewer
  states they reviewed it (see :mod:`.signoff_chain`)
  before any controller signature stands, the three acts
  belonging to three different people; the preparer may
  withdraw the pack before the chain completes, and no one
  may withdraw it after. The controller's act itself —
  the decision record, the SIGNED_OFF status, the run
  closing — is exactly what it was when signing was one
  act: everything downstream keys on it unchanged;
- **the comparative layer is prepared here** — the prior
  period's signed pack, its definition version, and any
  restatement of its sources are assembled at build time (see
  :mod:`.comparatives`); a pack carrying an unacknowledged
  restatement cannot be signed, and a restatement batch is
  received outside any run, because a signed period's run is
  closed and its record is history;
- **dispositions are recorded here, and only here** — a named
  controller's acceptance of a blocking variance (see
  :mod:`.dispositions`) is a service record on the blocked
  pack, actor and reason required, append-only. It changes
  neither the variance nor the pack's status: the close's
  next build re-verifies from source and is presented for
  sign-off only when every blocking variance is covered by a
  governing acceptance, with the acceptances on its face;
- **definition changes are governed here** — a candidate
  definition-pack version's impact is computed as a dry-run
  over a signed period (see :mod:`.governance`) and recorded
  before any activation may cite it; an activation names its
  actor, its reason, and the period it governs from, and can
  never reach a signed period. Which version governs a
  period is computed from those records at run creation and
  again at build, and printed on both;
- **pre-close readiness is governed here** — a period's
  expectation manifest (see :mod:`.readiness`) is recorded by
  a named controller, amended only by a new version; the
  readiness check is a pure read over a run's received
  sources; and the build — the one door every surface uses —
  refuses a period whose check fails, unless a named waiver
  on record covers the failing items exactly. A pack built
  under a manifest states the readiness on its face:
  complete, with the manifest version cited, or waived, with
  the items and the waivers that covered them;
- **the audit evidence bundle is a projection** — generated
  only for a signed pack, assembled from stored records by
  :mod:`.evidence`, checked for completeness before anything
  is written, and stored in the object store under a digest
  the bundle record carries;
- **figure drill-down is a re-performance** — any figure on
  any pack opens into the exact source lines it stands on,
  recomputed by :mod:`.drill` from the pack's stamped sources
  at the stamped rates, and served only when the composition
  foots to the figure (``DRILL_MISMATCH`` otherwise). The
  pack's state rides the drill; blocked and stale packs drill
  on their own stamps, like auditors do;
- **the source watch looks back** — a signed period's
  sources can still move: a corrected extract lands outside
  any run and attaches to nothing. The watch (see
  :mod:`.sourcewatch`) names every stamped source whose
  supersession chain has since advanced, computed on read
  from the signed packs' stamps; a named controller answers
  an item with an acknowledgement covering exactly the tip
  they saw — RESTATEMENT_PLANNED or NO_ACTION, reason
  required either way — and an item whose movement later
  goes through the restatement road reads ANSWERED, derived
  from the answering pack's own record. The watch rebuilds,
  restates, and unsigns nothing; recording an
  acknowledgement writes only the acknowledgement.

Nothing here posts to a ledger, files a return, or moves money:
the signed pack is the end of the line, by design.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import Command

from . import comparatives as comparatives_module
from . import dispositions as dispositions_module
from . import drill as drill_module
from . import evidence as evidence_module
from . import governance as governance_module
from . import guardrails
from . import readiness as readiness_module
from . import signoff_chain as chain_module
from . import sourcewatch as watch_module
from .definitions import DefinitionPack, bundled_pack_dir
from .errors import (
    BatchNotFound,
    BundleNotFound,
    ChecklistIncomplete,
    GateError,
    PackNotFound,
    ReadinessError,
    RunNotFound,
)
from .graph import PackPipeline
from .marts import build_marts, slot_key
from .ports import ConnectorPort, ObjectStorePort
from .schemas import (
    Acknowledgement,
    BoardPack,
    ChainAct,
    CloseRun,
    DefinitionDryRun,
    Disposition,
    EvidenceBundle,
    ExpectationManifest,
    FigureDrill,
    ManifestEntry,
    PackActivation,
    ReadinessReport,
    ReadinessStatement,
    ReadinessWaiver,
    SourceBatch,
    SourceWatchAcknowledgement,
    SourceWatchReport,
    WaiverCitation,
    Withdrawal,
)

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CloseService:
    def __init__(self, pipeline: PackPipeline, store, connector: ConnectorPort,
                 objects: ObjectStorePort, pack_def: DefinitionPack,
                 pack_dirs: list[Path] | None = None) -> None:
        self.pipeline = pipeline
        self.store = store
        self.connector = connector
        self.objects = objects
        self.pack_def = pack_def
        # Where prior definition-pack versions live, for the
        # comparative layer's registry lookups (restatement
        # recomputation runs under the prior period's own pack).
        self.pack_dirs = pack_dirs

    # -- runs ---------------------------------------------------------

    def create_run(self, period: str) -> CloseRun:
        base = f"RUN-{period}"
        run_id, suffix = base, 2
        while self.store.get_run(run_id) is not None:
            run_id = f"{base}-{suffix}"
            suffix += 1
        # The definition selection rule, applied and printed:
        # the version governing this period is computed from
        # the activation records (see governance.select_pack)
        # and recorded on the run — never left implicit in
        # whichever service object happened to be wired.
        pack_def, activation = self.select_pack(period)
        run = CloseRun(
            run_id=run_id, period=period,
            checklist={eid: {} for eid in pack_def.entity_ids()},
            definition_pack_id=pack_def.pack_id,
            definition_pack_version=pack_def.version,
            audit=[{
                "event": "run_created", "at": _now(),
                "detail": f"definition pack {pack_def.pack_id} "
                          f"v{pack_def.version} governs {period}"
                          + (f" (activation "
                             f"{activation.activation_id})"
                             if activation is not None
                             else " (deployment default — no "
                                  "activation governs this period)"),
            }],
            created_at=_now(), updated_at=_now(),
        )
        return self.store.save_run(run)

    def get_run(self, run_id: str) -> CloseRun:
        run = self.store.get_run(run_id)
        if run is None:
            raise RunNotFound(f"no close run {run_id}")
        return run

    def list_runs(self) -> list[CloseRun]:
        return self.store.list_runs()

    def missing(self, run: CloseRun) -> list[str]:
        return guardrails.missing_sources(run, self.pack_def.entity_ids())

    # -- ingestion -----------------------------------------------------

    def ingest(self, run_id: str, batch_ids: list[str]) -> CloseRun:
        run = self.get_run(run_id)
        if run.status == "CLOSED":
            raise GateError(
                f"run {run_id} is closed (a pack was signed); "
                "late sources belong to a new run, not this one"
            )
        for batch_id in batch_ids:
            batch = self.connector.fetch(batch_id)  # BatchNotFound propagates
            # Archive the raw evidence before anything else uses it.
            key = f"extracts/{run.period}/{batch.batch_id}.json"
            self.objects.put(key, batch.model_dump_json().encode("utf-8"),
                             "application/json")
            self.store.save_batch(batch)
            slot = slot_key(batch)
            previous = run.current_batches.get(slot)
            run.current_batches[slot] = batch.batch_id
            if batch.entity_id:
                run.checklist.setdefault(batch.entity_id, {})[batch.kind] = \
                    batch.version
            else:
                run.group_checklist[batch.kind] = batch.version
            if batch.batch_id not in run.ingested_batch_ids:
                run.ingested_batch_ids.append(batch.batch_id)
            for journal in batch.journals:
                flags, _ = guardrails.screen_injection(journal.memo)
                run.injection_flags.extend(
                    f"{batch.entity_id}/{journal.journal_id}: {f}" for f in flags
                )
                for line in journal.lines:
                    line_flags, _ = guardrails.screen_injection(line.memo)
                    run.injection_flags.extend(
                        f"{batch.entity_id}/{journal.journal_id}: {f}"
                        for f in line_flags
                    )
            run.audit.append({
                "event": "ingested", "at": _now(),
                "detail": f"{batch.batch_id} ({batch.kind}"
                          f"{' ' + batch.entity_id if batch.entity_id else ''} "
                          f"v{batch.version})"
                          + (f" supersedes {previous}" if previous else ""),
            })
        run.status = "READY" if not self.missing(run) else "COLLECTING"
        run.updated_at = _now()
        self.store.save_run(run)
        self._mark_stale_packs(run)
        return run

    def receive_restatement(self, batch_id: str) -> SourceBatch:
        """Take delivery of a corrected extract for a period
        whose pack is already signed.

        A signed pack's run is CLOSED and refuses ingestion —
        history is not edited — so a restatement arrives outside
        any run: archived and stored as evidence, attached to
        nothing. Its effect is computed later, when the next
        period's pack is built: the comparative layer walks the
        supersession chain off the signed pack's stamps, finds
        this batch at the end of it, and names what it moved."""
        batch = self.connector.fetch(batch_id)  # BatchNotFound propagates
        key = f"extracts/restated/{batch.batch_id}.json"
        self.objects.put(key, batch.model_dump_json().encode("utf-8"),
                         "application/json")
        self.store.save_batch(batch)
        log.info("restatement received", extra={"batch_id": batch.batch_id})
        return batch

    def _mark_stale_packs(self, run: CloseRun) -> None:
        """Any unsigned pack whose source stamps no longer match
        the run's current batches is stale — marked in the same
        step that moved the sources, never discovered later."""
        for pack in self.store.list_packs(run_id=run.run_id):
            if pack.status in ("SIGNED_OFF", "RETURNED", "STALE",
                               "WITHDRAWN"):
                continue
            if pack.source_versions.batches != self._current_versions(run):
                pack.status = "STALE"
                pack.audit.append({
                    "event": "marked_stale", "at": _now(),
                    "detail": "a source extract or rate table superseded "
                              "the versions this pack was built from",
                })
                pack.updated_at = _now()
                self.store.save_pack(pack)

    def _current_versions(self, run: CloseRun) -> dict[str, int]:
        versions: dict[str, int] = {}
        for batch_id in run.current_batches.values():
            batch = self.store.get_batch(batch_id)
            if batch is not None:
                versions[batch.batch_id] = batch.version
        return versions

    def _current_batches(self, run: CloseRun) -> list:
        batches = []
        for batch_id in run.current_batches.values():
            batch = self.store.get_batch(batch_id)
            if batch is None:
                raise BatchNotFound(
                    f"run {run.run_id} references uningested batch {batch_id}"
                )
            batches.append(batch)
        return batches

    # -- definition governance ------------------------------------------

    def _registry_dirs(self) -> list[Path]:
        dirs: list[Path] = list(self.pack_dirs or [])
        bundled = bundled_pack_dir()
        if bundled not in dirs:
            dirs.append(bundled)
        return dirs

    def definition_versions(self) -> list[DefinitionPack]:
        """Every version of this deployment's pack the registry
        holds, oldest first."""
        return governance_module.registry_versions(
            self.pack_def.pack_id, self._registry_dirs())

    def select_pack(self, period: str,
                    ) -> tuple[DefinitionPack, PackActivation | None]:
        """The selection rule, in one place: the governing
        activation for ``period`` (the latest act whose
        from-period has arrived) names the version, loaded from
        the registry; with no governing activation, the
        deployment's wired pack governs, as it always has."""
        activation = governance_module.governing_activation(
            self.store.list_activations(), period)
        if activation is None:
            return self.pack_def, None
        pack = governance_module.load_version(
            activation.pack_id, activation.to_version,
            self._registry_dirs())
        if pack is None:
            raise GateError(
                f"activation {activation.activation_id} makes "
                f"definition pack {activation.pack_id} "
                f"v{activation.to_version} govern {period}, but "
                "that version is not in the registry — a close "
                "is never computed under a substitute version"
            )
        return pack, activation

    def dry_run_definition_change(
            self, candidate_version: str,
            reference_period: str | None = None) -> DefinitionDryRun:
        """Compute a candidate version's impact over a signed
        period, and record it. Signs nothing, activates
        nothing: the report is the evidence an activation
        will have to cite.

        The reference is the signed pack of ``reference_period``
        (or the latest signed pack on record): the dry-run
        recomputes that period from its stamped sources under
        its own cited version and under the candidate, so the
        change list is the candidate's effect and nothing
        else's. Recomputing the same dry-run returns the
        recorded one — the report is a pure function of its
        inputs, and a recorded report whose digest no longer
        reproduces is a refusal, not a quiet rewrite."""
        candidate = governance_module.load_version(
            self.pack_def.pack_id, candidate_version,
            self._registry_dirs())
        if candidate is None:
            raise GateError(
                f"definition pack {self.pack_def.pack_id} "
                f"v{candidate_version} is not in the registry — "
                "a dry-run measures a version that exists as a "
                "pack file, not a version number in the air"
            )
        if reference_period is not None:
            signed = comparatives_module.find_signed_pack(
                self.store, reference_period)
            if signed is None:
                raise GateError(
                    f"period {reference_period} has no signed "
                    "pack to measure against — a dry-run needs a "
                    "signed reference: the period whose stamped "
                    "sources both versions are recomputed over"
                )
        else:
            signed_candidates = [
                p for p in self.store.list_packs()
                if p.status == "SIGNED_OFF"
            ]
            if not signed_candidates:
                raise GateError(
                    "no signed pack on record — a dry-run "
                    "measures a candidate against a period the "
                    "board has already approved, and there is "
                    "none yet"
                )
            signed = max(signed_candidates,
                         key=lambda p: (p.created_at, p.pack_id))
        if signed.definition_pack_id != candidate.pack_id:
            raise GateError(
                f"signed pack {signed.pack_id} cites definition "
                f"pack {signed.definition_pack_id}, not "
                f"{candidate.pack_id} — versions of one pack are "
                "measured against their own pack's history"
            )
        base = governance_module.load_version(
            signed.definition_pack_id, signed.definition_pack_version,
            self._registry_dirs())
        if base is None:
            raise GateError(
                f"signed pack {signed.pack_id} cites definition "
                f"pack v{signed.definition_pack_version}, which "
                "is not in the registry — its period cannot be "
                "recomputed under its own definitions, so no "
                "honest baseline exists"
            )
        report = governance_module.compute_dry_run(
            self.store, signed, base, candidate, self.pipeline.engine)
        digest = governance_module.report_digest(report)
        dry_run_id = governance_module.dry_run_id_for(
            candidate.pack_id, candidate_version, signed.pack_id)
        existing = self.store.get_dry_run(dry_run_id)
        if existing is not None:
            if existing.digest != digest:
                raise GateError(
                    f"dry-run {dry_run_id} is on record with "
                    f"digest {existing.digest}, but recomputing "
                    f"it now produces {digest} — a definition "
                    "file or a stamped source changed under the "
                    "record, and the recorded impact is not "
                    "quietly rewritten; resolve the registry "
                    "before relying on either"
                )
            return existing
        record = DefinitionDryRun(
            dry_run_id=dry_run_id, report=report, digest=digest,
            computed_at=_now(),
        )
        return self.store.save_dry_run(record)

    def activate_definition_pack(self, version: str, from_period: str,
                                 actor: str, reason: str,
                                 ) -> PackActivation:
        """Make a candidate version govern closes from
        ``from_period`` onward, as a named, recorded act.

        Refusals, each naming its ground: an unnamed actor; a
        missing reason; a version the registry does not hold;
        no dry-run on record for the version (the impact must
        exist before the act, and the act cites it — id and
        digest); the version already governing ``from_period``;
        and a from-period that is already signed (a signed
        period's pack keeps its cited version forever)."""
        if not actor or not actor.strip():
            raise GateError("an activation must name its actor")
        if not reason or not reason.strip():
            raise GateError(
                "an activation must carry a reason — why this "
                "definition change, in the activator's own words"
            )
        candidate = governance_module.load_version(
            self.pack_def.pack_id, version, self._registry_dirs())
        if candidate is None:
            raise GateError(
                f"definition pack {self.pack_def.pack_id} "
                f"v{version} is not in the registry — an "
                "activation governs with a version that exists "
                "as a pack file"
            )
        activations = self.store.list_activations()
        governing = governance_module.governing_activation(
            activations, from_period)
        current = governing.to_version if governing is not None \
            else self.pack_def.version
        if current == version:
            raise GateError(
                f"definition pack v{version} already governs "
                f"{from_period}"
                + (f" under activation {governing.activation_id}"
                   if governing is not None
                   else " as the deployment default")
                + " — an activation that changes nothing is "
                  "not an act, and is not recorded as one"
            )
        signed = comparatives_module.find_signed_pack(
            self.store, from_period)
        if signed is not None:
            raise GateError(
                f"period {from_period} is already signed (pack "
                f"{signed.pack_id}, under definition pack "
                f"v{signed.definition_pack_version}) — an "
                "activation governs only periods not yet "
                "signed; a signed period's cited version never "
                "changes"
            )
        dry_runs = [
            r for r in self.store.list_dry_runs()
            if r.report.pack_id == candidate.pack_id
            and r.report.candidate_version == version
        ]
        if not dry_runs:
            raise GateError(
                f"no dry-run on record for definition pack "
                f"{candidate.pack_id} v{version} — the impact "
                "must be computed and recorded before it can be "
                "activated (run the dry-run against a signed "
                "period first); an activation never precedes "
                "its evidence"
            )
        dry_run = dry_runs[-1]
        governing = governance_module.governing_activation(
            activations, from_period)
        supersedes = governing.activation_id \
            if governing is not None \
            and governing.from_period == from_period else None
        record = PackActivation(
            activation_id=(
                f"ACT-{candidate.pack_id}-{len(activations) + 1}"),
            pack_id=candidate.pack_id,
            from_version=current,
            to_version=version,
            from_period=from_period,
            dry_run_id=dry_run.dry_run_id,
            dry_run_digest=dry_run.digest,
            actor=actor, reason=reason, at=_now(),
            supersedes=supersedes,
        )
        log.info(
            "definition pack activated",
            extra={"activation_id": record.activation_id,
                   "to_version": version, "from_period": from_period,
                   "actor": actor},
        )
        return self.store.save_activation(record)

    def definition_state(self, period: str | None = None) -> dict:
        """The governance state of the deployment's pack: the
        versions on record, the dry-runs, the activations, and
        — for ``period`` — the version the selection rule
        assigns and the act that assigned it."""
        activations = self.store.list_activations()
        state: dict = {
            "pack_id": self.pack_def.pack_id,
            "default_version": self.pack_def.version,
            "registry_versions": [
                p.version for p in self.definition_versions()],
            "dry_runs": [r.model_dump()
                         for r in self.store.list_dry_runs()],
            "activations": [a.model_dump() for a in activations],
        }
        if period is not None:
            activation = governance_module.governing_activation(
                activations, period)
            state["governing"] = {
                "period": period,
                "version": activation.to_version
                if activation is not None else self.pack_def.version,
                "source": "activation" if activation is not None
                else "deployment default",
                "activation_id": activation.activation_id
                if activation is not None else None,
                "from_period": activation.from_period
                if activation is not None else None,
            }
        return state

    # -- pre-close readiness -------------------------------------------

    def record_manifest(self, period: str,
                        entries: list[ManifestEntry], actor: str,
                        note: str) -> ExpectationManifest:
        """Record a named controller's expectation manifest
        for a period: the sources its close expects, slot by
        slot, with the delivery version expected where one is
        stated.

        Append-only, like every governance record here:
        amending what a period expects is a new version of
        the period's manifest naming the one it supersedes —
        so the version that governed a check or a build stays
        citable forever. Refusals name their grounds: an
        unnamed author; a missing note (where the expectation
        comes from, in the author's own words); no entries
        (an expectation that expects nothing governs nothing);
        a slot stated twice, or a slot that does not match
        its own entity and kind."""
        if not actor or not actor.strip():
            raise GateError("a manifest must name its author")
        if not note or not note.strip():
            raise GateError(
                "a manifest must carry a note — where this "
                "expectation comes from, in the author's own "
                "words"
            )
        if not entries:
            raise GateError(
                "a manifest with no entries expects nothing, "
                "and an expectation that expects nothing "
                "governs nothing — name at least one source"
            )
        seen: set[str] = set()
        for entry in entries:
            expected_slot = (
                f"{entry.entity_id or 'GROUP'}:{entry.kind}")
            if entry.slot != expected_slot:
                raise GateError(
                    f"manifest entry for {entry.kind}"
                    f"{' ' + entry.entity_id if entry.entity_id else ''} "
                    f"carries slot {entry.slot!r}, but its slot "
                    f"is {expected_slot!r} — the slot is the "
                    "identity a delivery fills, and it is "
                    "derived, never restated"
                )
            if entry.slot in seen:
                raise GateError(
                    f"manifest names slot {entry.slot} twice — "
                    "one expectation per slot"
                )
            seen.add(entry.slot)
            if entry.expected_version is not None \
                    and entry.expected_version < 1:
                raise GateError(
                    f"manifest entry {entry.slot} expects "
                    f"version {entry.expected_version} — "
                    "delivery versions start at 1"
                )
        existing = self.store.list_manifests(period)
        supersedes = None
        if existing:
            supersedes = max(
                existing, key=lambda m: m.version).manifest_id
        record = ExpectationManifest(
            manifest_id=f"MAN-{period}-{len(existing) + 1}",
            period=period,
            version=len(existing) + 1,
            actor=actor, note=note, entries=list(entries),
            supersedes=supersedes, at=_now(),
        )
        log.info(
            "expectation manifest recorded",
            extra={"manifest_id": record.manifest_id,
                   "period": period, "actor": actor},
        )
        return self.store.save_manifest(record)

    def list_manifests(self, period: str | None = None,
                       ) -> list[ExpectationManifest]:
        return self.store.list_manifests(period)

    def readiness(self, run_id: str) -> ReadinessReport:
        """The pre-close readiness check for a run: expected
        vs received, computed in code (see :mod:`.readiness`).
        A pure read — it registers nothing and mutates
        nothing — against the manifest governing the run's
        period (or NO_MANIFEST, stated, when none does)."""
        run = self.get_run(run_id)
        pack_def, _ = self.select_pack(run.period)
        manifest = readiness_module.latest_manifest(
            self.store, run.period)
        return readiness_module.check_readiness(
            self.store, run, pack_def, manifest)

    def record_waiver(self, period: str, items: list[str],
                      actor: str, reason: str) -> ReadinessWaiver:
        """Record a named controller's waiver: this period's
        close may be built despite these exact readiness
        failures.

        Refusals, each naming its ground: an unnamed
        controller; a missing reason; a blanket waiver (no
        items named — a licence covering whatever turns out
        to be missing is not a record a controller may
        make); a period already signed (a waiver governs a
        close still to be built; history needs no licence);
        no close run for the period (readiness is checked
        against a run's received sources — there is nothing
        to waive against); no manifest governing the period
        (no stated expectation, so no named failure exists to
        accept); and any item the period's current check is
        not failing on — a waiver covers a gap the check
        actually found, by its exact name."""
        if not actor or not actor.strip():
            raise GateError("a readiness waiver must name its controller")
        if not reason or not reason.strip():
            raise GateError(
                "a readiness waiver must carry a reason — why "
                "this close may start short-handed, in the "
                "controller's own words"
            )
        named = list(dict.fromkeys(
            item.strip() for item in items if item and item.strip()))
        if not named:
            raise GateError(
                "a readiness waiver must name the items it "
                "covers — a blanket waiver, covering whatever "
                "turns out to be missing, is not a record a "
                "controller may make"
            )
        signed = comparatives_module.find_signed_pack(
            self.store, period)
        if signed is not None:
            raise GateError(
                f"period {period} is already signed (pack "
                f"{signed.pack_id}) — a waiver governs a close "
                "still to be built; history needs no licence"
            )
        runs = [r for r in self.store.list_runs()
                if r.period == period]
        if not runs:
            raise GateError(
                f"no close run exists for period {period} — "
                "readiness is checked against a run's received "
                "sources, and there is nothing to waive against"
            )
        report = self.readiness(runs[-1].run_id)
        if report.manifest_id is None:
            raise GateError(
                f"no manifest governs period {period} — there "
                "is no stated expectation, so no named failure "
                "exists for a waiver to accept"
            )
        failing = [item.name for item in report.items]
        for item in named:
            if item not in failing:
                raise GateError(
                    f"waiver item {item!r} is not a failing "
                    f"item for period {period} — a waiver "
                    "covers a gap the readiness check actually "
                    "found, named exactly"
                    + (f" (currently failing: "
                       f"{', '.join(failing)})" if failing
                       else " (readiness is currently complete "
                            "for the period's latest run)")
                )
        record = ReadinessWaiver(
            waiver_id=(
                f"WVR-{period}-"
                f"{len(self.store.list_waivers(period)) + 1}"),
            period=period, items=named,
            actor=actor, reason=reason, at=_now(),
        )
        log.info(
            "readiness waiver recorded",
            extra={"waiver_id": record.waiver_id, "period": period,
                   "items": named, "actor": actor},
        )
        return self.store.save_waiver(record)

    def list_waivers(self, period: str | None = None,
                     ) -> list[ReadinessWaiver]:
        return self.store.list_waivers(period)

    # -- the post-sign-off source watch ---------------------------

    def source_watch(self, period: str | None = None,
                     ) -> SourceWatchReport:
        """The post-sign-off source watch (see
        :mod:`.sourcewatch`): every source that moved behind
        a signed pack, computed in code from the signed
        packs' stamps against the supersession chains as
        they now stand. A pure read — it registers nothing
        and mutates nothing."""
        return watch_module.compute_watch(self.store, period)

    def list_watch_acknowledgements(
            self, period: str | None = None,
            ) -> list[SourceWatchAcknowledgement]:
        return self.store.list_watch_acknowledgements(period)

    def acknowledge_source_movement(
            self, period: str, slot: str, tip_batch_id: str,
            disposition: str, actor: str, reason: str,
            ) -> SourceWatchAcknowledgement:
        """Record a named controller's answer to one source
        movement behind a signed pack: RESTATEMENT_PLANNED
        (a restatement will follow — the acknowledgement
        records the intent and restates nothing itself) or
        NO_ACTION (the controller's stated judgement that
        this movement needs none), the reason required
        either way.

        The record covers exactly the movement it names —
        one period, one slot, and the chain tip the
        controller saw. Refusals, each naming its ground: an
        unnamed controller; a missing reason; a disposition
        that is neither of the two; a period with no signed
        pack (the watch covers signed periods only — a close
        still in flight finds its changed inputs at its own
        gate); a slot the signed pack carries no source in,
        or whose chain has not moved; a tip that is not the
        chain's current tip (the movement was overtaken —
        read the watch again); a movement already answered
        through the restatement road; and a movement already
        acknowledged at that tip, whose record stands and is
        named. Recording writes only the acknowledgement:
        the signed pack is history and is not touched."""
        if not actor or not actor.strip():
            raise GateError(
                "a source-watch acknowledgement must name its "
                "controller")
        if not reason or not reason.strip():
            raise GateError(
                "a source-watch acknowledgement must carry a "
                "reason — what the controller made of the "
                "movement, in their own words")
        if disposition not in ("RESTATEMENT_PLANNED", "NO_ACTION"):
            raise GateError(
                f"disposition must be RESTATEMENT_PLANNED or "
                f"NO_ACTION, got {disposition!r} — the two "
                "answers a controller may record for a movement")
        pack = comparatives_module.find_signed_pack(
            self.store, period)
        if pack is None:
            raise GateError(
                f"period {period} has no signed pack — the "
                "watch covers signed periods only; a close "
                "still in flight finds its changed inputs at "
                "its own gate, and there is no signed record "
                "for an acknowledgement to answer for")
        report = watch_module.compute_watch(self.store, period)
        item = next((i for i in report.items if i.slot == slot),
                    None)
        if item is None:
            stamped_slots = {}
            for batch_id in pack.source_versions.batches:
                batch = self.store.get_batch(batch_id)
                if batch is not None:
                    stamped_slots[slot_key(batch)] = batch_id
            if slot not in stamped_slots:
                raise GateError(
                    f"signed pack {pack.pack_id} carries no "
                    f"source in slot {slot} — its stamped "
                    f"sources stand in: "
                    + ", ".join(sorted(stamped_slots)))
            raise GateError(
                f"the {slot} source behind signed pack "
                f"{pack.pack_id} has not moved — its chain "
                f"still ends at {stamped_slots[slot]}, the "
                "delivery the pack signed against, and there "
                "is no movement to acknowledge")
        if item.state == "ANSWERED":
            raise GateError(
                f"the {slot} movement behind signed pack "
                f"{pack.pack_id} was already answered by "
                f"signed pack {item.answered_by_pack_id}, "
                "whose acknowledged restatement report names "
                "it — there is nothing left to acknowledge")
        if tip_batch_id != item.tip_batch_id:
            raise GateError(
                f"the acknowledgement names tip {tip_batch_id}, "
                f"but the {slot} chain behind signed pack "
                f"{pack.pack_id} now ends at {item.tip_batch_id} "
                f"(v{item.tip_version}) — an acknowledgement "
                "covers exactly the movement it saw; read the "
                "watch again and answer the movement that "
                "stands")
        if item.state == "ACKNOWLEDGED":
            standing = next(
                a for a in self.store.list_watch_acknowledgements(
                    period)
                if a.slot == slot
                and a.tip_batch_id == item.tip_batch_id)
            raise GateError(
                f"the {slot} movement to {item.tip_batch_id} "
                f"was already acknowledged by {standing.actor} "
                f"({standing.disposition}, record "
                f"{standing.ack_id}) — that record stands; a "
                "further answer waits for a further movement")
        record = SourceWatchAcknowledgement(
            ack_id=(
                f"SWK-{period}-"
                f"{len(self.store.list_watch_acknowledgements(period)) + 1}"),
            period=period, pack_id=pack.pack_id, slot=slot,
            signed_batch_id=item.signed_batch_id,
            signed_version=item.signed_version,
            tip_batch_id=item.tip_batch_id,
            tip_version=item.tip_version,
            disposition=disposition, actor=actor, reason=reason,
            at=_now(),
        )
        log.info(
            "source movement acknowledged",
            extra={"ack_id": record.ack_id, "period": period,
                   "slot": slot, "tip_batch_id": item.tip_batch_id,
                   "disposition": disposition, "actor": actor},
        )
        return self.store.save_watch_acknowledgement(record)

    def _readiness_gate(self, run: CloseRun,
                        pack_def: DefinitionPack,
                        ) -> ReadinessStatement | None:
        """The build's readiness gate, at the one door every
        surface builds through. Returns the statement the pack
        will carry on its face, or ``None`` when no manifest
        governs the period (the standing checklist already
        gated the build; there is no stated expectation to
        state). Raises :class:`ReadinessError` — naming every
        uncovered item, in the check's own words — when the
        check fails beyond what the period's waivers cover."""
        manifest = readiness_module.latest_manifest(
            self.store, run.period)
        if manifest is None:
            return None
        report = readiness_module.check_readiness(
            self.store, run, pack_def, manifest)
        if not report.items:
            return ReadinessStatement(
                manifest_id=manifest.manifest_id,
                manifest_version=manifest.version,
                status="COMPLETE",
                expected_count=len(manifest.entries),
            )
        waivers = readiness_module.waivers_for(self.store, run.period)
        covered_by: dict[str, ReadinessWaiver] = {}
        for waiver in waivers:
            for name in waiver.items:
                covered_by.setdefault(name, waiver)
        uncovered = [item for item in report.items
                     if item.name not in covered_by]
        if uncovered:
            raise ReadinessError(
                f"run {run.run_id} cannot build a pack: "
                f"readiness for period {run.period} under "
                f"manifest {manifest.manifest_id} "
                f"(v{manifest.version}) fails on "
                + "; ".join(
                    f"{item.name} — {item.detail}"
                    for item in uncovered)
                + " — the close does not start on missing "
                  "sources: ingest them, amend the manifest, "
                  "or record a waiver naming exactly the "
                  "items accepted"
            )
        citations: list[WaiverCitation] = []
        for waiver in waivers:
            covered_here = [item.name for item in report.items
                            if covered_by.get(item.name) is waiver]
            if covered_here:
                citations.append(WaiverCitation(
                    waiver_id=waiver.waiver_id, actor=waiver.actor,
                    reason=waiver.reason, items=covered_here))
        return ReadinessStatement(
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.version,
            status="WAIVED",
            expected_count=len(manifest.entries),
            waived_items=[item.name for item in report.items],
            waivers=citations,
        )

    # -- pack build ------------------------------------------------------

    def build_pack(self, run_id: str) -> BoardPack:
        run = self.get_run(run_id)
        missing = self.missing(run)
        if missing:
            raise ChecklistIncomplete(
                f"run {run_id} cannot build a pack; still waiting for: "
                + ", ".join(missing)
            )
        batches = self._current_batches(run)
        # The build runs under the version the selection rule
        # assigns to the run's period — which may have moved
        # since the run was created (an activation landed in
        # between); the pack's own audit names it when it has.
        pack_def, activation = self.select_pack(run.period)
        # The readiness gate: when a manifest governs the
        # period, the check must pass — or be waived, item by
        # exact item — before anything is computed. The
        # statement it returns rides the build into the pack,
        # where the verify step states it on the face.
        readiness_statement = self._readiness_gate(run, pack_def)
        marts = build_marts(batches, pack_def)
        pack_id = f"PACK-{run.run_id}-{len(run.pack_ids) + 1}"
        # The comparative layer is prepared here, where the
        # store lives: the prior period's signed pack, the
        # definition versions on both sides, and whether the
        # prior period's sources have been restated since.
        comparative_ctx = comparatives_module.prepare_comparatives(
            self.store, pack_def, run.period, self.pack_dirs
        )
        # The governance layer likewise: when this build is the
        # first governed by a newly activated version, the
        # change statement the pack carries on its face.
        change_statement = governance_module.prepare_change_statement(
            self.store, run.period, pack_def, activation)
        self.pipeline.contexts[pack_id] = {
            "marts": marts, "batches": batches,
            "pack_def": pack_def,
            "readiness": readiness_statement,
            "definition_change": change_statement,
            "selection_note": (
                f"definition pack v{pack_def.version} governs "
                f"{run.period}"
                + (f" (activation {activation.activation_id})"
                   if activation is not None
                   else " (deployment default)")
                + (f"; the run was created expecting "
                   f"v{run.definition_pack_version}"
                   if run.definition_pack_version
                   and run.definition_pack_version != pack_def.version
                   else "")
            ),
            "comparatives": comparative_ctx,
            # The disposition layer, prepared here for the same
            # reason: the run's governing acceptances (a rebuild
            # is presented for sign-off when every blocking
            # variance is covered by one) and the prior signed
            # pack's carried acceptances (re-tested against this
            # build's variances as opening items).
            "dispositions": dispositions_module.governing_dispositions(
                self.store, run.run_id),
            "carried": dispositions_module.prepare_carried(
                self.store, run.period),
        }
        config = {"configurable": {"thread_id": pack_id}}
        state = {"run_id": run.run_id, "pack_id": pack_id, "period": run.period}
        self.pipeline.graph.invoke(state, config=config)
        run.pack_ids.append(pack_id)
        run.updated_at = _now()
        self.store.save_run(run)
        return self.get_pack(pack_id)

    def get_pack(self, pack_id: str) -> BoardPack:
        pack = self.store.get_pack(pack_id)
        if pack is None:
            raise PackNotFound(f"no board pack {pack_id}")
        return pack

    def list_packs(self, run_id: str | None = None) -> list[BoardPack]:
        return self.store.list_packs(run_id=run_id)

    # -- the gate ---------------------------------------------------------

    def prepare_pack(self, pack_id: str, actor: str,
                     note: str = "") -> BoardPack:
        """Record the chain's first act: a named preparer
        states the pack is ready for review.

        The act stamps the pack as it stands — figure and
        variance counts, the dispositions on its face, the
        readiness statement's status — because that is what
        the preparer is vouching for. Preparation is only
        possible on an AWAITING_CONTROLLER pack: the blocking
        discipline has already bitten at verification, so a
        blocked pack cannot even be prepared (its breaks are
        fixed at the source, or accepted on the record and
        the close rebuilt — the chain wraps the gate, it
        does not soften it)."""
        if not actor or not actor.strip():
            raise GateError("a preparation must name its preparer")
        pack = self.get_pack(pack_id)
        if pack.status != "AWAITING_CONTROLLER":
            raise GateError(
                f"pack {pack_id} is {pack.status}; only "
                "AWAITING_CONTROLLER packs can be prepared — a "
                "blocked pack is fixed by fixing its sources, "
                "or presented by accepting its breaks on the "
                "record (a disposition per blocking variance, "
                "then a rebuild), a stale pack by rebuilding "
                "it, and a withdrawn or decided pack is out of "
                "the chain for good"
            )
        existing = chain_module.preparer_of(pack)
        if existing is not None:
            raise GateError(
                f"pack {pack_id} was already prepared by "
                f"{existing.actor} — preparation is recorded "
                "once; to start over, the preparer withdraws "
                "the pack and the close is rebuilt"
            )
        pack.signoff_chain.append(ChainAct(
            role="preparer", actor=actor, at=_now(), note=note,
            **chain_module.snapshot(pack),
        ))
        pack.audit.append({
            "event": "pack_prepared", "at": _now(),
            "detail": f"prepared by {actor}",
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return pack

    def review_pack(self, pack_id: str, actor: str,
                    note: str) -> BoardPack:
        """Record the chain's second act: a named reviewer —
        never the preparer — states they reviewed the pack,
        in their own words.

        The act stamps the pack as it stands at review time:
        the variances, dispositions, and readiness statement
        the reviewer saw are counted on the act, so the
        record shows what the review covered."""
        if not actor or not actor.strip():
            raise GateError("a review must name its reviewer")
        if not note or not note.strip():
            raise GateError(
                "a review must carry a note — what was "
                "reviewed, in the reviewer's own words"
            )
        pack = self.get_pack(pack_id)
        if pack.status != "AWAITING_CONTROLLER":
            raise GateError(
                f"pack {pack_id} is {pack.status}; only "
                "AWAITING_CONTROLLER packs can be reviewed"
            )
        preparer = chain_module.preparer_of(pack)
        if preparer is None:
            raise GateError(
                f"pack {pack_id} has not been prepared — the "
                "chain runs in order: a named preparer states "
                "the pack is ready before a review can stand "
                "on it"
            )
        existing = chain_module.reviewer_of(pack)
        if existing is not None:
            raise GateError(
                f"pack {pack_id} was already reviewed by "
                f"{existing.actor} — a review is recorded once"
            )
        if actor == preparer.actor:
            raise GateError(
                f"{actor} prepared pack {pack_id} and cannot "
                "also review it — preparation and review are "
                "two acts by two people, or the chain is one "
                "person talking to themselves"
            )
        pack.signoff_chain.append(ChainAct(
            role="reviewer", actor=actor, at=_now(), note=note,
            **chain_module.snapshot(pack),
        ))
        pack.audit.append({
            "event": "pack_reviewed", "at": _now(),
            "detail": f"reviewed by {actor}: {note}",
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return pack

    def withdraw_pack(self, pack_id: str, actor: str,
                      reason: str) -> BoardPack:
        """Record the preparer taking a pack back before the
        chain completes: a named act with a reason, on the
        pack's record.

        The pack leaves the gate as WITHDRAWN; the close is
        rebuilt instead, and the withdrawn pack is never
        edited back into play. Only the preparer who prepared
        it can withdraw it — the act undoes their own
        statement of readiness, nobody else's. After the
        controller's signature there is no withdrawal at all:
        a signed pack is immutable, and a restated period is
        corrected by the restatement machinery, not by
        taking history back."""
        if not actor or not actor.strip():
            raise GateError("a withdrawal must name its preparer")
        if not reason or not reason.strip():
            raise GateError(
                "a withdrawal must carry a reason — why the "
                "pack is being taken back, in the preparer's "
                "own words"
            )
        pack = self.get_pack(pack_id)
        if pack.status == "SIGNED_OFF":
            raise GateError(
                f"pack {pack_id} is signed; a signed pack "
                "cannot be withdrawn — the signature stands, "
                "and a period that must be corrected is "
                "corrected by the restatement machinery, not "
                "by withdrawing history"
            )
        if pack.status != "AWAITING_CONTROLLER":
            raise GateError(
                f"pack {pack_id} is {pack.status}; only a "
                "pack standing at the gate can be withdrawn"
            )
        preparer = chain_module.preparer_of(pack)
        if preparer is None:
            raise GateError(
                f"pack {pack_id} has not been prepared — "
                "there is no statement of readiness to take "
                "back; a pack nobody has taken up is simply "
                "left, and a rebuild supersedes it"
            )
        if actor != preparer.actor:
            raise GateError(
                f"pack {pack_id} was prepared by "
                f"{preparer.actor}; only its preparer can "
                "withdraw it — the withdrawal undoes their "
                "own statement of readiness"
            )
        pack.withdrawal = Withdrawal(actor=actor, reason=reason,
                                     at=_now())
        pack.status = "WITHDRAWN"
        pack.audit.append({
            "event": "pack_withdrawn", "at": _now(),
            "detail": f"withdrawn by {actor}: {reason}",
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return pack

    def sign_off(self, pack_id: str, decision: str, actor: str,
                 reason: str = "") -> BoardPack:
        if decision not in ("sign", "return"):
            raise GateError(f"decision must be 'sign' or 'return', got {decision!r}")
        if not actor or not actor.strip():
            raise GateError("a sign-off must name its controller")
        pack = self.get_pack(pack_id)
        if pack.status != "AWAITING_CONTROLLER":
            raise GateError(
                f"pack {pack_id} is {pack.status}; only AWAITING_CONTROLLER "
                "packs can be signed — a blocked pack is fixed by fixing its "
                "sources, or presented by accepting its breaks on the "
                "record (a disposition per blocking variance, then a "
                "rebuild), a stale pack by rebuilding it"
            )
        run = self.get_run(pack.run_id)
        if pack.source_versions.batches != self._current_versions(run):
            raise GateError(
                f"pack {pack_id} was built from superseded sources; "
                "rebuild it before signing"
            )
        if pack.restatement is not None \
                and pack.restatement_acknowledgement is None:
            raise GateError(
                f"pack {pack_id} carries an unacknowledged restatement "
                f"of {pack.restatement.prior_period} (signed pack "
                f"{pack.restatement.prior_pack_id}): a named controller "
                "must acknowledge the restatement on the record before "
                "this pack can be signed — the signed prior pack is "
                "not changed by acknowledging, and neither is this one"
            )
        # The chain gate: the signature is the chain's third
        # act, and it is refused until the first two stand —
        # and refused to either earlier hand. Every refusal
        # above keeps its own ground and its own order; the
        # chain is the last gate the signature passes.
        preparer = chain_module.preparer_of(pack)
        if preparer is None:
            raise GateError(
                f"pack {pack_id} has not been prepared — a "
                "signature is the third act of a chain: a "
                "named preparer states the pack is ready, a "
                "named reviewer states they reviewed it, and "
                "only then does a controller sign"
            )
        reviewer = chain_module.reviewer_of(pack)
        if reviewer is None:
            raise GateError(
                f"pack {pack_id} was prepared by "
                f"{preparer.actor} but has not been reviewed "
                "— the chain runs in order: preparation, "
                "review, signature"
            )
        if actor in (preparer.actor, reviewer.actor):
            raise GateError(
                f"{actor} already stands on pack {pack_id}'s "
                f"chain as its {preparer.role if actor == preparer.actor else reviewer.role} "
                "and cannot also sign it — preparation, "
                "review, and signature are three acts by "
                "three different people"
            )
        config = {"configurable": {"thread_id": pack_id}}
        self.pipeline.graph.invoke(
            Command(resume={"decision": decision, "actor": actor,
                            "reason": reason}),
            config=config,
        )
        return self.get_pack(pack_id)

    def acknowledge_restatement(self, pack_id: str, actor: str,
                                note: str) -> BoardPack:
        """Record a named controller's acknowledgement of the
        restatement a pack carries.

        The acknowledgement changes nothing else: not the signed
        prior pack (history), not this pack's figures or its
        variance (the restatement stays named on the record
        permanently). It is the gate's evidence that a human saw
        the thing the gate was holding the signature for."""
        if not actor or not actor.strip():
            raise GateError("an acknowledgement must name its controller")
        if not note or not note.strip():
            raise GateError(
                "an acknowledgement must carry a note — what was "
                "reviewed, in the controller's own words"
            )
        pack = self.get_pack(pack_id)
        if pack.restatement is None:
            raise GateError(
                f"pack {pack_id} carries no restatement to acknowledge"
            )
        if pack.restatement_acknowledgement is not None:
            raise GateError(
                f"the restatement on pack {pack_id} was already "
                f"acknowledged by "
                f"{pack.restatement_acknowledgement.actor}"
            )
        if pack.status not in ("AWAITING_CONTROLLER", "BLOCKED"):
            raise GateError(
                f"pack {pack_id} is {pack.status}; a restatement can "
                "only be acknowledged on a live pack"
            )
        pack.restatement_acknowledgement = Acknowledgement(
            actor=actor, note=note, at=_now()
        )
        pack.audit.append({
            "event": "restatement_acknowledged", "at": _now(),
            "detail": f"{actor}: {note}",
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return pack

    def record_disposition(self, pack_id: str, *, code: str, actor: str,
                           reason: str, entity_id: str | None = None,
                           metric_id: str | None = None,
                           subject: str | None = None) -> BoardPack:
        """Record a named controller's acceptance of one blocking
        variance on a blocked pack: ACCEPTED_CARRY, with a reason.

        The record changes nothing else — not the variance (it
        stands on the pack word for word), not the pack's status
        (it stays BLOCKED; the acceptance is presented by the
        close's next build, which re-verifies from source and is
        presented for sign-off only when every blocking variance
        is covered). Recording is append-only: accepting the same
        break again supersedes the governing record with a new
        one naming it, and the chain stays on the pack.

        Refusals, each naming its ground: an unnamed controller;
        a missing reason; a pack that is not BLOCKED (a signed
        pack is history, an awaiting pack has no blocking
        variance to accept); a code the pack does not carry, or
        carries only as the restatement variance — that one is
        governed by the acknowledgement, not by disposition,
        because it holds a signature rather than blocking a
        pack; and a code that names more than one break on the
        pack with no subject to tell them apart."""
        if not actor or not actor.strip():
            raise GateError("a disposition must name its controller")
        if not reason or not reason.strip():
            raise GateError(
                "a disposition must carry a reason — why this break "
                "is accepted, in the controller's own words"
            )
        pack = self.get_pack(pack_id)
        if pack.status != "BLOCKED":
            raise GateError(
                f"pack {pack_id} is {pack.status}; dispositions are "
                "recorded on a BLOCKED pack — a signed pack is "
                "history, a stale pack is rebuilt first, and an "
                "awaiting pack has no blocking variance to accept"
            )
        if code in dispositions_module.NON_BLOCKING_CODES:
            raise GateError(
                f"{code} is not a blocking variance and cannot be "
                "dispositioned: it does not hold this pack at "
                "BLOCKED — it holds the signature, and it is "
                "governed by the restatement acknowledgement, "
                "which is the record a controller makes for it"
            )
        candidates = [
            v for v in dispositions_module.blocking_variances(pack)
            if v.code == code and v.entity_id == entity_id
            and v.metric_id == metric_id
        ]
        if not candidates:
            raise GateError(
                f"pack {pack_id} carries no blocking variance "
                f"{code}"
                + (f" for entity {entity_id}" if entity_id else "")
                + (f" on metric {metric_id}" if metric_id else "")
                + " — a disposition accepts a break the verifier "
                "actually computed, by its name"
            )
        if len(candidates) > 1 or subject is not None:
            named = [
                v for v in candidates
                if dispositions_module.subject_for(pack, v)
                == (subject or "")
            ]
            if len(named) != 1:
                subjects = sorted({
                    dispositions_module.subject_for(pack, v)
                    for v in candidates
                })
                raise GateError(
                    f"{code} names {len(candidates)} breaks on pack "
                    f"{pack_id}; name the one being accepted by its "
                    f"subject ({', '.join(subjects)})"
                )
            candidates = named
        variance = candidates[0]
        var_subject = dispositions_module.subject_for(pack, variance)
        core = dispositions_module.core_key(
            code, entity_id, metric_id, var_subject)
        # Supersession: the governing record for this exact
        # break on this pack, if one stands, is replaced — by a
        # new record naming it, never by an edit.
        supersedes = None
        for existing in pack.dispositions:
            if (existing.code, existing.entity_id, existing.metric_id,
                    existing.subject, existing.detail) == (
                    code, entity_id, metric_id, var_subject,
                    variance.detail) and not any(
                    d.supersedes == existing.disposition_id
                    for d in pack.dispositions):
                supersedes = existing.disposition_id
        # Lineage: a break that opened this pack as a carried
        # item and still breaks (or came back mutated) keeps its
        # origin; its acceptance here is the next carry.
        origin_period, origin_pack_id, carry_number = \
            pack.period, pack.pack_id, 1
        for item in pack.opening_items:
            if (item.code, item.entity_id, item.metric_id,
                    item.subject) == core \
                    and item.retest in ("STILL_PRESENT", "MUTATED"):
                origin_period = item.origin_period
                origin_pack_id = item.origin_pack_id
                carry_number = item.carry_number + 1
                break
        record = Disposition(
            disposition_id=(
                f"DISP-{pack.pack_id}-{len(pack.dispositions) + 1}"),
            pack_id=pack.pack_id,
            run_id=pack.run_id,
            period=pack.period,
            code=code,
            entity_id=entity_id,
            metric_id=metric_id,
            subject=var_subject,
            detail=variance.detail,
            actor=actor,
            reason=reason,
            at=_now(),
            supersedes=supersedes,
            origin_period=origin_period,
            origin_pack_id=origin_pack_id,
            carry_number=carry_number,
        )
        pack.dispositions.append(record)
        pack.audit.append({
            "event": "variance_dispositioned", "at": _now(),
            "detail": f"{record.disposition_id}: {code}"
                      f"{f' ({var_subject})' if var_subject else ''} "
                      f"accepted and carried by {actor} — {reason}"
                      + (f" (carry {carry_number}, first accepted on "
                         f"{origin_pack_id} in {origin_period})"
                         if carry_number > 1 else "")
                      + (f"; supersedes {supersedes}" if supersedes
                         else ""),
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return pack

    # -- figure drill-down -------------------------------------------

    def figure_drill(self, pack_id: str, metric_id: str,
                     entity_id: str | None = None) -> FigureDrill:
        """Open one figure on a pack into the source lines it
        stands on: a re-performance by :mod:`.drill` over the
        pack's stamped sources, under the definitions the pack
        cites (resolved the evidence layer's way — the version
        on record or a refusal, never a substitute).

        Any pack state may be drilled — the drill is computed
        from the pack's stamps, so it stays true of the pack
        after the world moves — and the state is named on the
        drill. Refusals name their ground: no such figure
        (:class:`DrillNotFound`), a stamped source missing or
        moved, an unresolvable definition version, or a
        composition that does not foot to the figure
        (``DRILL_MISMATCH``)."""
        pack = self.get_pack(pack_id)
        definitions = evidence_module.resolve_definitions(self, pack)
        return drill_module.build_drill(
            self.store, pack, definitions, metric_id, entity_id)

    # -- audit evidence -------------------------------------------------

    def generate_evidence(self, pack_id: str) -> EvidenceBundle:
        """Generate (or return) the audit evidence bundle for a
        signed pack.

        Generation is gated and checked in
        :func:`evidence.assemble_bundle`: only a SIGNED_OFF pack
        gets a bundle, and any completeness gap refuses with the
        gap named, before anything is written. The bundle is a
        pure projection of stored records, so regeneration is
        byte-identical by construction; when a bundle already
        exists and its stored bytes still hash to the recorded
        digest, it is returned as-is — the record, keys, and
        bytes are one artifact and are never quietly rewritten.
        """
        pack = self.get_pack(pack_id)
        document = evidence_module.assemble_bundle(self, pack)
        json_bytes = evidence_module.canonical_json(document)
        digest = hashlib.sha256(json_bytes).hexdigest()
        bundle_id = evidence_module.bundle_id_for(pack.pack_id)
        existing = self.store.get_bundle(bundle_id)
        if existing is not None and existing.sha256 == digest \
                and self.objects.exists(existing.json_key):
            stored = self.objects.get(existing.json_key)
            if hashlib.sha256(stored).hexdigest() == existing.sha256:
                return existing
        json_key, text_key = evidence_module.bundle_keys(pack)
        self.objects.put(json_key, json_bytes, "application/json")
        self.objects.put(
            text_key,
            evidence_module.render_text(document).encode("utf-8"),
            "text/plain",
        )
        record = EvidenceBundle(
            bundle_id=bundle_id,
            pack_id=pack.pack_id,
            run_id=pack.run_id,
            period=pack.period,
            json_key=json_key,
            text_key=text_key,
            sha256=digest,
            figure_count=len(document["figures"]),
            manifest_count=len(document["source_manifest"]),
            generated_at=_now(),
        )
        self.store.save_bundle(record)
        log.info(
            "evidence bundle generated",
            extra={"pack_id": pack.pack_id, "bundle_id": bundle_id,
                   "sha256": digest},
        )
        return record

    def get_evidence(self, pack_id: str) -> EvidenceBundle:
        """The bundle record for a pack, or a named miss —
        generation is an explicit act, never a read side effect."""
        self.get_pack(pack_id)  # PackNotFound before BundleNotFound
        bundles = self.store.list_bundles(pack_id=pack_id)
        if not bundles:
            raise BundleNotFound(
                f"no evidence bundle has been generated for pack "
                f"{pack_id} — generate it first"
            )
        return bundles[0]

    def evidence_download(self, pack_id: str, fmt: str) -> tuple[bytes, str]:
        """The stored bundle bytes for a pack: ``(bytes,
        content_type)``. Served from the object store by the
        record's key — what downloads is what the digest on the
        record was taken over."""
        record = self.get_evidence(pack_id)
        if fmt == "json":
            return self.objects.get(record.json_key), "application/json"
        if fmt == "txt":
            return self.objects.get(record.text_key), "text/plain; charset=utf-8"
        raise BundleNotFound(
            f"evidence format {fmt!r} does not exist — the bundle is "
            "stored as 'json' and 'txt'"
        )
