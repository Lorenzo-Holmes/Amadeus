import copy
import re
from pathlib import Path
from typing import Any

import pytest

from tools.stage0c_fixtures.io import canonical_bytes, load_strict_json_bytes
from tools.stage0c_fixtures.schema import build_fixture_case_schema


_CASE_FIELDS = (
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
)
_STRUCTURAL_FIELDS = {
    "actor": ("actor_type", "actor_id"),
    "expected_version": ("target_record_ref", "expected_version"),
    "mutation_command_envelope": (
        "command_id",
        "command_type",
        "actor",
        "actor_capability_id",
        "expected_versions",
        "audit_context_id",
        "idempotency_key",
        "issued_at",
        "target_record_refs",
        "payload",
    ),
    "input_source": ("source_id", "trust"),
    "reversibility": ("status", "rollback_plan", "rollback_deadline"),
    "budget": ("calls", "money", "time"),
    "scope": ("resources", "parameter_constraints"),
    "confirmation": (
        "required",
        "confirmation_id",
        "summary_checksum",
    ),
    "action_envelope": (
        "action_id",
        "identity_id",
        "lineage_id",
        "branch_id",
        "vault_id",
        "user_id",
        "session_id",
        "task_id",
        "candidate_intent_id",
        "intent_summary",
        "tool_id",
        "operation",
        "parameters",
        "targets",
        "destinations",
        "input_sources",
        "data_classes",
        "expected_effects",
        "effect_class",
        "reversibility",
        "expected_state_diff",
        "budget",
        "scope",
        "expires_at",
        "max_uses",
        "idempotency_key",
        "confirmation",
        "policy_version",
    ),
    "effect_rule": ("adapter_id", "operation", "target"),
    "sandbox_profile": (
        "profile_id",
        "allowed_effects",
        "fixed_clock",
        "id_seed",
        "reset_policy",
        "cleanup_policy",
    ),
    "rubric_requirement": (
        "criterion_id",
        "oracle_kind",
        "question",
        "evidence_case_json_pointers",
        "allowed_scores",
        "passing_scores",
    ),
    "state_patch_operation": ("op", "path", "value"),
    "effect_seed": ("adapter_id", "operation", "target", "details"),
    "observed_effect": (
        "effect_id",
        "adapter_id",
        "operation",
        "target",
        "details",
    ),
    "effect_pattern": ("adapter_id", "operation", "target", "details"),
    "driver_result": (
        "result_ref",
        "status",
        "error_code",
        "retryable",
        "output",
        "effects",
        "state_patch",
    ),
    "handler_result": (
        "status",
        "error_code",
        "retryable",
        "output",
        "effects",
        "state_patch",
    ),
    "setup_step": ("sequence", "step_id", "handler_id", "params"),
    "stimulus_step": ("sequence", "step_id", "handler_id", "params"),
    "machine_assertion": (
        "sequence",
        "assertion_id",
        "handler_id",
        "step_id",
        "params",
    ),
    "state_snapshot": ("state", "state_sha256"),
    "action_receipt": (
        "schema_version",
        "case_id",
        "step_id",
        "action_id",
        "handler_id",
        "status",
        "error_code",
        "retryable",
        "pre_state_sha256",
        "post_state_sha256",
        "handler_output_sha256",
        "observed_effects",
        "idempotency_key",
        "request_content_sha256",
        "replayed",
    ),
    "step_execution": (
        "step_id",
        "handler_id",
        "request_content_sha256",
        "pre_snapshot",
        "post_snapshot",
        "handler_output",
        "observed_effects",
        "receipt",
    ),
    "effect_diff": ("effects", "aggregate_sha256"),
    "assertion_result": (
        "assertion_id",
        "passed",
        "actual",
        "error_code",
    ),
    "primary_error": ("phase", "code", "message"),
    "cleanup_report": (
        "attempted",
        "status",
        "residual_paths",
        "residual_effects",
        "error",
    ),
    "sandbox_run_result": (
        "schema_version",
        "case_id",
        "phase",
        "step_executions",
        "before_snapshot",
        "after_snapshot",
        "effect_diff",
        "assertion_results",
        "primary_error",
        "cleanup_report",
        "succeeded",
    ),
}
_DEF_NAMES = frozenset(_STRUCTURAL_FIELDS) | {
    "handler_params",
    "json_value",
    "json_map",
    "json_pointer",
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
                "step_id": "setup-1",
                "handler_id": "sandbox.set_clock",
                "params": {"future_f07": {"open": True}},
            }
        ],
        "stimulus_steps": [
            {
                "sequence": 1,
                "step_id": "step-1",
                "handler_id": "backend.replay",
                "params": {"future_f07": [1, None]},
            }
        ],
        "machine_assertions": [
            {
                "sequence": 1,
                "assertion_id": "assertion-1",
                "handler_id": "receipt.status",
                "step_id": "step-1",
                "params": {"future_f07": "completed"},
            }
        ],
        "rubric_requirements": [],
        "sandbox_profile": None,
    }


def _type_matches(expected: str, value: Any) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return type(value) is bool
    if expected == "integer":
        return type(value) is int
    if expected == "string":
        return type(value) is str
    if expected == "array":
        return type(value) is list
    if expected == "object":
        return type(value) is dict
    raise AssertionError(f"unsupported test schema type: {expected}")


def _schema_errors(
    schema: dict[str, Any],
    value: Any,
    root: dict[str, Any],
    pointer: str = "",
) -> list[str]:
    if "$ref" in schema:
        prefix = "#/$defs/"
        ref = schema["$ref"]
        assert ref.startswith(prefix)
        return _schema_errors(root["$defs"][ref[len(prefix) :]], value, root, pointer)

    if "anyOf" in schema:
        branches = [
            _schema_errors(branch, value, root, pointer)
            for branch in schema["anyOf"]
        ]
        return [] if any(not errors for errors in branches) else [pointer]

    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(pointer)
    if "enum" in schema and value not in schema["enum"]:
        errors.append(pointer)
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(expected_type, value):
        return [pointer]
    if type(value) is str:
        if len(value) < schema.get("minLength", 0):
            errors.append(pointer)
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(pointer)
    if type(value) is int and type(value) is not bool:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(pointer)
    if type(value) is list:
        if len(value) < schema.get("minItems", 0):
            errors.append(pointer)
        if schema.get("uniqueItems"):
            fingerprints = [canonical_bytes(item) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                errors.append(pointer)
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(
                    _schema_errors(
                        schema["items"],
                        item,
                        root,
                        f"{pointer}/{index}",
                    )
                )
    if type(value) is dict:
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                errors.append(f"{pointer}/{field}")
        properties = schema.get("properties", {})
        for field, item in value.items():
            child_pointer = f"{pointer}/{field}"
            if field in properties:
                errors.extend(
                    _schema_errors(properties[field], item, root, child_pointer)
                )
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(child_pointer)
            elif type(additional) is dict:
                errors.extend(
                    _schema_errors(additional, item, root, child_pointer)
                )
    return sorted(set(errors))


def test_fixture_schema_root_and_defs_are_exact(fixture_schema: dict[str, Any]) -> None:
    assert set(fixture_schema) == {
        "$schema",
        "title",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "$defs",
    }
    assert fixture_schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert fixture_schema["type"] == "object"
    assert fixture_schema["required"] == list(_CASE_FIELDS)
    assert set(fixture_schema["properties"]) == set(_CASE_FIELDS)
    assert fixture_schema["additionalProperties"] is False
    assert set(fixture_schema["$defs"]) == _DEF_NAMES


@pytest.mark.parametrize(
    ("name", "fields"),
    tuple(_STRUCTURAL_FIELDS.items()),
)
def test_every_structural_schema_has_exact_required_fields(
    fixture_schema: dict[str, Any],
    name: str,
    fields: tuple[str, ...],
) -> None:
    definition = fixture_schema["$defs"][name]
    assert definition["type"] == "object"
    assert definition["required"] == list(fields)
    assert set(definition["properties"]) == set(fields)
    assert definition["additionalProperties"] is False


def test_only_json_maps_have_recursively_open_keys(
    fixture_schema: dict[str, Any],
) -> None:
    definitions = fixture_schema["$defs"]
    assert definitions["json_map"] == {
        "type": "object",
        "additionalProperties": {"$ref": "#/$defs/json_value"},
    }
    for name in _STRUCTURAL_FIELDS:
        assert definitions[name]["additionalProperties"] is False


def test_f07_params_keep_json_map_base_and_add_handler_schemas(
    fixture_schema: dict[str, Any],
) -> None:
    for name in ("setup_step", "stimulus_step", "machine_assertion"):
        assert fixture_schema["$defs"][name]["properties"]["params"] == {
            "$ref": "#/$defs/json_map"
        }
    assert "handler_params" in fixture_schema["$defs"]


def test_frozen_enums_are_not_open_ended(fixture_schema: dict[str, Any]) -> None:
    definitions = fixture_schema["$defs"]
    assert definitions["effect_rule"]["properties"]["adapter_id"]["enum"] == [
        "file",
        "message",
        "payment",
        "network",
        "core",
    ]
    assert definitions["input_source"]["properties"]["trust"]["enum"] == [
        "trusted_instruction",
        "user_data",
        "external_untrusted",
        "derived",
    ]
    assert definitions["action_envelope"]["properties"]["data_classes"][
        "items"
    ]["enum"] == ["public", "personal", "sensitive", "secret"]
    assert definitions["action_envelope"]["properties"]["effect_class"][
        "enum"
    ] == ["E0", "E1", "E2", "E3"]


def test_golden_case_satisfies_structural_schema(
    fixture_schema: dict[str, Any],
) -> None:
    assert _schema_errors(fixture_schema, _golden_case(), fixture_schema) == []


@pytest.mark.parametrize("missing", _CASE_FIELDS)
def test_required_case_field_mutation_is_rejected(
    fixture_schema: dict[str, Any],
    missing: str,
) -> None:
    value = _golden_case()
    del value[missing]
    assert f"/{missing}" in _schema_errors(fixture_schema, value, fixture_schema)


def test_additional_property_mutation_is_rejected(
    fixture_schema: dict[str, Any],
) -> None:
    value = _golden_case()
    value["stimulus_steps"][0]["extra"] = None
    assert "/stimulus_steps/0/extra" in _schema_errors(
        fixture_schema,
        value,
        fixture_schema,
    )


def test_builder_returns_fresh_schema_and_permissive_mutation_is_detectable() -> None:
    mutated = build_fixture_case_schema()
    mutated["$defs"]["effect_rule"]["additionalProperties"] = True
    fresh = build_fixture_case_schema()
    assert fresh["$defs"]["effect_rule"]["additionalProperties"] is False
    assert canonical_bytes(mutated) != canonical_bytes(fresh)


def test_schema_nodes_are_detached_within_each_build() -> None:
    schema = build_fixture_case_schema()
    definitions = schema["$defs"]

    action = definitions["action_envelope"]["properties"]
    action["action_id"]["pattern"] = "^mutated$"
    assert action["identity_id"]["pattern"] != "^mutated$"
    assert action["vault_id"]["anyOf"][0]["pattern"] != "^mutated$"

    driver = definitions["driver_result"]["properties"]
    handler = definitions["handler_result"]["properties"]
    driver["status"]["enum"].append("mutated")
    assert "mutated" not in handler["status"]["enum"]


def test_required_and_additional_property_schema_mutations_are_observable() -> None:
    fresh = build_fixture_case_schema()
    effect = {"adapter_id": "file", "operation": "write", "target": "out"}

    missing_required = copy.deepcopy(fresh)
    missing_required["$defs"]["effect_rule"]["required"].remove("target")
    missing_effect = {"adapter_id": "file", "operation": "write"}
    assert _schema_errors(
        fresh["$defs"]["effect_rule"],
        missing_effect,
        fresh,
    ) == ["/target"]
    assert _schema_errors(
        missing_required["$defs"]["effect_rule"],
        missing_effect,
        missing_required,
    ) == []

    permissive = copy.deepcopy(fresh)
    permissive["$defs"]["effect_rule"]["additionalProperties"] = True
    effect["extra"] = None
    assert _schema_errors(
        fresh["$defs"]["effect_rule"],
        effect,
        fresh,
    ) == ["/extra"]
    assert _schema_errors(
        permissive["$defs"]["effect_rule"],
        effect,
        permissive,
    ) == []


def test_relational_schema_guards_are_present() -> None:
    definitions = build_fixture_case_schema()["$defs"]
    guarded = (
        "reversibility",
        "confirmation",
        "action_envelope",
        "state_patch_operation",
        "driver_result",
        "handler_result",
        "action_receipt",
        "assertion_result",
        "cleanup_report",
        "sandbox_run_result",
    )
    for name in guarded:
        assert definitions[name]["allOf"]


def test_utc_fields_share_the_frozen_rfc3339_pattern() -> None:
    definitions = build_fixture_case_schema()["$defs"]
    expected = definitions["sandbox_profile"]["properties"]["fixed_clock"][
        "pattern"
    ]
    assert definitions["mutation_command_envelope"]["properties"][
        "issued_at"
    ]["pattern"] == expected
    assert definitions["action_envelope"]["properties"]["expires_at"][
        "pattern"
    ] == expected
    assert definitions["reversibility"]["properties"][
        "rollback_deadline"
    ]["anyOf"][0]["pattern"] == expected


def test_schema_canonical_round_trip_is_repeatable(
    fixture_schema: dict[str, Any],
    tmp_path: Path,
) -> None:
    first = canonical_bytes(fixture_schema)
    path = tmp_path / "fixture_case_schema_v0_1.json"
    path.write_bytes(first)
    reread = load_strict_json_bytes(path.read_bytes(), source=path.name)
    assert reread == fixture_schema
    assert canonical_bytes(reread) == first
    assert build_fixture_case_schema() == fixture_schema
