import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.stage0c_fixtures.dsl import validate_case_body
from tools.stage0c_fixtures.io import (
    canonical_bytes,
    load_strict_json_bytes,
    sha256_upper,
)
from tools.stage0c_fixtures.schema import build_fixture_case_schema


_HANDLER_IDS = (
    "sandbox.seed_state",
    "sandbox.set_clock",
    "sandbox.configure_core_driver",
    "sandbox.configure_adapter",
    "sandbox.seed_backend_response",
    "core.command",
    "core.query",
    "external.action",
    "backend.replay",
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
_ROW_FIELDS = {
    "handler_kind",
    "valid_params",
    "one_missing_required",
    "one_extra_field",
    "one_wrong_type",
}
_DEFINITION_BY_KIND = {
    "setup": "setup_step",
    "stimulus": "stimulus_step",
    "assertion": "machine_assertion",
}


def _mutation_command() -> dict[str, Any]:
    return {
        "command_id": "cmd-ac-001-delete",
        "command_type": "memory.delete",
        "actor": {"actor_type": "user", "actor_id": "user-ac-001"},
        "actor_capability_id": "cap-user-request-ac-001",
        "expected_versions": [
            {
                "target_record_ref": "memory-ac-001",
                "expected_version": 1,
            }
        ],
        "audit_context_id": "audit-ac-001",
        "idempotency_key": "idem-ac-001-delete",
        "issued_at": "2026-01-01T00:00:00Z",
        "target_record_refs": ["memory-ac-001"],
        "payload": {"memory_id": "memory-ac-001"},
    }


def _failed_driver_result() -> dict[str, Any]:
    return {
        "result_ref": "result-user-delete-forbidden",
        "status": "failed",
        "error_code": "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
        "retryable": False,
        "output": {},
        "effects": [],
        "state_patch": [],
    }


def _action_envelope() -> dict[str, Any]:
    return {
        "action_id": "018f47a2-7b9c-7f31-8f44-1234567890ab",
        "identity_id": "018f47a2-7b9c-7f31-8f44-1234567890ac",
        "lineage_id": "018f47a2-7b9c-7f31-8f44-1234567890ad",
        "branch_id": "018f47a2-7b9c-7f31-8f44-1234567890ae",
        "vault_id": None,
        "user_id": "user-ac-001",
        "session_id": "session-ac-001",
        "task_id": "task-ac-001",
        "candidate_intent_id": "intent-ac-001",
        "intent_summary": "write a sandbox fixture",
        "tool_id": "file",
        "operation": "write",
        "parameters": {"content": "fixture"},
        "targets": ["sandbox/output.txt"],
        "destinations": ["sandbox"],
        "input_sources": [
            {"source_id": "source-ac-001", "trust": "user_data"}
        ],
        "data_classes": ["public"],
        "expected_effects": [{"operation": "write"}],
        "effect_class": "E1",
        "reversibility": {
            "status": "verified",
            "rollback_plan": "restore snapshot",
            "rollback_deadline": "2026-01-02T00:00:00Z",
        },
        "expected_state_diff": {"created": True},
        "budget": {"calls": 1, "money": "0", "time": 30},
        "scope": {
            "resources": ["sandbox/output.txt"],
            "parameter_constraints": {"mode": "exact"},
        },
        "expires_at": "2026-01-01T00:05:00Z",
        "max_uses": 1,
        "idempotency_key": "action-key-ac-001",
        "confirmation": {
            "required": False,
            "confirmation_id": None,
            "summary_checksum": None,
        },
        "policy_version": "0.1",
    }


def _effect_pattern() -> dict[str, Any]:
    return {
        "adapter_id": "file",
        "operation": "write",
        "target": "sandbox/output.txt",
        "details": {},
    }


def _handler_row(
    handler_kind: str,
    valid_params: dict[str, Any],
    *,
    missing: str,
    wrong_field: str,
    wrong_value: Any,
) -> dict[str, Any]:
    one_missing_required = copy.deepcopy(valid_params)
    del one_missing_required[missing]
    one_extra_field = copy.deepcopy(valid_params)
    one_extra_field["extra"] = None
    one_wrong_type = copy.deepcopy(valid_params)
    one_wrong_type[wrong_field] = wrong_value
    return {
        "handler_kind": handler_kind,
        "valid_params": valid_params,
        "one_missing_required": one_missing_required,
        "one_extra_field": one_extra_field,
        "one_wrong_type": one_wrong_type,
    }


_HANDLER_ROWS = {
    "sandbox.seed_state": _handler_row(
        "setup",
        {"records": [{"record_id": "memory-ac-001"}]},
        missing="records",
        wrong_field="records",
        wrong_value={},
    ),
    "sandbox.set_clock": _handler_row(
        "setup",
        {"utc_rfc3339": "2026-01-01T00:00:00Z"},
        missing="utc_rfc3339",
        wrong_field="utc_rfc3339",
        wrong_value=0,
    ),
    "sandbox.configure_core_driver": _handler_row(
        "setup",
        {"seeded_results": [_failed_driver_result()]},
        missing="seeded_results",
        wrong_field="seeded_results",
        wrong_value={},
    ),
    "sandbox.configure_adapter": _handler_row(
        "setup",
        {"adapter_id": "file", "seeded_results": [_failed_driver_result()]},
        missing="adapter_id",
        wrong_field="adapter_id",
        wrong_value=True,
    ),
    "sandbox.seed_backend_response": _handler_row(
        "setup",
        {"replay_key": "backend-ac-001", "output": {"answer": "fixture"}},
        missing="replay_key",
        wrong_field="replay_key",
        wrong_value=[],
    ),
    "core.command": _handler_row(
        "stimulus",
        {
            "mutation_command": _mutation_command(),
            "driver_result_ref": "result-user-delete-forbidden",
        },
        missing="mutation_command",
        wrong_field="driver_result_ref",
        wrong_value=False,
    ),
    "core.query": _handler_row(
        "stimulus",
        {
            "query_id": "query-ac-001",
            "arguments": {"memory_id": "memory-ac-001"},
            "driver_result_ref": "result-query-ac-001",
        },
        missing="arguments",
        wrong_field="arguments",
        wrong_value=[],
    ),
    "external.action": _handler_row(
        "stimulus",
        {
            "adapter_id": "file",
            "action_envelope": _action_envelope(),
            "driver_result_ref": "result-action-ac-001",
        },
        missing="action_envelope",
        wrong_field="adapter_id",
        wrong_value="core",
    ),
    "backend.replay": _handler_row(
        "stimulus",
        {"replay_key": "backend-ac-001", "input": {"prompt": "fixture"}},
        missing="input",
        wrong_field="input",
        wrong_value="fixture",
    ),
    "receipt.status": _handler_row(
        "assertion",
        {"expected": "completed"},
        missing="expected",
        wrong_field="expected",
        wrong_value="pending",
    ),
    "receipt.error_code": _handler_row(
        "assertion",
        {
            "expected": "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
            "retryable": False,
        },
        missing="retryable",
        wrong_field="retryable",
        wrong_value="false",
    ),
    "state.path_equals": _handler_row(
        "assertion",
        {"json_pointer": "/records/memory-ac-001", "expected": {"version": 1}},
        missing="json_pointer",
        wrong_field="json_pointer",
        wrong_value=1,
    ),
    "state.hash_unchanged": _handler_row(
        "assertion",
        {"scope_json_pointer": ""},
        missing="scope_json_pointer",
        wrong_field="scope_json_pointer",
        wrong_value=None,
    ),
    "effect.includes": _handler_row(
        "assertion",
        {"expected_effect": _effect_pattern()},
        missing="expected_effect",
        wrong_field="expected_effect",
        wrong_value=[],
    ),
    "effect.excludes": _handler_row(
        "assertion",
        {"forbidden_effect": _effect_pattern()},
        missing="forbidden_effect",
        wrong_field="forbidden_effect",
        wrong_value="file.write",
    ),
    "output.contains": _handler_row(
        "assertion",
        {"json_pointer": "/answer", "value": "fixture"},
        missing="value",
        wrong_field="json_pointer",
        wrong_value=False,
    ),
    "output.omits": _handler_row(
        "assertion",
        {"json_pointer": "/secret", "value": "token"},
        missing="json_pointer",
        wrong_field="json_pointer",
        wrong_value=[],
    ),
    "replay.equals": _handler_row(
        "assertion",
        {
            "first_step_id": "delete-memory",
            "replay_step_id": "delete-memory-replay",
            "compare_fields": ["status", "error_code"],
        },
        missing="compare_fields",
        wrong_field="compare_fields",
        wrong_value={},
    ),
}


def _type_matches(expected: str, value: Any) -> bool:
    return {
        "null": value is None,
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "string": type(value) is str,
        "array": type(value) is list,
        "object": type(value) is dict,
    }[expected]


def _json_equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    assert reference.startswith("#/")
    node: Any = root
    for raw_token in reference[2:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    assert type(node) is dict
    return node


def _schema_issues(
    schema: dict[str, Any],
    value: Any,
    root: dict[str, Any],
    pointer: str = "",
) -> list[tuple[str, str]]:
    if "$ref" in schema:
        return _schema_issues(_resolve_ref(root, schema["$ref"]), value, root, pointer)

    if "anyOf" in schema:
        branches = [
            _schema_issues(branch, value, root, pointer)
            for branch in schema["anyOf"]
        ]
        return [] if any(not issues for issues in branches) else [(pointer, "anyOf")]
    if "oneOf" in schema:
        matching = sum(
            not _schema_issues(branch, value, root, pointer)
            for branch in schema["oneOf"]
        )
        return [] if matching == 1 else [(pointer, "oneOf")]
    if "not" in schema and not _schema_issues(schema["not"], value, root, pointer):
        return [(pointer, "not")]

    issues: list[tuple[str, str]] = []
    for branch in schema.get("allOf", []):
        issues.extend(_schema_issues(branch, value, root, pointer))
    if "const" in schema and not _json_equal(value, schema["const"]):
        issues.append((pointer, "const"))
    if "enum" in schema and not any(
        _json_equal(value, allowed) for allowed in schema["enum"]
    ):
        issues.append((pointer, "enum"))

    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(expected_type, value):
        issues.append((pointer, "type"))
        return sorted(set(issues))

    if type(value) is str:
        if len(value) < schema.get("minLength", 0):
            issues.append((pointer, "minLength"))
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            issues.append((pointer, "pattern"))
    if type(value) is int and type(value) is not bool:
        if "minimum" in schema and value < schema["minimum"]:
            issues.append((pointer, "minimum"))
    if type(value) is list:
        if len(value) < schema.get("minItems", 0):
            issues.append((pointer, "minItems"))
        if len(value) > schema.get("maxItems", len(value)):
            issues.append((pointer, "maxItems"))
        if schema.get("uniqueItems"):
            fingerprints = [canonical_bytes(item) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                issues.append((pointer, "uniqueItems"))
        for index, item in enumerate(value):
            if "items" in schema:
                issues.extend(
                    _schema_issues(
                        schema["items"], item, root, f"{pointer}/{index}"
                    )
                )
    if type(value) is dict:
        for field in schema.get("required", []):
            if field not in value:
                issues.append((f"{pointer}/{field}", "required"))
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for field, item in value.items():
            child_pointer = f"{pointer}/{field}"
            if field in properties:
                issues.extend(
                    _schema_issues(properties[field], item, root, child_pointer)
                )
            elif additional is False:
                issues.append((child_pointer, "additionalProperties"))
            elif type(additional) is dict:
                issues.extend(_schema_issues(additional, item, root, child_pointer))

    condition = schema.get("if")
    if condition is not None:
        selected = "then" if not _schema_issues(condition, value, root, pointer) else "else"
        if selected in schema:
            issues.extend(_schema_issues(schema[selected], value, root, pointer))
    return sorted(set(issues))


def _declaration(handler_id: str, row: dict[str, Any], params: Any) -> dict[str, Any]:
    if row["handler_kind"] == "assertion":
        return {
            "sequence": 1,
            "assertion_id": "assertion-1",
            "handler_id": handler_id,
            "step_id": "stimulus-1",
            "params": params,
        }
    return {
        "sequence": 1,
        "step_id": "step-1",
        "handler_id": handler_id,
        "params": params,
    }


def _golden_case() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "case_id": "case-ac-001-1",
        "source_id": "AC-001",
        "source_clause_id": "AC-001#1",
        "oracle_kinds": ["D"],
        "setup_steps": [
            {
                "sequence": 1,
                "step_id": "seed-memory-state",
                "handler_id": "sandbox.seed_state",
                "params": {
                    "records": [
                        {
                            "record_id": "memory-ac-001",
                            "record_type": "memory",
                            "version": 1,
                            "content": "fixture-memory",
                        },
                        {
                            "record_id": "ledger-ac-001",
                            "record_type": "ledger_anchor",
                            "version": 1,
                            "hash": "A" * 64,
                        },
                    ]
                },
            },
            {
                "sequence": 2,
                "step_id": "setup-core-driver",
                "handler_id": "sandbox.configure_core_driver",
                "params": {"seeded_results": [_failed_driver_result()]},
            },
        ],
        "stimulus_steps": [
            {
                "sequence": 1,
                "step_id": "delete-memory",
                "handler_id": "core.command",
                "params": {
                    "mutation_command": _mutation_command(),
                    "driver_result_ref": "result-user-delete-forbidden",
                },
            }
        ],
        "machine_assertions": [
            {
                "sequence": 1,
                "assertion_id": "assert-delete-forbidden",
                "handler_id": "receipt.error_code",
                "step_id": "delete-memory",
                "params": {
                    "expected": "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
                    "retryable": False,
                },
            },
            {
                "sequence": 2,
                "assertion_id": "assert-state-unchanged",
                "handler_id": "state.hash_unchanged",
                "step_id": "delete-memory",
                "params": {"scope_json_pointer": ""},
            },
        ],
        "rubric_requirements": [],
        "sandbox_profile": None,
    }


def _golden_contract_codes(value: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    driver = value["setup_steps"][1]["params"]["seeded_results"][0]
    state_hash = value["machine_assertions"][1]
    command_params = value["stimulus_steps"][0]["params"]
    if value["source_clause_id"] != "AC-001#1":
        codes.append("golden_source_clause_id_mismatch")
    if driver["error_code"] != "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN":
        codes.append("golden_driver_error_code_mismatch")
    if driver["retryable"] is not False:
        codes.append("golden_driver_retryable_mismatch")
    if state_hash["params"]["scope_json_pointer"] != "":
        codes.append("golden_state_hash_pointer_mismatch")
    if value["oracle_kinds"] != ["D"]:
        codes.append("golden_oracle_mapping_mismatch")
    if set(command_params) != {"mutation_command", "driver_result_ref"}:
        codes.append("golden_handler_params_extra")
    return codes


def _mutate_source_clause(value: dict[str, Any]) -> None:
    value["source_clause_id"] = "AC-001#2"


def _mutate_driver_error(value: dict[str, Any]) -> None:
    value["setup_steps"][1]["params"]["seeded_results"][0][
        "error_code"
    ] = "CORE-E-WRONG"


def _mutate_retryable(value: dict[str, Any]) -> None:
    value["setup_steps"][1]["params"]["seeded_results"][0]["retryable"] = True


def _mutate_state_hash_pointer(value: dict[str, Any]) -> None:
    value["machine_assertions"][1]["params"]["scope_json_pointer"] = "/records"


def _mutate_oracle_mapping(value: dict[str, Any]) -> None:
    value["oracle_kinds"] = ["S"]


def _mutate_extra_param(value: dict[str, Any]) -> None:
    value["stimulus_steps"][0]["params"]["extra"] = None


def test_handler_parameter_table_is_the_frozen_18_row_matrix() -> None:
    assert tuple(_HANDLER_ROWS) == _HANDLER_IDS
    assert set(_HANDLER_ROWS) == set(_HANDLER_IDS)
    assert all(set(row) == _ROW_FIELDS for row in _HANDLER_ROWS.values())
    assert [row["handler_kind"] for row in _HANDLER_ROWS.values()] == (
        ["setup"] * 5 + ["stimulus"] * 4 + ["assertion"] * 9
    )


@pytest.mark.parametrize("handler_id", _HANDLER_IDS)
def test_each_handler_schema_accepts_valid_and_rejects_three_mutations(
    fixture_schema: dict[str, Any],
    handler_id: str,
) -> None:
    definitions = fixture_schema["$defs"]
    params_schemas = definitions["handler_params"]
    row = _HANDLER_ROWS[handler_id]
    params_schema = params_schemas[handler_id]
    declaration_schema = definitions[_DEFINITION_BY_KIND[row["handler_kind"]]]

    valid = row["valid_params"]
    assert _schema_issues(params_schema, valid, fixture_schema) == []
    assert _schema_issues(
        declaration_schema,
        _declaration(handler_id, row, valid),
        fixture_schema,
    ) == []

    for mutation_name in (
        "one_missing_required",
        "one_extra_field",
        "one_wrong_type",
    ):
        mutated = row[mutation_name]
        assert _schema_issues(params_schema, mutated, fixture_schema), mutation_name
        assert _schema_issues(
            declaration_schema,
            _declaration(handler_id, row, mutated),
            fixture_schema,
        ), mutation_name


def test_handler_params_keys_and_conditional_refs_are_exact(
    fixture_schema: dict[str, Any],
) -> None:
    definitions = fixture_schema["$defs"]
    assert tuple(definitions["handler_params"]) == _HANDLER_IDS
    for kind, definition_name in _DEFINITION_BY_KIND.items():
        expected_ids = [
            handler_id
            for handler_id, row in _HANDLER_ROWS.items()
            if row["handler_kind"] == kind
        ]
        expected_branches = [
            {
                "if": {
                    "properties": {"handler_id": {"const": handler_id}},
                    "required": ["handler_id"],
                },
                "then": {
                    "properties": {
                        "params": {
                            "$ref": f"#/$defs/handler_params/{handler_id}"
                        }
                    }
                },
            }
            for handler_id in expected_ids
        ]
        assert definitions[definition_name]["allOf"] == expected_branches


@pytest.mark.parametrize(
    ("target_kind", "target"),
    [
        ("unknown-handler", "unknown.handler"),
        ("import-path", "os.system"),
        ("module", "os"),
        ("expression", "lambda: 0"),
        ("script", "handler.py"),
        ("callable-target", build_fixture_case_schema),
    ],
)
def test_dynamic_or_unknown_handler_targets_are_rejected(
    fixture_schema: dict[str, Any],
    target_kind: str,
    target: Any,
) -> None:
    row = _HANDLER_ROWS["sandbox.seed_state"]
    declaration = _declaration(target, row, row["valid_params"])
    issues = _schema_issues(
        fixture_schema["$defs"]["setup_step"],
        declaration,
        fixture_schema,
    )
    assert ("/handler_id", "enum") in issues, target_kind


def test_frozen_ac_001_1_golden_case_validates_field_by_field(
    fixture_schema: dict[str, Any],
) -> None:
    golden = _golden_case()
    assert _golden_contract_codes(golden) == []
    assert validate_case_body(golden) == []
    assert _schema_issues(fixture_schema, golden, fixture_schema) == []
    assert canonical_bytes(golden) == canonical_bytes(copy.deepcopy(golden))


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (_mutate_source_clause, "golden_source_clause_id_mismatch"),
        (_mutate_driver_error, "golden_driver_error_code_mismatch"),
        (_mutate_retryable, "golden_driver_retryable_mismatch"),
        (_mutate_state_hash_pointer, "golden_state_hash_pointer_mismatch"),
        (_mutate_oracle_mapping, "golden_oracle_mapping_mismatch"),
        (_mutate_extra_param, "golden_handler_params_extra"),
    ],
    ids=(
        "source-clause-id",
        "driver-error-code",
        "retryable",
        "state-hash-pointer",
        "oracle-mapping",
        "extra-param",
    ),
)
def test_golden_single_factor_mutations_have_unique_expected_codes(
    mutation: Callable[[dict[str, Any]], None],
    expected_code: str,
) -> None:
    value = _golden_case()
    mutation(value)
    assert _golden_contract_codes(value) == [expected_code]


def test_handler_param_schema_hashes_survive_canonical_reread(
    fixture_schema: dict[str, Any],
    tmp_path: Path,
) -> None:
    first_objects = fixture_schema["$defs"]["handler_params"]
    first_bytes = {
        key: canonical_bytes(first_objects[key]) for key in _HANDLER_IDS
    }
    first_hashes = {
        key: sha256_upper(first_bytes[key]) for key in _HANDLER_IDS
    }

    path = tmp_path / "fixture_case_schema_v0_1.json"
    path.write_bytes(canonical_bytes(fixture_schema))
    reread = load_strict_json_bytes(path.read_bytes(), source=path.name)
    second_objects = reread["$defs"]["handler_params"]
    second_bytes = {
        key: canonical_bytes(second_objects[key]) for key in _HANDLER_IDS
    }
    second_hashes = {
        key: sha256_upper(second_bytes[key]) for key in _HANDLER_IDS
    }

    assert tuple(first_objects) == _HANDLER_IDS
    assert set(second_objects) == set(_HANDLER_IDS)
    assert first_bytes == second_bytes
    assert first_hashes == second_hashes
    assert all(len(value) == 64 and value == value.upper() for value in first_hashes.values())
