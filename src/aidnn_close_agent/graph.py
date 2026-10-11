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
        figures = self.engine.answer(self.pack_def, marts)
        pack = BoardPack(
            pack_id=state["pack_id"],
            run_id=state["run_id"],
            period=state["period"],
            status="BLOCKED",
            figures=figures,
            definition_pack_id=self.pack_def.pack_id,
            definition_pack_version=self.pack_def.version,
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
        pack = self.store.get_pack(state["pack_id"])
        assert pack is not None
        report = verifier_module.verify(self.pack_def, batches, pack.figures)
        checks = {(c.metric_id, c.entity_id): c for c in report.checks}
        for figure in pack.figures:
            check = checks.get((figure.metric_id, figure.entity_id))
            figure.status = "verified" if check and check.ok else "mismatch"
        pack.variances = report.variances
        if report.passed:
            pack.status = "AWAITING_CONTROLLER"
            pack.narrative = build_narrative(pack.figures, pack.period)
            pack.audit.append({
                "event": "verified", "at": _now(),
                "detail": f"all {len(report.checks)} figures recomputed from "
                          "source; no variances",
            })
        else:
            pack.status = "BLOCKED"
            pack.audit.append({
                "event": "blocked", "at": _now(),
                "detail": "; ".join(
                    f"{v.code}: {v.detail}" for v in report.variances
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
