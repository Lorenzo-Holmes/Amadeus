"""Deterministic SQLite connection factory for the authority store."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from importlib import resources
from os import PathLike
from pathlib import Path
from time import monotonic, sleep
from types import TracebackType
from typing import TypeAlias


DatabasePath: TypeAlias = str | PathLike[str]
_MIGRATIONS_PACKAGE = "amadeus_core.storage.migrations"
_INITIAL_MIGRATION = "0001_authority.sql"
SchemaFingerprint = tuple[tuple[str, str, str, str | None], ...]


class SchemaDriftError(ValueError):
    """The on-disk user schema differs from the frozen migration schema."""


def _migration_sql() -> str:
    return (
        resources.files(_MIGRATIONS_PACKAGE)
        .joinpath(_INITIAL_MIGRATION)
        .read_text(encoding="utf-8")
    )


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
def _expected_schema_fingerprint(migration_sql: str) -> SchemaFingerprint:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.executescript("BEGIN IMMEDIATE;\n" + migration_sql)
        return _schema_fingerprint(connection)
    finally:
        connection.close()


def _migrate_and_verify(
    connection: sqlite3.Connection,
    migration_sql: str,
) -> None:
    expected = _expected_schema_fingerprint(migration_sql)
    try:
        connection.executescript("BEGIN IMMEDIATE;\n" + migration_sql)
        if _schema_fingerprint(connection) != expected:
            raise SchemaDriftError("storage schema drift detected")
        connection.commit()
    except BaseException as error:
        if connection.in_transaction:
            connection.rollback()
        if (
            isinstance(error, sqlite3.OperationalError)
            and _schema_fingerprint(connection) != expected
        ):
            raise SchemaDriftError("storage schema drift detected") from error
        raise


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

    connection = sqlite3.connect(
        str(path),
        isolation_level=None,
        timeout=5.0,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        _enable_wal(connection)
        connection.execute("PRAGMA synchronous = FULL")
        _migrate_and_verify(connection, _migration_sql())
    except BaseException:
        connection.close()
        raise
    return connection


class SQLiteDatabase:
    """Re-openable connection factory bound to one database path."""

    def __init__(self, path: DatabasePath) -> None:
        self._path = Path(path) if not isinstance(path, str) else path

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
    "open_database",
    "serialized_transaction",
]
