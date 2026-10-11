"""The record model: sources, runs, figures, variances, packs.

One vocabulary runs from the connectors through the engine and
the verifier to the controller's desk, so a figure means the same
thing at every layer: a Decimal amount (carried as a string, see
:mod:`.fx`), produced by one named definition, from named source
batches, at named versions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .fx import RateTable

SourceKind = Literal["gl", "ar", "fx", "crm"]
RunStatus = Literal["COLLECTING", "READY", "CLOSED"]
PackStatus = Literal[
    "BLOCKED",              # the verifier would not let it through
    "AWAITING_CONTROLLER",  # every figure verified; a human decides
    "SIGNED_OFF",           # the controller signed; nothing posts anywhere
    "RETURNED",             # the controller sent it back, reason recorded
    "STALE",                # a source moved after this pack was built
]
FigureStatus = Literal["proposed", "verified", "mismatch"]


class Entity(BaseModel):
    entity_id: str
    name: str
    currency: str
    source_system: str  # the customer's system the connector mirrors


class JournalLine(BaseModel):
    account: str
    debit: str = "0.00"   # Decimal as string — see fx.py
    credit: str = "0.00"
    ic_counterparty: str | None = None  # entity_id, on intercompany lines
    memo: str = ""


class Journal(BaseModel):
    journal_id: str
    entity_id: str
    date: str
    memo: str = ""
    lines: list[JournalLine] = Field(default_factory=list)


class ArBilling(BaseModel):
    """One entity's AR subledger summary for the period: what the
    subledger says was billed, to tie out against GL revenue."""

    entity_id: str
    billings: str  # Decimal as string, entity currency
    currency: str


class Opportunity(BaseModel):
    name: str
    amount: str  # Decimal as string, reporting currency
    stage: str = "open"


class SourceBatch(BaseModel):
    """One connector delivery: an extract, at a version.

    A batch is immutable once ingested. A corrected extract is a
    *new* batch whose ``supersedes`` names the batch it replaces —
    that single discipline is what makes staleness computable.
    """

    batch_id: str
    kind: SourceKind
    entity_id: str | None = None  # None for group-level kinds (fx, crm)
    version: int = 1
    supersedes: str | None = None
    # "restatement": a corrected extract for a period whose pack is
    # already signed — it lands outside any open run and is picked
    # up by the next period's comparative check, never by editing
    # the signed record.
    phase: Literal["initial", "late", "restatement"] = "initial"
    journals: list[Journal] = Field(default_factory=list)
    ar_billings: list[ArBilling] = Field(default_factory=list)
    rate_table: RateTable | None = None
    opportunities: list[Opportunity] = Field(default_factory=list)
    sha256: str = ""


class SourceVersions(BaseModel):
    """The exact source versions a pack was built from — the
    provenance stamp every figure carries."""

    batches: dict[str, int] = Field(default_factory=dict)  # batch_id → version
    fx_version: int = 0


class Figure(BaseModel):
    """One number in the board pack, with its provenance."""

    metric_id: str
    label: str
    scope: Literal["entity", "consolidated", "group"]
    entity_id: str | None = None
    value: str  # Decimal as string
    currency: str
    status: FigureStatus = "proposed"
    definition_pack_version: str = ""
    source_versions: SourceVersions = Field(default_factory=SourceVersions)


class Variance(BaseModel):
    """A named reason a pack cannot go forward, or a figure to
    look at. Codes are stable strings; the eval pack gates on them."""

    code: str
    detail: str
    entity_id: str | None = None
    metric_id: str | None = None


class SignOff(BaseModel):
    decision: Literal["sign", "return"]
    actor: str
    reason: str = ""
    at: str = ""


class FigureComparative(BaseModel):
    """One figure's comparative: this period's value against the
    prior period's **signed** figure.

    The prior value is copied from the signed pack record — the
    numbers the board actually approved — never recomputed from
    prior-period sources, which may have been restated since.
    ``change`` / ``change_pct`` are computed here, in code, from
    those two values; both are ``None`` when the comparison is
    not meaningful (currencies differ, or the prior value is
    zero). ``definition_changed`` names the silent-error case: the
    metric's definition (or one it derives from, or its plan
    baseline) differs between the two packs' definition-pack
    versions, so the two numbers were not produced by the same
    rule. ``restated`` marks a figure the prior period's
    restatement touched — the comparative still shows the signed
    value, flagged, because that is what the board approved."""

    metric_id: str
    entity_id: str | None = None
    prior_value: str  # Decimal as string — the signed figure, exactly
    prior_currency: str
    prior_pack_id: str  # the signed pack the comparative cites
    prior_definition_pack_version: str = ""
    definition_changed: bool = False
    restated: bool = False
    change: str | None = None      # current − prior, Decimal as string
    change_pct: str | None = None  # change / prior × 100, 2dp


class RestatedFigure(BaseModel):
    """One signed figure a restatement moved: what the board
    approved vs what the restated sources now produce."""

    metric_id: str
    entity_id: str | None = None
    signed_value: str
    recomputed_value: str
    currency: str


class RestatementReport(BaseModel):
    """A prior period's sources no longer reproduce its signed
    pack. The signed pack is never altered; the report rides the
    *next* period's pack, whose sign-off is refused until a named
    controller acknowledges it."""

    prior_period: str
    prior_pack_id: str
    restated_batch_ids: list[str] = Field(default_factory=list)
    affected_figures: list[RestatedFigure] = Field(default_factory=list)


class Acknowledgement(BaseModel):
    """A named human's recorded acknowledgement — of a
    restatement, here. It changes nothing about the record it
    acknowledges; it unblocks the gate that was waiting on a
    human having seen the thing."""

    actor: str
    note: str
    at: str = ""


class BoardPack(BaseModel):
    """The close pack: figures, variances, versions, one decision.

    The pack is a *proposal with evidence* — signing it records a
    human's approval of the numbers. Nothing in this type, or
    anywhere in the package, posts to a ledger or files anything.
    """

    pack_id: str
    run_id: str
    period: str
    status: PackStatus = "BLOCKED"
    figures: list[Figure] = Field(default_factory=list)
    variances: list[Variance] = Field(default_factory=list)
    # The comparative layer: prior-period figures cited from the
    # prior period's signed pack (empty for a first close), the
    # restatement report when the prior period's sources moved
    # after sign-off, and the controller's acknowledgement of it.
    comparatives: list[FigureComparative] = Field(default_factory=list)
    restatement: RestatementReport | None = None
    restatement_acknowledgement: Acknowledgement | None = None
    definition_pack_id: str = ""
    definition_pack_version: str = ""
    mart_version: str = ""
    source_versions: SourceVersions = Field(default_factory=SourceVersions)
    narrative: str | None = None
    decision: SignOff | None = None
    audit: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class CloseRun(BaseModel):
    """One period's close, from first extract to signed pack."""

    run_id: str
    period: str
    status: RunStatus = "COLLECTING"
    # entity_id → source kind → ingested batch version
    checklist: dict[str, dict[str, int]] = Field(default_factory=dict)
    # group-level kinds → ingested batch version (fx, crm)
    group_checklist: dict[str, int] = Field(default_factory=dict)
    ingested_batch_ids: list[str] = Field(default_factory=list)
    # "ENTITY:kind" (or "GROUP:kind") → the batch currently in
    # force for that slot. A superseding batch replaces the entry;
    # packs stamp the map they were built from, and a map that has
    # moved on is exactly what "stale" means.
    current_batches: dict[str, str] = Field(default_factory=dict)
    pack_ids: list[str] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
