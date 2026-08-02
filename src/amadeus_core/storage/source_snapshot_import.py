"""Atomic initial SourceSnapshot import after Core Genesis."""

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from pydantic import TypeAdapter, ValidationError

from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import FrozenModel, RecordId
from amadeus_core.contracts.errors import (
    CoreContractViolation,
    CoreError,
    CoreErrorCode,
    RETRYABLE_ERROR_CODES,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.source_snapshot import SourceSnapshot
from amadeus_core.contracts.validation import (
    ContentHashMismatch,
    validate_authoritative_record,
)
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.ids import new_id

from ._records import _ZERO_HASH, _record_header, _reseal_update, _seal_record
from .ledger import get_verified_ledger_head
from .payloads import StoredLedgerPayload, prepare_inline_payload
from .repository import AuthorityRepository
from .unit_of_work import ReceiptIntegrityError, execute_command_on_connection


_RECORD_ID_ADAPTER = TypeAdapter(RecordId)


class SourceSnapshotImportResult(FrozenModel):
    snapshot_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    event_id: RecordId


@dataclass(frozen=True, slots=True)
class _SourceImportViolation(ValueError):
    code: CoreErrorCode


def _failure_result(
    command: MutationCommandEnvelope,
    code: CoreErrorCode,
) -> CommandResult[SourceSnapshotImportResult]:
    return CommandResult[SourceSnapshotImportResult](
        value=None,
        event_ids=(),
        error=CoreError(
            error_id=new_id("error"),
            code=code,
            message=code.value,
            correlation_id=command.audit_context_id,
            audit_event_id=None,
            retryable=code in RETRYABLE_ERROR_CODES,
            details_ref=None,
        ),
        replayed=False,
    )


def _semantic_input_hash_matches(
    command: MutationCommandEnvelope,
    snapshot: SourceSnapshot,
) -> bool:
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(snapshot.model_dump(mode="python")))
    return isinstance(supplied, str) and hmac.compare_digest(supplied, expected)


def _typed_result(
    result: CommandResult[object],
) -> CommandResult[SourceSnapshotImportResult]:
    try:
        value = (
            None
            if result.value is None
            else SourceSnapshotImportResult.model_validate(
                dict(cast(Mapping[str, object], result.value))
            )
        )
    except (TypeError, ValueError) as error:
        if result.replayed:
            raise ReceiptIntegrityError(
                "source snapshot receipt value does not match SourceSnapshotImportResult"
            ) from error
        raise
    return CommandResult[SourceSnapshotImportResult](
        value=value,
        event_ids=result.event_ids,
        error=result.error,
        replayed=result.replayed,
    )


def _validate_record_id(value: object, code: CoreErrorCode) -> str:
    try:
        return _RECORD_ID_ADAPTER.validate_python(value)
    except ValidationError as error:
        raise _SourceImportViolation(code) from error


def _validated_record(
    schema_root: str,
    record: FrozenModel | None,
    expected_type: type[FrozenModel],
) -> FrozenModel:
    if not isinstance(record, expected_type):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    return validate_authoritative_record(schema_root, record.model_dump(mode="python"))


def _validate_import_request(
    connection: sqlite3.Connection,
    repository: AuthorityRepository,
    command: MutationCommandEnvelope,
    snapshot: SourceSnapshot,
) -> tuple[Identity, Lineage, Branch, LedgerEvent, str, str]:
    write_spec = WRITE_API_BY_NAME["import_source_snapshot"]
    if command.actor.actor_type not in write_spec.actor_types:
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)

    event_id = command.payload.get("event_id")
    instance_id = command.payload.get("instance_id")
    if not isinstance(event_id, str) or not isinstance(instance_id, str):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    _validate_record_id(event_id, CoreErrorCode.HEADER_BODY_MISMATCH)
    _validate_record_id(instance_id, CoreErrorCode.HEADER_BODY_MISMATCH)
    if not instance_id.startswith("ins-"):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    _validate_record_id(command.actor.actor_id, CoreErrorCode.HEADER_BODY_MISMATCH)
    if not event_id.startswith(TYPE_REGISTRY["LedgerEvent"].id_prefix):
        raise _SourceImportViolation(CoreErrorCode.RECORD_ID_MISMATCH)
    causation_id = command.payload.get("causation_id")
    if causation_id is not None:
        _validate_record_id(causation_id, CoreErrorCode.HEADER_BODY_MISMATCH)

    ids_by_record_type = dict(
        zip(
            write_spec.target_record_types,
            (snapshot.snapshot_id, snapshot.identity_id, snapshot.lineage_id, event_id),
            strict=True,
        )
    )
    for record_type, record_id in ids_by_record_type.items():
        if not record_id.startswith(TYPE_REGISTRY[record_type].id_prefix):
            raise _SourceImportViolation(CoreErrorCode.RECORD_ID_MISMATCH)
    expected_targets = frozenset(ids_by_record_type.values())
    if (
        len(command.target_record_refs) != len(expected_targets)
        or frozenset(command.target_record_refs) != expected_targets
    ):
        raise _SourceImportViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)

    validated_snapshot = cast(
        SourceSnapshot,
        validate_authoritative_record(
            "source_snapshot", snapshot.model_dump(mode="python")
        ),
    )
    identity = cast(
        Identity,
        _validated_record(
            "identity", repository.get_validated(snapshot.identity_id), Identity
        ),
    )
    lineage = cast(
        Lineage,
        _validated_record(
            "lineage", repository.get_validated(snapshot.lineage_id), Lineage
        ),
    )
    branch = cast(
        Branch,
        _validated_record(
            "branch", repository.get_validated(snapshot.branch_id), Branch
        ),
    )
    try:
        ledger_head = get_verified_ledger_head(connection, snapshot.branch_id)
    except ReceiptIntegrityError as error:
        raise _SourceImportViolation(CoreErrorCode.HASH_SCOPE_MISMATCH) from error
    genesis = cast(
        LedgerEvent,
        _validated_record("event", ledger_head, LedgerEvent),
    )

    normalized_expected = {
        expected.target_record_ref: (
            0 if expected.expected_version == "absent" else expected.expected_version
        )
        for expected in command.expected_versions
    }
    required_expected = {
        snapshot.snapshot_id: 0,
        event_id: 0,
        identity.identity_id: identity.version,
        lineage.lineage_id: lineage.version,
    }
    if normalized_expected != required_expected:
        raise _SourceImportViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)

    linked = (
        snapshot.identity_id == identity.identity_id == lineage.root_identity_id,
        snapshot.lineage_id == identity.lineage_id == lineage.lineage_id,
        snapshot.branch_id
        == identity.active_branch_id
        == lineage.root_branch_id
        == branch.branch_id,
        branch.identity_id == identity.identity_id,
        branch.lineage_id == lineage.lineage_id,
    )
    if not all(linked) or branch.status != "active":
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if identity.created_from_snapshot_id is not None or lineage.root_snapshot_id is not None:
        raise _SourceImportViolation(CoreErrorCode.STALE_VERSION)
    if (
        snapshot.version != 1
        or snapshot.status != "active"
        or snapshot.parent_snapshot_id is not None
    ):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if (
        snapshot.deployment_policy_ref != identity.deployment_policy_ref
        or snapshot.record_header.deployment_policy_ref
        != identity.record_header.deployment_policy_ref
        or lineage.record_header.deployment_policy_ref
        != identity.record_header.deployment_policy_ref
        or branch.record_header.deployment_policy_ref
        != identity.record_header.deployment_policy_ref
    ):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if (
        snapshot.record_header.created_at != command.issued_at
        or snapshot.imported_at != command.issued_at
        or snapshot.record_header.created_by_event_id != event_id
        or snapshot.cutoff_at > snapshot.imported_at
    ):
        raise _SourceImportViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if (
        genesis.event_type != "identity_genesis_created"
        or genesis.ledger_seq != 1
        or genesis.previous_event_hash is not None
        or genesis.identity_id != identity.identity_id
        or genesis.lineage_id != lineage.lineage_id
        or genesis.branch_id != branch.branch_id
    ):
        raise _SourceImportViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)
    return identity, lineage, branch, genesis, event_id, instance_id


def _build_updates_and_event(
    command: MutationCommandEnvelope,
    execution_context: CommandExecutionContext,
    snapshot: SourceSnapshot,
    identity: Identity,
    lineage: Lineage,
    genesis: LedgerEvent,
    event_id: str,
    instance_id: str,
) -> tuple[Identity, Lineage, LedgerEvent, StoredLedgerPayload]:
    updated_identity = cast(
        Identity,
        _reseal_update(
            identity,
            {
                "created_from_snapshot_id": snapshot.snapshot_id,
                "version": identity.version + 1,
            },
        ),
    )
    updated_lineage = cast(
        Lineage,
        _reseal_update(
            lineage,
            {
                "root_snapshot_id": snapshot.snapshot_id,
                "version": lineage.version + 1,
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
                    "LedgerEvent",
                    event_id,
                    identity_id=snapshot.identity_id,
                    lineage_id=snapshot.lineage_id,
                    branch_id=snapshot.branch_id,
                    created_at=command.issued_at,
                    created_by_event_id=event_id,
                    deployment_policy_ref=snapshot.deployment_policy_ref,
                ),
                "event_id": event_id,
                "ledger_seq": 2,
                "identity_id": snapshot.identity_id,
                "lineage_id": snapshot.lineage_id,
                "branch_id": snapshot.branch_id,
                "instance_id": instance_id,
                "vault_id": None,
                "event_type": WRITE_API_BY_NAME[
                    "import_source_snapshot"
                ].emitted_event_types[0],
                "occurred_at": command.issued_at,
                "ingested_at": command.issued_at,
                "actor_type": command.actor.actor_type,
                "actor_id": command.actor.actor_id,
                "mutation_command_id": execution_context.command_id,
                "mutation_command_hash": execution_context.command_hash,
                "payload_ref": payload.payload_ref,
                "causation_id": command.payload.get("causation_id"),
                "correlation_id": execution_context.audit_context_id,
                "previous_event_hash": genesis.event_hash,
                "event_hash": _ZERO_HASH,
                "version": 1,
            },
        ),
    )
    return updated_identity, updated_lineage, event, payload


def _insert_snapshot(
    repository: AuthorityRepository,
    snapshot: SourceSnapshot,
) -> None:
    repository.save_authoritative(
        "source_snapshot", snapshot.model_dump(mode="python")
    )


def _update_identity(repository: AuthorityRepository, identity: Identity) -> None:
    repository.save_authoritative("identity", identity.model_dump(mode="python"))


def _update_lineage(repository: AuthorityRepository, lineage: Lineage) -> None:
    repository.save_authoritative("lineage", lineage.model_dump(mode="python"))


def _append_import_event(
    repository: AuthorityRepository,
    event: LedgerEvent,
    payload: StoredLedgerPayload,
) -> None:
    repository.append_ledger_event(event.model_dump(mode="python"), payload=payload)


def import_source_snapshot(
    connection: sqlite3.Connection,
    command: MutationCommandEnvelope,
    snapshot: SourceSnapshot,
) -> CommandResult[SourceSnapshotImportResult]:
    """Import the initial source snapshot in its own mutation transaction."""

    try:
        snapshot_copy = SourceSnapshot.model_validate(snapshot.model_dump(mode="python"))
    except ValidationError:
        return _failure_result(command, CoreErrorCode.HEADER_BODY_MISMATCH)
    if not _semantic_input_hash_matches(command, snapshot_copy):
        return _failure_result(command, CoreErrorCode.HASH_SCOPE_MISMATCH)

    def handler(
        repository: AuthorityRepository,
        mutation_command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> CommandResult[object]:
        identity, lineage, _branch, genesis, event_id, instance_id = (
            _validate_import_request(
                connection,
                repository,
                mutation_command,
                snapshot_copy,
            )
        )
        updated_identity, updated_lineage, event, payload = _build_updates_and_event(
            mutation_command,
            execution_context,
            snapshot_copy,
            identity,
            lineage,
            genesis,
            event_id,
            instance_id,
        )
        _insert_snapshot(repository, snapshot_copy)
        _update_identity(repository, updated_identity)
        _update_lineage(repository, updated_lineage)
        _append_import_event(repository, event, payload)
        return CommandResult[object](
            value=SourceSnapshotImportResult(
                snapshot_id=snapshot_copy.snapshot_id,
                identity_id=updated_identity.identity_id,
                lineage_id=updated_lineage.lineage_id,
                event_id=event.event_id,
            ),
            event_ids=(event.event_id,),
            error=None,
            replayed=False,
        )

    try:
        result = execute_command_on_connection(connection, command, handler)
    except _SourceImportViolation as error:
        return _failure_result(command, error.code)
    except CoreContractViolation as error:
        return _failure_result(command, error.code)
    except ContentHashMismatch:
        return _failure_result(command, CoreErrorCode.HASH_SCOPE_MISMATCH)
    except sqlite3.IntegrityError:
        return _failure_result(command, CoreErrorCode.HEADER_BODY_MISMATCH)
    return _typed_result(result)


__all__ = ["SourceSnapshotImportResult", "import_source_snapshot"]
