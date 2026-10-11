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
  tie-outs, intercompany leg pairing. Any variance — or any
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
- **The gate** — verified packs stop mid-pipeline at a
  LangGraph interrupt, checkpointed in Postgres, until the
  group controller signs or returns them, by name, with a
  reason. Engine proposes, verifier disposes, controller signs:
  three separate code paths.
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
- **Definition changes are flagged, not smoothed over** — when
  a period runs under a newer definition-pack version,
  comparatives whose metric (or anything it derives from, or
  its plan baseline) was redefined carry a `DEFINITION_CHANGED`
  flag with both versions named. October runs under pack
  v1.1.0, which widened operating expenses to include
  insurance; September's comparatives say so.

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
  October 2026) plus one post-sign-off restatement: one month
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
- The signed pack is a record of approval, not a posting.
  Filing, posting, and payment stay in the customer's systems
  of record, by design.

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
  BLOCKED with exactly `DUPLICATE_JOURNAL`,
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
  fx.py             money, FX conversion, the one rounding rule
  guardrails.py     injection screen + the checklist function
  graph.py          the LangGraph pipeline and its controller gate
  service.py        runs, ingestion, staleness, sign-off discipline
  store.py / db.py  batches, runs, packs in Postgres (or the double)
  datasets.py       the synthetic Harborlight world — gold by construction
  definition_packs/ the bundled catalog (harborlight-close v1.0.0 + v1.1.0)
migrations/         numbered SQL, applied at startup
evals/              the golden close pack and its runner
docs/               architecture.md — the deployment, in depth
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
