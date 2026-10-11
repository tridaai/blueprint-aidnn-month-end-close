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
definitions that produced its signed pack.

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
2. **Elimination pairing** — IC legs summed per entity from raw
   lines, converted per entity; revenue legs ≠ cost legs →
   `UNMATCHED_IC_LEG`, naming both totals and the gap.
3. **Tie-outs** — subledger vs GL per entity: `SUBLEDGER_TIE_OUT`,
   naming both amounts and the gap.
4. **Figure reproduction** — every defined figure recomputed;
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
  batch; a pack stamps the FX version it used. A revised rate
  table is a superseding batch like any other — see staleness.

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
restatement report and its acknowledgement; the standing
variances; and the sign-off record — decision, controller,
reason, time — with the run's checklist state.

The flux section joins the bundle **under the same `v1`
format** — the precedent the comparative layer set when it
joined in round 2. The format version names the bundle's
schema family, a projection whose sections mirror the layers
the pack itself carries; it is not a per-section changelog.
A pack signed before the flux schedule existed carries no
schedule and never will (a signed pack is never edited), so
its bundle states `flux: null` — the honest record that this
close predates the layer. Bundles already generated are
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
  refuses generation, naming the gap. A partial bundle is
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

## Data model

Two migrations, four JSONB tables mirroring the sibling
blueprints' record discipline:

- `source_batches` — every extract ever ingested, append-only
  (`0001_close.sql`);
- `close_runs` — run state incl. the checklist and slot map;
- `board_packs` — figures, variances, stamps, narrative,
  sign-off, and (from the second period) the comparative
  layer: cited prior figures, the restatement report, and its
  acknowledgement;
- `evidence_bundles` — one row per generated audit bundle
  (`0002_evidence_bundles.sql`): pack and period for lookup,
  the object-store keys, the digest, the counts, and the
  generation time. The bundle bytes themselves are not in the
  database.

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
