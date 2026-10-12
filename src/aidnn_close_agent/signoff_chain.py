"""The sign-off chain: a pack is signed by a chain, not a click.

Signing used to be one act: any named controller, one
decision, and the pack was the board's record. The rest of
the close's governance had already outgrown that — a
disposition names its controller and its reason, a waiver
names the items it covers, an activation cites the dry-run
it relied on — but the signature itself, the act everything
else answers to, was a single click by a single hand.

The chain gives the signature the same discipline, in the
order a close actually runs:

1. **Preparation.** A named preparer states the pack is
   ready. The act is stamped with the pack as it stands —
   figure count, variance count, the dispositions on its
   face, the readiness statement's status. The pack's
   figures need no freezing mechanism invented for the
   occasion: no code path in the close mutates a built
   pack's figures, so the state the preparer vouches for is
   the state there is. From preparation on, the only
   records that can still land on the pack are the chain's
   own acts and the restatement acknowledgement (which
   changes no figure) — dispositions are recorded on
   BLOCKED packs only, and a pack under preparation is by
   construction past that.
2. **Review.** A named reviewer — never the preparer —
   states they reviewed it, in their own words. The act
   stamps the same counts again: what the reviewer saw.
3. **Signature.** The controller's act, unchanged in shape
   and in everything downstream of it: the pack's
   ``decision`` is the :class:`SignOff` it has always been,
   the status becomes ``SIGNED_OFF``, the run closes. The
   signature is refused until both earlier acts stand, and
   refused to either earlier hand — three acts, three
   people, segregation the way the desk's other two-eyes
   rules already assume it (a handoff is never accepted by
   its own author; a template is never promoted by its own
   author; a signature is never the third act of one
   person's solo run).

The blocking discipline is exactly where it always was:
at verification. A blocked pack never reaches
``AWAITING_CONTROLLER``, so it cannot even be *prepared* —
the chain wraps the gate; it does not soften it, and no
act in the chain accepts, waives, or argues with a
variance. Each step's own refusal names its ground, in the
gate's idiom.

Before the chain completes, the preparer may take the
pack back — a withdrawal: named, reasoned, on the record.
The pack leaves the gate as ``WITHDRAWN`` and the close is
rebuilt; the withdrawn pack is never edited back into
play. After the signature there is no withdrawal at all:
a signed pack is immutable, and the restatement machinery
is the only road back, untouched.

Packs signed before the chain existed carry no chain, and
none is reconstructed for them: their single signature
stands as recorded, and the evidence bundle says so
(``chain: null`` — the honest-absence idiom every other
layer uses for what predates it).
"""

from __future__ import annotations

from .errors import EvidenceError
from .schemas import BoardPack, ChainAct


def act_for(pack: BoardPack, role: str) -> ChainAct | None:
    """The chain act for ``role`` on this pack, if it stands."""
    for act in pack.signoff_chain:
        if act.role == role:
            return act
    return None


def preparer_of(pack: BoardPack) -> ChainAct | None:
    return act_for(pack, "preparer")


def reviewer_of(pack: BoardPack) -> ChainAct | None:
    return act_for(pack, "reviewer")


def snapshot(pack: BoardPack) -> dict:
    """The pack as an act stamps it: the counts and the
    readiness statement the act's author vouched for /
    saw. Pure projection of the pack's own face."""
    return {
        "figures_count": len(pack.figures),
        "variances_count": len(pack.variances),
        "dispositions_count": len(pack.dispositions),
        "readiness_status": (
            pack.readiness.status if pack.readiness is not None
            else None
        ),
    }


def check_bundle_chain(pack: BoardPack) -> None:
    """The evidence bundle's completeness check for the
    chain: when a signed pack carries a chain, the chain
    must be whole — one preparation, one review, in order,
    by hands all different from each other and from the
    controller who signed. A signed pack carrying a broken
    chain is a gap in the sign-off evidence, named like
    every other gap the bundle refuses over. A signed pack
    carrying no chain is a legacy signature and passes:
    absence is stated, never repaired."""
    if not pack.signoff_chain:
        return
    roles = [act.role for act in pack.signoff_chain]
    if roles != ["preparer", "reviewer"]:
        raise EvidenceError(
            f"pack {pack.pack_id} is signed under a sign-off "
            f"chain reading {roles} — a whole chain is one "
            "preparation followed by one review, in that "
            "order; the sign-off evidence is incomplete"
        )
    preparer, reviewer = pack.signoff_chain
    if pack.decision is None:
        raise EvidenceError(
            f"pack {pack.pack_id} carries a sign-off chain "
            "but no sign decision — the chain's final act "
            "is missing from the record"
        )
    hands = {preparer.actor, reviewer.actor, pack.decision.actor}
    if len(hands) != 3:
        raise EvidenceError(
            f"pack {pack.pack_id} was signed under a chain "
            f"whose acts name {sorted(hands)} — preparation, "
            "review, and signature are three acts by three "
            "different people; the record shows fewer"
        )
