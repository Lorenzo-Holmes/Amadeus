"""Mutation command contracts, hashing, and idempotency addressing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Generic, Literal, TypeVar, cast

from pydantic import Field

from .common import Actor, FrozenModel, JsonObject, UtcDatetime
from .errors import CoreContractViolation, CoreError, CoreErrorCode
from .hashing import canonical_json, sha256_hex


ExpectedVersionValue = Annotated[int, Field(strict=True, ge=0)] | Literal["absent"]


class ExpectedVersion(FrozenModel):
    target_record_ref: str
    expected_version: ExpectedVersionValue


class MutationCommandEnvelope(FrozenModel):
    command_id: str
    command_type: str
    actor: Actor
    actor_capability_id: str
    expected_versions: tuple[ExpectedVersion, ...]
    audit_context_id: str
    idempotency_key: str
    issued_at: UtcDatetime
    target_record_refs: tuple[str, ...]
    payload: JsonObject


ResultValue = TypeVar("ResultValue")


class CommandResult(FrozenModel, Generic[ResultValue]):
    value: ResultValue | None
    event_ids: tuple[str, ...]
    error: CoreError | None
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class IdempotencyAddress:
    actor_capability_id: str
    scope_hash: str
    key: str


@dataclass(frozen=True, slots=True)
class CommandExecutionContext:
    command_id: str
    command_hash: str
    audit_context_id: str


@dataclass(frozen=True, slots=True)
class PreparedMutationCommand:
    mutation_command: MutationCommandEnvelope
    idempotency_address: IdempotencyAddress
    execution_context: CommandExecutionContext


def _validated_command_snapshot(
    command: MutationCommandEnvelope,
) -> MutationCommandEnvelope:
    return MutationCommandEnvelope.model_validate(command.model_dump(mode="python"))


def _normalize_expected_versions_snapshot(
    command: MutationCommandEnvelope,
) -> dict[str, int]:
    targets = command.target_record_refs
    expected_targets = tuple(
        expected.target_record_ref for expected in command.expected_versions
    )
    if len(set(targets)) != len(targets):
        raise CoreContractViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    if len(set(expected_targets)) != len(expected_targets):
        raise CoreContractViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    if set(expected_targets) != set(targets):
        raise CoreContractViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    return {
        expected.target_record_ref: (
            0 if expected.expected_version == "absent" else expected.expected_version
        )
        for expected in command.expected_versions
    }


def normalize_expected_versions(command: MutationCommandEnvelope) -> dict[str, int]:
    return _normalize_expected_versions_snapshot(_validated_command_snapshot(command))


def normalize_command_for_hash(
    command: MutationCommandEnvelope,
) -> dict[str, object]:
    return _normalize_command_for_hash_snapshot(_validated_command_snapshot(command))


def _normalize_command_for_hash_snapshot(
    command: MutationCommandEnvelope,
) -> dict[str, object]:
    normalized_versions = _normalize_expected_versions_snapshot(command)
    sorted_targets = tuple(sorted(command.target_record_refs))
    body = command.model_dump(mode="python")
    body["target_record_refs"] = sorted_targets
    body["expected_versions"] = [
        {
            "target_record_ref": target,
            "expected_version": normalized_versions[target],
        }
        for target in sorted_targets
    ]
    return body


def _compute_command_hash_snapshot(command: MutationCommandEnvelope) -> str:
    return sha256_hex(canonical_json(_normalize_command_for_hash_snapshot(command)))


def compute_command_hash(command: MutationCommandEnvelope) -> str:
    return _compute_command_hash_snapshot(_validated_command_snapshot(command))


def _idempotency_address_snapshot(
    command: MutationCommandEnvelope,
) -> IdempotencyAddress:
    _normalize_expected_versions_snapshot(command)
    scope_refs = cast(Sequence[str], command.payload.get("scope_refs", ()))
    scope = {
        "target_record_refs": sorted(command.target_record_refs),
        "scope_refs": sorted(scope_refs),
    }
    return IdempotencyAddress(
        actor_capability_id=command.actor_capability_id,
        scope_hash=sha256_hex(canonical_json(scope)),
        key=command.idempotency_key,
    )


def idempotency_address(command: MutationCommandEnvelope) -> IdempotencyAddress:
    return _idempotency_address_snapshot(_validated_command_snapshot(command))


def prepare_mutation_command(
    command: MutationCommandEnvelope,
) -> PreparedMutationCommand:
    snapshot = _validated_command_snapshot(command)
    command_hash = _compute_command_hash_snapshot(snapshot)
    return PreparedMutationCommand(
        mutation_command=snapshot,
        idempotency_address=_idempotency_address_snapshot(snapshot),
        execution_context=CommandExecutionContext(
            command_id=snapshot.command_id,
            command_hash=command_hash,
            audit_context_id=snapshot.audit_context_id,
        ),
    )


__all__ = [
    "Actor",
    "CommandExecutionContext",
    "CommandResult",
    "CoreContractViolation",
    "CoreError",
    "CoreErrorCode",
    "ExpectedVersion",
    "ExpectedVersionValue",
    "IdempotencyAddress",
    "MutationCommandEnvelope",
    "PreparedMutationCommand",
    "compute_command_hash",
    "idempotency_address",
    "normalize_command_for_hash",
    "normalize_expected_versions",
    "prepare_mutation_command",
]
