from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from amadeus_core.contracts.commands import (
    Actor,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.vault import RelationshipVault
from amadeus_core.storage.records import record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository


IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
INSTANCE_ID = "ins-a1"
VAULT_ID = "vlt-a1"
OTHER_VAULT_ID = "vlt-b1"
DEPLOYMENT_POLICY_REF = "deployment:test"
LLM_ID = "llm-a1"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


def _database_snapshot(database) -> tuple[object, ...]:
    connection = database.connect()
    try:
        tables = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        )
        return tuple(
            (
                table,
                tuple(
                    tuple(row)
                    for row in connection.execute(
                        f'SELECT * FROM "{table}" ORDER BY rowid'
                    ).fetchall()
                ),
            )
            for table in tables
        )
    finally:
        connection.close()


def _header(record_type: str, record_id: str, *, created_at, event_id: str):
    return record_header(
        record_type,
        record_id,
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        created_at=created_at,
        created_by_event_id=event_id,
        deployment_policy_ref=DEPLOYMENT_POLICY_REF,
    )


def _seed_other_vault_memory(database, *, now) -> str:
    memory_id = "mem-b1"
    vault = seal_record(
        RelationshipVault,
        {
            "record_header": _header(
                "RelationshipVault",
                OTHER_VAULT_ID,
                created_at=now,
                event_id=GENESIS_EVENT_ID,
            ),
            "vault_id": OTHER_VAULT_ID,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "relationship_principal_id": "usr-b1",
            "status": "active",
            "visibility_policy_ref": "visibility:test-other",
            "created_at": now,
            "version": 1,
        },
    )
    memory = seal_record(
        AutobiographicalMemory,
        {
            "record_header": _header(
                "AutobiographicalMemory",
                memory_id,
                created_at=now,
                event_id=GENESIS_EVENT_ID,
            ),
            "memory_id": memory_id,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "governing_vault_id": OTHER_VAULT_ID,
            "semantic_kind": "relationship",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {
                "mode": "restricted",
                "reason_refs": (GENESIS_EVENT_ID,),
            },
            "evidence_event_refs": (GENESIS_EVENT_ID,),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
            "governor_decision_id": "gvd-b1",
            "semantic_version": 1,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        },
    )
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(OTHER_VAULT_ID, memory_id),
        )
        repository.save_authoritative(
            "relationship_vault",
            vault.model_dump(mode="python"),
        )
        repository.save_authoritative(
            "autobiographical_memory",
            memory.model_dump(mode="python"),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    return memory_id


@pytest.mark.parametrize(
    ("target_kind", "expected_code"),
    (
        ("cross_vault_memory", CoreErrorCode.VAULT_SCOPE_MISMATCH),
        ("identity", CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH),
    ),
    ids=("memory-governing-vault", "illegal-identity-type"),
)
def test_request_submit_rejects_wrong_vault_or_disallowed_target_type_without_writes(
    database,
    request_service,
    request_factory,
    request_command_factory,
    target_kind: str,
    expected_code: CoreErrorCode,
) -> None:
    request = request_factory(
        "correction_request",
        request_id="req-d1",
        event_id="evt-d1",
    )
    if target_kind == "cross_vault_memory":
        target_ref = _seed_other_vault_memory(
            database,
            now=request.submitted_at,
        )
    else:
        target_ref = IDENTITY_ID
    rebound = reseal_update(request, {"target_refs": (target_ref,)})
    assert isinstance(rebound, MemoryRequest)
    command = request_command_factory(rebound, event_id="evt-d1")
    before = _database_snapshot(database)

    result = request_service.submit(command, rebound)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == expected_code
    assert _database_snapshot(database) == before


def _change_expression_policy_proposal(*, now) -> Proposal:
    proposal = seal_record(
        Proposal,
        {
            "record_header": _header(
                "Proposal",
                "prp-d2",
                created_at=now,
                event_id="evt-d2",
            ),
            "proposal_id": "prp-d2",
            "proposal_type": "change_expression_policy",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": LLM_ID},
            "target_refs": (GENESIS_EVENT_ID,),
            "evidence_refs": (GENESIS_EVENT_ID,),
            "proposed_patch": {
                "expression_policy": {
                    "mode": "non_mention",
                    "reason_refs": (GENESIS_EVENT_ID,),
                }
            },
            "created_at": now,
            "expires_at": now + timedelta(days=1),
            "status": "pending",
            "deferred_at": None,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": None,
            },
            "reopened_count": 0,
            "version": 1,
        },
    )
    assert isinstance(proposal, Proposal)
    return proposal


def _submit_proposal_command(proposal: Proposal) -> MutationCommandEnvelope:
    event_id = proposal.record_header.created_by_event_id
    targets = (proposal.proposal_id, event_id)
    return MutationCommandEnvelope(
        command_id="cmd-d2",
        command_type="memory_proposal.submit",
        actor=Actor(actor_type="llm", actor_id=LLM_ID),
        actor_capability_id="cap-d2",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-d2",
        idempotency_key="idem-d2",
        issued_at=proposal.created_at,
        target_record_refs=targets,
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                *proposal.target_refs,
                *proposal.evidence_refs,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            "semantic_input_hash": sha256_hex(
                canonical_json(proposal.model_dump(mode="python"))
            ),
        },
    )


def test_change_expression_policy_rejects_non_memory_target_without_writes(
    database,
) -> None:
    from amadeus_core.governance.proposal_service import ProposalService

    proposal_service = ProposalService(database, clock=_FixedClock(NOW))
    proposal = _change_expression_policy_proposal(now=NOW)
    command = _submit_proposal_command(proposal)
    before = _database_snapshot(database)

    result = proposal_service.submit(command, proposal)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH
    assert _database_snapshot(database) == before


def _seed_deferred_lifecycle_proposal(database) -> Proposal:
    base = _change_expression_policy_proposal(now=NOW)
    proposal = reseal_update(
        base,
        {
            "proposal_type": "lifecycle_transition",
            "target_refs": (IDENTITY_ID,),
            "proposed_patch": {"requested_action": "maintenance_paused"},
            "status": "deferred",
            "deferred_at": NOW,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": NOW,
            },
        },
    )
    assert isinstance(proposal, Proposal)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(proposal.proposal_id,),
        ).save_authoritative(
            "proposal",
            proposal.model_dump(mode="python"),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    return proposal


def _disable_proposal_binding(database, binding_state: str) -> None:
    record_id = BRANCH_ID if binding_state == "inactive_branch" else VAULT_ID
    schema_root = "branch" if binding_state == "inactive_branch" else "relationship_vault"
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(record_id,),
        )
        current = repository.get_validated(record_id)
        if binding_state == "inactive_branch":
            assert isinstance(current, Branch)
            updated = reseal_update(
                current,
                {
                    "status": "inactive",
                    "activated_at": None,
                    "deactivated_at": NOW,
                    "version": current.version + 1,
                },
            )
        else:
            assert isinstance(current, RelationshipVault)
            updated = reseal_update(
                current,
                {"status": "sealed", "version": current.version + 1},
            )
        repository.save_authoritative(
            schema_root,
            updated.model_dump(mode="python"),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


@pytest.mark.parametrize(
    "binding_state",
    ("inactive_branch", "sealed_vault"),
    ids=("inactive-branch", "sealed-vault"),
)
def test_detectors_exclude_proposal_with_inactive_authority_binding(
    database,
    binding_state: str,
) -> None:
    from amadeus_core.governance.proposal_service import ProposalService

    proposal_service = ProposalService(database, clock=_FixedClock(NOW))
    proposal = _seed_deferred_lifecycle_proposal(database)
    expired_at = proposal.expires_at + timedelta(microseconds=1)
    assert proposal.proposal_id in proposal_service.find_expired(expired_at)

    _disable_proposal_binding(database, binding_state)
    before = _database_snapshot(database)

    assert proposal.proposal_id not in proposal_service.find_reopenable(NOW)
    assert proposal.proposal_id not in proposal_service.find_expired(expired_at)
    assert _database_snapshot(database) == before
