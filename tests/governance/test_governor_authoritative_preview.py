from __future__ import annotations

from amadeus_core.governance.policy_v0_1 import POLICY_VERSION
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from tests.governance.test_model_commit_boundary import (
    NOW,
    _database_snapshot,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


def test_authoritative_preview_is_repeatable_and_side_effect_free(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-c1",
        memory_id="mem-c1",
        submit_event_id="evt-c1",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c1"),
        proposal,
    ).error is None
    governor = _memory_governor(database)
    before = _database_snapshot(database)

    first = governor.preview_authoritative(
        proposal.proposal_id,
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    second = governor.preview_authoritative(
        proposal.proposal_id,
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert first == second
    assert first.result == "commit"
    assert first.evidence_refs == (evidence.event_id,)
    assert _database_snapshot(database) == before
