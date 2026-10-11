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
- **the audit evidence bundle is a projection** — generated
  only for a signed pack, assembled from stored records by
  :mod:`.evidence`, checked for completeness before anything
  is written, and stored in the object store under a digest
  the bundle record carries.

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
from . import evidence as evidence_module
from . import guardrails
from .definitions import DefinitionPack
from .errors import (
    BatchNotFound,
    BundleNotFound,
    ChecklistIncomplete,
    GateError,
    PackNotFound,
    RunNotFound,
)
from .graph import PackPipeline
from .marts import build_marts, slot_key
from .ports import ConnectorPort, ObjectStorePort
from .schemas import (
    Acknowledgement,
    BoardPack,
    CloseRun,
    Disposition,
    EvidenceBundle,
    SourceBatch,
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
        run = CloseRun(
            run_id=run_id, period=period,
            checklist={eid: {} for eid in self.pack_def.entity_ids()},
            audit=[{"event": "run_created", "at": _now()}],
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
            if pack.status in ("SIGNED_OFF", "RETURNED", "STALE"):
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
        marts = build_marts(batches, self.pack_def)
        pack_id = f"PACK-{run.run_id}-{len(run.pack_ids) + 1}"
        # The comparative layer is prepared here, where the
        # store lives: the prior period's signed pack, the
        # definition versions on both sides, and whether the
        # prior period's sources have been restated since.
        comparative_ctx = comparatives_module.prepare_comparatives(
            self.store, self.pack_def, run.period, self.pack_dirs
        )
        self.pipeline.contexts[pack_id] = {
            "marts": marts, "batches": batches,
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
