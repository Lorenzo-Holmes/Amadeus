"""Append, verify, and replay the authoritative per-branch Ledger chain."""

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, cast

from pydantic import Field, TypeAdapter, ValidationError

from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import (
    FrozenModel,
    HashHex,
    JsonObject,
    RecordId,
)
from amadeus_core.contracts.errors import (
    CoreContractViolation,
    CoreError,
    CoreErrorCode,
    RETRYABLE_ERROR_CODES,
)
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import ContentHashMismatch
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.ids import new_id

from ._records import (
    _SESSION_LEDGER_EVENT_TYPES,
    _ZERO_HASH,
    _record_header,
    _seal_record,
)
from .payloads import (
    StoredLedgerPayload,
    _load_closed_json,
    closed_json_object,
    prepare_inline_payload,
    validate_authority_bound_payload,
)
from .repository import AuthorityRepository
from .unit_of_work import ReceiptIntegrityError, execute_command_on_connection


_RECORD_ID = TypeAdapter(RecordId)
_HASH_HEX = TypeAdapter(HashHex)
_NONNEGATIVE_INT = TypeAdapter(Annotated[int, Field(strict=True, ge=0)])
_REQUIRED_PAYLOAD_FIELDS = frozenset(
    {
        "event_id",
        "identity_id",
        "lineage_id",
        "branch_id",
        "instance_id",
        "vault_id",
        "event_type",
        "ledger_seq",
        "expected_previous_event_hash",
        "event_payload",
        "scope_refs",
    }
)
_OPTIONAL_PAYLOAD_FIELDS = frozenset({"causation_id"})
_EXPECTED_SESSION_TRANSITION = {
    (): ("session_started", None),
    ("session_started",): ("conversation_message_recorded", "user"),
    ("session_started", "user"): (
        "conversation_message_recorded",
        "amadeus",
    ),
    ("session_started", "user", "amadeus"): ("session_ended", None),
}


class LedgerAppendResult(FrozenModel):
    event_id: RecordId
    ledger_seq: Annotated[int, Field(strict=True, ge=1)]
    event_hash: HashHex


class LedgerVerification(FrozenModel):
    valid: bool
    checked_events: Annotated[int, Field(strict=True, ge=0)]
    first_invalid_seq: Annotated[int, Field(strict=True, ge=1)] | None
    root_hash: HashHex | None


class LedgerReplayResult(FrozenModel):
    branch_id: RecordId
    through_ledger_seq: Annotated[int, Field(strict=True, ge=0)]
    root_hash: HashHex | None
    events: tuple[LedgerEvent, ...]
    resolved_inline_payloads: tuple[JsonObject | None, ...]


@dataclass(frozen=True, slots=True)
class _LedgerViolation(ValueError):
    code: CoreErrorCode


@dataclass(frozen=True, slots=True)
class _VerifiedEvent:
    event: LedgerEvent
    payload: StoredLedgerPayload
    inline_payload: Mapping[str, object] | None


def _failure_result(
    command: MutationCommandEnvelope,
    code: CoreErrorCode,
) -> CommandResult[LedgerAppendResult]:
    return CommandResult[LedgerAppendResult](
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


def _typed_result(
    result: CommandResult[object],
) -> CommandResult[LedgerAppendResult]:
    try:
        value = (
            None
            if result.value is None
            else LedgerAppendResult.model_validate(
                dict(cast(Mapping[str, object], result.value))
            )
        )
    except (TypeError, ValueError) as error:
        if result.replayed:
            raise ReceiptIntegrityError(
                "Ledger receipt value does not match LedgerAppendResult"
            ) from error
        raise
    return CommandResult[LedgerAppendResult](
        value=value,
        event_ids=result.event_ids,
        error=result.error,
        replayed=result.replayed,
    )


def _record_id(value: object, prefix: str) -> str:
    try:
        validated = _RECORD_ID.validate_python(value)
    except ValidationError as error:
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH) from error
    if not validated.startswith(prefix):
        raise _LedgerViolation(CoreErrorCode.RECORD_ID_MISMATCH)
    return validated


def _closed_command_payload(command: MutationCommandEnvelope) -> Mapping[str, object]:
    payload = command.payload
    fields = frozenset(payload)
    if not _REQUIRED_PAYLOAD_FIELDS <= fields or not fields <= (
        _REQUIRED_PAYLOAD_FIELDS | _OPTIONAL_PAYLOAD_FIELDS
    ):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    scope_refs = payload["scope_refs"]
    if (
        not isinstance(scope_refs, Sequence)
        or isinstance(scope_refs, (str, bytes, bytearray))
        or any(not isinstance(item, str) for item in scope_refs)
    ):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if not isinstance(payload["event_payload"], Mapping):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    return payload


def _validated_request(
    command: MutationCommandEnvelope,
) -> tuple[
    Mapping[str, object],
    str,
    str,
    str,
    str,
    str,
    str,
    int,
    str,
]:
    payload = _closed_command_payload(command)
    write_spec = WRITE_API_BY_NAME["append_session_event"]
    event_type = payload["event_type"]
    if (
        command.actor.actor_type not in write_spec.actor_types
        or not isinstance(event_type, str)
        or event_type not in write_spec.emitted_event_types
    ):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    event_id = _record_id(payload["event_id"], TYPE_REGISTRY["LedgerEvent"].id_prefix)
    identity_id = _record_id(payload["identity_id"], TYPE_REGISTRY["Identity"].id_prefix)
    lineage_id = _record_id(payload["lineage_id"], TYPE_REGISTRY["Lineage"].id_prefix)
    branch_id = _record_id(payload["branch_id"], TYPE_REGISTRY["Branch"].id_prefix)
    instance_id = _record_id(payload["instance_id"], "ins-")
    vault_id = _record_id(payload["vault_id"], TYPE_REGISTRY["RelationshipVault"].id_prefix)
    _record_id(command.command_id, "cmd-")
    _record_id(command.actor.actor_id, command.actor.actor_id[:4])
    causation_id = payload.get("causation_id")
    if causation_id is not None:
        _record_id(causation_id, "evt-")
    try:
        ledger_seq = _NONNEGATIVE_INT.validate_python(payload["ledger_seq"])
        previous_hash = _HASH_HEX.validate_python(
            payload["expected_previous_event_hash"]
        )
    except ValidationError as error:
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH) from error
    if ledger_seq < 2:
        raise _LedgerViolation(CoreErrorCode.STALE_VERSION)
    if command.target_record_refs != (event_id,) or len(command.expected_versions) != 1:
        raise _LedgerViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    expected = command.expected_versions[0]
    if expected.target_record_ref != event_id or expected.expected_version not in (
        0,
        "absent",
    ):
        raise _LedgerViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    return (
        payload,
        event_id,
        identity_id,
        lineage_id,
        branch_id,
        instance_id,
        vault_id,
        ledger_seq,
        previous_hash,
    )


def _authority_binding(
    repository: AuthorityRepository,
    identity_id: str,
    lineage_id: str,
    branch_id: str,
) -> tuple[Identity, Lineage, Branch]:
    identity = repository.get_validated(identity_id)
    lineage = repository.get_validated(lineage_id)
    branch = repository.get_validated(branch_id)
    if (
        not isinstance(identity, Identity)
        or not isinstance(lineage, Lineage)
        or not isinstance(branch, Branch)
        or identity.lineage_id != lineage_id
        or identity.active_branch_id != branch_id
        or lineage.root_identity_id != identity_id
        or lineage.root_branch_id != branch_id
        or branch.identity_id != identity_id
        or branch.lineage_id != lineage_id
        or branch.status != "active"
        or identity.lifecycle_state != "active"
    ):
        raise _LedgerViolation(CoreErrorCode.ACTIVE_BRANCH_INVARIANT)
    return identity, lineage, branch


def _projection_payload(row: sqlite3.Row) -> StoredLedgerPayload:
    return StoredLedgerPayload(
        payload_ref=row["payload_ref"],
        mode=row["payload_mode"],
        inline_json=row["payload_inline_json"],
        external_ref=row["payload_external_ref"],
        payload_hash=row["payload_hash"],
        media_type=row["media_type"],
    )


def _verified_events(
    connection: sqlite3.Connection,
    branch_id: str,
) -> tuple[tuple[_VerifiedEvent, ...], LedgerVerification]:
    owns_snapshot = not connection.in_transaction
    if owns_snapshot:
        connection.execute("BEGIN")
    try:
        return _verified_events_in_snapshot(connection, branch_id)
    finally:
        if owns_snapshot and connection.in_transaction:
            connection.rollback()


def _verified_events_in_snapshot(
    connection: sqlite3.Connection,
    branch_id: str,
) -> tuple[tuple[_VerifiedEvent, ...], LedgerVerification]:
    all_projection_rows = connection.execute(
        """
        SELECT
            event_id,
            branch_id,
            ledger_seq,
            previous_event_hash,
            event_hash,
            payload_ref,
            payload_mode,
            payload_inline_json,
            payload_external_ref,
            payload_hash,
            media_type
        FROM ledger_events
        ORDER BY ledger_seq, event_id
        """,
    ).fetchall()
    all_authority_rows = connection.execute(
            """
            SELECT record_id, branch_id, content_json
            FROM authority_records
            WHERE record_type = 'LedgerEvent'
               OR json_extract(content_json, '$.record_header.record_type') = 'LedgerEvent'
            """,
        ).fetchall()
    authority_rows = []
    for row in all_authority_rows:
        content_branch_id = None
        try:
            content_branch_id = LedgerEvent.model_validate_json(
                row["content_json"]
            ).branch_id
        except (TypeError, ValueError, ValidationError):
            pass
        if row["branch_id"] == branch_id or content_branch_id == branch_id:
            authority_rows.append(row)
    authority_candidate_ids = {row["record_id"] for row in authority_rows}
    projection_rows = [
        row
        for row in all_projection_rows
        if row["branch_id"] == branch_id or row["event_id"] in authority_candidate_ids
    ]
    projections_by_id = {row["event_id"]: row for row in projection_rows}
    authorities_by_id = {row["record_id"]: row for row in authority_rows}
    candidate_ids = set(projections_by_id) | set(authorities_by_id)
    sequence_by_id: dict[str, int] = {}
    for event_id in candidate_ids:
        projection = projections_by_id.get(event_id)
        sequence = None if projection is None else projection["ledger_seq"]
        if type(sequence) is not int or sequence < 1:
            authority = authorities_by_id.get(event_id)
            try:
                parsed = (
                    None
                    if authority is None
                    else LedgerEvent.model_validate_json(authority["content_json"])
                )
                sequence = None if parsed is None else parsed.ledger_seq
            except (TypeError, ValueError, ValidationError):
                sequence = None
        if type(sequence) is not int or sequence < 1:
            return (), LedgerVerification(
                valid=False,
                checked_events=0,
                first_invalid_seq=1,
                root_hash=None,
            )
        sequence_by_id[event_id] = sequence
    ordered_ids = sorted(candidate_ids, key=lambda event_id: (sequence_by_id[event_id], event_id))
    repository = AuthorityRepository(connection)
    verified: list[_VerifiedEvent] = []
    previous_hash: str | None = None
    expected_seq = 1

    for event_id in ordered_ids:
        row = projections_by_id.get(event_id)
        if sequence_by_id[event_id] != expected_seq or row is None or event_id not in authorities_by_id:
            return tuple(verified), LedgerVerification(
                valid=False,
                checked_events=len(verified),
                first_invalid_seq=expected_seq,
                root_hash=previous_hash,
            )
        try:
            record = repository.get_validated(event_id)
            if not isinstance(record, LedgerEvent):
                raise ValueError("Ledger projection does not reference a LedgerEvent")
            payload = validate_authority_bound_payload(
                _projection_payload(row),
                record.payload_ref,
            )
            projection_matches = (
                row["event_id"] == record.event_id
                and row["branch_id"] == record.branch_id
                and row["ledger_seq"] == record.ledger_seq
                and row["previous_event_hash"] == record.previous_event_hash
                and row["event_hash"] == record.event_hash
                and row["payload_ref"] == record.payload_ref == payload.payload_ref
            )
            chain_matches = (
                record.ledger_seq == expected_seq
                and record.previous_event_hash == previous_hash
                and record.event_hash == record.record_header.content_hash
            )
            if not projection_matches or not chain_matches:
                raise ValueError("Ledger authority, projection, or chain mismatch")
            inline_payload: Mapping[str, object] | None = None
            if payload.mode == "inline":
                if payload.inline_json is None:
                    raise ValueError("inline Ledger payload is missing")
                inline_payload = closed_json_object(
                    _load_closed_json(payload.inline_json)
                )
            if record.event_type in _SESSION_LEDGER_EVENT_TYPES:
                session_id = (
                    None
                    if inline_payload is None
                    else inline_payload.get("session_id")
                )
                if (
                    not isinstance(session_id, str)
                    or not session_id.strip()
                    or record.correlation_id != session_id
                ):
                    raise ValueError("Session Ledger correlation is not authority-bound")
        except (
            ContentHashMismatch,
            CoreContractViolation,
            TypeError,
            UnicodeError,
            ValidationError,
            ValueError,
        ):
            return tuple(verified), LedgerVerification(
                valid=False,
                checked_events=len(verified),
                first_invalid_seq=expected_seq,
                root_hash=previous_hash,
            )
        verified.append(
            _VerifiedEvent(
                event=record,
                payload=payload,
                inline_payload=inline_payload,
            )
        )
        previous_hash = record.event_hash
        expected_seq += 1
    return tuple(verified), LedgerVerification(
        valid=True,
        checked_events=len(verified),
        first_invalid_seq=None,
        root_hash=previous_hash,
    )


def verify_ledger_chain(
    connection: sqlite3.Connection,
    branch_id: str,
) -> LedgerVerification:
    """Verify one branch without taking ownership of the connection."""

    try:
        validated_branch_id = _record_id(branch_id, TYPE_REGISTRY["Branch"].id_prefix)
    except _LedgerViolation:
        return LedgerVerification(
            valid=False,
            checked_events=0,
            first_invalid_seq=1,
            root_hash=None,
        )
    return _verified_events(connection, validated_branch_id)[1]


def get_verified_ledger_head(
    connection: sqlite3.Connection,
    branch_id: str,
) -> LedgerEvent | None:
    """Return the head only when authority, projection, payload, and chain agree."""

    try:
        validated_branch_id = _record_id(
            branch_id,
            TYPE_REGISTRY["Branch"].id_prefix,
        )
    except _LedgerViolation as error:
        raise ReceiptIntegrityError("Ledger chain is invalid at sequence 1") from error
    events, verification = _verified_events(connection, validated_branch_id)
    if not verification.valid:
        raise ReceiptIntegrityError(
            f"Ledger chain is invalid at sequence {verification.first_invalid_seq}"
        )
    return None if not events else events[-1].event


def replay_ledger(
    connection: sqlite3.Connection,
    branch_id: str,
    through_ledger_seq: int | None = None,
) -> LedgerReplayResult:
    """Replay validated events and only locally stored inline payloads."""

    validated_branch_id = _record_id(branch_id, TYPE_REGISTRY["Branch"].id_prefix)
    events, verification = _verified_events(connection, validated_branch_id)
    if not verification.valid:
        raise ReceiptIntegrityError(
            f"Ledger chain is invalid at sequence {verification.first_invalid_seq}"
        )
    if through_ledger_seq is None:
        through = len(events)
    else:
        try:
            through = _NONNEGATIVE_INT.validate_python(through_ledger_seq)
        except ValidationError as error:
            raise ValueError("through_ledger_seq must be a nonnegative integer") from error
        if through > len(events):
            raise ValueError("through_ledger_seq is beyond the verified Ledger head")
    selected = events[:through]
    return LedgerReplayResult(
        branch_id=validated_branch_id,
        through_ledger_seq=through,
        root_hash=None if not selected else selected[-1].event.event_hash,
        events=tuple(item.event for item in selected),
        resolved_inline_payloads=tuple(item.inline_payload for item in selected),
    )


def _session_history(
    connection: sqlite3.Connection,
    branch_id: str,
    existing: tuple[_VerifiedEvent, ...],
    session_id: str,
) -> tuple[_VerifiedEvent, ...]:
    events = list(existing)
    projection_rows = connection.execute(
        """
        SELECT
            event_id,
            branch_id,
            ledger_seq,
            previous_event_hash,
            event_hash,
            payload_ref,
            payload_mode,
            payload_inline_json,
            payload_external_ref,
            payload_hash,
            media_type
        FROM ledger_events
        WHERE payload_mode = 'inline'
          AND json_extract(payload_inline_json, '$.session_id') = ?
          AND branch_id != ?
        ORDER BY ledger_seq, event_id
        """,
        (session_id, branch_id),
    ).fetchall()
    authority_rows = connection.execute(
        """
        SELECT record_id
        FROM authority_records
        WHERE json_extract(content_json, '$.record_header.record_type') = 'LedgerEvent'
          AND json_extract(content_json, '$.event_type') IN (
              'session_started',
              'conversation_message_recorded',
              'session_ended'
          )
          AND json_extract(content_json, '$.correlation_id') = ?
          AND json_extract(content_json, '$.branch_id') != ?
        ORDER BY record_id
        """,
        (session_id, branch_id),
    ).fetchall()
    projections_by_id = {row["event_id"]: row for row in projection_rows}
    candidate_ids = set(projections_by_id) | {
        row["record_id"] for row in authority_rows
    }
    repository = AuthorityRepository(connection)
    for event_id_value in sorted(candidate_ids):
        try:
            event_id = _record_id(
                event_id_value,
                TYPE_REGISTRY["LedgerEvent"].id_prefix,
            )
            record = repository.get_validated(event_id)
            if not isinstance(record, LedgerEvent):
                raise ValueError("session projection has no Ledger authority")
            if (
                record.event_type not in _SESSION_LEDGER_EVENT_TYPES
                or record.correlation_id != session_id
                or record.branch_id == branch_id
            ):
                raise ValueError("session authority candidate does not match lookup")
            row = projections_by_id.get(event_id)
            if row is not None:
                payload = validate_authority_bound_payload(
                    _projection_payload(row),
                    record.payload_ref,
                )
                if payload.mode != "inline" or payload.inline_json is None:
                    raise ValueError("session candidate payload is not inline")
                inline_payload = closed_json_object(
                    _load_closed_json(payload.inline_json)
                )
                projection_matches = (
                    row["event_id"] == record.event_id
                    and row["branch_id"] == record.branch_id
                    and row["ledger_seq"] == record.ledger_seq
                    and row["previous_event_hash"] == record.previous_event_hash
                    and row["event_hash"] == record.event_hash
                    and row["payload_ref"] == record.payload_ref == payload.payload_ref
                    and inline_payload.get("session_id") == session_id
                )
                if not projection_matches:
                    raise ValueError("session authority and projection do not match")
        except (
            ContentHashMismatch,
            CoreContractViolation,
            _LedgerViolation,
            TypeError,
            UnicodeError,
            ValidationError,
            ValueError,
        ) as error:
            raise _LedgerViolation(CoreErrorCode.HASH_SCOPE_MISMATCH) from error
        if row is None:
            raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        events.append(
            _VerifiedEvent(
                event=record,
                payload=payload,
                inline_payload=inline_payload,
            )
        )
    return tuple(
        item
        for item in events
        if item.inline_payload is not None
        and item.inline_payload.get("session_id") == session_id
    )


def _session_state(history: tuple[_VerifiedEvent, ...]) -> tuple[str, ...]:
    state: list[str] = []
    for item in history:
        if item.event.event_type == "conversation_message_recorded":
            role = None if item.inline_payload is None else item.inline_payload.get("role")
            if role not in ("user", "amadeus"):
                raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
            state.append(role)
        else:
            state.append(item.event.event_type)
    return tuple(state)


def _validate_session_transition(
    connection: sqlite3.Connection,
    command: MutationCommandEnvelope,
    payload: Mapping[str, object],
    existing: tuple[_VerifiedEvent, ...],
    identity_id: str,
    lineage_id: str,
    branch_id: str,
    instance_id: str,
    vault_id: str,
) -> Mapping[str, object]:
    event_payload = cast(Mapping[str, object], payload["event_payload"])
    session_id = event_payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    if (
        event_payload.get("identity_id") != identity_id
        or event_payload.get("vault_id") != vault_id
    ):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    history = _session_history(connection, branch_id, existing, session_id)
    binding = (identity_id, lineage_id, branch_id, instance_id, vault_id)
    for item in history:
        item_payload = item.inline_payload
        if item_payload is None or (
            item.event.identity_id,
            item.event.lineage_id,
            item.event.branch_id,
            item.event.instance_id,
            item.event.vault_id,
        ) != binding or (
            item_payload.get("identity_id"),
            item_payload.get("vault_id"),
        ) != (identity_id, vault_id):
            raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    event_type = cast(str, payload["event_type"])
    role: object = None
    if event_type == "conversation_message_recorded":
        role = event_payload.get("role")
        text_ref = event_payload.get("text_ref")
        if (
            role not in ("user", "amadeus")
            or role != command.actor.actor_type
            or not isinstance(text_ref, str)
            or not text_ref.strip()
        ):
            raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    expected = _EXPECTED_SESSION_TRANSITION.get(_session_state(history))
    if expected != (event_type, role):
        raise _LedgerViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
    return event_payload


def append_session_event(
    connection: sqlite3.Connection,
    command: MutationCommandEnvelope,
) -> CommandResult[LedgerAppendResult]:
    """Append one command-bound session event through the connection-bound UoW."""

    def handler(
        repository: AuthorityRepository,
        mutation_command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> CommandResult[object]:
        (
            payload,
            event_id,
            identity_id,
            lineage_id,
            branch_id,
            instance_id,
            vault_id,
            ledger_seq,
            expected_previous_hash,
        ) = _validated_request(mutation_command)
        identity, _lineage, _branch = _authority_binding(
            repository,
            identity_id,
            lineage_id,
            branch_id,
        )
        existing, verification = _verified_events(connection, branch_id)
        if not verification.valid:
            raise _LedgerViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)
        if (
            ledger_seq != len(existing) + 1
            or verification.root_hash is None
            or not hmac.compare_digest(
                expected_previous_hash,
                verification.root_hash,
            )
        ):
            raise _LedgerViolation(CoreErrorCode.STALE_VERSION)
        event_payload = _validate_session_transition(
            connection,
            mutation_command,
            payload,
            existing,
            identity_id,
            lineage_id,
            branch_id,
            instance_id,
            vault_id,
        )
        stored_payload = prepare_inline_payload(event_payload)
        event = cast(
            LedgerEvent,
            _seal_record(
                LedgerEvent,
                {
                    "record_header": _record_header(
                        "LedgerEvent",
                        event_id,
                        identity_id=identity_id,
                        lineage_id=lineage_id,
                        branch_id=branch_id,
                        created_at=mutation_command.issued_at,
                        created_by_event_id=event_id,
                        deployment_policy_ref=identity.record_header.deployment_policy_ref,
                    ),
                    "event_id": event_id,
                    "ledger_seq": ledger_seq,
                    "identity_id": identity_id,
                    "lineage_id": lineage_id,
                    "branch_id": branch_id,
                    "instance_id": instance_id,
                    "vault_id": vault_id,
                    "event_type": payload["event_type"],
                    "occurred_at": mutation_command.issued_at,
                    "ingested_at": mutation_command.issued_at,
                    "actor_type": mutation_command.actor.actor_type,
                    "actor_id": mutation_command.actor.actor_id,
                    "mutation_command_id": execution_context.command_id,
                    "mutation_command_hash": execution_context.command_hash,
                    "payload_ref": stored_payload.payload_ref,
                    "causation_id": payload.get("causation_id"),
                    "correlation_id": event_payload["session_id"],
                    "previous_event_hash": expected_previous_hash,
                    "event_hash": _ZERO_HASH,
                    "version": 1,
                },
            ),
        )
        repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=stored_payload,
        )
        return CommandResult[object](
            value=LedgerAppendResult(
                event_id=event.event_id,
                ledger_seq=event.ledger_seq,
                event_hash=event.event_hash,
            ),
            event_ids=(event.event_id,),
            error=None,
            replayed=False,
        )

    try:
        result = execute_command_on_connection(connection, command, handler)
    except _LedgerViolation as error:
        return _failure_result(command, error.code)
    except CoreContractViolation as error:
        return _failure_result(command, error.code)
    except ContentHashMismatch:
        return _failure_result(command, CoreErrorCode.HASH_SCOPE_MISMATCH)
    except (ValidationError, sqlite3.IntegrityError):
        return _failure_result(command, CoreErrorCode.HEADER_BODY_MISMATCH)
    return _typed_result(result)


def deny_user_hard_delete(
    command: MutationCommandEnvelope,
) -> CommandResult[None]:
    """Purely deny a user's request to physically delete one Ledger event."""

    snapshot = MutationCommandEnvelope.model_validate(command.model_dump(mode="python"))
    payload = snapshot.payload
    if (
        snapshot.actor.actor_type != "user"
        or snapshot.command_type != "event.hard_delete"
        or frozenset(payload) != {"delete_mode", "event_id"}
        or payload.get("delete_mode") != "hard"
    ):
        raise ValueError("not a valid user Ledger hard-delete request")
    event_id = _record_id(payload.get("event_id"), TYPE_REGISTRY["LedgerEvent"].id_prefix)
    if snapshot.target_record_refs != (event_id,):
        raise ValueError("hard-delete target does not match its event payload")
    return CommandResult[None](
        value=None,
        event_ids=(),
        error=CoreError(
            error_id=new_id("error"),
            code=CoreErrorCode.USER_HARD_DELETE_FORBIDDEN,
            message=CoreErrorCode.USER_HARD_DELETE_FORBIDDEN.value,
            correlation_id=snapshot.audit_context_id,
            audit_event_id=None,
            retryable=False,
            details_ref=None,
        ),
        replayed=False,
    )


__all__ = [
    "LedgerAppendResult",
    "LedgerReplayResult",
    "LedgerVerification",
    "append_session_event",
    "deny_user_hard_delete",
    "get_verified_ledger_head",
    "replay_ledger",
    "verify_ledger_chain",
]
