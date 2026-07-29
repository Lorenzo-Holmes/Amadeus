import copy
import json
from pathlib import Path

import pytest

from tools.stage0b_adjudication.checklist import build_checklist
from tools.stage0b_adjudication.io import load_stage0a_inputs


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_inputs_have_exact_identity_and_counts() -> None:
    inputs = load_stage0a_inputs(ROOT)

    assert set(inputs) == {
        "source_index_v0_1.json",
        "oracle_assignment_worklist_v0_1.json",
        "atomicity_worklist_v0_1.json",
        "source_toolchain_report_v0_1.json",
    }
    assert len(inputs["source_index_v0_1.json"]["sources"]) == 214
    assert inputs["oracle_assignment_worklist_v0_1.json"]["pending_assignment_count"] == 95
    assert inputs["atomicity_worklist_v0_1.json"]["pending_review_count"] == 214


@pytest.mark.parametrize("target", ["oracle", "atomicity"])
def test_checklist_rejects_binding_mismatch(target: str) -> None:
    inputs = copy.deepcopy(load_stage0a_inputs(ROOT))
    key = (
        "oracle_assignment_worklist_v0_1.json"
        if target == "oracle"
        else "atomicity_worklist_v0_1.json"
    )
    inputs[key]["items"][0]["source_binding_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="binding mismatch"):
        build_checklist(inputs)


def test_checklist_rejects_duplicate_source_id() -> None:
    inputs = copy.deepcopy(load_stage0a_inputs(ROOT))
    items = inputs["oracle_assignment_worklist_v0_1.json"]["items"]
    items[1]["source_id"] = items[0]["source_id"]

    with pytest.raises(ValueError, match="source id set"):
        build_checklist(inputs)
