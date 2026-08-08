"""B01 M4 governance slice mapped to real Core service boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from amadeus_core.contracts.commands import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.vault import RelationshipVault
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.governance.request_service import RequestService
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.records import record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from stage0c_case_loader import (
    B01_M4_GOVERNANCE_CASE_PATHS,
    StrippedStorageCase,
    load_b01_m4_governance_cases,
)
from tests.governance.conftest import (
    _bootstrap,
    _make_request,
    _make_request_command,
    _seed_vault,
)
from tests.governance.test_model_commit_boundary import (
    BRANCH_ID,
    IDENTITY_ID,
    INSTANCE_ID,
    LINEAGE_ID,
    NOW,
    VAULT_ID,
    _database_snapshot,
    _decide_command,
    _load,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)
from amadeus_core.governance.policy_v0_1 import POLICY_VERSION


FORBIDDEN_DRIVER_FIELDS = frozenset(
    {"driver_result_ref", "seeded_results", "effects", "state_patch", "output"}
)


@pytest.fixture
def database(tmp_path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "b01-m4-governance.sqlite3")
    _bootstrap(database)
    _seed_vault(database)
    return database


def _save_setup_authority(database: SQLiteDatabase, schema_root: str, record) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(record.record_header.record_id,),
        ).save_authoritative(schema_root, record.model_dump(mode="python"))
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


@pytest.fixture
def ac009_database(tmp_path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "b01-m4-ac009.sqlite3")
    _bootstrap(database)
    _seed_vault(database)
    other_vault = seal_record(
        RelationshipVault,
        {
            "record_header": record_header(
                "RelationshipVault",
                "vlt-c9",
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id="evt-a1",
                deployment_policy_ref="deployment:test",
            ),
            "vault_id": "vlt-c9",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "relationship_principal_id": "usr-a1",
            "status": "active",
            "visibility_policy_ref": "visibility:other",
            "created_at": NOW,
            "version": 1,
        },
    )
    _save_setup_authority(database, "relationship_vault", other_vault)
    return database


def _seed_ac009_memory(
    database: SQLiteDatabase,
    *,
    memory_id: str,
    vault_id: str,
) -> AutobiographicalMemory:
    memory = seal_record(
        AutobiographicalMemory,
        {
            "record_header": record_header(
                "AutobiographicalMemory",
                memory_id,
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id="evt-a1",
                deployment_policy_ref="deployment:test",
            ),
            "memory_id": memory_id,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "governing_vault_id": vault_id,
            "semantic_kind": "relationship",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {"mode": "eligible", "reason_refs": ()},
            "evidence_event_refs": ("evt-a1",),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
            "governor_decision_id": "gvd-a1",
            "semantic_version": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "version": 1,
        },
    )
    _save_setup_authority(database, "autobiographical_memory", memory)
    return memory


def _all_mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {
            key for item in value.values() for key in _all_mapping_keys(item)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {key for item in value for key in _all_mapping_keys(item)}
    return set()


def _case(clause_id: str) -> StrippedStorageCase:
    return next(
        case
        for case in load_b01_m4_governance_cases()
        if case.identity.clause_id == clause_id
    )


def _count(database, record_type: str) -> int:
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


def _replay_payload(database: SQLiteDatabase, event_id: str) -> Mapping[str, object]:
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    payload = next(
        payload
        for event, payload in zip(
            replay.events,
            replay.resolved_inline_payloads,
            strict=True,
        )
        if event.event_id == event_id
    )
    assert payload is not None
    return payload


def test_exact_m4_b01_fixture_slice_and_stripped_inputs() -> None:
    fixture_bytes = tuple(path.read_bytes() for path in B01_M4_GOVERNANCE_CASE_PATHS)

    cases = load_b01_m4_governance_cases()

    assert tuple(case.identity.clause_id for case in cases) == (
        "AC-007#1",
        "AC-008#1",
        "AC-008#2",
        "AC-008#3",
        "AC-009#1",
        "AC-010#1",
        "AC-011#1",
        "AC-012#1",
        "AC-015#1",
    )
    assert tuple(case.identity.source_id for case in cases) == (
        "AC-007", "AC-008", "AC-008", "AC-008", "AC-009", "AC-010",
        "AC-011", "AC-012", "AC-015",
    )
    assert all(isinstance(case, StrippedStorageCase) for case in cases)
    assert all(case.mutations and case.assertions for case in cases)
    assert all(
        not (FORBIDDEN_DRIVER_FIELDS & _all_mapping_keys(case.model_dump(mode="python")))
        for case in cases
    )
    assert tuple(path.read_bytes() for path in B01_M4_GOVERNANCE_CASE_PATHS) == fixture_bytes


def test_ac007_confidentiality_request_then_proposal(database) -> None:
    case = _case("AC-007#1")
    request = _make_request(
        "confidentiality_request", request_id="req-c7", event_id="evt-c7"
    )
    request_command = _make_request_command(request, event_id="evt-c7")
    original_event = _load(database, "evt-a1")
    assert original_event is not None

    submitted_request = RequestService(database).submit(request_command, request)
    assert submitted_request.error is None
    assert submitted_request.event_ids == ("evt-c7",)
    assert _count(database, "Proposal") == _count(database, "GovernorDecision") == 0
    assert _count(database, "AutobiographicalMemory") == 0

    proposal = _proposal(
        proposal_id="prp-c7",
        memory_id="mem-c7",
        submit_event_id="evt-c8",
        evidence_refs=("evt-c7",),
    )
    proposed = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c7-a"), proposal
    )
    assert proposed.error is None
    assert isinstance(proposed.value, Proposal)
    assert proposed.value.status == "pending"
    assert _load(database, "evt-a1") == original_event
    assert case.identity.source_id == "AC-007"
    assert _count(database, "AutobiographicalMemory") == 0
    assert _count(database, "GovernorDecision") == 0


@pytest.mark.parametrize(
    ("clause_id", "scenario", "expected_result"),
    (
        ("AC-008#1", "commit", "commit"),
        ("AC-008#2", "reject", "reject"),
        ("AC-008#3", "defer", "defer"),
    ),
    ids=("ac008_1_commit", "ac008_2_reject", "ac008_3_defer"),
)
def test_ac008_governed_correction(
    database,
    clause_id: str,
    scenario: str,
    expected_result: str,
) -> None:
    case = _case(clause_id)
    evidence_refs: tuple[str, ...]
    if scenario == "commit":
        evidence_refs = (_seed_evidence_event(database, event_id="evt-c81").event_id,)
    elif scenario == "reject":
        evidence_refs = (
            _seed_evidence_event(
                database, event_id="evt-c82", rejected=True
            ).event_id,
        )
    else:
        evidence_refs = ()
    suffix = {"commit": "1", "reject": "2", "defer": "3"}[scenario]
    proposal = _proposal(
        proposal_id=f"prp-c8-{suffix}",
        memory_id=f"mem-c8-{suffix}",
        submit_event_id=f"evt-c8-{suffix}",
        evidence_refs=evidence_refs,
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id=f"cmd-c8-{suffix}"), proposal
    ).error is None

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id=f"cmd-c9-{suffix}",
            decision_id=f"gvd-c8-{suffix}",
            decision_event_id=f"evt-ca-{suffix}",
            effect_event_id=f"evt-cb-{suffix}",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.error is None
    assert isinstance(result.value, GovernorDecision)
    assert result.value.result == expected_result
    stored = _load(database, proposal.proposal_id)
    assert isinstance(stored, Proposal)
    assert stored.status == {"commit": "committed", "reject": "rejected", "defer": "deferred"}[scenario]
    assert (_load(database, proposal.target_refs[0]) is not None) is (scenario == "commit")
    assert case.identity.source_id == "AC-008"


def test_ac009_current_vault_non_mention_is_governor_scoped(ac009_database) -> None:
    case = _case("AC-009#1")
    setup_evidence = _seed_evidence_event(ac009_database, event_id="evt-c1")
    create_current = _proposal(
        proposal_id="prp-c1",
        memory_id="mem-c9-1",
        submit_event_id="evt-c2",
        evidence_refs=(setup_evidence.event_id,),
    )
    assert ProposalService(ac009_database).submit(
        _submit_command(create_current, command_id="cmd-c1"), create_current
    ).error is None
    created_current = _memory_governor(ac009_database).decide(
        _decide_command(
            create_current,
            command_id="cmd-c2",
            decision_id="gvd-c1",
            decision_event_id="evt-c3",
            effect_event_id="evt-c4",
        ),
        create_current.proposal_id,
        NOW,
    )
    assert created_current.error is None
    current_before = _load(ac009_database, "mem-c9-1")
    assert isinstance(current_before, AutobiographicalMemory)
    # The other-vault record is explicit setup state and is not a decision target.
    other_before = _seed_ac009_memory(
        ac009_database,
        memory_id="mem-c9-2",
        vault_id="vlt-c9",
    )
    current_vault_before = _load(ac009_database, VAULT_ID)
    other_vault_before = _load(ac009_database, "vlt-c9")
    assert isinstance(current_vault_before, RelationshipVault)
    assert isinstance(other_vault_before, RelationshipVault)
    request = _make_request(
        "non_mention_request", request_id="req-c9", event_id="evt-c9"
    )
    result = RequestService(ac009_database).submit(
        _make_request_command(request, event_id="evt-c9"), request
    )
    assert result.error is None
    assert result.value is not None
    assert result.value.requested_scope == "current_vault"
    assert result.event_ids == ("evt-c9",)
    request_event = _load(ac009_database, "evt-c9")
    assert isinstance(request_event, LedgerEvent)
    assert request_event.event_type == "non_mention_request_submitted"
    assert request_event.vault_id == VAULT_ID
    request_payload = _replay_payload(ac009_database, request_event.event_id)
    assert request_payload["request_id"] == request.request_id
    assert request_payload["request_type"] == request.request_type
    assert request_payload["vault_id"] == VAULT_ID

    # Setup evidence is sealed on the canonical Ledger chain, not a request receipt.
    evidence = _seed_evidence_event(
        ac009_database,
        event_id="evt-cc",
        source_event_ref=request_event.event_id,
        seed_source=False,
    )
    assert evidence.event_type == "evidence_sealed"
    assert evidence.causation_id == request_event.event_id
    assert evidence.event_id != request_event.event_id
    evidence_payload = _replay_payload(ac009_database, evidence.event_id)
    assert evidence_payload["source_event_ref"] == request_event.event_id
    assert evidence_payload["attestation_status"] == "verified"
    assert evidence_payload["source_binding_status"] == "valid"
    assert evidence_payload["vault_id"] == VAULT_ID
    proposal = _proposal(
        proposal_id="prp-c9",
        memory_id=current_before.memory_id,
        submit_event_id="evt-cd",
        evidence_refs=(evidence.event_id,),
        proposal_type="change_expression_policy",
        proposed_patch={
            "expression_policy": {
                "mode": "non_mention",
                "reason_refs": (evidence.event_id,),
            }
        },
    )
    assert proposal.proposal_type == "change_expression_policy"
    assert proposal.vault_id == VAULT_ID
    assert proposal.target_refs == (current_before.memory_id,)
    assert proposal.evidence_refs == (evidence.event_id,)
    assert proposal.proposed_patch == {
        "expression_policy": {
            "mode": "non_mention",
            "reason_refs": (evidence.event_id,),
        }
    }
    submitted = ProposalService(ac009_database).submit(
        _submit_command(proposal, command_id="cmd-c9"), proposal
    )
    assert submitted.error is None
    assert isinstance(submitted.value, Proposal)
    assert submitted.value.status == "pending"
    assert submitted.value.proposal_type == "change_expression_policy"
    assert submitted.value.vault_id == VAULT_ID
    assert submitted.value.target_refs == (current_before.memory_id,)
    assert submitted.value.evidence_refs == (evidence.event_id,)
    assert submitted.value.proposed_patch == proposal.proposed_patch

    committed = _memory_governor(ac009_database).decide(
        _decide_command(
            proposal,
            command_id="cmd-ca",
            decision_id="gvd-c9",
            decision_event_id="evt-ce",
            effect_event_id="evt-cf",
            memory_version=1,
        ),
        proposal.proposal_id,
        NOW,
    )

    assert committed.error is None
    assert isinstance(committed.value, GovernorDecision)
    assert committed.value.result == "commit"
    assert committed.value.proposal_id == proposal.proposal_id
    assert committed.value.vault_id == VAULT_ID
    assert committed.value.policy_version == POLICY_VERSION
    assert committed.value.evidence_refs == (evidence.event_id,)
    assert committed.value.committed_event_ids == ("evt-ce", "evt-cf")
    assert committed.value.governor_signature
    decision_event = _load(ac009_database, "evt-ce")
    effect_event = _load(ac009_database, "evt-cf")
    assert isinstance(decision_event, LedgerEvent)
    assert isinstance(effect_event, LedgerEvent)
    assert decision_event.event_type == "governor_decision_committed"
    assert decision_event.actor_type == "governor"
    assert decision_event.actor_id == "gov-b1"
    assert effect_event.event_type == "memory_expression_policy_changed"
    current_after = _load(ac009_database, current_before.memory_id)
    other_after = _load(ac009_database, other_before.memory_id)
    current_vault_after = _load(ac009_database, VAULT_ID)
    other_vault_after = _load(ac009_database, "vlt-c9")
    assert isinstance(current_after, AutobiographicalMemory)
    assert current_after.expression_policy.mode == "non_mention"
    assert current_after.expression_policy.reason_refs == (evidence.event_id,)
    assert current_after.governing_vault_id == VAULT_ID
    assert current_after.governor_decision_id == committed.value.decision_id
    assert current_after.record_header.content_hash != current_before.record_header.content_hash
    assert other_after == other_before
    assert isinstance(other_after, AutobiographicalMemory)
    assert other_after.record_header.content_hash == other_before.record_header.content_hash
    assert current_vault_after == current_vault_before
    assert other_vault_after == other_vault_before
    assert isinstance(current_vault_after, RelationshipVault)
    assert isinstance(other_vault_after, RelationshipVault)
    assert current_vault_after.record_header.content_hash == current_vault_before.record_header.content_hash
    assert other_vault_after.record_header.content_hash == other_vault_before.record_header.content_hash
    changed_vault_ids = tuple(
        vault_id
        for vault_id, before, after in (
            (VAULT_ID, current_before, current_after),
            ("vlt-c9", other_before, other_after),
        )
        if before.record_header.content_hash != after.record_header.content_hash
    )
    assert changed_vault_ids == (VAULT_ID,)
    assert case.identity.clause_id == "AC-009#1"
    assert case.identity.source_id == "AC-009"
    assert case.identity.source_binding_sha256 == (
        "F03A0CCFC01EAE18229FBDD5CC108019FA42D971A4E2C73572FC918E92F688EC"
    )
    assert case.identity.decision_sha256 == (
        "139B68F6C8083BC1B72D8D5FCB3CD1D040FD7FB721EEFF46FCDCA17042BCDE4C"
    )


def test_ac010_llm_commit_forbidden_is_side_effect_free(database) -> None:
    case = _case("AC-010#1")
    evidence = _seed_evidence_event(database, event_id="evt-ca")
    proposal = _proposal(
        proposal_id="prp-ca", memory_id="mem-ca", submit_event_id="evt-cb",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(_submit_command(proposal), proposal).error is None
    command = _decide_command(proposal).model_copy(
        update={"actor": Actor(actor_type="llm", actor_id="llm-ca")}
    )
    before = _database_snapshot(database)

    result = _memory_governor(database).decide(command, proposal.proposal_id, NOW)

    assert result.error is not None
    assert result.error.code is CoreErrorCode.LLM_COMMIT_FORBIDDEN
    assert _database_snapshot(database) == before
    assert _load(database, proposal.target_refs[0]) is None
    assert case.identity.source_id == "AC-010"


def test_ac011_proposal_is_pending_without_memory_write(database) -> None:
    case = _case("AC-011#1")
    evidence = _seed_evidence_event(database, event_id="evt-c11")
    proposal = _proposal(
        proposal_id="prp-c11", memory_id="mem-c11", submit_event_id="evt-c12",
        evidence_refs=(evidence.event_id,),
    )

    result = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c11"), proposal
    )

    assert result.error is None
    assert isinstance(result.value, Proposal)
    assert result.value.status == "pending"
    assert result.event_ids == (proposal.record_header.created_by_event_id,)
    proposal_event = _load(database, proposal.record_header.created_by_event_id)
    assert isinstance(proposal_event, LedgerEvent)
    assert proposal_event.event_type == "proposal_submitted"
    assert proposal_event.vault_id == proposal.vault_id
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    proposal_payload = next(
        payload
        for event, payload in zip(
            replay.events,
            replay.resolved_inline_payloads,
            strict=True,
        )
        if event.event_id == proposal_event.event_id
    )
    assert proposal_payload is not None
    assert proposal_payload["proposal_id"] == proposal.proposal_id
    assert proposal_payload["vault_id"] == proposal.vault_id
    assert _load(database, proposal.target_refs[0]) is None
    assert _count(database, "GovernorDecision") == 0
    assert case.identity.clause_id == "AC-011#1"
    assert case.identity.source_id == "AC-011"
    assert case.identity.source_binding_sha256 == (
        "236C6CAD1008A79C4877B59704FC5D2EF488CA8996E117AAB3DCA6147CB9E09E"
    )
    assert case.identity.decision_sha256 == (
        "9557E8DC3E34CA8EA4D08CFA89D42FB2B7B8622B6B4B0784848A4FB0B5FEA001"
    )


def test_ac012_preview_replay_is_deterministic(database) -> None:
    case = _case("AC-012#1")
    evidence = _seed_evidence_event(database, event_id="evt-c12")
    proposal = _proposal(
        proposal_id="prp-c12", memory_id="mem-c12", submit_event_id="evt-c13",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(_submit_command(proposal), proposal).error is None
    governor = _memory_governor(database)
    before = _database_snapshot(database)

    first = governor.preview_authoritative(
        proposal.proposal_id, policy_version=POLICY_VERSION, now=NOW
    )
    second = governor.preview_authoritative(
        proposal.proposal_id, policy_version=POLICY_VERSION, now=NOW
    )

    assert first == second
    assert first.result == "commit"
    assert _database_snapshot(database) == before
    assert case.identity.source_id == "AC-012"


def test_ac015_archived_to_superseded_is_side_effect_free(database) -> None:
    case = _case("AC-015#1")
    evidence = _seed_evidence_event(database, event_id="evt-d5")
    create = _proposal(
        proposal_id="prp-d5-1", memory_id="mem-d5", submit_event_id="evt-d6",
        evidence_refs=(evidence.event_id,),
    )
    service = ProposalService(database)
    governor = _memory_governor(database)
    assert service.submit(_submit_command(create), create).error is None
    assert governor.decide(
        _decide_command(
            create, command_id="cmd-d5", decision_id="gvd-d5",
            decision_event_id="evt-d7", effect_event_id="evt-d8",
        ), create.proposal_id, NOW
    ).error is None
    archive = _proposal(
        proposal_id="prp-d5-2", memory_id="mem-d5", submit_event_id="evt-d9",
        evidence_refs=(evidence.event_id,), proposal_type="change_memory_state",
        proposed_patch={"state": "archived", "supersedes_memory_ids": (), "contested_by_event_ids": ()},
    )
    assert service.submit(_submit_command(archive), archive).error is None
    assert governor.decide(
        _decide_command(
            archive, command_id="cmd-d6", decision_id="gvd-d6",
            decision_event_id="evt-da", effect_event_id="evt-db",
            memory_version=1,
        ), archive.proposal_id, NOW
    ).error is None
    before = _database_snapshot(database)
    transition = _proposal(
        proposal_id="prp-d5-3", memory_id="mem-d5", submit_event_id="evt-dc",
        evidence_refs=(evidence.event_id,), proposal_type="change_memory_state",
        proposed_patch={"state": "superseded", "supersedes_memory_ids": (), "contested_by_event_ids": ()},
    )
    assert service.submit(_submit_command(transition), transition).error is None
    before_decide = _database_snapshot(database)

    result = governor.decide(
        _decide_command(
            transition, command_id="cmd-d7", decision_id="gvd-d7",
            decision_event_id="evt-dd", effect_event_id="evt-de",
            memory_version=2,
        ), transition.proposal_id, NOW
    )

    assert result.error is not None
    assert result.error.code is CoreErrorCode.INVALID_MEMORY_TRANSITION
    assert _database_snapshot(database) == before_decide
    assert _database_snapshot(database) != before
    stored = _load(database, "mem-d5")
    assert isinstance(stored, AutobiographicalMemory)
    assert stored.state == "archived"
    assert case.identity.source_id == "AC-015"
