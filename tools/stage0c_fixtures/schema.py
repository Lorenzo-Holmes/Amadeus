from __future__ import annotations

import re as _re
from copy import deepcopy as _deepcopy
from types import MappingProxyType as _MappingProxyType
from typing import Any as _Any
from typing import Callable as _Callable
from typing import Mapping as _Mapping
from typing import cast as _cast

from .constants import SCHEMA_VERSION as _SCHEMA_VERSION
from .dsl import _ADAPTER_ID_ORDER
from .dsl import _ADAPTER_IDS
from .dsl import _ASSERTION_FIELD_ORDER
from .dsl import _ASSERTION_HANDLER_ORDER
from .dsl import _CASE_FIELD_ORDER
from .dsl import _CLAUSE_ID_RE
from .dsl import _EFFECT_FIELD_ORDER
from .dsl import _HUMAN_ORACLES
from .dsl import _IDENTIFIER_RE
from .dsl import _JSON_POINTER_PATTERN
from .dsl import _ORACLE_ORDER
from .dsl import _RUBRIC_FIELD_ORDER
from .dsl import _SANDBOX_FIELD_ORDER
from .dsl import _SETUP_HANDLER_ORDER
from .dsl import _STEP_FIELD_ORDER
from .dsl import _STIMULUS_HANDLER_ORDER
from .dsl import _UTC_RFC3339_RE
from .dsl import _fixed_clock_is_valid
from .dsl import _json_pointer_syntax_is_valid
from .io import canonical_bytes as _canonical_bytes
from .io import sha256_upper as _sha256_upper
from .types import FixtureInputError as _FixtureInputError
from .types import ValidationIssue as _ValidationIssue


__all__ = ("build_fixture_case_schema", "validate_envelope")


_JSON_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
_UUID_PATTERN = (
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_UUID_RE = _re.compile(_UUID_PATTERN)
_SHA256_PATTERN = r"^[0-9A-F]{64}$"
_SHA256_RE = _re.compile(_SHA256_PATTERN)
_EFFECT_ID_PATTERN = r"^effect-[0-9a-f]{64}$"
_EFFECT_ID_RE = _re.compile(_EFFECT_ID_PATTERN)
_MONEY_PATTERN = r"^(0|[1-9][0-9]*)(\.[0-9]{1,6})?$"
_MONEY_RE = _re.compile(_MONEY_PATTERN)
_ACTOR_TYPES = (
    "user",
    "llm",
    "governor",
    "maintainer",
    "custodian_executor",
    "system",
    "amadeus",
)
_INPUT_TRUSTS = (
    "trusted_instruction",
    "user_data",
    "external_untrusted",
    "derived",
)
_DATA_CLASSES = ("public", "personal", "sensitive", "secret")
_EFFECT_CLASSES = ("E0", "E1", "E2", "E3")
_REVERSIBILITY_STATUSES = (
    "verified",
    "conditional",
    "irreversible",
    "unknown",
)
_RESULT_STATUSES = ("completed", "failed", "unknown")
_PATCH_OPERATIONS = ("add", "replace", "remove")
_RUN_PHASES = (
    "validation",
    "reset",
    "setup",
    "before_snapshot",
    "stimulus",
    "after_snapshot",
    "assertion",
    "cleanup",
    "completed",
)
_PRIMARY_ERROR_PHASES = _RUN_PHASES[:7]
_CLEANUP_STATUSES = ("completed", "failed")
_HUMAN_ORACLE_ORDER = tuple(
    kind for kind in _ORACLE_ORDER if kind in _HUMAN_ORACLES
)

_ACTOR_FIELDS = ("actor_type", "actor_id")
_EXPECTED_VERSION_FIELDS = ("target_record_ref", "expected_version")
_MUTATION_COMMAND_FIELDS = (
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
)
_INPUT_SOURCE_FIELDS = ("source_id", "trust")
_REVERSIBILITY_FIELDS = ("status", "rollback_plan", "rollback_deadline")
_BUDGET_FIELDS = ("calls", "money", "time")
_SCOPE_FIELDS = ("resources", "parameter_constraints")
_CONFIRMATION_FIELDS = (
    "required",
    "confirmation_id",
    "summary_checksum",
)
_ACTION_ENVELOPE_FIELDS = (
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
)
_STATE_PATCH_FIELDS = ("op", "path", "value")
_EFFECT_SEED_FIELDS = ("adapter_id", "operation", "target", "details")
_OBSERVED_EFFECT_FIELDS = (
    "effect_id",
    "adapter_id",
    "operation",
    "target",
    "details",
)
_EFFECT_PATTERN_FIELDS = ("adapter_id", "operation", "target", "details")
_DRIVER_RESULT_FIELDS = (
    "result_ref",
    "status",
    "error_code",
    "retryable",
    "output",
    "effects",
    "state_patch",
)
_HANDLER_RESULT_FIELDS = _DRIVER_RESULT_FIELDS[1:]
_STATE_SNAPSHOT_FIELDS = ("state", "state_sha256")
_ACTION_RECEIPT_FIELDS = (
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
)
_STEP_EXECUTION_FIELDS = (
    "step_id",
    "handler_id",
    "request_content_sha256",
    "pre_snapshot",
    "post_snapshot",
    "handler_output",
    "observed_effects",
    "receipt",
)
_EFFECT_DIFF_FIELDS = ("effects", "aggregate_sha256")
_ASSERTION_RESULT_FIELDS = (
    "assertion_id",
    "passed",
    "actual",
    "error_code",
)
_PRIMARY_ERROR_FIELDS = ("phase", "code", "message")
_CLEANUP_REPORT_FIELDS = (
    "attempted",
    "status",
    "residual_paths",
    "residual_effects",
    "error",
)
_SANDBOX_RUN_RESULT_FIELDS = (
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
)

_FIELD_ORDERS: _Mapping[str, tuple[str, ...]] = _MappingProxyType(
    {
        "actor": _ACTOR_FIELDS,
        "expected_version": _EXPECTED_VERSION_FIELDS,
        "mutation_command_envelope": _MUTATION_COMMAND_FIELDS,
        "input_source": _INPUT_SOURCE_FIELDS,
        "reversibility": _REVERSIBILITY_FIELDS,
        "budget": _BUDGET_FIELDS,
        "scope": _SCOPE_FIELDS,
        "confirmation": _CONFIRMATION_FIELDS,
        "action_envelope": _ACTION_ENVELOPE_FIELDS,
        "effect_rule": _EFFECT_FIELD_ORDER,
        "sandbox_profile": _SANDBOX_FIELD_ORDER,
        "rubric_requirement": _RUBRIC_FIELD_ORDER,
        "state_patch_operation": _STATE_PATCH_FIELDS,
        "effect_seed": _EFFECT_SEED_FIELDS,
        "observed_effect": _OBSERVED_EFFECT_FIELDS,
        "effect_pattern": _EFFECT_PATTERN_FIELDS,
        "driver_result": _DRIVER_RESULT_FIELDS,
        "handler_result": _HANDLER_RESULT_FIELDS,
        "setup_step": _STEP_FIELD_ORDER,
        "stimulus_step": _STEP_FIELD_ORDER,
        "machine_assertion": _ASSERTION_FIELD_ORDER,
        "state_snapshot": _STATE_SNAPSHOT_FIELDS,
        "action_receipt": _ACTION_RECEIPT_FIELDS,
        "step_execution": _STEP_EXECUTION_FIELDS,
        "effect_diff": _EFFECT_DIFF_FIELDS,
        "assertion_result": _ASSERTION_RESULT_FIELDS,
        "primary_error": _PRIMARY_ERROR_FIELDS,
        "cleanup_report": _CLEANUP_REPORT_FIELDS,
        "sandbox_run_result": _SANDBOX_RUN_RESULT_FIELDS,
    }
)
_EXACT_FIELDS: _Mapping[str, frozenset[str]] = _MappingProxyType(
    {name: frozenset(fields) for name, fields in _FIELD_ORDERS.items()}
)

_ISSUE_MESSAGES: _Mapping[str, str] = _MappingProxyType(
    {
        "assertion_result_invariant_invalid": (
            "assertion result passed and error_code fields are inconsistent"
        ),
        "cleanup_report_invariant_invalid": (
            "cleanup report status, residuals, and error are inconsistent"
        ),
        "confirmation_invariant_invalid": (
            "confirmation identifiers must agree with required"
        ),
        "effect_diff_hash_invalid": (
            "effect diff aggregate hash must match its canonical effects"
        ),
        "envelope_exact_fields_invalid": (
            "structural object fields must match the envelope contract exactly"
        ),
        "envelope_field_invalid": (
            "structural object field does not satisfy the envelope contract"
        ),
        "envelope_json_value_invalid": (
            "envelope value is outside the canonical JSON domain"
        ),
        "expected_versions_target_set_invalid": (
            "expected_versions must exactly cover unique target_record_refs"
        ),
        "receipt_invariant_invalid": (
            "receipt status, effects, replay, and state hashes are inconsistent"
        ),
        "result_invariant_invalid": (
            "result status, error, retry, effects, and patch are inconsistent"
        ),
        "reversibility_invariant_invalid": (
            "reversibility metadata is inconsistent with its status or effect"
        ),
        "sandbox_run_result_invariant_invalid": (
            "run phase, primary error, cleanup, assertions, and success disagree"
        ),
        "snapshot_hash_invalid": (
            "snapshot hash must match its canonical state"
        ),
        "state_patch_invariant_invalid": (
            "state patch path or operation-level invariant is invalid"
        ),
        "step_execution_invariant_invalid": (
            "step execution and receipt values must agree exactly"
        ),
    }
)


_Row = dict[str, object]
_IssueList = list[_ValidationIssue]
_EnvelopeValidator = _Callable[[object, str, _IssueList], None]


def _string_schema(
    *,
    nonempty: bool = False,
    pattern: str | None = None,
) -> dict[str, object]:
    schema: dict[str, object] = {"type": "string"}
    if nonempty:
        schema["minLength"] = 1
    if pattern is not None:
        schema["pattern"] = pattern
    return schema


def _array_schema(
    items: dict[str, object],
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": items}
    if nonempty:
        schema["minItems"] = 1
    if unique:
        schema["uniqueItems"] = True
    return schema


def _ref(name: str) -> dict[str, object]:
    return {"$ref": f"#/$defs/{name}"}


def _nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [schema, {"type": "null"}]}


def _detached_schema(value: object) -> object:
    if type(value) is dict:
        return {
            key: _detached_schema(item)
            for key, item in _cast(dict[str, object], value).items()
        }
    if type(value) is list:
        return [
            _detached_schema(item) for item in _cast(list[object], value)
        ]
    return value


def _object_schema(
    fields: tuple[str, ...],
    properties: dict[str, dict[str, object]],
    *,
    all_of: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if tuple(properties) != fields:
        raise AssertionError("schema property order differs from field order")
    schema: dict[str, object] = {
        "type": "object",
        "required": list(fields),
        "properties": _detached_schema(properties),
        "additionalProperties": False,
    }
    if all_of:
        schema["allOf"] = _detached_schema(all_of)
    return schema


def _status_condition(
    status: str,
    properties: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "if": {
            "properties": {"status": {"const": status}},
            "required": ["status"],
        },
        "then": {"properties": properties},
    }


def _result_conditions() -> list[dict[str, object]]:
    empty_effects = {"type": "array", "maxItems": 0}
    empty_patch = {"type": "array", "maxItems": 0}
    return [
        _status_condition(
            "completed",
            {
                "error_code": {"type": "null"},
                "retryable": {"const": False},
            },
        ),
        _status_condition(
            "failed",
            {
                "error_code": _string_schema(nonempty=True),
                "effects": empty_effects,
                "state_patch": empty_patch,
            },
        ),
        _status_condition(
            "unknown",
            {
                "error_code": {"const": "CORE-E-RESULT-UNKNOWN"},
                "retryable": {"const": False},
                "effects": empty_effects,
                "state_patch": empty_patch,
            },
        ),
    ]


def _receipt_conditions() -> list[dict[str, object]]:
    conditions = _result_conditions()
    for condition in conditions:
        then = _cast(
            dict[str, object],
            _cast(dict[str, object], condition["then"])["properties"],
        )
        then.pop("state_patch", None)
        if "effects" in then:
            then["observed_effects"] = then.pop("effects")
    conditions.append(
        _statusless_condition(
            "replayed",
            True,
            {"observed_effects": {"type": "array", "maxItems": 0}},
        )
    )
    return conditions


def _assertion_result_conditions() -> list[dict[str, object]]:
    return [
        {
            "if": {
                "properties": {"passed": {"const": True}},
                "required": ["passed"],
            },
            "then": {"properties": {"error_code": {"type": "null"}}},
            "else": {
                "properties": {
                    "error_code": _string_schema(nonempty=True),
                }
            },
        }
    ]


def _cleanup_conditions() -> list[dict[str, object]]:
    return [
        _status_condition(
            "completed",
            {
                "residual_paths": {"type": "array", "maxItems": 0},
                "residual_effects": {"type": "array", "maxItems": 0},
                "error": {"type": "null"},
            },
        ),
        {
            "if": {
                "properties": {"status": {"const": "failed"}},
                "required": ["status"],
            },
            "then": {
                "anyOf": [
                    {
                        "properties": {
                            "error": _string_schema(nonempty=True),
                        }
                    },
                    {"properties": {"residual_paths": {"minItems": 1}}},
                    {"properties": {"residual_effects": {"minItems": 1}}},
                ]
            },
        },
    ]


def _run_success_criteria() -> dict[str, object]:
    return {
        "properties": {
            "phase": {"const": "completed"},
            "primary_error": {"type": "null"},
            "assertion_results": {
                "items": {
                    "properties": {"passed": {"const": True}},
                    "required": ["passed"],
                }
            },
            "cleanup_report": {
                "properties": {"status": {"const": "completed"}},
                "required": ["status"],
            },
        },
        "required": [
            "phase",
            "primary_error",
            "assertion_results",
            "cleanup_report",
        ],
    }


def _run_conditions() -> list[dict[str, object]]:
    phase_relations: list[dict[str, object]] = []
    for phase in _PRIMARY_ERROR_PHASES:
        phase_relations.append(
            {
                "properties": {
                    "phase": {"const": phase},
                    "primary_error": {
                        "type": "object",
                        "properties": {"phase": {"const": phase}},
                        "required": ["phase"],
                    },
                },
                "required": ["phase", "primary_error"],
            }
        )
    phase_relations.extend(
        [
            {
                "properties": {
                    "phase": {"const": "cleanup"},
                    "primary_error": {"type": "null"},
                    "cleanup_report": {
                        "properties": {"status": {"const": "failed"}},
                        "required": ["status"],
                    },
                },
                "required": ["phase", "primary_error", "cleanup_report"],
            },
            _run_success_criteria(),
        ]
    )
    success = _run_success_criteria()
    conditions: list[dict[str, object]] = [
        {"oneOf": phase_relations},
        {
            "if": {
                "properties": {"succeeded": {"const": True}},
                "required": ["succeeded"],
            },
            "then": success,
            "else": {"not": _run_success_criteria()},
        },
    ]
    for phase in ("validation", "reset", "setup", "before_snapshot"):
        conditions.append(
            _statusless_condition(
                "phase",
                phase,
                {
                    "step_executions": {"type": "array", "maxItems": 0},
                    "before_snapshot": {"type": "null"},
                    "after_snapshot": {"type": "null"},
                    "effect_diff": {"type": "null"},
                    "assertion_results": {"type": "array", "maxItems": 0},
                },
            )
        )
    conditions.extend(
        [
            {
                "if": {
                    "properties": {"phase": {"const": "stimulus"}},
                    "required": ["phase"],
                },
                "then": {
                    "properties": {
                        "before_snapshot": {"type": "object"},
                        "assertion_results": {
                            "type": "array",
                            "maxItems": 0,
                        },
                    },
                    "oneOf": [
                        {
                            "properties": {
                                "after_snapshot": {"type": "object"},
                                "effect_diff": {"type": "object"},
                            }
                        },
                        {
                            "properties": {
                                "after_snapshot": {"type": "null"},
                                "effect_diff": {"type": "null"},
                            }
                        },
                    ],
                },
            },
            _statusless_condition(
                "phase",
                "after_snapshot",
                {
                    "before_snapshot": {"type": "object"},
                    "after_snapshot": {"type": "null"},
                    "effect_diff": {"type": "null"},
                    "assertion_results": {"type": "array", "maxItems": 0},
                },
            ),
        ]
    )
    for phase in ("assertion", "cleanup", "completed"):
        conditions.append(
            _statusless_condition(
                "phase",
                phase,
                {
                    "before_snapshot": {"type": "object"},
                    "after_snapshot": {"type": "object"},
                    "effect_diff": {"type": "object"},
                },
            )
        )
    return conditions


def _build_definitions() -> dict[str, object]:
    json_value: dict[str, object] = {
        "anyOf": [
            {"type": "null"},
            {"type": "boolean"},
            {"type": "integer"},
            {"type": "string"},
            _array_schema(_ref("json_value")),
            _ref("json_map"),
        ]
    }
    json_map: dict[str, object] = {
        "type": "object",
        "additionalProperties": _ref("json_value"),
    }
    json_pointer = _string_schema(pattern=_JSON_POINTER_PATTERN)
    actor = _object_schema(
        _ACTOR_FIELDS,
        {
            "actor_type": {"enum": list(_ACTOR_TYPES)},
            "actor_id": _string_schema(nonempty=True),
        },
    )
    expected_version = _object_schema(
        _EXPECTED_VERSION_FIELDS,
        {
            "target_record_ref": _string_schema(nonempty=True),
            "expected_version": {
                "anyOf": [
                    {"const": "absent"},
                    {"type": "integer", "minimum": 0},
                ]
            },
        },
    )
    mutation_command = _object_schema(
        _MUTATION_COMMAND_FIELDS,
        {
            "command_id": _string_schema(nonempty=True),
            "command_type": _string_schema(nonempty=True),
            "actor": _ref("actor"),
            "actor_capability_id": _string_schema(nonempty=True),
            "expected_versions": _array_schema(_ref("expected_version")),
            "audit_context_id": _string_schema(nonempty=True),
            "idempotency_key": _string_schema(nonempty=True),
            "issued_at": _string_schema(pattern=_UTC_RFC3339_RE.pattern),
            "target_record_refs": _array_schema(
                _string_schema(nonempty=True),
                nonempty=True,
                unique=True,
            ),
            "payload": _ref("json_map"),
        },
    )
    input_source = _object_schema(
        _INPUT_SOURCE_FIELDS,
        {
            "source_id": _string_schema(),
            "trust": {"enum": list(_INPUT_TRUSTS)},
        },
    )
    reversibility = _object_schema(
        _REVERSIBILITY_FIELDS,
        {
            "status": {"enum": list(_REVERSIBILITY_STATUSES)},
            "rollback_plan": _nullable(_string_schema()),
            "rollback_deadline": _nullable(
                _string_schema(pattern=_UTC_RFC3339_RE.pattern)
            ),
        },
        all_of=[
            _status_condition(
                "verified",
                {
                    "rollback_plan": _string_schema(nonempty=True),
                    "rollback_deadline": _string_schema(
                        pattern=_UTC_RFC3339_RE.pattern
                    ),
                },
            ),
            _status_condition(
                "irreversible",
                {
                    "rollback_plan": {"type": "null"},
                    "rollback_deadline": {"type": "null"},
                },
            ),
        ],
    )
    budget = _object_schema(
        _BUDGET_FIELDS,
        {
            "calls": {"type": "integer", "minimum": 0},
            "money": _string_schema(pattern=_MONEY_PATTERN),
            "time": {"type": "integer", "minimum": 0},
        },
    )
    scope = _object_schema(
        _SCOPE_FIELDS,
        {
            "resources": _array_schema(_string_schema()),
            "parameter_constraints": _ref("json_map"),
        },
    )
    confirmation = _object_schema(
        _CONFIRMATION_FIELDS,
        {
            "required": {"type": "boolean"},
            "confirmation_id": _nullable(_string_schema()),
            "summary_checksum": _nullable(_string_schema()),
        },
        all_of=[
            {
                "if": {
                    "properties": {"required": {"const": True}},
                    "required": ["required"],
                },
                "then": {
                    "properties": {
                        "confirmation_id": _string_schema(nonempty=True),
                        "summary_checksum": _string_schema(nonempty=True),
                    }
                },
                "else": {
                    "properties": {
                        "confirmation_id": {"type": "null"},
                        "summary_checksum": {"type": "null"},
                    }
                },
            }
        ],
    )
    uuid = _string_schema(pattern=_UUID_PATTERN)
    action_envelope = _object_schema(
        _ACTION_ENVELOPE_FIELDS,
        {
            "action_id": uuid,
            "identity_id": uuid,
            "lineage_id": uuid,
            "branch_id": uuid,
            "vault_id": _nullable(uuid),
            "user_id": _string_schema(nonempty=True),
            "session_id": _string_schema(nonempty=True),
            "task_id": _string_schema(nonempty=True),
            "candidate_intent_id": _string_schema(nonempty=True),
            "intent_summary": _string_schema(nonempty=True),
            "tool_id": _string_schema(nonempty=True),
            "operation": _string_schema(nonempty=True),
            "parameters": _ref("json_map"),
            "targets": _array_schema(_string_schema(), unique=True),
            "destinations": _array_schema(_string_schema(), unique=True),
            "input_sources": _array_schema(
                _ref("input_source"),
                nonempty=True,
            ),
            "data_classes": _array_schema(
                {"enum": list(_DATA_CLASSES)},
                unique=True,
            ),
            "expected_effects": _array_schema(_ref("json_map")),
            "effect_class": {"enum": list(_EFFECT_CLASSES)},
            "reversibility": _ref("reversibility"),
            "expected_state_diff": _ref("json_map"),
            "budget": _ref("budget"),
            "scope": _ref("scope"),
            "expires_at": _string_schema(pattern=_UTC_RFC3339_RE.pattern),
            "max_uses": {"type": "integer", "minimum": 1},
            "idempotency_key": _string_schema(nonempty=True),
            "confirmation": _ref("confirmation"),
            "policy_version": _string_schema(nonempty=True),
        },
        all_of=[
            {
                "if": {
                    "properties": {
                        "reversibility": {
                            "properties": {
                                "status": {"const": "unknown"},
                            },
                            "required": ["status"],
                        }
                    },
                    "required": ["reversibility"],
                },
                "then": {
                    "properties": {"effect_class": {"const": "E3"}},
                },
            }
        ],
    )
    effect_rule = _object_schema(
        _EFFECT_FIELD_ORDER,
        {
            "adapter_id": {"enum": list(_ADAPTER_ID_ORDER)},
            "operation": _string_schema(),
            "target": _string_schema(),
        },
    )
    sandbox_profile = _object_schema(
        _SANDBOX_FIELD_ORDER,
        {
            "profile_id": _string_schema(),
            "allowed_effects": _array_schema(
                _ref("effect_rule"),
                unique=True,
            ),
            "fixed_clock": _string_schema(pattern=_UTC_RFC3339_RE.pattern),
            "id_seed": _string_schema(),
            "reset_policy": {"const": "fresh_context"},
            "cleanup_policy": {"const": "always"},
        },
    )
    rubric_requirement = _object_schema(
        _RUBRIC_FIELD_ORDER,
        {
            "criterion_id": _string_schema(pattern=_IDENTIFIER_RE.pattern),
            "oracle_kind": {"enum": list(_HUMAN_ORACLE_ORDER)},
            "question": _string_schema(),
            "evidence_case_json_pointers": _array_schema(
                _ref("json_pointer"),
                nonempty=True,
                unique=True,
            ),
            "allowed_scores": _array_schema(
                {"type": "integer"},
                nonempty=True,
                unique=True,
            ),
            "passing_scores": _array_schema(
                {"type": "integer"},
                nonempty=True,
                unique=True,
            ),
        },
    )
    state_patch = _object_schema(
        _STATE_PATCH_FIELDS,
        {
            "op": {"enum": list(_PATCH_OPERATIONS)},
            "path": {
                "type": "string",
                "minLength": 1,
                "pattern": _JSON_POINTER_PATTERN,
            },
            "value": _ref("json_value"),
        },
        all_of=[
            _statusless_condition(
                "op",
                "remove",
                {"value": {"type": "null"}},
            )
        ],
    )
    effect_seed = _object_schema(
        _EFFECT_SEED_FIELDS,
        {
            "adapter_id": {"enum": list(_ADAPTER_ID_ORDER)},
            "operation": _string_schema(),
            "target": _string_schema(),
            "details": _ref("json_map"),
        },
    )
    observed_effect = _object_schema(
        _OBSERVED_EFFECT_FIELDS,
        {
            "effect_id": _string_schema(pattern=_EFFECT_ID_PATTERN),
            "adapter_id": {"enum": list(_ADAPTER_ID_ORDER)},
            "operation": _string_schema(),
            "target": _string_schema(),
            "details": _ref("json_map"),
        },
    )
    effect_pattern = _object_schema(
        _EFFECT_PATTERN_FIELDS,
        {
            "adapter_id": {"enum": list(_ADAPTER_ID_ORDER)},
            "operation": _nullable(_string_schema()),
            "target": _nullable(_string_schema()),
            "details": _ref("json_map"),
        },
    )
    result_properties: dict[str, dict[str, object]] = {
        "status": {"enum": list(_RESULT_STATUSES)},
        "error_code": _nullable(_string_schema()),
        "retryable": {"type": "boolean"},
        "output": _ref("json_value"),
        "effects": _array_schema(_ref("effect_seed")),
        "state_patch": _array_schema(_ref("state_patch_operation")),
    }
    driver_result = _object_schema(
        _DRIVER_RESULT_FIELDS,
        {"result_ref": _string_schema(), **result_properties},
        all_of=_result_conditions(),
    )
    handler_result = _object_schema(
        _HANDLER_RESULT_FIELDS,
        result_properties,
        all_of=_result_conditions(),
    )
    setup_step = _object_schema(
        _STEP_FIELD_ORDER,
        {
            "sequence": {"type": "integer", "minimum": 1},
            "step_id": _string_schema(pattern=_IDENTIFIER_RE.pattern),
            "handler_id": {"enum": list(_SETUP_HANDLER_ORDER)},
            "params": _ref("json_map"),
        },
    )
    stimulus_step = _object_schema(
        _STEP_FIELD_ORDER,
        {
            "sequence": {"type": "integer", "minimum": 1},
            "step_id": _string_schema(pattern=_IDENTIFIER_RE.pattern),
            "handler_id": {"enum": list(_STIMULUS_HANDLER_ORDER)},
            "params": _ref("json_map"),
        },
    )
    machine_assertion = _object_schema(
        _ASSERTION_FIELD_ORDER,
        {
            "sequence": {"type": "integer", "minimum": 1},
            "assertion_id": _string_schema(pattern=_IDENTIFIER_RE.pattern),
            "handler_id": {"enum": list(_ASSERTION_HANDLER_ORDER)},
            "step_id": _string_schema(pattern=_IDENTIFIER_RE.pattern),
            "params": _ref("json_map"),
        },
    )
    state_snapshot = _object_schema(
        _STATE_SNAPSHOT_FIELDS,
        {
            "state": _ref("json_map"),
            "state_sha256": _string_schema(pattern=_SHA256_PATTERN),
        },
    )
    action_receipt = _object_schema(
        _ACTION_RECEIPT_FIELDS,
        {
            "schema_version": {"const": _SCHEMA_VERSION},
            "case_id": _string_schema(),
            "step_id": _string_schema(),
            "action_id": _string_schema(),
            "handler_id": _string_schema(),
            "status": {"enum": list(_RESULT_STATUSES)},
            "error_code": _nullable(_string_schema()),
            "retryable": {"type": "boolean"},
            "pre_state_sha256": _string_schema(pattern=_SHA256_PATTERN),
            "post_state_sha256": _string_schema(pattern=_SHA256_PATTERN),
            "handler_output_sha256": _string_schema(pattern=_SHA256_PATTERN),
            "observed_effects": _array_schema(_ref("observed_effect")),
            "idempotency_key": _nullable(_string_schema()),
            "request_content_sha256": _string_schema(pattern=_SHA256_PATTERN),
            "replayed": {"type": "boolean"},
        },
        all_of=_receipt_conditions(),
    )
    step_execution = _object_schema(
        _STEP_EXECUTION_FIELDS,
        {
            "step_id": _string_schema(),
            "handler_id": _string_schema(),
            "request_content_sha256": _string_schema(pattern=_SHA256_PATTERN),
            "pre_snapshot": _ref("state_snapshot"),
            "post_snapshot": _ref("state_snapshot"),
            "handler_output": _ref("json_value"),
            "observed_effects": _array_schema(_ref("observed_effect")),
            "receipt": _ref("action_receipt"),
        },
    )
    effect_diff = _object_schema(
        _EFFECT_DIFF_FIELDS,
        {
            "effects": _array_schema(_ref("observed_effect")),
            "aggregate_sha256": _string_schema(pattern=_SHA256_PATTERN),
        },
    )
    assertion_result = _object_schema(
        _ASSERTION_RESULT_FIELDS,
        {
            "assertion_id": _string_schema(),
            "passed": {"type": "boolean"},
            "actual": _ref("json_value"),
            "error_code": _nullable(_string_schema()),
        },
        all_of=_assertion_result_conditions(),
    )
    primary_error = _object_schema(
        _PRIMARY_ERROR_FIELDS,
        {
            "phase": {"enum": list(_PRIMARY_ERROR_PHASES)},
            "code": _string_schema(),
            "message": _string_schema(),
        },
    )
    cleanup_report = _object_schema(
        _CLEANUP_REPORT_FIELDS,
        {
            "attempted": {"const": True},
            "status": {"enum": list(_CLEANUP_STATUSES)},
            "residual_paths": _array_schema(_string_schema()),
            "residual_effects": _array_schema(_ref("observed_effect")),
            "error": _nullable(_string_schema()),
        },
        all_of=_cleanup_conditions(),
    )
    sandbox_run_result = _object_schema(
        _SANDBOX_RUN_RESULT_FIELDS,
        {
            "schema_version": {"const": _SCHEMA_VERSION},
            "case_id": _string_schema(),
            "phase": {"enum": list(_RUN_PHASES)},
            "step_executions": _array_schema(_ref("step_execution")),
            "before_snapshot": _nullable(_ref("state_snapshot")),
            "after_snapshot": _nullable(_ref("state_snapshot")),
            "effect_diff": _nullable(_ref("effect_diff")),
            "assertion_results": _array_schema(_ref("assertion_result")),
            "primary_error": _nullable(_ref("primary_error")),
            "cleanup_report": _ref("cleanup_report"),
            "succeeded": {"type": "boolean"},
        },
        all_of=_run_conditions(),
    )
    return {
        "json_value": json_value,
        "json_map": json_map,
        "json_pointer": json_pointer,
        "actor": actor,
        "expected_version": expected_version,
        "mutation_command_envelope": mutation_command,
        "input_source": input_source,
        "reversibility": reversibility,
        "budget": budget,
        "scope": scope,
        "confirmation": confirmation,
        "action_envelope": action_envelope,
        "effect_rule": effect_rule,
        "sandbox_profile": sandbox_profile,
        "rubric_requirement": rubric_requirement,
        "state_patch_operation": state_patch,
        "effect_seed": effect_seed,
        "observed_effect": observed_effect,
        "effect_pattern": effect_pattern,
        "driver_result": driver_result,
        "handler_result": handler_result,
        "setup_step": setup_step,
        "stimulus_step": stimulus_step,
        "machine_assertion": machine_assertion,
        "state_snapshot": state_snapshot,
        "action_receipt": action_receipt,
        "step_execution": step_execution,
        "effect_diff": effect_diff,
        "assertion_result": assertion_result,
        "primary_error": primary_error,
        "cleanup_report": cleanup_report,
        "sandbox_run_result": sandbox_run_result,
    }


def _statusless_condition(
    field: str,
    expected: object,
    properties: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "if": {
            "properties": {field: {"const": expected}},
            "required": [field],
        },
        "then": {"properties": properties},
    }


def build_fixture_case_schema() -> dict[str, object]:
    oracle_combinations = [
        list(combination)
        for mask in range(1, 1 << len(_ORACLE_ORDER))
        for combination in [
            tuple(
                kind
                for index, kind in enumerate(_ORACLE_ORDER)
                if mask & (1 << index)
            )
        ]
    ]
    properties: dict[str, dict[str, object]] = {
        "schema_version": {"const": _SCHEMA_VERSION},
        "case_id": _string_schema(),
        "source_id": _string_schema(),
        "source_clause_id": _string_schema(pattern=_CLAUSE_ID_RE.pattern),
        "oracle_kinds": {"enum": oracle_combinations},
        "setup_steps": _array_schema(_ref("setup_step")),
        "stimulus_steps": _array_schema(_ref("stimulus_step")),
        "machine_assertions": _array_schema(_ref("machine_assertion")),
        "rubric_requirements": _array_schema(_ref("rubric_requirement")),
        "sandbox_profile": _nullable(_ref("sandbox_profile")),
    }
    schema: dict[str, object] = {
        "$schema": _JSON_SCHEMA_URI,
        "title": "Amadeus Stage 0C Fixture Case v0.1",
        "type": "object",
        "required": list(_CASE_FIELD_ORDER),
        "properties": properties,
        "additionalProperties": False,
        "$defs": _build_definitions(),
    }
    return _deepcopy(schema)


def _pointer(parent: str, token: str | int) -> str:
    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _add_issue(issues: _IssueList, pointer: str, code: str) -> None:
    issues.append(_ValidationIssue(pointer, code, _ISSUE_MESSAGES[code]))


def _finish(issues: _IssueList) -> list[_ValidationIssue]:
    triples = {
        (issue.json_pointer, issue.code, issue.message) for issue in issues
    }
    return [_ValidationIssue(*triple) for triple in sorted(triples)]


def _field_invalid(issues: _IssueList, pointer: str, field: str) -> None:
    _add_issue(
        issues,
        _pointer(pointer, field),
        "envelope_field_invalid",
    )


def _exact_row(
    kind: str,
    value: object,
    pointer: str,
    issues: _IssueList,
) -> _Row | None:
    if type(value) is not dict or set(value) != _EXACT_FIELDS[kind]:
        _add_issue(issues, pointer, "envelope_exact_fields_invalid")
        return None
    return _cast(_Row, value)


def _is_string(value: object, *, nonempty: bool = False) -> bool:
    return type(value) is str and (not nonempty or bool(value))


def _is_uuid(value: object) -> bool:
    return type(value) is str and _UUID_RE.fullmatch(value) is not None


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256_RE.fullmatch(value) is not None


def _is_money(value: object) -> bool:
    return type(value) is str and _MONEY_RE.fullmatch(value) is not None


def _is_identifier(value: object) -> bool:
    return (
        type(value) is str
        and _IDENTIFIER_RE.fullmatch(value) is not None
    )


def _is_nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_positive_integer(value: object) -> bool:
    return type(value) is int and value >= 1


def _string_list_is_valid(
    value: object,
    *,
    nonempty: bool = False,
    unique: bool = False,
    items_nonempty: bool = False,
) -> bool:
    if type(value) is not list or (nonempty and not value):
        return False
    items = _cast(list[object], value)
    if not all(_is_string(item, nonempty=items_nonempty) for item in items):
        return False
    strings = _cast(list[str], items)
    return not unique or len(strings) == len(set(strings))


def _unique_json_items(value: list[object]) -> bool:
    fingerprints = [
        _canonical_bytes(_cast(_Any, item)) for item in value
    ]
    return len(fingerprints) == len(set(fingerprints))


def _validate_actor(value: object, pointer: str, issues: _IssueList) -> None:
    row = _exact_row("actor", value, pointer, issues)
    if row is None:
        return
    if row["actor_type"] not in _ACTOR_TYPES:
        _field_invalid(issues, pointer, "actor_type")
    if not _is_string(row["actor_id"], nonempty=True):
        _field_invalid(issues, pointer, "actor_id")


def _validate_expected_version(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("expected_version", value, pointer, issues)
    if row is None:
        return
    if not _is_string(row["target_record_ref"], nonempty=True):
        _field_invalid(issues, pointer, "target_record_ref")
    expected = row["expected_version"]
    if expected != "absent" and not _is_nonnegative_integer(expected):
        _field_invalid(issues, pointer, "expected_version")


def _validate_mutation_command(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("mutation_command_envelope", value, pointer, issues)
    if row is None:
        return
    for field in (
        "command_id",
        "command_type",
        "actor_capability_id",
        "audit_context_id",
        "idempotency_key",
    ):
        if not _is_string(row[field], nonempty=True):
            _field_invalid(issues, pointer, field)
    _validate_actor(row["actor"], _pointer(pointer, "actor"), issues)
    if not _fixed_clock_is_valid(row["issued_at"]):
        _field_invalid(issues, pointer, "issued_at")
    if type(row["payload"]) is not dict:
        _field_invalid(issues, pointer, "payload")

    targets_valid = _string_list_is_valid(
        row["target_record_refs"],
        nonempty=True,
        unique=True,
        items_nonempty=True,
    )
    if not targets_valid:
        _field_invalid(issues, pointer, "target_record_refs")

    expected_value = row["expected_versions"]
    if type(expected_value) is not list:
        _field_invalid(issues, pointer, "expected_versions")
        return
    expected_rows = _cast(list[object], expected_value)
    for index, expected in enumerate(expected_rows):
        _validate_expected_version(
            expected,
            _pointer(_pointer(pointer, "expected_versions"), index),
            issues,
        )

    refs_valid = all(
        type(expected) is dict
        and set(expected) == _EXACT_FIELDS["expected_version"]
        and _is_string(
            _cast(_Row, expected)["target_record_ref"],
            nonempty=True,
        )
        for expected in expected_rows
    )
    if not targets_valid or not refs_valid:
        return
    target_refs = _cast(list[str], row["target_record_refs"])
    expected_refs = [
        _cast(str, _cast(_Row, expected)["target_record_ref"])
        for expected in expected_rows
    ]
    if (
        len(expected_refs) != len(target_refs)
        or len(expected_refs) != len(set(expected_refs))
        or set(expected_refs) != set(target_refs)
    ):
        _add_issue(
            issues,
            _pointer(pointer, "expected_versions"),
            "expected_versions_target_set_invalid",
        )


def _validate_input_source(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("input_source", value, pointer, issues)
    if row is None:
        return
    if not _is_string(row["source_id"]):
        _field_invalid(issues, pointer, "source_id")
    if row["trust"] not in _INPUT_TRUSTS:
        _field_invalid(issues, pointer, "trust")


def _validate_reversibility(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("reversibility", value, pointer, issues)
    if row is None:
        return
    status = row["status"]
    plan = row["rollback_plan"]
    deadline = row["rollback_deadline"]
    scalar_valid = True
    if status not in _REVERSIBILITY_STATUSES:
        _field_invalid(issues, pointer, "status")
        scalar_valid = False
    if plan is not None and type(plan) is not str:
        _field_invalid(issues, pointer, "rollback_plan")
        scalar_valid = False
    if deadline is not None and not _fixed_clock_is_valid(deadline):
        _field_invalid(issues, pointer, "rollback_deadline")
        scalar_valid = False
    if not scalar_valid:
        return
    if status == "verified" and not (
        _is_string(plan, nonempty=True) and _fixed_clock_is_valid(deadline)
    ):
        _add_issue(issues, pointer, "reversibility_invariant_invalid")
    if status == "irreversible" and (plan is not None or deadline is not None):
        _add_issue(issues, pointer, "reversibility_invariant_invalid")


def _validate_budget(value: object, pointer: str, issues: _IssueList) -> None:
    row = _exact_row("budget", value, pointer, issues)
    if row is None:
        return
    for field in ("calls", "time"):
        if not _is_nonnegative_integer(row[field]):
            _field_invalid(issues, pointer, field)
    if not _is_money(row["money"]):
        _field_invalid(issues, pointer, "money")


def _validate_scope(value: object, pointer: str, issues: _IssueList) -> None:
    row = _exact_row("scope", value, pointer, issues)
    if row is None:
        return
    if not _string_list_is_valid(row["resources"]):
        _field_invalid(issues, pointer, "resources")
    if type(row["parameter_constraints"]) is not dict:
        _field_invalid(issues, pointer, "parameter_constraints")


def _validate_confirmation(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("confirmation", value, pointer, issues)
    if row is None:
        return
    required = row["required"]
    confirmation_id = row["confirmation_id"]
    checksum = row["summary_checksum"]
    scalar_valid = True
    if type(required) is not bool:
        _field_invalid(issues, pointer, "required")
        scalar_valid = False
    for field, item in (
        ("confirmation_id", confirmation_id),
        ("summary_checksum", checksum),
    ):
        if item is not None and type(item) is not str:
            _field_invalid(issues, pointer, field)
            scalar_valid = False
    if not scalar_valid:
        return
    if required is True:
        valid = _is_string(confirmation_id, nonempty=True) and _is_string(
            checksum,
            nonempty=True,
        )
    else:
        valid = confirmation_id is None and checksum is None
    if not valid:
        _add_issue(issues, pointer, "confirmation_invariant_invalid")


def _validate_action_envelope(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("action_envelope", value, pointer, issues)
    if row is None:
        return
    for field in ("action_id", "identity_id", "lineage_id", "branch_id"):
        if not _is_uuid(row[field]):
            _field_invalid(issues, pointer, field)
    if row["vault_id"] is not None and not _is_uuid(row["vault_id"]):
        _field_invalid(issues, pointer, "vault_id")
    for field in (
        "user_id",
        "session_id",
        "task_id",
        "candidate_intent_id",
        "intent_summary",
        "tool_id",
        "operation",
        "idempotency_key",
        "policy_version",
    ):
        if not _is_string(row[field], nonempty=True):
            _field_invalid(issues, pointer, field)
    for field in ("parameters", "expected_state_diff"):
        if type(row[field]) is not dict:
            _field_invalid(issues, pointer, field)
    for field in ("targets", "destinations"):
        if not _string_list_is_valid(row[field], unique=True):
            _field_invalid(issues, pointer, field)

    input_sources = row["input_sources"]
    if type(input_sources) is not list or not input_sources:
        _field_invalid(issues, pointer, "input_sources")
    else:
        for index, source in enumerate(_cast(list[object], input_sources)):
            _validate_input_source(
                source,
                _pointer(_pointer(pointer, "input_sources"), index),
                issues,
            )

    data_classes = row["data_classes"]
    if (
        type(data_classes) is not list
        or not all(item in _DATA_CLASSES for item in data_classes)
        or len(data_classes) != len(set(_cast(list[str], data_classes)))
    ):
        _field_invalid(issues, pointer, "data_classes")

    expected_effects = row["expected_effects"]
    if type(expected_effects) is not list or not all(
        type(item) is dict for item in _cast(list[object], expected_effects)
    ):
        _field_invalid(issues, pointer, "expected_effects")
    if row["effect_class"] not in _EFFECT_CLASSES:
        _field_invalid(issues, pointer, "effect_class")

    reversibility_pointer = _pointer(pointer, "reversibility")
    _validate_reversibility(row["reversibility"], reversibility_pointer, issues)
    _validate_budget(row["budget"], _pointer(pointer, "budget"), issues)
    _validate_scope(row["scope"], _pointer(pointer, "scope"), issues)
    if not _fixed_clock_is_valid(row["expires_at"]):
        _field_invalid(issues, pointer, "expires_at")
    if not _is_positive_integer(row["max_uses"]):
        _field_invalid(issues, pointer, "max_uses")
    _validate_confirmation(
        row["confirmation"],
        _pointer(pointer, "confirmation"),
        issues,
    )

    reversibility = row["reversibility"]
    if (
        type(reversibility) is dict
        and set(reversibility) == _EXACT_FIELDS["reversibility"]
        and reversibility["status"] == "unknown"
        and row["effect_class"] != "E3"
    ):
        _add_issue(
            issues,
            _pointer(pointer, "effect_class"),
            "reversibility_invariant_invalid",
        )


def _validate_effect_rule(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("effect_rule", value, pointer, issues)
    if row is None:
        return
    if (
        type(row["adapter_id"]) is not str
        or row["adapter_id"] not in _ADAPTER_IDS
    ):
        _field_invalid(issues, pointer, "adapter_id")
    for field in ("operation", "target"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)


def _validate_sandbox_profile(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("sandbox_profile", value, pointer, issues)
    if row is None:
        return
    for field in ("profile_id", "id_seed"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)
    if not _fixed_clock_is_valid(row["fixed_clock"]):
        _field_invalid(issues, pointer, "fixed_clock")
    if row["reset_policy"] != "fresh_context":
        _field_invalid(issues, pointer, "reset_policy")
    if row["cleanup_policy"] != "always":
        _field_invalid(issues, pointer, "cleanup_policy")
    effects = row["allowed_effects"]
    if type(effects) is not list:
        _field_invalid(issues, pointer, "allowed_effects")
        return
    effect_items = _cast(list[object], effects)
    if not _unique_json_items(effect_items):
        _field_invalid(issues, pointer, "allowed_effects")
    for index, effect in enumerate(effect_items):
        _validate_effect_rule(
            effect,
            _pointer(_pointer(pointer, "allowed_effects"), index),
            issues,
        )


def _scores_are_valid(value: object) -> bool:
    if type(value) is not list or not value:
        return False
    scores = _cast(list[object], value)
    if not all(type(score) is int for score in scores):
        return False
    integers = _cast(list[int], scores)
    return integers == sorted(integers) and len(integers) == len(set(integers))


def _validate_rubric_requirement(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("rubric_requirement", value, pointer, issues)
    if row is None:
        return
    if not _is_identifier(row["criterion_id"]):
        _field_invalid(issues, pointer, "criterion_id")
    if (
        type(row["oracle_kind"]) is not str
        or row["oracle_kind"] not in _HUMAN_ORACLES
    ):
        _field_invalid(issues, pointer, "oracle_kind")
    if not _is_string(row["question"]):
        _field_invalid(issues, pointer, "question")

    evidence = row["evidence_case_json_pointers"]
    evidence_valid = _string_list_is_valid(
        evidence,
        nonempty=True,
        unique=True,
    )
    if evidence_valid:
        evidence_strings = _cast(list[str], evidence)
        evidence_valid = (
            evidence_strings == sorted(evidence_strings)
            and all(
                _json_pointer_syntax_is_valid(item)
                for item in evidence_strings
            )
        )
    if not evidence_valid:
        _field_invalid(issues, pointer, "evidence_case_json_pointers")

    allowed_valid = _scores_are_valid(row["allowed_scores"])
    passing_valid = _scores_are_valid(row["passing_scores"])
    if not allowed_valid:
        _field_invalid(issues, pointer, "allowed_scores")
    if not passing_valid or (
        allowed_valid
        and not set(_cast(list[int], row["passing_scores"])).issubset(
            _cast(list[int], row["allowed_scores"])
        )
    ):
        _field_invalid(issues, pointer, "passing_scores")


def _validate_state_patch_operation(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("state_patch_operation", value, pointer, issues)
    if row is None:
        return
    if row["op"] not in _PATCH_OPERATIONS:
        _field_invalid(issues, pointer, "op")
    path = row["path"]
    if type(path) is not str or not _json_pointer_syntax_is_valid(path):
        _field_invalid(issues, pointer, "path")
    elif path == "":
        _add_issue(
            issues,
            _pointer(pointer, "path"),
            "state_patch_invariant_invalid",
        )
    # Whether a token targets an array depends on the pre-state.  The F06
    # envelope gate preserves numeric map keys; the transactional patch
    # applier performs the state-aware array-parent rejection.
    if row["op"] == "remove" and row["value"] is not None:
        _add_issue(
            issues,
            _pointer(pointer, "value"),
            "state_patch_invariant_invalid",
        )


def _validate_effect_seed(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("effect_seed", value, pointer, issues)
    if row is None:
        return
    if (
        type(row["adapter_id"]) is not str
        or row["adapter_id"] not in _ADAPTER_IDS
    ):
        _field_invalid(issues, pointer, "adapter_id")
    for field in ("operation", "target"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)
    if type(row["details"]) is not dict:
        _field_invalid(issues, pointer, "details")


def _validate_observed_effect(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("observed_effect", value, pointer, issues)
    if row is None:
        return
    effect_id = row["effect_id"]
    if type(effect_id) is not str or _EFFECT_ID_RE.fullmatch(effect_id) is None:
        _field_invalid(issues, pointer, "effect_id")
    seed = {field: row[field] for field in _EFFECT_SEED_FIELDS}
    _validate_effect_seed(seed, pointer, issues)


def _validate_effect_pattern(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("effect_pattern", value, pointer, issues)
    if row is None:
        return
    if (
        type(row["adapter_id"]) is not str
        or row["adapter_id"] not in _ADAPTER_IDS
    ):
        _field_invalid(issues, pointer, "adapter_id")
    for field in ("operation", "target"):
        item = row[field]
        if item is not None and type(item) is not str:
            _field_invalid(issues, pointer, field)
    if type(row["details"]) is not dict:
        _field_invalid(issues, pointer, "details")


def _validate_patch_collection(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> bool:
    if type(value) is not list:
        _add_issue(issues, pointer, "envelope_field_invalid")
        return False
    patches = _cast(list[object], value)
    for index, patch in enumerate(patches):
        _validate_state_patch_operation(
            patch,
            _pointer(pointer, index),
            issues,
        )
    paths_valid = all(
        type(patch) is dict
        and set(patch) == _EXACT_FIELDS["state_patch_operation"]
        and type(_cast(_Row, patch)["path"]) is str
        for patch in patches
    )
    if paths_valid:
        paths = [_cast(_Row, patch)["path"] for patch in patches]
        if len(paths) != len(set(paths)):
            _add_issue(issues, pointer, "state_patch_invariant_invalid")
    return True


def _validate_effect_seed_collection(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> bool:
    if type(value) is not list:
        _add_issue(issues, pointer, "envelope_field_invalid")
        return False
    for index, effect in enumerate(_cast(list[object], value)):
        _validate_effect_seed(effect, _pointer(pointer, index), issues)
    return True


def _validate_observed_effect_collection(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> bool:
    if type(value) is not list:
        _add_issue(issues, pointer, "envelope_field_invalid")
        return False
    for index, effect in enumerate(_cast(list[object], value)):
        _validate_observed_effect(effect, _pointer(pointer, index), issues)
    return True


def _validate_result(
    kind: str,
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row(kind, value, pointer, issues)
    if row is None:
        return
    if kind == "driver_result" and not _is_string(row["result_ref"]):
        _field_invalid(issues, pointer, "result_ref")
    status = row["status"]
    error = row["error_code"]
    retryable = row["retryable"]
    scalar_valid = True
    if status not in _RESULT_STATUSES:
        _field_invalid(issues, pointer, "status")
        scalar_valid = False
    if error is not None and type(error) is not str:
        _field_invalid(issues, pointer, "error_code")
        scalar_valid = False
    if type(retryable) is not bool:
        _field_invalid(issues, pointer, "retryable")
        scalar_valid = False
    effects_valid = _validate_effect_seed_collection(
        row["effects"],
        _pointer(pointer, "effects"),
        issues,
    )
    patch_valid = _validate_patch_collection(
        row["state_patch"],
        _pointer(pointer, "state_patch"),
        issues,
    )
    if not scalar_valid or not effects_valid or not patch_valid:
        return
    effects = _cast(list[object], row["effects"])
    patches = _cast(list[object], row["state_patch"])
    invariant_valid = (
        status == "completed"
        and error is None
        and retryable is False
    ) or (
        status == "failed"
        and _is_string(error, nonempty=True)
        and not effects
        and not patches
    ) or (
        status == "unknown"
        and error == "CORE-E-RESULT-UNKNOWN"
        and retryable is False
        and not effects
        and not patches
    )
    if not invariant_valid:
        _add_issue(
            issues,
            _pointer(pointer, "status"),
            "result_invariant_invalid",
        )


def _validate_driver_result(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    _validate_result("driver_result", value, pointer, issues)


def _validate_handler_result(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    _validate_result("handler_result", value, pointer, issues)


def _validate_step(
    kind: str,
    handlers: tuple[str, ...],
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row(kind, value, pointer, issues)
    if row is None:
        return
    if not _is_positive_integer(row["sequence"]):
        _field_invalid(issues, pointer, "sequence")
    if not _is_identifier(row["step_id"]):
        _field_invalid(issues, pointer, "step_id")
    if row["handler_id"] not in handlers:
        _field_invalid(issues, pointer, "handler_id")
    if type(row["params"]) is not dict:
        _field_invalid(issues, pointer, "params")


def _validate_setup_step(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    _validate_step(
        "setup_step",
        _SETUP_HANDLER_ORDER,
        value,
        pointer,
        issues,
    )


def _validate_stimulus_step(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    _validate_step(
        "stimulus_step",
        _STIMULUS_HANDLER_ORDER,
        value,
        pointer,
        issues,
    )


def _validate_machine_assertion(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("machine_assertion", value, pointer, issues)
    if row is None:
        return
    if not _is_positive_integer(row["sequence"]):
        _field_invalid(issues, pointer, "sequence")
    for field in ("assertion_id", "step_id"):
        if not _is_identifier(row[field]):
            _field_invalid(issues, pointer, field)
    if row["handler_id"] not in _ASSERTION_HANDLER_ORDER:
        _field_invalid(issues, pointer, "handler_id")
    if type(row["params"]) is not dict:
        _field_invalid(issues, pointer, "params")


def _validate_state_snapshot(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("state_snapshot", value, pointer, issues)
    if row is None:
        return
    if type(row["state"]) is not dict:
        _field_invalid(issues, pointer, "state")
        return
    if not _is_sha256(row["state_sha256"]):
        _field_invalid(issues, pointer, "state_sha256")
        return
    expected = _sha256_upper(
        _canonical_bytes(_cast(_Any, row["state"]))
    )
    if row["state_sha256"] != expected:
        _add_issue(
            issues,
            _pointer(pointer, "state_sha256"),
            "snapshot_hash_invalid",
        )


def _validate_action_receipt(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("action_receipt", value, pointer, issues)
    if row is None:
        return
    if row["schema_version"] != _SCHEMA_VERSION:
        _field_invalid(issues, pointer, "schema_version")
    for field in ("case_id", "step_id", "action_id", "handler_id"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)
    for field in (
        "pre_state_sha256",
        "post_state_sha256",
        "handler_output_sha256",
        "request_content_sha256",
    ):
        if not _is_sha256(row[field]):
            _field_invalid(issues, pointer, field)
    idempotency_key = row["idempotency_key"]
    if idempotency_key is not None and type(idempotency_key) is not str:
        _field_invalid(issues, pointer, "idempotency_key")
    status = row["status"]
    error = row["error_code"]
    retryable = row["retryable"]
    replayed = row["replayed"]
    scalar_valid = True
    if status not in _RESULT_STATUSES:
        _field_invalid(issues, pointer, "status")
        scalar_valid = False
    if error is not None and type(error) is not str:
        _field_invalid(issues, pointer, "error_code")
        scalar_valid = False
    if type(retryable) is not bool:
        _field_invalid(issues, pointer, "retryable")
        scalar_valid = False
    if type(replayed) is not bool:
        _field_invalid(issues, pointer, "replayed")
        scalar_valid = False
    effects_valid = _validate_observed_effect_collection(
        row["observed_effects"],
        _pointer(pointer, "observed_effects"),
        issues,
    )
    if not scalar_valid or not effects_valid:
        return
    effects = _cast(list[object], row["observed_effects"])
    same_state = row["pre_state_sha256"] == row["post_state_sha256"]
    status_valid = (
        status == "completed"
        and error is None
        and retryable is False
    ) or (
        status == "failed"
        and _is_string(error, nonempty=True)
        and not effects
        and same_state
    ) or (
        status == "unknown"
        and error == "CORE-E-RESULT-UNKNOWN"
        and retryable is False
        and not effects
        and same_state
    )
    if not status_valid:
        _add_issue(
            issues,
            _pointer(pointer, "status"),
            "receipt_invariant_invalid",
        )
    if replayed is True and effects:
        _add_issue(
            issues,
            _pointer(pointer, "replayed"),
            "receipt_invariant_invalid",
        )


def _validate_step_execution(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("step_execution", value, pointer, issues)
    if row is None:
        return
    for field in ("step_id", "handler_id"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)
    if not _is_sha256(row["request_content_sha256"]):
        _field_invalid(issues, pointer, "request_content_sha256")
    _validate_state_snapshot(
        row["pre_snapshot"],
        _pointer(pointer, "pre_snapshot"),
        issues,
    )
    _validate_state_snapshot(
        row["post_snapshot"],
        _pointer(pointer, "post_snapshot"),
        issues,
    )
    effects_valid = _validate_observed_effect_collection(
        row["observed_effects"],
        _pointer(pointer, "observed_effects"),
        issues,
    )
    receipt_issue_count = len(issues)
    _validate_action_receipt(
        row["receipt"],
        _pointer(pointer, "receipt"),
        issues,
    )
    receipt_valid = len(issues) == receipt_issue_count
    receipt = row["receipt"]
    pre = row["pre_snapshot"]
    post = row["post_snapshot"]
    if not (
        receipt_valid
        and effects_valid
        and type(receipt) is dict
        and set(receipt) == _EXACT_FIELDS["action_receipt"]
        and type(pre) is dict
        and set(pre) == _EXACT_FIELDS["state_snapshot"]
        and type(post) is dict
        and set(post) == _EXACT_FIELDS["state_snapshot"]
    ):
        return
    receipt_row = _cast(_Row, receipt)
    pre_row = _cast(_Row, pre)
    post_row = _cast(_Row, post)
    expected_output_hash = _sha256_upper(
        _canonical_bytes(_cast(_Any, row["handler_output"]))
    )
    matches = (
        receipt_row["step_id"] == row["step_id"]
        and receipt_row["handler_id"] == row["handler_id"]
        and receipt_row["request_content_sha256"]
        == row["request_content_sha256"]
        and receipt_row["pre_state_sha256"] == pre_row["state_sha256"]
        and receipt_row["post_state_sha256"] == post_row["state_sha256"]
        and receipt_row["handler_output_sha256"] == expected_output_hash
        and receipt_row["observed_effects"] == row["observed_effects"]
    )
    if not matches:
        _add_issue(
            issues,
            _pointer(pointer, "receipt"),
            "step_execution_invariant_invalid",
        )


def _validate_effect_diff(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("effect_diff", value, pointer, issues)
    if row is None:
        return
    effects_valid = _validate_observed_effect_collection(
        row["effects"],
        _pointer(pointer, "effects"),
        issues,
    )
    if not _is_sha256(row["aggregate_sha256"]):
        _field_invalid(issues, pointer, "aggregate_sha256")
        return
    if not effects_valid:
        return
    expected = _sha256_upper(
        _canonical_bytes(_cast(_Any, row["effects"]))
    )
    if row["aggregate_sha256"] != expected:
        _add_issue(
            issues,
            _pointer(pointer, "aggregate_sha256"),
            "effect_diff_hash_invalid",
        )


def _validate_assertion_result(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("assertion_result", value, pointer, issues)
    if row is None:
        return
    if not _is_string(row["assertion_id"]):
        _field_invalid(issues, pointer, "assertion_id")
    passed = row["passed"]
    error = row["error_code"]
    if type(passed) is not bool:
        _field_invalid(issues, pointer, "passed")
        return
    if error is not None and type(error) is not str:
        _field_invalid(issues, pointer, "error_code")
        return
    if (passed and error is not None) or (
        not passed and not _is_string(error, nonempty=True)
    ):
        _add_issue(
            issues,
            _pointer(pointer, "error_code"),
            "assertion_result_invariant_invalid",
        )


def _validate_primary_error(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("primary_error", value, pointer, issues)
    if row is None:
        return
    if row["phase"] not in _PRIMARY_ERROR_PHASES:
        _field_invalid(issues, pointer, "phase")
    for field in ("code", "message"):
        if not _is_string(row[field]):
            _field_invalid(issues, pointer, field)


def _validate_cleanup_report(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("cleanup_report", value, pointer, issues)
    if row is None:
        return
    attempted = row["attempted"]
    status = row["status"]
    error = row["error"]
    scalar_valid = True
    if type(attempted) is not bool:
        _field_invalid(issues, pointer, "attempted")
        scalar_valid = False
    if status not in _CLEANUP_STATUSES:
        _field_invalid(issues, pointer, "status")
        scalar_valid = False
    if error is not None and type(error) is not str:
        _field_invalid(issues, pointer, "error")
        scalar_valid = False
    if not _string_list_is_valid(row["residual_paths"]):
        _field_invalid(issues, pointer, "residual_paths")
        scalar_valid = False
    effects_valid = _validate_observed_effect_collection(
        row["residual_effects"],
        _pointer(pointer, "residual_effects"),
        issues,
    )
    if not scalar_valid or not effects_valid:
        return
    residual_paths = _cast(list[object], row["residual_paths"])
    residual_effects = _cast(list[object], row["residual_effects"])
    valid = attempted is True and (
        (
            status == "completed"
            and error is None
            and not residual_paths
            and not residual_effects
        )
        or (
            status == "failed"
            and (
                _is_string(error, nonempty=True)
                or bool(residual_paths)
                or bool(residual_effects)
            )
        )
    )
    if not valid:
        issue_field = "attempted" if attempted is not True else "status"
        _add_issue(
            issues,
            _pointer(pointer, issue_field),
            "cleanup_report_invariant_invalid",
        )


def _validate_sandbox_run_result(
    value: object,
    pointer: str,
    issues: _IssueList,
) -> None:
    row = _exact_row("sandbox_run_result", value, pointer, issues)
    if row is None:
        return
    scalar_valid = True
    if row["schema_version"] != _SCHEMA_VERSION:
        _field_invalid(issues, pointer, "schema_version")
        scalar_valid = False
    if not _is_string(row["case_id"]):
        _field_invalid(issues, pointer, "case_id")
        scalar_valid = False
    phase = row["phase"]
    if phase not in _RUN_PHASES:
        _field_invalid(issues, pointer, "phase")
        scalar_valid = False
    succeeded = row["succeeded"]
    if type(succeeded) is not bool:
        _field_invalid(issues, pointer, "succeeded")
        scalar_valid = False

    nested_start = len(issues)
    executions = row["step_executions"]
    if type(executions) is not list:
        _field_invalid(issues, pointer, "step_executions")
    else:
        for index, execution in enumerate(_cast(list[object], executions)):
            _validate_step_execution(
                execution,
                _pointer(_pointer(pointer, "step_executions"), index),
                issues,
            )
    for field in ("before_snapshot", "after_snapshot"):
        snapshot = row[field]
        if snapshot is not None:
            _validate_state_snapshot(
                snapshot,
                _pointer(pointer, field),
                issues,
            )
    if row["effect_diff"] is not None:
        _validate_effect_diff(
            row["effect_diff"],
            _pointer(pointer, "effect_diff"),
            issues,
        )
    assertions = row["assertion_results"]
    if type(assertions) is not list:
        _field_invalid(issues, pointer, "assertion_results")
    else:
        for index, assertion in enumerate(_cast(list[object], assertions)):
            _validate_assertion_result(
                assertion,
                _pointer(_pointer(pointer, "assertion_results"), index),
                issues,
            )
    primary = row["primary_error"]
    if primary is not None:
        _validate_primary_error(
            primary,
            _pointer(pointer, "primary_error"),
            issues,
        )
    _validate_cleanup_report(
        row["cleanup_report"],
        _pointer(pointer, "cleanup_report"),
        issues,
    )
    if not scalar_valid or len(issues) != nested_start:
        return

    assertion_rows = _cast(list[_Row], assertions)
    all_passed = all(item["passed"] is True for item in assertion_rows)
    cleanup = _cast(_Row, row["cleanup_report"])
    primary_phase = (
        None if primary is None else _cast(_Row, primary)["phase"]
    )
    phase_relation_valid = (
        primary is not None and primary_phase == phase
    ) or (
        primary is None
        and cleanup["status"] == "failed"
        and phase == "cleanup"
    ) or (
        primary is None
        and cleanup["status"] == "completed"
        and phase == "completed"
        and all_passed
    )
    expected_success = (
        phase == "completed"
        and primary is None
        and all_passed
        and cleanup["status"] == "completed"
    )
    early_phases = {"validation", "reset", "setup", "before_snapshot"}
    if phase in early_phases:
        artifacts_valid = (
            not executions
            and row["before_snapshot"] is None
            and row["after_snapshot"] is None
            and row["effect_diff"] is None
            and not assertions
        )
    elif phase == "after_snapshot":
        artifacts_valid = (
            row["before_snapshot"] is not None
            and row["after_snapshot"] is None
            and row["effect_diff"] is None
            and not assertions
        )
    elif phase == "stimulus":
        artifacts_valid = (
            row["before_snapshot"] is not None
            and (
                (
                    row["after_snapshot"] is not None
                    and row["effect_diff"] is not None
                )
                or (
                    row["after_snapshot"] is None
                    and row["effect_diff"] is None
                )
            )
            and not assertions
        )
    else:
        artifacts_valid = (
            row["before_snapshot"] is not None
            and row["after_snapshot"] is not None
            and row["effect_diff"] is not None
        )
    if not artifacts_valid:
        _add_issue(
            issues,
            _pointer(pointer, "phase"),
            "sandbox_run_result_invariant_invalid",
        )

    execution_rows = _cast(list[_Row], executions)
    execution_chain_valid = all(
        _cast(_Row, execution["receipt"])["case_id"] == row["case_id"]
        for execution in execution_rows
    )
    for previous, following in zip(execution_rows, execution_rows[1:]):
        if previous["post_snapshot"] != following["pre_snapshot"]:
            execution_chain_valid = False
    before = row["before_snapshot"]
    after = row["after_snapshot"]
    if before is not None and after is not None:
        if execution_rows:
            execution_chain_valid = execution_chain_valid and (
                execution_rows[0]["pre_snapshot"] == before
                and execution_rows[-1]["post_snapshot"] == after
            )
        else:
            execution_chain_valid = execution_chain_valid and before == after
    if not execution_chain_valid:
        _add_issue(
            issues,
            _pointer(pointer, "step_executions"),
            "sandbox_run_result_invariant_invalid",
        )

    effect_diff = row["effect_diff"]
    if effect_diff is not None:
        flattened_effects = [
            effect
            for execution in execution_rows
            for effect in _cast(list[object], execution["observed_effects"])
        ]
        if _cast(_Row, effect_diff)["effects"] != flattened_effects:
            _add_issue(
                issues,
                _pointer(pointer, "effect_diff"),
                "sandbox_run_result_invariant_invalid",
            )
    if not phase_relation_valid:
        _add_issue(
            issues,
            _pointer(pointer, "phase"),
            "sandbox_run_result_invariant_invalid",
        )
    if type(succeeded) is bool and succeeded != expected_success:
        _add_issue(
            issues,
            _pointer(pointer, "succeeded"),
            "sandbox_run_result_invariant_invalid",
        )


_VALIDATORS: _Mapping[str, _EnvelopeValidator] = _MappingProxyType(
    {
        "actor": _validate_actor,
        "expected_version": _validate_expected_version,
        "mutation_command_envelope": _validate_mutation_command,
        "input_source": _validate_input_source,
        "reversibility": _validate_reversibility,
        "budget": _validate_budget,
        "scope": _validate_scope,
        "confirmation": _validate_confirmation,
        "action_envelope": _validate_action_envelope,
        "effect_rule": _validate_effect_rule,
        "sandbox_profile": _validate_sandbox_profile,
        "rubric_requirement": _validate_rubric_requirement,
        "state_patch_operation": _validate_state_patch_operation,
        "effect_seed": _validate_effect_seed,
        "observed_effect": _validate_observed_effect,
        "effect_pattern": _validate_effect_pattern,
        "driver_result": _validate_driver_result,
        "handler_result": _validate_handler_result,
        "setup_step": _validate_setup_step,
        "stimulus_step": _validate_stimulus_step,
        "machine_assertion": _validate_machine_assertion,
        "state_snapshot": _validate_state_snapshot,
        "action_receipt": _validate_action_receipt,
        "step_execution": _validate_step_execution,
        "effect_diff": _validate_effect_diff,
        "assertion_result": _validate_assertion_result,
        "primary_error": _validate_primary_error,
        "cleanup_report": _validate_cleanup_report,
        "sandbox_run_result": _validate_sandbox_run_result,
    }
)


def validate_envelope(kind: str, value: object) -> list[_ValidationIssue]:
    if type(kind) is not str or kind not in _VALIDATORS:
        raise _FixtureInputError("envelope_kind_invalid")
    try:
        _canonical_bytes(_cast(_Any, value))
    except (_FixtureInputError, RecursionError, TypeError, ValueError):
        issues: _IssueList = []
        _add_issue(issues, "", "envelope_json_value_invalid")
        return _finish(issues)
    issues = []
    _VALIDATORS[kind](value, "", issues)
    return _finish(issues)
