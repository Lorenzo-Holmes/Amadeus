from __future__ import annotations

from typing import Any

import pytest

from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.repository import AuthorityRepository
from tests.governance.test_model_commit_boundary import (
    NOW,
    _decide_command,
    _load,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase


@pytest.mark.parametrize(
    (
        "proposal_type",
        "proposed_patch",
        "expected_event_type",
        "field_name",
        "expected_value",
    ),
    (
        (
            "change_expression_policy",
            {
                "expression_policy": {
                    "mode": "restricted",
                    "reason_refs": ("evt-b4",),
                }
            },
            "memory_expression_policy_changed",
            "expression_policy",
            {"mode": "restricted", "reason_refs": ("evt-b4",)},
        ),
        (
            "set_importance",
            {"importance": 0.9},
            "memory_state_changed",
            "importance",
            0.9,
        ),
        (
            "set_consolidation",
            {"consolidation_state": "stable"},
            "memory_state_changed",
            "consolidation_state",
            "stable",
        ),
    ),
)
def test_real_commit_routes_each_memory_update_profile_to_its_ledger_effect(
    database: SQLiteDatabase,
    proposal_type: str,
    proposed_patch: dict[str, object],
    expected_event_type: str,
    field_name: str,
    expected_value: Any,
) -> None:
    evidence = _seed_evidence_event(database)
    service = ProposalService(database)
    governor = _memory_governor(database)

    create = _proposal(
        proposal_id="prp-b2",
        memory_id="mem-b2",
        submit_event_id="evt-b5",
        evidence_refs=(evidence.event_id,),
    )
    assert service.submit(
        _submit_command(create, command_id="cmd-b5"),
        create,
    ).error is None
    created = governor.decide(
        _decide_command(
            create,
            command_id="cmd-b6",
            decision_id="gvd-b2",
            decision_event_id="evt-b6",
            effect_event_id="evt-b7",
        ),
        create.proposal_id,
        NOW,
    )
    assert created.error is None
    assert isinstance(created.value, GovernorDecision)
    assert created.value.result == "commit"

    update = _proposal(
        proposal_id="prp-b8",
        memory_id="mem-b2",
        submit_event_id="evt-b8",
        evidence_refs=(evidence.event_id,),
        proposal_type=proposal_type,
        proposed_patch=proposed_patch,
    )
    assert service.submit(
        _submit_command(update, command_id="cmd-b8"),
        update,
    ).error is None
    committed = governor.decide(
        _decide_command(
            update,
            command_id="cmd-b9",
            decision_id="gvd-b3",
            decision_event_id="evt-b9",
            effect_event_id="evt-ba",
            memory_version=1,
        ),
        update.proposal_id,
        NOW,
    )

    assert committed.error is None
    assert isinstance(committed.value, GovernorDecision)
    assert committed.value.result == "commit"
    assert committed.event_ids == ("evt-b9", "evt-ba")

    stored_memory = _load(database, "mem-b2")
    assert isinstance(stored_memory, AutobiographicalMemory)
    assert stored_memory.version == 2
    assert stored_memory.semantic_version == 2
    assert stored_memory.governor_decision_id == "gvd-b3"
    actual_value = getattr(stored_memory, field_name)
    if hasattr(actual_value, "model_dump"):
        actual_value = actual_value.model_dump(mode="python")
    assert actual_value == expected_value

    connection = database.connect()
    try:
        effect_event = AuthorityRepository(connection).get_validated("evt-ba")
        replay = replay_ledger(connection, update.branch_id)
    finally:
        connection.close()
    assert effect_event is not None
    assert effect_event.event_type == expected_event_type
    assert replay.events[-1] == effect_event
