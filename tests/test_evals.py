"""The eval pack is part of the test gate: it must pass whole."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "run_evals",
    Path(__file__).resolve().parents[1] / "evals" / "run_evals.py",
)
run_evals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_evals)


def test_eval_pack_passes():
    results = run_evals.evaluate()
    assert results["gate_passed"], results["gates"]
    assert results["gold_passed"] == results["gold_questions"] == 25
    assert results["traceability"] == 1.0
    # Act two: the comparative month gates too.
    assert results["october_gold_passed"] == \
        results["october_gold_questions"] == 25
    assert results["gates"]["comparatives tie to the signed pack"]
    assert results["gates"]["restatement named with gold figures"]
    assert results["gates"]["signed prior pack byte-identical"]
    # Act three: the audit evidence bundles gate too.
    assert results["evidence_figures"] == 25
    assert results["gates"]["evidence bundle complete"]
    assert results["gates"]["evidence regenerates byte-identical"]
    assert results["gates"]["evidence digest matches stored bytes"]
    assert results["gates"]["evidence refused for the blocked pack"]
    assert results["gates"][
        "restated bundle carries restatement + acknowledgement"]
    # Round 4: the flux schedule gates too.
    assert results["gates"]["flux identities hold for every comparative figure"]
    assert results["gates"]["flux materiality flags the big movers"]
    assert results["gates"]["flux definition-changed figures flagged"]
    assert results["gates"]["restated bundle carries the flux schedule"]
    # Round 8: definition change governance gates too.
    assert results["gates"][
        "governance: activation without a dry-run refused by name"]
    assert results["gates"][
        "governance: dry-run reproduces the hand-computed change list"]
    assert results["gates"][
        "governance: dry-run byte-stable; signed packs untouched"]
    assert results["gates"][
        "governance: activation refusals name their grounds"]
    assert results["gates"][
        "governance: next period selects the activated version"]
    assert results["gates"][
        "governance: first governed pack states the change"]
    assert results["gates"][
        "governance: bundle carries the activation and the dry-run"]
    # Round 9: figure drill-down gates too.
    assert results["gates"][
        "drill: every september figure foots to its lines"]
    assert results["gates"][
        "drill: base figure lines are the planted lines"]
    assert results["gates"][
        "drill: elimination shows both legs at the stamp"]
    assert results["gates"][
        "drill: converted figure converts once per entity at the stamp"]
    assert results["gates"][
        "drill: derived figures compose, on no lines of their own"]
    assert results["gates"][
        "drill: blocked and stale packs drill on their own stamps"]
    assert results["gates"][
        "drill: tampered source line raises DRILL_MISMATCH "
        "naming the figure"]
    assert results["gates"][
        "drill: edited rate table reprices no drill (the stamp "
        "is the basis)"]
    assert results["gates"]["drill: october figures foot to their lines"]
    assert results["gates"][
        "drill: october bundle cites every drill by digest"]
    assert results["gates"][
        "evidence bundle cites every drill by digest"]
    assert results["evidence_drills"] == 25
    # Round 10: pre-close readiness gates too.
    assert results["gates"]["readiness: complete period passes, manifest cited"]
    assert results["gates"]["readiness: missing and short items named"]
    assert results["gates"]["readiness: build refused while unready, items named"]
    assert results["gates"]["readiness: waiver refusals name their grounds"]
    assert results["gates"][
        "readiness: waived build states the waiver; bundle carries it"]
    assert results["gates"]["readiness: another item's waiver does not unblock"]
    assert results["gates"]["readiness: the check is a pure read"]
    assert results["gates"]["readiness: signed packs byte-identical"]
    # Round 11: the sign-off chain gates too.
    assert results["gates"][
        "chain: blocked pack cannot be prepared "
        "(blocking bites at step one)"]
    assert results["gates"]["chain: review before preparation refused"]
    assert results["gates"]["chain: sign before preparation refused"]
    assert results["gates"]["chain: sign before review refused"]
    assert results["gates"]["chain: preparer cannot review their own pack"]
    assert results["gates"]["chain: neither earlier hand can sign"]
    assert results["gates"]["chain: withdrawal by another hand refused"]
    assert results["gates"][
        "chain: withdrawal recorded; pack out of the chain"]
    assert results["gates"][
        "chain: full chain signs; downstream reads work as before"]
    assert results["gates"][
        "chain: signed pack byte-identical after later builds"]
    assert results["gates"]["chain: bundle carries all three acts"]
    assert results["gates"]["chain: withdrawal after signature refused"]
    assert results["gates"][
        "chain: legacy bundle states its single signature, "
        "no invented acts"]
