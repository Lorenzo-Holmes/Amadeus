"""Serialized mutation-command execution and scoped idempotency receipts."""

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Callable, Mapping
from typing import TypeAlias

from amadeus_core.clock import Clock, SystemClock
from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
    prepare_mutation_command,
)
from amadeus_core.contracts.errors import CoreError, CoreErrorCode, RETRYABLE_ERROR_CODES
from amadeus_core.contracts.hashing import sha256_hex
from amadeus_core.ids import new_id

from .database import SQLiteDatabase, serialized_transaction
from .payloads import _load_closed_json, canonical_closed_json, canonical_receipt_result
from .repository import AuthorityRepository


MutationHandler: TypeAlias = Callable[
    [AuthorityRepository, MutationCommandEnvelope, CommandExecutionContext],
    CommandResult[object],
]


class ReceiptIntegrityError(ValueError):
    """A persisted command receipt no longer matches its integrity hash."""


class ResultEventMismatchError(ValueError):
    """A handler result does not name the Ledger events appended by its command."""


class _AbortCommand(Exception):
    def __init__(self, result: CommandResult[object]) -> None:
        self.result = result
        super().__init__(str(result))


def _core_error(
    code: CoreErrorCode,
    command: MutationCommandEnvelope,
) -> CoreError:
    return CoreError(
        error_id=new_id("error"),
        code=code,
        message=code.value,
        correlation_id=command.audit_context_id,
        audit_event_id=None,
        retryable=code in RETRYABLE_ERROR_CODES,
        details_ref=None,
    )


def _failure_result(
    code: CoreErrorCode,
    command: MutationCommandEnvelope,
) -> CommandResult[object]:
    return CommandResult[object](
        value=None,
        event_ids=(),
        error=_core_error(code, command),
        replayed=False,
    )


def _load_receipt(
    connection: sqlite3.Connection,
    actor_capability_id: str,
    scope_hash: str,
    key: str,
):
    return connection.execute(
        """
        SELECT command_hash, result_json, result_hash, semantic_event_ids_json
        FROM command_receipts
        WHERE actor_capability_id = ?
          AND idempotency_scope_hash = ?
          AND idempotency_key = ?
        """,
        (actor_capability_id, scope_hash, key),
    ).fetchone()


def _receipt_command_hash_matches(
    stored_command_hash: object,
    command_hash: str,
) -> bool:
    try:
        if (
            not isinstance(stored_command_hash, str)
            or len(stored_command_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in stored_command_hash
            )
        ):
            raise ValueError("receipt command hash is not canonical SHA-256 text")
        return hmac.compare_digest(stored_command_hash, command_hash)
    except (TypeError, ValueError, UnicodeError) as error:
        raise ReceiptIntegrityError("invalid receipt command hash") from error


def _decode_result(
    result_json: object,
    result_hash: object,
    semantic_event_ids_json: object,
) -> CommandResult[object]:
    try:
        if not isinstance(result_json, str) or not isinstance(result_hash, str):
            raise TypeError("receipt result and hash must be stored as text")
        actual_hash = sha256_hex(result_json.encode("utf-8"))
        hash_matches = hmac.compare_digest(result_hash, actual_hash)
    except (TypeError, ValueError, UnicodeError) as error:
        raise ReceiptIntegrityError("invalid receipt result") from error
    if not hash_matches:
        raise ReceiptIntegrityError("receipt result hash mismatch")
    try:
        decoded_result = _load_closed_json(result_json)
        canonical_result_json = canonical_receipt_result(decoded_result).decode("utf-8")
        if canonical_result_json != result_json:
            raise ValueError("receipt result is not canonical")
        stored = CommandResult[object].model_validate_json(result_json)
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ReceiptIntegrityError("invalid receipt result") from error
    try:
        if not isinstance(semantic_event_ids_json, str):
            raise ValueError("semantic event ids must be stored as JSON text")
        decoded_event_ids = _load_closed_json(semantic_event_ids_json)
        if not isinstance(decoded_event_ids, list) or any(
            not isinstance(event_id, str) for event_id in decoded_event_ids
        ):
            raise ValueError("semantic event ids must be a JSON string array")
        canonical_event_ids_json = canonical_closed_json(decoded_event_ids).decode(
            "utf-8"
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise ReceiptIntegrityError("invalid receipt semantic event ids") from error
    if canonical_event_ids_json != semantic_event_ids_json:
        raise ReceiptIntegrityError("receipt semantic event ids are not canonical")
    if tuple(decoded_event_ids) != stored.event_ids:
        raise ReceiptIntegrityError("receipt semantic event ids mismatch")
    return stored.model_copy(update={"replayed": True})


class SQLiteUnitOfWork:
    __slots__ = ("_database", "_clock")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SQLiteUnitOfWork is final")

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock | None = None,
    ) -> None:
        object.__setattr__(self, "_database", database)
        object.__setattr__(
            self,
            "_clock",
            SystemClock() if clock is None else clock,
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("SQLiteUnitOfWork configuration is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("SQLiteUnitOfWork configuration is immutable")

    def execute_command(
        self,
        command: MutationCommandEnvelope | Mapping[str, object],
        handler: MutationHandler,
    ) -> CommandResult[object]:
        connection = self._database.connect()
        try:
            return execute_command_on_connection(
                connection,
                command,
                handler,
                clock=self._clock,
            )
        finally:
            connection.close()

    execute = execute_command


UnitOfWork = SQLiteUnitOfWork


def execute_command_on_connection(
    connection: sqlite3.Connection,
    command: MutationCommandEnvelope | Mapping[str, object],
    handler: MutationHandler,
    *,
    clock: Clock | None = None,
) -> CommandResult[object]:
    """Execute one command without taking ownership of the caller's connection."""

    raw_command = (
        command.model_dump(mode="python")
        if isinstance(command, MutationCommandEnvelope)
        else command
    )
    validated_command = MutationCommandEnvelope.model_validate(raw_command)
    prepared = prepare_mutation_command(validated_command)
    mutation_command = prepared.mutation_command
    address = prepared.idempotency_address
    command_hash = prepared.execution_context.command_hash
    receipt_clock = SystemClock() if clock is None else clock

    try:
        with serialized_transaction(connection):
            receipt = _load_receipt(
                connection,
                address.actor_capability_id,
                address.scope_hash,
                address.key,
            )
            if receipt is not None:
                if _receipt_command_hash_matches(
                    receipt["command_hash"],
                    command_hash,
                ):
                    return _decode_result(
                        receipt["result_json"],
                        receipt["result_hash"],
                        receipt["semantic_event_ids_json"],
                    )
                raise _AbortCommand(
                    _failure_result(
                        CoreErrorCode.IDEMPOTENCY_CONFLICT,
                        mutation_command,
                    )
                )

            repository = AuthorityRepository(
                connection,
                allowed_target_refs=mutation_command.target_record_refs,
                actor_capability_id=address.actor_capability_id,
                execution_context=prepared.execution_context,
            )
            current_versions = repository.get_current_versions(
                mutation_command.target_record_refs
            )
            expected_versions = {
                expected.target_record_ref: (
                    0
                    if expected.expected_version == "absent"
                    else expected.expected_version
                )
                for expected in mutation_command.expected_versions
            }
            if any(
                current_versions[target] != expected_versions[target]
                for target in mutation_command.target_record_refs
            ):
                raise _AbortCommand(
                    _failure_result(CoreErrorCode.STALE_VERSION, mutation_command)
                )

            outcome = handler(
                repository,
                mutation_command,
                prepared.execution_context,
            )
            if not isinstance(outcome, CommandResult):
                raise TypeError("mutation handler must return CommandResult")
            first_result = CommandResult[object].model_validate(
                outcome.model_dump(mode="python")
            ).model_copy(update={"replayed": False})
            if first_result.event_ids != repository.event_ids:
                raise ResultEventMismatchError(
                    "result event ids do not match appended Ledger events"
                )
            result_json_bytes = canonical_receipt_result(
                first_result.model_dump(mode="python")
            )
            stored_result = CommandResult[object].model_validate_json(
                result_json_bytes
            )
            result_hash = sha256_hex(result_json_bytes)
            semantic_event_ids_json = canonical_closed_json(
                list(stored_result.event_ids)
            ).decode("utf-8")
            connection.execute(
                """
                INSERT INTO command_receipts (
                    actor_capability_id,
                    idempotency_scope_hash,
                    idempotency_key,
                    command_id,
                    command_hash,
                    result_json,
                    result_hash,
                    semantic_event_ids_json,
                    committed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    address.actor_capability_id,
                    address.scope_hash,
                    address.key,
                    prepared.execution_context.command_id,
                    command_hash,
                    result_json_bytes.decode("utf-8"),
                    result_hash,
                    semantic_event_ids_json,
                    receipt_clock.now().isoformat().replace("+00:00", "Z"),
                ),
            )
            return stored_result
    except _AbortCommand as aborted:
        return aborted.result


__all__ = [
    "MutationHandler",
    "ReceiptIntegrityError",
    "ResultEventMismatchError",
    "SQLiteUnitOfWork",
    "UnitOfWork",
    "execute_command_on_connection",
]
