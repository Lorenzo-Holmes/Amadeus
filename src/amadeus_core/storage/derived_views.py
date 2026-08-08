"""Transactional, non-authoritative storage for materialized derived views."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import hmac
import json
import sqlite3
from typing import Annotated

from pydantic import Field

from amadeus_core.contracts.common import FrozenModel, HashHex, RecordId
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.views import MaterializedViewManifest, RebuiltMaterializedViews
from .payloads import canonical_closed_json, closed_json_object


_VIEW_TYPES = ("summary", "timeline", "vector", "fulltext", "cue")
_LOWER_SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")


class DerivedViewScope(FrozenModel):
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId


class DerivedViewEntry(FrozenModel):
    manifest: MaterializedViewManifest
    content: Mapping[str, object]


class DerivedViewSnapshot(FrozenModel):
    scope: DerivedViewScope
    generation: Annotated[int, Field(strict=True, ge=1)]
    semantic_state_hash: HashHex
    entries: tuple[DerivedViewEntry, ...]


class DerivedViewCASConflict(RuntimeError):
    def __init__(self) -> None:
        super().__init__("derived-view compare-and-swap conflict")


class DerivedViewIntegrityError(ValueError):
    def __init__(self) -> None:
        super().__init__("derived-view integrity verification failed")


class DerivedViewTransactionRequired(RuntimeError):
    def __init__(self) -> None:
        super().__init__("replace_scope requires an active transaction")


def _scope_values(scope: DerivedViewScope) -> tuple[str, str, str, str]:
    if type(scope) is not DerivedViewScope:
        raise ValueError("derived view scope must be a DerivedViewScope")
    return scope.identity_id, scope.lineage_id, scope.branch_id, scope.vault_id


def _state_hash(scope: DerivedViewScope, entries: tuple[DerivedViewEntry, ...]) -> str:
    return sha256_hex(
        canonical_json(
            {
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
                        "content_hash": sha256_hex(canonical_closed_json(entry.content)),
                    }
                    for entry in entries
                ],
            }
        )
    )


def empty_derived_state_hash(scope: DerivedViewScope) -> str:
    """Return the canonical no-entry semantic-state hash for one scope."""

    _scope_values(scope)
    return _state_hash(scope, ())


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _decode_canonical_content(raw: str) -> Mapping[str, object]:
    decoded = json.loads(
        raw,
        parse_float=Decimal,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite,
    )
    content = closed_json_object(decoded)
    if canonical_closed_json(content) != raw.encode("utf-8"):
        raise ValueError("content JSON is not canonical")
    return content


def _entry_material(
    scope: DerivedViewScope,
    entries: tuple[DerivedViewEntry, ...],
) -> tuple[tuple[DerivedViewEntry, str, str, str, str], ...]:
    """Strictly validate all caller material before any store DML."""

    _scope_values(scope)
    if type(entries) is not tuple or len(entries) != len(_VIEW_TYPES):
        raise ValueError("entries must be an exact five-entry tuple")
    if any(type(entry) is not DerivedViewEntry for entry in entries):
        raise ValueError("entries must contain DerivedViewEntry values")
    if tuple(entry.manifest.view_type for entry in entries) != _VIEW_TYPES:
        raise ValueError("entries must use the canonical view-type order")
    view_ids = tuple(entry.manifest.view_id for entry in entries)
    if len(set(view_ids)) != len(view_ids):
        raise ValueError("view IDs must be unique")
    for entry in entries:
        manifest = entry.manifest
        if (
            manifest.identity_id != scope.identity_id
            or manifest.branch_id != scope.branch_id
            or manifest.vault_id != scope.vault_id
        ):
            raise ValueError("manifest scope does not match derived-view scope")
        if not isinstance(entry.content, Mapping):
            raise ValueError("derived-view content must be a JSON object")

    first = entries[0].manifest
    # Reuse the frozen P1 completeness/scope/watermark/root/builder validator exactly.
    RebuiltMaterializedViews(
        status="rebuilt",
        identity_id=scope.identity_id,
        lineage_id=scope.lineage_id,
        branch_id=scope.branch_id,
        vault_id=scope.vault_id,
        manifests=tuple(entry.manifest for entry in entries),
        source_watermark_seq=first.source_watermark_seq,
        source_root_hash=first.source_root_hash,
    )

    material: list[tuple[DerivedViewEntry, str, str, str, str]] = []
    for entry in entries:
        manifest_bytes = canonical_json(entry.manifest.model_dump(mode="python"))
        content_bytes = canonical_closed_json(entry.content)
        material.append(
            (
                entry,
                manifest_bytes.decode("utf-8"),
                sha256_hex(manifest_bytes),
                content_bytes.decode("utf-8"),
                sha256_hex(content_bytes),
            )
        )
    return tuple(material)


def _rollback_savepoint(connection: sqlite3.Connection) -> None:
    connection.execute("ROLLBACK TO derived_view_replace")
    connection.execute("RELEASE derived_view_replace")


class SQLiteDerivedViewStore:
    """CAS replacement store for reconstructable view data only."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def read_scope(self, scope: DerivedViewScope) -> DerivedViewSnapshot | None:
        try:
            identity_id, lineage_id, branch_id, vault_id = _scope_values(scope)
            rows = self._connection.execute(
                """
                SELECT
                    scopes.generation,
                    scopes.semantic_state_hash,
                    manifests.view_type,
                    manifests.view_id,
                    manifests.manifest_json,
                    manifests.manifest_hash,
                    manifests.content_hash AS manifest_content_hash,
                    contents.content_json,
                    contents.content_hash AS content_content_hash
                FROM derived_view_scopes AS scopes
                LEFT JOIN derived_view_manifests AS manifests
                  ON manifests.identity_id = scopes.identity_id
                 AND manifests.lineage_id = scopes.lineage_id
                 AND manifests.branch_id = scopes.branch_id
                 AND manifests.vault_id = scopes.vault_id
                LEFT JOIN derived_view_contents AS contents
                  ON contents.view_id = manifests.view_id
                WHERE scopes.identity_id = ?
                  AND scopes.lineage_id = ?
                  AND scopes.branch_id = ?
                  AND scopes.vault_id = ?
                ORDER BY CASE manifests.view_type
                    WHEN 'summary' THEN 1
                    WHEN 'timeline' THEN 2
                    WHEN 'vector' THEN 3
                    WHEN 'fulltext' THEN 4
                    WHEN 'cue' THEN 5
                    ELSE 6
                END
                """,
                (identity_id, lineage_id, branch_id, vault_id),
            ).fetchall()
            if not rows:
                return None
            if len(rows) != len(_VIEW_TYPES):
                raise ValueError("scope does not contain exactly five manifests")
            generation = rows[0]["generation"]
            state_hash = rows[0]["semantic_state_hash"]
            if type(generation) is not int or generation < 1:
                raise ValueError("invalid derived-view generation")
            if not isinstance(state_hash, str) or _LOWER_SHA256.fullmatch(state_hash) is None:
                raise ValueError("invalid semantic state hash")

            entries: list[DerivedViewEntry] = []
            for index, row in enumerate(rows):
                if row["view_type"] != _VIEW_TYPES[index]:
                    raise ValueError("manifest types are incomplete or unordered")
                raw_manifest = row["manifest_json"]
                raw_content = row["content_json"]
                if not isinstance(raw_manifest, str) or not isinstance(raw_content, str):
                    raise ValueError("manifest or content row is missing")
                manifest = MaterializedViewManifest.model_validate_json(raw_manifest)
                manifest_bytes = canonical_json(manifest.model_dump(mode="python"))
                if manifest_bytes != raw_manifest.encode("utf-8"):
                    raise ValueError("manifest JSON is not canonical")
                if (
                    manifest.view_type != _VIEW_TYPES[index]
                    or manifest.identity_id != scope.identity_id
                    or manifest.branch_id != scope.branch_id
                    or manifest.vault_id != scope.vault_id
                    or manifest.view_id != row["view_id"]
                ):
                    raise ValueError("stored manifest scope is invalid")
                content = _decode_canonical_content(raw_content)
                manifest_hash = sha256_hex(manifest_bytes)
                content_hash = sha256_hex(canonical_closed_json(content))
                if (
                    row["manifest_hash"] != manifest_hash
                    or row["manifest_content_hash"] != content_hash
                    or row["content_content_hash"] != content_hash
                ):
                    raise ValueError("stored derived-view hash is invalid")
                entries.append(DerivedViewEntry(manifest=manifest, content=content))

            snapshot = DerivedViewSnapshot(
                scope=scope,
                generation=generation,
                semantic_state_hash=state_hash,
                entries=tuple(entries),
            )
            if not hmac.compare_digest(snapshot.semantic_state_hash, _state_hash(scope, snapshot.entries)):
                raise ValueError("stored derived-view state hash is invalid")
            return snapshot
        except DerivedViewIntegrityError:
            raise
        except Exception as error:
            raise DerivedViewIntegrityError() from error

    def replace_scope(
        self,
        scope: DerivedViewScope,
        *,
        expected_generation: int,
        expected_semantic_state_hash: str,
        entries: tuple[DerivedViewEntry, ...],
    ) -> DerivedViewSnapshot:
        if self._connection.in_transaction is not True:
            raise DerivedViewTransactionRequired()
        try:
            if type(expected_generation) is not int or expected_generation < 0:
                raise ValueError("expected generation must be a non-negative built-in int")
            if (
                not isinstance(expected_semantic_state_hash, str)
                or _LOWER_SHA256.fullmatch(expected_semantic_state_hash) is None
            ):
                raise ValueError("expected semantic state hash must be lowercase SHA-256")
            material = _entry_material(scope, entries)
            candidate_hash = _state_hash(scope, entries)
            current = self.read_scope(scope)
            if current is None:
                current_generation = 0
                current_hash = empty_derived_state_hash(scope)
            else:
                current_generation = current.generation
                current_hash = current.semantic_state_hash
            if (
                expected_generation != current_generation
                or not hmac.compare_digest(expected_semantic_state_hash, current_hash)
            ):
                raise DerivedViewCASConflict()

            self._connection.execute("SAVEPOINT derived_view_replace")
            try:
                scope_values = _scope_values(scope)
                if current is None:
                    self._connection.execute(
                        """
                        INSERT INTO derived_view_scopes (
                            identity_id, lineage_id, branch_id, vault_id,
                            generation, semantic_state_hash
                        ) VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (*scope_values, candidate_hash),
                    )
                else:
                    updated = self._connection.execute(
                        """
                        UPDATE derived_view_scopes
                        SET generation = ?, semantic_state_hash = ?
                        WHERE identity_id = ? AND lineage_id = ?
                          AND branch_id = ? AND vault_id = ?
                          AND generation = ? AND semantic_state_hash = ?
                        """,
                        (
                            current_generation + 1,
                            candidate_hash,
                            *scope_values,
                            current_generation,
                            current_hash,
                        ),
                    )
                    if updated.rowcount != 1:
                        raise DerivedViewCASConflict()
                    self._connection.execute(
                        """
                        DELETE FROM derived_view_manifests
                        WHERE identity_id = ? AND lineage_id = ?
                          AND branch_id = ? AND vault_id = ?
                        """,
                        scope_values,
                    )

                for entry, manifest_json, manifest_hash, content_json, content_hash in material:
                    manifest = entry.manifest
                    self._connection.execute(
                        """
                        INSERT INTO derived_view_manifests (
                            identity_id, lineage_id, branch_id, vault_id, view_type,
                            view_id, manifest_json, manifest_hash, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (*scope_values, manifest.view_type, manifest.view_id, manifest_json, manifest_hash, content_hash),
                    )
                    self._connection.execute(
                        """
                        INSERT INTO derived_view_contents (view_id, content_json, content_hash)
                        VALUES (?, ?, ?)
                        """,
                        (manifest.view_id, content_json, content_hash),
                    )
                result = self.read_scope(scope)
                if (
                    result is None
                    or result.generation != current_generation + 1
                    or not hmac.compare_digest(result.semantic_state_hash, candidate_hash)
                ):
                    raise DerivedViewIntegrityError()
                self._connection.execute("RELEASE derived_view_replace")
            except (DerivedViewCASConflict, DerivedViewIntegrityError):
                _rollback_savepoint(self._connection)
                raise
            except sqlite3.IntegrityError as error:
                _rollback_savepoint(self._connection)
                if current is None and "derived_view_scopes" in str(error):
                    raise DerivedViewCASConflict() from error
                raise DerivedViewIntegrityError() from error
            except Exception as error:
                _rollback_savepoint(self._connection)
                raise DerivedViewIntegrityError() from error

            return result
        except (DerivedViewCASConflict, DerivedViewTransactionRequired, DerivedViewIntegrityError):
            raise
        except Exception as error:
            raise DerivedViewIntegrityError() from error


__all__ = [
    "DerivedViewScope",
    "DerivedViewEntry",
    "DerivedViewSnapshot",
    "DerivedViewCASConflict",
    "DerivedViewIntegrityError",
    "DerivedViewTransactionRequired",
    "empty_derived_state_hash",
    "SQLiteDerivedViewStore",
]
