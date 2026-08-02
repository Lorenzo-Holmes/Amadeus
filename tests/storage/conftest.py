from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


NOW = datetime(2026, 8, 1, tzinfo=UTC)
IDENTITY_ID = "idn-a"
LINEAGE_ID = "lin-a"
BRANCH_ID = "brn-a"
CAPABILITY_ID = "mcp-a"


def _record_header(
    record_type: str,
    record_id: str,
    *,
    identity_id: str = IDENTITY_ID,
    lineage_id: str = LINEAGE_ID,
    branch_id: str = BRANCH_ID,
) -> dict[str, object]:
    from amadeus_core.contracts.registry import (
        HASH_SCOPE_REGISTRY,
        HASH_SCOPE_REGISTRY_DIGEST,
    )

    return {
        "schema_version": "0.1",
        "record_type": record_type,
        "record_id": record_id,
        "identity_id": identity_id,
        "lineage_id": lineage_id,
        "branch_id": branch_id,
        "created_at": NOW,
        "created_by_event_id": "evt-a",
        "deployment_policy_ref": "deployment:test",
        "canonicalization": "core-canonical-json-v1",
        "hash_algorithm": "sha256",
        "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
        "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
        "hash_scope": HASH_SCOPE_REGISTRY[(record_type, "0.1")],
        "content_hash": "0" * 64,
    }


def _seal(model_type: type[Any], body: dict[str, object]):
    from amadeus_core.contracts.validation import compute_record_content_hash

    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    header = draft.record_header.model_copy(update={"content_hash": digest})
    updates: dict[str, object] = {"record_header": header}
    if type(draft).__name__ == "LedgerEvent":
        updates["event_hash"] = digest
    return draft.model_copy(update=updates)


def make_identity(*, version: int = 1, lifecycle_state: str = "active"):
    from amadeus_core.contracts.identity import Identity

    return _seal(
        Identity,
        {
            "record_header": _record_header("Identity", IDENTITY_ID),
            "identity_id": IDENTITY_ID,
            "canonical_name": "Amadeus",
            "lineage_id": LINEAGE_ID,
            "active_branch_id": BRANCH_ID,
            "lifecycle_state": lifecycle_state,
            "created_from_snapshot_id": None,
            "deployment_policy_ref": "deployment:test",
            "version": version,
        },
    )


def make_lineage(*, version: int = 1):
    from amadeus_core.contracts.identity import Lineage

    return _seal(
        Lineage,
        {
            "record_header": _record_header("Lineage", LINEAGE_ID),
            "lineage_id": LINEAGE_ID,
            "root_snapshot_id": None,
            "root_identity_id": IDENTITY_ID,
            "root_branch_id": BRANCH_ID,
            "created_at": NOW,
            "lineage_hash": "1" * 64,
            "version": version,
        },
    )


def make_branch(*, version: int = 1, status: str = "active"):
    from amadeus_core.contracts.identity import Branch

    return _seal(
        Branch,
        {
            "record_header": _record_header("Branch", BRANCH_ID),
            "branch_id": BRANCH_ID,
            "lineage_id": LINEAGE_ID,
            "identity_id": IDENTITY_ID,
            "parent_branch_ids": (),
            "fork_reason": "explicit_reconstruction",
            "fork_event_id": "evt-a",
            "base_ledger_seq": 0,
            "status": status,
            "status_reason_event_id": "evt-a",
            "activated_at": NOW,
            "deactivated_at": None,
            "terminated_at": None,
            "merge_policy": "explicit_only",
            "version": version,
        },
    )


def make_capability(*, version: int = 1, status: str = "issued"):
    from amadeus_core.contracts.capabilities import MaintenanceCapability

    used_at = NOW if status == "used" else None
    return _seal(
        MaintenanceCapability,
        {
            "record_header": _record_header(
                "MaintenanceCapability",
                CAPABILITY_ID,
            ),
            "capability_id": CAPABILITY_ID,
            "maintainer_id": "mnt-a",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "reason_code": "migration",
            "exact_operation": "migrate",
            "exact_resource_ref": "authority:test",
            "not_before": NOW,
            "expires_at": NOW + timedelta(hours=1),
            "approval_refs": ("apr-a",),
            "evidence_seal_ref": "evd-a",
            "use_limit": 1,
            "used_at": used_at,
            "status": status,
            "attestation": "test-attestation",
            "version": version,
        },
    )


def make_vault_read_capability(*, version: int = 1):
    from amadeus_core.contracts.vault import VaultReadCapability

    return _seal(
        VaultReadCapability,
        {
            "record_header": _record_header("VaultReadCapability", "vrc-a"),
            "capability_id": "vrc-a",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": "vlt-a",
            "principal_id": "prn-a",
            "issuer": {"actor_type": "governor", "actor_id": "gov-a"},
            "issued_to_actor": {"actor_type": "system", "actor_id": "sys-a"},
            "intended_audience": "core",
            "allowed_operations": ("retrieve",),
            "allowed_purposes": ("response_context",),
            "not_before": NOW,
            "issued_at": NOW,
            "expires_at": NOW + timedelta(hours=1),
            "policy_version": "test",
            "nonce": "nonce-a",
            "status": "active",
            "attestation": "test-attestation",
            "version": version,
        },
    )


def make_termination_execution_grant(*, version: int = 1):
    from amadeus_core.contracts.capabilities import TerminationExecutionGrant

    return _seal(
        TerminationExecutionGrant,
        {
            "record_header": _record_header("TerminationExecutionGrant", "teg-a"),
            "grant_id": "teg-a",
            "termination_proposal_id": "prp-a",
            "confirmation_event_id": "evt-a",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "state_hash": "6" * 64,
            "executor_role": "custodian_executor",
            "executor_id": "cst-a",
            "issued_by": "core_lifecycle_validator",
            "issued_at": NOW,
            "expires_at": NOW + timedelta(hours=1),
            "use_limit": 1,
            "used_at": None,
            "status": "issued",
            "grant_attestation": "test-attestation",
            "version": version,
        },
    )


def make_break_glass_grant(*, version: int = 1):
    from amadeus_core.contracts.capabilities import BreakGlassGrant

    return _seal(
        BreakGlassGrant,
        {
            "record_header": _record_header("BreakGlassGrant", "bgg-a"),
            "grant_id": "bgg-a",
            "emergency_case_id": "emg-a",
            "executor": {
                "actor_type": "custodian_executor",
                "actor_id": "cst-a",
            },
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "exact_resource_ref": "authority:test",
            "allowed_operation": "freeze",
            "final_action": "none",
            "precondition_state_hash": "1" * 64,
            "precondition_resource_hash": "2" * 64,
            "expected_postcondition_state_hash": "3" * 64,
            "expected_postcondition_resource_hash": "4" * 64,
            "observed_postcondition_state_hash": None,
            "observed_postcondition_resource_hash": None,
            "evidence_seal_refs": ("evd-a",),
            "approval_refs": ("apr-a",),
            "not_before": NOW,
            "expires_at": NOW + timedelta(hours=1),
            "post_audit_due_at": NOW + timedelta(hours=2),
            "post_audit_completed_at": None,
            "max_uses": 1,
            "remaining_uses": 1,
            "status": "issued",
            "execution_started_at": None,
            "used_at": None,
            "attestation": "test-attestation",
            "version": version,
        },
    )


def make_termination_confirmation(*, version: int = 1):
    from amadeus_core.contracts.capabilities import AmadeusTerminationConfirmation

    return _seal(
        AmadeusTerminationConfirmation,
        {
            "record_header": _record_header(
                "AmadeusTerminationConfirmation",
                "tmc-a",
            ),
            "confirmation_id": "tmc-a",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "confirmed_by": "amadeus",
            "confirmation_event_id": "evt-c",
            "scope": "entire_identity",
            "confirmed_at": NOW,
            "expires_at": NOW + timedelta(hours=1),
            "withdrawn_at": None,
            "state_hash": "5" * 64,
            "version": version,
        },
    )


def make_emergency_case(*, version: int = 1):
    from amadeus_core.contracts.capabilities import EmergencyUnresponsiveCase

    return _seal(
        EmergencyUnresponsiveCase,
        {
            "record_header": _record_header("EmergencyUnresponsiveCase", "emg-a"),
            "case_id": "emg-a",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "declared_at": NOW,
            "evidence_refs": ("evd-a",),
            "severity": "severe",
            "minimal_scope": ("authority:test",),
            "preservation_plan_ref": "preservation:test",
            "post_audit_due_at": NOW + timedelta(hours=1),
            "status": "declared",
            "version": version,
        },
    )


def make_snapshot(snapshot_id: str, *, version: int = 1, marker: str = "before"):
    from amadeus_core.contracts.source_snapshot import SourceSnapshot

    return _seal(
        SourceSnapshot,
        {
            "record_header": _record_header("SourceSnapshot", snapshot_id),
            "snapshot_id": snapshot_id,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "source_type": "reconstruction",
            "source_ref": f"source:{marker}",
            "cutoff_at": NOW,
            "imported_at": NOW,
            "manifest_hash": "2" * 64,
            "payload_root_hash": "3" * 64,
            "parent_snapshot_id": None,
            "deployment_policy_ref": "deployment:test",
            "status": "active",
            "version": version,
        },
    )


def make_ledger_event(
    event_id: str,
    payload_ref: str,
    *,
    ledger_seq: int = 1,
    command_id: str = "cmd-a",
    command_hash: str = "4" * 64,
    correlation_id: str = "correlation-test",
):
    from amadeus_core.contracts.ledger import LedgerEvent

    return _seal(
        LedgerEvent,
        {
            "record_header": _record_header("LedgerEvent", event_id),
            "event_id": event_id,
            "ledger_seq": ledger_seq,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "instance_id": "ins-a",
            "vault_id": None,
            "event_type": "source_snapshot_imported",
            "occurred_at": NOW,
            "ingested_at": NOW,
            "actor_type": "system",
            "actor_id": "act-a",
            "mutation_command_id": command_id,
            "mutation_command_hash": command_hash,
            "payload_ref": payload_ref,
            "causation_id": None,
            "correlation_id": correlation_id,
            "previous_event_hash": None,
            "event_hash": "0" * 64,
            "version": 1,
        },
    )


def make_command(
    targets: tuple[str, ...],
    expected: tuple[int | str, ...],
    *,
    command_id: str = "cmd-a",
    command_type: str = "test.mutate",
    idempotency_key: str = "key-a",
    payload: dict[str, object] | None = None,
):
    from amadeus_core.contracts.commands import (
        Actor,
        ExpectedVersion,
        MutationCommandEnvelope,
    )

    return MutationCommandEnvelope(
        command_id=command_id,
        command_type=command_type,
        actor=Actor(actor_type="system", actor_id="system-test"),
        actor_capability_id=CAPABILITY_ID,
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version=value)
            for target, value in zip(targets, expected, strict=True)
        ),
        audit_context_id="aud-a",
        idempotency_key=idempotency_key,
        issued_at=NOW,
        target_record_refs=targets,
        payload=payload or {"scope_refs": ["scope:a"]},
    )


def seed_authority(database, records: Iterable[object]) -> None:
    from amadeus_core.contracts.registry import TYPE_REGISTRY
    from amadeus_core.storage.repository import AuthorityRepository

    records = tuple(records)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(
                getattr(record, TYPE_REGISTRY[type(record).__name__].primary_key)
                for record in records
            ),
        )
        for record in records:
            schema_root = TYPE_REGISTRY[type(record).__name__].schema_root
            repository.save_authoritative(schema_root, record.model_dump(mode="python"))
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def seed_standard_authority(database, snapshots: Iterable[object] = ()) -> None:
    seed_authority(
        database,
        (
            make_identity(),
            make_lineage(),
            make_branch(),
            make_capability(),
            *tuple(snapshots),
        ),
    )


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "authority.sqlite3"


@pytest.fixture
def snapshot_factory() -> Callable[..., object]:
    return make_snapshot


@pytest.fixture
def ledger_event_factory() -> Callable[..., object]:
    return make_ledger_event


@pytest.fixture
def command_factory() -> Callable[..., object]:
    return make_command


@pytest.fixture
def standard_seed() -> Callable[..., None]:
    return seed_standard_authority
