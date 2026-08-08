"""Deterministic SQLite connection factory for authority and derived views."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from hashlib import sha256
from importlib import resources
from os import PathLike
from pathlib import Path
import re
import sqlite3
from time import monotonic, sleep
from types import TracebackType
from typing import TypeAlias


DatabasePath: TypeAlias = str | PathLike[str]
_MIGRATIONS_PACKAGE = "amadeus_core.storage.migrations"
_MIGRATION_SEQUENCE = ((1, "0001_authority.sql"), (2, "0002_derived_views.sql"))
_SCHEMA_MIGRATIONS_DDL = """CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version >= 1),
    migration_sha256 TEXT NOT NULL CHECK (
        length(migration_sha256) = 64
        AND migration_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    applied_at TEXT NOT NULL
);
"""
_APPLIED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
SchemaFingerprint = tuple[tuple[str, str, str, str | None], ...]


class SchemaDriftError(ValueError):
    """The on-disk user schema differs from the frozen migration schema."""

    def __init__(self) -> None:
        super().__init__("storage schema drift detected")


def _migration_sources() -> tuple[tuple[int, str, str, str], ...]:
    sources: list[tuple[int, str, str, str]] = []
    package = resources.files(_MIGRATIONS_PACKAGE)
    for version, name in _MIGRATION_SEQUENCE:
        raw = package.joinpath(name).read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("migration must not contain a UTF-8 BOM")
        text = raw.decode("utf-8", errors="strict")
        sources.append((version, name, text, sha256(raw).hexdigest()))
    return tuple(sources)


def _execute_statements(connection: sqlite3.Connection, sql: str) -> None:
    statement: list[str] = []
    for character in sql:
        statement.append(character)
        candidate = "".join(statement)
        if sqlite3.complete_statement(candidate):
            connection.execute(candidate)
            statement.clear()
    tail = "".join(statement)
    if tail and not tail.isspace():
        raise ValueError("migration contains an incomplete SQL statement")


def _schema_fingerprint(connection: sqlite3.Connection) -> SchemaFingerprint:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_schema
        WHERE type IN ('table', 'index', 'trigger')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    return tuple((row[0], row[1], row[2], row[3]) for row in rows)


@lru_cache(maxsize=1)
def _authority_schema_fingerprint() -> SchemaFingerprint:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _execute_statements(connection, _migration_sources()[0][2])
        return _schema_fingerprint(connection)
    finally:
        connection.close()


@lru_cache(maxsize=2)
def _prefix_schema_fingerprint(version: int) -> SchemaFingerprint:
    if version not in {1, 2}:
        raise ValueError("unsupported migration prefix")
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _execute_statements(connection, _SCHEMA_MIGRATIONS_DDL)
        for source_version, _name, source_sql, _digest in _migration_sources():
            if source_version > version:
                break
            _execute_statements(connection, source_sql)
        return _schema_fingerprint(connection)
    finally:
        connection.close()


def _valid_applied_at(value: object) -> bool:
    if not isinstance(value, str) or _APPLIED_AT.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def _history(connection: sqlite3.Connection) -> tuple[tuple[int, str, str], ...]:
    rows = connection.execute(
        """
        SELECT version, migration_sha256, applied_at
        FROM schema_migrations
        ORDER BY version
        """
    ).fetchall()
    return tuple((row[0], row[1], row[2]) for row in rows)


def _verify_history(
    connection: sqlite3.Connection,
    sources: tuple[tuple[int, str, str, str], ...],
) -> int:
    history = _history(connection)
    versions = tuple(row[0] for row in history)
    if versions not in {(1,), (1, 2)}:
        raise SchemaDriftError()
    expected_by_version = {version: digest for version, _name, _sql, digest in sources}
    for version, digest, applied_at in history:
        if type(version) is not int or digest != expected_by_version.get(version):
            raise SchemaDriftError()
        if not _valid_applied_at(applied_at):
            raise SchemaDriftError()
    return versions[-1]


def _insert_history(connection: sqlite3.Connection, version: int, digest: str) -> None:
    connection.execute(
        """
        INSERT INTO schema_migrations (version, migration_sha256, applied_at)
        VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        """,
        (version, digest),
    )


def _apply_migration(
    connection: sqlite3.Connection,
    source: tuple[int, str, str, str],
) -> None:
    version, _name, sql, digest = source
    _execute_statements(connection, sql)
    _insert_history(connection, version, digest)


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply the frozen migration sequence and reject all schema/history drift."""

    try:
        sources = _migration_sources()
        connection.execute("BEGIN IMMEDIATE")
        actual = _schema_fingerprint(connection)
        metadata_present = any(row[1] == "schema_migrations" for row in actual)

        if not metadata_present:
            if not actual:
                _execute_statements(connection, _SCHEMA_MIGRATIONS_DDL)
                _apply_migration(connection, sources[0])
                _apply_migration(connection, sources[1])
            elif actual == _authority_schema_fingerprint():
                _execute_statements(connection, _SCHEMA_MIGRATIONS_DDL)
                _insert_history(connection, sources[0][0], sources[0][3])
                _apply_migration(connection, sources[1])
            else:
                raise SchemaDriftError()
        else:
            current_version = _verify_history(connection, sources)
            if actual != _prefix_schema_fingerprint(current_version):
                raise SchemaDriftError()
            if current_version == 1:
                _apply_migration(connection, sources[1])

        if _verify_history(connection, sources) != 2:
            raise SchemaDriftError()
        if _schema_fingerprint(connection) != _prefix_schema_fingerprint(2):
            raise SchemaDriftError()
        connection.commit()
    except BaseException as error:
        if connection.in_transaction:
            connection.rollback()
        if isinstance(error, SchemaDriftError):
            raise
        raise SchemaDriftError() from error


def _enable_wal(connection: sqlite3.Connection) -> None:
    deadline = monotonic() + 5.0
    while True:
        try:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise sqlite3.OperationalError("failed to enable WAL journal mode")
            return
        except sqlite3.OperationalError as error:
            locked = "locked" in str(error).lower() or "busy" in str(error).lower()
            if not locked or monotonic() >= deadline:
                raise
            sleep(0.01)


def open_database(path: DatabasePath) -> sqlite3.Connection:
    """Open, configure, and migrate one authority database connection."""

    connection = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        _enable_wal(connection)
        connection.execute("PRAGMA synchronous = FULL")
        apply_migrations(connection)
    except BaseException:
        connection.close()
        raise
    return connection


class SQLiteDatabase:
    """Re-openable connection factory bound to one database path."""

    __slots__ = ("_path",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SQLiteDatabase is final")

    def __init__(self, path: DatabasePath) -> None:
        object.__setattr__(self, "_path", Path(path) if not isinstance(path, str) else path)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("SQLiteDatabase configuration is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("SQLiteDatabase configuration is immutable")

    @property
    def path(self) -> DatabasePath:
        return self._path

    def connect(self) -> sqlite3.Connection:
        return open_database(self._path)


class _SerializedTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_value, traceback
        if exc_type is not None:
            if self._connection.in_transaction:
                self._connection.rollback()
            return False
        try:
            self._connection.commit()
        except BaseException:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        return False


def serialized_transaction(connection: sqlite3.Connection) -> _SerializedTransaction:
    """Hold SQLite's write reservation across check, handler, and receipt."""

    return _SerializedTransaction(connection)


__all__ = [
    "DatabasePath",
    "SchemaDriftError",
    "SQLiteDatabase",
    "apply_migrations",
    "open_database",
    "serialized_transaction",
]
