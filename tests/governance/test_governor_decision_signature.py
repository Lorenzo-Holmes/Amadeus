from __future__ import annotations

import json

import pytest

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import compute_command_hash
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.proposals import GovernorDecision
from amadeus_core.governance.governor import MemoryGovernor
from amadeus_core.governance.governor_decision_attestation import (
    GovernorDecisionAttestor,
)
from amadeus_core.governance.policy_v0_1 import GovernorPolicyV01
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.payloads import canonical_receipt_result
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError
from tests.governance.test_model_commit_boundary import (
    NOW,
    _decide_command,
    _governor_verifier,
    _proposal,
    _seed_evidence_event,
    _submit_command,
)


DECISION_KEY_ID = "m4-decision-a1"
DECISION_ACTOR_ID = "gov-b1"
DECISION_SECRET = b"m4-decision-attestation-test-secret-32-bytes"


def _decision_attestor() -> GovernorDecisionAttestor:
    return GovernorDecisionAttestor(
        active_key_id=DECISION_KEY_ID,
        authorities={
            DECISION_KEY_ID: (DECISION_ACTOR_ID, DECISION_SECRET),
        },
    )


@pytest.mark.parametrize("field_name", ("_active_key_id", "_authorities"))
def test_decision_attestor_configuration_cannot_be_deleted_then_replaced(
    field_name: str,
) -> None:
    attestor = _decision_attestor()

    def delete_then_replace() -> None:
        delattr(attestor, field_name)
        setattr(attestor, field_name, {})

    with pytest.raises(AttributeError):
        delete_then_replace()


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (
        ("decision_content_hash", "c" * 64),
        ("command_hash", "d" * 64),
        ("actor_id", "gov-c1"),
    ),
)
def test_keyed_attestation_binds_decision_command_and_actor(
    changed_field: str,
    changed_value: str,
) -> None:
    attestor = _decision_attestor()
    bound = {
        "decision_content_hash": "a" * 64,
        "command_hash": "b" * 64,
        "actor_id": DECISION_ACTOR_ID,
    }
    signature = attestor.attest(**bound)
    assert attestor.verify(signature, **bound)

    changed = {**bound, changed_field: changed_value}
    assert not attestor.verify(signature, **changed)
    assert DECISION_SECRET.decode("utf-8") not in repr(attestor)


def _memory_governor(database) -> MemoryGovernor:
    return MemoryGovernor(
        database,
        GovernorPolicyV01(),
        command_verifier=_governor_verifier(),
        decision_attestor=_decision_attestor(),
        clock=FixedClock(NOW),
    )


def _ledger_snapshot(database) -> tuple[tuple[object, ...], ...]:
    connection = database.connect()
    try:
        return tuple(
            tuple(row)
            for row in connection.execute(
                """
                SELECT event_id, ledger_seq, event_hash, payload_inline_json
                FROM ledger_events
                ORDER BY ledger_seq
                """
            ).fetchall()
        )
    finally:
        connection.close()


def _event_payload(database, event_id: str) -> dict[str, object]:
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT payload_inline_json FROM ledger_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        assert row is not None
        payload = json.loads(row[0])
        assert isinstance(payload, dict)
        return payload
    finally:
        connection.close()


def _self_consistently_replace_excluded_signature(
    database,
    *,
    command_id: str,
    decision_id: str,
    replacement: str,
) -> None:
    connection = database.connect()
    try:
        authority_row = connection.execute(
            "SELECT content_json FROM authority_records WHERE record_id = ?",
            (decision_id,),
        ).fetchone()
        receipt_row = connection.execute(
            "SELECT result_json FROM command_receipts WHERE command_id = ?",
            (command_id,),
        ).fetchone()
        assert authority_row is not None
        assert receipt_row is not None

        authority_body = json.loads(authority_row[0])
        original_content_hash = authority_body["record_header"]["content_hash"]
        authority_body["governor_signature"] = replacement
        tampered_authority_json = canonical_json(authority_body).decode("utf-8")

        receipt_body = json.loads(receipt_row[0])
        receipt_body["value"]["governor_signature"] = replacement
        tampered_result = canonical_receipt_result(receipt_body)

        connection.execute(
            "UPDATE authority_records SET content_json = ? WHERE record_id = ?",
            (tampered_authority_json, decision_id),
        )
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        try:
            connection.execute(
                """
                UPDATE command_receipts
                SET result_json = ?, result_hash = ?
                WHERE command_id = ?
                """,
                (
                    tampered_result.decode("utf-8"),
                    sha256_hex(tampered_result),
                    command_id,
                ),
            )
            connection.commit()
        finally:
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS command_receipts_reject_update\n"
                "BEFORE UPDATE ON command_receipts\n"
                "BEGIN\n"
                "    SELECT RAISE(ABORT, 'command receipt is immutable');\n"
                "END;"
            )

        updated = connection.execute(
            "SELECT content_hash FROM authority_records WHERE record_id = ?",
            (decision_id,),
        ).fetchone()
        assert updated is not None
        assert updated[0] == original_content_hash
    finally:
        connection.close()


def test_replay_rejects_self_consistent_excluded_signature_tamper(
    database,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-c1",
        memory_id="mem-c1",
        submit_event_id="evt-c1",
        evidence_refs=(evidence.event_id,),
    )
    submitted = ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c1"),
        proposal,
    )
    assert submitted.error is None
    command = _decide_command(
        proposal,
        command_id="cmd-c2",
        decision_id="gvd-c1",
        decision_event_id="evt-c2",
        effect_event_id="evt-c3",
    )
    governor = _memory_governor(database)
    first = governor.decide(command, proposal.proposal_id, NOW)
    assert first.error is None
    assert isinstance(first.value, GovernorDecision)
    assert first.value.governor_signature.startswith(
        f"govdec-v1:{DECISION_KEY_ID}:"
    )
    assert _decision_attestor().verify(
        first.value.governor_signature,
        decision_content_hash=first.value.record_header.content_hash,
        command_hash=compute_command_hash(command),
        actor_id=command.actor.actor_id,
    )
    assert _event_payload(database, "evt-c2")["governor_signature"] == (
        first.value.governor_signature
    )
    before_ledger = _ledger_snapshot(database)

    _self_consistently_replace_excluded_signature(
        database,
        command_id=command.command_id,
        decision_id=first.value.decision_id,
        replacement="governor-signature:forged:" + "f" * 64,
    )

    assert _ledger_snapshot(database) == before_ledger
    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)
