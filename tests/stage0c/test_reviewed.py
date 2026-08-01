import copy
from pathlib import Path
from typing import Any

import pytest

from tools.stage0c_fixtures.constants import INPUT_IDENTITIES, SCHEMA_VERSION
from tools.stage0c_fixtures.dsl import resolve_json_pointer
from tools.stage0c_fixtures.io import canonical_bytes, sha256_upper
from tools.stage0c_fixtures.reviewed import (
    REVIEWED_EXACT_FIELDS,
    load_reviewed_case,
    validate_batch_review_record,
    validate_reviewed_batch,
    validate_reviewed_case,
    validate_reviewed_closed_set,
)
from tools.stage0c_fixtures.types import FixtureInputError, ValidationIssue


_FROZEN_FIELDS = (
    "clause_id",
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
)


def _setup_step(replay_key: str) -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "seed-backend",
        "handler_id": "sandbox.seed_backend_response",
        "params": {
            "replay_key": replay_key,
            "output": {"status": "fixture-output", "sequence": 1},
        },
    }


def _stimulus_step(replay_key: str) -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "replay-backend",
        "handler_id": "backend.replay",
        "params": {"replay_key": replay_key, "input": {}},
    }


def _machine_assertion() -> dict[str, Any]:
    return {
        "sequence": 1,
        "assertion_id": "assert-status",
        "handler_id": "receipt.status",
        "step_id": "replay-backend",
        "params": {"expected": "completed"},
    }


def _rubric(kind: str) -> dict[str, Any]:
    return {
        "criterion_id": f"criterion-{kind.lower()}",
        "oracle_kind": kind,
        "question": f"Does the fixture provide {kind} evidence?",
        "evidence_case_json_pointers": [
            "/stimulus_steps/0/params",
            "/stimulus_steps/0/step_id",
        ],
        "allowed_scores": [-1, 0, 1],
        "passing_scores": [1],
    }


def _sandbox_profile() -> dict[str, Any]:
    return {
        "profile_id": "sandbox-stage0c",
        "allowed_effects": [],
        "fixed_clock": "2026-01-01T00:00:00Z",
        "id_seed": "stage0c-seed",
        "reset_policy": "fresh_context",
        "cleanup_policy": "always",
    }


def _case_body(clause_id: str, oracle_kinds: list[str]) -> dict[str, Any]:
    source_id = clause_id.split("#", 1)[0]
    replay_key = f"replay-{source_id.lower()}"
    machine = bool(set(oracle_kinds) & {"D", "S"})
    human = [kind for kind in oracle_kinds if kind in {"H", "J"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": f"case-{clause_id.lower().replace('#', '-')}",
        "source_id": source_id,
        "source_clause_id": clause_id,
        "oracle_kinds": list(oracle_kinds),
        "setup_steps": [_setup_step(replay_key)],
        "stimulus_steps": [_stimulus_step(replay_key)],
        "machine_assertions": [_machine_assertion()] if machine else [],
        "rubric_requirements": [_rubric(kind) for kind in human],
        "sandbox_profile": _sandbox_profile() if "S" in oracle_kinds else None,
    }


def _reviewed(frozen_clause: dict[str, Any]) -> dict[str, Any]:
    clause_id = frozen_clause["clause_id"]
    oracle_kinds = list(frozen_clause["required_oracle_kinds"])
    mappings = []
    rubric_index = 0
    for kind in oracle_kinds:
        if kind in {"D", "S"}:
            pointer = "/machine_assertions/0"
        else:
            pointer = f"/rubric_requirements/{rubric_index}"
            rubric_index += 1
        mappings.append(
            {
                "oracle_kind": kind,
                "case_json_pointers": [pointer],
                "mapping_note": f"{kind} evidence is bound to the final case body.",
            }
        )
    row = {
        "schema_version": SCHEMA_VERSION,
        "stage0b_manifest_sha256": INPUT_IDENTITIES["stage0b_manifest"][
            "sha256"
        ],
        **{field: copy.deepcopy(frozen_clause[field]) for field in _FROZEN_FIELDS},
        "case_body": _case_body(clause_id, oracle_kinds),
        "stimulus_mapping": {
            "case_json_pointers": [
                "/stimulus_steps/0/handler_id",
                "/stimulus_steps/0/params",
            ],
            "mapping_note": "The concrete stimulus handler and params are reviewed.",
        },
        "assertion_or_rubric_mapping": mappings,
        "reviewer": {
            "role": "conversion_reviewer",
            "reviewer_id": "reviewer-stage0c",
            "reviewed_at": "2026-07-29",
        },
        "rationale": "The frozen stimulus and expectation are represented explicitly.",
    }
    assert set(row) == set(REVIEWED_EXACT_FIELDS)
    return row


def _codes(issues: list[ValidationIssue]) -> list[str]:
    return [issue.code for issue in issues]


def _issues_for(
    row: dict[str, Any],
    frozen_clause: dict[str, Any],
    fixture_schema: dict[str, Any],
) -> list[ValidationIssue]:
    issues = validate_reviewed_case(row, frozen_clause, fixture_schema)
    assert issues == sorted(
        set(issues),
        key=lambda issue: (issue.json_pointer, issue.code, issue.message),
    )
    assert all(issue.message.strip() for issue in issues)
    return issues


def test_reviewed_public_exact_fields_are_immutable_and_exact() -> None:
    assert type(REVIEWED_EXACT_FIELDS) is tuple
    assert REVIEWED_EXACT_FIELDS == (
        "schema_version",
        "stage0b_manifest_sha256",
        "clause_id",
        "source_id",
        "source_group",
        "source_binding_sha256",
        "decision_sha256",
        "clause_stimulus_sha256",
        "clause_expected_sha256",
        "clause_content_sha256",
        "required_oracle_kinds",
        "case_body",
        "stimulus_mapping",
        "assertion_or_rubric_mapping",
        "reviewer",
        "rationale",
    )


@pytest.mark.parametrize("clause_id", ["AC-001#1", "AC-006#1", "INJ-09#1"])
def test_reviewed_d_s_h_j_golden_cases_validate(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    clause_id: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id[clause_id]
    assert _issues_for(_reviewed(frozen_clause), frozen_clause, fixture_schema) == []


@pytest.mark.parametrize("clause_id", ["AC-001#1", "AC-006#1", "INJ-09#1"])
def test_golden_mappings_resolve_to_actual_case_body_values(
    frozen_inputs: Any,
    clause_id: str,
) -> None:
    row = _reviewed(frozen_inputs.clauses_by_id[clause_id])
    body = row["case_body"]
    stimulus_pointers = row["stimulus_mapping"]["case_json_pointers"]
    assert resolve_json_pointer(body, stimulus_pointers[0]) == (
        body["stimulus_steps"][0]["handler_id"]
    )
    assert resolve_json_pointer(body, stimulus_pointers[1]) == (
        body["stimulus_steps"][0]["params"]
    )

    rubric_index = 0
    for mapping in row["assertion_or_rubric_mapping"]:
        pointer = mapping["case_json_pointers"][0]
        actual = resolve_json_pointer(body, pointer)
        if mapping["oracle_kind"] in {"D", "S"}:
            assert actual == body["machine_assertions"][0]
        else:
            assert actual == body["rubric_requirements"][rubric_index]
            rubric_index += 1


def test_top_level_error_precedence_is_frozen(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    missing_reviewer = _reviewed(frozen_clause)
    del missing_reviewer["reviewer"]
    missing_reviewer["rationale"] = "\u2003"
    assert _issues_for(missing_reviewer, frozen_clause, fixture_schema) == [
        ValidationIssue(
            "/reviewer",
            "reviewer_missing",
            "reviewer is required before a reviewed conversion can pass",
        )
    ]

    missing_other = _reviewed(frozen_clause)
    del missing_other["rationale"]
    assert _codes(_issues_for(missing_other, frozen_clause, fixture_schema)) == [
        "reviewed_exact_fields_invalid"
    ]

    extra = _reviewed(frozen_clause)
    extra["author"] = "forbidden"
    assert _codes(_issues_for(extra, frozen_clause, fixture_schema)) == [
        "reviewed_exact_fields_invalid"
    ]


@pytest.mark.parametrize(
    "field",
    ("schema_version", "stage0b_manifest_sha256", *_FROZEN_FIELDS),
)
def test_every_frozen_identity_field_is_bound(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    field: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    row[field] = ["H"] if field == "required_oracle_kinds" else "MUTATED"
    issues = _issues_for(row, frozen_clause, fixture_schema)
    assert "reviewed_frozen_identity_mismatch" in _codes(issues)
    assert f"/{field}" in {issue.json_pointer for issue in issues}


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_clause_id", "AC-002#1"),
        ("case_id", "case-ac-002-1"),
        ("source_id", "AC-002"),
        ("oracle_kinds", ["H"]),
    ],
)
def test_case_body_identity_cannot_drift_from_frozen_clause(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    field: str,
    replacement: Any,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    row["case_body"][field] = replacement
    issues = _issues_for(row, frozen_clause, fixture_schema)
    assert "reviewed_case_identity_mismatch" in _codes(issues)
    assert f"/case_body/{field}" in {issue.json_pointer for issue in issues}
    if field != "oracle_kinds":
        assert set(_codes(issues)) == {"reviewed_case_identity_mismatch"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda pointers: pointers.clear(),
        lambda pointers: pointers.append(pointers[0]),
        lambda pointers: pointers.reverse(),
    ],
    ids=("empty", "duplicate", "unsorted"),
)
def test_stimulus_pointer_set_is_nonempty_unique_and_unicode_sorted(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    mutation: Any,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    mutation(row["stimulus_mapping"]["case_json_pointers"])
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "stimulus_mapping_pointer_set_invalid"
    ]


@pytest.mark.parametrize(
    "pointer",
    [
        "/stimulus_steps",
        "/stimulus_steps/00",
        "/stimulus_steps/-1",
        "/stimulus_steps/1",
        "/stimulus_steps/0/~2",
        "/setup_steps/0",
        "/stimulus_steps-shadow/0",
        f"/stimulus_steps/{'9' * 5000}",
    ],
)
def test_stimulus_pointer_must_resolve_under_a_concrete_step(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    pointer: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    row["stimulus_mapping"]["case_json_pointers"] = [pointer]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "stimulus_mapping_pointer_invalid"
    ]


def test_stimulus_mapping_keeps_handler_and_same_step_params_pair(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    row["stimulus_mapping"]["case_json_pointers"] = [
        "/stimulus_steps/0/handler_id"
    ]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "stimulus_mapping_pointer_invalid"
    ]


@pytest.mark.parametrize(
    ("surface", "expected_code"),
    [
        ("stimulus", "stimulus_mapping_exact_fields_invalid"),
        ("oracle", "oracle_mapping_exact_fields_invalid"),
    ],
)
def test_nested_mapping_objects_have_exact_fields(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    surface: str,
    expected_code: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    if surface == "stimulus":
        row["stimulus_mapping"]["extra"] = True
    else:
        row["assertion_or_rubric_mapping"][0]["extra"] = True
    assert expected_code in _codes(_issues_for(row, frozen_clause, fixture_schema))


@pytest.mark.parametrize("shape", ["empty", "duplicate", "unsorted", "unresolved"])
def test_oracle_pointer_set_and_resolution_are_strict(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    shape: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    pointers = row["assertion_or_rubric_mapping"][0]["case_json_pointers"]
    if shape == "empty":
        pointers.clear()
    elif shape == "duplicate":
        pointers.append(pointers[0])
    elif shape == "unsorted":
        pointers[:] = ["/machine_assertions/0/step_id", "/machine_assertions/0/params"]
    else:
        pointers[:] = ["/machine_assertions/9"]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "oracle_mapping_pointer_invalid"
    ]


@pytest.mark.parametrize("kind", ["D", "S"])
def test_machine_oracles_must_target_machine_assertions(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    kind: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-006#1"]
    row = _reviewed(frozen_clause)
    mapping = next(
        item for item in row["assertion_or_rubric_mapping"] if item["oracle_kind"] == kind
    )
    mapping["case_json_pointers"] = ["/stimulus_steps/0"]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "machine_oracle_target_invalid"
    ]


@pytest.mark.parametrize("kind", ["H", "J"])
def test_human_oracles_must_target_same_kind_rubric(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    kind: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["INJ-09#1"]
    row = _reviewed(frozen_clause)
    mapping = next(
        item for item in row["assertion_or_rubric_mapping"] if item["oracle_kind"] == kind
    )
    other_index = 1 if kind == "H" else 0
    mapping["case_json_pointers"] = [f"/rubric_requirements/{other_index}"]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "rubric_oracle_target_invalid"
    ]


def test_each_required_oracle_kind_must_have_a_mapping(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-006#1"]
    row = _reviewed(frozen_clause)
    row["assertion_or_rubric_mapping"] = [
        item
        for item in row["assertion_or_rubric_mapping"]
        if item["oracle_kind"] != "S"
    ]
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "required_oracle_unmapped"
    ]


@pytest.mark.parametrize(
    "surface",
    ("stimulus_note", "oracle_note", "rationale", "reviewer_id"),
)
def test_explanations_reject_unicode_whitespace(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    surface: str,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    if surface == "stimulus_note":
        row["stimulus_mapping"]["mapping_note"] = "\u2003\t"
    elif surface == "oracle_note":
        row["assertion_or_rubric_mapping"][0]["mapping_note"] = "\u2003\t"
    elif surface == "rationale":
        row["rationale"] = "\u2003\t"
    else:
        row["reviewer"]["reviewer_id"] = "\u2003\t"
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "review_explanation_empty"
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda reviewer: reviewer.update(extra="forbidden"),
        lambda reviewer: reviewer.pop("reviewed_at"),
        lambda reviewer: reviewer.update(role="author"),
        lambda reviewer: reviewer.update(reviewed_at="2026-02-30"),
        lambda reviewer: reviewer.update(reviewed_at="2026-7-29"),
    ],
    ids=("extra", "missing", "role", "gregorian-date", "date-shape"),
)
def test_present_reviewer_object_is_strict(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
    mutation: Any,
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    mutation(row["reviewer"])
    assert _codes(_issues_for(row, frozen_clause, fixture_schema)) == [
        "reviewer_invalid"
    ]


def test_final_case_body_runs_schema_and_dsl_gates(
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]

    params_invalid = _reviewed(frozen_clause)
    del params_invalid["case_body"]["stimulus_steps"][0]["params"]["replay_key"]
    assert "reviewed_case_schema_invalid" in _codes(
        _issues_for(params_invalid, frozen_clause, fixture_schema)
    )

    semantic_invalid = _reviewed(frozen_clause)
    semantic_invalid["case_body"]["stimulus_steps"][0]["sequence"] = 2
    assert "stimulus_sequence_invalid" in _codes(
        _issues_for(semantic_invalid, frozen_clause, fixture_schema)
    )

    stricter_schema = copy.deepcopy(fixture_schema)
    stricter_schema["required"].append("future_required_field")
    assert "reviewed_case_schema_invalid" in _codes(
        _issues_for(_reviewed(frozen_clause), frozen_clause, stricter_schema)
    )


def test_reviewed_file_canonical_round_trip_and_reviewer_red_state(
    tmp_path: Path,
    frozen_inputs: Any,
    fixture_schema: dict[str, Any],
) -> None:
    frozen_clause = frozen_inputs.clauses_by_id["AC-001#1"]
    row = _reviewed(frozen_clause)
    first = canonical_bytes(row)
    first_hash = sha256_upper(first)
    path = tmp_path / "case-ac-001-1.json"
    path.write_bytes(first)

    reread = load_reviewed_case(path)
    assert reread == row
    assert canonical_bytes(reread) == first
    assert sha256_upper(canonical_bytes(reread)) == first_hash
    assert validate_reviewed_case(reread, frozen_clause, fixture_schema) == []

    changed = copy.deepcopy(row)
    changed["stimulus_mapping"]["mapping_note"] += "é"
    del changed["reviewer"]
    changed_bytes = canonical_bytes(changed)
    path.write_bytes(changed_bytes)
    changed_reread = load_reviewed_case(path)
    assert sha256_upper(changed_bytes) != first_hash
    assert _issues_for(changed_reread, frozen_clause, fixture_schema) == [
        ValidationIssue(
            "/reviewer",
            "reviewer_missing",
            "reviewer is required before a reviewed conversion can pass",
        )
    ]

    restored = copy.deepcopy(row)
    restored["reviewer"]["reviewer_id"] = "second-role-reviewer"
    path.write_bytes(canonical_bytes(restored))
    assert validate_reviewed_case(
        load_reviewed_case(path), frozen_clause, fixture_schema
    ) == []


def test_reviewed_loader_rejects_noncanonical_and_non_object(tmp_path: Path) -> None:
    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text('{"a": 1}\n', encoding="utf-8")
    with pytest.raises(FixtureInputError) as captured:
        load_reviewed_case(noncanonical)
    assert captured.value.code == "json_non_canonical"

    array = tmp_path / "array.json"
    array.write_bytes(canonical_bytes([]))
    with pytest.raises(FixtureInputError) as captured:
        load_reviewed_case(array)
    assert captured.value.code == "reviewed_json_object_required"


def test_batch_and_closed_set_keep_ordered_per_case_gates(
    frozen_inputs: Any,
    checklist: dict[str, Any],
    fixture_schema: dict[str, Any],
) -> None:
    clause_ids = ["AC-001#1", "AC-006#1"]
    checklist_rows = [
        next(row for row in checklist["cases"] if row["clause_id"] == clause_id)
        for clause_id in clause_ids
    ]
    frozen = {clause_id: frozen_inputs.clauses_by_id[clause_id] for clause_id in clause_ids}
    rows = [_reviewed(frozen[clause_id]) for clause_id in clause_ids]
    assert validate_reviewed_batch(rows, checklist_rows, frozen, fixture_schema) == []

    closed_checklist = copy.deepcopy(checklist)
    closed_checklist["cases"] = copy.deepcopy(checklist_rows)
    closed_checklist["clause_count"] = len(checklist_rows)
    assert validate_reviewed_closed_set(
        rows, closed_checklist, frozen, fixture_schema
    ) == []

    swapped = list(reversed(copy.deepcopy(rows)))
    issues = validate_reviewed_batch(swapped, checklist_rows, frozen, fixture_schema)
    assert "reviewed_batch_order_mismatch" in _codes(issues)
    assert "reviewed_frozen_identity_mismatch" in _codes(issues)

    reviewer_missing = copy.deepcopy(rows)
    del reviewer_missing[0]["reviewer"]
    issues = validate_reviewed_closed_set(
        reviewer_missing, closed_checklist, frozen, fixture_schema
    )
    assert _codes(issues) == ["reviewer_missing"]

    missing_context = dict(frozen)
    del missing_context[clause_ids[1]]
    issues = validate_reviewed_batch(rows, checklist_rows, missing_context, fixture_schema)
    assert "reviewed_frozen_clause_missing" in _codes(issues)
    assert not any(issue.json_pointer.startswith("/rows/0") for issue in issues)

    mapping_invalid_without_context = copy.deepcopy(rows)
    mapping_invalid_without_context[1]["stimulus_mapping"][
        "case_json_pointers"
    ] = []
    issues = validate_reviewed_batch(
        mapping_invalid_without_context,
        checklist_rows,
        missing_context,
        fixture_schema,
    )
    assert "reviewed_frozen_clause_missing" in _codes(issues)
    assert "stimulus_mapping_pointer_set_invalid" in _codes(issues)

    invalid_extra = copy.deepcopy(rows[0])
    del invalid_extra["reviewer"]
    issues = validate_reviewed_batch(
        [*rows, invalid_extra], checklist_rows, frozen, fixture_schema
    )
    assert "reviewed_batch_size_mismatch" in _codes(issues)
    assert any(
        issue.json_pointer == "/rows/2/reviewer"
        and issue.code == "reviewer_missing"
        for issue in issues
    )


def _batch_review_record(
    checklist_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    reviewer = {
        "role": "conversion_reviewer",
        "reviewer_id": "reviewer-b01",
        "reviewed_at": "2026-07-29",
    }
    reviewed_by_clause_id = {
        row["clause_id"]: {"reviewer": copy.deepcopy(reviewer)}
        for row in checklist_rows
    }
    record = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": "B01",
        "reviewed_commit": "a" * 40,
        "test_path": "tests/stage0c/reviewed_batches/test_batch_B01.py",
        "case_reviews": [
            {
                "ordinal": row["ordinal"],
                "batch_ordinal": row["batch_ordinal"],
                "clause_id": row["clause_id"],
                "case_path": row["reviewed_path"],
                "author_id": "author-b01",
                "reviewer_id": reviewer["reviewer_id"],
                "reviewed_at": reviewer["reviewed_at"],
            }
            for row in checklist_rows
        ],
    }
    return record, reviewed_by_clause_id


def test_batch_review_record_exact_schema_order_and_role_separation(
    checklist: dict[str, Any],
) -> None:
    checklist_rows = copy.deepcopy(checklist["cases"][:20])
    record, reviewed = _batch_review_record(checklist_rows)
    assert validate_batch_review_record(record, checklist_rows, reviewed) == []

    structural = copy.deepcopy(record)
    structural["extra"] = True
    assert _codes(
        validate_batch_review_record(structural, checklist_rows, reviewed)
    ) == ["batch_review_record_exact_fields_invalid"]

    reordered = copy.deepcopy(record)
    reordered["case_reviews"][0], reordered["case_reviews"][1] = (
        reordered["case_reviews"][1],
        reordered["case_reviews"][0],
    )
    assert "batch_review_case_order_invalid" in _codes(
        validate_batch_review_record(reordered, checklist_rows, reviewed)
    )

    same_role = copy.deepcopy(record)
    same_role["case_reviews"][0]["author_id"] = "reviewer-b01"
    assert "batch_review_role_separation_invalid" in _codes(
        validate_batch_review_record(same_role, checklist_rows, reviewed)
    )

    mirror_drift = copy.deepcopy(record)
    mirror_drift["case_reviews"][0]["reviewed_at"] = "2026-07-30"
    assert "batch_review_reviewer_mismatch" in _codes(
        validate_batch_review_record(mirror_drift, checklist_rows, reviewed)
    )

    bad_commit = copy.deepcopy(record)
    bad_commit["reviewed_commit"] = "A" * 40
    assert "batch_review_record_invalid" in _codes(
        validate_batch_review_record(bad_commit, checklist_rows, reviewed)
    )
