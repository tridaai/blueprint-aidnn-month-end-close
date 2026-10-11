"""Variance disposition: the second honest exit from a block.

A blocking variance has always had exactly one exit in this
system: fix the books and rebuild. Real closes have a second
one, and this module is it — a named controller reviews the
break, accepts it in writing (immaterial, timing, known and
explained), and the item is *carried* into the next period as
an opening item that must clear there. What this module is
careful never to build is a dismiss button:

- **The verifier's verdict does not move.** A disposition is
  governance around the verifier, recorded in the service and
  consulted by the pipeline at build time. The variance it
  accepts stays on every pack that computes it, word for word;
  a pack that signs under disposition lists the acceptances
  on its face, next to the variances themselves.
- **Only blocking variances are dispositionable.** The
  taxonomy is the one the pipeline already keeps: every
  variance that holds a pack at BLOCKED. The one variance
  that is not blocking — ``RESTATED_PRIOR_PERIOD``, which
  holds a *signature*, not a pack — has its own governance
  (the acknowledgement) and is refused here by name. The
  informational flags (``DEFINITION_CHANGED``,
  ``RATE_CHANGED``) are not variances at all and there is
  nothing to accept: a flag is a fact about a comparison,
  not a break in the books.
- **An acceptance names the exact break.** A disposition
  records the variance's code, entity, metric, subject, and
  its detail text — figures and all. It covers a variance on
  a later pack only when all of those are identical: the
  break a controller accepted at 560.00 is not an acceptance
  of the same break at 900.00.
- **Carrying is a re-test, not a forgetting.** Every
  acceptance on a signed pack's face opens the next period
  as a named item. The new pack's own recomputation decides
  what became of it — cleared, still present (it blocks
  again), or mutated (same break, different figures; the
  old acceptance does not cover it) — and the item quotes
  the acceptance that carried it, with its carry count, so
  the age of a break is stated on the face of every pack it
  touches.
"""

from __future__ import annotations

import re

from . import comparatives as comparatives_module
from .schemas import BoardPack, Disposition, OpeningItem, Variance

#: The variance codes that never block a pack. Everything else
#: on a pack's variance list is what holds it at BLOCKED — the
#: verifier's figure variances, the comparative and flux
#: checks, the tie-outs, the pairing checks. The restatement
#: variance holds a signature instead and is governed by the
#: acknowledgement; dispositioning it is refused by name in
#: the service.
NON_BLOCKING_CODES = {"RESTATED_PRIOR_PERIOD"}

_PAIR_RE = re.compile(r"pair (\S+) → (\S+)")
_ELIM_RE = re.compile(r"elimination '([^']+)'")
_JOURNAL_RE = re.compile(r"journal (\S+) appears")


def blocking_variances(pack: BoardPack) -> list[Variance]:
    """The variances holding this pack at BLOCKED — the
    dispositionable set, exactly."""
    return [v for v in pack.variances if v.code not in NON_BLOCKING_CODES]


def subject_for(pack: BoardPack, variance: Variance) -> str:
    """The discriminator that names *which* break a variance
    is, where code + entity + metric do not.

    Most variances are already named by their fields (a figure
    mismatch names its figure; a tie-out its entity). Three
    families are not, and each takes its subject from the
    record the verifier produced — the pair, the elimination,
    the journal — in the verifier's own wording:

    - ``IC_DISAGREEMENT`` / ``IC_ONE_SIDED``: the pair on the
      pack whose seller, buyer, and elimination the detail
      names → ``elimination:seller->buyer``;
    - ``UNMATCHED_IC_LEG``: the elimination the detail names;
    - ``DUPLICATE_JOURNAL``: the journal id the detail names.

    Anything else has no subject (``""``) — its fields are
    its name."""
    if variance.code in ("IC_DISAGREEMENT", "IC_ONE_SIDED"):
        verdict = "IC_DISAGREEMENT" if variance.code == "IC_DISAGREEMENT" \
            else "ONE_SIDED"
        pair_match = _PAIR_RE.search(variance.detail)
        elim_match = _ELIM_RE.search(variance.detail)
        if pair_match and elim_match:
            seller, buyer = pair_match.groups()
            elimination = elim_match.group(1)
            for pair in pack.ic_pairs:
                if pair.verdict == verdict \
                        and pair.seller_id == seller \
                        and pair.buyer_id == buyer \
                        and pair.elimination_id == elimination:
                    return f"{elimination}:{seller}->{buyer}"
        return ""
    if variance.code == "UNMATCHED_IC_LEG":
        match = _ELIM_RE.search(variance.detail)
        return match.group(1) if match else ""
    if variance.code == "DUPLICATE_JOURNAL":
        match = _JOURNAL_RE.search(variance.detail)
        return match.group(1) if match else ""
    return ""


def core_key(code: str, entity_id: str | None, metric_id: str | None,
             subject: str) -> tuple:
    """A break's identity, without its figures: what makes two
    variances *the same break* across periods."""
    return (code, entity_id, metric_id, subject)


def variance_core(pack: BoardPack, variance: Variance) -> tuple:
    return core_key(variance.code, variance.entity_id,
                    variance.metric_id, subject_for(pack, variance))


def disposition_covers(disposition: Disposition, pack: BoardPack,
                       variance: Variance) -> bool:
    """Does this acceptance cover this variance, exactly?

    Identity *and* wording: the detail text is the break as
    computed, figures included, so a break that returns with
    different figures is not the break that was accepted and
    is not covered by it."""
    return (
        disposition.code == variance.code
        and disposition.entity_id == variance.entity_id
        and disposition.metric_id == variance.metric_id
        and disposition.subject == subject_for(pack, variance)
        and disposition.detail == variance.detail
    )


def governing_dispositions(store, run_id: str) -> list[Disposition]:
    """The current acceptances of a run: every disposition
    recorded on any of the run's packs, reduced to the head of
    each supersession chain.

    A rebuild consults this set — an acceptance written on a
    blocked pack governs the next build of the same close,
    not just the pack it was written on. Copies of a record
    (a rebuild carries the acceptances it used onto its own
    face, under the same id) are the same record, counted
    once."""
    by_id: dict[str, Disposition] = {}
    for pack in store.list_packs(run_id=run_id):
        for disposition in pack.dispositions:
            by_id.setdefault(disposition.disposition_id, disposition)
    superseded = {d.supersedes for d in by_id.values() if d.supersedes}
    return [d for d in by_id.values()
            if d.disposition_id not in superseded]


def prepare_carried(store, period: str) -> list[Disposition]:
    """The acceptances that open ``period``: the governing
    dispositions on the prior period's SIGNED pack's face.

    Carrying flows through signed packs only. An acceptance
    recorded on a blocked pack whose close was then fixed and
    signed clean was never used and carries nothing; an
    acceptance a signature relied on is owed a re-test by
    the next close, and this is the list it is owed to."""
    prior = comparatives_module.find_signed_pack(
        store, comparatives_module.previous_period(period))
    if prior is None or not prior.dispositions:
        return []
    superseded = {d.supersedes for d in prior.dispositions if d.supersedes}
    return [d for d in prior.dispositions
            if d.disposition_id not in superseded]


def retest_items(carried: list[Disposition],
                 pack: BoardPack) -> list[OpeningItem]:
    """Re-test each carried acceptance against the new pack's
    own variances and state what became of the break.

    The comparison is the pack's recomputation, not a memory:
    an exact match (identity and wording) is the same break,
    still present; an identity match with different wording
    is the same break with different figures — mutated, and
    not covered by the old acceptance; no match is a break
    the new period's sources no longer produce — cleared,
    by events, which is the only way an item ever leaves."""
    items: list[OpeningItem] = []
    for disposition in carried:
        core = core_key(disposition.code, disposition.entity_id,
                        disposition.metric_id, disposition.subject)
        exact = None
        kindred = None
        for variance in pack.variances:
            if variance_core(pack, variance) != core:
                continue
            if variance.detail == disposition.detail:
                exact = variance
                break
            kindred = kindred or variance
        if exact is not None:
            verdict, current = "STILL_PRESENT", exact.detail
        elif kindred is not None:
            verdict, current = "MUTATED", kindred.detail
        else:
            verdict, current = "CLEARED", None
        items.append(OpeningItem(
            code=disposition.code,
            entity_id=disposition.entity_id,
            metric_id=disposition.metric_id,
            subject=disposition.subject,
            detail=disposition.detail,
            origin_period=disposition.origin_period,
            origin_pack_id=disposition.origin_pack_id,
            disposition_id=disposition.disposition_id,
            dispositioned_by=disposition.actor,
            reason=disposition.reason,
            carry_number=disposition.carry_number,
            retest=verdict,
            current_detail=current,
        ))
    return items
