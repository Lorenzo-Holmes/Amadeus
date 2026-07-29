import json
from collections import Counter
from pathlib import Path

from tools.stage0b_adjudication.checklist import checklist_bytes
from tools.stage0b_adjudication.io import canonical_bytes
from tools.stage0b_adjudication.schema import validate_reviewed_manifest


ROOT = Path(__file__).resolve().parents[2]
REVIEWED_PATH = (
    ROOT / "fixtures/stage0b/reviewed/source_decisions_v0_1.json"
)


def _values() -> tuple[dict, dict]:
    checklist = json.loads(checklist_bytes(ROOT).decode("utf-8"))
    reviewed = json.loads(REVIEWED_PATH.read_text(encoding="utf-8"))
    return checklist, reviewed


def test_current_reviewed_manifest_is_valid_canonical_and_complete() -> None:
    checklist, reviewed = _values()
    validate_reviewed_manifest(reviewed, checklist)

    assert REVIEWED_PATH.read_bytes() == canonical_bytes(reviewed) + b"\n"
    assert len(reviewed["decisions"]) == 214
    assert Counter(
        decision["atomicity_decision"] for decision in reviewed["decisions"]
    ) == {"atomic": 185, "composite": 29}
    assert sum(len(decision["clauses"]) for decision in reviewed["decisions"]) == 259


def test_all_core_oracles_are_explicit_and_review_rationales_are_unique() -> None:
    _, reviewed = _values()
    core = [
        decision for decision in reviewed["decisions"]
        if decision["source_group"] == "core"
    ]

    assert len(core) == 95
    assert Counter(
        "+".join(decision["assigned_oracle_kinds"])
        for decision in core
    ) == {"D": 42, "D+S": 52, "D+H": 1}
    assert all(
        decision["source_id"] in decision["oracle_rationale"]
        and "explicit Core assignment" in decision["oracle_rationale"]
        for decision in core
    )
    assert len({
        decision["oracle_rationale"] for decision in reviewed["decisions"]
    }) == 214
    assert len({
        decision["atomicity_rationale"] for decision in reviewed["decisions"]
    }) == 214


def test_composite_decisions_are_an_explicit_reviewed_set() -> None:
    _, reviewed = _values()
    composite_ids = {
        decision["source_id"] for decision in reviewed["decisions"]
        if decision["atomicity_decision"] == "composite"
    }

    assert composite_ids == {
        "AC-008", "AC-023", "AC-042", "AC-050", "AC-051", "AC-058",
        "AC-060", "AC-066", "AC-069", "AC-070", "AC-073", "AC-076",
        "AC-081", "AC-087", "AC-088", "AC-093", "AC-095", "BR-03",
        "EXIT-02", "EXIT-03", "EXIT-06", "EXIT-10", "ID-04", "PRO-06",
        "REL-12", "SEC-06", "TIME-03", "TIME-04", "TOOL-06",
    }
