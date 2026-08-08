from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from amadeus_core.contracts.commands import CommandResult
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex

from tests.storage.conftest import (
    CAPABILITY_ID,
    make_break_glass_grant,
    make_capability,
    make_emergency_case,
    make_termination_execution_grant,
    make_termination_confirmation,
    make_vault_read_capability,
)


TARGETS = ("snp-a", "snp-b", "snp-c")


def _database(path: Path):
    from amadeus_core.storage.database import SQLiteDatabase

    return SQLiteDatabase(path)


def _state(database) -> tuple[str, int, int, int]:
    connection = database.connect()
    try:
        rows = connection.execute(
            """
            SELECT record_id, content_hash, version
            FROM authority_records
            ORDER BY record_id
            """
        ).fetchall()
        state_hash = sha256_hex(canonical_json([tuple(row) for row in rows]))
        ledger_count = connection.execute(
            "SELECT count(*) FROM ledger_events"
        ).fetchone()[0]
        remaining_uses = connection.execute(
            "SELECT remaining_uses FROM capabilities WHERE capability_id = ?",
            (CAPABILITY_ID,),
        ).fetchone()[0]
        receipt_count = connection.execute(
            "SELECT count(*) FROM command_receipts"
        ).fetchone()[0]
        return state_hash, ledger_count, remaining_uses, receipt_count
    finally:
        connection.close()


def test_commit_failure_from_deferred_foreign_key_explicitly_rolls_back(
    database_path: Path,
) -> None:
    from amadeus_core.storage.database import serialized_transaction

    connection = _database(database_path).connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with serialized_transaction(connection):
                connection.execute(
                    """
                    INSERT INTO authority_records (
                        record_id,
                        record_type,
                        schema_version,
                        identity_id,
                        lineage_id,
                        branch_id,
                        version,
                        content_json,
                        content_hash,
                        created_at
                    ) VALUES (
                        'idn-a', 'Identity', '0.1', 'idn-a', 'lin-missing',
                        'brn-missing', 1, '{}', ?, '2026-08-01T00:00:00Z'
                    )
                    """,
                    ("0" * 64,),
                )
                connection.execute(
                    """
                    INSERT INTO identities (
                        identity_id, lifecycle_state, active_branch_id, version
                    ) VALUES ('idn-a', 'active', 'brn-missing', 1)
                    """
                )

        assert connection.in_transaction is False
        assert connection.execute(
            "SELECT count(*) FROM authority_records"
        ).fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.parametrize("stale_index", [0, 1, 2])
def test_stale_at_each_target_position_has_zero_side_effects(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
    stale_index: int,
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    snapshots = tuple(snapshot_factory(target) for target in TARGETS)
    standard_seed(database, snapshots)
    expected = [1, 1, 1]
    expected[stale_index] = 2
    command = command_factory(TARGETS, tuple(expected))
    before = _state(database)
    handler_calls = 0

    def handler(repository, mutation_command, execution_context):
        del repository, mutation_command, execution_context
        nonlocal handler_calls
        handler_calls += 1
        return CommandResult[object](value="must-not-run", event_ids=(), error=None)

    result = SQLiteUnitOfWork(database).execute_command(command, handler)

    assert result.error is not None
    assert result.error.code is CoreErrorCode.STALE_VERSION
    assert result.replayed is False
    assert handler_calls == 0
    assert _state(database) == before


def test_handler_exception_rolls_back_authority_ledger_capability_and_receipt(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    ledger_event_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.database import SQLiteDatabase
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = SQLiteDatabase(database_path)
    snapshots = tuple(snapshot_factory(target) for target in TARGETS)
    standard_seed(database, snapshots)
    payload = {"attempt": "rolled-back"}
    payload_hash = sha256_hex(canonical_json(payload))
    command = command_factory(
        (*TARGETS, CAPABILITY_ID, "evt-b"),
        (1, 1, 1, 1, "absent"),
    )
    before = _state(database)

    def handler(repository, mutation_command, execution_context):
        del mutation_command
        for target in TARGETS:
            updated = snapshot_factory(target, version=2, marker="attempt")
            repository.save_authoritative(
                "source_snapshot",
                updated.model_dump(mode="python"),
            )
        repository.consume_capability(CAPABILITY_ID)
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
        raise RuntimeError("handler failed after writes")

    with pytest.raises(RuntimeError, match="handler failed after writes"):
        SQLiteUnitOfWork(database).execute_command(command, handler)

    assert _state(database) == before


def test_capability_consumption_outside_command_target_set_rolls_back_everything(
    database_path: Path,
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database)
    command = command_factory(
        ("snp-a",),
        ("absent",),
        idempotency_key="capability-target-set-bypass",
    )
    before = _state(database)

    def handler(repository, mutation_command, execution_context):
        del mutation_command, execution_context
        repository.consume_capability(CAPABILITY_ID)
        return CommandResult[object](value="must-not-commit", event_ids=(), error=None)

    with pytest.raises(CoreContractViolation) as captured:
        SQLiteUnitOfWork(database).execute_command(command, handler)

    assert captured.value.code is CoreErrorCode.VERSION_TARGET_SET_MISMATCH
    assert _state(database) == before


def test_reported_event_without_ledger_append_rolls_back_authority_and_receipt(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database, (snapshot_factory("snp-a"),))
    command = command_factory(
        ("snp-a",),
        (1,),
        idempotency_key="fake-result-event",
    )
    before = _state(database)

    def handler(repository, mutation_command, execution_context):
        del mutation_command, execution_context
        updated = snapshot_factory("snp-a", version=2, marker="must-roll-back")
        repository.save_authoritative(
            "source_snapshot",
            updated.model_dump(mode="python"),
        )
        return CommandResult[object](
            value="must-not-commit",
            event_ids=("evt-fake",),
            error=None,
        )

    with pytest.raises(ValueError, match="result event ids do not match appended Ledger events"):
        SQLiteUnitOfWork(database).execute_command(command, handler)

    assert _state(database) == before


def test_target_set_mismatch_fails_before_begin_and_handler(
    database_path: Path,
    command_factory: Callable[..., object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.storage import unit_of_work

    database = _database(database_path)
    command = command_factory(("snp-a",), ("absent",)).model_copy(
        update={"target_record_refs": ("snp-b",)}
    )
    monkeypatch.setattr(
        unit_of_work,
        "serialized_transaction",
        lambda connection: pytest.fail("transaction began before target validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        unit_of_work.SQLiteUnitOfWork(database).execute_command(
            command,
            lambda *args: pytest.fail("handler ran"),
        )

    assert captured.value.code is CoreErrorCode.VERSION_TARGET_SET_MISMATCH


def test_unvalidated_closed_schema_command_fails_before_begin_and_handler(
    database_path: Path,
    command_factory: Callable[..., object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.storage import unit_of_work

    database = _database(database_path)
    raw = command_factory(("snp-a",), ("absent",)).model_dump(mode="python")
    raw["unexpected"] = "outside-closed-schema"
    monkeypatch.setattr(
        unit_of_work,
        "serialized_transaction",
        lambda connection: pytest.fail("transaction began before command validation"),
    )

    with pytest.raises(ValidationError):
        unit_of_work.SQLiteUnitOfWork(database).execute_command(
            raw,
            lambda *args: pytest.fail("handler ran"),
        )


def test_prepare_is_called_once_and_handler_receives_exact_prepared_snapshot(
    database_path: Path,
    command_factory: Callable[..., object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import commands
    from amadeus_core.storage import unit_of_work

    database = _database(database_path)
    command = command_factory(("snp-a",), ("absent",))
    prepared_calls = []
    real_prepare = commands.prepare_mutation_command

    def tracking_prepare(validated_command):
        prepared = real_prepare(validated_command)
        prepared_calls.append(prepared)
        return prepared

    monkeypatch.setattr(unit_of_work, "prepare_mutation_command", tracking_prepare)

    def handler(repository, mutation_command, execution_context):
        del repository
        assert mutation_command is prepared_calls[0].mutation_command
        assert execution_context is prepared_calls[0].execution_context
        return CommandResult[object](
            value={"snapshot": "exact"},
            event_ids=(),
            error=None,
        )

    result = unit_of_work.SQLiteUnitOfWork(database).execute_command(command, handler)

    assert len(prepared_calls) == 1
    assert result.value == {"snapshot": "exact"}


def test_all_current_versions_are_loaded_by_one_repository_call(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.storage import repository as repository_module
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database, tuple(snapshot_factory(target) for target in TARGETS))
    command = command_factory(TARGETS, (1, 1, 1), idempotency_key="one-read")
    calls = []
    real = repository_module.AuthorityRepository.get_current_versions

    def tracking_read(self, target_record_refs):
        calls.append(tuple(target_record_refs))
        return real(self, target_record_refs)

    monkeypatch.setattr(
        repository_module.AuthorityRepository,
        "get_current_versions",
        tracking_read,
    )

    SQLiteUnitOfWork(database).execute_command(
        command,
        lambda repository, mutation_command, execution_context: CommandResult[object](
            value="ok",
            event_ids=(),
            error=None,
        ),
    )

    assert calls == [TARGETS]


def test_batch_version_snapshot_is_not_requeried_per_target_during_writes(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database, tuple(snapshot_factory(target) for target in TARGETS))
    statements: list[str] = []

    class TracingDatabase:
        def connect(self):
            connection = database.connect()
            connection.set_trace_callback(statements.append)
            return connection

    def handler(repository, mutation_command, execution_context):
        del mutation_command, execution_context
        for target in TARGETS:
            updated = snapshot_factory(target, version=2, marker="committed")
            repository.save_authoritative(
                "source_snapshot",
                updated.model_dump(mode="python"),
            )
        return CommandResult[object](value="ok", event_ids=(), error=None)

    command = command_factory(TARGETS, (1, 1, 1), idempotency_key="batch-read")
    result = SQLiteUnitOfWork(TracingDatabase()).execute_command(command, handler)

    assert result.error is None
    version_reads = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
        and "FROM AUTHORITY_RECORDS" in " ".join(statement.upper().split())
        and "VERSION" in statement.upper()
    ]
    assert len(version_reads) == 1
    assert " IN " in " ".join(version_reads[0].upper().split())


def test_same_target_cannot_be_written_twice_by_one_command(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database, (snapshot_factory("snp-a"),))
    command = command_factory(
        ("snp-a",),
        (1,),
        idempotency_key="same-target-twice",
    )

    def handler(repository, mutation_command, execution_context):
        del mutation_command, execution_context
        for version in (2, 3):
            updated = snapshot_factory(
                "snp-a",
                version=version,
                marker=f"attempt-{version}",
            )
            repository.save_authoritative(
                "source_snapshot",
                updated.model_dump(mode="python"),
            )
        return CommandResult[object](value="must-not-commit", event_ids=(), error=None)

    with pytest.raises(CoreContractViolation) as captured:
        SQLiteUnitOfWork(database).execute_command(command, handler)

    assert captured.value.code is CoreErrorCode.STALE_VERSION
    connection = database.connect()
    try:
        assert connection.execute(
            "SELECT version FROM authority_records WHERE record_id = 'snp-a'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM command_receipts"
        ).fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.parametrize(
    "write_order",
    [
        pytest.param(("save", "consume"), id="save-then-consume"),
        pytest.param(("consume", "save"), id="consume-then-save"),
    ],
)
def test_capability_save_and_consume_share_one_target_write_claim(
    database_path: Path,
    ledger_event_factory: Callable[..., object],
    command_factory: Callable[..., object],
    standard_seed: Callable[..., None],
    write_order: tuple[str, str],
) -> None:
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database)
    command = command_factory(
        (CAPABILITY_ID, "evt-b"),
        (1, "absent"),
        idempotency_key=f"capability-{'-'.join(write_order)}",
    )
    before = _state(database)
    payload = {"attempt": "rolled-back-double-write"}
    payload_hash = sha256_hex(canonical_json(payload))

    def handler(repository, mutation_command, execution_context):
        del mutation_command
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
        updated_capability = make_capability(version=2)
        for operation in write_order:
            if operation == "save":
                repository.save_authoritative(
                    "maintenance_capability",
                    updated_capability.model_dump(mode="python"),
                )
            else:
                repository.consume_capability(CAPABILITY_ID)
        return CommandResult[object](
            value="must-not-commit",
            event_ids=repository.event_ids,
            error=None,
        )

    with pytest.raises(CoreContractViolation) as captured:
        SQLiteUnitOfWork(database).execute_command(command, handler)

    assert captured.value.code is CoreErrorCode.STALE_VERSION
    assert _state(database) == before


@pytest.mark.parametrize(
    ("mutation", "expected_code", "expects_content_hash_error"),
    [
        ("record-type", CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH, False),
        ("schema-root", CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH, False),
        ("record-id", CoreErrorCode.RECORD_ID_MISMATCH, False),
        ("header-body", CoreErrorCode.HEADER_BODY_MISMATCH, False),
        ("hash-scope", CoreErrorCode.HASH_SCOPE_MISMATCH, False),
        ("content-hash", None, True),
    ],
)
def test_repository_rejects_every_m2_authority_validation_mismatch_before_write(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    mutation: str,
    expected_code: CoreErrorCode | None,
    expects_content_hash_error: bool,
) -> None:
    from amadeus_core.contracts.validation import ContentHashMismatch
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    snapshot = snapshot_factory("snp-a")
    body = snapshot.model_dump(mode="python")
    schema_root = "source_snapshot"
    header = body["record_header"]
    if mutation == "record-type":
        header["record_type"] = "NotAuthoritative"
    elif mutation == "schema-root":
        schema_root = "identity"
    elif mutation == "record-id":
        header["record_id"] = "snp-b"
    elif mutation == "header-body":
        header["identity_id"] = "idn-b"
    elif mutation == "hash-scope":
        header["hash_scope"] = tuple(header["hash_scope"])[1:]
    else:
        header["content_hash"] = "f" * 64

    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("snp-a",),
        )
        if expects_content_hash_error:
            with pytest.raises(ContentHashMismatch):
                repository.save_authoritative(schema_root, body)
        else:
            with pytest.raises(CoreContractViolation) as captured:
                repository.save_authoritative(schema_root, body)
            assert captured.value.code is expected_code
        assert connection.execute(
            "SELECT count(*) FROM authority_records"
        ).fetchone()[0] == 0
        connection.rollback()
    finally:
        connection.close()


def test_repository_calls_m2_validation_api_and_round_trips_typed_record(
    database_path: Path,
    snapshot_factory: Callable[..., object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation
    from amadeus_core.contracts.source_snapshot import SourceSnapshot
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    snapshot = snapshot_factory("snp-a")
    calls = []
    real_validate = validation.validate_authoritative_record

    def tracking_validate(schema_root, body):
        calls.append((schema_root, body))
        return real_validate(schema_root, body)

    monkeypatch.setattr(validation, "validate_authoritative_record", tracking_validate)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("snp-a",),
        )
        saved = repository.save_authoritative(
            "source_snapshot",
            snapshot.model_dump(mode="python"),
        )
        loaded = repository.get("snp-a")
        connection.commit()
    finally:
        connection.close()

    assert calls and calls[0][0] == "source_snapshot"
    assert isinstance(saved, SourceSnapshot)
    assert loaded == saved


def test_repository_rejects_non_authoritative_body(
    database_path: Path,
) -> None:
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("idn-a",),
        )
        with pytest.raises(CoreContractViolation) as captured:
            repository.save_authoritative(
                "identity",
                {"actor_type": "system", "actor_id": "not-a-record"},
            )
        assert captured.value.code is CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH
        connection.rollback()
    finally:
        connection.close()


def test_confirmation_and_emergency_case_are_not_capability_projections(
    database_path: Path,
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    standard_seed(database)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("tmc-a", "emg-a"),
        )
        confirmation = make_termination_confirmation()
        emergency_case = make_emergency_case()
        repository.save_authoritative(
            "amadeus_termination_confirmation",
            confirmation.model_dump(mode="python"),
        )
        repository.save_authoritative(
            "emergency_unresponsive_case",
            emergency_case.model_dump(mode="python"),
        )

        authority_ids = {
            row[0]
            for row in connection.execute(
                """
                SELECT record_id
                FROM authority_records
                WHERE record_id IN ('tmc-a', 'emg-a')
                """
            )
        }
        projected_ids = {
            row[0]
            for row in connection.execute(
                """
                SELECT capability_id
                FROM capabilities
                WHERE capability_id IN ('tmc-a', 'emg-a')
                """
            )
        }
        assert authority_ids == {"tmc-a", "emg-a"}
        assert projected_ids == set()
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("record_factory", "capability_id", "expected_type"),
    [
        (make_vault_read_capability, "vrc-a", "vault_read"),
        (make_capability, CAPABILITY_ID, "maintenance"),
        (make_termination_execution_grant, "teg-a", "termination_execution"),
        (make_break_glass_grant, "bgg-a", "break_glass"),
    ],
)
def test_capability_projection_uses_frozen_type_mapping(
    database_path: Path,
    standard_seed: Callable[..., None],
    record_factory: Callable[..., object],
    capability_id: str,
    expected_type: str,
) -> None:
    database = _database(database_path)
    additional_records = () if capability_id == CAPABILITY_ID else (record_factory(),)
    standard_seed(database, additional_records)

    connection = database.connect()
    try:
        actual_type = connection.execute(
            "SELECT capability_type FROM capabilities WHERE capability_id = ?",
            (capability_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert actual_type == expected_type
