from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import MutationCommandEnvelope, compute_command_hash
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.governance.policy_v0_1 import POLICY_VERSION
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.ledger import replay_ledger
from tests.governance.conftest import _bootstrap, _seed_vault
from tests.governance.test_model_commit_boundary import (
    BRANCH_ID,
    NOW,
    _decide_command,
    _expire_command,
    _governor_signer,
    _load,
    _memory_governor,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


def _logical_database_snapshot(database: SQLiteDatabase) -> tuple[object, ...]:
    """All user-table values, ordered without relying on SQLite rowid/layout."""
    connection = database.connect()
    try:
        tables = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        )
        snapshot: list[object] = []
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = tuple(
                row[1]
                for row in connection.execute(f"PRAGMA table_info({quoted})")
            )
            rows = tuple(
                sorted(
                    (tuple(row[column] for column in columns) for row in connection.execute(f"SELECT * FROM {quoted}")),
                    key=repr,
                )
            )
            snapshot.append((table, columns, rows))
        return tuple(snapshot)
    finally:
        connection.close()


def _stored_proposal(database: SQLiteDatabase, proposal_id: str) -> Proposal:
    proposal = _load(database, proposal_id)
    assert isinstance(proposal, Proposal)
    return proposal


def _reverse_mappings(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _reverse_mappings(child) for key, child in reversed(tuple(value.items()))}
    if isinstance(value, tuple):
        return tuple(_reverse_mappings(child) for child in value)
    if isinstance(value, list):
        return [_reverse_mappings(child) for child in value]
    return value


def _reordered_command(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    raw = command.model_dump(mode="python")
    reordered = _reverse_mappings(raw)
    assert isinstance(reordered, dict)
    return MutationCommandEnvelope.model_validate(reordered)


def _record(database: SQLiteDatabase, record_id: str) -> dict[str, object] | None:
    record = _load(database, record_id)
    return None if record is None else record.model_dump(mode="json")


def _ledger_tail(database: SQLiteDatabase, start_after: int) -> tuple[object, ...]:
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        return tuple(
            (
                event.event_id,
                event.ledger_seq,
                event.previous_event_hash,
                event.event_hash,
                event.payload_ref,
                sha256_hex(canonical_json(payload)),
                payload,
            )
            for event, payload in zip(replay.events, replay.resolved_inline_payloads, strict=True)
            if event.ledger_seq > start_after
        )
    finally:
        connection.close()


def _ledger_watermark(database: SQLiteDatabase) -> int:
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(ledger_seq), 0) FROM ledger_events WHERE branch_id = ?",
            (BRANCH_ID,),
        ).fetchone()
        assert row is not None
        return int(row[0])
    finally:
        connection.close()


def _receipt(database: SQLiteDatabase, command_id: str) -> dict[str, object]:
    connection = database.connect()
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(command_receipts)")
        }
        required = {
            "actor_capability_id",
            "idempotency_scope_hash",
            "idempotency_key",
            "command_id",
            "command_hash",
            "result_json",
            "result_hash",
            "semantic_event_ids_json",
            "committed_at",
        }
        assert required <= columns
        row = connection.execute(
            """
            SELECT actor_capability_id, idempotency_scope_hash, idempotency_key,
                   command_id, command_hash, result_json, result_hash,
                   semantic_event_ids_json, committed_at
            FROM command_receipts WHERE command_id = ?
            """,
            (command_id,),
        ).fetchone()
        assert row is not None
        result = json.loads(row[5])
        return {
            "actor_capability_id": row[0],
            "idempotency_scope_hash": row[1],
            "idempotency_key": row[2],
            "command_id": row[3],
            "command_hash": row[4],
            "result_json": row[5],
            "result_hash": row[6],
            "semantic_event_ids_json": row[7],
            "output_value": result["value"],
            "committed_at": row[8],
        }
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("terminal_state", "expected_error"),
    (
        ("committed", CoreErrorCode.PROPOSAL_TERMINAL),
        ("rejected", CoreErrorCode.PROPOSAL_TERMINAL),
        ("deferred", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("expired", CoreErrorCode.PROPOSAL_TERMINAL),
    ),
)
def test_fresh_decide_rejects_non_pending_proposal_without_writes(
    database: SQLiteDatabase,
    terminal_state: str,
    expected_error: CoreErrorCode,
) -> None:
    suffix = {"committed": "a", "rejected": "b", "deferred": "c", "expired": "d"}[terminal_state]
    proposal_id = f"prp-44{suffix}"
    evidence = None
    if terminal_state in {"committed", "rejected"}:
        evidence = _seed_evidence_event(
            database,
            event_id=f"evt-44{suffix}-1",
            rejected=terminal_state == "rejected",
            source_event_ref=f"evt-44{suffix}-0",
        )
    proposal = _proposal(
        proposal_id=proposal_id,
        memory_id=f"mem-44{suffix}",
        submit_event_id=f"evt-44{suffix}-2",
        evidence_refs=() if evidence is None else (evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id=f"cmd-44{suffix}-1"),
        proposal,
    )
    assert submitted.error is None

    if terminal_state == "expired":
        expired = ProposalService(database).expire(
            _expire_command(
                _stored_proposal(database, proposal_id),
                event_id="evt-44d-3",
                now=proposal.expires_at,
            ),
            proposal_id,
            proposal.expires_at,
        )
        assert expired.error is None
    else:
        pending = _stored_proposal(database, proposal_id)
        first = _memory_governor(database).decide(
            _decide_command(
                pending,
                command_id=f"cmd-44{suffix}-2",
                decision_id=f"gvd-44{suffix}-1",
                decision_event_id=f"evt-44{suffix}-3",
                effect_event_id=f"evt-44{suffix}-4",
            ),
            proposal_id,
            NOW,
        )
        assert first.error is None

    stored = _stored_proposal(database, proposal_id)
    assert stored.status == terminal_state
    memory = _load(database, proposal.target_refs[0])
    memory_version: int | str = "absent" if memory is None else memory.version
    fresh = _decide_command(
        stored,
        command_id=f"cmd-44{suffix}-3",
        decision_id=f"gvd-44{suffix}-2",
        decision_event_id=f"evt-44{suffix}-5",
        effect_event_id=f"evt-44{suffix}-6",
        proposal_version=stored.version,
        memory_version=memory_version,
    )
    before = _logical_database_snapshot(database)

    result = _memory_governor(database).decide(fresh, proposal_id, NOW)

    assert result.value is None
    assert result.event_ids == ()
    assert result.replayed is False
    assert result.error is not None
    assert result.error.code is expected_error
    assert _logical_database_snapshot(database) == before


def test_reordered_equivalent_mappings_preserve_governor_outputs_end_to_end(
    tmp_path: Path,
) -> None:
    left_database = SQLiteDatabase(tmp_path / "m44-left.sqlite3")
    right_database = SQLiteDatabase(tmp_path / "m44-right.sqlite3")
    for database in (left_database, right_database):
        _bootstrap(database)
        _seed_vault(database)
        _seed_evidence_event(
            database,
            event_id="evt-44e-1",
            source_event_ref="evt-44e-0",
        )

    base_proposal = _proposal(
        proposal_id="prp-44e",
        memory_id="mem-44e",
        submit_event_id="evt-44e-2",
        evidence_refs=("evt-44e-1",),
    )
    left_proposal_raw = base_proposal.model_dump(mode="python")
    right_proposal_raw = _reverse_mappings(left_proposal_raw)
    assert isinstance(right_proposal_raw, dict)
    assert tuple(left_proposal_raw) != tuple(right_proposal_raw)
    assert tuple(left_proposal_raw["proposed_patch"]) != tuple(right_proposal_raw["proposed_patch"])
    assert canonical_json(left_proposal_raw) == canonical_json(right_proposal_raw)
    left_proposal = Proposal.model_validate(left_proposal_raw)
    right_proposal = Proposal.model_validate(right_proposal_raw)
    assert left_proposal.record_header.content_hash == right_proposal.record_header.content_hash

    left_submit = _submit_command(left_proposal, command_id="cmd-44e-1")
    right_submit = _reordered_command(_submit_command(right_proposal, command_id="cmd-44e-1"))
    assert tuple(left_submit.payload) != tuple(right_submit.payload)
    assert canonical_json(left_submit.model_dump(mode="python")) == canonical_json(right_submit.model_dump(mode="python"))
    assert compute_command_hash(left_submit) == compute_command_hash(right_submit)
    left_submitted = ProposalService(left_database, clock=FixedClock(NOW)).submit(left_submit, left_proposal)
    right_submitted = ProposalService(right_database, clock=FixedClock(NOW)).submit(right_submit, right_proposal)
    assert left_submitted.error is None
    assert right_submitted.error is None

    left_preview = _memory_governor(left_database).preview_authoritative(
        left_proposal.proposal_id, policy_version=POLICY_VERSION, now=NOW
    )
    right_preview = _memory_governor(right_database).preview_authoritative(
        right_proposal.proposal_id, policy_version=POLICY_VERSION, now=NOW
    )
    assert left_preview == right_preview

    left_decide = _decide_command(
        left_proposal,
        command_id="cmd-44e-2",
        decision_id="gvd-44e",
        decision_event_id="evt-44e-3",
        effect_event_id="evt-44e-4",
    )
    right_unsigned = _decide_command(
        right_proposal,
        command_id="cmd-44e-2",
        decision_id="gvd-44e",
        decision_event_id="evt-44e-3",
        effect_event_id="evt-44e-4",
        authenticate=False,
    )
    right_decide = _governor_signer().sign(_reordered_command(right_unsigned))
    assert tuple(left_decide.payload) != tuple(right_decide.payload)
    assert canonical_json(left_decide.model_dump(mode="python")) == canonical_json(right_decide.model_dump(mode="python"))
    assert compute_command_hash(left_decide) == compute_command_hash(right_decide)
    assert left_decide.payload["actor_attestation"] == right_decide.payload["actor_attestation"]

    left_watermark = _ledger_watermark(left_database)
    right_watermark = _ledger_watermark(right_database)
    left_first = _memory_governor(left_database).decide(left_decide, left_proposal.proposal_id, NOW)
    right_first = _memory_governor(right_database).decide(right_decide, right_proposal.proposal_id, NOW)
    assert left_first.error is None
    assert right_first.error is None
    assert isinstance(left_first.value, GovernorDecision)
    assert isinstance(right_first.value, GovernorDecision)
    assert left_first == right_first

    left_state = {
        "proposal": _record(left_database, left_proposal.proposal_id),
        "decision": _record(left_database, "gvd-44e"),
        "memory": _record(left_database, left_proposal.target_refs[0]),
        "ledger": _ledger_tail(left_database, left_watermark),
        "submit_receipt": _receipt(left_database, "cmd-44e-1"),
        "decide_receipt": _receipt(left_database, "cmd-44e-2"),
    }
    right_state = {
        "proposal": _record(right_database, right_proposal.proposal_id),
        "decision": _record(right_database, "gvd-44e"),
        "memory": _record(right_database, right_proposal.target_refs[0]),
        "ledger": _ledger_tail(right_database, right_watermark),
        "submit_receipt": _receipt(right_database, "cmd-44e-1"),
        "decide_receipt": _receipt(right_database, "cmd-44e-2"),
    }
    assert left_state == right_state
    assert left_state["proposal"] is not None
    assert left_state["decision"] is not None
    assert left_state["memory"] is not None
    assert left_state["proposal"] == left_preview.proposal_after.model_dump(mode="json")
    assert right_state["proposal"] == right_preview.proposal_after.model_dump(mode="json")
    assert left_state["decision"]["input_state_hash"] == right_state["decision"]["input_state_hash"]
    assert left_state["decision"]["output_state_hash"] == right_state["decision"]["output_state_hash"]
    assert left_state["decision"]["reason_codes"] == right_state["decision"]["reason_codes"]
    assert left_state["decision"]["evidence_refs"] == right_state["decision"]["evidence_refs"]
    assert left_state["decision"]["committed_event_ids"] == right_state["decision"]["committed_event_ids"]

    left_before_replay = _logical_database_snapshot(left_database)
    right_before_replay = _logical_database_snapshot(right_database)
    left_replay = _memory_governor(left_database).decide(left_decide, left_proposal.proposal_id, NOW)
    right_replay = _memory_governor(right_database).decide(right_decide, right_proposal.proposal_id, NOW)
    assert left_replay.replayed is True
    assert right_replay.replayed is True
    assert left_replay.value == left_first.value
    assert left_replay.event_ids == left_first.event_ids
    assert right_replay.value == right_first.value
    assert right_replay.event_ids == right_first.event_ids
    assert _logical_database_snapshot(left_database) == left_before_replay
    assert _logical_database_snapshot(right_database) == right_before_replay
    assert left_replay == right_replay
