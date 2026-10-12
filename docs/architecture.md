# Architecture — aidnn Month-End Close, Deployed

This document describes the deployment, not just the code: what
runs where, what crosses which boundary, and which decisions are
made by arithmetic rather than by a model. It is written for the
two readers who pick up a blueprint like this — the platform
engineer deciding whether the shape is sound, and the group
controller deciding whether the discipline is real.

## The shape in one paragraph

A close run ingests versioned source extracts through
connectors; a mart builder normalizes them under the definition
pack's data-quality rules; a finance engine behind a port
answers the pack's defined questions; an independent verifier
recomputes every figure from the source batches and disposes;
and a LangGraph pipeline stops at an interrupt — the
controller's gate — before anything becomes a signed pack.
Batches, runs, packs, and checkpoints live in PostgreSQL; raw
extract bytes are archived to S3-compatible object storage; the
API tier is stateless, so a sign-off can land days after the
build that produced the pack.

## The aidnn seam

aidnn is the analysis engine in a live deployment: its
connectors pull from the customer's NetSuite, QuickBooks,
Salesforce, and warehouse systems; its agents plan, execute,
and self-check analyses; its NeoCortex layer holds the metric
catalog; its audit trail is the evidence. What it does not
publish — as of October 2026 — is a public API.

That fact decides the seam's shape. `FinanceEnginePort`
(`ports.py`) is one method: *given this definition pack version
and this governed mart set, return the pack's figures*. Two
adapters implement it:

- **`aidnn`** (`engine_aidnn.py`) — the integration contract.
  The adapter posts the defined queries plus the mart snapshot
  to `AIDNN_WORKSPACE_URL`, an endpoint agreed with Isotopes
  during deployment, and maps the returned figures onto the
  port. The module's docstring is explicit that the wire shape
  is the blueprint's contract for the seam — the concrete thing
  an FDE implements against the real workspace (whose transport
  may be its connector + plan-review machinery behind a thin
  internal service) — not a claim about a published aidnn API.
  No URL → `EngineNotConfigured` at startup. The offline
  engine's answers are never served under aidnn's name.
- **`offline`** (`engine_offline.py`) — a complete reference
  implementation over the local marts: deterministic, Decimal
  throughout. Tests, evals, and the demo run on it, and a
  deployment can diff a live engine's first closes against it
  on historical periods — the "validate against hand-built
  numbers" step, mechanized.

The verifier's independence is what makes this seam safe to
be honest about: whichever engine proposes, the figures that
reach the controller are the ones that recomputed from source.

## Definition packs: the catalog is data

The FDE deliverable at the center of the deployment is the
definition pack (`definition_packs/close_pack.json`, loaded and
strictly validated by `definitions.py`):

- **Metrics** — each defined once. A metric is a *base*
  aggregate (a measure — credit-minus-debit or debit-minus-
  credit — over an account set, per entity, optionally skipping
  intercompany-flagged lines; or a sum over the CRM extract) or
  a *derived* step over other metrics: `sum_converted`
  (consolidate an entity metric through the rate table), `add`,
  `subtract`, `vs_plan`, `elimination`. The language is closed
  on purpose: a new op is a code change with a review, never a
  string evaluated at runtime.
- **Eliminations** — revenue account × cost account pairs. Both
  legs must exist and agree after conversion; the matched amount
  is what eliminates.
- **Tie-outs** — subledger totals that must equal the GL figures
  they feed, per entity, in entity currency.
- **Data-quality rules** — currently `unique_journal_ids`: a
  journal id is unique per entity; later copies are void.
- **Plan** — the figures actuals are compared against.

Versioning discipline: a pack change is a new file with a
bumped `version`, never an in-place edit once a close has run
against it. The engine and the verifier read the same version
for a given build, and every figure carries the version in its
provenance — so "which revenue definition produced this pack?"
is a field lookup, not an archaeology project. The eval pack
reruns against the bundled pack on every change: that is the
catalog-change regression suite. Old versions stay loadable
by (pack id, version) through a registry lookup
(`definitions.load_definition_pack_version`): the comparative
layer needs them, because a prior period must always be
recomputed — when it is recomputed at all — under the
definitions that produced its signed pack. Which version
governs a *new* period is a governed question of its own —
measured by dry-run, decided by a recorded activation,
selected by a printed rule — see "Definition change
governance" below.

## Marts: governed, stamped, disposable

`marts.py` builds the only dataset the engine may see, from the
batches currently in force for the run:

- journal lines flattened, amounts parsed to Decimal and
  rounded by the package's one rule;
- the pack's data-quality rules applied — under
  `unique_journal_ids`, later copies of a journal are kept in
  the mart **voided**: visible, flagged, excluded from every
  aggregate;
- journal memos passed through the injection screen
  (`guardrails.py`) and carried fenced — figures never read
  memos, but no text surface downstream ever meets an unfenced
  payload;
- subledger summaries, opportunities, and the rate table
  carried as first-class citizens.

Each mart set carries a `mart_version`: a digest of the exact
source batches (id, version, content hash) plus the pack
version. Marts are disposable — rebuilt per build from the
current batch set — and the verifier never reads them. A mart
bug can make the engine propose wrong figures; it cannot make
wrong figures verify.

## The verifier: a second implementation, on purpose

`verifier.py` recomputes the pack from the **source batches
directly**, with its own aggregation code. It shares with the
engine exactly one input — the definition pack (the policy) —
and nothing else: not the marts, not helper functions, not the
rate table copy (it reads the FX batch itself).

Its checks, in order:

1. **Data quality** — its own scan for repeated journal ids:
   `DUPLICATE_JOURNAL`, naming entity, journal, and extract.
2. **Elimination pairing, aggregate** — IC legs summed per
   entity from raw lines, converted per entity; revenue legs ≠
   cost legs → `UNMATCHED_IC_LEG`, naming both totals and the
   gap.
3. **Intercompany agreement, per pair** — the same legs, keyed
   by counterparty against each elimination definition: the
   seller's IC-flagged credits on the revenue account flagged
   to the buyer, against the buyer's IC-flagged debits on the
   cost account flagged to the seller. The comparison runs in
   the **seller's currency** — the invoice currency — with the
   buyer's stated amount translated once at the run's rate
   table (the single table every figure in the close converts
   with), so the verdict is agreement to the cent on the
   close's own stated basis; comparing two converted
   consolidated totals instead would judge the elimination's
   output, not the two bookings. A pair with both legs and
   different amounts → `IC_DISAGREEMENT`, naming both stated
   figures, the basis figure, and the difference; a leg with
   no counterpart → `IC_ONE_SIDED`, naming the present side
   and the missing one. The two grains are complementary: the
   aggregate cannot tell one-sided from disagreed, and reads a
   leg flagged to the wrong counterparty as paired; the pair
   check names both. An open pair also flags the pack's
   consolidated figures whose derivation touches the disputed
   elimination (`ic_disagreement` on the figure) — entity
   figures are never flagged or restated; the variance text
   says the fix is a booking conversation between the
   entities.
4. **Tie-outs** — subledger vs GL per entity: `SUBLEDGER_TIE_OUT`,
   naming both amounts and the gap.
5. **Figure reproduction** — every defined figure recomputed;
   any difference from the engine's proposal →
   `FIGURE_MISMATCH`, naming both values. A figure the engine
   omitted, or one the pack does not define, is a mismatch too.

Any variance — or any unreproduced figure — blocks the pack:
status BLOCKED, narrative withheld, sign-off refused. The
naming matters operationally: the controller's queue shows
*which* discipline failed, and each code has a known owner
(source system, subsidiary accountant, or the definition pack).

**Honest limits.** Verification proves figures match sources
under the definitions. A journal posted to the wrong account
foots perfectly — arithmetic alone cannot catch it. The
defences are structural: tie-outs against independent
subledger totals (the planted mis-post is caught this way),
and the checklist's insistence that every entity's sources
arrive before a build. A deployment can add tie-out families
(AP, payroll, bank) as definitions; the mechanism does not
change.

## Money, FX, and the one rounding rule

`fx.py` is the only place money arithmetic rules live:

- **Decimal end to end.** Amounts are strings in JSON and the
  store, Decimal in code; no figure passes through a float.
- **Half-up to minor units**, applied at exactly two moments:
  when a journal line enters the mart (and, in the verifier,
  when it is read), and when an entity figure converts to the
  reporting currency.
- **Consolidation sums rounded components.** A consolidated
  figure is the sum of the *converted, rounded* entity figures
  — so the tie a controller performs by eye down the page holds
  by construction, and the eval pack checks it in independent
  arithmetic.
- **Rates are data.** The rate table is a versioned source
  batch; a pack stamps the table it used — the table itself,
  on `SourceVersions.fx_table`, not only its version — so a
  converted figure's provenance names the rate applied to it.
  A revised rate table is a superseding batch like any other
  — see staleness.
- **The verifier recomputes at the stamped table.** Its
  conversions never read whatever table the batch set carries
  at verify time. A stamp that disagrees with the batch set —
  a table superseded after the run, or edited in place under
  the same version (invisible to version-granular staleness) —
  is a `RATE_TABLE_MISMATCH` variance, and each figure is
  still judged against the stamped basis. When a figure
  reproduces at the batch-set table but not at its stamp, the
  mismatch is classified per figure as the same code: the
  figure was converted off-stamp. Figures stamped before
  tables rode the stamp carry none; the verifier falls back
  to the batch set's table for them, and comparatives across
  such a pack flag nothing — absence reads as absence.
- **Rate changes flag like definition changes.** When a
  currency's rate differs between a signed pack's stamp and
  the next pack's, consolidated comparatives whose derivation
  converts nonzero money booked in that currency carry
  `rate_changed` (exposure judged from the two packs' own
  figures and IC pairs, propagated through the derived-metric
  closure in `comparatives.rate_exposed_metrics`). The flux
  schedule states both tables' versions on its face and
  copies the flag per entry; `verify_flux` checks the copy.
  The movement is never decomposed into rate and trading
  parts — the same counterfactual argument as definitions.

## The checklist and staleness: two state machines

**Checklist.** A run tracks, per entity, the ingested version
of each required kind, plus the group kinds (`policy.py`).
`missing_sources` is a pure function over that state. Build
attempts with a non-empty missing list fail with
`ChecklistIncomplete`, naming every missing slot — a pack built
on three of four entities is not a pack, it is a rumor.

**Staleness.** Ingesting a batch moves its slot to the new
batch and, in the same service step, marks every unsigned pack
whose recorded source stamps differ from the run's current set
as STALE. Sign-off additionally re-compares the pack's stamps
against the run's current batches before resuming the graph —
belt and braces, because the cost of a signed-but-stale pack
is exactly the failure this blueprint exists to prevent. A
signed pack is history: ingestion into a CLOSED run is refused
outright, so the record of what was signed can never be made
ambiguous after the fact.

## Comparatives and restatement: the second month

The first close is verified against its sources. Every close
after that is *comparative*, and comparatives introduce a
second object of trust: not this month's sources, but last
month's **signed pack**. `comparatives.py` owns that layer.

**Comparatives cite the record.** At build time the service
looks up the prior period's signed pack (one calendar month
back; the store keeps signed packs by period). In the verify
step, each new figure gains a `FigureComparative`: the prior
figure's value copied from the signed pack — with the pack id
and the definition-pack version that produced it — and the
change / % change computed in code (both `None` when the
comparison is not meaningful: different currencies, or a zero
prior). `verifier.verify_comparatives` then checks the layer
against the record it cites: a comparative that does not equal
the signed figure, to the cent, is a `COMPARATIVE_MISMATCH`
and blocks the pack. The check deliberately does **not**
recompute the prior period from its sources — those sources
may have been restated, and a silent recompute would present
the corrected number as the number the board approved. The
signed record is the board's history; comparatives quote it.

**Restatement is detected off the supersession chain.** A
corrected extract for a signed period cannot be ingested into
its run — the run is CLOSED and refuses (see staleness above).
It arrives through `receive_restatement`: archived, stored,
attached to nothing. At the next period's build, the service
walks the supersession chain from each batch the signed pack
was stamped with; a terminal successor the signed pack never
saw means the prior period's sources have moved. The prior
period is then recomputed — by the verifier, under the prior
period's *own* definition-pack version (loaded from the pack
registry; versions are files, never edits) — over the restated
source set, and every signed figure that fails to reproduce is
listed in a `RestatementReport`: signed value vs recomputed
value. The new pack carries a `RESTATED_PRIOR_PERIOD`
variance, and its comparatives for the moved figures are
flagged `restated` — while still showing the signed values,
because those are what the board approved. The signed pack
itself is never modified; the eval pack asserts byte-identity
of the signed record across the whole second act.

**The acknowledgement gate.** A restatement does not block
the new pack's figures — they are this period's, and they
verify. It blocks the *signature*: `sign_off` refuses while a
pack carries an unacknowledged restatement, and
`acknowledge_restatement` (named controller, mandatory note,
audited on the pack) is what releases it. The variance is not
deleted on acknowledgement — it stays on the pack record
permanently, next to the acknowledgement. This mirrors how a
real close treats a prior-period adjustment the board has
seen: disclosed, owned by a name, and never quietly absorbed.

**Definition discipline across versions.** When the new
period runs under a newer definition-pack version, the
comparative layer compares the two packs and flags every
comparative whose metric changed meaning: its own definition
differs, an elimination it reads was redefined, a `vs_plan`
baseline moved, or anything it derives from changed
(transitively). October runs under v1.1.0 (operating expenses
gained account 6400, insurance; the revenue plan moved), and
its opex family, operating income, and revenue-vs-plan
comparatives carry the flag with both versions cited on the
pack. A metric absent from either period simply has no
comparative — invention is not an option here either.

## Flux: the movement, decomposed and footing

Boards do not only ask what the number is — they ask why it
moved. The flux schedule (`flux.py`) answers with arithmetic,
not prose: for every figure with a comparative, the movement
is decomposed two ways and each decomposition foots to the
movement exactly.

**Same sources, same versions.** Each side of a movement is
computed from that period's source batches under that
period's own definition-pack version — the current run's
batches on one side; on the other, the batches *stamped on the
prior period's signed pack*, loaded by id from the store. The
stamped set matters: a restated batch supersedes in the
store, but the movement the board reads is current against
the signed record, so the prior side is decomposed from what
the signed record was built from — pre-restatement — and
reproduces the signed figures exactly. This is the
restatement recomputation's convention (each period under its
own definitions) applied to the decomposition.

**Two shapes, honestly bounded.** By entity: an entity figure
splits to itself; a `sum_converted` splits per entity at each
period's own rates; `add`/`subtract` merge their arguments'
splits with signs; `vs_plan` adds a **plan line** carrying the
baseline's own move, negated — the plan moved too, and the
schedule says so. By account: base metrics split over their
account sets; converted figures split per account across
entities. Two figures carry no account split and say why: an
elimination is a matched pairing of two legs under a `min()`,
not a sum of accounts, and the CRM pipeline figure has no GL
accounts at all — both ride a single group line instead. And
when a definition changed, the account union is used, so an
account that joined the set (6400, insurance, under v1.1.0)
appears with a zero prior contribution: the definition
change becomes a visible line in the decomposition, flagged
on the entry, never separated into a counterfactual
"definition effect" figure.

**Footing is structural, residue is named.** Contributions
are Decimal sums. Conversion is the one place parts and whole
can round apart (an account cell converted per entity against
a figure converted per entity total); when they do, the
residue is appended as a `rounding` contribution — labelled,
signed, visible — never folded into a driver.

**Materiality is policy, stated on the schedule.** A movement
is material when it reaches either bar in `policy.py` — an
absolute bar in the figure's own currency, or a percentage
bar against the prior figure. Material entries order their
drivers by size; immaterial entries are computed and checked
identically but listed plainly. The thresholds ride the
schedule itself, and the verifier checks the flags against
the schedule's own stated bars.

**The check is a second implementation.** `verify_flux`
recomputes every entry from the two batch sets with this
module's own figure machinery — never importing the
producer's decomposition — and compares line for line: the
entry set against the comparatives, each movement against its
comparative's change, each prior value against the signed
figure, each contribution against recomputation, each
decomposition against its own sum, each material flag
against the stated thresholds. A disagreement is a
`FLUX_MISMATCH` variance and blocks the pack like any other.
The narrative then quotes flux only in the verified branch,
and `build_narrative` re-ties every entry it receives to the
verified figure it explains before speaking — a flux number
is a figure for the round-1 rule, and is treated as one.
When the prior period's definition version or a stamped batch
is unavailable, the schedule is absent rather than computed
under the wrong definitions — the same degradation the
restatement layer accepts.

## The gate: segregation as structure

The LangGraph pipeline (`graph.py`) has three nodes that matter:

1. **engine** — proposes figures; writes nothing but the draft
   pack record.
2. **verify** — recomputes, disposes: verified figures, a
   checked flux schedule where comparatives exist, and a
   narrative (verified figures only, `narrative.py` refuses
   anything else) on a pass; named variances on a block.
3. **gate** — an `interrupt` on a verified pack, checkpointed
   in Postgres; a blocked pack never reaches it.

The controller's decision arrives through the service
(`sign_off`), which validates the human (a name is required),
the pack's state (AWAITING_CONTROLLER only), the stamps
(current sources), and — from the second month on — the
restatement gate (an unacknowledged restatement of the prior
period holds the signature) before resuming the graph. Three
roles, three code paths, no shared "just proceed" switch
anywhere.

## The sign-off chain: the signature is the third act

Until round 11, the gate above was one act: a named
controller signed, and that was the whole of the close's
accountability at signing — thinner than the governance the
rest of the system had grown (dispositions are named acts,
acknowledgements are named acts, activations and waivers
are named acts). Signing is now a chain of three ordered
acts by three different people, recorded on the pack
(`signoff_chain.py` holds the vocabulary and the stamps;
the service holds the acts):

1. **Preparation** — a named preparer states the pack is
   ready. The act stamps the pack as it stands — figure,
   variance, and disposition counts, and the readiness
   statement's status where one governs — because that is
   what the preparer is vouching for.
2. **Review** — a named reviewer states they reviewed the
   pack, in a note in their own words (the acknowledgement
   precedent: review is evidenced, not implied). The act
   stamps the same counts at review time: what the review
   covered is on the record, and the console, the API, and
   the pack's face all show the reviewer the variances, the
   dispositions, and the readiness statement the stamp
   summarizes.
3. **Signature** — the controller's act, and exactly the
   act it was before the chain existed: the same decision
   record, the same SIGNED_OFF status, the same run closing.
   Everything downstream — comparatives, carries, drills,
   bundles — keys on the controller act exactly as it keyed
   on the single signature, and cannot tell the chain
   exists except by reading the pack's richer face. That
   was a design constraint, not a side effect: the chain
   deepens accountability at the gate without moving a
   single downstream read.

The refusals are the discipline. Out-of-order acts are
refused by name (a review with no preparation under it, a
signature with no review). The same person in two roles is
refused by name — the reviewer cannot be the preparer, and
neither earlier hand can sign — the two-eyes rule the
system already kept for shift handoffs and template
promotion elsewhere in this program: an act and its check
are never the same person's. One preparation and one
review stand per pack; to start over, the pack is
withdrawn and the close rebuilt.

**Where the blocking check bites.** It bites where it
always bit — at verification: a pack with blocking
variances never leaves BLOCKED, and a BLOCKED pack never
reaches the gate. The chain's first act inherits that
exactly: preparation requires AWAITING_CONTROLLER, so a
blocked pack cannot even be prepared — the first step of
the chain is the first place the bite is *felt*, but the
check itself did not move, and the chain wraps the gate
without softening it. The two honest exits from BLOCKED
are unchanged: fix the sources and rebuild, or accept each
break on the record with a disposition and rebuild under
it. Every refusal the signature always made — blocked,
stale, unacknowledged restatement, anonymous — keeps its
ground and its order; the chain check is the last gate the
signature passes, after all of them.

**Withdrawal.** Before the chain completes, the preparer
may take the pack back: a named act with a reason, on the
pack's record (the append-only idiom — the withdrawal is
stated, and the chain acts that stood stay stated). Only
the preparer can withdraw: the act undoes their own
statement of readiness. The pack leaves as WITHDRAWN — it
is never edited back into play; the close is rebuilt
instead, and the withdrawn pack is exempt from staleness
marking alongside the decided states. After the
controller's signature there is no withdrawal at all, by
name: a signed pack is immutable, and a period that must
be corrected is corrected by the restatement machinery,
which is untouched.

**"Figures frozen from the preparation act."** Surveyed
mechanically, a built pack's figures are never mutated by
any code path — dispositions land only on BLOCKED packs,
acknowledgements record beside the figures, staleness
retires unsigned packs whole. The preparation act's stamp
is therefore the freeze made legible: the counts the
preparer vouched for, against which the reviewer's stamp
and the signed record can be read. A pack whose stamps
moved under it goes STALE like any unsigned pack — chain
acts and all — and a rebuild starts the chain fresh.

**Legacy signatures.** Packs signed before the chain
existed carry the single signature and no chain, and the
record says so: the evidence bundle projects the chain as
`null` and its text rendering states the single-act
signature plainly. No preparation or review is ever
reconstructed for them — the honest-null idiom every
younger section of the bundle already kept. For packs
signed under the chain, the bundle's completeness checks
extend to it: one preparation, one review, in order,
three different hands, or generation refuses with the gap
named.

## Variance disposition: governance around the verdict

Until round 7, a blocking variance had exactly one exit:
fix the books and rebuild. Real closes have a second honest
exit — a controller reviews the break, judges it immaterial
or a known timing difference, accepts it in writing, and the
item is carried into the next period as an opening item that
must clear there. The design work is keeping that exit from
becoming a dismiss button, and the load-bearing decision is
where the layer lives: **in the service, around the
verifier — never inside it.** The verifier's code does not
know dispositions exist. A variance it computes stands on
every pack that computes it, word for word, whether or not
anyone has accepted it; the eval pins this by comparing the
signed-under-disposition pack's variances and figures to the
blocked pack's, exactly.

The record (`dispositions.py`, `Disposition` in
`schemas.py`) names the exact break accepted: code, entity,
metric, a *subject* where those do not suffice (the pair, the
elimination, the journal — read from the record the verifier
produced, in its own wording), and the variance's detail text
itself. Coverage is therefore exact, not thematic: an
acceptance written for a $560.00 disagreement does not cover
the same pair disagreeing by $1,120.00 next month. Actor and
reason are required, and the refusals name their grounds —
an unnamed controller, a missing reason, a pack that is not
BLOCKED, a code the pack does not carry. The taxonomy is the
pipeline's own: *blocking* is every variance that holds a
pack at BLOCKED. The one variance that is not blocking,
`RESTATED_PRIOR_PERIOD`, is refused by name — it holds a
signature, not a pack, and already has its governance in the
acknowledgement; letting a disposition swallow it would give
one break two competing records. The informational flags
(`DEFINITION_CHANGED`, `RATE_CHANGED`) are not variances at
all, and the refusal for them is the taxonomy's: there is no
blocking variance by that name to accept.

Recording a disposition changes neither the variance nor the
pack — the blocked pack stays BLOCKED, its record now
carrying the acceptance in an append-only list. What a
disposition governs is the close's *next build*: the service
prepares the run's governing acceptances (each supersession
chain reduced to its head) into the build context, and the
verify node — after the verdict is fully computed, variances,
comparatives, flux, and restatement alike — checks coverage.
Every blocking variance covered: the pack is presented for
sign-off (`AWAITING_CONTROLLER`) with the covering
acceptances copied onto its face, and an audit entry states
that the verdict stands and names each acceptance. Any one
uncovered: BLOCKED, exactly as before. Two consequences are
deliberate. First, there is no path where a disposition
mutates a pack into signability in place — the presented
pack is a fresh verification from source, so what signs is
always a pack the verifier actually computed. Second, a
disposition that is never needed (the books get fixed and
the rebuild verifies clean) simply never reaches a signed
face — and, per the carry rule below, carries nothing.

Changing an acceptance is a new record whose `supersedes`
names the record it replaces, on the append-only idiom the
store already keeps for batches. There is deliberately no
un-accept: a controller who reconsiders writes the new
reason, and the chain shows both readings. (An acceptance
also cannot be withdrawn by superseding it with an empty
record — a superseding record is itself an acceptance, with
actor and reason, or it is refused like any other.)

The carry is the layer's second half. Only acceptances that
reached a **signed pack's face** carry — they are the ones a
signature relied on. At the next period's build, the service
prepares them as the build's carried set, and the verify
node re-tests each against the new pack's own variances:
an exact match is `STILL_PRESENT` (the item blocks again,
like any variance), an identity match with different detail
is `MUTATED` (same break, different figures — not covered
by the old acceptance, by the exactness rule above), and no
match is `CLEARED` — cleared *by events*, the only way an
item ever leaves, since nothing in the layer deletes one.
Each outcome lands on the new pack as an `OpeningItem`
quoting the acceptance that carried it: origin period and
pack, the controller, the reason, and the carry count.
Accepting a still-breaking (or mutated) carried item again
inherits the lineage: the new record's `carry_number` is the
item's plus one, its origin still the first acceptance — so
the signed face of the third month's pack states, in data,
that this is the same break's second carry. Age is not an
annotation added for color; it is the fact a CFO reads first
about a carried break, so it is computed, not narrated.

One surface needed care: the narrative. A pack presented
under disposition may carry figures that all verify while a
pair stands in disagreement — and the narrative's
eliminations sentence speaks of legs "verified present and
paired", which would be false on such a pack; its builder
also raises on any unverified figure, which a dispositioned
figure mismatch is. The presented path therefore builds the
narrative only where it cannot misstate (every figure
verified, no open pair, no flux failure) and otherwise
leaves it absent, with the audit trail saying why: on such a
pack, the account of the close is the variances and the
acceptances, both on the face. The evidence bundle's
completeness rule bends in exactly the same place and no
further — see the next section.

## Definition change governance: the ruler changes by act

Everything above assumes the definition pack — the catalog
of what the figures *are* — and rounds 2 and 4 taught the
close to live with two versions at once: comparatives cite
each period's own version, flux flags the figures whose
definition changed. What none of that governed was the
change itself. A new pack file could simply appear in the
registry, and the next run would pick it up; the
`DEFINITION_CHANGED` flags would report, afterwards, that
the ruler had been swapped mid-argument. `governance.py`
builds the missing front door, in three parts.

**The dry-run: impact first, computed.** Given a candidate
version and a period with a signed pack, the period is
recomputed twice from its stamped sources — under the
version the signed pack cites and under the candidate — and
the two results are diffed into a change list: figures whose
value moves (recomputed baseline → candidate value, delta,
delta %, each judged against the flux schedule's standing
materiality bars in `policy.py`), figures the candidate
adds, figures it drops, and the variance families each side's
verification produces over those sources, so a tie-out the
candidate would newly fail (or newly pass) is computed here,
not asserted. Three disciplines keep the measurement honest:

- *The values compared are the verifier's.* Each side runs
  the deployment's engine over freshly built marts, and the
  diff reads the verifier checks' recomputed values — never
  the signed pack's recorded figures, never the engine's
  proposals. The verifier's independence (its own
  aggregation, its own duplicate scan) is inherited whole.
- *Both sides convert at the signed pack's stamped rate
  table* — the round-6 rule applied to a recomputation. A
  rate table edited in a batch since sign-off then raises
  `RATE_TABLE_MISMATCH` on both sides alike and reprices
  neither; the candidate's effect is the only difference
  between the two columns.
- *The baseline is audited, not assumed.* A signed figure
  the baseline recomputation does not reproduce is listed as
  a baseline discrepancy (signed value beside recomputed) —
  the dry-run reports that its reference no longer
  reproduces instead of quietly measuring from doctored
  numbers.

The report is a pure function of its inputs and carries no
timestamp, so its canonical digest (the evidence bundle's
canonical form) is stable across recomputation — and the
service enforces the stability: re-running a recorded
dry-run returns the record, and if recomputation now
produces a different digest, that is a refusal naming the
drift, not a quiet rewrite. A dry-run signs nothing and
activates nothing; it is a record an act can cite.

**Activation: governing is a named act.** A candidate
governs future periods only through a `PackActivation`:
actor, reason, the version, the period it governs from, and
the dry-run it relies on, cited by id and digest. The
refusals each name their ground — an unnamed actor, a
missing reason, a version the registry does not hold, no
dry-run on record for the version (the impact must exist
before the act), the version already governing the
from-period, and a from-period that is already signed. The
last is the load-bearing one: an activation reaches only
periods not yet signed, so a signed period's cited version
is immutable by construction, and comparatives keep citing
each period's own version exactly as rounds 2 and 4 built
them. Activations are append-only; changing course is a new
activation for the same from-period, which supersedes the
earlier act on the record — the earlier act is never
edited or deleted, and the superseded never governs.

**Selection: a rule, printed.** Which version governs a
period is computed from the activation records — the
governing activation is the non-superseded act with the
greatest from-period not after the period, ties broken by
recording order — or, with no governing act, the
deployment's wired default. The rule is applied twice: at
run creation, where the answer is recorded on the run with
its source ("(activation ACT-…)" or "(deployment default)"),
and again at pack build, which is the computation that
actually governs the figures — an activation landing
between creation and build moves the build, and the pack's
audit says so, naming the run's recorded expectation beside
the version that governed. The first pack governed by a
newly activated version states the change on its face
(`BoardPack.definition_change`): version from → to, the
activation's actor and reason, and the cited dry-run's
headline counts. The statement is prepared only when an
activation governs the period *and* the prior signed pack
cites a different version — a second period under the same
activated version states nothing, because nothing changed
under it. The evidence bundle carries the section under the
same v1 rule as every layer before it (`definition_change:
null` for a pack with no change to state), with its own
completeness clause: the cited activation and dry-run must
stand in the store and the stored digest must match the
citation, or generation refuses with the gap named — a
bundle that cited a vanished act would be asserting the
very thing it exists to prove.

The staged candidate is v1.2.0: account 6400 leaves
operating expenses for a metric of its own, with a
consolidated line over it. It is a presentation change —
operating income cannot move, since the split adds back
exactly what it removes — which is what makes it the honest
test of the machinery: over signed October the dry-run must
show four moved figures (opex at both USD entities and the
two consolidated lines standing on it), four added, none
dropped, none material, and the eval's gold for all of it is
derived from the journals by hand.

## The audit evidence pack: projection, not computation

A signed pack is the close's internal record. The auditors,
though, do not take "the system verified it" as evidence —
they re-perform. `evidence.py` assembles the artifact they
re-perform from, and its defining discipline is that it
**computes nothing**: assembly reads the stored pack, its run,
its source batches, the definition pack at the version the
pack stamps, and the signed prior pack a comparative cites,
and arranges them into one document (JSON, plus a text
rendering generated from the same document so the two cannot
drift). A bundle figure equals the pack figure because it *is*
the pack figure, copied — the eval gate pins the equality
rather than trusting it.

Contents: the pack's identity (period, pack and run ids,
definition-pack id and version, mart version); every figure
with its value, its definition entry reproduced from the
stamped definition-pack version, its own source stamps, and
the verifier verdict as recorded (`Figure.status` — the
verify node's disposition, stored on the pack at verification
time); the source manifest — every batch the pack stamps, with
kind, entity, version, and the content hash recorded on the
batch at ingestion; the comparatives with their citations;
the flux schedule, when the pack carries one; the
intercompany pairs with both stated figures and their
verdicts, when the pack carries them; the
restatement report and its acknowledgement; the dispositions
on the pack's face and the opening items it carried in, when
it carries them; the definition change the pack was first
governed under, with the activation and dry-run behind it,
when it carries one; the standing
variances; and the sign-off record — decision, controller,
reason, time — with the run's checklist state, and, inside
it, the sign-off chain: the preparation and review acts
that preceded the signature, checked whole at generation
(one preparation, one review, in order, three different
hands) when a chain stands on the pack, and projected as
absent — `chain: null`, stated in words in the text
rendering — for a pack signed under the single-act
sign-off, before the chain existed.

The flux section joins the bundle **under the same `v1`
format** — the precedent the comparative layer set when it
joined in round 2. The format version names the bundle's
schema family, a projection whose sections mirror the layers
the pack itself carries; it is not a per-section changelog.
A pack signed before the flux schedule existed carries no
schedule and never will (a signed pack is never edited), so
its bundle states `flux: null` — the honest record that this
close predates the layer. The intercompany section joins by
the same rule (`intercompany: null` for a pack whose record
carries no pairs); a disagreement blocks sign-off, so a
cleanly signed pack's section shows the pairs that agreed —
and since round 7, a pack signed *under disposition* shows
the disputed pair too, with the disposition that accepted it
listed in the bundle's dispositions section beside the
variance it answers for: the two records travel together or
not at all. The dispositions and opening-items sections join
by the same rule again (`null` for a pack that carries
neither). Bundles already generated are
stored bytes beside their records and are never rewritten;
a new generation simply projects what its pack carries. That last item
deserves its argument: the checklist is not stamped on the
pack at signing; it is read back from the run. That is sound
because a signed pack's run is CLOSED, and a closed run
refuses ingestion — the checklist cannot have moved since the
signature froze it. The completeness check below asserts the
run is CLOSED and nothing is missing, so the claim is verified
at generation time, not merely believed.

Two gates guard generation:

- **State.** Only a `SIGNED_OFF` pack gets a bundle. Any other
  state is refused with the state named — an auditor bundle
  for a blocked or unsigned close would be a false artifact,
  however complete its contents.
- **Completeness.** Before anything is written: every figure
  must resolve to a definition entry in the stamped pack
  version and carry a `verified` verdict; every stamped batch
  must be in the store at the stamped version with a recorded
  hash; the run must be CLOSED with no missing sources; every
  comparative's cited pack must stand in the store as signed;
  a restatement must carry its acknowledgement. Any gap
  refuses generation, naming the gap. The verdict clause has
  exactly one exception, and it is the disposition layer's:
  a figure may stand with a verdict other than `verified`
  when the variance naming that figure is itself on the pack
  and a disposition on the pack's face covers that exact
  variance — the figure is then shown with its true verdict
  and its named acceptance, never upgraded to `verified`,
  and an acceptance covering no variance on the pack refuses
  the bundle as decoration. Any other unexplained verdict
  refuses as it always has. A partial bundle is
  never written — the failure mode this defends against is
  the partially-stored pack (an interrupted write, an archived
  store restored without its batches) producing a
  confident-looking artifact with holes in it.

Definition resolution follows the comparative layer's rule:
the service's live pack when it *is* the stamped version,
otherwise the versioned registry. An unresolvable version is
a refusal, never a substitution — definitions reproduced from
the wrong version would fabricate the evidence. (Generating
September's bundle through October's v1.1.0 service exercises
exactly this path: v1.0.0 comes from the registry, and the
bytes are identical to September's own service's.)

The bytes are canonical — fixed key order, lists sorted by
the keys an auditor sorts by, and no wall-clock field anywhere
in the document. Generation metadata (when it happened) lives
on the bundle *record*; the digest lives there too. The same
pack therefore regenerates byte-identical bytes forever, and
the service returns the existing record untouched when the
stored bytes still hash to the recorded digest. What the
bundle deliberately omits is the raw extracts themselves: the
manifest names them by id, version, and hash, and the bytes
sit in the ingestion archive — an auditor pulls the exact
extract a manifest line names and checks its hash against
the bundle, rather than trusting a copy of the extract
embedded in the artifact that cites it.

## Figure drill-down: the last mile, re-performed

The bundle lets an auditor re-perform the *close*. The drill
(`drill.py`) answers the per-figure question the bundle
cannot: which journal lines, in which batches, sum to *this*
number. It is a third computation of the figure — after the
engine's proposal and the verifier's recomputation — and it
is deliberately independent of both: it flattens the pack's
stamped batches with its own scan (applying the pack's
duplicate rule itself: a repeated journal id inside one
extract counts once, first copy), sums with its own code,
and converts at the rate table the pack stamps. It reads
nothing from the marts and nothing from the verifier; the
only stored number it trusts is the one it must foot to —
the figure on the pack record.

Coverage follows the definition's shape, and stops where the
shape stops. Base GL figures drill to their lines, each
carrying batch and version, journal and position within it,
account, both stated amounts, and the signed contribution in
entity currency. CRM figures drill to their records.
Eliminations drill to both legs — every intercompany line on
each account, grouped per entity — and the matched amount is
stated as the rule it is (the lesser converted leg).
Converted figures drill per entity: lines, subtotal, the
stamped rate, the converted subtotal. Conversion is shown at
the subtotal because the close converts subtotals — a
per-line converted amount would be a precision the close
never computed, and the drill does not fabricate precision.
Derived figures carry no lines at all: an `add` / `subtract`
/ `vs_plan` figure's drill is its composition tree, the
operands' drills nested with the operator named, and the
plan baseline appears as a `plan` node — authored data from
the definition pack, labelled as such, because the figure
stands on it and pretending it is a source line would be the
one lie this layer exists to avoid. A base definition whose
measure the close gives no line semantics (`sum_amount` over
GL lines — the measure belongs to CRM records, and neither
the engine nor the verifier defines it over journal lines)
is refused by name: the drill approximates nothing.

The identity is enforced at the root: the composition must
equal the figure on the pack, Decimal-exact, or the drill is
not served — `DRILL_MISMATCH` names the figure and both
totals. This is the tamper detector working as designed: a
source record edited under a pack's stamps changes the
composition, not the recorded figure, and the drill says so
instead of footing a lie. An FX batch edited in place moves
nothing: like the verifier, the drill judges conversions at
the stamp, and a later table reprices no drill.

Any pack state may be drilled. The drill is computed from
the pack's *stamps* — the batch ids and versions on its
record, the rate table on its record — never from the run's
current slot map, so a stale pack still drills truthfully on
the sources it was built from, and a blocked pack shows the
lines behind the figures it proposed. The pack's state rides
the drill (`pack_status`), named on its face, following the
evidence idiom: state is disclosed wherever an artifact
could be misread, and refusal is reserved for what would
make the artifact false — a figure the pack does not carry,
a stamped batch missing from the store or standing at
another version, a definition version that cannot be
resolved.

The bundle's `drills` section is where the two layers meet:
for each figure, the composed total, the line count, and a
SHA-256 digest of the full drill, computed at assembly time
by performing the drill. The size tradeoff is deliberate —
the bundle already manifests the extracts by hash, and
embedding every line of every figure would duplicate that
content at length; a citation by digest keeps the bundle the
size of the close's *claims*, while the drill endpoint (or
CLI, or console) re-performs the full tree against the same
pack on demand and the digest either reproduces or something
moved. Because stamps and sources persist for any signed
pack, the section has no absence case — unlike `flux` or
`fx`, there is no pre-drill signed pack whose bundle must
confess a gap. The one non-footing entry is a mismatch: a
source moved under the signed pack's stamps after signing
records both totals and no digest, in the same spirit as a
dispositioned figure keeping its true verdict.

## Pre-close readiness: the close does not start on missing sources

The checklist in the section above is a presence machine: a
slot is either filled or it isn't, and the run's status is
the whole story. Presence is the floor a build must clear,
but it is not what a close *expects*. A close expects
specific deliveries — the corrected GL extract, not any GL
extract; a rate table that can actually convert the
period's currencies — and until round 10 nothing in the
system could say so. A missing or superseded extract
surfaced late: as a variance on the pack, an unnamed
`KeyError` when a conversion met a currency the received
table didn't carry, or a figure that simply felt wrong.
Readiness moves that knowledge to before the build, as
governed data.

**The expectation manifest.** Per period, a named
controller records what the close expects: one entry per
source slot (the same `ENTITY:kind` / `GROUP:kind`
identity the run's checklist uses), the delivery version
expected where one is stated, and the batch id the
expectation was taken from, where it was. The record names
its author and carries a note — where the expectation
comes from — and it is append-only in the by-now-familiar
way: amending what a period expects is a new *version* of
the manifest naming the one it supersedes, so the version
that governed a check or a build stays citable. The
manifests for the bundled periods are **derived**, and
the derivation is a stated rule, not a quiet invention:
for each slot, the terminal delivery of the world's
supersession chain — the batch the close actually used.
September's manifest therefore expects HLD:gl, HLE:gl,
and GROUP:fx at v2 (the corrected extracts and the revised
table its signed close stood on) and everything else at
v1; October and November closed on first deliveries
throughout. A deployment's controller authors manifests
from the close calendar the same way, through the same
service calls.

**The check.** `readiness.check_readiness` is a pure
function of the store, the run, the governing definition
pack, and the manifest: it registers nothing and mutates
nothing (pinned: the store is byte-identical across a
check). Each entry is judged ok / missing / short / ahead.
The version rule is **exact equality**, and it is worth
saying why: batch versions in this system are per-batch
content stamps — a delivery *is* a specific version — so a
received batch at any other version is a different
delivery. Below the expectation, the close would start on
a superseded extract. Above it, the manifest predates the
delivery, and the governed remedy is to amend the
manifest, not to pretend the expectation covered it. An
entry may state no version, in which case presence is the
whole expectation for that slot. The rate table is judged
as **coverage**: the FX batch must carry a table, and the
table must carry a rate for every currency the governing
pack's entities book in (other than the reporting
currency) — the currencies come from the definition pack
that will actually build the period, so the check judges
the table the build would use. Each failure becomes a
named item whose name is its identity — the slot for a
missing source, slot + both versions for a mismatch,
`FX:EUR (no rate in table v3)` for a rate gap — because a
waiver must name items in exactly those words. The prior
period's state rides the report as information —
`SIGNED` with the pack cited, `NO_PRIOR_CLOSE` (a first
close), or `PRIOR_UNSIGNED` — and is never a failure:
surveying what the build actually assumes about the prior
period shows it assumes *nothing*. Comparatives are
defined over the prior period's signed pack and degrade to
absent when there is none; carried items flow through
signed packs only. A readiness rule that blocked on an
unsigned prior period would invent a requirement the close
does not have, so the report states the fact and the gate
ignores it.

**The gate and the waiver.** The gate sits in
`CloseService.build_pack` — the one door the API, the CLI,
the demo, and the evals all build through — after the
standing checklist refusal (presence first) and after pack
selection (the check judges the governing pack's
currencies). When a manifest governs the period and the
check fails, the build is refused with a `ReadinessError`
naming every uncovered item and the manifest it failed
under — unless the period's waivers cover the failing
items. A **waiver** is a named controller's record: actor,
reason, and the exact items it covers. Recording refuses,
each by name: no actor; no reason; a blanket waiver (a
licence covering whatever turns out to be missing is not a
record a controller may make); a period already signed (a
waiver governs a close still to be built); no run for the
period (the check runs against a run's received sources —
there is nothing to waive against); no manifest (no stated
expectation, so no named failure exists to accept); and
any item the period's current check is not failing on.
Coverage is re-derived at build time from the *current*
check, so a waiver written against one failure never
stretches to a different one — an October waiver for a
missing CRM extract does nothing for an AR delivery that
arrives a version short, and the eval pack pins exactly
that. A pack built under a manifest carries the outcome on
its face: a `ReadinessStatement` — COMPLETE with the
manifest id and version cited, or WAIVED with the items
listed and each covering waiver cited (id, actor, reason,
the subset it covered) — plus a `readiness_stated` audit
event in the same words. Its evidence bundle resolves the
citations the way it resolves the governance ones: the
manifest record must stand at the cited version, and every
cited waiver must stand with the actor, reason, and items
the citation quotes, or generation refuses with the gap
named; a close that ran with no manifest projects
`readiness: null`, the honest absence. A period with no
manifest is deliberately unchanged behaviour — the
standing checklist alone gates it, and its packs carry no
statement: readiness is an expectation a controller chose
to state, and where none was stated the system does not
invent one.

## Data model

Four migrations, six JSONB tables mirroring the sibling
blueprints' record discipline:

- `source_batches` — every extract ever ingested, append-only
  (`0001_close.sql`);
- `close_runs` — run state incl. the checklist and slot map,
  and the definition version the selection rule recorded for
  the run's period;
- `board_packs` — figures, variances, stamps, narrative,
  sign-off, and (from the second period) the comparative
  layer: cited prior figures, the restatement report, and its
  acknowledgement; and the disposition layer: the acceptances
  recorded on the pack or carried onto its face, and the
  opening items it was re-tested against; and, on the first
  pack governed by a newly activated definition version, the
  change statement; and the sign-off chain: the preparation
  and review acts (role, actor, moment, note, and the counts
  each act stamped), and the withdrawal record when the
  preparer took the pack back. All ride the JSONB payload —
  no migration; the store's shape was already "the pack
  record, whole";
- `evidence_bundles` — one row per generated audit bundle
  (`0002_evidence_bundles.sql`): pack and period for lookup,
  the object-store keys, the digest, the counts, and the
  generation time. The bundle bytes themselves are not in the
  database;
- `definition_governance` — the dry-run reports and the
  activations (`0003_definition_governance.sql`): one JSONB
  record per act of governance, keyed by record id with kind,
  pack, and version columns for lookup. This one did need a
  migration, on the evidence-bundle precedent: governance
  records belong to the definition registry, not to any one
  run or pack — an activation is written before the periods
  it governs have runs at all — so they cannot ride another
  aggregate's payload.
- `readiness_records` — the expectation manifests and the
  readiness waivers (`0004_readiness.sql`): one JSONB
  record per governance act, keyed by record id with kind
  and period columns for lookup. A migration again, on the
  same justification: a period's readiness records belong
  to the period's close, not to any one build of it — a
  manifest is written before the period's run exists, and a
  waiver is consulted by every build the period attempts —
  so they are an aggregate of their own, not rows on a run
  or a pack.

Raw extract bytes are additionally archived to object storage
at ingestion (`extracts/<period>/<batch_id>.json`), so the
evidence chain survives independently of the record store.
Generated bundles live there too, under
`evidence/<period>/<pack_id>/evidence-v1.json` and
`evidence-v1.txt` — the record in `evidence_bundles` is the
index entry that names them and carries their digest.

## What a production deploy still needs

- **The real connectors.** The bundled connector serves
  synthetic extracts; a deployment wires NetSuite/QuickBooks/
  Salesforce pulls (scheduled or webhook-triggered) into the
  same batch discipline — immutable, versioned, superseding.
- **The aidnn workspace wiring.** `AIDNN_WORKSPACE_URL` set to
  the deployment's agreed endpoint; the first two closes run
  shadowed against the offline reference engine and hand-built
  numbers before the gate trusts the seam.
- **Secrets and TLS.** Compose credentials are local defaults;
  production injects from a secrets manager and terminates TLS
  in front of every hop, including the workspace endpoint.
- **The close calendar.** Scheduling, per-entity SLAs on
  extract delivery, and variance routing to owners are
  operational wrappers around the checklist this repo enforces;
  they belong to the customer's runbook, seeded by the audit
  trail the runs already produce.
