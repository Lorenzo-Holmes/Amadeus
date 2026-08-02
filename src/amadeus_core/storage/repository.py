"""Transaction-bound repository for authoritative Core records."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime

from amadeus_core.contracts import validation as contract_validation
from amadeus_core.contracts.commands import CommandExecutionContext
from amadeus_core.contracts.common import FrozenModel
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json
from amadeus_core.contracts.registry import AUTHORITATIVE_MODELS, TYPE_REGISTRY

from .payloads import (
    StoredLedgerPayload,
    _load_closed_json,
    closed_json_object,
    prepare_inline_payload,
    validate_authority_bound_payload,
)
from ._records import _SESSION_LEDGER_EVENT_TYPES


_CAPABILITY_TYPE_BY_RECORD = {
    "VaultReadCapability": "vault_read",
    "MaintenanceCapability": "maintenance",
    "TerminationExecutionGrant": "termination_execution",
    "BreakGlassGrant": "break_glass",
}
_CAPABILITY_RECORD_TYPES = frozenset(_CAPABILITY_TYPE_BY_RECORD)


def _datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


class AuthorityRepository:
    """All methods use the caller's already-open transaction snapshot."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        allowed_target_refs: Iterable[str] | None = None,
        actor_capability_id: str | None = None,
        execution_context: CommandExecutionContext | None = None,
    ) -> None:
        self._connection = connection
        self._allowed_target_refs = frozenset(
            () if allowed_target_refs is None else allowed_target_refs
        )
        self._actor_capability_id = actor_capability_id
        self._execution_context = execution_context
        self._event_ids: list[str] = []
        self._version_snapshot: dict[str, tuple[int, str | None]] | None = None
        self._written_target_refs: set[str] = set()

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(self._event_ids)

    def get_current_versions(
        self,
        target_record_refs: Iterable[str],
    ) -> dict[str, int]:
        targets = tuple(target_record_refs)
        if not targets:
            return {}
        placeholders = ",".join("?" for _ in targets)
        rows = self._connection.execute(
            f"""
            SELECT record_id, version, record_type
            FROM authority_records
            WHERE record_id IN ({placeholders})
            """,
            targets,
        ).fetchall()
        present = {
            row["record_id"]: (row["version"], row["record_type"])
            for row in rows
        }
        self._version_snapshot = {
            target: present.get(target, (0, None)) for target in targets
        }
        return {
            target: version
            for target, (version, _record_type) in self._version_snapshot.items()
        }

    def get(self, record_id: str) -> FrozenModel | None:
        row = self._connection.execute(
            """
            SELECT record_type, content_json
            FROM authority_records
            WHERE record_id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        model = AUTHORITATIVE_MODELS[row["record_type"]]
        return model.model_validate_json(row["content_json"])

    def get_validated(self, record_id: str) -> FrozenModel | None:
        """Load one authority and verify its row metadata and core projection."""

        row = self._connection.execute(
            """
            SELECT
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
            FROM authority_records
            WHERE record_id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        record_type = row["record_type"]
        model = AUTHORITATIVE_MODELS.get(record_type)
        spec = TYPE_REGISTRY.get(record_type)
        if model is None or spec is None:
            raise CoreContractViolation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        parsed = model.model_validate_json(row["content_json"])
        record = contract_validation.validate_authoritative_record(
            spec.schema_root,
            parsed.model_dump(mode="python"),
        )
        canonical_content = canonical_json(record.model_dump(mode="python")).decode(
            "utf-8"
        )
        if (
            row["content_json"] != canonical_content
            or row["content_hash"] != record.record_header.content_hash
        ):
            raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)
        if (
            row["record_id"] != getattr(record, spec.primary_key)
            or row["record_type"] != type(record).__name__
            or row["schema_version"] != record.record_header.schema_version
            or row["identity_id"] != record.record_header.identity_id
            or row["lineage_id"] != record.record_header.lineage_id
            or row["branch_id"] != record.record_header.branch_id
            or row["version"] != record.version
            or row["created_at"] != _datetime_text(record.record_header.created_at)
        ):
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        self._assert_core_projection_matches(record)
        return record

    def _assert_core_projection_matches(self, record: FrozenModel) -> None:
        record_type = type(record).__name__
        if record_type == "Identity":
            row = self._connection.execute(
                """
                SELECT identity_id, lifecycle_state, active_branch_id, version
                FROM identities
                WHERE identity_id = ?
                """,
                (record.identity_id,),
            ).fetchone()
            if row is None or row["active_branch_id"] != record.active_branch_id:
                raise CoreContractViolation(CoreErrorCode.ACTIVE_BRANCH_INVARIANT)
            if tuple(row) != (
                record.identity_id,
                record.lifecycle_state,
                record.active_branch_id,
                record.version,
            ):
                raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        elif record_type == "Lineage":
            row = self._connection.execute(
                """
                SELECT
                    lineage_id,
                    root_identity_id,
                    root_branch_id,
                    root_snapshot_id,
                    version
                FROM lineages
                WHERE lineage_id = ?
                """,
                (record.lineage_id,),
            ).fetchone()
            if row is None or tuple(row) != (
                record.lineage_id,
                record.root_identity_id,
                record.root_branch_id,
                record.root_snapshot_id,
                record.version,
            ):
                raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        elif record_type == "Branch":
            row = self._connection.execute(
                """
                SELECT branch_id, identity_id, lineage_id, status, version
                FROM branches
                WHERE branch_id = ?
                """,
                (record.branch_id,),
            ).fetchone()
            if row is None or row["status"] != record.status:
                code = (
                    CoreErrorCode.ACTIVE_BRANCH_INVARIANT
                    if record.status == "active"
                    or (row is not None and row["status"] == "active")
                    else CoreErrorCode.HEADER_BODY_MISMATCH
                )
                raise CoreContractViolation(code)
            if tuple(row) != (
                record.branch_id,
                record.identity_id,
                record.lineage_id,
                record.status,
                record.version,
            ):
                raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)

    def count_active_branches(self, identity_id: str) -> int:
        row = self._connection.execute(
            """
            SELECT count(*)
            FROM branches
            WHERE identity_id = ? AND status = 'active'
            """,
            (identity_id,),
        ).fetchone()
        return int(row[0])

    def save_authoritative(
        self,
        schema_root: str,
        body: Mapping[str, object],
    ) -> FrozenModel:
        record = contract_validation.validate_authoritative_record(schema_root, body)
        if type(record).__name__ == "LedgerEvent":
            raise TypeError("LedgerEvent must be appended with append_ledger_event")
        self._store_authority(record)
        self._store_projection(record)
        return record

    def append_ledger_event(
        self,
        body: Mapping[str, object],
        *,
        payload: Mapping[str, object] | StoredLedgerPayload,
    ) -> FrozenModel:
        record = contract_validation.validate_authoritative_record("event", body)
        if type(record).__name__ != "LedgerEvent":
            raise CoreContractViolation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        context = self._execution_context
        if context is None or (
            record.mutation_command_id,
            record.mutation_command_hash,
        ) != (
            context.command_id,
            context.command_hash,
        ):
            raise ValueError("Ledger event does not match command execution context")
        stored_payload = validate_authority_bound_payload(
            payload
            if isinstance(payload, StoredLedgerPayload)
            else prepare_inline_payload(payload),
            record.payload_ref,
        )
        if record.event_type in _SESSION_LEDGER_EVENT_TYPES:
            if stored_payload.mode != "inline" or stored_payload.inline_json is None:
                raise ValueError("Session Ledger event payload must be inline")
            inline_payload = closed_json_object(
                _load_closed_json(stored_payload.inline_json)
            )
            session_id = inline_payload.get("session_id")
            if (
                not isinstance(session_id, str)
                or not session_id.strip()
                or record.correlation_id != session_id
            ):
                raise ValueError("Session Ledger correlation does not match payload")
        elif record.correlation_id != context.audit_context_id:
            raise ValueError("Ledger event does not match command execution context")

        self._store_authority(record)
        self._connection.execute(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.event_id,
                record.branch_id,
                record.ledger_seq,
                record.previous_event_hash,
                record.event_hash,
                stored_payload.payload_ref,
                stored_payload.mode,
                stored_payload.inline_json,
                stored_payload.external_ref,
                stored_payload.payload_hash,
                stored_payload.media_type,
            ),
        )
        self._event_ids.append(record.event_id)
        return record

    def consume_capability(self, capability_id: str) -> None:
        self._assert_target_allowed(capability_id)
        if (
            self._actor_capability_id is not None
            and capability_id != self._actor_capability_id
        ):
            raise CoreContractViolation(CoreErrorCode.MAINTENANCE_SCOPE_EXCEEDED)
        self._claim_target_write(capability_id)
        cursor = self._connection.execute(
            """
            UPDATE capabilities
            SET remaining_uses = remaining_uses - 1
            WHERE capability_id = ? AND remaining_uses > 0
            """,
            (capability_id,),
        )
        if cursor.rowcount != 1:
            raise CoreContractViolation(CoreErrorCode.MAINTENANCE_CAPABILITY_CONSUMED)

    def _assert_target_allowed(self, record_id: str) -> None:
        if record_id not in self._allowed_target_refs:
            raise CoreContractViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)

    def _claim_target_write(self, record_id: str) -> None:
        if record_id in self._written_target_refs:
            raise CoreContractViolation(CoreErrorCode.STALE_VERSION)
        self._written_target_refs.add(record_id)

    def _store_authority(self, record: FrozenModel) -> None:
        record_type = type(record).__name__
        spec = TYPE_REGISTRY[record_type]
        record_id = getattr(record, spec.primary_key)
        self._assert_target_allowed(record_id)
        self._claim_target_write(record_id)
        if self._version_snapshot is not None and record_id in self._version_snapshot:
            existing_version, existing_record_type = self._version_snapshot[record_id]
        else:
            existing = self._connection.execute(
                """
                SELECT record_type, version
                FROM authority_records
                WHERE record_id = ?
                """,
                (record_id,),
            ).fetchone()
            if existing is None:
                existing_version, existing_record_type = 0, None
            else:
                existing_version = existing["version"]
                existing_record_type = existing["record_type"]
        version = record.version
        content_json = canonical_json(record.model_dump(mode="python")).decode("utf-8")
        header = record.record_header
        values = (
            record_type,
            header.schema_version,
            header.identity_id,
            header.lineage_id,
            header.branch_id,
            version,
            content_json,
            header.content_hash,
            _datetime_text(header.created_at),
            record_id,
        )
        if existing_version == 0:
            if version != 1:
                raise CoreContractViolation(CoreErrorCode.STALE_VERSION)
            self._connection.execute(
                """
                INSERT INTO authority_records (
                    record_type,
                    schema_version,
                    identity_id,
                    lineage_id,
                    branch_id,
                    version,
                    content_json,
                    content_hash,
                    created_at,
                    record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return
        if existing_record_type != record_type:
            raise CoreContractViolation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        if record_type == "LedgerEvent":
            raise CoreContractViolation(CoreErrorCode.LEDGER_IMMUTABLE)
        if version != existing_version + 1:
            raise CoreContractViolation(CoreErrorCode.STALE_VERSION)
        self._connection.execute(
            """
            UPDATE authority_records
            SET
                record_type = ?,
                schema_version = ?,
                identity_id = ?,
                lineage_id = ?,
                branch_id = ?,
                version = ?,
                content_json = ?,
                content_hash = ?,
                created_at = ?
            WHERE record_id = ?
            """,
            values,
        )

    def _store_projection(self, record: FrozenModel) -> None:
        record_type = type(record).__name__
        if record_type == "Identity":
            self._connection.execute(
                """
                INSERT INTO identities (
                    identity_id, lifecycle_state, active_branch_id, version
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(identity_id) DO UPDATE SET
                    lifecycle_state = excluded.lifecycle_state,
                    active_branch_id = excluded.active_branch_id,
                    version = excluded.version
                """,
                (
                    record.identity_id,
                    record.lifecycle_state,
                    record.active_branch_id,
                    record.version,
                ),
            )
        elif record_type == "Lineage":
            self._connection.execute(
                """
                INSERT INTO lineages (
                    lineage_id,
                    root_identity_id,
                    root_branch_id,
                    root_snapshot_id,
                    version
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lineage_id) DO UPDATE SET
                    root_identity_id = excluded.root_identity_id,
                    root_branch_id = excluded.root_branch_id,
                    root_snapshot_id = excluded.root_snapshot_id,
                    version = excluded.version
                """,
                (
                    record.lineage_id,
                    record.root_identity_id,
                    record.root_branch_id,
                    record.root_snapshot_id,
                    record.version,
                ),
            )
        elif record_type == "Branch":
            self._connection.execute(
                """
                INSERT INTO branches (
                    branch_id, identity_id, lineage_id, status, version
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(branch_id) DO UPDATE SET
                    identity_id = excluded.identity_id,
                    lineage_id = excluded.lineage_id,
                    status = excluded.status,
                    version = excluded.version
                """,
                (
                    record.branch_id,
                    record.identity_id,
                    record.lineage_id,
                    record.status,
                    record.version,
                ),
            )
        elif record_type == "RelationshipVault":
            self._connection.execute(
                """
                INSERT INTO relationship_vaults (
                    vault_id, identity_id, branch_id, status, version
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vault_id) DO UPDATE SET
                    identity_id = excluded.identity_id,
                    branch_id = excluded.branch_id,
                    status = excluded.status,
                    version = excluded.version
                """,
                (
                    record.vault_id,
                    record.identity_id,
                    record.branch_id,
                    record.status,
                    record.version,
                ),
            )
        elif record_type == "Proposal":
            self._connection.execute(
                """
                INSERT INTO proposals (
                    proposal_id,
                    identity_id,
                    branch_id,
                    status,
                    expires_at,
                    version
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    identity_id = excluded.identity_id,
                    branch_id = excluded.branch_id,
                    status = excluded.status,
                    expires_at = excluded.expires_at,
                    version = excluded.version
                """,
                (
                    record.proposal_id,
                    record.identity_id,
                    record.branch_id,
                    record.status,
                    _datetime_text(record.expires_at),
                    record.version,
                ),
            )
        elif record_type == "GovernorDecision":
            self._connection.execute(
                """
                INSERT INTO governor_decisions (
                    decision_id, proposal_id, result, version
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    proposal_id = excluded.proposal_id,
                    result = excluded.result,
                    version = excluded.version
                """,
                (
                    record.decision_id,
                    record.proposal_id,
                    record.result,
                    record.version,
                ),
            )
        elif record_type in _CAPABILITY_RECORD_TYPES:
            capability_id = getattr(
                record,
                TYPE_REGISTRY[record_type].primary_key,
            )
            used_at = getattr(record, "used_at", None)
            if hasattr(record, "remaining_uses"):
                remaining_uses = record.remaining_uses
            elif hasattr(record, "use_limit"):
                remaining_uses = 0 if used_at is not None else record.use_limit
            else:
                remaining_uses = None
            if hasattr(record, "status"):
                status = record.status
            else:
                status = "withdrawn" if record.withdrawn_at is not None else "active"
            self._connection.execute(
                """
                INSERT INTO capabilities (
                    capability_id,
                    capability_type,
                    identity_id,
                    branch_id,
                    status,
                    expires_at,
                    remaining_uses,
                    version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capability_id) DO UPDATE SET
                    capability_type = excluded.capability_type,
                    identity_id = excluded.identity_id,
                    branch_id = excluded.branch_id,
                    status = excluded.status,
                    expires_at = excluded.expires_at,
                    remaining_uses = excluded.remaining_uses,
                    version = excluded.version
                """,
                (
                    capability_id,
                    _CAPABILITY_TYPE_BY_RECORD[record_type],
                    record.record_header.identity_id,
                    record.record_header.branch_id,
                    status,
                    _datetime_text(getattr(record, "expires_at", None)),
                    remaining_uses,
                    record.version,
                ),
            )


__all__ = ["AuthorityRepository"]
