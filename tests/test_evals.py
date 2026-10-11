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
