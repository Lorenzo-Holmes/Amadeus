from __future__ import annotations

from pydantic import ValidationError

import amadeus_core.governance.governor as governor_module
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.proposals import GovernorDecision
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from tests.governance.test_model_commit_boundary import (
    NOW,
    _database_snapshot,
    _decide_command,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


def test_internal_decision_schema_drift_is_not_reported_as_caller_input(
    database: SQLiteDatabase,
    monkeypatch,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-c2",
        memory_id="mem-c2",
        submit_event_id="evt-c2",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c2"),
        proposal,
    ).error is None
    before = _database_snapshot(database)
    original_seal_record = governor_module.seal_record
    try:
        GovernorDecision.model_validate({})
    except ValidationError as error:
        internal_schema_error = error
    else:  # pragma: no cover - the contract has required fields
        raise AssertionError("GovernorDecision unexpectedly accepted an empty value")

    def fail_decision_schema(record_type, values):
        if record_type is GovernorDecision:
            raise internal_schema_error
        return original_seal_record(record_type, values)

    monkeypatch.setattr(governor_module, "seal_record", fail_decision_schema)

    result = _memory_governor(database).decide(
        _decide_command(
            proposal,
            command_id="cmd-c3",
            decision_id="gvd-c2",
            decision_event_id="evt-c3",
            effect_event_id="evt-c4",
        ),
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.GOVERNOR_POLICY_MISMATCH
    assert result.event_ids == ()
    assert _database_snapshot(database) == before
