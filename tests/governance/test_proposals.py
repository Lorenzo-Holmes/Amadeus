from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from amadeus_core.contracts.commands import (
    Actor,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.repository import AuthorityRepository


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
INSTANCE_ID = "ins-a1"
VAULT_ID = "vlt-a1"
DEPLOYMENT_POLICY_REF = "deployment:test"
LLM_ID = "llm-a1"
GOVERNOR_ID = "gov-a1"


@dataclass(frozen=True, slots=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


def _record_header(
    record_type: str,
    record_id: str,
    *,
    created_by_event_id: str,
    created_at: datetime = NOW,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": record_type,
        "record_id": record_id,
        "identity_id": IDENTITY_ID,
        "lineage_id": LINEAGE_ID,
        "branch_id": BRANCH_ID,
        "created_at": created_at,
        "created_by_event_id": created_by_event_id,
        "deployment_policy_ref": DEPLOYMENT_POLICY_REF,
        "canonicalization": "core-canonical-json-v1",
        "hash_algorithm": "sha256",
        "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
        "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
        "hash_scope": HASH_SCOPE_REGISTRY[(record_type, "0.1")],
        "content_hash": "0" * 64,
    }


def _seal(model_type: type[Any], body: dict[str, object]):
    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": digest}
            )
        }
    )


def _reseal_proposal(proposal: Proposal, **updates: object) -> Proposal:
    draft = proposal.model_copy(update=updates)
    digest = compute_record_content_hash(draft)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": digest}
            )
        }
    )


def _proposal(
    *,
    proposal_id: str,
    submitted_event_id: str,
    status: str = "pending",
) -> Proposal:
    return _seal(
        Proposal,
        {
            "record_header": _record_header(
                "Proposal",
                proposal_id,
                created_by_event_id=submitted_event_id,
            ),
            "proposal_id": proposal_id,
            "proposal_type": "lifecycle_transition",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": LLM_ID},
            "target_refs": (IDENTITY_ID,),
            "evidence_refs": (GENESIS_EVENT_ID,),
            "proposed_patch": {"requested_action": "maintenance_paused"},
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=1),
            "status": status,
            "deferred_at": None,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": None,
            },
            "reopened_count": 0,
            "version": 1,
        },
    )


def _command(
    *,
    command_id: str,
    command_type: str,
    actor_type: str,
    actor_id: str,
    targets: tuple[tuple[str, int | str], ...],
    payload: dict[str, object],
    issued_at: datetime = NOW,
) -> MutationCommandEnvelope:
    return MutationCommandEnvelope(
        command_id=command_id,
        command_type=command_type,
        actor=Actor(actor_type=actor_type, actor_id=actor_id),
        actor_capability_id=f"cap-{command_id.removeprefix('cmd-')}",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version=version)
            for target, version in targets
        ),
        audit_context_id=f"aud-{command_id.removeprefix('cmd-')}",
        idempotency_key=f"idem-{command_id}",
        issued_at=issued_at,
        target_record_refs=tuple(target for target, _version in targets),
        payload=payload,
    )


def _submit_command(proposal: Proposal, event_id: str) -> MutationCommandEnvelope:
    return _command(
        command_id=f"cmd-{event_id.removeprefix('evt-')}",
        command_type="memory_proposal.submit",
        actor_type="llm",
        actor_id=LLM_ID,
        targets=((proposal.proposal_id, "absent"), (event_id, "absent")),
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


def _decision(
    proposal: Proposal,
    conditions: DeferConditions,
    *,
    decision_id: str,
    decision_event_id: str,
    proposal_event_id: str,
) -> GovernorDecision:
    deferred_proposal = _reseal_proposal(
        proposal,
        status="deferred",
        deferred_at=NOW,
        defer_conditions=conditions,
        version=2,
    )
    return _seal(
        GovernorDecision,
        {
            "record_header": _record_header(
                "GovernorDecision",
                decision_id,
                created_by_event_id=decision_event_id,
            ),
            "decision_id": decision_id,
            "proposal_id": proposal.proposal_id,
            "identity_id": proposal.identity_id,
            "lineage_id": proposal.lineage_id,
            "branch_id": proposal.branch_id,
            "vault_id": proposal.vault_id,
            "result": "defer",
            "policy_version": "governor-policy:test",
            "input_state_hash": proposal.record_header.content_hash,
            "reason_codes": ("missing_verified_correction",),
            "evidence_refs": proposal.evidence_refs,
            "committed_event_ids": (decision_event_id, proposal_event_id),
            "output_state_hash": deferred_proposal.record_header.content_hash,
            "decided_at": NOW,
            "governor_signature": "governor-signature:test",
            "version": 1,
        },
    )


def _defer_command(
    proposal: Proposal,
    decision: GovernorDecision,
    conditions: DeferConditions,
    *,
    decision_event_id: str,
    proposal_event_id: str,
) -> MutationCommandEnvelope:
    descriptor = {
        "proposal_id": proposal.proposal_id,
        "decision": decision.model_dump(mode="python"),
        "defer_conditions": conditions.model_dump(mode="python"),
    }
    return _command(
        command_id=f"cmd-{decision_event_id.removeprefix('evt-')}",
        command_type="memory_proposal.defer",
        actor_type="governor",
        actor_id=GOVERNOR_ID,
        targets=(
            (proposal.proposal_id, 1),
            (decision.decision_id, "absent"),
            (decision_event_id, "absent"),
            (proposal_event_id, "absent"),
        ),
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                proposal.proposal_id,
                *proposal.evidence_refs,
            ),
            "decision_event_id": decision_event_id,
            "proposal_event_id": proposal_event_id,
            "instance_id": INSTANCE_ID,
            **descriptor,
            "semantic_input_hash": sha256_hex(canonical_json(descriptor)),
        },
    )


def _reopen_command(
    proposal: Proposal,
    event_id: str,
    *,
    evidence_event_ids: tuple[str, ...] = (),
    now: datetime = NOW,
) -> MutationCommandEnvelope:
    descriptor = {
        "proposal_id": proposal.proposal_id,
        "evidence_event_ids": evidence_event_ids,
        "now": now,
    }
    return _command(
        command_id=f"cmd-{event_id.removeprefix('evt-')}",
        command_type="memory_proposal.reopen",
        actor_type="governor",
        actor_id=GOVERNOR_ID,
        targets=((proposal.proposal_id, proposal.version), (event_id, "absent")),
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                proposal.proposal_id,
                *evidence_event_ids,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            **descriptor,
            "semantic_input_hash": sha256_hex(canonical_json(descriptor)),
        },
        issued_at=now,
    )


def _expire_command(
    proposal: Proposal,
    event_id: str,
    *,
    now: datetime,
) -> MutationCommandEnvelope:
    descriptor = {
        "proposal_id": proposal.proposal_id,
        "now": now,
    }
    return _command(
        command_id=f"cmd-{event_id.removeprefix('evt-')}",
        command_type="memory_proposal.expire",
        actor_type="governor",
        actor_id=GOVERNOR_ID,
        targets=((proposal.proposal_id, proposal.version), (event_id, "absent")),
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                proposal.proposal_id,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            **descriptor,
            "semantic_input_hash": sha256_hex(canonical_json(descriptor)),
        },
        issued_at=now,
    )


def _load(database: SQLiteDatabase, record_id: str):
    connection = database.connect()
    try:
        return AuthorityRepository(connection).get_validated(record_id)
    finally:
        connection.close()


def _count(database: SQLiteDatabase, record_type: str) -> int:
    connection = database.connect()
    try:
        return int(
            connection.execute(
                "SELECT count(*) FROM authority_records WHERE record_type = ?",
                (record_type,),
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _event_stream(
    database: SQLiteDatabase,
) -> tuple[tuple[str, str, dict[str, object]], ...]:
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        return tuple(
            (event.event_id, event.event_type, dict(payload or {}))
            for event, payload in zip(
                replay.events,
                replay.resolved_inline_payloads,
                strict=True,
            )
        )
    finally:
        connection.close()


def _authority_and_ledger_snapshot(database: SQLiteDatabase) -> tuple[object, ...]:
    connection = database.connect()
    try:
        authority = tuple(
            tuple(row)
            for row in connection.execute(
                """
                SELECT record_id, record_type, version, content_hash
                FROM authority_records
                ORDER BY record_id
                """
            ).fetchall()
        )
        ledger = tuple(
            tuple(row)
            for row in connection.execute(
                """
                SELECT event_id, ledger_seq, previous_event_hash, event_hash
                FROM ledger_events
                ORDER BY ledger_seq
                """
            ).fetchall()
        )
        return authority, ledger
    finally:
        connection.close()


def _full_database_snapshot(database: SQLiteDatabase) -> tuple[object, ...]:
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


def _seed_proposal(database: SQLiteDatabase, proposal: Proposal) -> None:
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


@pytest.fixture
def proposal_service(database: SQLiteDatabase):
    from amadeus_core.governance.proposal_service import ProposalService

    return ProposalService(database, clock=FixedClock(NOW))


def test_submit_writes_pending_proposal_and_one_event_only(
    database: SQLiteDatabase,
    proposal_service,
) -> None:
    proposal = _proposal(proposal_id="prp-a2", submitted_event_id="evt-a2")
    command = _submit_command(proposal, "evt-a2")

    result = proposal_service.submit(command, proposal)

    assert result.error is None
    assert isinstance(result.value, Proposal)
    assert result.value.status == "pending"
    assert result.value.version == 1
    assert result.event_ids == ("evt-a2",)
    assert _load(database, proposal.proposal_id) == result.value
    assert _event_stream(database)[-1] == (
        "evt-a2",
        "proposal_submitted",
        {
            "proposal_id": proposal.proposal_id,
            "proposal_type": proposal.proposal_type,
            "vault_id": VAULT_ID,
            "proposal_content_hash": proposal.record_header.content_hash,
        },
    )
    assert _count(database, "AutobiographicalMemory") == 0
    assert _count(database, "GovernorDecision") == 0


def test_defer_atomically_writes_decision_proposal_and_ordered_events(
    database: SQLiteDatabase,
    proposal_service,
) -> None:
    proposal = _proposal(proposal_id="prp-a3", submitted_event_id="evt-a3")
    submitted = proposal_service.submit(
        _submit_command(proposal, "evt-a3"),
        proposal,
    )
    assert submitted.error is None
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-a3",
        decision_event_id="evt-a4",
        proposal_event_id="evt-a5",
    )
    command = _defer_command(
        proposal,
        decision,
        conditions,
        decision_event_id="evt-a4",
        proposal_event_id="evt-a5",
    )

    result = proposal_service.defer(command, proposal.proposal_id, conditions)

    assert result.error is None
    assert isinstance(result.value, Proposal)
    assert result.value.status == "deferred"
    assert result.value.deferred_at == NOW
    assert result.value.defer_conditions.missing_evidence_types == (
        "correction_request_submitted",
    )
    assert result.value.version == 2
    assert (
        decision.output_state_hash
        == result.value.record_header.content_hash
    )
    assert result.event_ids == ("evt-a4", "evt-a5")
    assert _load(database, proposal.proposal_id) == result.value
    assert _load(database, decision.decision_id) == decision
    assert tuple(item[1] for item in _event_stream(database)[-2:]) == (
        "governor_decision_deferred",
        "proposal_deferred",
    )
    assert _count(database, "AutobiographicalMemory") == 0


@pytest.mark.parametrize(
    "proposal_type",
    (
        "create_memory",
        "change_memory_state",
        "change_expression_policy",
        "set_importance",
        "set_consolidation",
    ),
)
def test_specialized_defer_cannot_decide_memory_proposals(
    database: SQLiteDatabase,
    proposal_service,
    proposal_type: str,
) -> None:
    proposal = _reseal_proposal(
        _proposal(proposal_id="prp-d1", submitted_event_id="evt-d1"),
        proposal_type=proposal_type,
    )
    _seed_proposal(database, proposal)
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-d1",
        decision_event_id="evt-d2",
        proposal_event_id="evt-d3",
    )
    command = _defer_command(
        proposal,
        decision,
        conditions,
        decision_event_id="evt-d2",
        proposal_event_id="evt-d3",
    )
    before = _full_database_snapshot(database)

    result = proposal_service.defer(command, proposal.proposal_id, conditions)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code is CoreErrorCode.GOVERNOR_POLICY_MISMATCH
    assert _full_database_snapshot(database) == before


def test_reopen_terminal_proposal_is_side_effect_free(
    database: SQLiteDatabase,
    proposal_service,
) -> None:
    proposal = _proposal(
        proposal_id="prp-a4",
        submitted_event_id="evt-a6",
        status="expired",
    )
    _seed_proposal(database, proposal)
    command = _reopen_command(proposal, "evt-a7")
    before = _authority_and_ledger_snapshot(database)

    result = proposal_service.reopen(command, proposal.proposal_id, NOW)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.PROPOSAL_TERMINAL
    assert _authority_and_ledger_snapshot(database) == before
    assert _load(database, proposal.proposal_id) == proposal


def test_reopen_requires_authority_backed_evidence_and_is_explicit(
    database: SQLiteDatabase,
    proposal_service,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    proposal = _proposal(proposal_id="prp-a5", submitted_event_id="evt-a8")
    submitted = proposal_service.submit(
        _submit_command(proposal, "evt-a8"),
        proposal,
    )
    assert submitted.error is None
    reopen_at = NOW + timedelta(hours=2)
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=reopen_at,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-a5",
        decision_event_id="evt-a9",
        proposal_event_id="evt-b1",
    )
    deferred = proposal_service.defer(
        _defer_command(
            proposal,
            decision,
            conditions,
            decision_event_id="evt-a9",
            proposal_event_id="evt-b1",
        ),
        proposal.proposal_id,
        conditions,
    )
    assert deferred.error is None
    assert isinstance(deferred.value, Proposal)

    before_missing_evidence_detector = _full_database_snapshot(database)
    assert proposal_service.find_reopenable(reopen_at) == ()
    assert _full_database_snapshot(database) == before_missing_evidence_detector

    evidence_event_id = "evt-b2"
    request = request_factory(
        "correction_request",
        request_id="req-a5",
        event_id=evidence_event_id,
    )
    evidence_result = request_service.submit(
        request_command_factory(request, event_id=evidence_event_id),
        request,
    )
    assert evidence_result.error is None
    assert _event_stream(database)[-1][1] == "correction_request_submitted"

    before_time_detector = _full_database_snapshot(database)
    assert proposal_service.find_reopenable(reopen_at - timedelta(microseconds=1)) == ()
    assert _full_database_snapshot(database) == before_time_detector

    before_eligible_detector = _full_database_snapshot(database)
    assert proposal_service.find_reopenable(reopen_at) == (proposal.proposal_id,)
    assert _full_database_snapshot(database) == before_eligible_detector

    deferred_proposal = deferred.value
    reopen_event_id = "evt-b3"
    before_events = _event_stream(database)
    result = proposal_service.reopen(
        _reopen_command(
            deferred_proposal,
            reopen_event_id,
            evidence_event_ids=(evidence_event_id,),
            now=reopen_at,
        ),
        proposal.proposal_id,
        reopen_at,
    )

    assert result.error is None
    assert isinstance(result.value, Proposal)
    assert result.value.status == "pending"
    assert result.value.version == 3
    assert result.value.deferred_at is None
    assert result.value.defer_conditions == DeferConditions(
        missing_evidence_types=(),
        reopen_not_before=None,
    )
    assert result.value.reopened_count == 1
    assert result.event_ids == (reopen_event_id,)
    assert _load(database, proposal.proposal_id) == result.value
    after_events = _event_stream(database)
    assert len(after_events) == len(before_events) + 1
    event_id, event_type, payload = after_events[-1]
    assert (event_id, event_type) == (reopen_event_id, "proposal_reopened")
    assert payload["proposal_id"] == proposal.proposal_id
    assert tuple(payload["evidence_event_ids"]) == (evidence_event_id,)


@pytest.mark.parametrize("initial_status", ("pending", "deferred"))
def test_expire_detector_is_read_only_and_transition_is_explicit(
    initial_status: str,
    database: SQLiteDatabase,
    proposal_service,
) -> None:
    proposal = _proposal(proposal_id="prp-a6", submitted_event_id="evt-b4")
    submitted = proposal_service.submit(
        _submit_command(proposal, "evt-b4"),
        proposal,
    )
    assert submitted.error is None
    assert isinstance(submitted.value, Proposal)
    current = submitted.value
    if initial_status == "deferred":
        conditions = DeferConditions(
            missing_evidence_types=("correction_request_submitted",),
            reopen_not_before=proposal.expires_at + timedelta(hours=1),
        )
        decision = _decision(
            proposal,
            conditions,
            decision_id="gvd-a6",
            decision_event_id="evt-b5",
            proposal_event_id="evt-b6",
        )
        deferred = proposal_service.defer(
            _defer_command(
                proposal,
                decision,
                conditions,
                decision_event_id="evt-b5",
                proposal_event_id="evt-b6",
            ),
            proposal.proposal_id,
            conditions,
        )
        assert deferred.error is None
        assert isinstance(deferred.value, Proposal)
        current = deferred.value

    before_deadline = proposal.expires_at - timedelta(microseconds=1)
    before_early_detector = _full_database_snapshot(database)
    assert proposal_service.find_expired(before_deadline) == ()
    assert _full_database_snapshot(database) == before_early_detector

    before_due_detector = _full_database_snapshot(database)
    assert proposal_service.find_expired(proposal.expires_at) == (
        proposal.proposal_id,
    )
    assert _full_database_snapshot(database) == before_due_detector

    expire_event_id = "evt-b7"
    before_events = _event_stream(database)
    decisions_before = _count(database, "GovernorDecision")
    result = proposal_service.expire(
        _expire_command(
            current,
            expire_event_id,
            now=proposal.expires_at,
        ),
        proposal.proposal_id,
        proposal.expires_at,
    )

    assert result.error is None
    assert isinstance(result.value, Proposal)
    assert result.value.status == "expired"
    assert result.value.version == current.version + 1
    assert result.event_ids == (expire_event_id,)
    assert _load(database, proposal.proposal_id) == result.value
    after_events = _event_stream(database)
    assert len(after_events) == len(before_events) + 1
    event_id, event_type, payload = after_events[-1]
    assert (event_id, event_type) == (expire_event_id, "proposal_expired")
    assert payload["proposal_id"] == proposal.proposal_id
    assert _count(database, "GovernorDecision") == decisions_before
    assert _count(database, "AutobiographicalMemory") == 0


def test_defer_rejects_evidence_type_that_already_exists(
    database: SQLiteDatabase,
    proposal_service,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    existing_evidence = request_factory(
        "correction_request",
        request_id="req-c1",
        event_id="evt-c1",
    )
    recorded = request_service.submit(
        request_command_factory(existing_evidence, event_id="evt-c1"),
        existing_evidence,
    )
    assert recorded.error is None

    proposal = _proposal(proposal_id="prp-c2", submitted_event_id="evt-c2")
    assert proposal_service.submit(
        _submit_command(proposal, "evt-c2"),
        proposal,
    ).error is None
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-c2",
        decision_event_id="evt-c3",
        proposal_event_id="evt-c4",
    )
    command = _defer_command(
        proposal,
        decision,
        conditions,
        decision_event_id="evt-c3",
        proposal_event_id="evt-c4",
    )
    before = _full_database_snapshot(database)

    result = proposal_service.defer(command, proposal.proposal_id, conditions)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.GOVERNOR_POLICY_MISMATCH
    assert _full_database_snapshot(database) == before


def test_defer_rejects_decision_evidence_omitted_from_scope_refs(
    database: SQLiteDatabase,
    proposal_service,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    extra_evidence = request_factory(
        "non_mention_request",
        request_id="req-c5",
        event_id="evt-c5",
    )
    assert request_service.submit(
        request_command_factory(extra_evidence, event_id="evt-c5"),
        extra_evidence,
    ).error is None
    proposal = _proposal(proposal_id="prp-c6", submitted_event_id="evt-c6")
    assert proposal_service.submit(
        _submit_command(proposal, "evt-c6"),
        proposal,
    ).error is None
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    base_decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-c6",
        decision_event_id="evt-c7",
        proposal_event_id="evt-c8",
    )
    decision_draft = base_decision.model_copy(
        update={
            "evidence_refs": (*proposal.evidence_refs, "evt-c5"),
            "record_header": base_decision.record_header.model_copy(
                update={"content_hash": "0" * 64}
            ),
        }
    )
    decision = decision_draft.model_copy(
        update={
            "record_header": decision_draft.record_header.model_copy(
                update={
                    "content_hash": compute_record_content_hash(decision_draft)
                }
            )
        }
    )
    command = _defer_command(
        proposal,
        decision,
        conditions,
        decision_event_id="evt-c7",
        proposal_event_id="evt-c8",
    )
    before = _full_database_snapshot(database)

    result = proposal_service.defer(command, proposal.proposal_id, conditions)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.VAULT_SCOPE_MISMATCH
    assert _full_database_snapshot(database) == before
