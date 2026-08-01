from datetime import UTC, datetime, timedelta, timezone
from collections.abc import Mapping
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError


TARGET = "idn-00000000-0000-4000-8000-000000000001"


def _commands():
    from amadeus_core.contracts import commands

    return commands


def _command(expected_version: int | str = "absent", **changes):
    commands = _commands()
    body = {
        "command_id": "cmd-00000000-0000-4000-8000-000000000001",
        "command_type": "identity.create",
        "actor": commands.Actor(actor_type="system", actor_id="system-test"),
        "actor_capability_id": "cap-system-bootstrap",
        "expected_versions": (
            commands.ExpectedVersion(
                target_record_ref=TARGET,
                expected_version=expected_version,
            ),
        ),
        "audit_context_id": "aud-00000000-0000-4000-8000-000000000001",
        "idempotency_key": "bootstrap-test-1",
        "issued_at": datetime(2026, 8, 1, tzinfo=UTC),
        "target_record_refs": (TARGET,),
        "payload": {"scope_refs": ["lineage-root"]},
    }
    body.update(changes)
    return commands.MutationCommandEnvelope(**body)


def test_absent_and_zero_normalize_to_zero_and_hash_identically() -> None:
    commands = _commands()
    absent = _command("absent")
    zero = _command(0)

    assert commands.normalize_expected_versions(absent) == {TARGET: 0}
    assert commands.normalize_expected_versions(zero) == {TARGET: 0}
    assert commands.compute_command_hash(absent) == commands.compute_command_hash(zero)


@pytest.mark.parametrize("mismatch", ["duplicate_target", "duplicate_expected", "unequal_sets"])
def test_target_refs_and_expected_versions_must_form_an_exact_bijection(mismatch: str) -> None:
    commands = _commands()
    other = "lin-00000000-0000-4000-8000-000000000002"
    if mismatch == "duplicate_target":
        command = _command(target_record_refs=(TARGET, TARGET))
    elif mismatch == "duplicate_expected":
        item = commands.ExpectedVersion(target_record_ref=TARGET, expected_version=1)
        command = _command(expected_versions=(item, item))
    else:
        command = _command(target_record_refs=(other,))

    with pytest.raises(commands.CoreContractViolation) as captured:
        commands.normalize_expected_versions(command)
    assert captured.value.code is commands.CoreErrorCode.VERSION_TARGET_SET_MISMATCH


@pytest.mark.parametrize("invalid", [True, -1])
def test_expected_version_rejects_bool_and_negative_values(invalid: object) -> None:
    commands = _commands()

    with pytest.raises(ValidationError):
        commands.ExpectedVersion(target_record_ref=TARGET, expected_version=invalid)


@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 8, 1),
        datetime(2026, 8, 1, tzinfo=timezone(timedelta(hours=8))),
    ],
    ids=("naive", "non-utc"),
)
def test_command_issued_at_requires_utc(invalid_time: datetime) -> None:
    with pytest.raises(ValidationError):
        _command(issued_at=invalid_time)


def test_command_hash_and_idempotency_address_are_target_order_independent() -> None:
    commands = _commands()
    other = "lin-00000000-0000-4000-8000-000000000002"
    one = commands.ExpectedVersion(target_record_ref=TARGET, expected_version=1)
    two = commands.ExpectedVersion(target_record_ref=other, expected_version=1)
    left = _command(
        expected_versions=(one, two),
        target_record_refs=(TARGET, other),
        payload={"scope_refs": ["b", "a"]},
    )
    right = _command(
        expected_versions=(two, one),
        target_record_refs=(other, TARGET),
        payload={"scope_refs": ["b", "a"]},
    )

    assert commands.idempotency_address(left) == commands.idempotency_address(right)
    assert commands.compute_command_hash(left) == commands.compute_command_hash(right)


def test_idempotency_address_is_scope_ref_order_independent() -> None:
    commands = _commands()
    left = _command(payload={"scope_refs": ["b", "a"]})
    right = _command(payload={"scope_refs": ["a", "b"]})

    assert commands.idempotency_address(left) == commands.idempotency_address(right)
    assert commands.compute_command_hash(left) != commands.compute_command_hash(right)


def test_different_operations_share_the_same_capability_scope_key_address() -> None:
    commands = _commands()
    left = _command(command_type="identity.create")
    right = _command(command_type="identity.replace")

    assert commands.idempotency_address(left) == commands.idempotency_address(right)
    assert commands.compute_command_hash(left) != commands.compute_command_hash(right)


def test_command_result_preserves_value_error_and_replay_state() -> None:
    commands = _commands()
    error = commands.CoreError(
        error_id="err-00000000-0000-4000-8000-000000000001",
        code=commands.CoreErrorCode.STALE_VERSION,
        message="stale version",
        correlation_id="flow-1",
        audit_event_id=None,
        retryable=True,
        details_ref=None,
    )

    success = commands.CommandResult[str](value="ok", event_ids=(), error=None)
    failure = commands.CommandResult[str](value=None, event_ids=(), error=error, replayed=True)
    assert success.value == "ok"
    assert success.replayed is False
    assert failure.error == error
    assert failure.replayed is True


def test_command_payload_is_deeply_immutable_and_hash_stable() -> None:
    commands = _commands()
    command = _command(
        payload={
            "scope_refs": ["lineage-root"],
            "action": {"mode": "before"},
        }
    )
    command_hash = commands.compute_command_hash(command)
    address = commands.idempotency_address(command)
    action = command.payload["action"]
    scope_refs = command.payload["scope_refs"]

    assert isinstance(action, Mapping)
    assert not isinstance(action, dict)
    assert isinstance(scope_refs, tuple)
    with pytest.raises(TypeError):
        action["mode"] = "after"
    with pytest.raises(TypeError):
        dict.__setitem__(action, "mode", "after")
    with pytest.raises(TypeError):
        command.payload["new"] = "value"

    assert commands.compute_command_hash(command) == command_hash
    assert commands.idempotency_address(command) == address

    copied = command.model_copy(update={"payload": {"action": {"mode": "copy"}}})
    copied_action = copied.payload["action"]
    assert isinstance(copied_action, Mapping)
    with pytest.raises(TypeError):
        copied_action["mode"] = "mutated"
    with pytest.raises(ValidationError):
        command.model_copy(update={"payload": {"private_key_bytes": "secret"}})
    with pytest.raises(ValidationError):
        command.copy(update={"payload": {"private_key_bytes": "secret"}})

    bypass = BaseModel.model_copy(
        command,
        update={"payload": {"raw_key": "secret"}},
    )
    with pytest.raises(ValidationError):
        commands.compute_command_hash(bypass)


@pytest.mark.parametrize(
    "payload",
    [
        {"private_key_bytes": "secret"},
        {"nested": {"raw_key": "secret"}},
        {"nested": [{"default_shared_key": "secret"}]},
        {"opaque_binary": b"secret"},
        {"non_json_set": {"value"}},
        {"custom_object": object()},
        {"not_finite": float("nan")},
        {"not_finite_decimal": Decimal("Infinity")},
        {"surrogate": "\ud800"},
    ],
    ids=(
        "private-key-bytes",
        "raw-key",
        "default-shared-key",
        "binary",
        "set",
        "custom-object",
        "non-finite-float",
        "non-finite-decimal",
        "surrogate",
    ),
)
def test_command_payload_rejects_raw_key_material(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _command(payload=payload)


def test_prepare_command_binds_hash_address_and_handler_to_one_snapshot() -> None:
    commands = _commands()
    original = _command(payload={"scope_refs": ["x"], "action": {"mode": "before"}})
    bypass = BaseModel.model_copy(
        original,
        update={"payload": {"scope_refs": ["x"], "action": {"mode": "before"}}},
    )

    prepared = commands.prepare_mutation_command(bypass)
    bypass.payload["action"]["mode"] = "after"
    bypass.payload["scope_refs"].append("y")

    assert prepared.mutation_command.payload["action"]["mode"] == "before"
    assert prepared.execution_context.command_hash == commands.compute_command_hash(
        prepared.mutation_command
    )
    assert prepared.idempotency_address == commands.idempotency_address(
        prepared.mutation_command
    )
    with pytest.raises(TypeError):
        prepared.mutation_command.payload["action"]["mode"] = "mutated"
