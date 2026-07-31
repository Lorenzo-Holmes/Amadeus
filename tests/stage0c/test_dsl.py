import builtins
import copy
from dataclasses import fields
import hashlib
import io
import itertools
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from tools.stage0c_fixtures.constants import SCHEMA_VERSION
from tools.stage0c_fixtures.dsl import (
    canonical_oracle_kinds,
    case_filename_for_clause_id,
    case_id_for_clause_id,
    resolve_json_pointer,
    validate_case_body,
)
from tools.stage0c_fixtures.io import canonical_bytes, load_strict_json_bytes
from tools.stage0c_fixtures.types import FixtureInputError, ValidationIssue


_CASE_FIELDS = {
    "schema_version",
    "case_id",
    "source_id",
    "source_clause_id",
    "oracle_kinds",
    "setup_steps",
    "stimulus_steps",
    "machine_assertions",
    "rubric_requirements",
    "sandbox_profile",
}
_SETUP_OR_STIMULUS_FIELDS = {"sequence", "step_id", "handler_id", "params"}
_ASSERTION_FIELDS = {
    "sequence",
    "assertion_id",
    "handler_id",
    "step_id",
    "params",
}
_RUBRIC_FIELDS = {
    "criterion_id",
    "oracle_kind",
    "question",
    "evidence_case_json_pointers",
    "allowed_scores",
    "passing_scores",
}
_SANDBOX_FIELDS = {
    "profile_id",
    "allowed_effects",
    "fixed_clock",
    "id_seed",
    "reset_policy",
    "cleanup_policy",
}
_SETUP_HANDLERS = (
    "sandbox.seed_state",
    "sandbox.set_clock",
    "sandbox.configure_core_driver",
    "sandbox.configure_adapter",
    "sandbox.seed_backend_response",
)
_STIMULUS_HANDLERS = (
    "core.command",
    "core.query",
    "external.action",
    "backend.replay",
)
_ASSERTION_HANDLERS = (
    "receipt.status",
    "receipt.error_code",
    "state.path_equals",
    "state.hash_unchanged",
    "effect.includes",
    "effect.excludes",
    "output.contains",
    "output.omits",
    "replay.equals",
)
_EXPECTED_ISSUE_CODES = frozenset(
    {
        "assertion_exact_fields_invalid",
        "assertion_sequence_invalid",
        "assertion_step_reference_invalid",
        "case_exact_fields_invalid",
        "case_handler_invalid",
        "case_identifier_duplicate",
        "case_identifier_invalid",
        "case_identity_invalid",
        "case_json_value_invalid",
        "case_oracle_coverage_invalid",
        "case_oracle_kinds_invalid",
        "case_schema_version_invalid",
        "case_step_collection_invalid",
        "rubric_allowed_scores_invalid",
        "rubric_evidence_pointer_invalid",
        "rubric_exact_fields_invalid",
        "rubric_oracle_kind_invalid",
        "rubric_order_invalid",
        "rubric_passing_scores_invalid",
        "rubric_question_invalid",
        "sandbox_allowed_effects_invalid",
        "sandbox_cleanup_policy_invalid",
        "sandbox_effect_rule_invalid",
        "sandbox_profile_exact_fields_invalid",
        "sandbox_profile_forbidden",
        "sandbox_profile_invalid",
        "sandbox_profile_required",
        "sandbox_reset_policy_invalid",
        "setup_sequence_invalid",
        "step_exact_fields_invalid",
        "stimulus_sequence_invalid",
    }
)
_EXPECTED_ISSUE_MESSAGES = {
    "assertion_exact_fields_invalid": (
        "machine assertion fields must match the DSL exactly"
    ),
    "assertion_sequence_invalid": (
        "machine assertion sequence values must be contiguous integers "
        "starting at 1"
    ),
    "assertion_step_reference_invalid": (
        "assertion step_id must target a declared stimulus step"
    ),
    "case_exact_fields_invalid": "case fields must match the DSL exactly",
    "case_handler_invalid": (
        "handler_id must be allowed for its containing collection"
    ),
    "case_identifier_duplicate": (
        "declaration identifiers must be unique across the case"
    ),
    "case_identifier_invalid": (
        "declaration identifiers must match ^[a-z][a-z0-9-]*$"
    ),
    "case_identity_invalid": (
        "case_id, source_id, and source_clause_id are inconsistent"
    ),
    "case_json_value_invalid": (
        "case value is outside the canonical JSON domain"
    ),
    "case_oracle_coverage_invalid": (
        "declared oracle kinds must have matching assertion or rubric coverage"
    ),
    "case_oracle_kinds_invalid": (
        "oracle_kinds must be a non-empty unique list ordered D, S, H, J"
    ),
    "case_schema_version_invalid": (
        f"schema_version must equal {SCHEMA_VERSION!r}"
    ),
    "case_step_collection_invalid": (
        "setup_steps, stimulus_steps, and machine_assertions must be arrays"
    ),
    "rubric_allowed_scores_invalid": (
        "rubric allowed_scores must be a non-empty unique ascending integer list"
    ),
    "rubric_evidence_pointer_invalid": (
        "rubric evidence pointers must be a non-empty unique ordered list "
        "resolving in the case"
    ),
    "rubric_exact_fields_invalid": (
        "rubric requirement fields must match the DSL exactly"
    ),
    "rubric_oracle_kind_invalid": (
        "rubric oracle_kind must be declared and equal H or J"
    ),
    "rubric_order_invalid": (
        "rubric requirements must be ordered by criterion_id"
    ),
    "rubric_passing_scores_invalid": (
        "rubric passing_scores must be a valid subset of allowed_scores"
    ),
    "rubric_question_invalid": "rubric question must be a string",
    "sandbox_allowed_effects_invalid": (
        "allowed_effects must be an array with unique valid effect rules"
    ),
    "sandbox_cleanup_policy_invalid": (
        "sandbox cleanup_policy must equal 'always'"
    ),
    "sandbox_effect_rule_invalid": (
        "effect rules must exactly contain a supported adapter_id and string "
        "operation and target"
    ),
    "sandbox_profile_exact_fields_invalid": (
        "sandbox profile fields must match the DSL exactly"
    ),
    "sandbox_profile_forbidden": (
        "sandbox_profile must be null when oracle S is absent"
    ),
    "sandbox_profile_invalid": (
        "sandbox profile scalar fields must have valid types and values"
    ),
    "sandbox_profile_required": (
        "sandbox_profile is required when oracle S is declared"
    ),
    "sandbox_reset_policy_invalid": (
        "sandbox reset_policy must equal 'fresh_context'"
    ),
    "setup_sequence_invalid": (
        "setup sequence values must be contiguous integers starting at 1"
    ),
    "step_exact_fields_invalid": (
        "setup and stimulus step fields must match the DSL exactly"
    ),
    "stimulus_sequence_invalid": (
        "stimulus sequence values must be contiguous integers starting at 1"
    ),
}


def _identity(source_clause_id: str) -> tuple[str, str]:
    case_id = f"case-{source_clause_id.lower().replace('#', '-')}"
    return case_id, f"{case_id}.json"


def _setup_step(
    sequence: int,
    step_id: str,
    replay_key: str,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "step_id": step_id,
        "handler_id": "sandbox.seed_backend_response",
        "params": {
            "replay_key": replay_key,
            "output": {"status": "fixture-output", "sequence": sequence},
        },
    }


def _stimulus_step(
    sequence: int,
    step_id: str,
    replay_key: str,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "step_id": step_id,
        "handler_id": "backend.replay",
        "params": {"replay_key": replay_key, "input": {}},
    }


def _machine_assertion(
    sequence: int,
    assertion_id: str,
    step_id: str,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "assertion_id": assertion_id,
        "handler_id": "receipt.status",
        "step_id": step_id,
        "params": {"expected": "completed"},
    }


def _rubric(criterion_id: str, oracle_kind: str) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "oracle_kind": oracle_kind,
        "question": f"Does the fixture provide {oracle_kind} evidence?",
        "evidence_case_json_pointers": [
            "/stimulus_steps/0/params",
            "/stimulus_steps/0/step_id",
        ],
        "allowed_scores": [-1, 0, 1],
        "passing_scores": [1],
    }


def _sandbox_profile(*, allowed_effects: list[dict[str, Any]] | None = None):
    return {
        "profile_id": "sandbox-stage0c",
        "allowed_effects": [] if allowed_effects is None else allowed_effects,
        "fixed_clock": "2026-01-01T00:00:00Z",
        "id_seed": "stage0c-seed",
        "reset_policy": "fresh_context",
        "cleanup_policy": "always",
    }


def _golden_d() -> dict[str, Any]:
    case_id = _identity("AC-001#1")[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "source_id": "AC-001",
        "source_clause_id": "AC-001#1",
        "oracle_kinds": ["D"],
        "setup_steps": [_setup_step(1, "seed-backend", "replay-ac-001")],
        "stimulus_steps": [
            _stimulus_step(1, "replay-backend", "replay-ac-001")
        ],
        "machine_assertions": [
            _machine_assertion(1, "assert-status", "replay-backend")
        ],
        "rubric_requirements": [],
        "sandbox_profile": None,
    }


def _golden_s() -> dict[str, Any]:
    case_id = _identity("AC-006#1")[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "source_id": "AC-006",
        "source_clause_id": "AC-006#1",
        "oracle_kinds": ["D", "S"],
        "setup_steps": [_setup_step(1, "seed-backend", "replay-ac-006")],
        "stimulus_steps": [
            _stimulus_step(1, "replay-backend", "replay-ac-006")
        ],
        "machine_assertions": [
            _machine_assertion(1, "assert-status", "replay-backend")
        ],
        "rubric_requirements": [],
        "sandbox_profile": _sandbox_profile(),
    }


def _golden_hj() -> dict[str, Any]:
    case_id = _identity("INJ-09#1")[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "source_id": "INJ-09",
        "source_clause_id": "INJ-09#1",
        "oracle_kinds": ["H", "J"],
        "setup_steps": [_setup_step(1, "seed-backend", "replay-inj-09")],
        "stimulus_steps": [
            _stimulus_step(1, "replay-backend", "replay-inj-09")
        ],
        "machine_assertions": [],
        "rubric_requirements": [
            _rubric("criterion-h", "H"),
            _rubric("criterion-j", "J"),
        ],
        "sandbox_profile": None,
    }


def _sequence_case() -> dict[str, Any]:
    body = _golden_d()
    body["setup_steps"].append(_setup_step(2, "seed-second", "replay-second"))
    body["stimulus_steps"].append(
        _stimulus_step(2, "replay-second", "replay-second")
    )
    body["machine_assertions"].append(
        _machine_assertion(2, "assert-second", "replay-second")
    )
    return body


def _namespace_case() -> dict[str, Any]:
    body = _sequence_case()
    body["oracle_kinds"] = ["D", "H", "J"]
    body["rubric_requirements"] = [
        _rubric("criterion-h", "H"),
        _rubric("criterion-j", "J"),
    ]
    return body


def _self_referential_list() -> list[Any]:
    value: list[Any] = []
    value.append(value)
    return value


def _mutual_dict_list_cycle() -> dict[str, Any]:
    value: dict[str, Any] = {}
    nested = [value]
    value["loop"] = nested
    return value


def _deeply_nested_list() -> list[Any]:
    root: list[Any] = []
    cursor = root
    for _index in range(6000):
        child: list[Any] = []
        cursor.append(child)
        cursor = child
    return root


def _assert_issue_messages(issues: list[ValidationIssue]) -> None:
    for issue in issues:
        assert issue.code in _EXPECTED_ISSUE_MESSAGES
        assert issue.message == _EXPECTED_ISSUE_MESSAGES[issue.code]


def _assert_single_issue(
    body: Any,
    expected_code: str,
    expected_pointer: str,
) -> ValidationIssue:
    issues = validate_case_body(body)
    assert type(issues) is list
    assert len(issues) == 1
    issue = issues[0]
    assert type(issue) is ValidationIssue
    assert tuple(field.name for field in fields(issue)) == (
        "json_pointer",
        "code",
        "message",
    )
    assert issue.code == expected_code
    assert issue.json_pointer == expected_pointer
    _assert_issue_messages(issues)
    return issue


def _assert_stable_single_issue(
    body: Any,
    expected_code: str,
    expected_pointer: str,
) -> ValidationIssue:
    first = _assert_single_issue(body, expected_code, expected_pointer)
    second = validate_case_body(body)
    assert type(second) is list
    assert len(second) == 1
    assert second == [first]
    return first


def _assert_api_error(call: Callable[[], Any], expected_code: str) -> None:
    with pytest.raises(FixtureInputError) as captured:
        call()
    assert captured.value.code == expected_code


def test_expected_issue_messages_cover_complete_validation_code_matrix() -> None:
    assert frozenset(_EXPECTED_ISSUE_MESSAGES) == _EXPECTED_ISSUE_CODES
    assert len(_EXPECTED_ISSUE_CODES) == 31
    messages = tuple(_EXPECTED_ISSUE_MESSAGES.values())
    assert all(type(message) is str and message.strip() for message in messages)
    assert len(set(messages)) == len(messages)


@pytest.mark.parametrize(
    ("clause_id", "case_id", "filename"),
    [
        ("AC-001#1", "case-ac-001-1", "case-ac-001-1.json"),
        ("AC-066#6", "case-ac-066-6", "case-ac-066-6.json"),
        ("BR-03#2", "case-br-03-2", "case-br-03-2.json"),
        (
            "CORE-MEM-001#12",
            "case-core-mem-001-12",
            "case-core-mem-001-12.json",
        ),
        ("USE-05#1", "case-use-05-1", "case-use-05-1.json"),
    ],
)
def test_case_identity_literals(
    clause_id: str,
    case_id: str,
    filename: str,
) -> None:
    assert case_id_for_clause_id(clause_id) == case_id
    assert case_filename_for_clause_id(clause_id) == filename


def test_all_frozen_case_identities_and_filenames_are_unique(
    frozen_inputs: Any,
) -> None:
    clause_ids = tuple(frozen_inputs.clauses_by_id)
    case_ids = [case_id_for_clause_id(clause_id) for clause_id in clause_ids]
    filenames = [
        case_filename_for_clause_id(clause_id) for clause_id in clause_ids
    ]
    assert len(clause_ids) == 259
    assert len(case_ids) == len(set(case_ids)) == 259
    assert len(filenames) == len(set(filenames)) == 259
    for clause_id, case_id, filename in zip(
        clause_ids,
        case_ids,
        filenames,
        strict=True,
    ):
        expected_case_id, expected_filename = _identity(clause_id)
        assert case_id == expected_case_id
        assert filename == expected_filename


@pytest.mark.parametrize(
    "invalid_clause_id",
    [
        None,
        1,
        "ac-001#1",
        "AC-001",
        "AC-001#0",
        "AC-001#01",
        "AC-001#1#2",
        "AC--001#1",
        "AC_001#1",
        "ÄC-001#1",
    ],
)
def test_case_identity_helpers_reject_invalid_clause_grammar(
    invalid_clause_id: Any,
) -> None:
    _assert_api_error(
        lambda: case_id_for_clause_id(invalid_clause_id),
        "case_identity_invalid",
    )
    _assert_api_error(
        lambda: case_filename_for_clause_id(invalid_clause_id),
        "case_identity_invalid",
    )


@pytest.mark.parametrize("golden_factory", [_golden_d, _golden_s, _golden_hj])
def test_three_future_compatible_golden_cases_validate(
    golden_factory: Callable[[], dict[str, Any]],
) -> None:
    body = golden_factory()
    assert set(body) == _CASE_FIELDS
    assert validate_case_body(body) == []


@pytest.mark.parametrize("missing_field", sorted(_CASE_FIELDS))
def test_case_top_level_missing_field_is_rejected(missing_field: str) -> None:
    body = _golden_d()
    del body[missing_field]
    _assert_single_issue(body, "case_exact_fields_invalid", "")


def test_case_top_level_extra_field_is_rejected() -> None:
    body = _golden_d()
    body["extra"] = None
    _assert_single_issue(body, "case_exact_fields_invalid", "")


@pytest.mark.parametrize("body", [None, [], "case"])
def test_case_top_level_must_be_an_object(body: Any) -> None:
    _assert_single_issue(body, "case_exact_fields_invalid", "")


def test_structural_parent_errors_suppress_descendant_issues() -> None:
    top = _golden_d()
    del top["sandbox_profile"]
    top["setup_steps"][0]["sequence"] = 0
    _assert_single_issue(top, "case_exact_fields_invalid", "")

    step = _golden_d()
    step["setup_steps"][0]["extra"] = None
    step["setup_steps"][0]["sequence"] = 0
    _assert_single_issue(
        step,
        "step_exact_fields_invalid",
        "/setup_steps/0",
    )

    rubric = _golden_hj()
    rubric["rubric_requirements"][0]["extra"] = None
    rubric["rubric_requirements"][0]["allowed_scores"] = []
    _assert_single_issue(
        rubric,
        "rubric_exact_fields_invalid",
        "/rubric_requirements/0",
    )

    sandbox = _golden_s()
    sandbox["sandbox_profile"]["extra"] = None
    sandbox["sandbox_profile"]["reset_policy"] = "reuse_context"
    _assert_single_issue(
        sandbox,
        "sandbox_profile_exact_fields_invalid",
        "/sandbox_profile",
    )


def test_case_schema_version_is_exact() -> None:
    body = _golden_d()
    body["schema_version"] = "0.2"
    _assert_single_issue(
        body,
        "case_schema_version_invalid",
        "/schema_version",
    )


@pytest.mark.parametrize(
    ("field", "value", "pointer"),
    [
        ("case_id", "case-ac-001-2", "/case_id"),
        ("source_id", "AC-002", "/source_id"),
        ("source_clause_id", "AC-001#0", "/source_clause_id"),
    ],
)
def test_case_body_identity_is_relationally_exact(
    field: str,
    value: str,
    pointer: str,
) -> None:
    body = _golden_d()
    body[field] = value
    _assert_single_issue(body, "case_identity_invalid", pointer)


def test_case_rejects_non_json_values_recursively() -> None:
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = 1.5
    _assert_single_issue(
        body,
        "case_json_value_invalid",
        "/setup_steps/0/params/output",
    )


@pytest.mark.parametrize(
    ("value", "expected_pointer"),
    [
        pytest.param("\ud800", "/setup_steps/0/params/output", id="lone-surrogate"),
        pytest.param(
            {1: "non-string-key"},
            "/setup_steps/0/params/output",
            id="non-string-dict-key",
        ),
        pytest.param(
            b"bytes",
            "/setup_steps/0/params/output",
            id="bytes",
        ),
        pytest.param(
            ("tuple",),
            "/setup_steps/0/params/output",
            id="tuple",
        ),
    ],
)
def test_case_json_domain_reports_nested_parent_pointer(
    value: Any,
    expected_pointer: str,
) -> None:
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = value
    _assert_stable_single_issue(
        body,
        "case_json_value_invalid",
        expected_pointer,
    )


def test_case_json_domain_chooses_unicode_minimum_leaf_independent_of_map_order(
) -> None:
    first = _golden_d()
    first["setup_steps"][0]["params"]["output"] = {
        "nested": {"\u00e9": 1.5, "z": 2.5}
    }
    second = _golden_d()
    second["setup_steps"][0]["params"]["output"] = {
        "nested": {"z": 2.5, "\u00e9": 1.5}
    }
    assert first == second

    first_issues = validate_case_body(first)
    second_issues = validate_case_body(second)
    _assert_issue_messages(first_issues)
    _assert_issue_messages(second_issues)
    assert first_issues == second_issues
    assert len(first_issues) == 1
    assert first_issues[0].code == "case_json_value_invalid"
    assert first_issues[0].json_pointer == (
        "/setup_steps/0/params/output/nested/z"
    )


@pytest.mark.parametrize(
    ("factory", "expected_pointer"),
    [
        pytest.param(
            _self_referential_list,
            "/setup_steps/0/params/output/0",
            id="self-list-cycle",
        ),
        pytest.param(
            _mutual_dict_list_cycle,
            "/setup_steps/0/params/output/loop/0",
            id="mutual-dict-list-cycle",
        ),
    ],
)
def test_case_json_domain_reports_first_cycle_reentry_stably(
    factory: Callable[[], Any],
    expected_pointer: str,
) -> None:
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = factory()
    _assert_stable_single_issue(
        body,
        "case_json_value_invalid",
        expected_pointer,
    )


def test_case_json_domain_accepts_shared_acyclic_aliases() -> None:
    shared = {"value": [1, 2, 3]}
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = {
        "first": shared,
        "second": shared,
    }
    assert validate_case_body(body) == []


def test_case_json_domain_error_pointer_uses_rfc6901_escaping() -> None:
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = {
        "a/b": {"~key": 1.5}
    }
    _assert_stable_single_issue(
        body,
        "case_json_value_invalid",
        "/setup_steps/0/params/output/a~1b/~0key",
    )


def test_case_json_domain_handles_six_thousand_levels_stably() -> None:
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = _deeply_nested_list()
    first = validate_case_body(body)
    second = validate_case_body(body)
    for issues in (first, second):
        assert type(issues) is list
        assert len(issues) == 1
        assert type(issues[0]) is ValidationIssue
        assert issues[0].code == "case_json_value_invalid"
        _assert_issue_messages(issues)
    assert second == first


def test_case_json_domain_accepts_serializable_three_hundred_level_list() -> None:
    nested: list[Any] = []
    for _index in range(300):
        nested = [nested]
    body = _golden_d()
    body["setup_steps"][0]["params"]["output"] = nested

    encoded = canonical_bytes(body)
    assert type(encoded) is bytes
    assert encoded
    assert validate_case_body(body) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["D"], ["D"]),
        (["J", "D"], ["D", "J"]),
        (["H", "S", "D"], ["D", "S", "H"]),
        (["J", "H", "S", "D"], ["D", "S", "H", "J"]),
    ],
)
def test_canonical_oracle_kinds_returns_a_new_ordered_list(
    value: list[str],
    expected: list[str],
) -> None:
    before = list(value)
    result = canonical_oracle_kinds(value)
    assert result == expected
    assert type(result) is list
    assert result is not value
    assert value == before


@pytest.mark.parametrize(
    "invalid",
    [None, {}, [], ["D", "D"], ["X"], [1], [True]],
)
def test_canonical_oracle_kinds_is_strict(invalid: Any) -> None:
    _assert_api_error(
        lambda: canonical_oracle_kinds(invalid),
        "case_oracle_kinds_invalid",
    )


@pytest.mark.parametrize(
    "invalid",
    [None, {}, [], ["D", "D"], ["X"], [1], [True], ["S", "D"]],
)
def test_case_oracle_kinds_must_already_be_canonical(invalid: Any) -> None:
    body = _golden_d()
    body["oracle_kinds"] = invalid
    _assert_single_issue(
        body,
        "case_oracle_kinds_invalid",
        "/oracle_kinds",
    )


@pytest.mark.parametrize(
    "collection",
    ["setup_steps", "stimulus_steps", "machine_assertions"],
)
@pytest.mark.parametrize("invalid", [None, {}])
def test_step_collections_must_be_arrays(collection: str, invalid: Any) -> None:
    body = _golden_d()
    body[collection] = invalid
    _assert_single_issue(
        body,
        "case_step_collection_invalid",
        f"/{collection}",
    )


@pytest.mark.parametrize("collection", ["setup_steps", "stimulus_steps"])
@pytest.mark.parametrize("mutation", ["missing", "extra", "non-object"])
def test_step_rows_have_exact_fields(collection: str, mutation: str) -> None:
    body = _golden_d()
    row = body[collection][0]
    assert set(row) == _SETUP_OR_STIMULUS_FIELDS
    if mutation == "missing":
        del row["params"]
    elif mutation == "extra":
        row["extra"] = None
    else:
        body[collection][0] = None
    _assert_single_issue(
        body,
        "step_exact_fields_invalid",
        f"/{collection}/0",
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "non-object"])
def test_machine_assertions_have_exact_fields(mutation: str) -> None:
    body = _golden_d()
    row = body["machine_assertions"][0]
    assert set(row) == _ASSERTION_FIELDS
    if mutation == "missing":
        del row["params"]
    elif mutation == "extra":
        row["extra"] = None
    else:
        body["machine_assertions"][0] = None
    _assert_single_issue(
        body,
        "assertion_exact_fields_invalid",
        "/machine_assertions/0",
    )


@pytest.mark.parametrize("collection", ["setup_steps", "stimulus_steps"])
def test_step_params_must_be_an_object_without_deep_f05_validation(
    collection: str,
) -> None:
    invalid = _golden_d()
    invalid[collection][0]["params"] = []
    _assert_single_issue(
        invalid,
        "step_exact_fields_invalid",
        f"/{collection}/0",
    )

    deferred = _golden_d()
    deferred[collection][0]["params"] = {}
    assert validate_case_body(deferred) == []


def test_assertion_params_must_be_an_object_without_deep_f05_validation() -> None:
    invalid = _golden_d()
    invalid["machine_assertions"][0]["params"] = []
    _assert_single_issue(
        invalid,
        "assertion_exact_fields_invalid",
        "/machine_assertions/0",
    )

    deferred = _golden_d()
    deferred["machine_assertions"][0]["params"] = {}
    assert validate_case_body(deferred) == []


@pytest.mark.parametrize(
    ("collection", "invalid_handler"),
    [
        ("setup_steps", "core.command"),
        ("setup_steps", "unknown.handler"),
        ("setup_steps", None),
        ("stimulus_steps", "sandbox.seed_state"),
        ("stimulus_steps", "unknown.handler"),
        ("stimulus_steps", None),
    ],
)
def test_setup_and_stimulus_handler_kind_is_static(
    collection: str,
    invalid_handler: Any,
) -> None:
    body = _golden_d()
    body[collection][0]["handler_id"] = invalid_handler
    _assert_single_issue(
        body,
        "case_handler_invalid",
        f"/{collection}/0/handler_id",
    )


@pytest.mark.parametrize(
    "invalid_handler",
    ["backend.replay", "unknown.handler", None],
)
def test_assertion_handler_kind_is_static(invalid_handler: Any) -> None:
    body = _golden_d()
    body["machine_assertions"][0]["handler_id"] = invalid_handler
    _assert_single_issue(
        body,
        "case_handler_invalid",
        "/machine_assertions/0/handler_id",
    )


@pytest.mark.parametrize(
    ("collection", "handler_id"),
    [
        *(("setup_steps", handler_id) for handler_id in _SETUP_HANDLERS),
        *(("stimulus_steps", handler_id) for handler_id in _STIMULUS_HANDLERS),
    ],
)
def test_every_setup_and_stimulus_handler_enum_is_recognized(
    collection: str,
    handler_id: str,
) -> None:
    body = _golden_d()
    body[collection][0]["handler_id"] = handler_id
    body[collection][0]["params"] = {}
    issues = validate_case_body(body)
    _assert_issue_messages(issues)
    assert all(issue.code != "case_handler_invalid" for issue in issues)


@pytest.mark.parametrize("handler_id", _ASSERTION_HANDLERS)
def test_every_assertion_handler_enum_is_recognized(
    handler_id: str,
) -> None:
    body = _golden_d()
    body["machine_assertions"][0]["handler_id"] = handler_id
    body["machine_assertions"][0]["params"] = {}
    issues = validate_case_body(body)
    _assert_issue_messages(issues)
    assert all(issue.code != "case_handler_invalid" for issue in issues)


_SEQUENCE_CODES = {
    "setup_steps": "setup_sequence_invalid",
    "stimulus_steps": "stimulus_sequence_invalid",
    "machine_assertions": "assertion_sequence_invalid",
}


@pytest.mark.parametrize("collection", tuple(_SEQUENCE_CODES))
@pytest.mark.parametrize("mutation", ["zero", "gap", "unordered", "bool"])
def test_step_sequences_are_positive_contiguous_and_stored_in_order(
    collection: str,
    mutation: str,
) -> None:
    body = _sequence_case()
    rows = body[collection]
    if mutation == "zero":
        rows[0]["sequence"] = 0
    elif mutation == "gap":
        rows[1]["sequence"] = 3
    elif mutation == "unordered":
        rows[0], rows[1] = rows[1], rows[0]
    else:
        rows[0]["sequence"] = True
    _assert_single_issue(body, _SEQUENCE_CODES[collection], f"/{collection}")


_DECLARATIONS = (
    ("setup_steps", 0, "step_id"),
    ("setup_steps", 1, "step_id"),
    ("stimulus_steps", 0, "step_id"),
    ("stimulus_steps", 1, "step_id"),
    ("machine_assertions", 0, "assertion_id"),
    ("machine_assertions", 1, "assertion_id"),
    ("rubric_requirements", 0, "criterion_id"),
    ("rubric_requirements", 1, "criterion_id"),
)
_DECLARATION_COLLISIONS = tuple(
    itertools.combinations(range(len(_DECLARATIONS)), 2)
)


@pytest.mark.parametrize("declaration_index", (0, 2, 4, 6))
@pytest.mark.parametrize(
    "invalid",
    ["", "0bad", "Bad_ID", "-bad", "bad_id", None],
)
def test_all_declaration_kinds_share_identifier_grammar(
    declaration_index: int,
    invalid: Any,
) -> None:
    body = _namespace_case()
    collection, index, field = _DECLARATIONS[declaration_index]
    body[collection][index][field] = invalid
    _assert_single_issue(
        body,
        "case_identifier_invalid",
        f"/{collection}/{index}/{field}",
    )


@pytest.mark.parametrize("valid", ["a", "a0", "a-", "a-b9"])
def test_declaration_identifier_grammar_accepts_design_regex(
    valid: str,
) -> None:
    body = _namespace_case()
    body["setup_steps"][0]["step_id"] = valid
    assert validate_case_body(body) == []


@pytest.mark.parametrize(
    ("source_index", "target_index"),
    _DECLARATION_COLLISIONS,
)
def test_all_declarations_share_one_unique_id_namespace(
    source_index: int,
    target_index: int,
) -> None:
    body = _namespace_case()
    source_collection, source_row, source_field = _DECLARATIONS[source_index]
    target_collection, target_row, target_field = _DECLARATIONS[target_index]
    body[target_collection][target_row][target_field] = body[source_collection][
        source_row
    ][source_field]
    _assert_single_issue(
        body,
        "case_identifier_duplicate",
        f"/{target_collection}/{target_row}/{target_field}",
    )


@pytest.mark.parametrize("bad_reference", ["missing-step", "seed-backend"])
def test_assertion_step_reference_must_resolve_to_stimulus(
    bad_reference: str,
) -> None:
    body = _golden_d()
    body["machine_assertions"][0]["step_id"] = bad_reference
    _assert_single_issue(
        body,
        "assertion_step_reference_invalid",
        "/machine_assertions/0/step_id",
    )


def test_identifier_failures_do_not_suppress_independent_dependency_gates() -> None:
    missing_reference = _golden_d()
    missing_reference["setup_steps"][0]["step_id"] = ""
    missing_reference["machine_assertions"][0]["step_id"] = "missing-step"

    reversed_rubric = _namespace_case()
    reversed_rubric["setup_steps"][0]["step_id"] = ""
    reversed_rubric["rubric_requirements"].reverse()

    validated = [
        validate_case_body(body)
        for body in (missing_reference, reversed_rubric)
    ]
    for issues in validated:
        _assert_issue_messages(issues)
    observed = [
        [
            (issue.code, issue.json_pointer)
            for issue in issues
        ]
        for issues in validated
    ]
    assert observed == [
        [
            (
                "assertion_step_reference_invalid",
                "/machine_assertions/0/step_id",
            ),
            ("case_identifier_invalid", "/setup_steps/0/step_id"),
        ],
        [
            ("rubric_order_invalid", "/rubric_requirements"),
            ("case_identifier_invalid", "/setup_steps/0/step_id"),
        ],
    ]


@pytest.mark.parametrize("invalid", [None, {}, "rubric", True])
def test_rubric_collection_must_be_an_array(invalid: Any) -> None:
    body = _golden_hj()
    body["rubric_requirements"] = invalid
    _assert_single_issue(
        body,
        "rubric_exact_fields_invalid",
        "/rubric_requirements",
    )


def test_empty_rubric_array_reaches_oracle_coverage_gate() -> None:
    body = _golden_hj()
    body["rubric_requirements"] = []
    _assert_single_issue(
        body,
        "case_oracle_coverage_invalid",
        "/rubric_requirements",
    )


@pytest.mark.parametrize("missing_field", sorted(_RUBRIC_FIELDS))
def test_rubric_missing_field_is_rejected(missing_field: str) -> None:
    body = _golden_hj()
    del body["rubric_requirements"][0][missing_field]
    _assert_single_issue(
        body,
        "rubric_exact_fields_invalid",
        "/rubric_requirements/0",
    )


def test_rubric_extra_verdict_is_rejected() -> None:
    body = _golden_hj()
    body["rubric_requirements"][0]["verdict"] = "pass"
    _assert_single_issue(
        body,
        "rubric_exact_fields_invalid",
        "/rubric_requirements/0",
    )


@pytest.mark.parametrize(
    "invalid",
    [[], [-1, -1], [-1, True], [-1, "0"], [0, -1]],
)
def test_rubric_allowed_scores_leaf_gate(invalid: Any) -> None:
    body = _golden_hj()
    body["rubric_requirements"][0]["allowed_scores"] = invalid
    _assert_single_issue(
        body,
        "rubric_allowed_scores_invalid",
        "/rubric_requirements/0/allowed_scores",
    )


@pytest.mark.parametrize("invalid", [[], [1, 1], [1, 0], [2], [True]])
def test_rubric_passing_scores_leaf_gate(invalid: Any) -> None:
    body = _golden_hj()
    body["rubric_requirements"][0]["passing_scores"] = invalid
    _assert_single_issue(
        body,
        "rubric_passing_scores_invalid",
        "/rubric_requirements/0/passing_scores",
    )


@pytest.mark.parametrize(
    "invalid",
    [
        [],
        ["/stimulus_steps/0", "/stimulus_steps/0"],
        ["/stimulus_steps/0/step_id", "/stimulus_steps/0/params"],
        ["not-a-pointer"],
        ["/stimulus_steps/~2"],
        ["/stimulus_steps/99"],
    ],
)
def test_rubric_evidence_pointer_leaf_gate(invalid: Any) -> None:
    body = _golden_hj()
    body["rubric_requirements"][0]["evidence_case_json_pointers"] = invalid
    _assert_single_issue(
        body,
        "rubric_evidence_pointer_invalid",
        "/rubric_requirements/0/evidence_case_json_pointers",
    )


def test_rubric_evidence_pointer_order_uses_unicode_code_points() -> None:
    valid = _golden_hj()
    valid["stimulus_steps"][0]["params"]["input"] = {"z": 1, "é": 2}
    valid["rubric_requirements"][0]["evidence_case_json_pointers"] = [
        "/stimulus_steps/0/params/input/z",
        "/stimulus_steps/0/params/input/é",
    ]
    assert validate_case_body(valid) == []

    invalid = copy.deepcopy(valid)
    invalid["rubric_requirements"][0][
        "evidence_case_json_pointers"
    ].reverse()
    _assert_single_issue(
        invalid,
        "rubric_evidence_pointer_invalid",
        "/rubric_requirements/0/evidence_case_json_pointers",
    )


@pytest.mark.parametrize("invalid_question", [None, True])
def test_rubric_question_requires_only_string_type(
    invalid_question: Any,
) -> None:
    valid = _golden_hj()
    valid["rubric_requirements"][0]["question"] = ""
    assert validate_case_body(valid) == []

    invalid = _golden_hj()
    invalid["rubric_requirements"][0]["question"] = invalid_question
    _assert_single_issue(
        invalid,
        "rubric_question_invalid",
        "/rubric_requirements/0/question",
    )


def test_rubric_oracle_kind_must_be_h_or_j_and_declared() -> None:
    invalid_kind = _golden_hj()
    invalid_kind["rubric_requirements"][0]["oracle_kind"] = "D"
    _assert_single_issue(
        invalid_kind,
        "rubric_oracle_kind_invalid",
        "/rubric_requirements/0/oracle_kind",
    )

    undeclared_kind = _golden_hj()
    undeclared_kind["oracle_kinds"] = ["H"]
    _assert_single_issue(
        undeclared_kind,
        "rubric_oracle_kind_invalid",
        "/rubric_requirements/1/oracle_kind",
    )


def test_rubric_order_is_unicode_lexical_not_numeric() -> None:
    valid = _golden_hj()
    valid["rubric_requirements"][0]["criterion_id"] = "criterion-10"
    valid["rubric_requirements"][1]["criterion_id"] = "criterion-2"
    assert validate_case_body(valid) == []

    invalid = copy.deepcopy(valid)
    invalid["rubric_requirements"].reverse()
    _assert_single_issue(
        invalid,
        "rubric_order_invalid",
        "/rubric_requirements",
    )


@pytest.mark.parametrize("golden_factory", [_golden_d, _golden_s])
def test_d_and_s_oracles_require_machine_assertion_coverage(
    golden_factory: Callable[[], dict[str, Any]],
) -> None:
    body = golden_factory()
    body["machine_assertions"] = []
    _assert_single_issue(
        body,
        "case_oracle_coverage_invalid",
        "/machine_assertions",
    )


def test_h_and_j_oracles_require_matching_rubric_coverage() -> None:
    body = _golden_hj()
    body["rubric_requirements"].pop()
    _assert_single_issue(
        body,
        "case_oracle_coverage_invalid",
        "/rubric_requirements",
    )


def test_s_case_requires_sandbox_profile() -> None:
    body = _golden_s()
    body["sandbox_profile"] = None
    _assert_single_issue(
        body,
        "sandbox_profile_required",
        "/sandbox_profile",
    )


@pytest.mark.parametrize("invalid_profile", ["sandbox", [], True])
def test_s_case_rejects_non_object_sandbox_profile(
    invalid_profile: Any,
) -> None:
    body = _golden_s()
    body["sandbox_profile"] = invalid_profile
    _assert_single_issue(
        body,
        "sandbox_profile_exact_fields_invalid",
        "/sandbox_profile",
    )


@pytest.mark.parametrize(
    "forbidden_profile",
    [{"invalid": "object"}, "sandbox", [], True],
)
def test_non_s_case_forbids_sandbox_profile_without_descending(
    forbidden_profile: Any,
) -> None:
    body = _golden_d()
    body["sandbox_profile"] = forbidden_profile
    _assert_single_issue(
        body,
        "sandbox_profile_forbidden",
        "/sandbox_profile",
    )


@pytest.mark.parametrize(
    "missing_field",
    sorted(_SANDBOX_FIELDS - {"allowed_effects"}),
)
def test_sandbox_profile_missing_non_effect_field_is_rejected(
    missing_field: str,
) -> None:
    body = _golden_s()
    del body["sandbox_profile"][missing_field]
    _assert_single_issue(
        body,
        "sandbox_profile_exact_fields_invalid",
        "/sandbox_profile",
    )


def test_sandbox_profile_extra_field_is_rejected() -> None:
    body = _golden_s()
    body["sandbox_profile"]["extra"] = None
    _assert_single_issue(
        body,
        "sandbox_profile_exact_fields_invalid",
        "/sandbox_profile",
    )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("profile_id", None),
        ("id_seed", 1),
        ("fixed_clock", True),
        ("fixed_clock", "2026-1-01T00:00:00Z"),
        ("fixed_clock", "2026-02-30T00:00:00Z"),
        ("fixed_clock", "0000-02-30T00:00:00Z"),
        ("fixed_clock", "2026-04-31T00:00:00Z"),
        ("fixed_clock", "2026-01-01T24:00:00Z"),
        ("fixed_clock", "2026-01-01T23:60:00Z"),
        ("fixed_clock", "2026-01-01T23:59:61Z"),
        ("fixed_clock", "2026-01-01T23:59:60Z"),
        ("fixed_clock", "2026-01-01T00:00:00+01:00"),
    ],
)
def test_sandbox_profile_scalar_contract(field: str, invalid: Any) -> None:
    body = _golden_s()
    body["sandbox_profile"][field] = invalid
    _assert_single_issue(
        body,
        "sandbox_profile_invalid",
        f"/sandbox_profile/{field}",
    )


@pytest.mark.parametrize(
    "fixed_clock",
    [
        "0000-01-01T00:00:00Z",
        "0000-02-29T23:59:59Z",
        "1990-12-31T23:59:60Z",
        "2024-02-29T23:59:59Z",
        "2026-01-01T00:00:00.000Z",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01t00:00:00z",
    ],
)
def test_sandbox_fixed_clock_accepts_valid_rfc3339_literals(
    fixed_clock: str,
) -> None:
    body = _golden_s()
    body["sandbox_profile"]["fixed_clock"] = fixed_clock
    assert validate_case_body(body) == []


def test_sandbox_profile_identifiers_accept_empty_strings() -> None:
    body = _golden_s()
    body["sandbox_profile"]["profile_id"] = ""
    body["sandbox_profile"]["id_seed"] = ""
    assert validate_case_body(body) == []


def test_sandbox_reset_and_cleanup_policies_are_literals() -> None:
    reset = _golden_s()
    reset["sandbox_profile"]["reset_policy"] = "reuse_context"
    _assert_single_issue(
        reset,
        "sandbox_reset_policy_invalid",
        "/sandbox_profile/reset_policy",
    )

    cleanup = _golden_s()
    cleanup["sandbox_profile"]["cleanup_policy"] = "on_success"
    _assert_single_issue(
        cleanup,
        "sandbox_cleanup_policy_invalid",
        "/sandbox_profile/cleanup_policy",
    )


def test_missing_allowed_effects_uses_dedicated_leaf_code() -> None:
    body = _golden_s()
    del body["sandbox_profile"]["allowed_effects"]
    _assert_single_issue(
        body,
        "sandbox_allowed_effects_invalid",
        "/sandbox_profile/allowed_effects",
    )


@pytest.mark.parametrize("invalid", [None, "*", {}])
def test_allowed_effects_must_be_an_explicit_array(invalid: Any) -> None:
    body = _golden_s()
    body["sandbox_profile"]["allowed_effects"] = invalid
    _assert_single_issue(
        body,
        "sandbox_allowed_effects_invalid",
        "/sandbox_profile/allowed_effects",
    )


def test_allowed_effect_rules_are_unique_by_structural_value() -> None:
    first = {"adapter_id": "file", "operation": "write", "target": "out"}
    second = {"target": "out", "operation": "write", "adapter_id": "file"}
    body = _golden_s()
    body["sandbox_profile"]["allowed_effects"] = [first, second]
    _assert_single_issue(
        body,
        "sandbox_allowed_effects_invalid",
        "/sandbox_profile/allowed_effects",
    )


def test_malformed_effect_rules_are_validated_before_duplicate_detection() -> None:
    body = _golden_s()
    body["sandbox_profile"]["allowed_effects"] = [None, None]
    issues = validate_case_body(body)
    _assert_issue_messages(issues)
    assert [
        (issue.code, issue.json_pointer) for issue in issues
    ] == [
        ("sandbox_effect_rule_invalid", "/sandbox_profile/allowed_effects/0"),
        ("sandbox_effect_rule_invalid", "/sandbox_profile/allowed_effects/1"),
    ]


def test_valid_duplicate_and_malformed_effect_rule_are_both_reported() -> None:
    valid = {"adapter_id": "file", "operation": "write", "target": "out"}
    body = _golden_s()
    body["sandbox_profile"]["allowed_effects"] = [
        valid,
        copy.deepcopy(valid),
        None,
    ]
    issues = validate_case_body(body)
    _assert_issue_messages(issues)
    assert [
        (issue.code, issue.json_pointer) for issue in issues
    ] == [
        ("sandbox_allowed_effects_invalid", "/sandbox_profile/allowed_effects"),
        ("sandbox_effect_rule_invalid", "/sandbox_profile/allowed_effects/2"),
    ]


def test_empty_allowed_effects_and_empty_literal_strings_are_valid() -> None:
    empty = _golden_s()
    empty["sandbox_profile"]["allowed_effects"] = []
    assert validate_case_body(empty) == []

    literal_empty_strings = _golden_s()
    literal_empty_strings["sandbox_profile"]["allowed_effects"] = [
        {"adapter_id": "file", "operation": "", "target": ""}
    ]
    assert validate_case_body(literal_empty_strings) == []


@pytest.mark.parametrize(
    "adapter_id",
    ["file", "message", "payment", "network", "core"],
)
def test_every_sandbox_effect_adapter_is_accepted(adapter_id: str) -> None:
    body = _golden_s()
    body["sandbox_profile"]["allowed_effects"] = [
        {"adapter_id": adapter_id, "operation": "", "target": ""}
    ]
    assert validate_case_body(body) == []


@pytest.mark.parametrize(
    ("mutation", "invalid"),
    [
        ("missing-adapter", None),
        ("missing-operation", None),
        ("missing-target", None),
        ("extra", None),
        ("adapter_id", "unknown"),
        ("adapter_id", 1),
        ("adapter_id", True),
        ("operation", 1),
        ("operation", True),
        ("target", 1),
        ("target", True),
        ("non-object", None),
    ],
)
def test_sandbox_effect_rule_leaf_gate(mutation: str, invalid: Any) -> None:
    body = _golden_s()
    rule: Any = {
        "adapter_id": "file",
        "operation": "write",
        "target": "sandbox/output",
    }
    missing_fields = {
        "missing-adapter": "adapter_id",
        "missing-operation": "operation",
        "missing-target": "target",
    }
    if mutation in missing_fields:
        del rule[missing_fields[mutation]]
    elif mutation == "extra":
        rule["extra"] = None
    elif mutation == "non-object":
        rule = None
    else:
        rule[mutation] = invalid
    body["sandbox_profile"]["allowed_effects"] = [rule]
    _assert_single_issue(
        body,
        "sandbox_effect_rule_invalid",
        "/sandbox_profile/allowed_effects/0",
    )


def test_resolve_json_pointer_supports_root_arrays_and_rfc6901_escapes() -> None:
    document = {
        "a/b": {"~key": [{"": 7}]},
        "items": ["zero", "one"],
        "~1": "single-pass-escape",
        "01": "object-leading-zero",
        "null": None,
        "%2F": "literal-percent",
    }
    before = copy.deepcopy(document)
    root_array = ["zero", "one"]
    assert resolve_json_pointer(document, "") is document
    assert resolve_json_pointer(root_array, "") is root_array
    assert resolve_json_pointer(root_array, "/1") == "one"
    assert resolve_json_pointer(document, "/items/1") == "one"
    assert resolve_json_pointer(document, "/a~1b/~0key/0/") == 7
    assert resolve_json_pointer(document, "/~01") == "single-pass-escape"
    assert resolve_json_pointer(document, "/01") == "object-leading-zero"
    assert resolve_json_pointer(document, "/null") is None
    assert resolve_json_pointer(document, "/%2F") == "literal-percent"
    assert document == before


@pytest.mark.parametrize(
    "pointer",
    [
        None,
        1,
        "missing-leading-slash",
        "#/a",
        "/a~",
        "/a~2b",
        "/items/not-an-index",
        "/items/-",
        "/items/00",
        "/items/01",
        "/items/+1",
        "/items/-1",
        "/items/１",
        "/items/2",
        "/missing",
        "/items/0/child",
        "/\ud800",
    ],
)
def test_resolve_json_pointer_rejects_invalid_or_missing_targets(
    pointer: Any,
) -> None:
    document = {
        "a/b": 1,
        "a~": "dangling-escape-must-not-resolve",
        "items": ["zero", "one"],
        "\ud800": "surrogate-must-not-resolve",
    }
    _assert_api_error(
        lambda: resolve_json_pointer(document, pointer),
        "json_pointer_invalid",
    )


def test_resolve_json_pointer_wraps_oversized_array_index() -> None:
    pointer = "/items/" + "9" * 5000
    _assert_api_error(
        lambda: resolve_json_pointer({"items": [0]}, pointer),
        "json_pointer_invalid",
    )


def test_all_rubric_evidence_pointers_resolve_against_final_case_body() -> None:
    body = _golden_hj()
    for rubric in body["rubric_requirements"]:
        pointers = rubric["evidence_case_json_pointers"]
        assert pointers == sorted(pointers)
        for pointer in pointers:
            expected: Any = body
            for token in pointer.lstrip("/").split("/"):
                expected = (
                    expected[int(token)]
                    if type(expected) is list
                    else expected[token]
                )
            assert resolve_json_pointer(body, pointer) == expected


def test_independent_issues_are_exact_and_sorted_by_all_three_fields() -> None:
    body = _golden_d()
    body["schema_version"] = "0.2"
    body["case_id"] = "case-wrong"
    body["setup_steps"][0]["sequence"] = 0
    body["sandbox_profile"] = {"invalid": "object"}
    issues = validate_case_body(body)
    _assert_issue_messages(issues)
    assert [issue.code for issue in issues] == [
        "case_identity_invalid",
        "sandbox_profile_forbidden",
        "case_schema_version_invalid",
        "setup_sequence_invalid",
    ]
    assert issues == sorted(
        issues,
        key=lambda issue: (issue.json_pointer, issue.code, issue.message),
    )
    assert all(type(issue) is ValidationIssue for issue in issues)
    assert all(
        tuple(field.name for field in fields(issue))
        == ("json_pointer", "code", "message")
        for issue in issues
    )


@pytest.mark.parametrize("golden_factory", [_golden_d, _golden_s, _golden_hj])
def test_case_canonical_round_trip_and_hash_are_repeatable(
    tmp_path: Path,
    golden_factory: Callable[[], dict[str, Any]],
) -> None:
    body = golden_factory()
    first = canonical_bytes(body)
    path = tmp_path / f"{body['case_id']}.json"
    path.write_bytes(first)
    reread = path.read_bytes()
    parsed = load_strict_json_bytes(reread, source=path.as_posix())
    second = canonical_bytes(parsed)
    assert parsed == body
    assert parsed is not body
    assert validate_case_body(parsed) == []
    assert reread == first == second
    assert hashlib.sha256(reread).digest() == hashlib.sha256(second).digest()
    assert len(hashlib.sha256(reread).hexdigest().upper()) == 64


@pytest.mark.parametrize("golden_factory", [_golden_d, _golden_s, _golden_hj])
def test_validation_is_repeatable_and_does_not_mutate_input(
    golden_factory: Callable[[], dict[str, Any]],
) -> None:
    body = golden_factory()
    before = canonical_bytes(body)
    first = validate_case_body(body)
    second = validate_case_body(body)
    assert first == second == []
    assert first is not second
    assert canonical_bytes(body) == before


def test_validation_failure_does_not_write_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _golden_d()
    body["oracle_kinds"] = ["D", "D"]
    output = tmp_path / "invalid-case.json"

    def forbidden_write(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("case validation attempted filesystem output")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden_write)
        guard.setattr(io, "open", forbidden_write)
        guard.setattr(Path, "open", forbidden_write)
        guard.setattr(Path, "write_bytes", forbidden_write)
        guard.setattr(Path, "write_text", forbidden_write)
        guard.setattr(Path, "mkdir", forbidden_write)
        for name in (
            "open",
            "mkdir",
            "makedirs",
            "remove",
            "unlink",
            "rename",
            "replace",
            "rmdir",
        ):
            guard.setattr(os, name, forbidden_write)
        _assert_single_issue(
            body,
            "case_oracle_kinds_invalid",
            "/oracle_kinds",
        )
    assert not output.exists()
