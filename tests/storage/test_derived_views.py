from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
import typing

import pytest


_VIEW_TYPES = ("summary", "timeline", "vector", "fulltext", "cue")
_EMPTY_SCOPE_HASH = "8143fd305150364771de1177d1359eefdb378c6d423aa113b46eb25ee92942e2"


def _module():
    import amadeus_core.storage.derived_views as module

    return module


def _contracts():
    import amadeus_core.contracts as contracts

    return contracts


def _scope(*, suffix: str = "1"):
    return _module().DerivedViewScope(
        identity_id=f"idn-{suffix}",
        lineage_id=f"lin-{suffix}",
        branch_id=f"brn-{suffix}",
        vault_id=f"vlt-{suffix}",
    )


def _entries(
    scope,
    *,
    built_at: datetime = datetime(2026, 8, 6, tzinfo=timezone.utc),
    contents: tuple[Mapping[str, object], ...] | None = None,
    view_ids: tuple[str, ...] | None = None,
    watermark: int = 0,
    root_hash: str = "0" * 64,
    builder_version: str = "builder-v1",
) -> tuple[Any, ...]:
    module = _module()
    contracts = _contracts()
    if contents is None:
        contents = tuple({"ordinal": index} for index in range(1, 6))
    if view_ids is None:
        view_ids = tuple(f"viw-{index}" for index in range(1, 6))
    return tuple(
        module.DerivedViewEntry(
            manifest=contracts.MaterializedViewManifest(
                view_id=view_ids[index - 1],
                view_type=view_type,
                identity_id=scope.identity_id,
                branch_id=scope.branch_id,
                vault_id=scope.vault_id,
                source_watermark_seq=watermark,
                source_root_hash=root_hash,
                builder_version=builder_version,
                built_at=built_at,
                view_hash=(str(index) * 64),
            ),
            content=contents[index - 1],
        )
        for index, view_type in enumerate(_VIEW_TYPES, start=1)
    )


def _independent_state_hash(scope, entries: tuple[Any, ...]) -> str:
    """A test oracle deliberately independent of derived_views._state_hash."""

    from amadeus_core.contracts.hashing import canonical_json
    from amadeus_core.storage.payloads import canonical_closed_json

    preimage = {
        "state_hash_version": "derived-view-state-v1",
        "scope_refs": {
            "identity_id": scope.identity_id,
            "lineage_id": scope.lineage_id,
            "branch_id": scope.branch_id,
            "vault_id": scope.vault_id,
        },
        "entries": [
            {
                "view_type": entry.manifest.view_type,
                "view_id": entry.manifest.view_id,
                "source_watermark_seq": entry.manifest.source_watermark_seq,
                "source_root_hash": entry.manifest.source_root_hash,
                "builder_version": entry.manifest.builder_version,
                "view_hash": entry.manifest.view_hash,
                "content_hash": hashlib.sha256(
                    canonical_closed_json(entry.content)
                ).hexdigest(),
            }
            for entry in entries
        ],
    }
    return hashlib.sha256(canonical_json(preimage)).hexdigest()


def _connection(database_path: Path) -> sqlite3.Connection:
    from amadeus_core.storage.database import SQLiteDatabase

    return SQLiteDatabase(database_path).connect()


def _derived_counts(connection: sqlite3.Connection) -> tuple[int, int, int]:
    return tuple(
        int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in (
            "derived_view_scopes",
            "derived_view_manifests",
            "derived_view_contents",
        )
    )


def _derived_rows(connection: sqlite3.Connection) -> tuple[tuple[tuple[object, ...], ...], ...]:
    return (
        tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM derived_view_scopes ORDER BY identity_id, lineage_id, branch_id, vault_id"
            )
        ),
        tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM derived_view_manifests ORDER BY view_id"
            )
        ),
        tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM derived_view_contents ORDER BY view_id"
            )
        ),
    )


def _replace_first(connection: sqlite3.Connection, scope, entries):
    module = _module()
    store = module.SQLiteDerivedViewStore(connection)
    connection.execute("BEGIN")
    snapshot = store.replace_scope(
        scope,
        expected_generation=0,
        expected_semantic_state_hash=module.empty_derived_state_hash(scope),
        entries=entries,
    )
    connection.commit()
    return snapshot


def _authority_ledger_receipt_history_schema(connection: sqlite3.Connection) -> tuple[object, ...]:
    return (
        tuple(connection.execute("SELECT * FROM authority_records ORDER BY record_id")),
        tuple(connection.execute("SELECT * FROM ledger_events ORDER BY event_id")),
        tuple(connection.execute("SELECT * FROM command_receipts ORDER BY command_id")),
        tuple(connection.execute("SELECT * FROM schema_migrations ORDER BY version")),
        tuple(
            connection.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_schema
                WHERE type IN ('table', 'index', 'trigger')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            )
        ),
    )


class _ConnectionProxy:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def in_transaction(self) -> bool:
        return self._connection.in_transaction

    def execute(self, statement: str, parameters: tuple[object, ...] = ()):
        return self._connection.execute(statement, parameters)


class _ZeroRowcountCursor:
    rowcount = 0


class _GuardUpdateZeroConnection(_ConnectionProxy):
    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)
        self.guard_update_seen = False

    def execute(self, statement: str, parameters: tuple[object, ...] = ()):
        if statement.lstrip().startswith("UPDATE derived_view_scopes"):
            self.guard_update_seen = True
            return _ZeroRowcountCursor()
        return super().execute(statement, parameters)


class _FailNthContentInsertConnection(_ConnectionProxy):
    def __init__(self, connection: sqlite3.Connection, fail_at: int) -> None:
        super().__init__(connection)
        self._fail_at = fail_at
        self.content_inserts = 0

    def execute(self, statement: str, parameters: tuple[object, ...] = ()):
        if statement.lstrip().startswith("INSERT INTO derived_view_contents"):
            self.content_inserts += 1
            if self.content_inserts == self._fail_at:
                raise sqlite3.IntegrityError("fixture mid-insert failure")
        return super().execute(statement, parameters)


def _valid_scope_row(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO derived_view_scopes VALUES
        ('idn-1', 'lin-1', 'brn-1', 'vlt-1', 1, ?)
        """,
        ("0" * 64,),
    )


def _valid_manifest_row(connection: sqlite3.Connection, *, view_id: str = "viw-a") -> None:
    _valid_scope_row(connection)
    connection.execute(
        """
        INSERT INTO derived_view_manifests VALUES
        ('idn-1', 'lin-1', 'brn-1', 'vlt-1', 'summary', ?, '{}', ?, ?)
        """,
        (view_id, "1" * 64, "2" * 64),
    )


def test_derived_view_api_surface_exists(database_path: Path) -> None:
    module = _module()
    package = __import__("amadeus_core.storage", fromlist=["__all__"])
    required = (
        "DerivedViewScope",
        "DerivedViewEntry",
        "DerivedViewSnapshot",
        "DerivedViewCASConflict",
        "DerivedViewIntegrityError",
        "DerivedViewTransactionRequired",
        "empty_derived_state_hash",
        "SQLiteDerivedViewStore",
    )
    assert tuple(module.__all__) == required
    assert set(required) <= set(package.__all__)
    model_specs = (
        (
            module.DerivedViewScope,
            ("identity_id", "lineage_id", "branch_id", "vault_id"),
            {
                "identity_id": str,
                "lineage_id": str,
                "branch_id": str,
                "vault_id": str,
            },
        ),
        (
            module.DerivedViewEntry,
            ("manifest", "content"),
            {
                "manifest": _contracts().MaterializedViewManifest,
                "content": Mapping[str, object],
            },
        ),
        (
            module.DerivedViewSnapshot,
            ("scope", "generation", "semantic_state_hash", "entries"),
            {
                "scope": module.DerivedViewScope,
                "generation": int,
                "semantic_state_hash": str,
                "entries": tuple[module.DerivedViewEntry, ...],
            },
        ),
    )
    for model, fields, annotations in model_specs:
        assert tuple(model.model_fields) == fields
        assert typing.get_type_hints(model) == annotations

    expected_exceptions = (
        (module.DerivedViewCASConflict, RuntimeError, "derived-view compare-and-swap conflict"),
        (module.DerivedViewIntegrityError, ValueError, "derived-view integrity verification failed"),
        (module.DerivedViewTransactionRequired, RuntimeError, "replace_scope requires an active transaction"),
    )
    for exception_type, direct_base, message in expected_exceptions:
        assert exception_type.__bases__ == (direct_base,)
        assert str(exception_type()) == message

    empty = inspect.signature(module.empty_derived_state_hash)
    assert tuple(empty.parameters) == ("scope",)
    assert empty.parameters["scope"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert typing.get_type_hints(module.empty_derived_state_hash) == {
        "scope": module.DerivedViewScope,
        "return": str,
    }
    initializer = inspect.signature(module.SQLiteDerivedViewStore.__init__)
    assert tuple(initializer.parameters) == ("self", "connection")
    assert initializer.parameters["connection"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert typing.get_type_hints(module.SQLiteDerivedViewStore.__init__) == {
        "connection": sqlite3.Connection,
        "return": type(None),
    }
    read = inspect.signature(module.SQLiteDerivedViewStore.read_scope)
    assert tuple(read.parameters) == ("self", "scope")
    assert read.parameters["scope"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert typing.get_type_hints(module.SQLiteDerivedViewStore.read_scope) == {
        "scope": module.DerivedViewScope,
        "return": module.DerivedViewSnapshot | None,
    }
    replace = inspect.signature(module.SQLiteDerivedViewStore.replace_scope)
    assert tuple(replace.parameters) == (
        "self", "scope", "expected_generation", "expected_semantic_state_hash", "entries"
    )
    assert replace.parameters["expected_generation"].kind is inspect.Parameter.KEYWORD_ONLY
    assert replace.parameters["expected_semantic_state_hash"].kind is inspect.Parameter.KEYWORD_ONLY
    assert replace.parameters["entries"].kind is inspect.Parameter.KEYWORD_ONLY
    assert typing.get_type_hints(module.SQLiteDerivedViewStore.replace_scope) == {
        "scope": module.DerivedViewScope,
        "expected_generation": int,
        "expected_semantic_state_hash": str,
        "entries": tuple[module.DerivedViewEntry, ...],
        "return": module.DerivedViewSnapshot,
    }

    with closing(_connection(database_path)) as connection:
        expected_columns = {
            "derived_view_scopes": (
                ("identity_id", "TEXT", 1, 1), ("lineage_id", "TEXT", 1, 2),
                ("branch_id", "TEXT", 1, 3), ("vault_id", "TEXT", 1, 4),
                ("generation", "INTEGER", 1, 0), ("semantic_state_hash", "TEXT", 1, 0),
            ),
            "derived_view_manifests": (
                ("identity_id", "TEXT", 1, 1), ("lineage_id", "TEXT", 1, 2),
                ("branch_id", "TEXT", 1, 3), ("vault_id", "TEXT", 1, 4),
                ("view_type", "TEXT", 1, 5), ("view_id", "TEXT", 1, 0),
                ("manifest_json", "TEXT", 1, 0), ("manifest_hash", "TEXT", 1, 0),
                ("content_hash", "TEXT", 1, 0),
            ),
            "derived_view_contents": (
                ("view_id", "TEXT", 0, 1), ("content_json", "TEXT", 1, 0),
                ("content_hash", "TEXT", 1, 0),
            ),
        }
        for table, expected in expected_columns.items():
            actual = tuple(
                (row["name"], row["type"], row["notnull"], row["pk"])
                for row in connection.execute(f"PRAGMA table_info({table})")
            )
            assert actual == expected

        manifest_indexes = tuple(connection.execute("PRAGMA index_list(derived_view_manifests)"))
        unique_indexes = [row["name"] for row in manifest_indexes if row["unique"] == 1]
        assert any(
            tuple(row["name"] for row in connection.execute(f"PRAGMA index_info({name})"))
            == ("view_id",)
            for name in unique_indexes
        )
        manifest_fks = tuple(connection.execute("PRAGMA foreign_key_list(derived_view_manifests)"))
        assert len({row["id"] for row in manifest_fks}) == 1
        assert tuple(
            (
                row["id"],
                row["seq"],
                row["from"],
                row["to"],
                row["table"],
                row["on_delete"],
            )
            for row in sorted(manifest_fks, key=lambda row: row["seq"])
        ) == (
            (0, 0, "identity_id", "identity_id", "derived_view_scopes", "CASCADE"),
            (0, 1, "lineage_id", "lineage_id", "derived_view_scopes", "CASCADE"),
            (0, 2, "branch_id", "branch_id", "derived_view_scopes", "CASCADE"),
            (0, 3, "vault_id", "vault_id", "derived_view_scopes", "CASCADE"),
        )
        content_fks = tuple(connection.execute("PRAGMA foreign_key_list(derived_view_contents)"))
        assert len(content_fks) == 1
        assert (content_fks[0]["table"], content_fks[0]["from"], content_fks[0]["to"], content_fks[0]["on_delete"]) == (
            "derived_view_manifests", "view_id", "view_id", "CASCADE"
        )


def test_derived_ddl_checks_generation_view_type_and_json_validity(
    database_path: Path,
) -> None:
    with closing(_connection(database_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO derived_view_scopes VALUES ('idn-1','lin-1','brn-1','vlt-1',0, ?)",
                ("0" * 64,),
            )
        _valid_scope_row(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO derived_view_manifests VALUES
                ('idn-1','lin-1','brn-1','vlt-1','wrong','viw-a','{}',?,?)
                """,
                ("1" * 64, "2" * 64),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO derived_view_manifests VALUES
                ('idn-1','lin-1','brn-1','vlt-1','summary','viw-a','not json',?,?)
                """,
                ("1" * 64, "2" * 64),
            )
    with closing(_connection(database_path.with_name("content-json.sqlite3"))) as connection:
        _valid_manifest_row(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO derived_view_contents VALUES ('viw-a', 'not json', ?)",
                ("3" * 64,),
            )


@pytest.mark.parametrize("bad_hash", ("0" * 63, "A" * 64, "g" * 64), ids=("length", "uppercase", "nonhex"))
@pytest.mark.parametrize("target", ("scope", "manifest", "content"))
def test_derived_ddl_rejects_every_hash_field_variant(
    database_path: Path,
    bad_hash: str,
    target: str,
) -> None:
    with closing(_connection(database_path)) as connection:
        if target == "scope":
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO derived_view_scopes VALUES ('idn-1','lin-1','brn-1','vlt-1',1, ?)",
                    (bad_hash,),
                )
        elif target == "manifest":
            _valid_scope_row(connection)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO derived_view_manifests VALUES
                    ('idn-1','lin-1','brn-1','vlt-1','summary','viw-a','{}',?,?)
                    """,
                    (bad_hash, "2" * 64),
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO derived_view_manifests VALUES
                    ('idn-1','lin-1','brn-1','vlt-1','summary','viw-b','{}',?,?)
                    """,
                    ("1" * 64, bad_hash),
                )
        else:
            _valid_manifest_row(connection)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO derived_view_contents VALUES ('viw-a','{}',?)", (bad_hash,)
                )


def test_empty_derived_state_hash_matches_independent_lowercase_golden() -> None:
    module = _module()
    scope = _scope()
    assert _independent_state_hash(scope, ()) == _EMPTY_SCOPE_HASH
    assert module.empty_derived_state_hash(scope) == _EMPTY_SCOPE_HASH


def test_first_replace_uses_generation_one_and_canonical_hashes(database_path: Path) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        connection.execute("BEGIN")
        snapshot = module.SQLiteDerivedViewStore(connection).replace_scope(
            scope,
            expected_generation=0,
            expected_semantic_state_hash=_EMPTY_SCOPE_HASH,
            entries=entries,
        )
        assert snapshot.generation == 1
        assert snapshot.scope == scope
        assert snapshot.semantic_state_hash == _independent_state_hash(scope, entries)
        assert tuple(entry.manifest.view_type for entry in snapshot.entries) == _VIEW_TYPES
        connection.rollback()


def test_built_at_only_changes_manifest_not_semantic_state_and_content_changes_state(
    database_path: Path,
) -> None:
    module = _module()
    scope = _scope()
    early = _entries(scope)
    late = _entries(scope, built_at=datetime(2026, 8, 6, tzinfo=timezone.utc) + timedelta(seconds=1))
    changed_content = _entries(scope, contents=({"ordinal": 99}, *tuple({"ordinal": i} for i in range(2, 6))))
    assert _independent_state_hash(scope, early) == _independent_state_hash(scope, late)
    assert _independent_state_hash(scope, early) != _independent_state_hash(scope, changed_content)
    with closing(_connection(database_path)) as connection:
        first = _replace_first(connection, scope, early)
        first_manifest_hashes = tuple(
            row[0] for row in connection.execute("SELECT manifest_hash FROM derived_view_manifests ORDER BY view_id")
        )
        connection.execute("BEGIN")
        second = module.SQLiteDerivedViewStore(connection).replace_scope(
            scope,
            expected_generation=first.generation,
            expected_semantic_state_hash=first.semantic_state_hash,
            entries=late,
        )
        assert second.semantic_state_hash == first.semantic_state_hash
        assert tuple(
            row[0] for row in connection.execute("SELECT manifest_hash FROM derived_view_manifests ORDER BY view_id")
        ) != first_manifest_hashes
        connection.rollback()


def test_stored_rows_independently_match_canonical_bytes_and_all_hashes(
    database_path: Path,
) -> None:
    from amadeus_core.contracts.hashing import canonical_json
    from amadeus_core.storage.payloads import canonical_closed_json

    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        _replace_first(connection, scope, entries)
        rows = tuple(
            connection.execute(
                """
                SELECT manifests.view_id, manifests.manifest_json, manifests.manifest_hash,
                       manifests.content_hash AS manifest_content_hash,
                       contents.content_json, contents.content_hash AS content_content_hash
                FROM derived_view_manifests AS manifests
                JOIN derived_view_contents AS contents ON contents.view_id = manifests.view_id
                ORDER BY CASE manifests.view_type
                    WHEN 'summary' THEN 1
                    WHEN 'timeline' THEN 2
                    WHEN 'vector' THEN 3
                    WHEN 'fulltext' THEN 4
                    WHEN 'cue' THEN 5
                END
                """
            )
        )
        assert len(rows) == 5
        for entry, row in zip(entries, rows, strict=True):
            manifest_bytes = canonical_json(entry.manifest.model_dump(mode="python"))
            content_bytes = canonical_closed_json(entry.content)
            assert row["view_id"] == entry.manifest.view_id
            assert row["manifest_json"].encode("utf-8") == manifest_bytes
            assert row["content_json"].encode("utf-8") == content_bytes
            assert row["manifest_hash"] == hashlib.sha256(manifest_bytes).hexdigest()
            assert row["manifest_content_hash"] == hashlib.sha256(content_bytes).hexdigest()
            assert row["content_content_hash"] == hashlib.sha256(content_bytes).hexdigest()


def _assert_input_rejected_without_derived_dml(connection: sqlite3.Connection, scope, entries: object) -> None:
    module = _module()
    store = module.SQLiteDerivedViewStore(connection)
    before_counts = _derived_counts(connection)
    before_changes = connection.total_changes
    with pytest.raises(module.DerivedViewIntegrityError):
        store.replace_scope(
            scope,
            expected_generation=0,
            expected_semantic_state_hash=module.empty_derived_state_hash(scope),
            entries=entries,  # type: ignore[arg-type]
        )
    assert _derived_counts(connection) == before_counts
    assert connection.total_changes == before_changes


@pytest.mark.parametrize(
    ("label", "build"),
    (
        ("non_tuple", lambda scope, entries: list(entries)),
        ("four", lambda scope, entries: entries[:4]),
        ("six", lambda scope, entries: entries + entries[:1]),
        ("unordered", lambda scope, entries: (entries[1], entries[0], *entries[2:])),
        ("identity_mismatch", lambda scope, entries: (module_entry(entries[0], identity_id="idn-2"), *entries[1:])),
        ("branch_mismatch", lambda scope, entries: (module_entry(entries[0], branch_id="brn-2"), *entries[1:])),
        ("vault_mismatch", lambda scope, entries: (module_entry(entries[0], vault_id="vlt-2"), *entries[1:])),
        ("duplicate_view_id", lambda scope, entries: (entries[0], module_entry(entries[1], view_id=entries[0].manifest.view_id), *entries[2:])),
        ("watermark_mismatch", lambda scope, entries: (entries[0], module_entry(entries[1], source_watermark_seq=1), *entries[2:])),
        ("root_mismatch", lambda scope, entries: (entries[0], module_entry(entries[1], source_root_hash="f" * 64), *entries[2:])),
        ("builder_mismatch", lambda scope, entries: (entries[0], module_entry(entries[1], builder_version="builder-v2"), *entries[2:])),
    ),
)
def test_invalid_entry_shape_or_p1_mismatch_rejects_before_store_dml(
    database_path: Path,
    label: str,
    build: Callable[[Any, tuple[Any, ...]], object],
) -> None:
    del label
    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        connection.execute("BEGIN")
        _assert_input_rejected_without_derived_dml(connection, scope, build(scope, entries))
        connection.rollback()


def module_entry(entry, **updates: object):
    manifest = entry.manifest.model_copy(update=updates)
    return _module().DerivedViewEntry(manifest=manifest, content=entry.content)


@pytest.mark.parametrize(
    ("label", "bad_content"),
    (
        ("non_object", ["not", "an", "object"]),
        ("non_string_key", {1: "value"}),
        ("nan", {"number": float("nan")}),
        ("positive_infinity", {"number": float("inf")}),
        ("negative_infinity", {"number": float("-inf")}),
        ("forbidden_key_material", {"raw_key": "secret"}),
        ("unsupported_value", {"value": object()}),
        ("utf8_surrogate", {"text": "\ud800"}),
        ("nfc_key_collision", {"é": 1, "e\u0301": 2}),
    ),
)
def test_noncanonical_or_nonclosed_content_rejects_before_derived_dml(
    database_path: Path,
    label: str,
    bad_content: object,
) -> None:
    del label
    module = _module()
    scope = _scope()
    base = _entries(scope)
    with closing(_connection(database_path)) as connection:
        connection.execute("BEGIN")
        before_counts = _derived_counts(connection)
        before_changes = connection.total_changes
        try:
            bad_entry = module.DerivedViewEntry(manifest=base[0].manifest, content=bad_content)
        except Exception:
            pass
        else:
            with pytest.raises(module.DerivedViewIntegrityError):
                module.SQLiteDerivedViewStore(connection).replace_scope(
                    scope,
                    expected_generation=0,
                    expected_semantic_state_hash=module.empty_derived_state_hash(scope),
                    entries=(bad_entry, *base[1:]),
                )
        assert _derived_counts(connection) == before_counts
        assert connection.total_changes == before_changes
        connection.rollback()


def test_read_scope_none_and_success_roundtrip_are_exact(database_path: Path) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        store = module.SQLiteDerivedViewStore(connection)
        assert store.read_scope(scope) is None
        expected = _replace_first(connection, scope, entries)
        actual = store.read_scope(scope)
        assert actual == expected
        assert actual is not None
        assert actual.scope == scope
        assert actual.generation == 1
        assert actual.semantic_state_hash == _independent_state_hash(scope, entries)
        assert tuple(entry.manifest.view_type for entry in actual.entries) == _VIEW_TYPES
        assert actual.entries == entries


def test_second_replace_increments_generation_replaces_all_five_and_cleans_old_rows(
    database_path: Path,
) -> None:
    module = _module()
    scope = _scope()
    old_entries = _entries(scope)
    new_ids = tuple(f"viw-{index}-b" for index in range(1, 6))
    new_entries = _entries(
        scope,
        view_ids=new_ids,
        contents=tuple({"replacement": index} for index in range(1, 6)),
    )
    with closing(_connection(database_path)) as connection:
        first = _replace_first(connection, scope, old_entries)
        connection.execute("BEGIN")
        second = module.SQLiteDerivedViewStore(connection).replace_scope(
            scope,
            expected_generation=first.generation,
            expected_semantic_state_hash=first.semantic_state_hash,
            entries=new_entries,
        )
        connection.commit()
        assert second.generation == 2
        assert second.entries == new_entries
        assert _derived_counts(connection) == (1, 5, 5)
        ids = tuple(row[0] for row in connection.execute("""
            SELECT view_id FROM derived_view_manifests
            ORDER BY CASE view_type
                WHEN 'summary' THEN 1
                WHEN 'timeline' THEN 2
                WHEN 'vector' THEN 3
                WHEN 'fulltext' THEN 4
                WHEN 'cue' THEN 5
            END
        """))
        assert ids == new_ids
        assert set(old.manifest.view_id for old in old_entries).isdisjoint(ids)
        assert tuple(row[0] for row in connection.execute("SELECT view_id FROM derived_view_contents ORDER BY view_id")) == tuple(sorted(new_ids))


@pytest.mark.parametrize("stale_kind", ("generation", "hash"))
def test_stale_compare_and_swap_is_zero_derived_dml_with_trace_and_snapshot(
    database_path: Path,
    stale_kind: str,
) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        first = _replace_first(connection, scope, entries)
        before_rows = _derived_rows(connection)
        before_changes = connection.total_changes
        trace: list[str] = []
        connection.set_trace_callback(trace.append)
        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewCASConflict):
            module.SQLiteDerivedViewStore(connection).replace_scope(
                scope,
                expected_generation=0 if stale_kind == "generation" else first.generation,
                expected_semantic_state_hash=("f" * 64 if stale_kind == "hash" else first.semantic_state_hash),
                entries=entries,
            )
        connection.set_trace_callback(None)
        assert _derived_rows(connection) == before_rows
        assert connection.total_changes == before_changes
        assert not any(
            sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
            and "DERIVED_VIEW" in sql.upper()
            for sql in trace
        )
        connection.rollback()


def test_guard_update_rowcount_zero_maps_to_cas_and_keeps_snapshot(database_path: Path) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    replacement = _entries(scope, contents=tuple({"new": index} for index in range(1, 6)))
    with closing(_connection(database_path)) as connection:
        first = _replace_first(connection, scope, entries)
        before = _derived_rows(connection)
        guarded = _GuardUpdateZeroConnection(connection)
        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewCASConflict):
            module.SQLiteDerivedViewStore(guarded).replace_scope(
                scope,
                expected_generation=first.generation,
                expected_semantic_state_hash=first.semantic_state_hash,
                entries=replacement,
            )
        assert guarded.guard_update_seen is True
        assert _derived_rows(connection) == before
        assert connection.in_transaction is True
        connection.rollback()


def test_absent_scope_cross_scope_view_id_competition_is_integrity_not_cas(
    database_path: Path,
) -> None:
    module = _module()
    first_scope = _scope(suffix="1")
    second_scope = _scope(suffix="2")
    incumbent_entries = _entries(first_scope)
    competing_entries = _entries(second_scope)
    with closing(_connection(database_path)) as connection:
        _replace_first(connection, first_scope, incumbent_entries)
        incumbent = _derived_rows(connection)
        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewIntegrityError):
            module.SQLiteDerivedViewStore(connection).replace_scope(
                second_scope,
                expected_generation=0,
                expected_semantic_state_hash=module.empty_derived_state_hash(second_scope),
                entries=competing_entries,
            )
        assert _derived_rows(connection) == incumbent
        assert module.SQLiteDerivedViewStore(connection).read_scope(second_scope) is None
        assert connection.in_transaction is True
        connection.rollback()


@pytest.mark.parametrize("fail_at", (2, 3, 4))
def test_mid_insert_failure_rolls_back_all_replacement_writes_and_keeps_old_generation(
    database_path: Path,
    fail_at: int,
) -> None:
    module = _module()
    scope = _scope()
    initial_entries = _entries(scope)
    replacement = _entries(
        scope,
        view_ids=tuple(f"viw-{index}-c" for index in range(1, 6)),
        contents=tuple({"replacement": index} for index in range(1, 6)),
    )
    with closing(_connection(database_path)) as connection:
        first = _replace_first(connection, scope, initial_entries)
        before = _derived_rows(connection)
        failing = _FailNthContentInsertConnection(connection, fail_at=fail_at)
        connection.execute(
            "CREATE TEMP TABLE caller_owned_sentinel (marker TEXT NOT NULL)"
        )
        marker = f"mid-insert-{fail_at}"
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO caller_owned_sentinel (marker) VALUES (?)", (marker,)
        )
        with pytest.raises(module.DerivedViewIntegrityError):
            module.SQLiteDerivedViewStore(failing).replace_scope(
                scope,
                expected_generation=first.generation,
                expected_semantic_state_hash=first.semantic_state_hash,
                entries=replacement,
            )
        assert failing.content_inserts == fail_at
        assert _derived_rows(connection) == before
        assert connection.in_transaction is True
        assert tuple(
            row[0]
            for row in connection.execute(
                "SELECT marker FROM caller_owned_sentinel ORDER BY marker"
            )
        ) == (marker,)
        assert module.SQLiteDerivedViewStore(connection).read_scope(scope) == first
        connection.rollback()


@pytest.mark.parametrize("postwrite", ("raises", "none", "wrong_generation", "wrong_hash"))
def test_postwrite_verification_failure_rolls_back_savepoint_and_keeps_outer_transaction(
    database_path: Path,
    postwrite: str,
) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    candidate_hash = _independent_state_hash(scope, entries)
    with closing(_connection(database_path)) as connection:
        store = module.SQLiteDerivedViewStore(connection)
        calls = 0

        def postwrite_read(requested_scope):
            nonlocal calls
            calls += 1
            assert requested_scope == scope
            if calls == 1:
                return None
            if postwrite == "raises":
                raise module.DerivedViewIntegrityError()
            if postwrite == "none":
                return None
            return module.DerivedViewSnapshot(
                scope=scope,
                generation=2 if postwrite == "wrong_generation" else 1,
                semantic_state_hash=("f" * 64 if postwrite == "wrong_hash" else candidate_hash),
                entries=entries,
            )

        store.read_scope = postwrite_read  # type: ignore[method-assign]
        connection.execute(
            "CREATE TEMP TABLE caller_owned_sentinel (marker TEXT NOT NULL)"
        )
        marker = f"postwrite-{postwrite}"
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO caller_owned_sentinel (marker) VALUES (?)", (marker,)
        )
        before_changes = connection.total_changes
        with pytest.raises(module.DerivedViewIntegrityError):
            store.replace_scope(
                scope,
                expected_generation=0,
                expected_semantic_state_hash=module.empty_derived_state_hash(scope),
                entries=entries,
            )
        assert calls == 2
        assert _derived_counts(connection) == (0, 0, 0)
        assert connection.total_changes >= before_changes
        assert connection.in_transaction is True
        assert tuple(
            row[0]
            for row in connection.execute(
                "SELECT marker FROM caller_owned_sentinel ORDER BY marker"
            )
        ) == (marker,)
        assert module.SQLiteDerivedViewStore(connection).read_scope(scope) is None
        connection.rollback()


def _tamper_manifest_with_semantically_empty_whitespace(
    connection: sqlite3.Connection,
) -> None:
    canonical = connection.execute(
        "SELECT manifest_json FROM derived_view_manifests WHERE view_type = 'summary'"
    ).fetchone()[0]
    manifest = _contracts().MaterializedViewManifest.model_validate_json(canonical)
    tampered = f"\n\t{canonical}  \n"
    assert tampered != canonical
    assert _contracts().MaterializedViewManifest.model_validate_json(tampered) == manifest
    connection.execute(
        "UPDATE derived_view_manifests SET manifest_json = ? WHERE view_type = 'summary'",
        (tampered,),
    )


@pytest.mark.parametrize(
    ("tamper", "case"),
    (
        (lambda c: c.execute("DELETE FROM derived_view_manifests WHERE view_type = 'summary'"), "missing_manifest"),
        (lambda c: c.execute("DELETE FROM derived_view_contents WHERE view_id = 'viw-1'"), "missing_content"),
        (_tamper_manifest_with_semantically_empty_whitespace, "noncanonical_manifest"),
        (lambda c: c.execute("UPDATE derived_view_manifests SET manifest_json = replace(manifest_json, '\"identity_id\":\"idn-1\"', '\"identity_id\":\"idn-2\"') WHERE view_type = 'summary'"), "manifest_scope_cross_binding"),
        (lambda c: c.execute("UPDATE derived_view_manifests SET manifest_json = (SELECT manifest_json FROM derived_view_manifests WHERE view_type = 'timeline') WHERE view_type = 'summary'"), "manifest_type_view_id_cross_binding"),
        (lambda c: c.execute("UPDATE derived_view_manifests SET manifest_hash = ? WHERE view_type = 'summary'", ("f" * 64,)), "manifest_hash"),
        (lambda c: c.execute("UPDATE derived_view_manifests SET content_hash = ? WHERE view_type = 'summary'", ("f" * 64,)), "manifest_content_hash"),
        (lambda c: c.execute("UPDATE derived_view_contents SET content_json = '{\"ordinal\": 1}' WHERE view_id = 'viw-1'"), "noncanonical_content"),
        (lambda c: c.execute("UPDATE derived_view_contents SET content_json = '{\"ordinal\":1,\"ordinal\":1}' WHERE view_id = 'viw-1'"), "duplicate_content_key"),
        (lambda c: c.execute("UPDATE derived_view_contents SET content_hash = ? WHERE view_id = 'viw-1'", ("f" * 64,)), "content_hash"),
        (lambda c: c.execute("UPDATE derived_view_scopes SET semantic_state_hash = ?", ("f" * 64,)), "scope_state_hash"),
    ),
)
def test_read_tamper_matrix_unifies_to_derived_view_integrity_error(
    database_path: Path,
    tamper: Callable[[sqlite3.Connection], object],
    case: str,
) -> None:
    del case
    module = _module()
    scope = _scope()
    with closing(_connection(database_path)) as connection:
        _replace_first(connection, scope, _entries(scope))
        tamper(connection)
        with pytest.raises(module.DerivedViewIntegrityError):
            module.SQLiteDerivedViewStore(connection).read_scope(scope)


def test_derived_operations_leave_authority_ledger_receipt_and_schema_history_unchanged(
    database_path: Path,
) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    replacement = _entries(scope, contents=tuple({"new": index} for index in range(1, 6)))
    with closing(_connection(database_path)) as connection:
        before = _authority_ledger_receipt_history_schema(connection)
        first = _replace_first(connection, scope, entries)
        assert _authority_ledger_receipt_history_schema(connection) == before

        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewCASConflict):
            module.SQLiteDerivedViewStore(connection).replace_scope(
                scope,
                expected_generation=0,
                expected_semantic_state_hash=first.semantic_state_hash,
                entries=replacement,
            )
        assert _authority_ledger_receipt_history_schema(connection) == before
        connection.rollback()

        failing = _FailNthContentInsertConnection(connection, fail_at=2)
        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewIntegrityError):
            module.SQLiteDerivedViewStore(failing).replace_scope(
                scope,
                expected_generation=first.generation,
                expected_semantic_state_hash=first.semantic_state_hash,
                entries=replacement,
            )
        assert _authority_ledger_receipt_history_schema(connection) == before
        connection.rollback()

        store = module.SQLiteDerivedViewStore(connection)
        read_calls = 0
        original_read = store.read_scope

        def bad_postwrite(requested_scope):
            nonlocal read_calls
            read_calls += 1
            if read_calls == 1:
                return original_read(requested_scope)
            return None

        store.read_scope = bad_postwrite  # type: ignore[method-assign]
        connection.execute("BEGIN")
        with pytest.raises(module.DerivedViewIntegrityError):
            store.replace_scope(
                scope,
                expected_generation=first.generation,
                expected_semantic_state_hash=first.semantic_state_hash,
                entries=replacement,
            )
        assert _authority_ledger_receipt_history_schema(connection) == before
        connection.rollback()


def test_transaction_requirement_and_outer_transaction_ownership(database_path: Path) -> None:
    module = _module()
    scope = _scope()
    entries = _entries(scope)
    with closing(_connection(database_path)) as connection:
        store = module.SQLiteDerivedViewStore(connection)
        with pytest.raises(module.DerivedViewTransactionRequired):
            store.replace_scope(
                scope,
                expected_generation=0,
                expected_semantic_state_hash=module.empty_derived_state_hash(scope),
                entries=entries,
            )
        assert connection.in_transaction is False
        assert _derived_counts(connection) == (0, 0, 0)

        connection.execute("CREATE TEMP TABLE caller_writes (marker TEXT)")
        connection.execute("BEGIN")
        connection.execute("INSERT INTO caller_writes VALUES ('before-success')")
        snapshot = store.replace_scope(
            scope,
            expected_generation=0,
            expected_semantic_state_hash=module.empty_derived_state_hash(scope),
            entries=entries,
        )
        assert snapshot.generation == 1
        assert connection.in_transaction is True
        assert connection.execute("SELECT marker FROM caller_writes").fetchone()[0] == "before-success"
        connection.rollback()
        assert _derived_counts(connection) == (0, 0, 0)

        connection.execute("BEGIN")
        connection.execute("INSERT INTO caller_writes VALUES ('before-failure')")
        with pytest.raises(module.DerivedViewCASConflict):
            store.replace_scope(
                scope,
                expected_generation=1,
                expected_semantic_state_hash="f" * 64,
                entries=entries,
            )
        assert connection.in_transaction is True
        assert connection.execute("SELECT marker FROM caller_writes").fetchone()[0] == "before-failure"
        connection.rollback()
        assert connection.execute("SELECT count(*) FROM caller_writes").fetchone()[0] == 0
