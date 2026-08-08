"""Atomic MemoryRequest submission with one registry-bound Ledger event."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import ValidationError

from amadeus_core.clock import Clock
from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.validation import (
    ContentHashMismatch,
    validate_authoritative_record,
)
from amadeus_core.contracts.vault import RelationshipVault
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.reader import SQLiteAuthorityReader
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError, SQLiteUnitOfWork

from ._event_writer import _GovernanceEventWriter
from ._service import (
    GovernanceViolation,
    failure_result,
    semantic_input_hash_matches,
    typed_result,
)


_EVENT_BY_REQUEST_TYPE = {
    "confidentiality_request": "confidentiality_request_submitted",
    "correction_request": "correction_request_submitted",
    "non_mention_request": "non_mention_request_submitted",
}
_REQUIRED_COMMAND_PAYLOAD_FIELDS = frozenset(
    {"scope_refs", "event_id", "instance_id", "semantic_input_hash"}
)
_OPTIONAL_COMMAND_PAYLOAD_FIELDS = frozenset({"causation_id"})


def _request_stable_identity(request: MemoryRequest) -> tuple[object, ...]:
    header = request.record_header.model_dump(mode="python")
    header.pop("content_hash")
    return (
        header,
        request.request_id,
        request.request_type,
        request.identity_id,
        request.lineage_id,
        request.branch_id,
        request.vault_id,
        request.requester_id,
        request.submitted_at,
        request.target_refs,
        request.statement,
        request.requested_scope,
    )


def _fail(code: CoreErrorCode) -> None:
    raise GovernanceViolation(code)


def _validate_record_id(value: object, prefix: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        _fail(CoreErrorCode.RECORD_ID_MISMATCH)
    return value


def _normalized_absent_targets(
    command: MutationCommandEnvelope,
) -> frozenset[str]:
    normalized = {
        item.target_record_ref: (
            0 if item.expected_version == "absent" else item.expected_version
        )
        for item in command.expected_versions
    }
    expected = frozenset(command.target_record_refs)
    if (
        len(expected) != len(command.target_record_refs)
        or set(normalized) != expected
        or any(value != 0 for value in normalized.values())
    ):
        _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    return expected


def _validated_scope_refs(command: MutationCommandEnvelope) -> tuple[str, ...]:
    value = command.payload.get("scope_refs")
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or any(not isinstance(item, str) for item in value)
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    return tuple(cast(Sequence[str], value))


def _validated_authorities(
    repository: AuthorityRepository,
    request: MemoryRequest,
) -> tuple[Identity, Lineage, Branch, RelationshipVault]:
    identity = repository.get_validated(request.identity_id)
    lineage = repository.get_validated(request.lineage_id)
    branch = repository.get_validated(request.branch_id)
    vault = repository.get_validated(request.vault_id)
    if (
        not isinstance(identity, Identity)
        or not isinstance(lineage, Lineage)
        or not isinstance(branch, Branch)
        or identity.lineage_id != request.lineage_id
        or identity.active_branch_id != request.branch_id
        or identity.lifecycle_state != "active"
        or lineage.root_identity_id != request.identity_id
        or branch.identity_id != request.identity_id
        or branch.lineage_id != request.lineage_id
        or branch.status != "active"
    ):
        _fail(CoreErrorCode.ACTIVE_BRANCH_INVARIANT)
    if (
        not isinstance(vault, RelationshipVault)
        or vault.identity_id != request.identity_id
        or vault.lineage_id != request.lineage_id
        or vault.branch_id != request.branch_id
        or vault.relationship_principal_id != request.requester_id
        or vault.status == "sealed"
    ):
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
    return identity, lineage, branch, vault


def _validate_target_authorities(
    repository: AuthorityRepository,
    request: MemoryRequest,
) -> None:
    for target_ref in request.target_refs:
        target = repository.get_validated(target_ref)
        if target is None:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if not isinstance(target, (LedgerEvent, AutobiographicalMemory)):
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        header = target.record_header
        if (
            header.identity_id != request.identity_id
            or header.lineage_id != request.lineage_id
            or header.branch_id != request.branch_id
        ):
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        target_vault_id = (
            target.governing_vault_id
            if isinstance(target, AutobiographicalMemory)
            else target.vault_id
        )
        if target_vault_id not in (None, request.vault_id):
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)


def _validate_submit(
    repository: AuthorityRepository,
    command: MutationCommandEnvelope,
    request: MemoryRequest,
) -> tuple[str, str, Identity]:
    write_spec = WRITE_API_BY_NAME["submit_memory_request"]
    if command.actor.actor_type not in write_spec.actor_types:
        code = (
            CoreErrorCode.LLM_COMMIT_FORBIDDEN
            if command.actor.actor_type == "llm"
            else CoreErrorCode.HEADER_BODY_MISMATCH
        )
        _fail(code)
    if command.command_type != "memory_request.submit":
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if frozenset(command.payload) != (
        _REQUIRED_COMMAND_PAYLOAD_FIELDS
        | (frozenset(command.payload) & _OPTIONAL_COMMAND_PAYLOAD_FIELDS)
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)

    event_id = _validate_record_id(
        command.payload.get("event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    instance_id = _validate_record_id(command.payload.get("instance_id"), "ins-")
    causation_id = command.payload.get("causation_id")
    if causation_id is not None and (
        not isinstance(causation_id, str)
        or not causation_id.startswith(("evt-", "cmd-"))
    ):
        _fail(CoreErrorCode.RECORD_ID_MISMATCH)
    _validate_record_id(request.request_id, TYPE_REGISTRY["MemoryRequest"].id_prefix)
    _validate_record_id(command.command_id, "cmd-")

    expected_targets = frozenset({request.request_id, event_id})
    if (
        tuple(command.target_record_refs) != (request.request_id, event_id)
        or _normalized_absent_targets(command) != expected_targets
    ):
        _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)

    if (
        request.status != "submitted"
        or request.version != 1
        or request.requested_scope != "current_vault"
        or request.resulting_proposal_ids
        or request.resulting_decision_ids
        or not request.statement.strip()
        or request.submitted_at != command.issued_at
        or request.record_header.record_type != "MemoryRequest"
        or request.record_header.record_id != request.request_id
        or request.record_header.identity_id != request.identity_id
        or request.record_header.lineage_id != request.lineage_id
        or request.record_header.branch_id != request.branch_id
        or request.record_header.created_at != request.submitted_at
        or request.record_header.created_by_event_id != event_id
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if command.actor.actor_type == "user" and (
        command.actor.actor_id != request.requester_id
    ):
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)

    identity, _lineage, _branch, _vault = _validated_authorities(
        repository,
        request,
    )
    if (
        request.record_header.deployment_policy_ref
        != identity.deployment_policy_ref
    ):
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    _validate_target_authorities(repository, request)

    supplied_scope = _validated_scope_refs(command)
    required_scope = (
        request.identity_id,
        request.lineage_id,
        request.branch_id,
        request.vault_id,
        *request.target_refs,
    )
    if (
        len(supplied_scope) != len(required_scope)
        or frozenset(supplied_scope) != frozenset(required_scope)
    ):
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)

    event_type = _EVENT_BY_REQUEST_TYPE[request.request_type]
    if event_type not in write_spec.emitted_event_types:
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    return event_id, instance_id, identity


class RequestService:
    """Submit immutable request evidence without creating a Proposal or Memory."""

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._unit_of_work = SQLiteUnitOfWork(database, clock=clock)
        self._reader = SQLiteAuthorityReader(database)

    def submit(
        self,
        mutation_command: MutationCommandEnvelope,
        request: MemoryRequest | Mapping[str, object],
    ) -> CommandResult[MemoryRequest]:
        try:
            request_snapshot = MemoryRequest.model_validate(
                request.model_dump(mode="python")
                if isinstance(request, MemoryRequest)
                else request
            )
            request_snapshot = cast(
                MemoryRequest,
                validate_authoritative_record(
                    "memory_request",
                    request_snapshot.model_dump(mode="python"),
                ),
            )
        except CoreContractViolation as error:
            return cast(
                CommandResult[MemoryRequest],
                failure_result(mutation_command, error.code),
            )
        except ContentHashMismatch:
            return cast(
                CommandResult[MemoryRequest],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HASH_SCOPE_MISMATCH,
                ),
            )
        except ValidationError:
            return cast(
                CommandResult[MemoryRequest],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        if not semantic_input_hash_matches(mutation_command, request_snapshot):
            return cast(
                CommandResult[MemoryRequest],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HASH_SCOPE_MISMATCH,
                ),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            event_id, instance_id, identity = _validate_submit(
                repository,
                command,
                request_snapshot,
            )
            event = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            ).request_submitted(
                request_snapshot,
                event_type=_EVENT_BY_REQUEST_TYPE[request_snapshot.request_type],
                event_id=event_id,
                instance_id=instance_id,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=cast(str | None, command.payload.get("causation_id")),
            )
            if not isinstance(event, LedgerEvent):
                raise TypeError("registered Ledger append returned the wrong type")
            stored = repository.save_authoritative(
                "memory_request",
                request_snapshot.model_dump(mode="python"),
            )
            if not isinstance(stored, MemoryRequest):
                raise TypeError("request authority save returned the wrong type")
            return CommandResult[object](
                value=stored.model_dump(mode="json"),
                event_ids=(event.event_id,),
                error=None,
                replayed=False,
            )

        try:
            result = self._unit_of_work.execute_command(mutation_command, handler)
        except GovernanceViolation as error:
            result = failure_result(mutation_command, error.code)
        except CoreContractViolation as error:
            result = failure_result(mutation_command, error.code)
        except ContentHashMismatch:
            result = failure_result(
                mutation_command,
                CoreErrorCode.HASH_SCOPE_MISMATCH,
            )
        except ValidationError:
            result = failure_result(
                mutation_command,
                CoreErrorCode.HEADER_BODY_MISMATCH,
            )
        typed = typed_result(
            result,
            MemoryRequest,
            receipt_label="MemoryRequest",
            schema_root="memory_request",
            expected_record_id=request_snapshot.request_id,
        )
        if typed.value is not None:
            current = self._reader.get_validated(request_snapshot.request_id)
            if (
                typed.value != request_snapshot
                or not isinstance(current, MemoryRequest)
                or _request_stable_identity(current)
                != _request_stable_identity(typed.value)
            ):
                raise ReceiptIntegrityError(
                    "MemoryRequest receipt value does not match its history anchor"
                )
        return typed


__all__ = ["RequestService"]
