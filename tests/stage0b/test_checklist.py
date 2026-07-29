import hashlib
import json
from pathlib import Path

from tools.stage0b_adjudication.checklist import checklist_bytes


ROOT = Path(__file__).resolve().parents[2]


def test_checklist_is_complete_ordered_and_canonical() -> None:
    payload = checklist_bytes(ROOT)
    checklist = json.loads(payload.decode("utf-8"))

    assert payload.endswith(b"\n")
    assert checklist["source_counts"] == {
        "baseline": 53,
        "core": 95,
        "increment": 66,
    }
    assert checklist["source_declared_count"] == 119
    assert checklist["pending_assignment_count"] == 95
    assert checklist["pending_review_count"] == 214
    assert len(checklist["items"]) == 214

    ids = [item["source_id"] for item in checklist["items"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids)) == 214
    assert ids[0] == "AC-001"
    assert ids[-1] == "USE-05"

    first = checklist["items"][0]
    assert first["source_group"] == "core"
    assert first["oracle_review_state"] == "pending_assignment"
    assert first["assigned_oracle_kinds"] == []
    assert first["atomicity_review_state"] == "pending_review"
    assert first["atomicity_decision"] is None
    assert first["clauses"] == []

    assert payload == checklist_bytes(ROOT)
    assert hashlib.sha256(payload).hexdigest() == hashlib.sha256(
        checklist_bytes(ROOT)
    ).hexdigest()


def test_checklist_embeds_all_frozen_input_hashes() -> None:
    checklist = json.loads(checklist_bytes(ROOT).decode("utf-8"))
    assert checklist["input_artifacts"] == {
        "atomicity_worklist_v0_1.json": "D93342C7E93F4C368DF44989BB3B341AAB364B472E9B6150FC7B97E469D0BFD2",
        "oracle_assignment_worklist_v0_1.json": "7BD9350A108B4274FA07D83A1315FC33226504DCD998DAA17AE3ED83C917DE51",
        "source_index_v0_1.json": "D29855B5F8ED870608CF52B91A9997E4D41922E4085FBAE41E385610D87DE25C",
        "source_toolchain_report_v0_1.json": "3154019197C1B6C16E951F278E9688F1DD6D18459BD5D2B3AD71A87C92BBD3F0",
    }
