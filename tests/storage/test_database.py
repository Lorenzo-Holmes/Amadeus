from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier

import pytest


EXPECTED_USER_TABLES = {
    "authority_records",
    "command_receipts",
    "ledger_events",
    "branches",
    "identities",
    "lineages",
    "relationship_vaults",
    "proposals",
    "governor_decisions",
    "capabilities",
}


def _database(path: Path):
    from amadeus_core.storage.database import SQLiteDatabase

    return SQLiteDatabase(path)


def _user_tables(connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _schema_rows(connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            WHERE type IN ('table', 'index', 'trigger')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    )


def _insert_authority_stub(
    connection,
    *,
    record_id: str,
    record_type: str,
    identity_id: str = "idn-1",
    lineage_id: str = "lin-1",
    branch_id: str = "brn-1",
) -> None:
    connection.execute(
        """
        INSERT INTO authority_records (
            record_id,
            record_type,
            schema_version,
            version,
            identity_id,
            lineage_id,
            branch_id,
            content_hash,
            content_json,
            created_at
        ) VALUES (?, ?, '0.1', 1, ?, ?, ?, ?, '{}', '2026-08-01T00:00:00Z')
        """,
        (
            record_id,
            record_type,
            identity_id,
            lineage_id,
            branch_id,
            "0" * 64,
        ),
    )


def test_initial_schema_is_exactly_ten_tables(database_path: Path) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        assert _user_tables(connection) == EXPECTED_USER_TABLES


def test_connection_enables_foreign_keys_and_migration_is_repeatable(
    database_path: Path,
) -> None:
    database = _database(database_path)

    with closing(database.connect()) as first:
        assert first.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert _user_tables(first) == EXPECTED_USER_TABLES

    with closing(database.connect()) as reopened:
        assert reopened.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert _user_tables(reopened) == EXPECTED_USER_TABLES


def test_closed_connection_allows_immediate_database_delete(
    database_path: Path,
) -> None:
    with closing(_database(database_path).connect()) as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1

    database_path.unlink()
    assert not database_path.exists()


def test_genesis_cross_references_are_deferred_until_commit(database_path: Path) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        connection.execute("BEGIN")
        for record_id, record_type in (
            ("idn-1", "Identity"),
            ("lin-1", "Lineage"),
            ("brn-1", "Branch"),
        ):
            _insert_authority_stub(
                connection,
                record_id=record_id,
                record_type=record_type,
            )

        connection.execute(
            """
            INSERT INTO identities (
                identity_id, lifecycle_state, active_branch_id, version
            ) VALUES ('idn-1', 'active', 'brn-1', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO lineages (
                lineage_id, root_identity_id, root_branch_id, root_snapshot_id, version
            ) VALUES ('lin-1', 'idn-1', 'brn-1', NULL, 1)
            """
        )
        connection.execute(
            """
            INSERT INTO branches (
                branch_id, identity_id, lineage_id, status, version
            ) VALUES ('brn-1', 'idn-1', 'lin-1', 'active', 1)
            """
        )
        connection.commit()


def test_one_active_branch_per_identity_is_a_partial_unique_index(
    database_path: Path,
) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        row = connection.execute(
            """
            SELECT sql
            FROM sqlite_schema
            WHERE type = 'index' AND name = 'one_active_branch_per_identity'
            """
        ).fetchone()

    assert row is not None
    normalized_sql = " ".join(row[0].lower().replace('"', "").split())
    assert "unique index one_active_branch_per_identity" in normalized_sql
    assert "branches (identity_id)" in normalized_sql
    assert "where status = 'active'" in normalized_sql


def test_inline_session_lookup_uses_its_partial_expression_index(
    database_path: Path,
) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT event_id
            FROM ledger_events
            WHERE payload_mode = 'inline'
              AND json_extract(payload_inline_json, '$.session_id') = ?
              AND branch_id != ?
            """,
            ("session-a1", "brn-a1"),
        ).fetchall()

    details = " ".join(str(row[3]).lower() for row in plan)
    assert "using index ledger_events_inline_session" in details


def test_authority_session_lookup_uses_its_partial_expression_index(
    database_path: Path,
) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
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
            """,
            ("session-a1", "brn-a1"),
        ).fetchall()

    details = " ".join(str(row[3]).lower() for row in plan)
    assert "using index authority_records_ledger_session_correlation" in details


def test_session_started_correlation_is_a_global_partial_unique_index(
    database_path: Path,
) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        row = connection.execute(
            """
            SELECT sql
            FROM sqlite_schema
            WHERE type = 'index'
              AND name = 'authority_records_session_started_correlation'
            """
        ).fetchone()

    assert row is not None
    normalized_sql = " ".join(row[0].lower().replace('"', "").split())
    assert "unique index authority_records_session_started_correlation" in normalized_sql
    assert "json_extract(content_json, '$.correlation_id')" in normalized_sql
    assert "json_extract(content_json, '$.record_header.record_type') = 'ledgerevent'" in normalized_sql
    assert "json_extract(content_json, '$.event_type') = 'session_started'" in normalized_sql


def test_ledger_update_is_rejected_as_append_only(database_path: Path) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        connection.execute("BEGIN")
        _insert_authority_stub(
            connection,
            record_id="evt-1",
            record_type="LedgerEvent",
        )
        connection.execute(
            """
            INSERT INTO ledger_events (
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
            ) VALUES (
                'evt-1', 'brn-1', 1, NULL, ?, ?, 'inline', '{}', NULL, ?,
                'application/json'
            )
            """,
            ("0" * 64, f"inline:{'0' * 64}", "0" * 64),
        )

        with pytest.raises(sqlite3.IntegrityError, match="ledger is append-only"):
            connection.execute(
                "UPDATE ledger_events SET media_type = 'changed' WHERE event_id = 'evt-1'"
            )
        connection.rollback()


def test_ledger_delete_is_rejected_as_append_only(database_path: Path) -> None:
    database = _database(database_path)

    with closing(database.connect()) as connection:
        connection.execute("BEGIN")
        _insert_authority_stub(
            connection,
            record_id="evt-1",
            record_type="LedgerEvent",
        )
        connection.execute(
            """
            INSERT INTO ledger_events (
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
            ) VALUES (
                'evt-1', 'brn-1', 1, NULL, ?, ?, 'inline', '{}', NULL, ?,
                'application/json'
            )
            """,
            ("0" * 64, f"inline:{'0' * 64}", "0" * 64),
        )

        with pytest.raises(sqlite3.IntegrityError, match="ledger is append-only"):
            connection.execute("DELETE FROM ledger_events WHERE event_id = 'evt-1'")
        connection.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO branches VALUES ('brn-a','idn-a','lin-a','bogus',1)",
        "INSERT INTO identities VALUES ('idn-a','bogus','brn-a',1)",
        "INSERT INTO relationship_vaults VALUES ('vlt-a','idn-a','brn-a','bogus',1)",
        "INSERT INTO proposals VALUES ('prp-a','idn-a','brn-a','bogus','x',1)",
        "INSERT INTO governor_decisions VALUES ('gvd-a','prp-a','bogus',1)",
        "INSERT INTO capabilities VALUES ('mcp-a','bogus','idn-a','brn-a','issued',NULL,1,1)",
    ],
)
def test_projection_state_checks_reject_bogus_values(
    database_path: Path,
    statement: str,
) -> None:
    connection = _database(database_path).connect()
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(statement)
    finally:
        connection.close()


def test_reopen_rejects_an_extra_user_table(database_path: Path) -> None:
    database = _database(database_path)
    connection = database.connect()
    try:
        connection.execute("CREATE TABLE unexpected_extra_table (value TEXT)")
    finally:
        connection.close()

    with pytest.raises(ValueError, match="schema drift"):
        reopened = database.connect()
        reopened.close()


def test_open_rejects_incomplete_preexisting_authority_table(
    database_path: Path,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "CREATE TABLE authority_records (record_id TEXT PRIMARY KEY)"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ValueError, match="schema drift"):
        reopened = _database(database_path).connect()
        reopened.close()


def test_two_connections_can_initialize_one_exact_schema_concurrently(
    database_path: Path,
) -> None:
    database = _database(database_path)
    start = Barrier(2)

    def initialize() -> tuple[tuple[object, ...], ...]:
        start.wait()
        connection = database.connect()
        try:
            return _schema_rows(connection)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        fingerprints = tuple(
            future.result(timeout=10)
            for future in (executor.submit(initialize), executor.submit(initialize))
        )

    assert fingerprints[0] == fingerprints[1]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE command_receipts SET committed_at = 'changed'",
        "DELETE FROM command_receipts",
    ],
    ids=("update", "delete"),
)
def test_command_receipts_are_immutable(
    database_path: Path,
    statement: str,
) -> None:
    connection = _database(database_path).connect()
    try:
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
                "mcp-a",
                "0" * 64,
                "key-a",
                "cmd-a",
                "1" * 64,
                '{"value":null,"event_ids":[],"error":null,"replayed":false}',
                "2" * 64,
                "[]",
                "2026-08-01T00:00:00Z",
            ),
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="command receipt is immutable",
        ):
            connection.execute(statement)
    finally:
        connection.close()
