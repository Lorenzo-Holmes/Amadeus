from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import (
    Actor,
    CommandExecutionContext,
    CommandResult,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.governance.governor import MemoryGovernor
from amadeus_core.governance.governor_command_auth import (
    GovernorCommandSigner,
    GovernorCommandVerifier,
)
from amadeus_core.governance.governor_decision_attestation import (
    GovernorDecisionAttestor,
)
from amadeus_core.governance.policy_v0_1 import GovernorPolicyV01, POLICY_VERSION
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import (
    ZERO_HASH,
    record_header,
    seal_record,
)
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
VAULT_ID = "vlt-a1"
INSTANCE_ID = "ins-a1"
MEMORY_ID = "mem-b1"
PROPOSAL_ID = "prp-b1"
GOVERNOR_ACTOR_ID = "gov-b1"
GOVERNOR_KEY_ID = "m4-local-a1"
GOVERNOR_SECRET = b"m4-local-governor-test-secret-32-bytes"
DECISION_KEY_ID = "m4-decision-a1"
DECISION_SECRET = b"m4-decision-attestation-test-secret-32-bytes"


def _governor_signer() -> GovernorCommandSigner:
    return GovernorCommandSigner(
        key_id=GOVERNOR_KEY_ID,
        actor_id=GOVERNOR_ACTOR_ID,
        secret=GOVERNOR_SECRET,
    )


def _governor_verifier() -> GovernorCommandVerifier:
    return GovernorCommandVerifier(
        {GOVERNOR_KEY_ID: (GOVERNOR_ACTOR_ID, GOVERNOR_SECRET)}
    )


def _decision_attestor() -> GovernorDecisionAttestor:
    return GovernorDecisionAttestor(
        active_key_id=DECISION_KEY_ID,
        authorities={
            DECISION_KEY_ID: (GOVERNOR_ACTOR_ID, DECISION_SECRET),
        },
    )


def _memory_governor(
    database: SQLiteDatabase,
    policy: GovernorPolicyV01 | None = None,
    *,
    now: datetime = NOW,
) -> MemoryGovernor:
    return MemoryGovernor(
        database,
        policy or GovernorPolicyV01(),
        command_verifier=_governor_verifier(),
        decision_attestor=_decision_attestor(),
        clock=FixedClock(now),
    )


def _proposal(
    *,
    proposal_id: str = PROPOSAL_ID,
    memory_id: str = MEMORY_ID,
    submit_event_id: str = "evt-b1",
    evidence_refs: tuple[str, ...] = ("evt-a1",),
    proposal_type: str = "create_memory",
    proposed_patch: dict[str, object] | None = None,
) -> Proposal:
    patch = proposed_patch or {
        "memory_id": memory_id,
        "semantic_kind": "episode",
        "state": "active",
        "importance": 0.5,
        "consolidation_state": "candidate",
        "expression_policy": {"mode": "eligible", "reason_refs": ()},
        "evidence_event_refs": evidence_refs,
        "supersedes_memory_ids": (),
        "contested_by_event_ids": (),
    }
    return seal_record(
        Proposal,
        {
            "record_header": record_header(
                "Proposal",
                proposal_id,
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id=submit_event_id,
                deployment_policy_ref="deployment:test",
            ),
            "proposal_id": proposal_id,
            "proposal_type": proposal_type,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": "llm-b1"},
            "target_refs": (memory_id,),
            "evidence_refs": evidence_refs,
            "proposed_patch": patch,
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=1),
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


def _command(
    *,
    command_id: str,
    command_type: str,
    actor_type: str,
    actor_id: str = "llm-b1",
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


def _expire_command(
    proposal: Proposal,
    *,
    event_id: str,
    now: datetime,
) -> MutationCommandEnvelope:
    descriptor = {"proposal_id": proposal.proposal_id, "now": now}
    return _command(
        command_id=f"cmd-{event_id.removeprefix('evt-')}",
        command_type="memory_proposal.expire",
        actor_type="governor",
        actor_id="gov-b1",
        targets=((proposal.proposal_id, proposal.version), (event_id, "absent")),
        payload={
            "scope_refs": (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                proposal.vault_id,
                proposal.proposal_id,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            **descriptor,
            "semantic_input_hash": sha256_hex(canonical_json(descriptor)),
        },
        issued_at=now,
    )


def _reopen_command(
    proposal: Proposal,
    *,
    event_id: str,
    evidence_event_ids: tuple[str, ...],
    now: datetime,
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
        actor_id="gov-b1",
        targets=((proposal.proposal_id, proposal.version), (event_id, "absent")),
        payload={
            "scope_refs": (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                proposal.vault_id,
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


def _submit_command(
    proposal: Proposal,
    *,
    command_id: str = "cmd-b1",
) -> MutationCommandEnvelope:
    event_id = proposal.record_header.created_by_event_id
    return _command(
        command_id=command_id,
        command_type="memory_proposal.submit",
        actor_type="llm",
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


def _decide_command(
    proposal: Proposal,
    *,
    command_id: str = "cmd-b2",
    actor_type: str = "governor",
    actor_id: str = GOVERNOR_ACTOR_ID,
    decision_id: str = "gvd-b1",
    decision_event_id: str = "evt-b2",
    effect_event_id: str = "evt-b3",
    proposal_version: int = 1,
    memory_version: int | str = "absent",
    authenticate: bool | None = None,
    effective_evidence_refs: tuple[str, ...] | None = None,
    now: datetime = NOW,
) -> MutationCommandEnvelope:
    memory_id = proposal.target_refs[0]
    targets = (
        (proposal.proposal_id, proposal_version),
        (decision_id, "absent"),
        (memory_id, memory_version),
        (decision_event_id, "absent"),
        (effect_event_id, "absent"),
    )
    descriptor = {
        "proposal_id": proposal.proposal_id,
        "policy_version": POLICY_VERSION,
        "now": now,
        "decision_id": decision_id,
        "decision_event_id": decision_event_id,
        "effect_event_id": effect_event_id,
    }
    command = _command(
        command_id=command_id,
        command_type="memory_proposal.decide",
        actor_type=actor_type,
        actor_id=actor_id,
        targets=targets,
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                proposal.proposal_id,
                *proposal.target_refs,
                *(
                    proposal.evidence_refs
                    if effective_evidence_refs is None
                    else effective_evidence_refs
                ),
            ),
            "instance_id": INSTANCE_ID,
            **descriptor,
            "semantic_input_hash": sha256_hex(canonical_json(descriptor)),
        },
        issued_at=now,
    )
    should_authenticate = (
        actor_type == "governor" if authenticate is None else authenticate
    )
    return _governor_signer().sign(command) if should_authenticate else command


def _llm_decide_command() -> MutationCommandEnvelope:
    return _decide_command(_proposal(), actor_type="llm", actor_id="llm-b1")


def _database_snapshot(database: SQLiteDatabase) -> tuple[tuple[object, ...], ...]:
    connection = database.connect()
    try:
        rows: list[tuple[object, ...]] = []
        for table, columns in (
            ("authority_records", "record_id, record_type, version, content_hash"),
            ("ledger_events", "event_id, ledger_seq, event_hash"),
            ("command_receipts", "command_id, command_hash, result_hash"),
        ):
            rows.extend(
                (table, *tuple(row))
                for row in connection.execute(
                    f"SELECT {columns} FROM {table} ORDER BY 1"
                ).fetchall()
            )
        return tuple(rows)
    finally:
        connection.close()


def _seed_fixture_event(
    database: SQLiteDatabase,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, object],
    vault_id: str | None = VAULT_ID,
    causation_id: str = "evt-a1",
) -> LedgerEvent:
    command = _command(
        command_id=f"cmd-{event_id.removeprefix('evt-')}-f1",
        command_type="fixture.event.append",
        actor_type="system",
        actor_id="sys-b1",
        targets=((event_id, "absent"),),
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                *((vault_id,) if vault_id is not None else ()),
            ),
            "semantic_input_hash": sha256_hex(canonical_json(payload)),
        },
    )

    def handler(
        repository: AuthorityRepository,
        mutation_command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> CommandResult[object]:
        head = repository.verified_ledger_head(BRANCH_ID)
        assert isinstance(head, LedgerEvent)
        stored_payload = prepare_inline_payload(payload)
        event = seal_record(
            LedgerEvent,
            {
                "record_header": record_header(
                    "LedgerEvent",
                    event_id,
                    identity_id=IDENTITY_ID,
                    lineage_id=LINEAGE_ID,
                    branch_id=BRANCH_ID,
                    created_at=NOW,
                    created_by_event_id=event_id,
                    deployment_policy_ref="deployment:test",
                ),
                "event_id": event_id,
                "ledger_seq": head.ledger_seq + 1,
                "identity_id": IDENTITY_ID,
                "lineage_id": LINEAGE_ID,
                "branch_id": BRANCH_ID,
                "instance_id": INSTANCE_ID,
                "vault_id": vault_id,
                "event_type": event_type,
                "occurred_at": NOW,
                "ingested_at": mutation_command.issued_at,
                "actor_type": mutation_command.actor.actor_type,
                "actor_id": mutation_command.actor.actor_id,
                "mutation_command_id": execution_context.command_id,
                "mutation_command_hash": execution_context.command_hash,
                "payload_ref": stored_payload.payload_ref,
                "causation_id": causation_id,
                "correlation_id": execution_context.audit_context_id,
                "previous_event_hash": head.event_hash,
                "event_hash": ZERO_HASH,
                "version": 1,
            },
        )
        appended = repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=stored_payload,
        )
        return CommandResult[object](
            value=appended.model_dump(mode="json"),
            event_ids=(event_id,),
            error=None,
            replayed=False,
        )

    result = SQLiteUnitOfWork(database).execute_command(command, handler)
    assert result.error is None
    assert result.value is not None
    stored = _load(database, event_id)
    assert isinstance(stored, LedgerEvent)
    return stored


def _seed_evidence_event(
    database: SQLiteDatabase,
    event_id: str = "evt-b4",
    *,
    rejected: bool = False,
    source_event_ref: str = "evt-b0",
    seed_source: bool = True,
) -> LedgerEvent:
    if seed_source and _load(database, source_event_ref) is None:
        _seed_fixture_event(
            database,
            event_id=source_event_ref,
            event_type="audit_finding_recorded",
            payload={"source_kind": "user_observation", "vault_id": VAULT_ID},
        )
    payload = (
        {
            "attestation_status": "revoked",
            "source_binding_status": "invalid",
            "source_event_ref": source_event_ref,
            "vault_id": VAULT_ID,
        }
        if rejected
        else {
            "attestation_status": "verified",
            "source_binding_status": "valid",
            "source_event_ref": source_event_ref,
            "vault_id": VAULT_ID,
        }
    )
    return _seed_fixture_event(
        database,
        event_id=event_id,
        event_type="evidence_sealed",
        payload=payload,
        causation_id=source_event_ref,
    )


def _seed_archived_memory(database: SQLiteDatabase) -> AutobiographicalMemory:
    memory = seal_record(
        AutobiographicalMemory,
        {
            "record_header": record_header(
                "AutobiographicalMemory",
                MEMORY_ID,
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id="evt-a1",
                deployment_policy_ref="deployment:test",
            ),
            "memory_id": MEMORY_ID,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "governing_vault_id": VAULT_ID,
            "semantic_kind": "episode",
            "state": "archived",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {"mode": "eligible", "reason_refs": ()},
            "evidence_event_refs": ("evt-a1",),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
            "governor_decision_id": "gvd-a2",
            "semantic_version": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "version": 1,
        },
    )
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(MEMORY_ID,),
        ).save_authoritative(
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
    return memory


def _load(database: SQLiteDatabase, record_id: str) -> object | None:
    connection = database.connect()
    try:
        return AuthorityRepository(connection).get_validated(record_id)
    finally:
        connection.close()




def test_llm_can_submit_but_cannot_decide_memory_proposal(
    database: SQLiteDatabase,
) -> None:
    proposal = _proposal()
    submitted = ProposalService(database).submit(_submit_command(proposal), proposal)
    assert submitted.error is None
    assert submitted.value is not None
    before = _database_snapshot(database)

    result = _memory_governor(database).decide(
        _llm_decide_command(),
        PROPOSAL_ID,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.LLM_COMMIT_FORBIDDEN
    assert result.event_ids == ()
    assert _database_snapshot(database) == before
    connection = database.connect()
    try:
        stored = AuthorityRepository(connection).get_validated(PROPOSAL_ID)
        assert isinstance(stored, Proposal)
        assert stored.status == "pending"
        assert AuthorityRepository(connection).get_validated("gvd-b1") is None
        assert AuthorityRepository(connection).get_validated(MEMORY_ID) is None
        assert (
            connection.execute(
                "SELECT count(*) FROM command_receipts WHERE command_id = 'cmd-b2'"
            ).fetchone()[0]
            == 0
        )
    finally:
        connection.close()


def test_forged_governor_actor_capability_cannot_decide_memory_proposal(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None
    before = _database_snapshot(database)

    forged = _decide_command(
        proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
        authenticate=False,
    )
    result = _memory_governor(database).decide(
        forged,
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == ()
    assert _database_snapshot(database) == before


def test_memory_governor_requires_a_concrete_command_verifier(
    database: SQLiteDatabase,
) -> None:
    with pytest.raises(TypeError, match="command_verifier"):
        MemoryGovernor(database, GovernorPolicyV01())


def test_memory_governor_rejects_policy_subclasses(
    database: SQLiteDatabase,
) -> None:
    class SubstitutedPolicy(GovernorPolicyV01):
        pass

    with pytest.raises(TypeError, match="exact GovernorPolicyV01"):
        MemoryGovernor(
            database,
            SubstitutedPolicy(),
            command_verifier=_governor_verifier(),
            decision_attestor=_decision_attestor(),
        )


def test_create_commit_cannot_drop_validated_memory_provenance(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-e1",
        memory_id="mem-e1",
        submit_event_id="evt-e1",
        evidence_refs=(evidence.event_id,),
        proposed_patch={
            "memory_id": "mem-e1",
            "semantic_kind": "episode",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {"mode": "eligible", "reason_refs": ()},
            "evidence_event_refs": (),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
        },
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-e1"),
        proposal,
    )
    assert submitted.error is None

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-e2",
            decision_id="gvd-e1",
            decision_event_id="evt-e2",
            effect_event_id="evt-e3",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.error is None
    stored = _load(database, "mem-e1")
    assert isinstance(stored, AutobiographicalMemory)
    assert stored.evidence_event_refs == (evidence.event_id,)


def test_create_submit_records_replacement_intent_but_governor_rejects_unatomic_commit(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    old_memory = _seed_archived_memory(database)
    new_memory_id = "mem-f1"
    proposal = _proposal(
        proposal_id="prp-f1",
        memory_id=new_memory_id,
        submit_event_id="evt-f1",
        evidence_refs=(evidence.event_id,),
        proposed_patch={
            "memory_id": new_memory_id,
            "semantic_kind": "episode",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {"mode": "eligible", "reason_refs": ()},
            "evidence_event_refs": (evidence.event_id,),
            "supersedes_memory_ids": (old_memory.memory_id,),
            "contested_by_event_ids": (),
        },
    )
    connection = database.connect()
    try:
        before_submit_event_ids = frozenset(
            event.event_id for event in replay_ledger(connection, BRANCH_ID).events
        )
    finally:
        connection.close()

    submit_command = _submit_command(proposal, command_id="cmd-f1")
    submit_command = submit_command.model_copy(
        update={
            "payload": {
                **submit_command.payload,
                "scope_refs": (
                    IDENTITY_ID,
                    LINEAGE_ID,
                    BRANCH_ID,
                    VAULT_ID,
                    new_memory_id,
                    old_memory.memory_id,
                    *proposal.evidence_refs,
                ),
            }
        }
    )
    submitted = ProposalService(database).submit(submit_command, proposal)

    assert submitted.error is None
    assert submitted.value == proposal
    assert submitted.event_ids == ("evt-f1",)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    newly_appended = tuple(
        event for event in replay.events if event.event_id not in before_submit_event_ids
    )
    assert len(newly_appended) == 1
    assert newly_appended[0].event_id == "evt-f1"
    assert newly_appended[0].event_type == "proposal_submitted"
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.proposed_patch["supersedes_memory_ids"] == (
        old_memory.memory_id,
    )
    assert _load(database, old_memory.memory_id) == old_memory
    assert _load(database, new_memory_id) is None

    decide_before = _database_snapshot(database)
    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-f2",
            decision_id="gvd-f1",
            decision_event_id="evt-f2",
            effect_event_id="evt-f3",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.INVALID_MEMORY_TRANSITION
    assert result.event_ids == ()
    assert _database_snapshot(database) == decide_before
    assert _load(database, old_memory.memory_id) == old_memory
    assert _load(database, new_memory_id) is None
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "pending"
    assert _load(database, "gvd-f1") is None


def test_archived_memory_cannot_be_superseded_through_real_submit_and_decide(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    archived = _seed_archived_memory(database)
    proposal = _proposal(
        proposal_id="prp-b4",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
        proposal_type="change_memory_state",
        proposed_patch={
            "state": "superseded",
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
        },
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None
    before = _database_snapshot(database)

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-b6",
            decision_id="gvd-b4",
            decision_event_id="evt-b6",
            effect_event_id="evt-b7",
            memory_version=1,
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.INVALID_MEMORY_TRANSITION
    assert result.event_ids == ()
    assert _database_snapshot(database) == before
    assert _load(database, MEMORY_ID) == archived
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "pending"
    assert _load(database, "gvd-b4") is None


def test_governor_commit_is_atomic_idempotent_and_terminal(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None
    decide = _decide_command(
        proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
    )

    first = _memory_governor(database).decide(
        decide,
        proposal.proposal_id,
        NOW,
    )

    assert first.error is None
    assert isinstance(first.value, GovernorDecision)
    assert first.value.result == "commit"
    assert first.event_ids == ("evt-b6", "evt-b7")
    assert first.value.committed_event_ids == first.event_ids
    stored_proposal = _load(database, proposal.proposal_id)
    stored_decision = _load(database, "gvd-b2")
    stored_memory = _load(database, "mem-b2")
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "committed"
    assert stored_proposal.version == 2
    assert stored_decision == first.value
    assert isinstance(stored_memory, AutobiographicalMemory)
    assert stored_memory.state == "active"
    assert stored_memory.governor_decision_id == "gvd-b2"

    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert tuple(event.event_type for event in replay.events[-2:]) == (
        "governor_decision_committed",
        "memory_created",
    )
    assert tuple(event.event_id for event in replay.events).count("evt-b6") == 1
    assert tuple(event.event_id for event in replay.events).count("evt-b7") == 1
    after_first = _database_snapshot(database)

    replayed = _memory_governor(database).decide(
        decide,
        proposal.proposal_id,
        NOW,
    )
    assert replayed.replayed is True
    assert replayed.value == first.value
    assert replayed.event_ids == first.event_ids
    assert _database_snapshot(database) == after_first

    terminal = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-b8",
            decision_id="gvd-b3",
            decision_event_id="evt-b8",
            effect_event_id="evt-b9",
            proposal_version=2,
            memory_version=1,
        ),
        proposal.proposal_id,
        NOW,
    )
    assert terminal.value is None
    assert terminal.error is not None
    assert terminal.error.code is CoreErrorCode.PROPOSAL_TERMINAL
    assert terminal.event_ids == ()
    assert _database_snapshot(database) == after_first


def test_governor_commit_receipt_replays_after_memory_advances(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    create_proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    service = ProposalService(database)
    assert service.submit(
        _submit_command(create_proposal, command_id="cmd-b5"),
        create_proposal,
    ).error is None
    create_command = _decide_command(
        create_proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
    )
    governor = _memory_governor(database)
    created = governor.decide(create_command, create_proposal.proposal_id, NOW)
    assert created.error is None
    assert created.value is not None
    assert created.value.result == "commit"

    archive_proposal = _proposal(
        proposal_id="prp-b8",
        memory_id="mem-b2",
        submit_event_id="evt-b8",
        evidence_refs=(evidence.event_id,),
        proposal_type="change_memory_state",
        proposed_patch={
            "state": "archived",
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
        },
    )
    assert service.submit(
        _submit_command(archive_proposal, command_id="cmd-b8"),
        archive_proposal,
    ).error is None
    archived = governor.decide(
        _decide_command(
            archive_proposal,
            command_id="cmd-b9",
            decision_id="gvd-b3",
            decision_event_id="evt-b9",
            effect_event_id="evt-ba",
            memory_version=1,
        ),
        archive_proposal.proposal_id,
        NOW,
    )
    assert archived.error is None
    current_memory = _load(database, "mem-b2")
    assert isinstance(current_memory, AutobiographicalMemory)
    assert current_memory.version == 2
    assert current_memory.state == "archived"
    before_replay = _database_snapshot(database)

    replayed = governor.decide(create_command, create_proposal.proposal_id, NOW)

    assert replayed.replayed is True
    assert replayed.error is None
    assert replayed.value == created.value
    assert replayed.event_ids == created.event_ids
    assert _load(database, "mem-b2") == current_memory
    assert _database_snapshot(database) == before_replay


def test_memory_created_authority_failure_rolls_back_entire_governor_commit(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None
    decide = _decide_command(
        proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
    )
    before = _database_snapshot(database)

    class FaultInjectingDatabase:
        def connect(self) -> sqlite3.Connection:
            connection = database.connect()
            connection.execute(
                """
                CREATE TEMP TRIGGER fail_memory_created_authority
                BEFORE INSERT ON authority_records
                WHEN NEW.record_type = 'LedgerEvent'
                 AND json_extract(NEW.content_json, '$.event_type') = 'memory_created'
                BEGIN
                    SELECT RAISE(ABORT, 'fault:m4.2-memory-created');
                END
                """
            )
            return connection

    with pytest.raises(sqlite3.DatabaseError, match="fault:m4.2-memory-created"):
        _memory_governor(FaultInjectingDatabase()).decide(  # type: ignore[arg-type]
            decide,
            proposal.proposal_id,
            NOW,
        )

    assert _database_snapshot(database) == before
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "pending"
    assert _load(database, "gvd-b2") is None
    assert _load(database, "mem-b2") is None
    assert _load(database, "evt-b6") is None
    assert _load(database, "evt-b7") is None
    connection = database.connect()
    try:
        assert (
            connection.execute(
                "SELECT count(*) FROM command_receipts WHERE command_id = ?",
                (decide.command_id,),
            ).fetchone()[0]
            == 0
        )
    finally:
        connection.close()


def test_governor_rejects_revoked_evidence_without_creating_memory(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database, rejected=True)
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-b6",
            decision_id="gvd-b2",
            decision_event_id="evt-b6",
            effect_event_id="evt-b7",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.error is None
    assert isinstance(result.value, GovernorDecision)
    assert result.value.result == "reject"
    assert result.value.reason_codes == (
        "ATTESTATION_REVOKED",
        "SOURCE_BINDING_INVALID",
    )
    assert result.event_ids == ("evt-b6",)
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "rejected"
    assert _load(database, "mem-b2") is None
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert replay.events[-1].event_type == "governor_decision_rejected"


def test_governor_defers_missing_evidence_without_creating_memory(
    database: SQLiteDatabase,
) -> None:
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    )
    assert submitted.error is None

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-b6",
            decision_id="gvd-b2",
            decision_event_id="evt-b6",
            effect_event_id="evt-b7",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.error is None
    assert isinstance(result.value, GovernorDecision)
    assert result.value.result == "defer"
    assert result.value.reason_codes == ("REQUIRED_EVIDENCE_MISSING",)
    assert result.event_ids == ("evt-b6", "evt-b7")
    stored_proposal = _load(database, proposal.proposal_id)
    assert isinstance(stored_proposal, Proposal)
    assert stored_proposal.status == "deferred"
    assert _load(database, "mem-b2") is None
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert tuple(event.event_type for event in replay.events[-2:]) == (
        "governor_decision_deferred",
        "proposal_deferred",
    )


def test_governor_defer_receipt_replays_after_real_proposal_expire(
    database: SQLiteDatabase,
) -> None:
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(),
    )
    service = ProposalService(database)
    assert service.submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    ).error is None
    decide = _decide_command(
        proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
    )
    governor = _memory_governor(database)
    first = governor.decide(decide, proposal.proposal_id, NOW)
    assert first.error is None
    assert first.value is not None
    assert first.value.result == "defer"

    deferred = _load(database, proposal.proposal_id)
    assert isinstance(deferred, Proposal)
    expired = service.expire(
        _expire_command(
            deferred,
            event_id="evt-b8",
            now=proposal.expires_at,
        ),
        proposal.proposal_id,
        proposal.expires_at,
    )
    assert expired.error is None
    assert isinstance(expired.value, Proposal)
    assert expired.value.status == "expired"
    before_replay = _database_snapshot(database)

    replayed = governor.decide(decide, proposal.proposal_id, NOW)

    assert replayed.replayed is True
    assert replayed.error is None
    assert replayed.value == first.value
    assert replayed.event_ids == first.event_ids
    assert _load(database, proposal.proposal_id) == expired.value
    assert _database_snapshot(database) == before_replay


def test_governor_defer_receipt_replays_after_real_proposal_reopen(
    database: SQLiteDatabase,
) -> None:
    proposal = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(),
    )
    service = ProposalService(database)
    assert service.submit(
        _submit_command(proposal, command_id="cmd-b5"),
        proposal,
    ).error is None
    decide = _decide_command(
        proposal,
        command_id="cmd-b6",
        decision_id="gvd-b2",
        decision_event_id="evt-b6",
        effect_event_id="evt-b7",
    )
    governor = _memory_governor(database)
    first = governor.decide(decide, proposal.proposal_id, NOW)
    assert first.error is None
    assert first.value is not None
    assert first.value.result == "defer"

    deferred = _load(database, proposal.proposal_id)
    assert isinstance(deferred, Proposal)
    assert deferred.defer_conditions.missing_evidence_types == ("evidence_sealed",)
    evidence = _seed_evidence_event(database, event_id="evt-b8")
    reopen_at = NOW + timedelta(hours=1)
    reopened = service.reopen(
        _reopen_command(
            deferred,
            event_id="evt-b9",
            evidence_event_ids=(evidence.event_id,),
            now=reopen_at,
        ),
        proposal.proposal_id,
        reopen_at,
    )
    assert reopened.error is None
    assert isinstance(reopened.value, Proposal)
    assert reopened.value.status == "pending"
    before_replay = _database_snapshot(database)

    replayed = governor.decide(decide, proposal.proposal_id, NOW)

    assert replayed.replayed is True
    assert replayed.error is None
    assert replayed.value == first.value
    assert replayed.event_ids == first.event_ids
    assert _load(database, proposal.proposal_id) == reopened.value
    assert _database_snapshot(database) == before_replay

    second_decide = _decide_command(
        reopened.value,
        command_id="cmd-ba",
        decision_id="gvd-ba",
        decision_event_id="evt-ba",
        effect_event_id="evt-bb",
        proposal_version=reopened.value.version,
        effective_evidence_refs=(evidence.event_id,),
        now=reopen_at,
    )
    advanced_governor = _memory_governor(database, now=reopen_at)
    committed = advanced_governor.decide(
        second_decide,
        proposal.proposal_id,
        reopen_at,
    )

    assert committed.error is None
    assert committed.value is not None
    assert committed.value.result == "commit"
    assert committed.value.evidence_refs == (evidence.event_id,)
    stored_memory = _load(database, proposal.target_refs[0])
    assert isinstance(stored_memory, AutobiographicalMemory)
    assert stored_memory.evidence_event_refs == (evidence.event_id,)

    old_after_commit = governor.decide(decide, proposal.proposal_id, NOW)
    new_after_commit = advanced_governor.decide(
        second_decide,
        proposal.proposal_id,
        reopen_at,
    )
    assert old_after_commit.replayed is True
    assert old_after_commit.value == first.value
    assert new_after_commit.replayed is True
    assert new_after_commit.value == committed.value


