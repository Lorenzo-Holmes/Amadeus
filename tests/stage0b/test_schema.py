import copy
import json
from pathlib import Path

import pytest

from tools.stage0b_adjudication.checklist import checklist_bytes
from tools.stage0b_adjudication.schema import validate_reviewed_manifest


ROOT = Path(__file__).resolve().parents[2]


def _checklist() -> dict:
    return json.loads(checklist_bytes(ROOT).decode("utf-8"))


def _valid_reviewed() -> dict:
    checklist = _checklist()
    decisions = []
    for item in checklist["items"]:
        oracle_kinds = item["source_declared_oracle_kinds"] or ["D"]
        source_id = item["source_id"]
        decisions.append({
            "source_id": source_id,
            "source_group": item["source_group"],
            "source_binding_sha256": item["source_binding_sha256"],
            "assigned_oracle_kinds": oracle_kinds,
            "oracle_rationale": f"{source_id} oracle rationale",
            "atomicity_decision": "atomic",
            "atomicity_rationale": f"{source_id} atomicity rationale",
            "clauses": [{
                "clause_id": f"{source_id}#1",
                "stimulus_scope": item["action"] or item["scenario_or_title"],
                "expected_scope": item["expected"],
                "required_oracle_kinds": oracle_kinds,
            }],
        })
    return {
        "schema_version": "0.1",
        "input_artifacts": checklist["input_artifacts"],
        "decisions": decisions,
    }


def test_valid_reviewed_manifest_covers_exact_source_set() -> None:
    reviewed = _valid_reviewed()
    result = validate_reviewed_manifest(reviewed, _checklist())
    assert result is reviewed
    assert len(result["decisions"]) == 214


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(extra=True), "top-level fields"),
        (lambda value: value.update(schema_version="0.2"), "schema version"),
        (
            lambda value: value["input_artifacts"].update(
                {"source_index_v0_1.json": "0" * 64}
            ),
            "input artifact identity",
        ),
        (lambda value: value["decisions"].pop(), "source id set"),
        (
            lambda value: value["decisions"].__setitem__(
                1, copy.deepcopy(value["decisions"][0])
            ),
            "duplicate source id",
        ),
        (
            lambda value: value["decisions"][0].update(
                source_binding_sha256="0" * 64
            ),
            "binding identity",
        ),
        (
            lambda value: value["decisions"][0].update(
                assigned_oracle_kinds=[]
            ),
            "oracle kinds",
        ),
        (
            lambda value: value["decisions"][0].update(
                assigned_oracle_kinds=["H", "D"]
            ),
            "oracle kinds",
        ),
        (
            lambda value: value["decisions"][0].update(oracle_rationale=" "),
            "oracle rationale",
        ),
        (
            lambda value: value["decisions"][0].update(
                atomicity_decision="unknown"
            ),
            "atomicity decision",
        ),
        (
            lambda value: value["decisions"][0].update(clauses=[]),
            "atomic clause count",
        ),
        (
            lambda value: value["decisions"][0].update(
                atomicity_decision="composite"
            ),
            "composite clause count",
        ),
        (
            lambda value: value["decisions"][0]["clauses"][0].update(
                clause_id="AC-001#2"
            ),
            "clause id sequence",
        ),
        (
            lambda value: value["decisions"][0]["clauses"][0].update(
                stimulus_scope=""
            ),
            "stimulus scope",
        ),
        (
            lambda value: value["decisions"][0]["clauses"][0].update(
                required_oracle_kinds=["H"]
            ),
            "clause oracle coverage",
        ),
    ],
)
def test_reviewed_manifest_rejects_invalid_contract(mutation, message: str) -> None:
    reviewed = _valid_reviewed()
    mutation(reviewed)
    with pytest.raises(ValueError, match=message):
        validate_reviewed_manifest(reviewed, _checklist())


def test_behavior_source_cannot_drop_declared_oracle() -> None:
    reviewed = _valid_reviewed()
    decision = next(
        item for item in reviewed["decisions"]
        if len(item["assigned_oracle_kinds"]) > 1
    )
    decision["assigned_oracle_kinds"] = decision["assigned_oracle_kinds"][:1]
    decision["clauses"][0]["required_oracle_kinds"] = decision[
        "assigned_oracle_kinds"
    ]

    with pytest.raises(ValueError, match="declared oracle downgrade"):
        validate_reviewed_manifest(reviewed, _checklist())


def test_composite_decision_accepts_contiguous_clauses() -> None:
    reviewed = _valid_reviewed()
    decision = reviewed["decisions"][0]
    decision["atomicity_decision"] = "composite"
    decision["clauses"].append({
        "clause_id": "AC-001#2",
        "stimulus_scope": "second action scope",
        "expected_scope": "second assertion scope",
        "required_oracle_kinds": decision["assigned_oracle_kinds"],
    })

    validate_reviewed_manifest(reviewed, _checklist())
