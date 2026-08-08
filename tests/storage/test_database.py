from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
import hashlib
from importlib import resources
from pathlib import Path
import re
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
    "schema_migrations",
    "derived_view_scopes",
    "derived_view_manifests",
    "derived_view_contents",
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


def test_initial_schema_is_exactly_fourteen_tables(database_path: Path) -> None:
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


def test_fresh_database_records_exact_migration_history_and_latest_schema(
    database_path: Path,
) -> None:
    database = _database(database_path)
    with closing(database.connect()) as connection:
        history = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT version, migration_sha256, applied_at FROM schema_migrations ORDER BY version"
            )
        )
        assert tuple((version, digest) for version, digest, _ in history) == _EXPECTED_FINAL_MIGRATION_HISTORY
        for _version, _digest, applied_at in history:
            _assert_rfc3339_millis(applied_at)
        assert _raw_schema(connection) == _independent_final_schema_fingerprint()
        assert {"schema_migrations", "derived_view_scopes", "derived_view_manifests", "derived_view_contents"} <= _user_tables(
            connection
        )


_MIGRATION_0001_SHA256 = "5DAAB4E63E205386284EFD10319727BA422EF19DA10BA3472D87ADF2AB795ACB"
_MIGRATION_0002_SHA256 = "67F30B87C8FFD06CDB36622A7AE6DE16DA5B3B814E4BDD7CABEE3D183C4971F8"
_EXPECTED_FINAL_MIGRATION_HISTORY = (
    (1, _MIGRATION_0001_SHA256.lower()),
    (2, _MIGRATION_0002_SHA256.lower()),
)
_RFC3339_MILLIS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_TEST_SCHEMA_MIGRATIONS_DDL = """CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version >= 1),
    migration_sha256 TEXT NOT NULL CHECK (
        length(migration_sha256) = 64
        AND migration_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    applied_at TEXT NOT NULL
);
"""


def _migration_bytes(name: str) -> bytes:
    return (
        resources.files("amadeus_core.storage.migrations")
        .joinpath(name)
        .read_bytes()
    )


def _migration_digest(name: str) -> str:
    return hashlib.sha256(_migration_bytes(name)).hexdigest()


def _assert_rfc3339_millis(value: object) -> None:
    assert isinstance(value, str)
    assert _RFC3339_MILLIS.fullmatch(value) is not None
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")


def _raw_schema(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return _schema_rows(connection)


def _raw_history(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            "SELECT version, migration_sha256, applied_at FROM schema_migrations ORDER BY version"
        )
    )


def _independent_final_schema_fingerprint() -> tuple[tuple[object, ...], ...]:
    """Build the frozen final schema with raw SQLite, outside production helpers."""

    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(_TEST_SCHEMA_MIGRATIONS_DDL)
        for name in ("0001_authority.sql", "0002_derived_views.sql"):
            connection.executescript(_migration_bytes(name).decode("utf-8"))
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
    finally:
        connection.close()


def _run_sql_bytes(connection: sqlite3.Connection, raw: bytes) -> None:
    """Execute a frozen migration in raw SQLite only for legacy-state fixtures."""

    connection.executescript(raw.decode("utf-8"))


def _create_authority_prefix(path: Path, *, metadata: bool) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    _run_sql_bytes(connection, _migration_bytes("0001_authority.sql"))
    if metadata:
        import amadeus_core.storage.database as database_module

        connection.execute(database_module._SCHEMA_MIGRATIONS_DDL)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, ?, '2026-08-06T00:00:00.000Z')",
            (_migration_digest("0001_authority.sql"),),
        )
    return connection


def _assert_reopen_rejects_without_repair(path: Path) -> None:
    """A rejected open must leave the adversarial on-disk state byte-for-byte logical."""

    raw = sqlite3.connect(path)
    try:
        before_history = _raw_history(raw)
        before_schema = _raw_schema(raw)
    finally:
        raw.close()
    with pytest.raises(ValueError, match="schema drift"):
        _database(path).connect()
    raw = sqlite3.connect(path)
    try:
        assert _raw_history(raw) == before_history
        assert _raw_schema(raw) == before_schema
    finally:
        raw.close()


def test_frozen_migration_resource_sha256_values_are_exact() -> None:
    assert _migration_digest("0001_authority.sql").lower() == _MIGRATION_0001_SHA256.lower()
    assert _migration_digest("0002_derived_views.sql").lower() == _MIGRATION_0002_SHA256.lower()


def test_fresh_migration_history_is_exact_and_reopen_preserves_schema(
    database_path: Path,
) -> None:
    database = _database(database_path)
    with closing(database.connect()) as connection:
        history = _raw_history(connection)
        first_schema = _raw_schema(connection)
        assert tuple((version, digest) for version, digest, _ in history) == _EXPECTED_FINAL_MIGRATION_HISTORY
        for _version, _digest, applied_at in history:
            _assert_rfc3339_millis(applied_at)
        assert first_schema == _independent_final_schema_fingerprint()
        assert _user_tables(connection) == EXPECTED_USER_TABLES
    with closing(database.connect()) as reopened:
        assert _raw_history(reopened) == history
        assert _raw_schema(reopened) == first_schema
        assert _user_tables(reopened) == EXPECTED_USER_TABLES


def test_legacy_exact_0001_without_metadata_preserves_authority_and_upgrades(
    database_path: Path,
) -> None:
    legacy = _create_authority_prefix(database_path, metadata=False)
    try:
        _insert_authority_stub(
            legacy,
            record_id="legacy-record",
            record_type="LegacyFixture",
        )
        legacy.commit()
    finally:
        legacy.close()

    with closing(_database(database_path).connect()) as connection:
        assert tuple(connection.execute(
            "SELECT record_id, record_type FROM authority_records WHERE record_id = 'legacy-record'"
        ).fetchone()) == ("legacy-record", "LegacyFixture")
        assert tuple(row[0] for row in _raw_history(connection)) == (1, 2)
        assert _user_tables(connection) == EXPECTED_USER_TABLES


def test_metadata_0001_prefix_resumes_to_final_without_rewriting_prefix(
    database_path: Path,
) -> None:
    prefix = _create_authority_prefix(database_path, metadata=True)
    try:
        _insert_authority_stub(
            prefix,
            record_id="prefix-record",
            record_type="PrefixFixture",
        )
        prefix.commit()
    finally:
        prefix.close()

    with closing(_database(database_path).connect()) as connection:
        history = _raw_history(connection)
        assert history[0] == (
            1,
            _migration_digest("0001_authority.sql"),
            "2026-08-06T00:00:00.000Z",
        )
        assert history[1][0:2] == (2, _migration_digest("0002_derived_views.sql"))
        assert connection.execute(
            "SELECT record_type FROM authority_records WHERE record_id = 'prefix-record'"
        ).fetchone()[0] == "PrefixFixture"
        assert _user_tables(connection) == EXPECTED_USER_TABLES


@pytest.mark.parametrize(
    ("mutate", "case"),
    (
        (lambda c: c.execute("DELETE FROM schema_migrations"), "zero_rows"),
        (
            lambda c: (
                c.execute("DELETE FROM schema_migrations"),
                c.execute(
                    "INSERT INTO schema_migrations VALUES (2, ?, '2026-08-06T00:00:00.000Z')",
                    (_migration_digest("0002_derived_views.sql"),),
                ),
            ),
            "only_v2",
        ),
        (lambda c: c.execute("DELETE FROM schema_migrations WHERE version = 2"), "final_schema_partial_v1"),
        (
            lambda c: c.execute(
                "INSERT INTO schema_migrations VALUES (3, ?, '2026-08-06T00:00:00.000Z')",
                ("3" * 64,),
            ),
            "extra_v3",
        ),
        (
            lambda c: c.execute(
                "UPDATE schema_migrations SET migration_sha256 = ? WHERE version = 1",
                ("f" * 64,),
            ),
            "v1_wrong_digest",
        ),
        (
            lambda c: c.execute(
                "UPDATE schema_migrations SET migration_sha256 = ? WHERE version = 2",
                ("e" * 64,),
            ),
            "v2_wrong_digest",
        ),
        (
            lambda c: c.execute(
                "UPDATE schema_migrations SET applied_at = 'not-an-rfc3339-millis' WHERE version = 1"
            ),
            "illegal_applied_at",
        ),
    ),
)
def test_invalid_migration_history_rejects_closed_without_repair(
    database_path: Path,
    mutate,
    case: str,
) -> None:
    del case
    with closing(_database(database_path).connect()) as connection:
        pass
    raw = sqlite3.connect(database_path)
    try:
        mutate(raw)
        raw.commit()
    finally:
        raw.close()
    _assert_reopen_rejects_without_repair(database_path)


@pytest.mark.parametrize("changed_version", (1, 2))
def test_registered_database_rejects_changed_migration_resource_or_hash(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_version: int,
) -> None:
    import amadeus_core.storage.database as database_module

    with closing(_database(database_path).connect()):
        pass
    original_sources = database_module._migration_sources
    changed_digest = ("a" if changed_version == 1 else "b") * 64

    def changed_sources():
        return tuple(
            (version, name, text + ("\n-- changed resource" if version == changed_version else ""),
             changed_digest if version == changed_version else digest)
            for version, name, text, digest in original_sources()
        )

    monkeypatch.setattr(database_module, "_migration_sources", changed_sources)
    _assert_reopen_rejects_without_repair(database_path)


@pytest.mark.parametrize("prefix_version", (1, 2))
def test_legal_history_with_schema_drift_is_rejected_without_repair(
    database_path: Path,
    prefix_version: int,
) -> None:
    if prefix_version == 1:
        prefix = _create_authority_prefix(database_path, metadata=True)
        try:
            prefix.execute("CREATE TABLE prefix_drift (value TEXT)")
            prefix.commit()
        finally:
            prefix.close()
    else:
        with closing(_database(database_path).connect()) as connection:
            connection.execute("CREATE INDEX final_drift ON derived_view_scopes(generation)")
    _assert_reopen_rejects_without_repair(database_path)


def test_connection_settings_are_all_pinned(database_path: Path) -> None:
    with closing(_database(database_path).connect()) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert connection.row_factory is sqlite3.Row
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2  # SQLite FULL


class _OpenDatabaseStageFailure(RuntimeError):
    pass


class _OpenDatabaseStageConnection:
    """Transparent connection wrapper that injects one exact setup-stage failure."""

    def __init__(self, connection: sqlite3.Connection, stage: str) -> None:
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_stage", stage)

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_connection", "_stage"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._connection, name, value)

    def execute(self, statement: str, parameters: tuple[object, ...] = ()):
        normalized = " ".join(statement.split()).lower()
        if (
            self._stage == "foreign_keys"
            and normalized == "pragma foreign_keys = on"
        ) or (
            self._stage == "busy_timeout"
            and normalized == "pragma busy_timeout = 5000"
        ) or (
            self._stage == "synchronous"
            and normalized == "pragma synchronous = full"
        ):
            raise _OpenDatabaseStageFailure(f"fixture {self._stage} failure")
        return self._connection.execute(statement, parameters)

    def close(self) -> None:
        self._connection.close()


@pytest.mark.parametrize(
    "stage",
    ("foreign_keys", "busy_timeout", "wal", "synchronous", "apply_migrations"),
    ids=("foreign_keys", "busy_timeout", "wal", "synchronous", "apply_migrations"),
)
def test_initialization_failure_closes_its_actual_connection(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    import amadeus_core.storage.database as database_module

    captured_underlying: list[sqlite3.Connection] = []
    received_by_open_database: list[_OpenDatabaseStageConnection] = []
    real_connect = sqlite3.connect

    def capture_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        captured_underlying.append(connection)
        wrapped = _OpenDatabaseStageConnection(connection, stage)
        received_by_open_database.append(wrapped)
        return wrapped

    def fail_wal(connection: _OpenDatabaseStageConnection) -> None:
        assert connection is received_by_open_database[0]
        raise _OpenDatabaseStageFailure("fixture wal failure")

    def fail_migrations(connection: _OpenDatabaseStageConnection) -> None:
        assert connection is received_by_open_database[0]
        raise _OpenDatabaseStageFailure("fixture apply_migrations failure")

    monkeypatch.setattr(database_module.sqlite3, "connect", capture_connect)
    if stage == "wal":
        monkeypatch.setattr(database_module, "_enable_wal", fail_wal)
    elif stage == "apply_migrations":
        monkeypatch.setattr(database_module, "apply_migrations", fail_migrations)

    with pytest.raises(_OpenDatabaseStageFailure, match=f"fixture {stage} failure"):
        database_module.open_database(database_path)
    assert len(captured_underlying) == 1
    assert len(received_by_open_database) == 1
    assert received_by_open_database[0]._connection is captured_underlying[0]
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        captured_underlying[0].execute("SELECT 1")
