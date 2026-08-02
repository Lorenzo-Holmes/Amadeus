from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Lock
from time import sleep

import pytest

from amadeus_core.contracts.commands import CommandResult
from amadeus_core.contracts.errors import CoreError, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex


def _database(path: Path):
    from amadeus_core.storage.database import SQLiteDatabase

    return SQLiteDatabase(path)


def _receipt_count(database) -> int:
    connection = database.connect()
    try:
        return connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0]
    finally:
        connection.close()


def _fault_inject_receipt_update(
    database,
    statement: str,
    parameters: tuple[object, ...],
) -> None:
    connection = database.connect()
    try:
        connection.execute("DROP TRIGGER IF EXISTS command_receipts_reject_update")
        connection.execute(statement, parameters)
    finally:
        connection.close()


def _string_result_at_canonical_size(total_bytes: int) -> str:
    from amadeus_core.storage.payloads import canonical_closed_json

    empty_result = CommandResult[object](value="", event_ids=(), error=None)
    empty_size = len(
        canonical_closed_json(empty_result.model_dump(mode="python"))
    )
    assert total_bytes >= empty_size
    return "x" * (total_bytes - empty_size)


def test_same_address_and_hash_replays_first_value_event_ids_and_error(
    database_path: Path,
    command_factory: Callable[..., object],
    ledger_event_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database)
    command = command_factory(("evt-b",), ("absent",))
    calls = 0
    payload = {"semantic": "persisted"}
    payload_hash = sha256_hex(canonical_json(payload))
    frozen_error = CoreError(
        error_id="err-a",
        code=CoreErrorCode.STALE_VERSION,
        message="stored failure",
        correlation_id="correlation-a",
        audit_event_id="evt-a",
        retryable=True,
        details_ref="details:a",
    )

    def handler(repository, mutation_command, execution_context):
        del mutation_command
        nonlocal calls
        calls += 1
        event = ledger_event_factory(
            "evt-b",
            f"inline:{payload_hash}",
            command_id=execution_context.command_id,
            command_hash=execution_context.command_hash,
            correlation_id=execution_context.audit_context_id,
        )
        repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=payload,
        )
        return CommandResult[object](
            value=None,
            event_ids=repository.event_ids,
            error=frozen_error,
        )

    first = SQLiteUnitOfWork(database).execute_command(command, handler)
    replay = SQLiteUnitOfWork(database).execute_command(command, handler)

    assert calls == 1
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.value == first.value
    assert replay.event_ids == first.event_ids == ("evt-b",)
    assert replay.error == first.error == frozen_error
    assert _receipt_count(database) == 1


def test_first_result_and_replay_share_one_closed_json_value_representation(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="closed-json-result",
    )

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        return CommandResult[object](
            value={"score": Decimal("0.1")},
            event_ids=(),
            error=None,
        )

    first = SQLiteUnitOfWork(database).execute_command(command, handler)
    replay = SQLiteUnitOfWork(database).execute_command(command, handler)

    assert isinstance(first.value, Mapping)
    assert isinstance(replay.value, Mapping)
    assert first.value["score"] == replay.value["score"]
    assert type(first.value["score"]) is type(replay.value["score"])


def test_replay_wraps_non_text_command_hash_as_receipt_integrity_error(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import (
        ReceiptIntegrityError,
        SQLiteUnitOfWork,
    )

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="non-text-command-hash",
    )
    handler_calls = 0

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal handler_calls
        handler_calls += 1
        return CommandResult[object](value="original", event_ids=(), error=None)

    unit_of_work = SQLiteUnitOfWork(database)
    unit_of_work.execute_command(command, handler)
    _fault_inject_receipt_update(
        database,
        "UPDATE command_receipts SET command_hash = zeroblob(64)",
        (),
    )

    with pytest.raises(ReceiptIntegrityError, match="invalid receipt command hash"):
        unit_of_work.execute_command(command, handler)
    assert handler_calls == 1


def test_replay_rejects_result_json_that_no_longer_matches_receipt_hash(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="tampered-receipt",
    )
    unit_of_work = SQLiteUnitOfWork(database)
    unit_of_work.execute_command(
        command,
        lambda repository, mutation_command, execution_context: CommandResult[object](
            value="original",
            event_ids=(),
            error=None,
        ),
    )
    tampered = canonical_json(
        {
            "value": "tampered",
            "event_ids": [],
            "error": None,
            "replayed": False,
        }
    ).decode("utf-8")
    _fault_inject_receipt_update(
        database,
        "UPDATE command_receipts SET result_json = ?",
        (tampered,),
    )

    with pytest.raises(ValueError, match="receipt result hash mismatch"):
        unit_of_work.execute_command(
            command,
            lambda *args: pytest.fail("tampered receipt reran handler"),
        )


def test_replay_wraps_hash_matching_structurally_invalid_result(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import (
        ReceiptIntegrityError,
        SQLiteUnitOfWork,
    )

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="invalid-result-structure",
    )
    handler_calls = 0

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal handler_calls
        handler_calls += 1
        return CommandResult[object](value="original", event_ids=(), error=None)

    unit_of_work = SQLiteUnitOfWork(database)
    unit_of_work.execute_command(command, handler)
    invalid_result = canonical_json({"value": "missing-required-fields"})
    _fault_inject_receipt_update(
        database,
        "UPDATE command_receipts SET result_json = ?, result_hash = ?",
        (invalid_result.decode("utf-8"), sha256_hex(invalid_result)),
    )

    with pytest.raises(ReceiptIntegrityError, match="invalid receipt result"):
        unit_of_work.execute_command(command, handler)
    assert handler_calls == 1


def test_replay_rejects_semantic_event_ids_that_disagree_with_result(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import (
        ReceiptIntegrityError,
        SQLiteUnitOfWork,
    )

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="tampered-semantic-events",
    )
    handler_calls = 0

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal handler_calls
        handler_calls += 1
        return CommandResult[object](
            value="original",
            event_ids=(),
            error=None,
        )

    unit_of_work = SQLiteUnitOfWork(database)
    unit_of_work.execute_command(command, handler)
    _fault_inject_receipt_update(
        database,
        "UPDATE command_receipts SET semantic_event_ids_json = ?",
        (canonical_json(["evt-tampered"]).decode("utf-8"),),
    )

    with pytest.raises(ReceiptIntegrityError):
        unit_of_work.execute_command(command, handler)
    assert handler_calls == 1


def test_same_address_different_hash_is_conflict_with_zero_handler_or_new_writes(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    first_command = command_factory(
        ("snp-a",),
        ("absent",),
        command_type="snapshot.create",
    )
    conflicting_command = command_factory(
        ("snp-a",),
        ("absent",),
        command_type="snapshot.replace",
    )
    first_calls = 0
    conflict_calls = 0

    def first_handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal first_calls
        first_calls += 1
        return CommandResult[object](value="first", event_ids=(), error=None)

    def conflict_handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal conflict_calls
        conflict_calls += 1
        return CommandResult[object](value="wrong", event_ids=(), error=None)

    first = SQLiteUnitOfWork(database).execute_command(first_command, first_handler)
    conflict = SQLiteUnitOfWork(database).execute_command(
        conflicting_command,
        conflict_handler,
    )

    assert first.error is None
    assert first_calls == 1
    assert conflict_calls == 0
    assert conflict.error is not None
    assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
    assert conflict.event_ids == ()
    assert conflict.replayed is False
    connection = database.connect()
    try:
        assert connection.execute("SELECT count(*) FROM authority_records").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0] == 1
    finally:
        connection.close()


def test_two_connections_competing_for_one_address_run_semantic_handler_once(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    command = command_factory(("snp-a",), ("absent",), idempotency_key="race")
    start = Barrier(2)
    counter_lock = Lock()
    calls = 0

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal calls
        with counter_lock:
            calls += 1
            call_number = calls
        sleep(0.05)
        return CommandResult[object](
            value={"semantic_call": call_number},
            event_ids=(),
            error=None,
        )

    def compete():
        start.wait()
        return SQLiteUnitOfWork(database).execute_command(command, handler)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(compete) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    assert calls == 1
    assert sorted(result.replayed for result in results) == [False, True]
    assert all(isinstance(result.value, Mapping) for result in results)
    assert {result.value["semantic_call"] for result in results} == {1}
    assert _receipt_count(database) == 1


def test_large_original_command_payload_is_not_copied_into_receipt(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    marker = "original-large-payload-marker"
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="large-payload",
        payload={
            "scope_refs": ["scope:a"],
            "blob": marker * 10_000,
        },
    )

    result = SQLiteUnitOfWork(database).execute_command(
        command,
        lambda repository, mutation_command, execution_context: CommandResult[object](
            value={"payload_ref": "reference:object-store:item-a"},
            event_ids=(),
            error=None,
        ),
    )

    assert result.error is None
    connection = database.connect()
    try:
        receipt_json = connection.execute(
            "SELECT result_json FROM command_receipts"
        ).fetchone()[0]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(command_receipts)")
        }
    finally:
        connection.close()
    assert marker not in receipt_json
    assert "payload" not in columns
    assert "command_json" not in columns


def test_receipt_result_at_exact_canonical_byte_limit_is_persisted(
    database_path: Path,
    command_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.payloads import MAX_RECEIPT_RESULT_BYTES
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="receipt-limit-exact",
    )
    value = _string_result_at_canonical_size(MAX_RECEIPT_RESULT_BYTES)

    result = SQLiteUnitOfWork(database).execute_command(
        command,
        lambda repository, mutation_command, execution_context: CommandResult[object](
            value=value,
            event_ids=(),
            error=None,
        ),
    )

    assert result.value == value
    connection = database.connect()
    try:
        stored_bytes = connection.execute(
            "SELECT length(CAST(result_json AS BLOB)) FROM command_receipts"
        ).fetchone()[0]
    finally:
        connection.close()
    assert stored_bytes == MAX_RECEIPT_RESULT_BYTES


def test_receipt_result_one_byte_over_limit_rolls_back_authority_and_receipt(
    database_path: Path,
    command_factory: Callable[..., object],
    snapshot_factory: Callable[..., object],
) -> None:
    from amadeus_core.storage.payloads import (
        MAX_RECEIPT_RESULT_BYTES,
        ReceiptResultTooLarge,
    )
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="receipt-limit-over",
    )
    value = _string_result_at_canonical_size(MAX_RECEIPT_RESULT_BYTES + 1)

    def handler(repository, mutation_command, execution_context):
        del mutation_command, execution_context
        snapshot = snapshot_factory("snp-a")
        repository.save_authoritative(
            "source_snapshot",
            snapshot.model_dump(mode="python"),
        )
        return CommandResult[object](value=value, event_ids=(), error=None)

    with pytest.raises(ReceiptResultTooLarge):
        SQLiteUnitOfWork(database).execute_command(command, handler)

    connection = database.connect()
    try:
        assert connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_id = 'snp-a'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM command_receipts"
        ).fetchone()[0] == 0
    finally:
        connection.close()
