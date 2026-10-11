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
