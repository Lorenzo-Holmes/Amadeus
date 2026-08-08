from __future__ import annotations

from collections.abc import Mapping

import pytest

from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.storage.database import SQLiteDatabase

from tests.governance.test_proposals import (
    GENESIS_EVENT_ID,
    NOW,
    FixedClock,
    _decision,
    _defer_command,
    _full_database_snapshot,
    _proposal,
    _reseal_proposal,
    _submit_command,
)


def _valid_create_memory_patch(memory_id: str) -> dict[str, object]:
    return {
        "memory_id": memory_id,
        "semantic_kind": "episode",
        "state": "active",
        "importance": 0.5,
        "consolidation_state": "candidate",
        "expression_policy": {"mode": "eligible", "reason_refs": ()},
        "evidence_event_refs": (GENESIS_EVENT_ID,),
        "supersedes_memory_ids": (),
        "contested_by_event_ids": (),
    }


def _create_memory_proposal(
    *,
    memory_id: str,
    target_refs: tuple[str, ...] | None = None,
    patch_updates: Mapping[str, object] | None = None,
):
    patch = _valid_create_memory_patch(memory_id)
    patch.update(patch_updates or {})
    return _reseal_proposal(
        _proposal(proposal_id="prp-d1", submitted_event_id="evt-d1"),
        proposal_type="create_memory",
        target_refs=target_refs if target_refs is not None else (memory_id,),
        proposed_patch=patch,
    )


@pytest.mark.parametrize(
    ("case", "expected_code"),
    (
        pytest.param(
            "unknown_missing_evidence_type",
            CoreErrorCode.HEADER_BODY_MISMATCH,
            id="defer-rejects-non-ledger-event-type",
        ),
        pytest.param(
            "deep_executable_or_credential_key",
            CoreErrorCode.HEADER_BODY_MISMATCH,
            id="patch-rejects-deep-sql-and-credential-token",
        ),
        pytest.param(
            "memory_id_wrong_record_type",
            CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH,
            id="create-memory-requires-mem-prefix",
        ),
        pytest.param(
            "memory_id_not_target",
            CoreErrorCode.HEADER_BODY_MISMATCH,
            id="create-memory-id-must-equal-target",
        ),
        pytest.param(
            "multiple_create_targets",
            CoreErrorCode.HEADER_BODY_MISMATCH,
            id="create-memory-requires-sole-target",
        ),
        pytest.param(
            "patch_evidence_not_proposal_evidence",
            CoreErrorCode.HEADER_BODY_MISMATCH,
            id="create-memory-evidence-must-be-subset",
        ),
        pytest.param(
            "patch_record_ref_outside_command_scope",
            CoreErrorCode.VAULT_SCOPE_MISMATCH,
            id="create-memory-patch-refs-must-be-in-scope",
        ),
    ),
)
def test_proposal_patch_and_defer_conditions_fail_closed_without_writes(
    case: str,
    expected_code: CoreErrorCode,
    database: SQLiteDatabase,
) -> None:
    from amadeus_core.governance.proposal_service import ProposalService

    service = ProposalService(database, clock=FixedClock(NOW))

    if case == "unknown_missing_evidence_type":
        proposal = _proposal(proposal_id="prp-d1", submitted_event_id="evt-d1")
        assert (
            service.submit(_submit_command(proposal, "evt-d1"), proposal).error
            is None
        )
        conditions = DeferConditions(
            missing_evidence_types=("fabricated_evidence_type",),
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
        result = service.defer(command, proposal.proposal_id, conditions)
    else:
        if case == "deep_executable_or_credential_key":
            proposal = _create_memory_proposal(
                memory_id="mem-d1",
                patch_updates={
                    "expression_policy": {
                        "mode": "eligible",
                        "reason_refs": (),
                        "sql": "SELECT * FROM authority_records",
                        "credential": {"token": "fixture-secret"},
                    }
                },
            )
        elif case == "memory_id_wrong_record_type":
            proposal = _create_memory_proposal(memory_id="req-d1")
        elif case == "memory_id_not_target":
            proposal = _create_memory_proposal(
                memory_id="mem-d1",
                target_refs=("mem-d2",),
            )
        elif case == "multiple_create_targets":
            proposal = _create_memory_proposal(
                memory_id="mem-d1",
                target_refs=("mem-d1", "mem-d2"),
            )
        elif case == "patch_evidence_not_proposal_evidence":
            proposal = _create_memory_proposal(
                memory_id="mem-d1",
                patch_updates={"evidence_event_refs": ("evt-d4",)},
            )
        else:
            assert case == "patch_record_ref_outside_command_scope"
            proposal = _create_memory_proposal(
                memory_id="mem-d1",
                patch_updates={"supersedes_memory_ids": ("mem-d4",)},
            )
        command = _submit_command(proposal, "evt-d1")
        before = _full_database_snapshot(database)
        result = service.submit(command, proposal)

    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == expected_code
    assert _full_database_snapshot(database) == before
