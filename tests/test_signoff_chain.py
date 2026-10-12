"""The sign-off chain: preparation, review, signature —
three acts by three people, in order, or no signature.

The pins here are the chain's own: the order and its
refusals, segregation, the counts each act stamps, the
blocking discipline biting at the first step, withdrawal
before completion and its impossibility after, and the
evidence bundle carrying the chain whole — or stating a
legacy signature's absence honestly.
"""

from __future__ import annotations

import pytest

from aidnn_close_agent import comparatives
from aidnn_close_agent.errors import EvidenceError, GateError

PREPARER = "Priya Nair"
REVIEWER = "Jonas Weber"
CONTROLLER = "Mara Ellison"
NOTE = "reviewed the variances, the figures, and the readiness statement"


@pytest.fixture()
def awaiting(service, run_corrected):
    """A verified pack standing at the gate."""
    pack = service.build_pack(run_corrected.run_id)
    assert pack.status == "AWAITING_CONTROLLER"
    return pack


def _signed(service, pack):
    service.prepare_pack(pack.pack_id, PREPARER)
    service.review_pack(pack.pack_id, REVIEWER, NOTE)
    return service.sign_off(pack.pack_id, "sign", CONTROLLER,
                            "chain complete; figures verified")


# -- the happy path -------------------------------------------------------


def test_full_chain_signs_and_the_face_carries_it(service, awaiting):
    signed = _signed(service, awaiting)
    assert signed.status == "SIGNED_OFF"
    # The controller's act is the decision it has always been.
    assert signed.decision.actor == CONTROLLER
    assert signed.decision.decision == "sign"
    # The chain stands on the face, in order, each act
    # stamping the pack as it stood: 25 verified figures,
    # no variances, no dispositions, no readiness governor.
    assert [a.role for a in signed.signoff_chain] == [
        "preparer", "reviewer"]
    for act in signed.signoff_chain:
        assert act.figures_count == 25
        assert act.variances_count == 0
        assert act.dispositions_count == 0
        assert act.readiness_status is None
        assert act.at
    assert signed.signoff_chain[0].actor == PREPARER
    assert signed.signoff_chain[1].actor == REVIEWER
    assert signed.signoff_chain[1].note == NOTE
    # Downstream reads key on the signature exactly as
    # before: the signed pack is findable as the period's.
    found = comparatives.find_signed_pack(service.store, "2026-09")
    assert found is not None and found.pack_id == signed.pack_id
    assert service.get_run(signed.run_id).status == "CLOSED"


def test_return_is_also_the_chains_third_act(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    service.review_pack(awaiting.pack_id, REVIEWER, NOTE)
    returned = service.sign_off(awaiting.pack_id, "return", CONTROLLER,
                                "one figure needs another look")
    assert returned.status == "RETURNED"
    assert returned.decision.decision == "return"
    assert [a.role for a in returned.signoff_chain] == [
        "preparer", "reviewer"]


# -- order, each refusal by name ------------------------------------------


def test_sign_without_preparation_is_refused(service, awaiting):
    with pytest.raises(GateError, match="has not been prepared"):
        service.sign_off(awaiting.pack_id, "sign", CONTROLLER)


def test_sign_after_preparation_without_review_is_refused(
        service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    with pytest.raises(GateError, match="has not been reviewed"):
        service.sign_off(awaiting.pack_id, "sign", CONTROLLER)


def test_review_before_preparation_is_refused(service, awaiting):
    with pytest.raises(GateError, match="has not been prepared"):
        service.review_pack(awaiting.pack_id, REVIEWER, NOTE)


def test_preparation_is_recorded_once(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    with pytest.raises(GateError, match="already prepared"):
        service.prepare_pack(awaiting.pack_id, "Someone Else")


def test_review_is_recorded_once(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    service.review_pack(awaiting.pack_id, REVIEWER, NOTE)
    with pytest.raises(GateError, match="already reviewed"):
        service.review_pack(awaiting.pack_id, "Someone Else", NOTE)


def test_acts_must_name_their_people(service, awaiting):
    with pytest.raises(GateError, match="must name its preparer"):
        service.prepare_pack(awaiting.pack_id, "  ")
    service.prepare_pack(awaiting.pack_id, PREPARER)
    with pytest.raises(GateError, match="must name its reviewer"):
        service.review_pack(awaiting.pack_id, "", NOTE)
    with pytest.raises(GateError, match="must carry a note"):
        service.review_pack(awaiting.pack_id, REVIEWER, "  ")


# -- segregation: three acts, three people ---------------------------------


def test_preparer_cannot_review_their_own_pack(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    with pytest.raises(GateError, match="cannot also review"):
        service.review_pack(awaiting.pack_id, PREPARER, NOTE)


def test_preparer_cannot_sign_their_own_pack(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    service.review_pack(awaiting.pack_id, REVIEWER, NOTE)
    with pytest.raises(GateError, match="already stands on"):
        service.sign_off(awaiting.pack_id, "sign", PREPARER)


def test_reviewer_cannot_sign_the_pack_they_reviewed(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    service.review_pack(awaiting.pack_id, REVIEWER, NOTE)
    with pytest.raises(GateError, match="already stands on"):
        service.sign_off(awaiting.pack_id, "sign", REVIEWER)


# -- the blocking discipline bites at the first step ------------------------


def test_blocked_pack_cannot_even_be_prepared(service, run_ready):
    pack = service.build_pack(run_ready.run_id)
    assert pack.status == "BLOCKED"
    with pytest.raises(GateError, match="is BLOCKED"):
        service.prepare_pack(pack.pack_id, PREPARER)
    with pytest.raises(GateError, match="is BLOCKED"):
        service.review_pack(pack.pack_id, REVIEWER, NOTE)
    with pytest.raises(GateError, match="is BLOCKED"):
        service.withdraw_pack(pack.pack_id, PREPARER, "take it back")


# -- withdrawal ---------------------------------------------------------------


def test_withdrawal_takes_the_pack_back_on_the_record(
        service, awaiting, run_corrected):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    service.review_pack(awaiting.pack_id, REVIEWER, NOTE)
    withdrawn = service.withdraw_pack(
        awaiting.pack_id, PREPARER,
        "the HLE subledger extract is being re-issued; rebuild "
        "against the corrected one")
    assert withdrawn.status == "WITHDRAWN"
    assert withdrawn.withdrawal.actor == PREPARER
    assert "re-issued" in withdrawn.withdrawal.reason
    assert withdrawn.withdrawal.at
    # The chain that stood stays on the record.
    assert [a.role for a in withdrawn.signoff_chain] == [
        "preparer", "reviewer"]
    # A withdrawn pack is out of the chain for good.
    with pytest.raises(GateError, match="is WITHDRAWN"):
        service.sign_off(withdrawn.pack_id, "sign", CONTROLLER)
    with pytest.raises(GateError, match="is WITHDRAWN"):
        service.prepare_pack(withdrawn.pack_id, PREPARER)
    # And the close is rebuilt instead: a fresh pack walks
    # the chain and signs.
    rebuilt = service.build_pack(run_corrected.run_id)
    assert rebuilt.pack_id != withdrawn.pack_id
    assert _signed(service, rebuilt).status == "SIGNED_OFF"


def test_only_the_preparer_can_withdraw(service, awaiting):
    service.prepare_pack(awaiting.pack_id, PREPARER)
    with pytest.raises(GateError, match="only its preparer"):
        service.withdraw_pack(awaiting.pack_id, REVIEWER, "not mine")
    with pytest.raises(GateError, match="must carry a reason"):
        service.withdraw_pack(awaiting.pack_id, PREPARER, "  ")


def test_unprepared_pack_has_nothing_to_withdraw(service, awaiting):
    with pytest.raises(GateError, match="has not been prepared"):
        service.withdraw_pack(awaiting.pack_id, PREPARER, "take it back")


def test_signed_pack_cannot_be_withdrawn(service, awaiting):
    signed = _signed(service, awaiting)
    with pytest.raises(GateError, match="cannot be withdrawn"):
        service.withdraw_pack(signed.pack_id, PREPARER, "too late")


# -- the evidence bundle: the chain whole, or legacy stated -------------------


def test_bundle_carries_the_whole_chain(service, awaiting):
    signed = _signed(service, awaiting)
    record = service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    import json
    document = json.loads(data)
    chain = document["sign_off"]["chain"]
    assert [a["role"] for a in chain] == ["preparer", "reviewer"]
    assert chain[0]["actor"] == PREPARER
    assert chain[1]["actor"] == REVIEWER
    assert chain[1]["note"] == NOTE
    raw, _ = service.evidence_download(signed.pack_id, "txt")
    text = raw.decode("utf-8")
    assert "chain · preparer: Priya Nair" in text
    assert "chain · reviewer: Jonas Weber" in text
    assert record.figure_count == 25


def test_bundle_states_a_legacy_signature_honestly(service, awaiting):
    """A pack whose record carries a signature and no chain
    — the shape pre-chain code wrote — bundles with the
    absence stated, never with acts reconstructed."""
    signed = _signed(service, awaiting)
    pack = service.store.get_pack(signed.pack_id)
    pack.signoff_chain = []
    service.store.save_pack(pack)
    service.generate_evidence(signed.pack_id)
    data, _ = service.evidence_download(signed.pack_id, "json")
    import json
    document = json.loads(data)
    assert document["sign_off"]["chain"] is None
    assert document["sign_off"]["actor"] == CONTROLLER
    raw, _ = service.evidence_download(signed.pack_id, "txt")
    assert "signed under the single-act sign-off" in raw.decode("utf-8")


def test_bundle_refuses_a_broken_chain(service, awaiting):
    """A signed pack whose chain is present but incomplete
    is a gap in the sign-off evidence, named at generation."""
    signed = _signed(service, awaiting)
    pack = service.store.get_pack(signed.pack_id)
    pack.signoff_chain = pack.signoff_chain[:1]  # review struck
    service.store.save_pack(pack)
    with pytest.raises(EvidenceError, match="chain"):
        service.generate_evidence(signed.pack_id)
