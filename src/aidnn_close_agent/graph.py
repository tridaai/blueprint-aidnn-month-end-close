"""The pack pipeline: a LangGraph graph with a human gate.

    engine proposes → verifier disposes → GATE → sign-off applied

The graph earns its place at the gate: a verified pack stops
mid-graph (a LangGraph ``interrupt``, checkpointed) until the
controller signs or returns it, and resumes exactly where it
stopped — the segregation is structural. Three separate code
paths: the engine node only proposes figures, the verify node
only recomputes and disposes, and the decision that ends the
run arrives from outside the graph entirely, from a named
human, through the service.

Records, not state, are the system of record: the graph's state
carries ids; every figure, variance, and stamp lives on the
:class:`BoardPack` in the store. The mart set and source batches
a build runs on are registered by the service under the pack id
for the duration of the build — they are inputs to the build,
not state the gate pause needs to survive.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import comparatives as comparatives_module
from . import dispositions as dispositions_module
from . import flux as flux_module
from . import verifier as verifier_module
from .definitions import DefinitionPack
from .marts import MartSet
from .narrative import build_narrative
from .ports import FinanceEnginePort
from .schemas import BoardPack, SignOff, SourceBatch

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PackState(TypedDict, total=False):
    run_id: str
    pack_id: str
    period: str
    decision: dict[str, Any]


class PackPipeline:
    """The compiled pipeline plus the collaborators it runs on."""

    def __init__(self, engine: FinanceEnginePort, store, pack: DefinitionPack,
                 *, checkpointer=None) -> None:
        self.engine = engine
        self.store = store
        self.pack_def = pack
        self.contexts: dict[str, dict[str, Any]] = {}  # pack_id → build inputs
        builder = StateGraph(PackState)
        builder.add_node("engine", self._engine)
        builder.add_node("verify", self._verify)
        builder.add_node("gate", self._gate)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "engine")
        builder.add_edge("engine", "verify")
        builder.add_edge("verify", "gate")
        builder.add_edge("gate", "finalize")
        builder.add_edge("finalize", END)
        self.graph = builder.compile(checkpointer=checkpointer)

    # -- nodes -----------------------------------------------------

    def _engine(self, state: PackState) -> dict:
        context = self.contexts[state["pack_id"]]
        marts: MartSet = context["marts"]
        # The build's definition pack comes from the service's
        # selection for the period (see governance) when one is
        # registered; the pipeline's wired pack is the default.
        pack_def = context.get("pack_def") or self.pack_def
        figures = self.engine.answer(pack_def, marts)
        pack = BoardPack(
            pack_id=state["pack_id"],
            run_id=state["run_id"],
            period=state["period"],
            status="BLOCKED",
            figures=figures,
            definition_pack_id=pack_def.pack_id,
            definition_pack_version=pack_def.version,
            mart_version=marts.mart_version,
            source_versions=marts.source_versions,
            audit=[{"event": "figures_proposed", "at": _now(),
                    "detail": f"engine {self.engine.name}, "
                              f"{len(figures)} figures"}],
            created_at=_now(), updated_at=_now(),
        )
        self.store.save_pack(pack)
        return {}

    def _verify(self, state: PackState) -> dict:
        context = self.contexts[state["pack_id"]]
        batches: list[SourceBatch] = context["batches"]
        pack_def = context.get("pack_def") or self.pack_def
        pack = self.store.get_pack(state["pack_id"])
        assert pack is not None
        report = verifier_module.verify(pack_def, batches, pack.figures)
        checks = {(c.metric_id, c.entity_id): c for c in report.checks}
        for figure in pack.figures:
            check = checks.get((figure.metric_id, figure.entity_id))
            figure.status = "verified" if check and check.ok else "mismatch"
        pack.variances = list(report.variances)

        # The intercompany agreement layer: the verifier's
        # per-pair verdicts ride the pack, and the consolidated
        # figures whose arithmetic touches a disputed pair's legs
        # carry the flag tying them to the open disagreement.
        # Entity figures are never flagged — they stand as
        # booked; the disagreement is a consolidation-truth
        # problem, and it blocks through the pair variances
        # above, like every other variance.
        pack.ic_pairs = list(report.ic_pairs)
        open_elims = {p.elimination_id for p in pack.ic_pairs
                      if p.verdict != "AGREED"}
        if open_elims:
            flagged = verifier_module.ic_flagged_metrics(
                pack_def, open_elims)
            for figure in pack.figures:
                if figure.entity_id is None \
                        and figure.metric_id in flagged:
                    figure.ic_disagreement = True
        if pack.ic_pairs:
            agreed = sum(1 for p in pack.ic_pairs
                         if p.verdict == "AGREED")
            pack.audit.append({
                "event": "ic_pairs_checked", "at": _now(),
                "detail": f"{len(pack.ic_pairs)} intercompany pair(s) "
                          f"checked by counterparty: {agreed} agreed, "
                          f"{len(pack.ic_pairs) - agreed} open",
            })

        # The comparative layer: prior-period figures cited from
        # the prior period's signed pack, checked against that
        # record (never recomputed from its sources). A restated
        # prior period adds its named variance here — it does not
        # block the pack's figures, which are this period's and
        # verified; it holds the *signature* instead, in the
        # service, until a controller acknowledges it.
        comparative_failures: list = []
        comparative_ctx = context.get("comparatives")
        if comparative_ctx is not None:
            comparative_failures = comparatives_module.attach_comparatives(
                pack, comparative_ctx
            )
            pack.variances.extend(comparative_failures)
            pack.audit.append({
                "event": "comparatives_attached", "at": _now(),
                "detail": f"{len(pack.comparatives)} comparatives cite "
                          f"signed pack {comparative_ctx.prior_pack.pack_id} "
                          f"({comparative_ctx.prior_pack.period}); definition "
                          f"pack v{comparative_ctx.prior_pack.definition_pack_version}"
                          f" → v{pack.definition_pack_version}",
            })
            rate_flagged = sorted({
                c.metric_id for c in pack.comparatives if c.rate_changed
            })
            if rate_flagged:
                pack.audit.append({
                    "event": "rate_change_flagged", "at": _now(),
                    "detail": f"{len(rate_flagged)} consolidated "
                              "comparatives cross a rate change "
                              "between the two packs' stamped rate "
                              "tables: " + ", ".join(rate_flagged),
                })
            if pack.restatement is not None:
                variance = comparatives_module.restatement_variance(
                    pack.restatement
                )
                pack.variances.append(variance)
                pack.audit.append({
                    "event": "restatement_detected", "at": _now(),
                    "detail": variance.detail,
                })

        # The flux schedule: every comparative figure's movement
        # decomposed by entity and by account, produced here and
        # checked by the verifier's own implementation over the
        # same two batch sets. A schedule that disagrees with
        # the sources blocks the pack — an explanation that does
        # not foot is worse than none. The schedule is absent
        # (not fabricated) when the prior period's definitions
        # or stamped batches are unavailable.
        flux_failures: list = []
        if comparative_ctx is not None and pack.comparatives:
            schedule = flux_module.build_schedule(
                pack_def, comparative_ctx.prior_pack_def,
                batches, comparative_ctx.prior_batches,
                pack.figures, pack.comparatives,
                prior_period=comparative_ctx.prior_pack.period,
                prior_pack_id=comparative_ctx.prior_pack.pack_id,
            )
            if schedule is not None:
                pack.flux = schedule
                flux_failures = verifier_module.verify_flux(
                    schedule, pack_def,
                    comparative_ctx.prior_pack_def,
                    batches, comparative_ctx.prior_batches or [],
                    pack.figures, pack.comparatives,
                )
                pack.variances.extend(flux_failures)
                material = sum(1 for e in schedule.entries if e.material)
                pack.audit.append({
                    "event": "flux_attached", "at": _now(),
                    "detail": f"flux schedule decomposes "
                              f"{len(schedule.entries)} movements "
                              f"({material} material) against signed "
                              f"pack {schedule.prior_pack_id}; each "
                              "decomposition recomputed independently "
                              "by the verifier",
                })
            else:
                pack.audit.append({
                    "event": "flux_unavailable", "at": _now(),
                    "detail": "no flux schedule: the prior period's "
                              "definition-pack version or stamped "
                              "source batches are unavailable, and a "
                              "decomposition under the wrong "
                              "definitions would be a fabrication",
                })

        # The definition-governance layer: the selection that
        # governed this build is named on the pack, and when
        # the build is the first under a newly activated
        # version, the change statement rides its face — who
        # activated the version, why, and what the dry-run
        # found before the act (see governance).
        selection_note = context.get("selection_note")
        if selection_note:
            pack.audit.append({
                "event": "definition_selected", "at": _now(),
                "detail": selection_note,
            })
        change = context.get("definition_change")
        if change is not None:
            pack.definition_change = change
            pack.audit.append({
                "event": "definition_change_stated", "at": _now(),
                "detail": f"first pack governed by definition "
                          f"pack v{change.to_version} (activation "
                          f"{change.activation_id} by "
                          f"{change.actor}, governing from "
                          f"{change.from_period}): the dry-run "
                          f"it relied on ({change.dry_run_id}) "
                          f"found {change.moved_count} figure(s) "
                          f"moved, {change.added_count} added, "
                          f"{change.dropped_count} dropped over "
                          f"the prior signed period",
            })

        # The pre-close readiness layer: the statement the
        # build's gate computed — the manifest that governed,
        # and whether the close started complete or under a
        # named waiver — is stated on the pack's face, beside
        # the audit event that records it. The gate itself
        # lives in the service (it refuses the build before
        # the graph runs); what lands here is its outcome, so
        # the signed record shows the terms the close started
        # on.
        readiness = context.get("readiness")
        if readiness is not None:
            pack.readiness = readiness
            if readiness.status == "WAIVED":
                detail = (
                    f"readiness WAIVED under manifest "
                    f"{readiness.manifest_id} "
                    f"v{readiness.manifest_version}: the close "
                    f"started short-handed on "
                    f"{len(readiness.waived_items)} item(s) — "
                    + "; ".join(readiness.waived_items)
                    + " — covered by "
                    + "; ".join(
                        f"{c.waiver_id} ({c.actor}): {c.reason}"
                        for c in readiness.waivers)
                )
            else:
                detail = (
                    f"readiness complete under manifest "
                    f"{readiness.manifest_id} "
                    f"v{readiness.manifest_version}: all "
                    f"{readiness.expected_count} expected "
                    "sources received at their expected "
                    "versions, and the rate table covers the "
                    "period's currencies"
                )
            pack.audit.append({
                "event": "readiness_stated", "at": _now(),
                "detail": detail,
            })

        # The disposition layer: governance around the verdict,
        # consulted only after the verdict is fully computed.
        # Carried acceptances from the prior signed pack are
        # re-tested against this build's variances as opening
        # items — cleared, still present, or mutated — whatever
        # the pack's own fate. And when the pack is blocked, the
        # run's governing acceptances are checked for coverage:
        # every blocking variance covered, exactly as computed,
        # is the second honest path to the gate. The variances
        # themselves are untouched either way.
        carried = context.get("carried") or []
        if carried:
            pack.opening_items = dispositions_module.retest_items(
                carried, pack)
            pack.audit.append({
                "event": "opening_items_retested", "at": _now(),
                "detail": "; ".join(
                    f"{item.code}"
                    f"{f' ({item.subject})' if item.subject else ''} "
                    f"carried from {item.origin_period} "
                    f"(acceptance {item.disposition_id}, carry "
                    f"{item.carry_number}): {item.retest}"
                    for item in pack.opening_items
                ),
            })
        governing = context.get("dispositions") or []
        blocking = dispositions_module.blocking_variances(pack)
        covering = [
            d for d in governing
            if any(dispositions_module.disposition_covers(d, pack, v)
                   for v in blocking)
        ]
        presented = bool(blocking) and all(
            any(dispositions_module.disposition_covers(d, pack, v)
                for d in governing)
            for v in blocking
        )

        if report.passed and not comparative_failures and not flux_failures:
            pack.status = "AWAITING_CONTROLLER"
            pack.narrative = build_narrative(pack.figures, pack.period,
                                             flux=pack.flux)
            pack.audit.append({
                "event": "verified", "at": _now(),
                "detail": f"all {len(report.checks)} figures recomputed from "
                          "source; no figure variances"
                          + ("; the signature is held on the restatement "
                             "variance until it is acknowledged"
                             if pack.restatement is not None else ""),
            })
        elif presented:
            # Presented for sign-off under disposition. The
            # acceptances ride the pack's face — the signed
            # record will list what was accepted, by whom, and
            # why, next to the variances, which stand exactly
            # as computed. The narrative is built only where it
            # cannot misstate: every figure verified, no pair
            # in dispute (its eliminations sentence speaks of
            # legs "verified present and paired"), and no flux
            # failure (a schedule the verifier rejected is not
            # quoted). Elsewhere the pack's account of itself
            # is the variances and the acceptances.
            pack.status = "AWAITING_CONTROLLER"
            pack.dispositions = covering
            if all(f.status == "verified" for f in pack.figures) \
                    and not any(p.verdict != "AGREED"
                                for p in pack.ic_pairs) \
                    and not flux_failures:
                pack.narrative = build_narrative(
                    pack.figures, pack.period, flux=pack.flux)
            pack.audit.append({
                "event": "presented_under_disposition", "at": _now(),
                "detail": "the verifier's verdict stands — "
                          + "; ".join(
                              f"{v.code}: {v.detail}" for v in blocking)
                          + " — and every blocking variance is "
                          "accepted on the record: "
                          + "; ".join(
                              f"{d.code}"
                              f"{f' ({d.subject})' if d.subject else ''} "
                              f"accepted by {d.actor} "
                              f"({d.disposition_id}, carry "
                              f"{d.carry_number})"
                              for d in covering),
            })
        else:
            pack.status = "BLOCKED"
            pack.audit.append({
                "event": "blocked", "at": _now(),
                "detail": "; ".join(
                    f"{v.code}: {v.detail}" for v in pack.variances
                ) or "figure mismatch",
            })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        return {}

    def _gate(self, state: PackState) -> dict:
        pack = self.store.get_pack(state["pack_id"])
        assert pack is not None
        if pack.status != "AWAITING_CONTROLLER":
            return {"decision": {}}
        decision = interrupt({
            "pack_id": pack.pack_id,
            "awaiting": "controller_sign_off",
            "period": pack.period,
        })
        return {"decision": decision or {}}

    def _finalize(self, state: PackState) -> dict:
        raw = state.get("decision") or {}
        if not raw:
            return {}
        pack = self.store.get_pack(state["pack_id"])
        assert pack is not None
        if pack.status != "AWAITING_CONTROLLER":
            return {}
        signoff = SignOff(
            decision=raw["decision"], actor=raw["actor"],
            reason=raw.get("reason", ""), at=_now(),
        )
        pack.decision = signoff
        pack.status = "SIGNED_OFF" if signoff.decision == "sign" else "RETURNED"
        pack.audit.append({
            "event": "controller_decision", "at": _now(),
            "detail": f"{signoff.decision} by {signoff.actor}",
        })
        pack.updated_at = _now()
        self.store.save_pack(pack)
        if signoff.decision == "sign":
            run = self.store.get_run(pack.run_id)
            if run is not None:
                run.status = "CLOSED"
                run.audit.append({
                    "event": "run_closed", "at": _now(),
                    "detail": f"pack {pack.pack_id} signed by {signoff.actor}",
                })
                run.updated_at = _now()
                self.store.save_run(run)
        return {}
