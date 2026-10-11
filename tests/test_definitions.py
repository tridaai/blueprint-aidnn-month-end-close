"""Definition packs: versioned data, strictly validated."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aidnn_close_agent.config import definition_pack_path
from aidnn_close_agent.definitions import DefinitionPack, load_definition_pack


def test_bundled_pack_loads():
    pack = load_definition_pack(definition_pack_path())
    assert pack.pack_id == "harborlight-close"
    assert pack.version == "1.0.0"
    assert pack.entity_ids() == ["HLG", "HLD", "HLE"]
    assert pack.metric("consolidated_revenue").derived.op == "sum_converted"


def test_pack_rejects_duplicate_metric_ids():
    raw = json.loads(definition_pack_path().read_text())
    raw["metrics"].append(dict(raw["metrics"][0]))
    with pytest.raises(ValidationError):
        DefinitionPack.model_validate(raw)


def test_pack_rejects_unknown_derived_reference():
    raw = json.loads(definition_pack_path().read_text())
    for metric in raw["metrics"]:
        if metric["metric_id"] == "consolidated_revenue":
            metric["derived"]["of"] = "no_such_metric"
    with pytest.raises(ValidationError):
        DefinitionPack.model_validate(raw)


def test_pack_rejects_unknown_elimination_reference():
    raw = json.loads(definition_pack_path().read_text())
    for metric in raw["metrics"]:
        if metric["metric_id"] == "eliminations_total":
            metric["derived"]["elimination_id"] = "nope"
    with pytest.raises(ValidationError):
        DefinitionPack.model_validate(raw)


def test_base_metric_needs_source_and_measure():
    raw = json.loads(definition_pack_path().read_text())
    for metric in raw["metrics"]:
        if metric["metric_id"] == "opex":
            metric.pop("measure")
    with pytest.raises(ValidationError):
        DefinitionPack.model_validate(raw)


def test_a_pack_change_is_a_new_version():
    """The regression discipline: same pack id, bumped version —
    the loader takes the file as it finds it, and packs built
    under each version stamp their own. (The eval suite reruns
    against whichever version is bundled.)"""
    raw = json.loads(definition_pack_path().read_text())
    raw["version"] = "1.1.0"
    pack = DefinitionPack.model_validate(raw)
    assert pack.version == "1.1.0"
    assert pack.pack_id == "harborlight-close"
