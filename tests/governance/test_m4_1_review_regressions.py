from __future__ import annotations

from collections.abc import Mapping

import pytest

from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch, Lineage
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.records import record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository

from tests.governance.conftest import (
    BRANCH_ID,
    DEPLOYMENT_POLICY_REF,
    GENESIS_EVENT_ID,
    IDENTITY_ID,
    LINEAGE_ID,
    VAULT_ID,
    NOW,
)
from tests.governance.test_proposal_patch_guards import _valid_create_memory_patch
from tests.governance.test_proposals import (
    FixedClock,
    _decision,
    _defer_command,
    _expire_command,
    _full_database_snapshot,
    _load,
    _proposal,
    _reseal_proposal,
    _seed_proposal,
    _submit_command,
)


ROOT_BRANCH_ID = "brn-b1"


def _reseal(model, updates: Mapping[str, object], *, header_branch_id: str | None = None):
    body = model.model_dump(mode="python")
    body.update(updates)
    header = dict(body["record_header"])
    if header_branch_id is not None:
        header["branch_id"] = header_branch_id
    header["content_hash"] = "0" * 64
    body["record_header"] = header
    draft = type(model).model_validate(body)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": compute_record_content_hash(draft)}
            )
        }
    )


@pytest.fixture
def non_root_active_branch(database: SQLiteDatabase) -> SQLiteDatabase:
    connection = database.connect()
    try:
        repository = AuthorityRepository(connection)
        lineage = repository.get_validated(LINEAGE_ID)
        active_branch = repository.get_validated(BRANCH_ID)
        assert isinstance(lineage, Lineage)
        assert isinstance(active_branch, Branch)

        root_body = active_branch.model_dump(mode="python")
        root_body.update(
            {
                "branch_id": ROOT_BRANCH_ID,
                "parent_branch_ids": (),
                "base_ledger_seq": 0,
                "status": "inactive",
                "deactivated_at": NOW,
                "version": 1,
            }
        )
        root_header = dict(root_body["record_header"])
        root_header.update(
            {
                "record_id": ROOT_BRANCH_ID,
                "branch_id": ROOT_BRANCH_ID,
                "content_hash": "0" * 64,
            }
        )
        root_body["record_header"] = root_header
        root_draft = Branch.model_validate(root_body)
        root_branch = root_draft.model_copy(
            update={
                "record_header": root_draft.record_header.model_copy(
                    update={"content_hash": compute_record_content_hash(root_draft)}
                )
            }
        )
        current_branch = _reseal(
            active_branch,
            {
                "parent_branch_ids": (ROOT_BRANCH_ID,),
                "base_ledger_seq": 1,
                "version": active_branch.version + 1,
            },
        )
        updated_lineage = _reseal(
            lineage,
            {
                "root_branch_id": ROOT_BRANCH_ID,
                "version": lineage.version + 1,
            },
            header_branch_id=ROOT_BRANCH_ID,
        )

        connection.execute("BEGIN IMMEDIATE")
        writer = AuthorityRepository(
            connection,
            allowed_target_refs=(ROOT_BRANCH_ID, BRANCH_ID, LINEAGE_ID),
        )
        writer.save_authoritative("branch", root_branch.model_dump(mode="python"))
        writer.save_authoritative(
            "branch",
            current_branch.model_dump(mode="python"),
        )
        writer.save_authoritative(
            "lineage",
            updated_lineage.model_dump(mode="python"),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    return database


def test_request_submit_accepts_active_non_root_branch(
    non_root_active_branch: SQLiteDatabase,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    del non_root_active_branch
    request = request_factory(
        "correction_request",
        request_id="req-e1",
        event_id="evt-e1",
    )
    result = request_service.submit(
        request_command_factory(request, event_id="evt-e1"),
        request,
    )

    assert result.error is None
    assert result.value is not None
    assert result.value.branch_id == BRANCH_ID
    assert result.event_ids == ("evt-e1",)


def test_proposal_submit_and_detector_accept_active_non_root_branch(
    non_root_active_branch: SQLiteDatabase,
) -> None:
    service = ProposalService(non_root_active_branch, clock=FixedClock(NOW))
    submitted = _proposal(proposal_id="prp-e2", submitted_event_id="evt-e2")
    result = service.submit(_submit_command(submitted, "evt-e2"), submitted)

    assert result.error is None
    assert result.value is not None
    assert result.value.branch_id == BRANCH_ID
    assert result.event_ids == ("evt-e2",)

    expiring = _proposal(proposal_id="prp-e3", submitted_event_id="evt-e3")
    _seed_proposal(non_root_active_branch, expiring)
    before = _full_database_snapshot(non_root_active_branch)
    assert service.find_expired(expiring.expires_at) == (
        submitted.proposal_id,
        expiring.proposal_id,
    )
    assert _full_database_snapshot(non_root_active_branch) == before


def test_submit_receipt_replays_original_value_after_proposal_advances(
    database: SQLiteDatabase,
) -> None:
    service = ProposalService(database, clock=FixedClock(NOW))
    proposal = _proposal(proposal_id="prp-e4", submitted_event_id="evt-e4")
    submit_command = _submit_command(proposal, "evt-e4")
    first = service.submit(submit_command, proposal)
    assert first.error is None

    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-e4",
        decision_event_id="evt-e5",
        proposal_event_id="evt-e6",
    )
    advanced = service.defer(
        _defer_command(
            proposal,
            decision,
            conditions,
            decision_event_id="evt-e5",
            proposal_event_id="evt-e6",
        ),
        proposal.proposal_id,
        conditions,
    )
    assert advanced.error is None
    assert advanced.value is not None
    assert advanced.value.status == "deferred"

    before = _full_database_snapshot(database)
    replay = service.submit(submit_command, proposal)

    assert replay.replayed is True
    assert replay.error is None
    assert replay.value == first.value
    assert replay.event_ids == first.event_ids == ("evt-e4",)
    assert _load(database, proposal.proposal_id) == advanced.value
    assert _full_database_snapshot(database) == before


def test_defer_receipt_replays_original_value_after_proposal_expires(
    database: SQLiteDatabase,
) -> None:
    service = ProposalService(database, clock=FixedClock(NOW))
    proposal = _proposal(proposal_id="prp-ea", submitted_event_id="evt-ea")
    assert service.submit(_submit_command(proposal, "evt-ea"), proposal).error is None
    conditions = DeferConditions(
        missing_evidence_types=("correction_request_submitted",),
        reopen_not_before=NOW,
    )
    decision = _decision(
        proposal,
        conditions,
        decision_id="gvd-ea",
        decision_event_id="evt-eb",
        proposal_event_id="evt-ec",
    )
    defer_command = _defer_command(
        proposal,
        decision,
        conditions,
        decision_event_id="evt-eb",
        proposal_event_id="evt-ec",
    )
    first = service.defer(defer_command, proposal.proposal_id, conditions)
    assert first.error is None
    assert first.value is not None

    expired = service.expire(
        _expire_command(first.value, "evt-ed", now=proposal.expires_at),
        proposal.proposal_id,
        proposal.expires_at,
    )
    assert expired.error is None
    assert expired.value is not None
    before = _full_database_snapshot(database)

    replay = service.defer(defer_command, proposal.proposal_id, conditions)

    assert replay.replayed is True
    assert replay.error is None
    assert replay.value == first.value
    assert replay.event_ids == first.event_ids == ("evt-eb", "evt-ec")
    assert _load(database, proposal.proposal_id) == expired.value
    assert _full_database_snapshot(database) == before


@pytest.mark.parametrize(
    ("proposal_type", "patch"),
    (
        ("change_memory_state", {"state": "fabricated"}),
        ("change_memory_state", {"contested_by_event_ids": ()}),
        (
            "change_expression_policy",
            {
                "expression_policy": {
                    "mode": "restricted",
                    "reason_refs": ("evt-e7",),
                }
            },
        ),
        ("set_importance", {"importance": "high"}),
        ("set_consolidation", {"consolidation_state": "forever"}),
        ("lifecycle_transition", {"lifecycle_state": "contact_paused"}),
        ("lifecycle_transition", {"reason_refs": ()}),
        ("lifecycle_transition", {"requested_action": "drop_database"}),
        (
            "maintenance_trigger",
            {
                "requested_action": "terminate",
                "reason_code": "routine",
                "scope_refs": (),
            },
        ),
    ),
)
def test_proposal_patch_values_are_closed_before_authority_write(
    proposal_type: str,
    patch: dict[str, object],
    database: SQLiteDatabase,
) -> None:
    service = ProposalService(database, clock=FixedClock(NOW))
    proposal = _reseal_proposal(
        _proposal(proposal_id="prp-e7", submitted_event_id="evt-e7"),
        proposal_type=proposal_type,
        proposed_patch=patch,
    )
    command = _submit_command(proposal, "evt-e7")
    before = _full_database_snapshot(database)

    result = service.submit(command, proposal)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.HEADER_BODY_MISMATCH
    assert _full_database_snapshot(database) == before


def test_request_and_proposal_submit_accept_command_causation(
    database: SQLiteDatabase,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    request = request_factory(
        "correction_request",
        request_id="req-e8",
        event_id="evt-e8",
    )
    request_command = request_command_factory(request, event_id="evt-e8")
    request_payload = dict(request_command.payload)
    request_payload["causation_id"] = "cmd-a1"
    request_command = request_command.model_copy(update={"payload": request_payload})
    request_result = request_service.submit(request_command, request)
    assert request_result.error is None

    proposal = _proposal(proposal_id="prp-e9", submitted_event_id="evt-e9")
    proposal_command = _submit_command(proposal, "evt-e9")
    proposal_payload = dict(proposal_command.payload)
    proposal_payload["causation_id"] = "cmd-a1"
    proposal_command = proposal_command.model_copy(update={"payload": proposal_payload})
    proposal_result = ProposalService(database, clock=FixedClock(NOW)).submit(
        proposal_command,
        proposal,
    )
    assert proposal_result.error is None

    connection = database.connect()
    try:
        repository = AuthorityRepository(connection)
        assert repository.get_validated("evt-e8").causation_id == "cmd-a1"
        assert repository.get_validated("evt-e9").causation_id == "cmd-a1"
    finally:
        connection.close()

@pytest.mark.parametrize(
    ("target_ref", "requested_action"),
    (
        (IDENTITY_ID, "sealed"),
        (BRANCH_ID, "contact_paused"),
        (VAULT_ID, "quarantined"),
    ),
)
def test_lifecycle_patch_state_is_bound_to_target_type(
    target_ref: str,
    requested_action: str,
    database: SQLiteDatabase,
) -> None:
    service = ProposalService(database, clock=FixedClock(NOW))
    proposal = _reseal_proposal(
        _proposal(proposal_id="prp-eb", submitted_event_id="evt-eb"),
        target_refs=(target_ref,),
        proposed_patch={"requested_action": requested_action},
    )
    before = _full_database_snapshot(database)

    result = service.submit(_submit_command(proposal, "evt-eb"), proposal)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.HEADER_BODY_MISMATCH
    assert _full_database_snapshot(database) == before


def _seed_same_vault_memory(database: SQLiteDatabase, memory_id: str) -> None:
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
                created_by_event_id=GENESIS_EVENT_ID,
                deployment_policy_ref=DEPLOYMENT_POLICY_REF,
            ),
            "memory_id": memory_id,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "governing_vault_id": VAULT_ID,
            "semantic_kind": "episode",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {
                "mode": "eligible",
                "reason_refs": (GENESIS_EVENT_ID,),
            },
            "evidence_event_refs": (GENESIS_EVENT_ID,),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
            "governor_decision_id": "gvd-ea",
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
            allowed_target_refs=(memory_id,),
        ).save_authoritative(
            "autobiographical_memory",
            memory.model_dump(mode="python"),
        )
        connection.commit()
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def _create_memory_with_supersedes(
    *,
    memory_id: str,
    supersedes: tuple[str, ...],
):
    patch = _valid_create_memory_patch(memory_id)
    patch["supersedes_memory_ids"] = supersedes
    return _reseal_proposal(
        _proposal(proposal_id="prp-ec", submitted_event_id="evt-ec"),
        proposal_type="create_memory",
        target_refs=(memory_id,),
        proposed_patch=patch,
    )


def _with_nested_scope(command, nested_refs: tuple[str, ...]):
    payload = dict(command.payload)
    base_scope = tuple(payload["scope_refs"])
    payload["scope_refs"] = (*base_scope[:-1], *nested_refs, base_scope[-1])
    return command.model_copy(update={"payload": payload})


def test_create_memory_validates_and_accepts_existing_superseded_memory(
    database: SQLiteDatabase,
) -> None:
    old_memory_id = "mem-ea"
    _seed_same_vault_memory(database, old_memory_id)
    proposal = _create_memory_with_supersedes(
        memory_id="mem-eb",
        supersedes=(old_memory_id,),
    )
    command = _with_nested_scope(
        _submit_command(proposal, "evt-ec"),
        (old_memory_id,),
    )

    result = ProposalService(database, clock=FixedClock(NOW)).submit(
        command,
        proposal,
    )

    assert result.error is None
    assert result.value == proposal
    assert result.event_ids == ("evt-ec",)


@pytest.mark.parametrize("superseded_id", ("mem-eb", "mem-ec"))
def test_create_memory_rejects_self_or_missing_superseded_memory(
    superseded_id: str,
    database: SQLiteDatabase,
) -> None:
    proposal = _create_memory_with_supersedes(
        memory_id="mem-eb",
        supersedes=(superseded_id,),
    )
    command = _with_nested_scope(
        _submit_command(proposal, "evt-ec"),
        (() if superseded_id == "mem-eb" else (superseded_id,)),
    )
    before = _full_database_snapshot(database)

    result = ProposalService(database, clock=FixedClock(NOW)).submit(
        command,
        proposal,
    )

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == CoreErrorCode.HEADER_BODY_MISMATCH
    assert _full_database_snapshot(database) == before


def test_proposal_submit_result_is_not_invalidated_by_post_commit_advance(
    monkeypatch,
    database: SQLiteDatabase,
) -> None:
    service = ProposalService(database, clock=FixedClock(NOW))
    original_get = service._reader.get_validated

    def advanced_get(record_id: str):
        current = original_get(record_id)
        if isinstance(current, Proposal):
            return reseal_update(
                current,
                {
                    "status": "deferred",
                    "deferred_at": NOW,
                    "defer_conditions": DeferConditions(
                        missing_evidence_types=("correction_request_submitted",),
                        reopen_not_before=NOW,
                    ),
                    "version": current.version + 1,
                },
            )
        return current

    monkeypatch.setattr(service._reader, "get_validated", advanced_get)
    proposal = _proposal(proposal_id="prp-ed", submitted_event_id="evt-ed")

    result = service.submit(_submit_command(proposal, "evt-ed"), proposal)

    assert result.error is None
    assert result.value == proposal
    assert result.replayed is False


def test_request_submit_result_is_not_invalidated_by_post_commit_advance(
    monkeypatch,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    original_get = request_service._reader.get_validated

    def advanced_get(record_id: str):
        current = original_get(record_id)
        if isinstance(current, MemoryRequest):
            return reseal_update(
                current,
                {"status": "under_review", "version": current.version + 1},
            )
        return current

    monkeypatch.setattr(request_service._reader, "get_validated", advanced_get)
    request = request_factory(
        "correction_request",
        request_id="req-ed",
        event_id="evt-ee",
    )

    result = request_service.submit(
        request_command_factory(request, event_id="evt-ee"),
        request,
    )

    assert result.error is None
    assert result.value == request
    assert result.replayed is False

