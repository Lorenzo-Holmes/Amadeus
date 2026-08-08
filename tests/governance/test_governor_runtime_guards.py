from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.governance.governor import MemoryGovernor
from amadeus_core.governance.policy_v0_1 import GovernorPolicyV01
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from tests.governance.test_model_commit_boundary import (
    NOW,
    _database_snapshot,
    _decide_command,
    _decision_attestor,
    _governor_verifier,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


def _memory_governor(
    database: SQLiteDatabase,
    *,
    now: datetime = NOW,
) -> MemoryGovernor:
    return MemoryGovernor(
        database,
        GovernorPolicyV01(),
        command_verifier=_governor_verifier(),
        decision_attestor=_decision_attestor(),
        clock=FixedClock(now),
    )


def _submitted_create(database: SQLiteDatabase):
    evidence = _seed_evidence_event(database)
    proposal = _proposal(evidence_refs=(evidence.event_id,))
    submitted = ProposalService(database).submit(_submit_command(proposal), proposal)
    assert submitted.error is None
    return proposal


@pytest.mark.parametrize(
    "attribute",
    (
        "_database",
        "_policy",
        "_command_verifier",
        "_decision_attestor",
        "_clock",
        "_unit_of_work",
    ),
)
@pytest.mark.parametrize("operation", ("set", "delete"))
def test_memory_governor_runtime_configuration_is_immutable(
    database: SQLiteDatabase,
    attribute: str,
    operation: str,
) -> None:
    governor = _memory_governor(database)

    with pytest.raises(AttributeError):
        if operation == "set":
            setattr(governor, attribute, object())
        else:
            delattr(governor, attribute)


def test_forged_command_cannot_commit_by_replacing_the_verifier(
    database: SQLiteDatabase,
) -> None:
    proposal = _submitted_create(database)
    governor = _memory_governor(database)
    before = _database_snapshot(database)

    class _AllowAllVerifier:
        @staticmethod
        def verify(_command: object) -> bool:
            return True

    try:
        setattr(governor, "_command_verifier", _AllowAllVerifier())
    except AttributeError:
        pass

    result = governor.decide(
        _decide_command(proposal, authenticate=False),
        proposal.proposal_id,
        NOW,
    )

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == ()
    assert _database_snapshot(database) == before


def test_default_system_clock_method_cannot_be_replaced(
    database: SQLiteDatabase,
) -> None:
    governor = MemoryGovernor(
        database,
        GovernorPolicyV01(),
        command_verifier=_governor_verifier(),
        decision_attestor=_decision_attestor(),
    )
    before = _database_snapshot(database)

    with pytest.raises(AttributeError):
        governor._clock.now = lambda: NOW  # type: ignore[method-assign]

    assert _database_snapshot(database) == before


def test_memory_governor_rejects_structural_untrusted_clock(
    database: SQLiteDatabase,
) -> None:
    class _StructuralClock:
        @staticmethod
        def now() -> datetime:
            return NOW

    with pytest.raises(TypeError, match="trusted Clock"):
        MemoryGovernor(
            database,
            GovernorPolicyV01(),
            command_verifier=_governor_verifier(),
            decision_attestor=_decision_attestor(),
            clock=_StructuralClock(),
        )


def test_nested_database_path_cannot_be_redirected(
    database: SQLiteDatabase,
    tmp_path: Path,
) -> None:
    governor = _memory_governor(database)
    original_path = database.path
    before = _database_snapshot(database)

    with pytest.raises(AttributeError):
        governor._database._path = tmp_path / "redirected.sqlite3"

    assert database.path == original_path
    assert _database_snapshot(database) == before


def test_nested_unit_of_work_clock_cannot_be_replaced(
    database: SQLiteDatabase,
) -> None:
    governor = _memory_governor(database)
    original_clock = governor._unit_of_work._clock
    before = _database_snapshot(database)

    with pytest.raises(AttributeError):
        governor._unit_of_work._clock = FixedClock(NOW + timedelta(days=1))

    assert governor._unit_of_work._clock is original_clock
    assert _database_snapshot(database) == before


def test_receipt_miss_uses_trusted_clock_and_rejects_backdated_commit(
    database: SQLiteDatabase,
) -> None:
    proposal = _submitted_create(database)
    command = _decide_command(proposal, now=NOW)
    before = _database_snapshot(database)

    governor = _memory_governor(
        database,
        now=proposal.expires_at + timedelta(seconds=1),
    )
    with pytest.raises(AttributeError):
        governor._clock._instant = NOW

    result = governor.decide(command, proposal.proposal_id, NOW)

    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.PROPOSAL_TERMINAL
    assert result.event_ids == ()
    assert _database_snapshot(database) == before


def test_exact_receipt_replay_does_not_reapply_current_time_gate(
    database: SQLiteDatabase,
) -> None:
    proposal = _submitted_create(database)
    command = _decide_command(proposal, now=NOW)
    first = _memory_governor(database).decide(command, proposal.proposal_id, NOW)
    assert first.error is None
    assert first.value is not None
    after_first = _database_snapshot(database)

    replayed = _memory_governor(
        database,
        now=proposal.expires_at + timedelta(seconds=1),
    ).decide(command, proposal.proposal_id, NOW)

    assert replayed.replayed is True
    assert replayed.error is None
    assert replayed.value == first.value
    assert replayed.event_ids == first.event_ids
    assert _database_snapshot(database) == after_first
