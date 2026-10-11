"""Governed data marts: what the engine is allowed to see.

The marts are the deployment's contract with the engine. Source
extracts arrive messy — divergent charts, a duplicated journal,
a memo with instructions in it — and the mart builder is where
that mess is normalized, once, in code:

- journal lines are flattened, amounts parsed to Decimal and
  rounded by the package's one rule (:mod:`.fx`);
- the definition pack's data-quality rules are applied — under
  ``unique_journal_ids``, a repeated journal id within an
  entity's extract is **voided** (kept in the mart, flagged, and
  excluded from every aggregate), never silently summed twice;
- journal memos pass the injection screen and are carried
  *fenced*; figures never read memos, but no text surface
  downstream ever sees an unfenced payload;
- subledger summaries, opportunities, and the FX rate table are
  carried as first-class mart citizens.

Every mart set carries a ``mart_version`` — a digest of the exact
source batches (id + version + content hash) and the definition
pack version that shaped it. A board pack stamps the mart
version it was built from; when a late extract lands, the mart
version moves, and the stamp is how the service knows the pack
is stale. The verifier does **not** read marts — it recomputes
from source batches directly, so a mart bug cannot hide.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal

from .definitions import DefinitionPack
from .fx import D, RateTable, q
from .guardrails import screen_injection
from .schemas import ArBilling, Opportunity, SourceBatch, SourceVersions


@dataclass
class MartLine:
    entity_id: str
    journal_id: str
    account: str
    debit: Decimal
    credit: Decimal
    ic_counterparty: str | None = None
    memo: str = ""  # fenced at build time
    voided: bool = False  # duplicate journal — excluded from aggregates

    @property
    def net(self) -> Decimal:
        return self.debit - self.credit


@dataclass
class MartSet:
    gl_lines: list[MartLine] = field(default_factory=list)
    ar_billings: dict[str, ArBilling] = field(default_factory=dict)
    opportunities: list[Opportunity] = field(default_factory=list)
    rate_table: RateTable = field(default_factory=lambda: RateTable(version=0))
    mart_version: str = ""
    source_versions: SourceVersions = field(default_factory=SourceVersions)
    voided_journals: list[str] = field(default_factory=list)  # "ENTITY:JID"
    injection_flags: list[str] = field(default_factory=list)

    def gl(self, entity_id: str | None = None) -> list[MartLine]:
        """Live (non-voided) GL lines, optionally for one entity."""
        lines = [ln for ln in self.gl_lines if not ln.voided]
        if entity_id is not None:
            lines = [ln for ln in lines if ln.entity_id == entity_id]
        return lines


def slot_key(batch: SourceBatch) -> str:
    """The checklist slot a batch fills: one current batch per
    (scope, kind). A superseding batch takes the slot over."""
    scope = batch.entity_id if batch.entity_id else "GROUP"
    return f"{scope}:{batch.kind}"


def build_marts(batches: list[SourceBatch], pack: DefinitionPack) -> MartSet:
    """Build the mart set from the batches currently in force.

    ``batches`` is the run's current set — one batch per slot,
    already resolved by the service. Order in the list does not
    matter; the version stamp canonicalizes it.
    """
    marts = MartSet()
    versions = SourceVersions()

    for batch in sorted(batches, key=lambda b: b.batch_id):
        versions.batches[batch.batch_id] = batch.version
        if batch.kind == "gl" and batch.entity_id:
            seen: set[str] = set()
            for journal in batch.journals:
                voided = False
                if pack.unique_journal_ids and journal.journal_id in seen:
                    voided = True
                    marts.voided_journals.append(
                        f"{batch.entity_id}:{journal.journal_id}"
                    )
                seen.add(journal.journal_id)
                flags, fenced_memo = screen_injection(journal.memo)
                marts.injection_flags.extend(
                    f"{batch.entity_id}/{journal.journal_id}: {f}" for f in flags
                )
                for line in journal.lines:
                    line_flags, fenced_line_memo = screen_injection(line.memo)
                    marts.injection_flags.extend(
                        f"{batch.entity_id}/{journal.journal_id}: {f}"
                        for f in line_flags
                    )
                    marts.gl_lines.append(MartLine(
                        entity_id=batch.entity_id,
                        journal_id=journal.journal_id,
                        account=line.account,
                        debit=q(D(line.debit)),
                        credit=q(D(line.credit)),
                        ic_counterparty=line.ic_counterparty,
                        memo=fenced_line_memo or fenced_memo,
                        voided=voided,
                    ))
        elif batch.kind == "ar":
            for billing in batch.ar_billings:
                marts.ar_billings[billing.entity_id] = billing
        elif batch.kind == "fx" and batch.rate_table is not None:
            marts.rate_table = batch.rate_table
            versions.fx_version = batch.rate_table.version
            # The stamp carries the table itself, not only its
            # version: the rates are part of what produced every
            # converted figure, so they are part of its
            # provenance (see SourceVersions.fx_table).
            versions.fx_table = batch.rate_table
        elif batch.kind == "crm":
            marts.opportunities.extend(batch.opportunities)

    marts.source_versions = versions
    stamp = {
        "batches": [
            [b.batch_id, b.version, b.sha256]
            for b in sorted(batches, key=lambda b: b.batch_id)
        ],
        "pack": [pack.pack_id, pack.version],
    }
    marts.mart_version = hashlib.sha256(
        json.dumps(stamp, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return marts
