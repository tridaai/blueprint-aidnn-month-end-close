<p align="center">
  <img src="https://trida.ai/logos-rounded/trida-rounded.png" alt="Trida AI" width="96">
</p>

# Blueprint — aidnn Month-End Close, Deployed

A working prototype of the deployment a multi-entity finance
team needs around an AI analytics platform: source extracts
arrive from the group's systems, a **versioned definition pack**
says what every figure means, the finance engine behind a port
answers the pack's defined questions — and then an **independent
verifier recomputes every figure from the source extracts, in
code**, before a controller is allowed to sign. A figure the
verifier cannot reproduce blocks the pack, with the variance
named. **Nothing in this system posts to a general ledger or
files anything.**

Where aidnn sits is the point, so it is stated plainly: aidnn's
agents do the analysis in a live deployment; the distance
between a signed customer and a trusted first close is the work
*around* the product — connectors into multiple ERP instances
with divergent charts of accounts, the metric catalog (what
"revenue" means *here*, recognition cutoffs, intercompany
eliminations), and independent validation of the first closes
against source. That deployment layer is what this blueprint
builds: connectors, governed data marts, the definition packs,
the verifier, the checklist discipline, and the controller's
gate.

One honest fact shapes the integration: **aidnn publishes no
public API** (checked October 2026). So the engine seam is a
port with a documented *integration contract* — the defined
queries an FDE implements against the customer's deployed aidnn
workspace during onboarding — plus a complete offline reference
engine implementing the same contract, which is what the tests,
evals, and demo run. The blueprint never invents endpoints and
calls them aidnn's, and the service refuses to serve the
offline engine's answers under aidnn's name.

This is an independent Trida AI blueprint. It is **not
affiliated with or endorsed by Isotopes AI**; it is built by
Trida AI from public information about aidnn to show how a
forward-deployed team would put the platform into production
inside a multi-entity finance operation. Everything in the
dataset is synthetic — there is no real company, ledger, or
person anywhere in this repository.

> **Work in progress** — this blueprint is built and passing its automated test and eval gates, but it has not yet finished hands-on local testing, and its companion blog post is not yet published. Expect changes. This notice comes off when both are done.

---

## Try it in 3 commands

```bash
git clone https://github.com/tridaai/blueprint-aidnn-month-end-close
cd blueprint-aidnn-month-end-close
uv sync --extra dev && uv run aidnn-close-demo
```

The demo runs Harborlight Group's September close twice. The
first attempt, on the extracts as they arrive, is **blocked by
the verifier** — a duplicated journal, an intercompany leg with
no counterpart, an AR tie-out gap where a services billing was
posted to payroll. Then the corrected extracts land late, the
first pack goes **stale by its version stamps**, and the rebuilt
pack verifies figure for figure — where a named controller
signs it. A second act closes **October**: September's parent
extract is restated after sign-off, the definition pack has
been upgraded, and October's pack presents every figure against
September's *signed* figures — restatement named, signature
held until a controller acknowledges it. It runs on the
**offline reference engine**; see
[Configuration](#configuration) for the aidnn seam.

Serve the console instead:

```bash
uv run uvicorn aidnn_close_agent.api:app --port 8000
# → Console: http://localhost:8000/   API docs: http://localhost:8000/docs
```

No uv? The pip fallback is the two-step form in the Makefile:
`make install-pip` (the frozen set first, then the package
itself).

Or the full stack:

```bash
docker compose up --build
# → Console: http://localhost:8000/ — records in Postgres, extracts in object storage
```

---

## The problem

A finance team's first month-end close on an AI analytics
platform is where trust is won or lost, and the risk is rarely
the analysis. It is everything around it: three entities on two
ERPs and two currencies; a chart of accounts that matches no
template; "revenue" defined in the controller's head; an
intercompany leg one subsidiary forgot to post; a rate table
that moved mid-close. An agent that produces a beautiful pack
from the wrong sources is worse than no agent, because the pack
gets believed.

This blueprint is Trida's answer, shaped as a deployment of
aidnn: the platform does what it is for (connected, verified
analysis over the company's systems), and a production-shaped
layer around it makes the first close trustworthy — sources
versioned, definitions explicit, every figure independently
recomputed, and a human gate at the end.

## How it works

```
extracts ──► ingest ──► marts ──► engine ──► VERIFY ──► GATE ──► signed pack
(NetSuite /   (archive,   (governed,  (Finance-  (recompute   (controller
 QuickBooks /  checklist,  DQ rules,   EnginePort: every figure sign-off)
 Salesforce)   versions)   fenced)     aidnn /     from source,
                                       offline)    in code)
```

- **Connectors + checklist** — extracts land as immutable,
  versioned batches; a corrected extract is a *new* batch that
  supersedes the old one, never an edit. A close run's checklist
  tracks which required sources (GL + AR per entity, FX, CRM)
  are in force; **a pack cannot be built until the checklist is
  complete** — the refusal names what is missing.
- **Governed marts** — the mart builder normalizes extracts
  once, in code: Decimal amounts, the pack's data-quality rules
  applied (a duplicated journal id is voided, not summed twice),
  journal memos passed through an injection screen and carried
  fenced. Every mart set carries a version digest of the exact
  batches and pack version that shaped it.
- **Definition packs** — the metric catalog as versioned JSON:
  each metric defined once (base aggregates over accounts, or
  derived arithmetic — consolidation through the rate table,
  eliminations, plan variance), plus elimination definitions,
  subledger tie-outs, and data-quality rules. The engine and the
  verifier read the **same pack version**, and every pack record
  stamps the version that produced it.
- **FinanceEnginePort** — one seam, two adapters. `aidnn`: the
  integration contract (defined queries over the governed
  marts) against the workspace endpoint a deployment agrees
  with Isotopes — no URL configured means startup refuses, in
  those words. `offline`: the deterministic reference engine
  the tests and evals run. The pipeline cannot tell which
  engine answered; the verifier does not care.
- **The independent verifier** — a *separate implementation* of
  the pack's semantics that reads **source batches directly,
  never the marts**, and recomputes every figure. It also runs
  its own structural checks: duplicate journal ids, AR-to-GL
  tie-outs, intercompany leg pairing at two grains — the
  pooled totals, and each pair keyed by counterparty. Any
  variance — or any
  figure it cannot reproduce — blocks the pack by name. Honest
  limit, stated in the open: a figure that foots to a *wrong*
  source recomputes cleanly; what catches that class is the
  tie-out family, which is why the planted mis-post is caught
  by the AR tie-out and not by arithmetic.
- **Staleness by stamps** — a pack records the exact source
  versions it was built from. When a late extract or a revised
  rate table lands, the affected packs go STALE in the same
  step, and a stale pack cannot be signed — sign-off re-checks
  the stamps, so the rule holds even if a marking step is
  missed.
- **Rate provenance** — the stamp carries the rate table
  itself, not just its version, so every converted figure's
  provenance names the rate that produced it. The verifier
  recomputes conversions at the **stamped** table — never at
  whatever table the batch set carries when it runs — and a
  table that moved after the run, or was edited in place under
  the same version, is named `RATE_TABLE_MISMATCH` while the
  figures still reproduce at their stamp. A figure that
  reproduces at the batch table but not at its own stamp was
  converted off-stamp, and is named per figure as the
  provenance break it is, not blurred into a figure mismatch.
- **The gate** — verified packs stop mid-pipeline at a
  LangGraph interrupt, checkpointed in Postgres, until the
  group controller signs or returns them, by name, with a
  reason. Engine proposes, verifier disposes, controller signs:
  three separate code paths.
- **The sign-off chain** — the signature is a chain's third
  act, not a click. A named **preparer** first states the
  pack is ready, stamping the counts they vouch for (figures,
  variances, dispositions, the readiness statement's
  status); a named **reviewer** — never the preparer — then
  states they reviewed it, in their own words, stamping what
  the review saw; only then does the controller sign, and
  neither earlier hand may hold the pen. Out-of-order acts
  and same-person acts are refused by name. The blocking
  discipline is untouched and bites at the chain's first
  step: a blocked pack cannot even be prepared — its breaks
  are fixed at the source, or accepted on the record and the
  close rebuilt. Before the chain completes, the preparer
  may **withdraw** the pack (a named act with a reason, on
  the record; the close is rebuilt instead); after the
  signature, nobody may — a signed pack is immutable, and a
  restated period is corrected by restatement, not by taking
  history back. The controller's act itself is exactly what
  it was when signing was one act — comparatives, carries,
  and bundles key on it unchanged — and the pack's face and
  its evidence bundle carry the whole chain, so an auditor
  reads who prepared, who reviewed, and who signed. A pack
  signed before the chain existed states its single legacy
  signature as exactly that; no earlier acts are invented
  for it.
- **The narrative** — composed **only from verified figures**:
  the builder raises on any unverified input, so a blocked pack
  has no narrative and no number can be talked into the board
  pack that the verifier has not recomputed.
- **Comparatives from the signed record** — from the second
  month on, every figure carries a comparative: the prior
  period's figure **copied from the prior period's signed
  pack**, with the pack id and definition version cited, plus
  the change and % computed in code. The comparative is
  *checked against the signed record* exactly — never
  recomputed over prior sources, which may have been restated
  since the board approved them.
- **Restatement, named and gated** — a corrected extract for
  an already-signed period arrives outside any run (signed
  history is never edited). At the next build, the prior period
  is recomputed under *its own* definition-pack version over
  the restated sources; every signed figure that no longer
  reproduces is listed — signed vs recomputed — in a
  `RESTATED_PRIOR_PERIOD` variance. The new pack's signature is
  **refused until a named controller acknowledges the
  restatement** on the record; the variance and the
  acknowledgement then stay on the pack permanently.
- **Variance disposition: the second honest exit** — a blocked
  pack has always had one exit: fix the books and rebuild.
  Real closes have another, and it is built as governance, not
  as a dismiss button. A named controller may accept a
  blocking variance in writing — actor and reason required,
  the record naming the exact break (code, entity, metric,
  subject, and the variance's own detail text, figures and
  all) — as `ACCEPTED_CARRY`. Recording changes neither the
  variance nor the blocked pack: the close's next build
  re-verifies from source and is presented for sign-off only
  when **every** blocking variance is covered by an
  acceptance, with the acceptances copied onto the pack's
  face — count and items — beside the variances, which stand
  exactly as computed. Only blocking variances are
  dispositionable: the restatement variance holds a signature,
  not a pack, and keeps its own governance (the
  acknowledgement); the definition and rate flags are not
  variances at all, and there is nothing to accept. Acceptances
  are append-only — changing one is a new record superseding
  the old, never an edit, and there is no un-accept. And an
  accepted break is carried, not forgotten: every acceptance
  on a signed pack's face opens the next period as a named
  **opening item**, re-tested against the new period's own
  recomputation — cleared by events, still present (it blocks
  again, and a second acceptance states plainly that it is
  carry 2, with the first acceptance's period, controller, and
  reason quoted), or mutated (the same break with different
  figures — the old acceptance does not cover the new one).
- **Definition changes are flagged, not smoothed over** — when
  a period runs under a newer definition-pack version,
  comparatives whose metric (or anything it derives from, or
  its plan baseline) was redefined carry a `DEFINITION_CHANGED`
  flag with both versions named. October runs under pack
  v1.1.0, which widened operating expenses to include
  insurance; September's comparatives say so.
- **Rate changes are flagged the same way** — definitions are
  one silent input; rates are the other. September signed at
  EUR 1.10 (rate table v2); October converts at 1.12 (table
  v3). A consolidated comparative whose derivation converts
  money booked in a currency whose rate moved carries a
  `RATE_CHANGED` flag — judged from the two packs' own
  records, so a figure no EUR flows through (the consolidated
  intercompany revenue, whose converted metric is nonzero only
  in USD; the pipeline total, which converts nothing) stays
  unflagged, and entity figures are never flagged: they stand
  in their own currency. The flux schedule states both rate
  tables' versions on its face beside the definition versions
  and carries the flag per entry. Like the definition flag,
  it is a flag, not a decomposition: the movement is never
  split into a "rate part" and a "trading part" — that split
  would mean converting one period at the other period's
  rates and presenting the counterfactual as fact.
- **Flux: every movement explains itself, and the explanation
  foots** — alongside the comparatives, the pack carries a
  flux schedule: each figure's period-over-period movement
  decomposed **by entity** and, where the definition's shape
  allows, **by account**. Each side is computed from that
  period's own source batches — the current run's on one side,
  the batches stamped on the prior period's signed pack on the
  other — under that period's own definition version, so the
  decomposed movement is exactly the movement the comparative
  presents. The identities are hard: contributions sum to the
  movement to the cent, and any conversion residue lands on a
  named **rounding** line, never absorbed. A movement reaching
  either materiality bar (an absolute bar and a percentage bar,
  stated on the schedule's face) is **material** and carries
  its drivers ordered largest first; quieter lines are listed
  whole. Where a definition changed, the entry keeps the flag
  and says the movement includes the definition change —
  the widened insurance account appears as its own line —
  rather than splitting the movement into a "definition part"
  and a "trading part" that would rest on a counterfactual.
  An elimination (a matched pairing, not a sum of accounts)
  and the pipeline figure carry no account split, and say why.
  The schedule is **verified like a figure**: the verifier
  recomputes every decomposition independently from the same
  sources, and a mismatch is a named `FLUX_MISMATCH` variance
  that blocks the pack. The narrative quotes flux only after
  that check, and only for entries that tie to verified
  figures.
- **Intercompany agreement, pair by pair** — an elimination
  nets whatever the two sides of an internal trade booked, so
  the verifier checks that the two sides actually mirror. For
  every intercompany pair in the period's sources — keyed by
  counterparty against the pack's elimination definitions —
  the seller's stated revenue leg is compared with the buyer's
  stated cost leg, judged in the **seller's currency** (the
  invoice currency) with the buyer's amount translated once at
  the close's own rate table, so agreement means agreement to
  the cent on the close's stated basis, never a comparison of
  two converted totals. Each pair lands **AGREED**,
  **IC_DISAGREEMENT** (both legs booked, different amounts), or
  **IC_ONE_SIDED** (a leg one entity booked and the other never
  did — a different failure, named separately); an open pair
  blocks the pack like any other variance, carrying both
  figures, both entities, and the difference. Neither entity's
  own figures are restated — the variance says plainly that the
  fix is a booking conversation between the entities — but the
  consolidated figures whose arithmetic touches a disputed
  pair's legs (the elimination, the consolidated intercompany
  revenue, and what derives from them) carry an
  `ic_disagreement` flag tying them to the open pair. The pairs
  ride the pack, the console's pairs table, and the evidence
  bundle.
- **The audit evidence pack** — a signed pack can generate
  one bundle an external auditor can re-perform from: every
  figure with its definition entry reproduced and the
  verifier's verdict as recorded, the manifest of the exact
  source extracts consumed (versions and the content hashes
  from ingestion), the comparatives and the signed pack they
  cite, the **rate provenance** (both closes' stamped rate
  tables and the rates that moved between them), the flux schedule, any restatement and its
  acknowledgement, any dispositions on the pack's face and the
  opening items it carried in, any definition change the pack
  was first governed under — the activation that made the new
  version govern and the dry-run behind it — and the sign-off record with the checklist
  state the signature froze, the sign-off chain inside it
  (who prepared, who reviewed, what each act stamped —
  checked whole at generation, or stated as a legacy
  single-act signature for a pack that predates the chain). The bundle is a **projection of stored records** —
  it recomputes nothing — it is refused for anything but a
  `SIGNED_OFF` pack (state named), it is checked for
  completeness before anything is written (any gap refuses,
  naming the gap), and its canonical bytes regenerate
  byte-identically, with the SHA-256 digest carried on the
  bundle record.
- **Figure drill-down** — every figure on any pack opens into
  the exact lines it stands on. The drill is a
  **re-performance, not a report**: it walks the batches the
  pack stamps (at their stamped versions), under the
  definitions the pack cites and the rate table the pack
  stamps, with its own aggregation — never the engine's
  numbers, never the marts, never the verifier's totals. A
  base figure drills to its journal lines (batch, journal,
  account, both stated amounts, the signed contribution); an
  elimination drills to **both legs**; a converted figure
  drills per entity — lines in entity currency, the subtotal,
  the stamped rate, the converted subtotal — because the
  close converts a subtotal once and the drill will not dress
  lines with conversions it never computed; a derived figure
  drills as its **composition tree**, the operands' drills
  nested with the operator named, and the `vs_plan` baseline
  shown as authored data, never as a source line. The drill
  is served only when its composition foots to the figure on
  the pack, Decimal-exact: a source record moved under the
  pack's stamps raises **`DRILL_MISMATCH`** naming the figure
  and both totals, and a measure the close gives no line
  semantics (`sum_amount` over GL lines) is refused by name
  rather than approximated. Any pack state drills — blocked
  and stale packs drill on their own stamps, the state named
  on the drill, because auditors drill blocked packs too. The
  evidence bundle cites each figure's drill by **digest**
  (composed total + line count + a hash of the full drill)
  rather than embedding every line: the lines are the
  manifested extracts' own content, and the full drill is one
  call away against the same pack, reproducible byte for
  byte — a source moved after signing is recorded in the
  bundle as the mismatch it is, never cited clean. Surfaces:
  the API (`GET /packs/{id}/figures/{metric}/drill`), the CLI
  (`drill`), and a Drill button on every console figure row.

- **Definition changes are governed, not dropped in** — the
  definition pack is the close's constitution, and changing
  it is an act with its impact printed first. A candidate
  version's effect is computed as a **dry-run** over a period
  with a signed pack: that period is recomputed from its
  stamped sources under its own cited version and under the
  candidate — both at the rate table the signed pack stamps —
  and the change list is figures moved (old → new, with
  deltas), figures added, figures dropped, and variance
  families whose membership would change, each moved figure
  judged against the close's standing materiality ruler. The
  values compared are the verifier's recomputations, never
  the signed pack's recorded figures; a signed figure that no
  longer reproduces from its own sources surfaces as a named
  baseline discrepancy instead of poisoning the measurement.
  The report carries no timestamp, so its digest is stable —
  and a candidate becomes the pack for future periods only
  through a named **activation** (actor + reason, an
  append-only record) that cites a recorded dry-run's id and
  digest. Activating without a dry-run, into an
  already-signed period, or over the version that already
  governs is refused, each refusal naming its ground. Which
  version governs a period is a **computed rule** — the
  latest activation whose from-period has arrived, else the
  deployment's wired default — printed on the run and stamped
  on the pack; a signed period's cited version never changes.
  The first pack governed by a new version **states the
  change on its face** (version from → to, who activated it
  and why, the dry-run's headline counts), beyond the
  per-figure `DEFINITION_CHANGED` flags, and its evidence
  bundle carries the activation and the dry-run report. The
  demo's fourth act stages it: candidate v1.2.0 takes
  insurance premiums out of operating expenses onto their own
  line — measured over signed October first (four figures
  move, four are born, none material), then activated for
  November by the controller, with November's run created on
  a service still wired to the old version to show the rule,
  not the wiring, doing the selecting.

- **The close does not start on missing sources** — before
  any of that, a period's close is checked against what it
  *expects* to receive, not just what the checklist requires
  to be present. The expectation is itself governed data: an
  **expectation manifest** a named controller records for
  the period — one entry per source slot, with the delivery
  version expected where one is stated — amended only by a
  new version naming the one it supersedes, so the version
  that governed a check or a build is citable. The
  **readiness check** is a pure read over a run's received
  sources (it registers nothing, mutates nothing): every
  entry's state — ok, missing, version **short**, version
  **ahead** (batch versions are per-batch content stamps, so
  any version other than the expected one is a different
  delivery; the remedy for a legitimate newer delivery is to
  amend the manifest) — plus the rate table judged as
  *coverage*: a table carried on the FX batch, with a rate
  for every currency the period's entities book in, checked
  before the build instead of failing unnamed inside it.
  The prior period's state (signed, pack cited / no prior
  close / packs but none signed) rides the report as a named
  fact, never a failure: the build requires nothing of the
  prior period, because comparatives are defined over the
  signed record and degrade to absent by design. A build
  whose readiness fails is **refused by name** at the one
  service door every surface builds through, listing the
  uncovered items in the check's own words — unless a named
  controller has recorded a **readiness waiver** covering
  exactly those items (actor + reason + the items named; a
  blanket waiver is refused, as is an item the check is not
  currently failing on, and any waiver for a period already
  signed). A pack built under waiver **states it on its
  face** — the items it started without, waived by whom and
  why — and its evidence bundle carries the manifest and
  the waiver records it cites; a pack built complete states
  that too, with the manifest version cited. The bundled
  periods' manifests are **derived**, not invented: each is
  the terminal delivery per slot of the batches the close
  actually used (September's expects the corrected extracts
  and the revised rate table at v2; October and November
  closed on first deliveries throughout), recorded as data
  through the same service a deployment's controller would
  use. Surfaces: the API (`GET /runs/{id}/readiness`,
  `POST /manifests`, `POST /waivers`), the CLI (`readiness`,
  `record-manifest`, `record-waiver`), and the console (the
  run's readiness, and the statement on every pack).

## The aidnn seam

aidnn is a deployed product application, not a public API
platform — its integrations run through its own connectors and
plan-review flow inside a customer workspace. This blueprint
therefore treats the seam as deployment work, the way an FDE
team meets it:

- `FINANCE_ENGINE=aidnn` selects the adapter in
  `engine_aidnn.py`; `AIDNN_WORKSPACE_URL` names the workspace
  endpoint agreed during onboarding, `AIDNN_API_TOKEN` its
  credential where the deployment issues one.
- The adapter sends one contract payload — the definition
  pack's defined queries plus the governed mart snapshot they
  run over — and maps the returned figure set onto the port.
  The docstring in that module is the contract's statement of
  record, including what it is *not*: not aidnn's published
  API, because there isn't one.
- Without the URL, wiring raises `EngineNotConfigured` at
  startup. There is no silent fallback, by design.

## Configuration

Copy `.env.example` to `.env` and set what you use:

| Variable | Meaning |
|---|---|
| `FINANCE_ENGINE` | `offline` (reference engine; standard run) or `aidnn` (deployed workspace) |
| `AIDNN_WORKSPACE_URL` | The aidnn workspace endpoint agreed during deployment — required for `aidnn`, no default exists |
| `AIDNN_API_TOKEN` | Credential for that endpoint, where the deployment issues one |
| `DEFINITION_PACK` | Path to a definition pack JSON; unset = the bundled Harborlight pack |
| `DATABASE_URL` | PostgreSQL for batches, runs, packs + checkpoints; unset = in-memory doubles, and `/readiness` says so |
| `S3_ENDPOINT_URL`, `S3_BUCKET` | Object storage for the raw extract archive (S3-compatible) |

## Honest status

- **Live aidnn verification is pending a deployment.** There is
  no public API or sandbox to verify against; the adapter is
  written to the documented integration contract and its wire
  mapping is unit-tested against stubbed transports. The
  offline engine is what the tests, evals, and demo actually
  run — and the verifier's guarantee does not depend on which
  engine proposed the figures.
- The synthetic sources cover **two periods** (September and
  October 2026) plus one post-sign-off restatement — and a
  third staged month, November, which is October's trading one
  month on and exists to exercise the disposition carry: one month
  of journals per entity per period, AR summaries, a rate
  table, a CRM snapshot. A customer deployment's connectors
  pull the same shapes from the real systems on the close
  calendar, period after period; the comparative machinery
  keys off the period on the run, so a third month needs no
  new code.
- Comparatives look back exactly one period — the board-pack
  convention this blueprint implements. Longer trend columns
  would cite the same signed records the same way, but are
  not built here.
- The definition pack's formula language is deliberately
  small (base aggregates + five derived ops). A deployment
  that needs a new op adds it in code, reviewed — definitions
  are data, never strings evaluated at runtime.
- Definition governance is forward-only, deliberately. There
  is no un-activation and no edit to a recorded act: changing
  course is a new activation for the same from-period that
  supersedes the earlier one, and the superseded act stays on
  the record. A dry-run measures a candidate only against a
  period that closed and signed — there is no measuring
  against a draft close, because a draft's sources are still
  moving.
- Expectation manifests are authored data, like definition
  packs. In a deployment, the period's controller writes
  the manifest from the close calendar — which extracts, at
  which delivery versions — and amends it the same governed
  way when the calendar changes. The manifests bundled here
  are derived from the synthetic worlds (the terminal
  delivery per slot of the batches each close actually
  used); they demonstrate the machinery over history, they
  are not a claim about any real close's expectations.
- The signed pack is a record of approval, not a posting.
  Filing, posting, and payment stay in the customer's systems
  of record, by design.
- The evidence bundle names the source extracts by batch id,
  version, and recorded content hash — it deliberately does
  not embed the raw extracts. The bytes themselves sit in the
  object-store archive written at ingestion, so an auditor
  pulls the exact extract a manifest line names and checks
  its hash against the bundle.

## Evaluations

`make evals` runs the golden close over the synthetic world and
gates on it:

- **Traceability — 100%, hard gate.** Every figure in the
  signed pack carries its definition-pack version and source
  stamps, and was reproduced from source by the verifier.
- **Gold figures** — the corrected close's 25 figures equal the
  gold close-question answers exactly (Decimal-exact), from
  per-entity revenue to consolidated operating income.
- **Planted traps, named** — the first attempt's pack is
  BLOCKED with exactly `DUPLICATE_JOURNAL`, `IC_ONE_SIDED`,
  `UNMATCHED_IC_LEG`, and `SUBLEDGER_TIE_OUT`.
- **Staleness** — the first pack goes STALE when the corrected
  extracts land, and refuses sign-off at every stage.
- **Consolidation ties** — consolidated figures tie to the
  entity figures through the pack's own identities, checked in
  the eval's independent arithmetic.
- **October gold figures** — the second month's 25 figures,
  under definition pack v1.1.0, exact.
- **Comparatives tie to the signed pack** — all 25 October
  comparatives equal the signed September figures they cite.
- **Definition changes flagged** — exactly the comparatives
  crossing the v1.0.0 → v1.1.0 change carry the flag.
- **Restatement named** — the planted September restatement
  surfaces with its five affected figures at gold values
  (signed vs recomputed); sign-off refuses while it is
  unacknowledged and succeeds after acknowledgement; the
  signed September pack is byte-identical at the end.
- **Evidence bundles** — both signed packs generate theirs:
  complete (25 figures with definitions and verdicts, the
  full source manifest, the sign-off record), byte-identical
  on regeneration, the record's digest matching the stored
  bytes — and generation for the blocked first-attempt pack
  is refused with its state named. October's bundle carries
  the comparatives, the restatement, and the acknowledgement.
- **Flux identities** — every one of the 25 flux entries'
  decompositions sums to its movement exactly, by entity and
  by account; **materiality** flags the planted big mover
  (the pipeline drop) and the large revenue movement while
  the quiet figures stay unflagged; **definition-changed
  figures** carry the flux flag too; and October's evidence
  bundle carries the schedule's 25 entries while September's
  — a close that predates the schedule — states `flux: null`
  in the same bundle format.
- **Intercompany agreement** — September's first attempt
  names its planted pair one-sided; both signed packs carry
  exactly the one HLD → HLE pair, AGREED with the stated
  figures exact, and both bundles carry the intercompany
  section. A staged variant October — HLE booking the
  purchase €500 light — blocks on exactly one
  `IC_DISAGREEMENT` naming both figures and the $560.00
  difference, flags exactly the consolidated figures standing
  on the pair, and leaves every entity figure at its gold.
- **Rate provenance** — both signed packs stamp the rate
  table itself (September v2 at EUR 1.10, October v3 at
  1.12) on the pack and on every figure; October's
  comparatives flag `RATE_CHANGED` on exactly the eight
  consolidated figures EUR money flows through, the flux
  schedule states both table versions and agrees, and
  October's bundle carries both tables with the change named.
  A staged fourth act replays October's figures against an
  FX batch edited in place (EUR 1.15, same batch and table
  version): the verifier names `RATE_TABLE_MISMATCH` and
  still reproduces every figure at the stamp; figures
  re-stamped with a table they were not computed at are
  named per figure as converted off-stamp.
- **Variance disposition** — a fifth act accepts the staged
  October disagreement in writing: disposition without a
  named controller or a reason is refused, each refusal
  naming its ground; `DEFINITION_CHANGED` cannot be
  dispositioned (it is a flag, not a variance); with one of
  the break's two variances still unaccepted the rebuild
  stays BLOCKED and sign-off refuses; with both accepted the
  pack presents and signs, its variances identical to the
  blocked pack's word for word, and both acceptances listed
  on the signed face and in its evidence bundle. November
  then opens both carried items — origin period, controller,
  and reason quoted — retests them STILL_PRESENT, blocks
  again, and a second acceptance signs with carry 2 stated
  on the face.
- **Definition governance** — a sixth act closes September
  and October canonically, then governs the v1.2.0 candidate:
  activation without a dry-run is refused by name; the
  dry-run over signed October reproduces the hand-computed
  change list exactly (four moved figures with their old →
  new values, four added, none dropped, none material, no
  variance-family change, no baseline discrepancy — gold
  derived from the journals by hand); recomputing the
  dry-run returns the same record and digest while both
  signed packs stay byte-identical; the activation's
  refusals (unnamed actor, missing reason, signed
  from-period, already-governing version) each name their
  ground; November's run, created on a service still wired
  to v1.1.0, selects v1.2.0 by rule and its figures are the
  candidate's; the first governed pack states the change on
  its face; and its evidence bundle carries the activation
  and the dry-run, while September's bundle — a close with
  no change to state — projects `definition_change: null`.
- **Figure drill-down** — a seventh act opens the figures:
  all 25 figures on both signed packs re-perform to their
  lines and compose exactly; September's HLE external
  revenue is precisely the two corrected-extract lines; the
  elimination shows both legs with the EUR leg converted at
  the stamped 1.10; the converted figure converts once per
  entity at the stamp; derived figures compose from their
  operands' drills and stand on no lines of their own, the
  plan shown as authored data; both bundles cite every drill
  by a digest a fresh drill reproduces. The blocked first
  pack drills with its duplicated journal counted once, and
  the stale pack drills on its own v1 stamps after the world
  moved. On a fresh store, a source line edited under a
  signed pack's stamps raises `DRILL_MISMATCH` naming the
  figure, while an FX batch edited in place (EUR 1.15 under
  the same version) reprices no drill — conversions stand
  on the stamp.
- **Pre-close readiness** — an eighth act checks the close
  before it starts: September on its opening deliveries
  fails on exactly the three version items its derived
  manifest implies, the build is refused with the items
  named, and blanket and non-failing-item waivers are
  refused by name, as is a waiver for the by-then-signed
  period; waived exactly, the opening build proceeds and
  states the waiver, and the corrected rebuild states
  COMPLETE with the manifest cited. October staged short
  two extracts fails on exactly those two slots; its
  manifest amended to expect HLE's AR at v2, a waiver on
  record for a different item unblocks nothing, and the
  waiver covering exactly the version item lets the build
  proceed — the pack's face states it, and the signed
  pack's evidence bundle carries the manifest (v2) and the
  waiver record. The check is a pure read (the store is
  byte-identical across it), and the September pack signed
  in the act is byte-identical at the end of everything.

A live-engine run (`EVAL_LIVE=1` with a workspace configured)
is reported, never gated.

## Layout

```
src/aidnn_close_agent/
  ports.py          FinanceEnginePort + ConnectorPort + ObjectStorePort
  engine_aidnn.py   the aidnn adapter — the integration contract
  engine_offline.py the labelled reference engine
  definitions.py    versioned definition packs (catalog as data)
  marts.py          governed marts: normalization, DQ rules, stamps
  verifier.py       the independent recomputation — separate code path
  comparatives.py   prior-period comparatives, restatement detection
  dispositions.py   variance disposition: acceptances, coverage, the carry
  governance.py     definition change: dry-runs, activations, selection
  evidence.py       the audit evidence pack: gated, checked projection
  drill.py          figure drill-down: every figure re-performed to its lines
  readiness.py      pre-close readiness: manifests, the check, the waiver math
  signoff_chain.py  the sign-off chain: the acts' vocabulary, stamps, bundle check
  fx.py             money, FX conversion, the one rounding rule
  guardrails.py     injection screen + the checklist function
  graph.py          the LangGraph pipeline and its controller gate
  service.py        runs, ingestion, staleness, sign-off discipline
  store.py / db.py  batches, runs, packs in Postgres (or the double)
  datasets.py       the synthetic Harborlight world — gold by construction
  definition_packs/ the bundled catalog (harborlight-close v1.0.0, v1.1.0, and the v1.2.0 candidate)
migrations/         numbered SQL, applied at startup
evals/              the golden close pack and its runner
docs/               architecture.md — the deployment, in depth
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
