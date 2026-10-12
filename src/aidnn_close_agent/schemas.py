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
    # The rate table itself, as used — not just its version
    # number. A version is a claim; the table is the evidence:
    # with the rates on the stamp, every converted figure's
    # provenance names the rate that was applied to it, the
    # verifier can recompute at the stamped rates rather than
    # at whatever table is current when it runs, and a later
    # period can see that the EUR rate moved, not merely that
    # the table's version did. ``None`` on packs and figures
    # stamped before rate tables were carried on the stamp —
    # the absence reads as absence, and is never backfilled.
    fx_table: RateTable | None = None


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
    rule. ``rate_changed`` is its sibling for the other silent
    input: the figure is a consolidated figure whose derivation
    converts money booked in a currency whose rate differs
    between the two packs' stamped rate tables, so the two
    numbers were not converted on the same basis either. It is
    a flag, never a decomposition — the movement is not split
    into "rate" and "trading" parts, for the same reason the
    definition change is not separated out. ``restated`` marks
    a figure the prior period's
    restatement touched — the comparative still shows the signed
    value, flagged, because that is what the board approved."""

    metric_id: str
    entity_id: str | None = None
    prior_value: str  # Decimal as string — the signed figure, exactly
    prior_currency: str
    prior_pack_id: str  # the signed pack the comparative cites
    prior_definition_pack_version: str = ""
    definition_changed: bool = False
    rate_changed: bool = False
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
    rate_changed: bool = False
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
    # The two closes' rate-table versions, stated on the face
    # beside the definition versions: a reader should see that
    # the conversion basis moved without opening either pack.
    # ``None`` when a period's batches carried no rate table.
    current_fx_version: int | None = None
    prior_fx_version: int | None = None
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


class Disposition(BaseModel):
    """A named controller's acceptance of one blocking variance:
    the break stands as the verifier computed it, and the close
    proceeds anyway — carried into the next period, on the
    record.

    A disposition is governance *around* the verifier, never an
    edit of its verdict: the variance it accepts stays on the
    pack, word for word, and the pack that signs under it lists
    the disposition on its face. The record names the exact
    break accepted — code, entity, metric, subject, and the
    variance's detail text, figures and all — so a break that
    comes back with different figures is a different break and
    is not covered by an acceptance written for the old one.

    Dispositions are append-only. One governs a variance at a
    time; changing an acceptance is a new record whose
    ``supersedes`` names the record it replaces, never an edit
    of it. There is no un-accept: an acceptance withdrawn in
    substance is an acceptance re-written with its reason, and
    the chain shows both.

    ``origin_period`` / ``origin_pack_id`` name where the break
    was *first* accepted, and ``carry_number`` counts its
    acceptances: 1 for a fresh break, 2 when an item that
    opened a period still breaks and is accepted again — the
    second carry, stated plainly, because the third month of
    the same break is a fact a CFO should see on the face."""

    disposition_id: str
    pack_id: str        # the pack the record was written on
    run_id: str
    period: str
    code: str
    entity_id: str | None = None
    metric_id: str | None = None
    subject: str = ""   # pair / elimination / journal, where the
                        # code alone does not name the break
    detail: str         # the variance's detail, exactly as computed
    decision: Literal["ACCEPTED_CARRY"] = "ACCEPTED_CARRY"
    actor: str
    reason: str
    at: str = ""
    supersedes: str | None = None  # disposition_id replaced, if any
    origin_period: str = ""
    origin_pack_id: str = ""
    carry_number: int = 1


class OpeningItem(BaseModel):
    """One carried break, opening the next period's close.

    When a pack signs under dispositions, every acceptance on
    its face becomes an opening item on the next period's pack:
    the break is re-tested against the new period's sources and
    the verdict recorded — ``CLEARED`` (no corresponding
    variance in the new pack), ``STILL_PRESENT`` (the same
    break, word for word, and it blocks again like any other
    variance), or ``MUTATED`` (the same break's identity with
    different figures — the break changed shape, and the old
    acceptance does not cover the new one). The item quotes
    the acceptance that carried it: who, why, from which
    period, and which carry this is."""

    code: str
    entity_id: str | None = None
    metric_id: str | None = None
    subject: str = ""
    detail: str                 # the break as it was accepted
    origin_period: str
    origin_pack_id: str
    disposition_id: str         # the acceptance that carried it
    dispositioned_by: str
    reason: str                 # the acceptance's reason, quoted
    carry_number: int = 1
    retest: Literal["CLEARED", "STILL_PRESENT", "MUTATED"]
    current_detail: str | None = None  # this period's wording of
                                       # the break, when it recurs


class FigureDelta(BaseModel):
    """One figure the candidate definitions would move: the
    value the signed period's own definitions produce from its
    stamped sources, the value the candidate produces from the
    *same* sources, and the difference — all recomputed, none
    copied from any pack record."""

    metric_id: str
    entity_id: str | None = None
    currency: str
    signed_pack_value: str  # what the signed pack carries
    base_value: str         # recomputed under the signed version
    candidate_value: str    # recomputed under the candidate
    delta: str              # candidate − base
    delta_pct: str | None = None  # delta / base × 100, 2dp
    # Judged by the close's standing ruler — the flux
    # schedule's materiality bars in policy — applied to the
    # change the candidate itself would make.
    material: bool = False


class DryRunFigure(BaseModel):
    """One figure a definition change would add or drop: it
    exists under exactly one of the two versions."""

    metric_id: str
    entity_id: str | None = None
    currency: str
    value: str  # under the version that produces it


class BaselineDiscrepancy(BaseModel):
    """A signed figure the dry-run's baseline recomputation
    does not reproduce from the signed pack's own stamped
    sources. Expected to be empty in an honest world: batches
    are append-only and the stamps name them exactly, so a
    discrepancy here means a record was tampered with — and
    the dry-run says so instead of inheriting the number."""

    metric_id: str
    entity_id: str | None = None
    signed_value: str
    recomputed_value: str


class DryRunReport(BaseModel):
    """The impact of a candidate definition-pack version,
    computed before the candidate governs anything.

    The report is a pure function of its inputs — the signed
    reference pack's identity, its stamped sources, the two
    definition versions — and carries no timestamp, so its
    canonical bytes (and the digest an activation cites) are
    stable: recompute it tomorrow and it is the same report.
    Both sides are recomputed from the reference period's
    stamped source batches at the rate table the signed pack
    stamps: the candidate's effect is the *only* difference
    between the two columns. ``variance_families`` are the
    variance codes each side's verification produces over
    those sources — a tie-out the candidate would newly fail
    (or newly pass) is computed here, not asserted."""

    pack_id: str
    base_version: str       # the version the reference pack cites
    candidate_version: str
    reference_period: str
    reference_pack_id: str  # the signed pack measured against
    changed_metrics: list[str] = Field(default_factory=list)
    moved: list[FigureDelta] = Field(default_factory=list)
    added: list[DryRunFigure] = Field(default_factory=list)
    dropped: list[DryRunFigure] = Field(default_factory=list)
    variance_families_base: list[str] = Field(default_factory=list)
    variance_families_candidate: list[str] = Field(default_factory=list)
    families_added: list[str] = Field(default_factory=list)
    families_removed: list[str] = Field(default_factory=list)
    baseline_discrepancies: list[BaselineDiscrepancy] = \
        Field(default_factory=list)

    @property
    def material_count(self) -> int:
        return sum(1 for d in self.moved if d.material)


class DefinitionDryRun(BaseModel):
    """The stored dry-run record: the report, its digest, and
    when it was computed (on the record, never inside the
    report — the report's bytes are the digest's subject)."""

    dry_run_id: str
    report: DryRunReport
    digest: str  # sha256 of the report's canonical bytes
    computed_at: str = ""


class PackActivation(BaseModel):
    """A named human's act: this definition-pack version
    governs closes from this period onward.

    Append-only, like every governance record in this system.
    An activation cites the dry-run whose impact justified it
    (id + digest — the impact must exist before the act, and
    the act names the exact impact it relied on). It can only
    govern periods not yet signed: a signed period's pack
    keeps the version it cites forever, and selection for a
    period is computed from these records, never stored as a
    mutable pointer — superseding an activation is a new
    record naming the one it replaces."""

    activation_id: str
    pack_id: str
    from_version: str  # the version governing before this act
    to_version: str
    from_period: str   # first period the new version governs
    dry_run_id: str
    dry_run_digest: str
    actor: str
    reason: str
    at: str = ""
    supersedes: str | None = None  # activation replaced, if any


class DefinitionChange(BaseModel):
    """The change statement a pack carries on its face when it
    is the first pack governed by a newly activated version:
    the version it runs under is not the version its prior
    period signed under, and the pack says how that came to
    be — who activated it, why, from which period, and what
    the pre-activation dry-run found (headline counts; the
    full report is the record the activation cites)."""

    from_version: str
    to_version: str
    from_period: str
    activation_id: str
    actor: str
    reason: str
    dry_run_id: str
    dry_run_digest: str
    moved_count: int
    added_count: int
    dropped_count: int
    material_count: int


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
    # The disposition layer: acceptances recorded on this pack
    # (a blocked pack collecting its governance) and, on a pack
    # presented for sign-off under disposition, the acceptances
    # that cover its blocking variances — copied onto its face
    # at verification, so the signed record lists what was
    # accepted, by whom, and why, next to the variances
    # themselves, which stand exactly as computed.
    dispositions: list[Disposition] = Field(default_factory=list)
    # The carried breaks opening this pack: the prior signed
    # pack's acceptances, re-tested against this period's
    # sources by the verifier's own recomputation (see
    # :class:`OpeningItem`). Empty on a first close and on any
    # close whose predecessor signed clean.
    opening_items: list[OpeningItem] = Field(default_factory=list)
    # The definition-governance layer: when this pack is the
    # first governed by a newly activated definition-pack
    # version, the change is stated on its face — the versions,
    # the activation that made it govern, and the dry-run
    # headline the activation relied on (see
    # :class:`DefinitionChange`). None on every other pack:
    # a close under the version its predecessor signed under
    # has no change to state.
    definition_change: DefinitionChange | None = None
    definition_pack_id: str = ""
    definition_pack_version: str = ""
    mart_version: str = ""
    source_versions: SourceVersions = Field(default_factory=SourceVersions)
    narrative: str | None = None
    decision: SignOff | None = None
    audit: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class DrillLine(BaseModel):
    """One source journal line inside a figure drill: the exact
    line, in the exact batch the pack stamps, with its signed
    contribution to the figure stated in the entity's currency.

    The line carries no converted amount of its own, on
    purpose: the close converts an entity *subtotal* once, at
    the stamped rate (the conversion lives on the drill node
    whose subtotal it is), so a per-line converted figure would
    be a precision the close never computed. What a line does
    carry is everything needed to find it again in the raw
    extract: batch and version, journal, its position within
    the journal, account, both stated amounts, and the
    intercompany flag."""

    entity_id: str
    batch_id: str
    batch_version: int
    journal_id: str
    journal_date: str = ""
    line_index: int  # the line's position within its journal
    account: str
    debit: str   # as stated in the extract, entity currency
    credit: str  # as stated in the extract, entity currency
    ic_counterparty: str | None = None
    memo: str = ""
    amount: str  # the line's signed contribution, entity currency
    currency: str  # the entity's currency


class DrillRecord(BaseModel):
    """One source record inside a drill for a figure that does
    not stand on journal lines — a CRM opportunity, today.
    Same discipline as :class:`DrillLine`: the record as
    stated, its batch and version, and its contribution."""

    batch_id: str
    batch_version: int
    name: str
    stage: str = ""
    amount: str  # the record's contribution, in ``currency``
    currency: str


class DrillNode(BaseModel):
    """One level of a figure drill: a value and what it stands
    on — source lines, source records, or child nodes.

    A **base** node's value is the sum of its own lines (or
    records). A derived node carries no lines of its own —
    ever: its value is the composition of its children under
    the definition's operator, and the drill shows the
    operands' drills instead of fabricating a line set.
    ``sign`` is how the node enters its parent (``-1`` for a
    subtracted operand; a plan child carries its negative
    value directly, with sign ``1``). On a converted child,
    ``pre_conversion_value`` is the entity subtotal in the
    entity's currency and ``rate`` the stamped rate that was
    applied to it — once, to the subtotal, never per line."""

    metric_id: str
    label: str = ""
    entity_id: str | None = None
    kind: Literal[
        "base", "sum_converted", "add", "subtract", "vs_plan",
        "elimination", "leg", "plan",
    ]
    currency: str
    value: str  # Decimal as string — this node's composed total
    sign: int = 1
    rate: str | None = None
    pre_conversion_value: str | None = None
    pre_conversion_currency: str | None = None
    lines: list[DrillLine] = Field(default_factory=list)
    records: list[DrillRecord] = Field(default_factory=list)
    children: list["DrillNode"] = Field(default_factory=list)
    note: str = ""


class FigureDrill(BaseModel):
    """One figure, opened: the composition the pack's stamped
    sources produce for it, computed by re-performance.

    The drill is a recomputation, not a report over stored
    numbers: it walks the exact batches the pack stamps (at
    their stamped versions) and the rate table the pack stamps,
    with its own aggregation, and it is served only when the
    composition foots to the figure on the pack record,
    Decimal-exact — otherwise the request fails with
    ``DRILL_MISMATCH`` naming both totals. ``pack_status``
    rides the drill because auditors drill blocked and stale
    packs too: the drill is a true statement about the pack's
    own stamped sources, with the pack's state named on it.
    The drill carries no timestamp, so it is byte-deterministic
    and digestible (see :func:`aidnn_close_agent.drill.drill_digest`)."""

    pack_id: str
    period: str
    pack_status: PackStatus
    metric_id: str
    entity_id: str | None = None
    label: str
    figure_value: str  # the value on the pack record
    currency: str
    composed_total: str  # the drill's own composition
    line_count: int  # source lines + records across the tree
    definition_pack_version: str = ""
    fx_version: int = 0  # the rate table the conversions stand on
    fx_basis: str = ""   # where that table came from, in words
    root: DrillNode


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
    # The definition-pack version the governance selection
    # rule assigns to this run's period, computed and recorded
    # at creation — the selection is printed here, not left
    # implicit in whichever service happened to be wired.
    # Empty on runs recorded before selection existed.
    definition_pack_id: str = ""
    definition_pack_version: str = ""
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
