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
    # A consolidated figure whose arithmetic touches intercompany
    # legs an open pair disagreement disputes (see ICPair). The
    # flag ties the number to the disagreement on the pack; it
    # never appears on an entity figure — entity packs stand as
    # booked, disputed or not.
    ic_disagreement: bool = False
    definition_pack_version: str = ""
    source_versions: SourceVersions = Field(default_factory=SourceVersions)


class ICPair(BaseModel):
    """One intercompany pair, checked for agreement: the revenue
    leg one entity booked against the cost leg its counterparty
    booked, for one elimination definition.

    The two sides book in their own entity currencies, so the
    amounts as *stated* in each entity's books are recorded
    first, exactly as posted. The comparison runs in the pair's
    basis currency — the seller's, the currency the trade was
    invoiced in — with the buyer's stated amount translated
    once, at the close's own rate table (the single table every
    figure in the pack converts with), so the verdict is
    agreement to the cent on the close's stated basis, never a
    comparison of two converted consolidated totals. ``fx_rate``
    is that translation factor (buyer currency → basis), kept
    on the record as provenance; it is ``None`` when the two
    sides book in the same currency and no translation happens.

    A pair is ``AGREED`` (both legs present, difference zero),
    ``IC_DISAGREEMENT`` (both legs present, different amounts),
    or ``ONE_SIDED`` (a leg on one side only — a booking one
    entity made and the other never did, which is a different
    failure from booking different amounts and is named
    separately)."""

    elimination_id: str
    seller_id: str  # the entity that booked the revenue leg
    buyer_id: str   # the entity that booked the cost leg
    revenue_account: str
    cost_account: str
    seller_amount: str | None = None  # stated, in seller_currency
    seller_currency: str
    buyer_amount: str | None = None   # stated, in buyer_currency
    buyer_currency: str
    basis_currency: str  # the seller's currency — the invoice currency
    buyer_amount_basis: str | None = None  # buyer amount in basis
    fx_rate: str | None = None  # buyer currency → basis, when applied
    difference: str | None = None  # seller − buyer (basis); None if one-sided
    verdict: Literal["AGREED", "IC_DISAGREEMENT", "ONE_SIDED"]
    missing_side: Literal["revenue", "cost"] | None = None


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


class FluxContribution(BaseModel):
    """One driver's share of a figure's movement.

    ``kind`` names what the line is: an entity's contribution,
    an account's contribution, the plan-baseline line of a
    ``vs_plan`` figure, a group-level line (a figure whose
    definition has no finer split — its whole movement rides
    one line), or the named rounding line that absorbs the
    residue when converted parts are summed against a converted
    whole. ``amount`` is signed: the contribution to
    ``current − prior``, in the figure's currency."""

    key: str = ""  # entity_id, account, or "" for group-level lines
    kind: Literal["entity", "account", "plan", "group", "rounding"]
    label: str
    amount: str  # Decimal as string, signed


class FigureFlux(BaseModel):
    """One figure's movement, explained: the flux entry.

    The movement is the comparative's movement — current figure
    minus the prior period's **signed** figure — decomposed two
    ways: by entity, and by account where the figure's
    definition bottoms out in GL accounts. Both decompositions
    foot exactly: their lines sum to ``movement`` to the cent,
    with any conversion residue on a named rounding line rather
    than absorbed. ``by_account`` is ``None`` where the
    definition's shape allows no account split (an elimination
    is a pairing, not a sum of accounts; a CRM pipeline figure
    has no accounts at all) — ``note`` says which and why.

    Each period's side of the decomposition is computed under
    that period's own definition-pack version, from that
    period's source batches — the convention the restatement
    recomputation already uses. When the versions differ the
    entry carries ``definition_changed`` and the movement mixes
    the definition change with trading movement; the schedule
    names both versions in ``basis`` instead of pretending the
    two were separated."""

    metric_id: str
    entity_id: str | None = None
    currency: str
    current_value: str
    prior_value: str  # the signed figure, exactly as cited
    movement: str     # current − prior, Decimal as string
    movement_pct: str | None = None
    material: bool = False
    definition_changed: bool = False
    restated: bool = False
    basis: str = ""   # the definition versions each side stands on
    by_entity: list[FluxContribution] = Field(default_factory=list)
    by_account: list[FluxContribution] | None = None
    note: str = ""


class FluxSchedule(BaseModel):
    """The pack's flux schedule: one entry per comparative
    figure, the materiality ruler stated on its face.

    A movement is material when it reaches either bar in
    :mod:`.policy` — ``threshold_abs`` in the figure's own
    currency, or ``threshold_pct`` against the prior figure.
    Material entries carry their drivers ordered largest first;
    immaterial entries are listed whole, without driver ordering
    theatre."""

    prior_period: str
    prior_pack_id: str
    current_definition_pack_version: str = ""
    prior_definition_pack_version: str = ""
    threshold_abs: str = ""
    threshold_pct: str = ""
    entries: list[FigureFlux] = Field(default_factory=list)


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
    # The intercompany agreement check: every IC pair in the
    # period's sources, keyed by counterparty against the pack's
    # elimination definitions, with the verifier's verdict per
    # pair (see :class:`ICPair`). Produced by the verifier from
    # source, like the variances; a disagreement or a one-sided
    # pair also lands as a named variance and blocks the pack.
    ic_pairs: list[ICPair] = Field(default_factory=list)
    # The flux schedule: every comparative figure's movement
    # decomposed by entity and by account, footing exactly to
    # the movement (see :mod:`.flux`). None when the pack has no
    # comparatives, or when the prior period's definition-pack
    # version is not on disk — a decomposition computed under
    # the wrong definitions would be a fabrication, so the
    # schedule degrades to absent, like the restatement
    # recomputation does.
    flux: FluxSchedule | None = None
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


class EvidenceBundle(BaseModel):
    """The record of one generated audit evidence bundle.

    The bundle *bytes* live in the object store under
    ``json_key`` / ``text_key``; this record is the index entry
    that names them, carries the digest an auditor (or a test)
    checks the bytes against, and remembers when generation
    happened. Generation metadata lives here, on the record —
    never inside the bundle bytes, which are a pure projection
    of the signed pack and regenerate byte-identically."""

    bundle_id: str
    pack_id: str
    run_id: str
    period: str
    json_key: str
    text_key: str
    sha256: str  # of the JSON bundle bytes, hex
    figure_count: int
    manifest_count: int
    generated_at: str = ""


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
