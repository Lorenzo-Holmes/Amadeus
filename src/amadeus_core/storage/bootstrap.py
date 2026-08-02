"""Atomic four-record Core Genesis creation."""

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Mapping
from typing import cast

from pydantic import TypeAdapter, ValidationError

from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import FrozenModel, HashHex, RecordId
from amadeus_core.contracts.errors import (
    CoreContractViolation,
    CoreError,
    CoreErrorCode,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import ContentHashMismatch
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.ids import new_id
from ._records import _ZERO_HASH, _record_header, _seal_record
from .payloads import StoredLedgerPayload, prepare_inline_payload
from .repository import AuthorityRepository
from .unit_of_work import ReceiptIntegrityError, execute_command_on_connection


_RECORD_ID_ADAPTER = TypeAdapter(RecordId)


class _BootstrapValidationError(ValueError):
    """An expected caller-input or Genesis invariant failure."""


class BootstrapPreallocated(FrozenModel):
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    genesis_event_id: RecordId


class BootstrapCommand(FrozenModel):
    preallocated: BootstrapPreallocated
    deployment_policy_ref: str


class BootstrapResult(FrozenModel):
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    genesis_event_id: RecordId
    genesis_event_hash: HashHex


def _bootstrap_failure(command: MutationCommandEnvelope) -> CommandResult[BootstrapResult]:
    error = CoreError(
        error_id=new_id("error"),
        code=CoreErrorCode.BOOTSTRAP_FAILED,
        message=CoreErrorCode.BOOTSTRAP_FAILED.value,
        correlation_id=command.audit_context_id,
        audit_event_id=None,
        retryable=True,
        details_ref=None,
    )
    return CommandResult[BootstrapResult](
        value=None,
        event_ids=(),
        error=error,
        replayed=False,
    )


def _typed_result(result: CommandResult[object]) -> CommandResult[BootstrapResult]:
    try:
        value = (
            None
            if result.value is None
            else BootstrapResult.model_validate(
                dict(cast(Mapping[str, object], result.value))
            )
        )
    except (TypeError, ValueError) as error:
        if result.replayed:
            raise ReceiptIntegrityError(
                "bootstrap receipt value does not match BootstrapResult"
            ) from error
        raise
    return CommandResult[BootstrapResult](
        value=value,
        event_ids=result.event_ids,
        error=result.error,
        replayed=result.replayed,
    )


def _validate_record_id(value: object, field: str) -> str:
    try:
        return _RECORD_ID_ADAPTER.validate_python(value)
    except ValidationError as error:
        raise _BootstrapValidationError(f"invalid bootstrap {field}") from error


def _validate_bootstrap_request(
    command: MutationCommandEnvelope,
    bootstrap: BootstrapCommand,
) -> str:
    write_spec = WRITE_API_BY_NAME["bootstrap_core"]
    if command.actor.actor_type not in write_spec.actor_types:
        raise _BootstrapValidationError(
            "bootstrap actor type is outside the write API registry"
        )

    ids_by_record_type = dict(
        zip(
            write_spec.target_record_types,
            (
                bootstrap.preallocated.identity_id,
                bootstrap.preallocated.lineage_id,
                bootstrap.preallocated.branch_id,
                bootstrap.preallocated.genesis_event_id,
            ),
            strict=True,
        )
    )
    for record_type, record_id in ids_by_record_type.items():
        if not record_id.startswith(TYPE_REGISTRY[record_type].id_prefix):
            raise _BootstrapValidationError(
                f"invalid preallocated {record_type} identifier"
            )

    expected_targets = frozenset(ids_by_record_type.values())
    if (
        len(command.target_record_refs) != len(expected_targets)
        or frozenset(command.target_record_refs) != expected_targets
    ):
        raise _BootstrapValidationError(
            "bootstrap target refs do not match preallocated ids"
        )
    expected_versions = {
        expected.target_record_ref: expected.expected_version
        for expected in command.expected_versions
    }
    if set(expected_versions) != expected_targets or any(
        value not in (0, "absent") for value in expected_versions.values()
    ):
        raise _BootstrapValidationError(
            "bootstrap requires all four targets to be absent"
        )

    instance_id = command.payload.get("instance_id")
    if not isinstance(instance_id, str):
        raise _BootstrapValidationError(
            "bootstrap command payload requires instance_id"
        )
    _validate_record_id(instance_id, "instance_id")
    if not instance_id.startswith("ins-"):
        raise _BootstrapValidationError(
            "bootstrap instance_id must use the ins- prefix"
        )
    _validate_record_id(command.actor.actor_id, "actor_id")
    causation_id = command.payload.get("causation_id")
    if causation_id is not None:
        _validate_record_id(causation_id, "causation_id")
    return instance_id


def _lineage_hash(bootstrap: BootstrapCommand) -> str:
    preallocated = bootstrap.preallocated
    preimage = {
        "kind": "core-genesis-lineage-v0.1",
        "identity_id": preallocated.identity_id,
        "lineage_id": preallocated.lineage_id,
        "branch_id": preallocated.branch_id,
        "deployment_policy_ref": bootstrap.deployment_policy_ref,
    }
    return sha256_hex(canonical_json(preimage))


def _validate_semantic_input_hash(
    command: MutationCommandEnvelope,
    bootstrap: BootstrapCommand,
) -> None:
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(bootstrap.model_dump(mode="python")))
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        raise _BootstrapValidationError("bootstrap semantic input hash mismatch")


def _build_genesis_records(
    command: MutationCommandEnvelope,
    bootstrap: BootstrapCommand,
    execution_context: CommandExecutionContext,
    instance_id: str,
) -> tuple[Identity, Lineage, Branch, LedgerEvent, StoredLedgerPayload]:
    ids = bootstrap.preallocated
    created_at = command.issued_at
    common_header = {
        "identity_id": ids.identity_id,
        "lineage_id": ids.lineage_id,
        "branch_id": ids.branch_id,
        "created_at": created_at,
        "created_by_event_id": ids.genesis_event_id,
        "deployment_policy_ref": bootstrap.deployment_policy_ref,
    }
    identity = cast(
        Identity,
        _seal_record(
            Identity,
            {
                "record_header": _record_header(
                    "Identity", ids.identity_id, **common_header
                ),
                "identity_id": ids.identity_id,
                "canonical_name": "Amadeus",
                "lineage_id": ids.lineage_id,
                "active_branch_id": ids.branch_id,
                "lifecycle_state": "active",
                "created_from_snapshot_id": None,
                "deployment_policy_ref": bootstrap.deployment_policy_ref,
                "version": 1,
            },
        ),
    )
    lineage = cast(
        Lineage,
        _seal_record(
            Lineage,
            {
                "record_header": _record_header(
                    "Lineage", ids.lineage_id, **common_header
                ),
                "lineage_id": ids.lineage_id,
                "root_snapshot_id": None,
                "root_identity_id": ids.identity_id,
                "root_branch_id": ids.branch_id,
                "created_at": created_at,
                "lineage_hash": _lineage_hash(bootstrap),
                "version": 1,
            },
        ),
    )
    branch = cast(
        Branch,
        _seal_record(
            Branch,
            {
                "record_header": _record_header(
                    "Branch", ids.branch_id, **common_header
                ),
                "branch_id": ids.branch_id,
                "lineage_id": ids.lineage_id,
                "identity_id": ids.identity_id,
                "parent_branch_ids": (),
                "fork_reason": "explicit_reconstruction",
                "fork_event_id": ids.genesis_event_id,
                "base_ledger_seq": 0,
                "status": "active",
                "status_reason_event_id": ids.genesis_event_id,
                "activated_at": created_at,
                "deactivated_at": None,
                "terminated_at": None,
                "merge_policy": "explicit_only",
                "version": 1,
            },
        ),
    )
    payload = prepare_inline_payload(command.payload)
    event = cast(
        LedgerEvent,
        _seal_record(
            LedgerEvent,
            {
                "record_header": _record_header(
                    "LedgerEvent", ids.genesis_event_id, **common_header
                ),
                "event_id": ids.genesis_event_id,
                "ledger_seq": 1,
                "identity_id": ids.identity_id,
                "lineage_id": ids.lineage_id,
                "branch_id": ids.branch_id,
                "instance_id": instance_id,
                "vault_id": None,
                "event_type": WRITE_API_BY_NAME["bootstrap_core"].emitted_event_types[0],
                "occurred_at": created_at,
                "ingested_at": created_at,
                "actor_type": command.actor.actor_type,
                "actor_id": command.actor.actor_id,
                "mutation_command_id": execution_context.command_id,
                "mutation_command_hash": execution_context.command_hash,
                "payload_ref": payload.payload_ref,
                "causation_id": command.payload.get("causation_id"),
                "correlation_id": execution_context.audit_context_id,
                "previous_event_hash": None,
                "event_hash": _ZERO_HASH,
                "version": 1,
            },
        ),
    )
    return identity, lineage, branch, event, payload


def _insert_identity(repository: AuthorityRepository, identity: Identity) -> None:
    repository.save_authoritative("identity", identity.model_dump(mode="python"))


def _insert_lineage(repository: AuthorityRepository, lineage: Lineage) -> None:
    repository.save_authoritative("lineage", lineage.model_dump(mode="python"))


def _insert_branch(repository: AuthorityRepository, branch: Branch) -> None:
    repository.save_authoritative("branch", branch.model_dump(mode="python"))


def _insert_event(
    repository: AuthorityRepository,
    event: LedgerEvent,
    payload: StoredLedgerPayload,
) -> None:
    repository.append_ledger_event(event.model_dump(mode="python"), payload=payload)


def bootstrap_core(
    connection: sqlite3.Connection,
    command: MutationCommandEnvelope,
    bootstrap: BootstrapCommand,
) -> CommandResult[BootstrapResult]:
    """Create Identity, Lineage, Branch, and Genesis LedgerEvent atomically."""

    try:
        bootstrap_snapshot = BootstrapCommand.model_validate(
            bootstrap.model_dump(mode="python")
            if isinstance(bootstrap, BootstrapCommand)
            else bootstrap
        )
        _validate_semantic_input_hash(command, bootstrap_snapshot)
    except (ValidationError, _BootstrapValidationError):
        return _bootstrap_failure(command)

    def handler(
        repository: AuthorityRepository,
        mutation_command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> CommandResult[object]:
        instance_id = _validate_bootstrap_request(mutation_command, bootstrap_snapshot)
        identity, lineage, branch, event, payload = _build_genesis_records(
            mutation_command,
            bootstrap_snapshot,
            execution_context,
            instance_id,
        )
        _insert_identity(repository, identity)
        _insert_lineage(repository, lineage)
        _insert_branch(repository, branch)
        _insert_event(repository, event, payload)
        if repository.count_active_branches(identity.identity_id) != 1:
            raise _BootstrapValidationError(
                "bootstrap did not create exactly one active branch"
            )
        return CommandResult[object](
            value=BootstrapResult(
                identity_id=identity.identity_id,
                lineage_id=lineage.lineage_id,
                branch_id=branch.branch_id,
                genesis_event_id=event.event_id,
                genesis_event_hash=event.event_hash,
            ),
            event_ids=(event.event_id,),
            error=None,
            replayed=False,
        )

    try:
        result = execute_command_on_connection(connection, command, handler)
    except (
        _BootstrapValidationError,
        CoreContractViolation,
        ContentHashMismatch,
        sqlite3.IntegrityError,
    ):
        return _bootstrap_failure(command)
    return _typed_result(result)


__all__ = [
    "BootstrapCommand",
    "BootstrapPreallocated",
    "BootstrapResult",
    "bootstrap_core",
]
