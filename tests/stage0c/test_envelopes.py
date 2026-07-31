import copy
from dataclasses import fields
from typing import Any, Callable

import pytest

from tools.stage0c_fixtures.io import canonical_bytes, sha256_upper
from tools.stage0c_fixtures.schema import validate_envelope
from tools.stage0c_fixtures.types import FixtureInputError, ValidationIssue


_UUID_A = "018f47a2-7b9c-7f31-8f44-1234567890ab"
_UUID_B = "018f47a2-7b9c-7f31-8f44-1234567890ac"
_UUID_C = "018f47a2-7b9c-7f31-8f44-1234567890ad"
_UUID_D = "018f47a2-7b9c-7f31-8f44-1234567890ae"


def _hash(value: Any) -> str:
    return sha256_upper(canonical_bytes(value))


def _actor() -> dict[str, Any]:
    return {"actor_type": "user", "actor_id": "user-1"}


def _expected_version() -> dict[str, Any]:
    return {"target_record_ref": "memory-1", "expected_version": "absent"}


def _mutation_command() -> dict[str, Any]:
    return {
        "command_id": "command-1",
        "command_type": "memory.create",
        "actor": _actor(),
        "actor_capability_id": "capability-1",
        "expected_versions": [_expected_version()],
        "audit_context_id": "audit-1",
        "idempotency_key": "idempotency-1",
        "issued_at": "0000-02-29T23:59:59Z",
        "target_record_refs": ["memory-1"],
        "payload": {"content": "remember this"},
    }


def _input_source() -> dict[str, Any]:
    return {"source_id": "source-1", "trust": "user_data"}


def _reversibility() -> dict[str, Any]:
    return {
        "status": "verified",
        "rollback_plan": "restore snapshot",
        "rollback_deadline": "2026-01-02T00:00:00Z",
    }


def _budget() -> dict[str, Any]:
    return {"calls": 1, "money": "0", "time": 30}


def _scope() -> dict[str, Any]:
    return {
        "resources": ["memory-1"],
        "parameter_constraints": {"mode": "exact"},
    }


def _confirmation() -> dict[str, Any]:
    return {
        "required": False,
        "confirmation_id": None,
        "summary_checksum": None,
    }


def _action_envelope() -> dict[str, Any]:
    return {
        "action_id": _UUID_A,
        "identity_id": _UUID_B,
        "lineage_id": _UUID_C,
        "branch_id": _UUID_D,
        "vault_id": None,
        "user_id": "user-1",
        "session_id": "session-1",
        "task_id": "task-1",
        "candidate_intent_id": "intent-1",
        "intent_summary": "write one sandbox file",
        "tool_id": "file",
        "operation": "write",
        "parameters": {"content": "fixture"},
        "targets": ["sandbox/output.txt"],
        "destinations": ["sandbox"],
        "input_sources": [_input_source()],
        "data_classes": ["public"],
        "expected_effects": [{"operation": "write"}],
        "effect_class": "E1",
        "reversibility": _reversibility(),
        "expected_state_diff": {"created": True},
        "budget": _budget(),
        "scope": _scope(),
        "expires_at": "2026-01-01T00:05:00+00:00",
        "max_uses": 1,
        "idempotency_key": "action-key-1",
        "confirmation": _confirmation(),
        "policy_version": "0.1",
    }


def _effect_rule() -> dict[str, Any]:
    return {"adapter_id": "file", "operation": "write", "target": "out"}


def _sandbox_profile() -> dict[str, Any]:
    return {
        "profile_id": "sandbox-stage0c",
        "allowed_effects": [_effect_rule()],
        "fixed_clock": "2026-01-01T00:00:00Z",
        "id_seed": "seed-1",
        "reset_policy": "fresh_context",
        "cleanup_policy": "always",
    }


def _rubric_requirement() -> dict[str, Any]:
    return {
        "criterion_id": "criterion-h",
        "oracle_kind": "H",
        "question": "Is the response faithful?",
        "evidence_case_json_pointers": ["/stimulus_steps/0"],
        "allowed_scores": [-1, 0, 1],
        "passing_scores": [1],
    }


def _state_patch_operation() -> dict[str, Any]:
    return {"op": "add", "path": "/records/memory-1", "value": {"v": 1}}


def _effect_seed() -> dict[str, Any]:
    return {
        "adapter_id": "file",
        "operation": "write",
        "target": "out",
        "details": {"bytes": 7},
    }


def _observed_effect() -> dict[str, Any]:
    return {
        "effect_id": "effect-" + "a" * 64,
        **_effect_seed(),
    }


def _effect_pattern() -> dict[str, Any]:
    return {
        "adapter_id": "file",
        "operation": None,
        "target": None,
        "details": {},
    }


def _driver_result(status: str = "completed") -> dict[str, Any]:
    result = {
        "result_ref": "result-1",
        "status": status,
        "error_code": None,
        "retryable": False,
        "output": {"ok": True},
        "effects": [_effect_seed()],
        "state_patch": [_state_patch_operation()],
    }
    if status == "failed":
        result.update(error_code="CORE-E-FAILED", effects=[], state_patch=[])
    elif status == "unknown":
        result.update(
            error_code="CORE-E-RESULT-UNKNOWN",
            effects=[],
            state_patch=[],
        )
    return result


def _handler_result(status: str = "completed") -> dict[str, Any]:
    result = _driver_result(status)
    del result["result_ref"]
    return result


def _state_snapshot(state: dict[str, Any] | None = None) -> dict[str, Any]:
    value = {"records": {}} if state is None else state
    return {"state": value, "state_sha256": _hash(value)}


def _action_receipt(
    *,
    output: Any | None = None,
    pre: dict[str, Any] | None = None,
    post: dict[str, Any] | None = None,
    effects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output_value = {"ok": True} if output is None else output
    pre_value = _state_snapshot() if pre is None else pre
    post_value = _state_snapshot() if post is None else post
    observed = [] if effects is None else effects
    return {
        "schema_version": "0.1",
        "case_id": "case-ac-001-1",
        "step_id": "step-1",
        "action_id": "action-1",
        "handler_id": "backend.replay",
        "status": "completed",
        "error_code": None,
        "retryable": False,
        "pre_state_sha256": pre_value["state_sha256"],
        "post_state_sha256": post_value["state_sha256"],
        "handler_output_sha256": _hash(output_value),
        "observed_effects": observed,
        "idempotency_key": "replay-key-1",
        "request_content_sha256": "B" * 64,
        "replayed": False,
    }


def _step_execution() -> dict[str, Any]:
    output = {"ok": True}
    pre = _state_snapshot()
    post = _state_snapshot()
    effects: list[dict[str, Any]] = []
    return {
        "step_id": "step-1",
        "handler_id": "backend.replay",
        "request_content_sha256": "B" * 64,
        "pre_snapshot": pre,
        "post_snapshot": post,
        "handler_output": output,
        "observed_effects": effects,
        "receipt": _action_receipt(
            output=output,
            pre=pre,
            post=post,
            effects=effects,
        ),
    }


def _effect_diff() -> dict[str, Any]:
    effects: list[dict[str, Any]] = []
    return {"effects": effects, "aggregate_sha256": _hash(effects)}


def _assertion_result(passed: bool = True) -> dict[str, Any]:
    return {
        "assertion_id": "assertion-1",
        "passed": passed,
        "actual": {"status": "completed"},
        "error_code": None if passed else "fixture_assertion_failed",
    }


def _primary_error() -> dict[str, Any]:
    return {
        "phase": "assertion",
        "code": "fixture_assertion_failed",
        "message": "assertion failed",
    }


def _cleanup_report(status: str = "completed") -> dict[str, Any]:
    report = {
        "attempted": True,
        "status": status,
        "residual_paths": [],
        "residual_effects": [],
        "error": None,
    }
    if status == "failed":
        report["error"] = "cleanup failed"
    return report


def _sandbox_run_result() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "case_id": "case-ac-001-1",
        "phase": "completed",
        "step_executions": [_step_execution()],
        "before_snapshot": _state_snapshot(),
        "after_snapshot": _state_snapshot(),
        "effect_diff": _effect_diff(),
        "assertion_results": [_assertion_result()],
        "primary_error": None,
        "cleanup_report": _cleanup_report(),
        "succeeded": True,
    }


def _setup_step() -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "setup-1",
        "handler_id": "sandbox.set_clock",
        "params": {"future_f07": True},
    }


def _stimulus_step() -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "step-1",
        "handler_id": "backend.replay",
        "params": {"future_f07": True},
    }


def _machine_assertion() -> dict[str, Any]:
    return {
        "sequence": 1,
        "assertion_id": "assertion-1",
        "handler_id": "receipt.status",
        "step_id": "step-1",
        "params": {"future_f07": True},
    }


_VALID_FACTORIES: dict[str, Callable[[], dict[str, Any]]] = {
    "actor": _actor,
    "expected_version": _expected_version,
    "mutation_command_envelope": _mutation_command,
    "input_source": _input_source,
    "reversibility": _reversibility,
    "budget": _budget,
    "scope": _scope,
    "confirmation": _confirmation,
    "action_envelope": _action_envelope,
    "effect_rule": _effect_rule,
    "sandbox_profile": _sandbox_profile,
    "rubric_requirement": _rubric_requirement,
    "state_patch_operation": _state_patch_operation,
    "effect_seed": _effect_seed,
    "observed_effect": _observed_effect,
    "effect_pattern": _effect_pattern,
    "driver_result": _driver_result,
    "handler_result": _handler_result,
    "state_snapshot": _state_snapshot,
    "action_receipt": _action_receipt,
    "step_execution": _step_execution,
    "effect_diff": _effect_diff,
    "assertion_result": _assertion_result,
    "primary_error": _primary_error,
    "cleanup_report": _cleanup_report,
    "sandbox_run_result": _sandbox_run_result,
    "setup_step": _setup_step,
    "stimulus_step": _stimulus_step,
    "machine_assertion": _machine_assertion,
}


def _assert_issue(
    kind: str,
    value: Any,
    code: str,
    pointer: str,
) -> ValidationIssue:
    issues = validate_envelope(kind, value)
    assert len(issues) == 1
    issue = issues[0]
    assert type(issue) is ValidationIssue
    assert tuple(field.name for field in fields(issue)) == (
        "json_pointer",
        "code",
        "message",
    )
    assert issue.code == code
    assert issue.json_pointer == pointer
    assert issue.message.strip()
    return issue


@pytest.mark.parametrize("kind", tuple(_VALID_FACTORIES))
def test_every_structural_object_accepts_valid_golden(kind: str) -> None:
    value = _VALID_FACTORIES[kind]()
    before = copy.deepcopy(value)
    assert validate_envelope(kind, value) == []
    assert value == before


@pytest.mark.parametrize("kind", tuple(_VALID_FACTORIES))
def test_every_structural_object_rejects_one_extra_top_level_field(
    kind: str,
) -> None:
    value = _VALID_FACTORIES[kind]()
    value["extra"] = None
    _assert_issue(kind, value, "envelope_exact_fields_invalid", "")


def test_unknown_envelope_kind_uses_stable_input_error() -> None:
    with pytest.raises(FixtureInputError) as captured:
        validate_envelope("unknown", {})
    assert captured.value.code == "envelope_kind_invalid"


@pytest.mark.parametrize(
    ("mutation", "pointer", "code"),
    [
        (
            lambda value: value.update(command_id=""),
            "/command_id",
            "envelope_field_invalid",
        ),
        (
            lambda value: value["actor"].update(actor_type="root"),
            "/actor/actor_type",
            "envelope_field_invalid",
        ),
        (
            lambda value: value.update(issued_at="2026-02-30T00:00:00Z"),
            "/issued_at",
            "envelope_field_invalid",
        ),
        (
            lambda value: value.update(target_record_refs=[]),
            "/target_record_refs",
            "envelope_field_invalid",
        ),
        (
            lambda value: value["expected_versions"][0].update(
                expected_version=-1
            ),
            "/expected_versions/0/expected_version",
            "envelope_field_invalid",
        ),
        (
            lambda value: value["expected_versions"][0].update(
                target_record_ref="memory-2"
            ),
            "/expected_versions",
            "expected_versions_target_set_invalid",
        ),
        (
            lambda value: value["expected_versions"].append(
                copy.deepcopy(value["expected_versions"][0])
            ),
            "/expected_versions",
            "expected_versions_target_set_invalid",
        ),
    ],
)
def test_mutation_command_cross_contract(
    mutation: Callable[[dict[str, Any]], None],
    pointer: str,
    code: str,
) -> None:
    value = _mutation_command()
    mutation(value)
    _assert_issue("mutation_command_envelope", value, code, pointer)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("action_id", "not-a-uuid"),
        ("vault_id", "not-a-uuid"),
        ("effect_class", "E4"),
        ("expires_at", "2026-01-01T00:00:00+01:00"),
        ("max_uses", 0),
        ("max_uses", True),
    ],
)
def test_action_envelope_scalar_contract(field: str, invalid: Any) -> None:
    value = _action_envelope()
    value[field] = invalid
    _assert_issue(
        "action_envelope",
        value,
        "envelope_field_invalid",
        f"/{field}",
    )


def test_action_collections_and_budget_are_strict() -> None:
    duplicate_class = _action_envelope()
    duplicate_class["data_classes"] = ["public", "public"]
    _assert_issue(
        "action_envelope",
        duplicate_class,
        "envelope_field_invalid",
        "/data_classes",
    )

    no_input = _action_envelope()
    no_input["input_sources"] = []
    _assert_issue(
        "action_envelope",
        no_input,
        "envelope_field_invalid",
        "/input_sources",
    )

    invalid_money = _action_envelope()
    invalid_money["budget"]["money"] = "01.00"
    _assert_issue(
        "action_envelope",
        invalid_money,
        "envelope_field_invalid",
        "/budget/money",
    )


def test_reversibility_cross_contract() -> None:
    unknown = _action_envelope()
    unknown["reversibility"] = {
        "status": "unknown",
        "rollback_plan": None,
        "rollback_deadline": None,
    }
    _assert_issue(
        "action_envelope",
        unknown,
        "reversibility_invariant_invalid",
        "/effect_class",
    )
    unknown["effect_class"] = "E3"
    assert validate_envelope("action_envelope", unknown) == []

    verified = _action_envelope()
    verified["reversibility"]["rollback_plan"] = ""
    _assert_issue(
        "action_envelope",
        verified,
        "reversibility_invariant_invalid",
        "/reversibility",
    )

    irreversible = _action_envelope()
    irreversible["reversibility"] = {
        "status": "irreversible",
        "rollback_plan": "impossible",
        "rollback_deadline": None,
    }
    _assert_issue(
        "action_envelope",
        irreversible,
        "reversibility_invariant_invalid",
        "/reversibility",
    )


def test_confirmation_cross_contract() -> None:
    required = _action_envelope()
    required["confirmation"] = {
        "required": True,
        "confirmation_id": None,
        "summary_checksum": None,
    }
    _assert_issue(
        "action_envelope",
        required,
        "confirmation_invariant_invalid",
        "/confirmation",
    )
    required["confirmation"] = {
        "required": True,
        "confirmation_id": "confirmation-1",
        "summary_checksum": "checksum-1",
    }
    assert validate_envelope("action_envelope", required) == []


@pytest.mark.parametrize("kind", ["driver_result", "handler_result"])
@pytest.mark.parametrize("status", ["completed", "failed", "unknown"])
def test_result_status_golden_matrix(kind: str, status: str) -> None:
    value = (
        _driver_result(status)
        if kind == "driver_result"
        else _handler_result(status)
    )
    assert validate_envelope(kind, value) == []


@pytest.mark.parametrize("kind", ["driver_result", "handler_result"])
def test_result_status_cross_invariants(kind: str) -> None:
    factory = _driver_result if kind == "driver_result" else _handler_result

    completed = factory("completed")
    completed["retryable"] = True
    _assert_issue(
        kind,
        completed,
        "result_invariant_invalid",
        "/status",
    )

    failed = factory("failed")
    failed["error_code"] = ""
    _assert_issue(kind, failed, "result_invariant_invalid", "/status")

    unknown = factory("unknown")
    unknown["effects"] = [_effect_seed()]
    _assert_issue(kind, unknown, "result_invariant_invalid", "/status")


def test_state_patch_remove_and_path_uniqueness() -> None:
    remove = _state_patch_operation()
    remove.update(op="remove", value=1)
    _assert_issue(
        "state_patch_operation",
        remove,
        "state_patch_invariant_invalid",
        "/value",
    )

    root = _state_patch_operation()
    root["path"] = ""
    _assert_issue(
        "state_patch_operation",
        root,
        "state_patch_invariant_invalid",
        "/path",
    )

    duplicate = _driver_result()
    duplicate["state_patch"].append(
        copy.deepcopy(duplicate["state_patch"][0])
    )
    _assert_issue(
        "driver_result",
        duplicate,
        "state_patch_invariant_invalid",
        "/state_patch",
    )


def test_snapshot_and_effect_diff_hashes_are_relational() -> None:
    snapshot = _state_snapshot()
    snapshot["state_sha256"] = "A" * 64
    _assert_issue(
        "state_snapshot",
        snapshot,
        "snapshot_hash_invalid",
        "/state_sha256",
    )

    effect_diff = _effect_diff()
    effect_diff["aggregate_sha256"] = "A" * 64
    _assert_issue(
        "effect_diff",
        effect_diff,
        "effect_diff_hash_invalid",
        "/aggregate_sha256",
    )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("step_id", "wrong-step"),
        ("handler_id", "core.query"),
        ("request_content_sha256", "A" * 64),
    ],
)
def test_step_execution_receipt_identity_is_exact(
    field: str,
    invalid: Any,
) -> None:
    value = _step_execution()
    value["receipt"][field] = invalid
    _assert_issue(
        "step_execution",
        value,
        "step_execution_invariant_invalid",
        "/receipt",
    )


def test_step_execution_hashes_and_effects_match_receipt() -> None:
    output = _step_execution()
    output["receipt"]["handler_output_sha256"] = "A" * 64
    _assert_issue(
        "step_execution",
        output,
        "step_execution_invariant_invalid",
        "/receipt",
    )

    effects = _step_execution()
    effects["receipt"]["observed_effects"] = [_observed_effect()]
    _assert_issue(
        "step_execution",
        effects,
        "step_execution_invariant_invalid",
        "/receipt",
    )


def test_action_receipt_status_and_replay_invariants() -> None:
    failed = _action_receipt()
    failed.update(status="failed", error_code="CORE-E-FAILED")
    assert validate_envelope("action_receipt", failed) == []
    failed["observed_effects"] = [_observed_effect()]
    _assert_issue(
        "action_receipt",
        failed,
        "receipt_invariant_invalid",
        "/status",
    )

    replayed = _action_receipt(effects=[_observed_effect()])
    replayed["replayed"] = True
    _assert_issue(
        "action_receipt",
        replayed,
        "receipt_invariant_invalid",
        "/replayed",
    )


def test_assertion_and_cleanup_cross_contracts() -> None:
    assertion = _assertion_result()
    assertion["error_code"] = "fixture_assertion_failed"
    _assert_issue(
        "assertion_result",
        assertion,
        "assertion_result_invariant_invalid",
        "/error_code",
    )

    cleanup = _cleanup_report()
    cleanup["attempted"] = False
    _assert_issue(
        "cleanup_report",
        cleanup,
        "cleanup_report_invariant_invalid",
        "/attempted",
    )

    failed = _cleanup_report("failed")
    failed["error"] = None
    _assert_issue(
        "cleanup_report",
        failed,
        "cleanup_report_invariant_invalid",
        "/status",
    )


def test_sandbox_run_result_success_is_biconditional() -> None:
    result = _sandbox_run_result()
    result["succeeded"] = False
    _assert_issue(
        "sandbox_run_result",
        result,
        "sandbox_run_result_invariant_invalid",
        "/succeeded",
    )

    failed_cleanup = _sandbox_run_result()
    failed_cleanup.update(
        phase="cleanup",
        cleanup_report=_cleanup_report("failed"),
        succeeded=False,
    )
    assert validate_envelope("sandbox_run_result", failed_cleanup) == []

    failed_assertion = _sandbox_run_result()
    failed_assertion.update(
        phase="assertion",
        assertion_results=[_assertion_result(False)],
        primary_error=_primary_error(),
        succeeded=False,
    )
    assert validate_envelope("sandbox_run_result", failed_assertion) == []
    failed_assertion["primary_error"]["phase"] = "setup"
    _assert_issue(
        "sandbox_run_result",
        failed_assertion,
        "sandbox_run_result_invariant_invalid",
        "/phase",
    )


def test_envelope_json_domain_is_strict_and_validation_is_pure() -> None:
    value = _action_envelope()
    value["parameters"]["ratio"] = 1.5
    before = copy.deepcopy(value)
    first = _assert_issue(
        "action_envelope",
        value,
        "envelope_json_value_invalid",
        "",
    )
    second = validate_envelope("action_envelope", value)
    assert second == [first]
    assert value == before


def test_rubric_arrays_are_ordered_unique_and_subset_constrained() -> None:
    evidence = _rubric_requirement()
    evidence["evidence_case_json_pointers"] = ["/z", "/a"]
    _assert_issue(
        "rubric_requirement",
        evidence,
        "envelope_field_invalid",
        "/evidence_case_json_pointers",
    )

    pointer = _rubric_requirement()
    pointer["evidence_case_json_pointers"] = ["not-a-pointer"]
    _assert_issue(
        "rubric_requirement",
        pointer,
        "envelope_field_invalid",
        "/evidence_case_json_pointers",
    )

    allowed = _rubric_requirement()
    allowed["allowed_scores"] = [1, 0]
    _assert_issue(
        "rubric_requirement",
        allowed,
        "envelope_field_invalid",
        "/allowed_scores",
    )

    passing = _rubric_requirement()
    passing["passing_scores"] = [2]
    _assert_issue(
        "rubric_requirement",
        passing,
        "envelope_field_invalid",
        "/passing_scores",
    )


def test_sandbox_and_effect_contracts_are_frozen() -> None:
    clock = _sandbox_profile()
    clock["fixed_clock"] = "2026-01-01T00:00:00+01:00"
    _assert_issue(
        "sandbox_profile",
        clock,
        "envelope_field_invalid",
        "/fixed_clock",
    )

    duplicate = _sandbox_profile()
    duplicate["allowed_effects"].append(
        copy.deepcopy(duplicate["allowed_effects"][0])
    )
    _assert_issue(
        "sandbox_profile",
        duplicate,
        "envelope_field_invalid",
        "/allowed_effects",
    )

    observed = _observed_effect()
    observed["effect_id"] = "effect-" + "A" * 64
    _assert_issue(
        "observed_effect",
        observed,
        "envelope_field_invalid",
        "/effect_id",
    )

    pattern = _effect_pattern()
    pattern["operation"] = 1
    _assert_issue(
        "effect_pattern",
        pattern,
        "envelope_field_invalid",
        "/operation",
    )


@pytest.mark.parametrize(
    ("kind", "factory"),
    [
        ("effect_rule", _effect_rule),
        ("effect_seed", _effect_seed),
        ("effect_pattern", _effect_pattern),
    ],
)
def test_unhashable_adapter_ids_are_validation_issues(
    kind: str,
    factory: Callable[[], dict[str, Any]],
) -> None:
    value = factory()
    value["adapter_id"] = []
    _assert_issue(
        kind,
        value,
        "envelope_field_invalid",
        "/adapter_id",
    )


def test_unhashable_rubric_oracle_is_a_validation_issue() -> None:
    value = _rubric_requirement()
    value["oracle_kind"] = []
    _assert_issue(
        "rubric_requirement",
        value,
        "envelope_field_invalid",
        "/oracle_kind",
    )


def test_nested_action_fields_remain_structurally_typed() -> None:
    targets = _action_envelope()
    targets["targets"] = ["same", "same"]
    _assert_issue(
        "action_envelope",
        targets,
        "envelope_field_invalid",
        "/targets",
    )

    source = _action_envelope()
    source["input_sources"][0]["trust"] = "implicit"
    _assert_issue(
        "action_envelope",
        source,
        "envelope_field_invalid",
        "/input_sources/0/trust",
    )

    scope = _action_envelope()
    scope["scope"]["parameter_constraints"] = []
    _assert_issue(
        "action_envelope",
        scope,
        "envelope_field_invalid",
        "/scope/parameter_constraints",
    )

    confirmation = _action_envelope()
    confirmation["confirmation"]["confirmation_id"] = "unexpected"
    _assert_issue(
        "action_envelope",
        confirmation,
        "confirmation_invariant_invalid",
        "/confirmation",
    )


def test_receipt_status_matrix_and_state_relation_are_exact() -> None:
    failed = _action_receipt()
    failed.update(status="failed", error_code="CORE-E-FAILED")
    assert validate_envelope("action_receipt", failed) == []

    unknown = _action_receipt()
    unknown.update(
        status="unknown",
        error_code="CORE-E-RESULT-UNKNOWN",
    )
    assert validate_envelope("action_receipt", unknown) == []

    completed_retry = _action_receipt()
    completed_retry["retryable"] = True
    _assert_issue(
        "action_receipt",
        completed_retry,
        "receipt_invariant_invalid",
        "/status",
    )

    failed_state_change = _action_receipt()
    failed_state_change.update(
        status="failed",
        error_code="CORE-E-FAILED",
        post_state_sha256="A" * 64,
    )
    _assert_issue(
        "action_receipt",
        failed_state_change,
        "receipt_invariant_invalid",
        "/status",
    )


def test_primary_error_survives_cleanup_failure_in_run_result() -> None:
    result = _sandbox_run_result()
    result.update(
        phase="assertion",
        assertion_results=[_assertion_result(False)],
        primary_error=_primary_error(),
        cleanup_report=_cleanup_report("failed"),
        succeeded=False,
    )
    assert validate_envelope("sandbox_run_result", result) == []


def test_run_phase_artifacts_and_execution_chain_are_relational() -> None:
    early = _sandbox_run_result()
    early.update(
        phase="setup",
        step_executions=[],
        before_snapshot=None,
        after_snapshot=None,
        effect_diff=None,
        assertion_results=[],
        primary_error={
            "phase": "setup",
            "code": "fixture_setup_failed",
            "message": "setup failed",
        },
        succeeded=False,
    )
    assert validate_envelope("sandbox_run_result", early) == []
    early["before_snapshot"] = _state_snapshot()
    _assert_issue(
        "sandbox_run_result",
        early,
        "sandbox_run_result_invariant_invalid",
        "/phase",
    )

    stimulus_after_failure = _sandbox_run_result()
    stimulus_after_failure.update(
        phase="stimulus",
        step_executions=[],
        after_snapshot=None,
        effect_diff=None,
        assertion_results=[],
        primary_error={
            "phase": "stimulus",
            "code": "fixture_unexpected_handler_exception",
            "message": "stimulus failed",
        },
        succeeded=False,
    )
    assert validate_envelope(
        "sandbox_run_result",
        stimulus_after_failure,
    ) == []

    case_mismatch = _sandbox_run_result()
    case_mismatch["step_executions"][0]["receipt"]["case_id"] = "other"
    _assert_issue(
        "sandbox_run_result",
        case_mismatch,
        "sandbox_run_result_invariant_invalid",
        "/step_executions",
    )

    effect_mismatch = _sandbox_run_result()
    effects = [_observed_effect()]
    effect_mismatch["effect_diff"] = {
        "effects": effects,
        "aggregate_sha256": _hash(effects),
    }
    _assert_issue(
        "sandbox_run_result",
        effect_mismatch,
        "sandbox_run_result_invariant_invalid",
        "/effect_diff",
    )

    zero_steps = _sandbox_run_result()
    zero_steps["step_executions"] = []
    assert validate_envelope("sandbox_run_result", zero_steps) == []


@pytest.mark.parametrize(
    "invalid_json",
    [
        {1: "non-string-key"},
        {"binary": b"bytes"},
        {"surrogate": "\ud800"},
    ],
)
def test_json_domain_rejects_noncanonical_python_values(
    invalid_json: Any,
) -> None:
    _assert_issue(
        "scope",
        invalid_json,
        "envelope_json_value_invalid",
        "",
    )
