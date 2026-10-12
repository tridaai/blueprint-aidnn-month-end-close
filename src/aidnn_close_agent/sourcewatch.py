"""The post-sign-off source watch: the signed period whose
inputs moved.

Every other layer of the close looks forward. Readiness
checks a period before it builds; the comparative layer
detects a restatement when the *next* period builds; the
gate holds that next pack's signature until a controller
acknowledges what the recomputation found. All of it is
sound — and all of it is silent about a signed period in
the meantime. A corrected extract can land the week after
sign-off (``receive_restatement`` takes it in, archives it,
and attaches it to nothing, by design), and until somebody
builds the next close, nothing anywhere says that the
signed period's inputs no longer stand where the board
left them. If the next close is never built, nothing ever
says it at all.

The watch is the look back. For every period with a signed
pack of record, it compares each source version stamped on
that pack against the tip of its supersession chain as the
chain stands now, and names every source that moved:

- **The matching rule is the chain itself.** A stamped
  batch is matched to its chain by identity — the stamp
  names the exact batch the pack was built from, and the
  chain is walked forward through the ``supersedes`` links
  (the same walk the comparative layer performs), to the
  terminal batch. The item's source identity is the slot
  (:func:`aidnn_close_agent.marts.slot_key` —
  ``ENTITY:kind`` / ``GROUP:kind``), read off the stamped
  batch. A stamp whose batch is missing from the store
  cannot be matched and is skipped, the degrade-to-absent
  idiom: the watch names what it can prove, nothing else.
- **Movement, not materiality.** The watch never
  recomputes a figure. Whether a corrected extract changes
  a number is the next build's recomputation (the
  comparative layer's ``RESTATED_PRIOR_PERIOD``), or a
  controller's stated judgement, recorded as a NO_ACTION
  acknowledgement with the reason in the controller's own
  words. The watch's one claim is the movement itself:
  signed against this delivery, the chain now ends at that
  one.
- **"When" is the delivery's own stamp.** Batches carry no
  receipt clock — a delivery outside a run is archived and
  stored, never timestamped — so an item names the landing
  delivery (its batch id, its version, its phase) and the
  full chain that landed after the signed batch, in order.
  It does not invent a time the record does not hold.

An item's state is **derived, never stored**, in this
precedence:

1. ``ANSWERED`` — a later signed pack's restatement report
   names this period's pack and lists this tip among its
   restated batches, and that pack stands signed — which
   the gate only allows behind a named controller's
   acknowledgement of the restatement. The movement has
   been through the board's own road: recomputed, named
   on a signed pack, acknowledged before its signature.
   The derivation reads the answering pack's stamps and
   report; no flag is stored anywhere.
2. ``ACKNOWLEDGED`` — a controller's watch acknowledgement
   covers this exact tip: RESTATEMENT_PLANNED (the intent
   and the reason, on the record; the acknowledgement
   itself restates nothing), or NO_ACTION (the controller's
   stated judgement, reason required, and the item stays
   visible in the considered section — a legible record,
   not an absence of noise).
3. ``OPEN`` — neither. The movement stands unexamined.

The watch never fires for a period with no signed pack —
blocked, stale, awaiting, returned, or withdrawn packs
raise nothing here. A close still in flight discovers
changed inputs through its own machinery: the sign gate
refuses a pack built from superseded sources, and the
build itself reads the chains as they stand. The watch
exists for the one state that machinery cannot reach —
signed, closed, and believed finished.

And it never acts: it rebuilds nothing, restates nothing,
unsigns nothing. Reading it writes nothing (the tests pin
the store byte-identical across it), and acknowledging an
item writes only the acknowledgement record — the signed
pack, its figures, its chain, and its evidence bundle are
byte-identical across both. The boundary is stated on the
report's own face.
"""

from __future__ import annotations

from . import comparatives as comparatives_module
from .marts import slot_key
from .schemas import (
    BoardPack,
    SourceBatch,
    SourceWatchReport,
    WatchItem,
)

BOUNDARY = (
    "The watch rebuilds nothing, restates nothing, and "
    "unsigns nothing: a movement it names is answered by a "
    "controller's acknowledgement on this record, or by the "
    "restatement road the next close walks — never by the "
    "watch itself. It judges movement, not materiality: "
    "whether a movement changes a figure is the next "
    "build's recomputation, or a controller's stated "
    "judgement recorded as NO_ACTION."
)


def _chain_steps(store, by_supersedes: dict[str, SourceBatch],
                 stamped: SourceBatch) -> list[SourceBatch]:
    """Every delivery that landed after ``stamped`` on its
    supersession chain, in chain order — the terminal (tip)
    batch last. Empty when the chain still ends where the
    pack signed."""
    steps: list[SourceBatch] = []
    terminal = stamped
    while terminal.batch_id in by_supersedes:
        nxt = by_supersedes[terminal.batch_id]
        if nxt.batch_id == terminal.batch_id:
            break
        steps.append(nxt)
        terminal = nxt
    return steps


def _answering_pack(store, pack: BoardPack,
                    tip_batch_id: str) -> BoardPack | None:
    """The later signed pack whose acknowledged restatement
    report names this pack and this tip — the derivation of
    ANSWERED, read off the answering pack's own record."""
    for other in store.list_packs():
        if other.status != "SIGNED_OFF":
            continue
        report = other.restatement
        if report is None or report.prior_pack_id != pack.pack_id:
            continue
        if other.restatement_acknowledgement is None:
            continue
        if tip_batch_id in report.restated_batch_ids:
            return other
    return None


def compute_watch(store, period: str | None = None,
                  ) -> SourceWatchReport:
    """The watch over every signed period (or one period):
    each stamped source whose supersession chain has
    advanced past the version the pack signed against,
    stated as an item with its derived state. A pure read:
    nothing is registered, nothing is mutated."""
    if period is not None:
        periods = [period]
    else:
        periods = sorted({
            p.period for p in store.list_packs()
            if p.status == "SIGNED_OFF"
        })
    by_supersedes: dict[str, SourceBatch] = {}
    for batch in store.list_batches():
        if batch.supersedes:
            by_supersedes[batch.supersedes] = batch
    acks = store.list_watch_acknowledgements()
    items: list[WatchItem] = []
    for one_period in periods:
        pack = comparatives_module.find_signed_pack(store, one_period)
        if pack is None:
            continue
        for batch_id, signed_version in sorted(
                pack.source_versions.batches.items()):
            stamped = store.get_batch(batch_id)
            if stamped is None:
                continue
            steps = _chain_steps(store, by_supersedes, stamped)
            if not steps:
                continue
            tip = steps[-1]
            slot = slot_key(stamped)
            item = WatchItem(
                period=one_period,
                pack_id=pack.pack_id,
                slot=slot,
                signed_batch_id=batch_id,
                signed_version=signed_version,
                tip_batch_id=tip.batch_id,
                tip_version=tip.version,
                chain=[b.batch_id for b in steps],
                landed_phase=tip.phase,
            )
            ack = next(
                (a for a in acks
                 if a.period == one_period and a.slot == slot
                 and a.pack_id == pack.pack_id
                 and a.tip_batch_id == tip.batch_id),
                None,
            )
            if ack is not None:
                item.state = "ACKNOWLEDGED"
                item.disposition = ack.disposition
                item.acknowledged_by = ack.actor
                item.acknowledgement_reason = ack.reason
            answer = _answering_pack(store, pack, tip.batch_id)
            if answer is not None:
                item.state = "ANSWERED"
                item.answered_by_pack_id = answer.pack_id
            items.append(item)
    items.sort(key=lambda i: (i.period, i.slot))
    return SourceWatchReport(items=items, boundary=BOUNDARY)


def open_items(report: SourceWatchReport) -> list[WatchItem]:
    """The items still waiting on a controller."""
    return [i for i in report.items if i.state == "OPEN"]


def open_count(report: SourceWatchReport, period: str) -> int:
    """Open items standing behind one period's signed pack —
    the count the pack's face carries (display only)."""
    return sum(1 for i in report.items
               if i.period == period and i.state == "OPEN")


def render_text(report: SourceWatchReport) -> str:
    lines = ["Source watch — sources that moved behind signed packs"]
    lines.append(f"Boundary: {report.boundary}")
    if not report.items:
        lines.append("No signed period's sources have moved.")
        return "\n".join(lines)
    sections = [
        ("OPEN — waiting on a controller",
         [i for i in report.items if i.state == "OPEN"]),
        ("ACKNOWLEDGED — restatement planned",
         [i for i in report.items
          if i.state == "ACKNOWLEDGED"
          and i.disposition == "RESTATEMENT_PLANNED"]),
        ("CONSIDERED — no action, on the record",
         [i for i in report.items
          if i.state == "ACKNOWLEDGED"
          and i.disposition == "NO_ACTION"]),
        ("ANSWERED — through the restatement road",
         [i for i in report.items if i.state == "ANSWERED"]),
    ]
    for title, section in sections:
        if not section:
            continue
        lines.append("")
        lines.append(title)
        for item in section:
            lines.append(
                f"  {item.period} · {item.slot:<10} signed against "
                f"{item.signed_batch_id} (v{item.signed_version}); "
                f"the chain now ends at {item.tip_batch_id} "
                f"(v{item.tip_version}, landed as a "
                f"{item.landed_phase} delivery) — behind signed "
                f"pack {item.pack_id}"
            )
            if len(item.chain) > 1:
                lines.append(
                    "      landed since: " + " → ".join(item.chain))
            if item.acknowledged_by:
                lines.append(
                    f"      acknowledged by {item.acknowledged_by} "
                    f"({item.disposition}): "
                    f"{item.acknowledgement_reason}")
            if item.answered_by_pack_id:
                lines.append(
                    f"      answered by signed pack "
                    f"{item.answered_by_pack_id}, whose acknowledged "
                    "restatement report names this movement")
    return "\n".join(lines)
