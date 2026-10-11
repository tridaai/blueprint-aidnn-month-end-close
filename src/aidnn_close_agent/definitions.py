"""Definition packs: the versioned catalog of what figures mean.

In a real deployment this is the FDE team's central deliverable —
the customer's metric catalog (aidnn's world calls this layer
NeoCortex): what "revenue" means *here*, which accounts feed it,
how intercompany legs eliminate, what the plan was. It is data,
not code, and it is versioned like data:

- every metric is defined **once**, in the pack;
- the engine and the independent verifier both read the **same
  pack version**, and every pack record stamps the version that
  produced it — a figure can always be traced to the definition
  that defined it;
- changing a definition means a new pack file with a bumped
  ``version``. Packs are never edited in place once a close has
  run against them; the eval pack's regression suite reruns
  whenever a pack changes.

Formula language, deliberately small: a metric is either a
**base** aggregate over source records (sum a measure over an
account set, per entity or for the group) or a **derived**
arithmetic step over other metrics — ``sum_converted`` (consol-
idate an entity metric through the rate table), ``add`` /
``subtract`` over named metrics, ``vs_plan`` (actual minus the
pack's plan figure), or ``elimination`` (the matched amount of a
named elimination definition). Anything a deployment needs
beyond this is a new op, added in code and reviewed — never a
string evaluated at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Measure = Literal["credit_minus_debit", "debit_minus_credit", "sum_amount"]


class DerivedFormula(BaseModel):
    op: Literal["sum_converted", "add", "subtract", "vs_plan", "elimination"]
    of: str | None = None             # sum_converted / vs_plan: the base metric
    args: list[str] = Field(default_factory=list)  # add / subtract operands
    elimination_id: str | None = None


class MetricDefinition(BaseModel):
    metric_id: str
    label: str
    scope: Literal["entity", "consolidated", "group"]
    # Base metrics:
    source: Literal["gl", "crm"] | None = None
    measure: Measure | None = None
    accounts: list[str] = Field(default_factory=list)
    exclude_ic: bool = False  # skip intercompany-flagged lines (GL base metrics)
    # Derived metrics:
    derived: DerivedFormula | None = None

    @model_validator(mode="after")
    def _shape(self) -> "MetricDefinition":
        if self.derived is None:
            if self.source is None or self.measure is None:
                raise ValueError(
                    f"metric {self.metric_id}: a base metric needs source + measure"
                )
            if self.scope == "consolidated":
                raise ValueError(
                    f"metric {self.metric_id}: consolidated metrics must be derived"
                )
        return self


class EliminationDefinition(BaseModel):
    """Intercompany elimination: revenue booked in one entity
    against cost booked in another. Both legs must exist and agree
    after conversion; the matched amount is what eliminates."""

    elimination_id: str
    label: str
    revenue_account: str
    cost_account: str


class TieOutDefinition(BaseModel):
    """A subledger-to-GL tie-out: the subledger's own total must
    equal the GL figure it feeds, per entity, in entity currency."""

    tie_out_id: str
    label: str
    subledger: Literal["ar"] = "ar"
    gl_accounts: list[str] = Field(default_factory=list)


class DefinitionPack(BaseModel):
    pack_id: str
    version: str
    reporting_currency: str = "USD"
    entities: list[dict] = Field(default_factory=list)  # Entity-shaped dicts
    metrics: list[MetricDefinition] = Field(default_factory=list)
    eliminations: list[EliminationDefinition] = Field(default_factory=list)
    tie_outs: list[TieOutDefinition] = Field(default_factory=list)
    unique_journal_ids: bool = True  # data-quality rule, from the pack
    plan: dict[str, str] = Field(default_factory=dict)  # metric_id → amount

    @model_validator(mode="after")
    def _references(self) -> "DefinitionPack":
        ids = [m.metric_id for m in self.metrics]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate metric_id in definition pack")
        known = set(ids)
        for metric in self.metrics:
            if metric.derived is None:
                continue
            refs = list(metric.derived.args)
            if metric.derived.of:
                refs.append(metric.derived.of)
            for ref in refs:
                if ref not in known:
                    raise ValueError(
                        f"metric {metric.metric_id} derives from unknown metric {ref}"
                    )
            if metric.derived.op == "elimination":
                elim_ids = {e.elimination_id for e in self.eliminations}
                if metric.derived.elimination_id not in elim_ids:
                    raise ValueError(
                        f"metric {metric.metric_id} names unknown elimination "
                        f"{metric.derived.elimination_id}"
                    )
        return self

    def metric(self, metric_id: str) -> MetricDefinition:
        return next(m for m in self.metrics if m.metric_id == metric_id)

    def entity_ids(self) -> list[str]:
        return [e["entity_id"] for e in self.entities]


def load_definition_pack(path: Path) -> DefinitionPack:
    """Load and validate a pack file. Validation is strict: a pack
    that does not parse never reaches a close."""
    return DefinitionPack.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
