from __future__ import annotations

from copy import deepcopy
from typing import Any

from amadeus_core.contracts.commands import (
    MutationCommandEnvelope,
    compute_command_hash,
)
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.repository import AuthorityRepository
from tests.governance.test_model_commit_boundary import (
    NOW,
    _decide_command,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


def test_decide_uses_one_exact_command_snapshot_for_every_boundary(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-d1",
        memory_id="mem-d1",
        submit_event_id="evt-d1",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-d1"),
        proposal,
    ).error is None
    signed = _decide_command(
        proposal,
        command_id="cmd-d2",
        decision_id="gvd-d1",
        decision_event_id="evt-d2",
        effect_event_id="evt-d3",
    )
    changed_after_first_read = signed.model_copy(
        update={"command_id": "cmd-d3"}
    )
    serialized_values = (
        signed.model_dump(mode="python"),
        changed_after_first_read.model_dump(mode="python"),
    )
    read_count = 0

    class _NonStableEnvelope(MutationCommandEnvelope):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal read_count
            value = serialized_values[min(read_count, 1)]
            read_count += 1
            return deepcopy(value)

    supplied = _NonStableEnvelope.model_validate(
        signed.model_dump(mode="python")
    )

    result = _memory_governor(database).decide(
        supplied,
        proposal.proposal_id,
        NOW,
    )

    assert result.error is None
    assert result.value is not None
    assert read_count == 1
    connection = database.connect()
    try:
        decision_event = AuthorityRepository(connection).get_validated("evt-d2")
    finally:
        connection.close()
    assert decision_event is not None
    assert decision_event.mutation_command_id == signed.command_id
    assert decision_event.mutation_command_hash == compute_command_hash(signed)


def test_decide_rejects_snapshot_that_is_not_the_exact_base_envelope(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database, event_id="evt-e0")
    proposal = _proposal(
        proposal_id="prp-e1",
        memory_id="mem-e1",
        submit_event_id="evt-e1",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-e1"),
        proposal,
    ).error is None
    signed = _decide_command(
        proposal,
        command_id="cmd-e2",
        decision_id="gvd-e1",
        decision_event_id="evt-e2",
        effect_event_id="evt-e3",
    )
    read_count = 0

    class _SelfReturningEnvelope(MutationCommandEnvelope):
        def model_dump(self, *args: Any, **kwargs: Any) -> Any:
            nonlocal read_count
            del args, kwargs
            read_count += 1
            return self

    supplied = _SelfReturningEnvelope.model_validate(
        signed.model_dump(mode="python")
    )

    result = _memory_governor(database).decide(
        supplied,
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code == CoreErrorCode.HEADER_BODY_MISMATCH
    assert read_count == 1
