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
catalog-change regression suite.

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

## The gate: segregation as structure

The LangGraph pipeline (`graph.py`) has three nodes that matter:

1. **engine** — proposes figures; writes nothing but the draft
   pack record.
2. **verify** — recomputes, disposes: verified figures and a
   narrative (verified figures only, `narrative.py` refuses
   anything else) on a pass; named variances on a block.
3. **gate** — an `interrupt` on a verified pack, checkpointed
   in Postgres; a blocked pack never reaches it.

The controller's decision arrives through the service
(`sign_off`), which validates the human (a name is required),
the pack's state (AWAITING_CONTROLLER only), and the stamps
(current sources) before resuming the graph. Three roles,
three code paths, no shared "just proceed" switch anywhere.

## Data model

One migration (`0001_close.sql`), three JSONB tables mirroring
the sibling blueprints' record discipline:

- `source_batches` — every extract ever ingested, append-only;
- `close_runs` — run state incl. the checklist and slot map;
- `board_packs` — figures, variances, stamps, narrative,
  sign-off.

Raw extract bytes are additionally archived to object storage
at ingestion (`extracts/<period>/<batch_id>.json`), so the
evidence chain survives independently of the record store.

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
