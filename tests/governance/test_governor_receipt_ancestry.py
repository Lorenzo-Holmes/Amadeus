from __future__ import annotations

import ast
import inspect
from datetime import timedelta
from textwrap import dedent

import pytest

from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.governance import _receipt_ancestry as receipt_ancestry
from amadeus_core.governance._receipt_output_binding import (
    compute_receipt_output_binding_hash,
    receipt_output_attestation_subject_hash,
    receipt_output_binding_from_payloads,
)
from amadeus_core.governance.governor import MemoryGovernor
from amadeus_core.governance.policy_v0_1 import POLICY_VERSION
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError, SQLiteUnitOfWork

from test_model_commit_boundary import (
    BRANCH_ID,
    GOVERNOR_ACTOR_ID,
    IDENTITY_ID,
    INSTANCE_ID,
    LINEAGE_ID,
    NOW,
    VAULT_ID,
    _command,
    _decide_command,
    _decision_attestor,
    _load,
    _memory_governor,
    _proposal,
    _reopen_command,
    _seed_evidence_event,
    _submit_command,
)

def _replace_authority_without_ledger(
    database: SQLiteDatabase,
    schema_root: str,
    record_id: str,
    replacement: object,
) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(record_id,),
        ).save_authoritative(
            schema_root,
            replacement.model_dump(mode="python"),  # type: ignore[attr-defined]
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _rewrite_authority_content(
    database: SQLiteDatabase,
    record_id: str,
    replacement: object,
) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE authority_records
            SET content_json = ?, content_hash = ?
            WHERE record_id = ?
            """,
            (
                canonical_json(
                    replacement.model_dump(mode="python")  # type: ignore[attr-defined]
                ).decode("utf-8"),
                replacement.record_header.content_hash,  # type: ignore[attr-defined]
                record_id,
            ),
        )
        assert cursor.rowcount == 1
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _rewrite_ledger_tail_correlation(
    database: SQLiteDatabase,
    event_id: str,
    correlation_id: str,
) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(connection)
        event = repository.get_validated(event_id)
        head = repository.verified_ledger_head(BRANCH_ID)
        assert isinstance(event, LedgerEvent)
        assert isinstance(head, LedgerEvent)
        assert head.event_id == event.event_id
        body = event.model_dump(mode="python")
        body.update(
            {
                "record_header": event.record_header.model_copy(
                    update={"content_hash": ZERO_HASH}
                ),
                "correlation_id": correlation_id,
                "event_hash": ZERO_HASH,
            }
        )
        replacement = seal_record(LedgerEvent, body)
        assert isinstance(replacement, LedgerEvent)
        connection.execute("DROP TRIGGER authority_ledger_reject_update")
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE authority_records
            SET content_json = ?, content_hash = ?
            WHERE record_id = ?
            """,
            (
                canonical_json(replacement.model_dump(mode="python")).decode("utf-8"),
                replacement.record_header.content_hash,
                replacement.event_id,
            ),
        )
        connection.execute(
            "UPDATE ledger_events SET event_hash = ? WHERE event_id = ?",
            (replacement.event_hash, replacement.event_id),
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS ledger_events_reject_update\n"
            "BEFORE UPDATE ON ledger_events\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS authority_ledger_reject_update\n"
            "BEFORE UPDATE ON authority_records\n"
            "WHEN OLD.record_type = 'LedgerEvent' OR NEW.record_type = 'LedgerEvent'\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _rewrite_ledger_tail_payload(
    database: SQLiteDatabase,
    event_id: str,
    updates: dict[str, object],
    *,
    event_updates: dict[str, object] | None = None,
) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(connection)
        event = repository.get_validated(event_id)
        head = repository.verified_ledger_head(BRANCH_ID)
        replay = repository.validated_ledger_replay(BRANCH_ID)
        assert isinstance(event, LedgerEvent)
        assert isinstance(head, LedgerEvent)
        assert head.event_id == event.event_id
        payload = next(
            resolved
            for candidate, resolved in zip(
                replay.events,
                replay.resolved_inline_payloads,
                strict=True,
            )
            if candidate.event_id == event_id
        )
        assert payload is not None
        rewritten_payload = {**payload, **updates}
        stored_payload = prepare_inline_payload(rewritten_payload)
        body = event.model_dump(mode="python")
        body.update(
            {
                "record_header": event.record_header.model_copy(
                    update={"content_hash": ZERO_HASH}
                ),
                "payload_ref": stored_payload.payload_ref,
                "event_hash": ZERO_HASH,
            }
        )
        if event_updates is not None:
            body.update(event_updates)
        replacement = seal_record(LedgerEvent, body)
        assert isinstance(replacement, LedgerEvent)
        connection.execute("DROP TRIGGER authority_ledger_reject_update")
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE authority_records
            SET content_json = ?, content_hash = ?
            WHERE record_id = ?
            """,
            (
                canonical_json(replacement.model_dump(mode="python")).decode("utf-8"),
                replacement.record_header.content_hash,
                replacement.event_id,
            ),
        )
        connection.execute(
            """
            UPDATE ledger_events
            SET event_hash = ?, payload_ref = ?, payload_mode = ?,
                payload_inline_json = ?, payload_external_ref = ?,
                payload_hash = ?, media_type = ?
            WHERE event_id = ?
            """,
            (
                replacement.event_hash,
                stored_payload.payload_ref,
                stored_payload.mode,
                stored_payload.inline_json,
                stored_payload.external_ref,
                stored_payload.payload_hash,
                stored_payload.media_type,
                replacement.event_id,
            ),
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS ledger_events_reject_update\n"
            "BEFORE UPDATE ON ledger_events\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS authority_ledger_reject_update\n"
            "BEFORE UPDATE ON authority_records\n"
            "WHEN OLD.record_type = 'LedgerEvent' OR NEW.record_type = 'LedgerEvent'\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _assert_receipt_output_binding_valid(
    database: SQLiteDatabase,
    decision_event_id: str,
    effect_event_id: str,
) -> None:
    connection = database.connect()
    try:
        replay = AuthorityRepository(connection).validated_ledger_replay(BRANCH_ID)
    finally:
        connection.close()
    event_payloads = {
        event.event_id: (event, payload)
        for event, payload in zip(
            replay.events,
            replay.resolved_inline_payloads,
            strict=True,
        )
    }
    decision_event, decision_payload = event_payloads[decision_event_id]
    effect_event, effect_payload = event_payloads[effect_event_id]
    assert decision_payload is not None
    assert effect_payload is not None
    committed_event_ids = (decision_event_id, effect_event_id)
    assert decision_payload.get("committed_event_ids") == committed_event_ids
    binding_kwargs: dict[str, object] = {
        "result": "commit",
        "committed_event_ids": committed_event_ids,
        "memory_payload": effect_payload,
    }
    if "memory_event_type" in inspect.signature(
        receipt_output_binding_from_payloads
    ).parameters:
        binding_kwargs["memory_event_type"] = effect_event.event_type
    recomputed = receipt_output_binding_from_payloads(
        decision_payload,
        decision_payload,
        **binding_kwargs,  # type: ignore[arg-type]
    )
    stored = decision_payload.get("receipt_output_binding_hash")
    signature = decision_payload.get("receipt_output_signature")
    decision_content_hash = decision_payload.get("decision_content_hash")
    assert isinstance(recomputed, str)
    assert stored == recomputed
    assert isinstance(signature, str)
    assert isinstance(decision_content_hash, str)
    assert _decision_attestor().verify(
        signature,
        decision_content_hash=receipt_output_attestation_subject_hash(
            decision_content_hash=decision_content_hash,
            output_binding_hash=recomputed,
        ),
        command_hash=decision_event.mutation_command_hash,
        actor_id=decision_event.actor_id,
    )


def _append_forged_governor_commit_pair(
    database: SQLiteDatabase,
    *,
    decision_id: str,
    decision_event_id: str,
    effect_event_id: str,
    proposal_id: str,
    proposal_type: str,
    proposal_target_refs: tuple[str, ...],
    memory_id: str,
    before_content_hash: str | None,
    memory_content_hash: str,
    state: str,
    version: int,
    semantic_version: int,
    effect_event_type: str,
    store_decision_authority: bool,
    proposal_before: Proposal | None = None,
    proposal_after: Proposal | None = None,
    effect_actor_id: str = GOVERNOR_ACTOR_ID,
    effect_instance_id: str = INSTANCE_ID,
    output_binding_fault: str | None = None,
) -> tuple[LedgerEvent, LedgerEvent]:
    command = _command(
        command_id=f"cmd-{decision_event_id.removeprefix('evt-')}-f1",
        command_type="fixture.governor.commit",
        actor_type="governor",
        actor_id=GOVERNOR_ACTOR_ID,
        targets=(
            (decision_id, "absent"),
            (decision_event_id, "absent"),
            (effect_event_id, "absent"),
        ),
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                proposal_id,
                *proposal_target_refs,
            ),
            "semantic_input_hash": sha256_hex(
                canonical_json(
                    {
                        "decision_id": decision_id,
                        "proposal_id": proposal_id,
                        "event_ids": (decision_event_id, effect_event_id),
                    }
                )
            ),
        },
    )

    def handler(
        repository: AuthorityRepository,
        mutation_command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> CommandResult[object]:
        unsigned = seal_record(
            GovernorDecision,
            {
                "record_header": record_header(
                    "GovernorDecision",
                    decision_id,
                    identity_id=IDENTITY_ID,
                    lineage_id=LINEAGE_ID,
                    branch_id=BRANCH_ID,
                    created_at=NOW,
                    created_by_event_id=decision_event_id,
                    deployment_policy_ref="deployment:test",
                ),
                "decision_id": decision_id,
                "proposal_id": proposal_id,
                "identity_id": IDENTITY_ID,
                "lineage_id": LINEAGE_ID,
                "branch_id": BRANCH_ID,
                "vault_id": VAULT_ID,
                "result": "commit",
                "policy_version": POLICY_VERSION,
                "input_state_hash": "a" * 64,
                "reason_codes": ("EVIDENCE_COMPLETE",),
                "evidence_refs": (),
                "committed_event_ids": (decision_event_id, effect_event_id),
                "output_state_hash": "b" * 64,
                "decided_at": NOW,
                "governor_signature": "__PENDING_GOVERNOR_ATTESTATION__",
                "version": 1,
            },
        )
        assert isinstance(unsigned, GovernorDecision)
        decision = unsigned.model_copy(
            update={
                "governor_signature": _decision_attestor().attest(
                    decision_content_hash=unsigned.record_header.content_hash,
                    command_hash=execution_context.command_hash,
                    actor_id=mutation_command.actor.actor_id,
                )
            }
        )
        if store_decision_authority:
            stored_decision = repository.save_authoritative(
                "governor_decision",
                decision.model_dump(mode="python"),
            )
            assert stored_decision == decision

        before_proposal_hash = (
            proposal_before.record_header.content_hash
            if proposal_before is not None
            else "c" * 64
        )
        before_proposal_version = (
            proposal_before.version if proposal_before is not None else 1
        )
        before_proposal_status = (
            proposal_before.status if proposal_before is not None else "pending"
        )
        proposal_hash = (
            proposal_after.record_header.content_hash
            if proposal_after is not None
            else "d" * 64
        )
        proposal_version = (
            proposal_after.version if proposal_after is not None else 2
        )
        proposal_status = (
            proposal_after.status if proposal_after is not None else "committed"
        )
        if "memory_effect" in inspect.signature(
            compute_receipt_output_binding_hash
        ).parameters:
            receipt_output_binding_hash = compute_receipt_output_binding_hash(
                decision_id=decision.decision_id,
                proposal_id=decision.proposal_id,
                proposal_type=proposal_type,
                result=decision.result,
                committed_event_ids=decision.committed_event_ids,
                proposal_after_content_hash=proposal_hash,
                memory_effect={
                    "event_type": effect_event_type,
                    "operation": (
                        "create"
                        if effect_event_type == "memory_created"
                        else "update"
                    ),
                    "decision_id": decision.decision_id,
                    "proposal_id": decision.proposal_id,
                    "proposal_type": proposal_type,
                    "memory_id": memory_id,
                    "before_content_hash": before_content_hash,
                    "memory_content_hash": memory_content_hash,
                    "state": state,
                    "semantic_version": semantic_version,
                    "version": version,
                },
            )
        else:
            receipt_output_binding_hash = compute_receipt_output_binding_hash(
                decision_id=decision.decision_id,
                proposal_id=decision.proposal_id,
                result=decision.result,
                committed_event_ids=decision.committed_event_ids,
                proposal_after_content_hash=proposal_hash,
                memory_id=memory_id,
                memory_content_hash=memory_content_hash,
            )
        receipt_output_signature = _decision_attestor().attest(
            decision_content_hash=receipt_output_attestation_subject_hash(
                decision_content_hash=decision.record_header.content_hash,
                output_binding_hash=receipt_output_binding_hash,
            ),
            command_hash=execution_context.command_hash,
            actor_id=mutation_command.actor.actor_id,
        )
        assert _decision_attestor().verify(
            receipt_output_signature,
            decision_content_hash=receipt_output_attestation_subject_hash(
                decision_content_hash=decision.record_header.content_hash,
                output_binding_hash=receipt_output_binding_hash,
            ),
            command_hash=execution_context.command_hash,
            actor_id=mutation_command.actor.actor_id,
        )
        decision_payload = {
            "decision_id": decision.decision_id,
            "proposal_id": decision.proposal_id,
            "proposal_type": proposal_type,
            "result": decision.result,
            "policy_version": decision.policy_version,
            "reason_codes": decision.reason_codes,
            "evidence_refs": decision.evidence_refs,
            "committed_event_ids": decision.committed_event_ids,
            "input_state_hash": decision.input_state_hash,
            "output_state_hash": decision.output_state_hash,
            "decision_content_hash": decision.record_header.content_hash,
            "governor_signature": decision.governor_signature,
            "receipt_output_binding_hash": receipt_output_binding_hash,
            "receipt_output_signature": receipt_output_signature,
            "before_proposal_content_hash": before_proposal_hash,
            "before_proposal_version": before_proposal_version,
            "before_proposal_status": before_proposal_status,
            "proposal_content_hash": proposal_hash,
            "proposal_version": proposal_version,
            "proposal_status": proposal_status,
            "proposal_target_refs": proposal_target_refs,
        }
        if output_binding_fault == "binding_hash_missing":
            del decision_payload["receipt_output_binding_hash"]
        elif output_binding_fault == "binding_hash_mismatch":
            decision_payload["receipt_output_binding_hash"] = (
                ("0" if receipt_output_binding_hash[0] != "0" else "1")
                + receipt_output_binding_hash[1:]
            )
        elif output_binding_fault == "signature_missing":
            del decision_payload["receipt_output_signature"]
        elif output_binding_fault == "signature_invalid":
            decision_payload["receipt_output_signature"] = (
                receipt_output_signature[:-1]
                + ("0" if receipt_output_signature[-1] != "0" else "1")
            )
        else:
            assert output_binding_fault is None
        effect_payload = {
            "decision_id": decision.decision_id,
            "proposal_id": decision.proposal_id,
            "proposal_type": proposal_type,
            "memory_id": memory_id,
            "before_content_hash": before_content_hash,
            "memory_content_hash": memory_content_hash,
            "state": state,
            "semantic_version": semantic_version,
            "version": version,
        }

        def append(
            *,
            event_id: str,
            event_type: str,
            payload: dict[str, object],
            causation_id: str,
            actor_id: str,
            instance_id: str,
        ) -> LedgerEvent:
            head = repository.verified_ledger_head(BRANCH_ID)
            assert isinstance(head, LedgerEvent)
            stored_payload = prepare_inline_payload(payload)
            candidate = seal_record(
                LedgerEvent,
                {
                    "record_header": record_header(
                        "LedgerEvent",
                        event_id,
                        identity_id=IDENTITY_ID,
                        lineage_id=LINEAGE_ID,
                        branch_id=BRANCH_ID,
                        created_at=NOW,
                        created_by_event_id=event_id,
                        deployment_policy_ref="deployment:test",
                    ),
                    "event_id": event_id,
                    "ledger_seq": head.ledger_seq + 1,
                    "identity_id": IDENTITY_ID,
                    "lineage_id": LINEAGE_ID,
                    "branch_id": BRANCH_ID,
                    "instance_id": instance_id,
                    "vault_id": VAULT_ID,
                    "event_type": event_type,
                    "occurred_at": NOW,
                    "ingested_at": mutation_command.issued_at,
                    "actor_type": "governor",
                    "actor_id": actor_id,
                    "mutation_command_id": execution_context.command_id,
                    "mutation_command_hash": execution_context.command_hash,
                    "payload_ref": stored_payload.payload_ref,
                    "causation_id": causation_id,
                    "correlation_id": execution_context.audit_context_id,
                    "previous_event_hash": head.event_hash,
                    "event_hash": ZERO_HASH,
                    "version": 1,
                },
            )
            assert isinstance(candidate, LedgerEvent)
            stored = repository.append_ledger_event(
                candidate.model_dump(mode="python"),
                payload=stored_payload,
            )
            assert isinstance(stored, LedgerEvent)
            return stored

        decision_event = append(
            event_id=decision_event_id,
            event_type="governor_decision_committed",
            payload=decision_payload,
            causation_id="evt-a1",
            actor_id=GOVERNOR_ACTOR_ID,
            instance_id=INSTANCE_ID,
        )
        effect_event = append(
            event_id=effect_event_id,
            event_type=effect_event_type,
            payload=effect_payload,
            causation_id=decision_event.event_id,
            actor_id=effect_actor_id,
            instance_id=effect_instance_id,
        )
        return CommandResult[object](
            value=decision.model_dump(mode="json"),
            event_ids=(decision_event.event_id, effect_event.event_id),
            error=None,
            replayed=False,
        )

    result = SQLiteUnitOfWork(database).execute_command(command, handler)
    assert result.error is None
    if output_binding_fault is None:
        _assert_receipt_output_binding_valid(
            database, decision_event_id, effect_event_id
        )
    decision_event = _load(database, decision_event_id)
    effect_event = _load(database, effect_event_id)
    assert isinstance(decision_event, LedgerEvent)
    assert isinstance(effect_event, LedgerEvent)
    return decision_event, effect_event


def _committed_memory_receipt_fixture(
    database: SQLiteDatabase,
    *,
    proposal_id: str,
    memory_id: str,
    submit_event_id: str,
    submit_command_id: str,
    decide_command_id: str,
    decision_id: str,
    decision_event_id: str,
    effect_event_id: str,
) -> tuple[MemoryGovernor, MutationCommandEnvelope, Proposal, AutobiographicalMemory]:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id=proposal_id,
        memory_id=memory_id,
        submit_event_id=submit_event_id,
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id=submit_command_id),
        proposal,
    ).error is None
    command = _decide_command(
        proposal,
        command_id=decide_command_id,
        decision_id=decision_id,
        decision_event_id=decision_event_id,
        effect_event_id=effect_event_id,
    )
    governor = _memory_governor(database)
    result = governor.decide(command, proposal.proposal_id, NOW)
    assert result.error is None
    assert result.value is not None
    assert result.value.result == "commit"
    memory = _load(database, memory_id)
    assert isinstance(memory, AutobiographicalMemory)
    return governor, command, proposal, memory


def _seed_successor_proposal_authority(
    database: SQLiteDatabase,
    *,
    proposal_id: str,
    proposal_type: str,
    memory_id: str,
    submitted_event_id: str,
) -> tuple[Proposal, Proposal]:
    proposed_patch_by_type: dict[str, dict[str, object]] = {
        "change_memory_state": {
            "state": "contested",
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
        },
        "set_importance": {"importance": 0.75},
    }
    pending = _proposal(
        proposal_id=proposal_id,
        memory_id=memory_id,
        submit_event_id=submitted_event_id,
        evidence_refs=(),
        proposal_type=proposal_type,
        proposed_patch=proposed_patch_by_type.get(proposal_type),
    )
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        stored = AuthorityRepository(
            connection,
            allowed_target_refs=(proposal_id,),
        ).save_authoritative("proposal", pending.model_dump(mode="python"))
        assert stored == pending
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()
    committed = reseal_update(
        pending,
        {"status": "committed", "version": pending.version + 1},
    )
    assert isinstance(committed, Proposal)
    return pending, committed


def _commit_real_importance_successor(
    database: SQLiteDatabase,
    governor: MemoryGovernor,
    memory: AutobiographicalMemory,
    *,
    suffix: str,
    expect_memory_ancestry_error: bool = False,
) -> tuple[MutationCommandEnvelope, AutobiographicalMemory, str]:
    proposal = _proposal(
        proposal_id=f"prp-{suffix}",
        memory_id=memory.memory_id,
        submit_event_id=f"evt-{suffix}1",
        evidence_refs=memory.evidence_event_refs,
        proposal_type="set_importance",
        proposed_patch={"importance": 0.75},
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id=f"cmd-{suffix}1"),
        proposal,
    ).error is None
    decision_id = f"gvd-{suffix}1"
    decision_event_id = f"evt-{suffix}2"
    effect_event_id = f"evt-{suffix}3"
    command = _decide_command(
        proposal,
        command_id=f"cmd-{suffix}2",
        decision_id=decision_id,
        decision_event_id=decision_event_id,
        effect_event_id=effect_event_id,
        memory_version=memory.version,
    )
    if expect_memory_ancestry_error:
        with pytest.raises(
            ReceiptIntegrityError,
            match=(
                r"^GovernorDecision receipt does not anchor historical Memory authority$"
            ),
        ):
            governor.decide(command, proposal.proposal_id, NOW)
        terminal_proposal = _load(database, proposal.proposal_id)
        terminal_decision = _load(database, decision_id)
        updated = _load(database, memory.memory_id)
        decision_event = _load(database, decision_event_id)
        effect_event = _load(database, effect_event_id)
        expected_updated = reseal_update(
            memory,
            {
                "importance": 0.75,
                "governor_decision_id": decision_id,
                "semantic_version": memory.semantic_version + 1,
                "updated_at": NOW,
                "version": memory.version + 1,
            },
        )
        assert isinstance(terminal_proposal, Proposal)
        assert isinstance(terminal_decision, GovernorDecision)
        assert isinstance(updated, AutobiographicalMemory)
        assert isinstance(decision_event, LedgerEvent)
        assert isinstance(effect_event, LedgerEvent)
        assert isinstance(expected_updated, AutobiographicalMemory)
        assert terminal_proposal.status == "committed"
        assert terminal_decision.result == "commit"
        assert terminal_decision.committed_event_ids == (
            decision_event_id,
            effect_event_id,
        )
        assert decision_event.event_type == "governor_decision_committed"
        assert effect_event.event_type == "memory_state_changed"
        assert updated == expected_updated
        _assert_receipt_output_binding_valid(
            database,
            decision_event_id,
            effect_event_id,
        )
    else:
        result = governor.decide(command, proposal.proposal_id, NOW)
        assert result.error is None
        assert result.value is not None
        assert result.value.result == "commit"
        updated = _load(database, memory.memory_id)
        assert isinstance(updated, AutobiographicalMemory)
        assert updated.importance == 0.75
    return command, updated, effect_event_id


def _append_authenticated_memory_effect(
    database: SQLiteDatabase,
    memory: AutobiographicalMemory,
    *,
    suffix: str,
    before_content_hash: str | None,
    proposal_type: str = "set_importance",
    updates: dict[str, object] | None = None,
    output_binding_fault: str | None = None,
) -> tuple[AutobiographicalMemory, LedgerEvent, LedgerEvent]:
    replacement_updates: dict[str, object] = {
        "importance": 0.625,
        "governor_decision_id": f"gvd-{suffix}",
        "semantic_version": memory.semantic_version + 1,
        "updated_at": memory.updated_at,
        "version": memory.version + 1,
    }
    if updates is not None:
        replacement_updates.update(updates)
    successor = reseal_update(memory, replacement_updates)
    assert isinstance(successor, AutobiographicalMemory)
    proposal_before, proposal_after = _seed_successor_proposal_authority(
        database,
        proposal_id=f"prp-{suffix}",
        proposal_type=proposal_type,
        memory_id=memory.memory_id,
        submitted_event_id=f"evt-{suffix}0",
    )
    decision_event, effect_event = _append_forged_governor_commit_pair(
        database,
        decision_id=f"gvd-{suffix}",
        decision_event_id=f"evt-{suffix}1",
        effect_event_id=f"evt-{suffix}2",
        proposal_id=proposal_before.proposal_id,
        proposal_type=proposal_type,
        proposal_target_refs=(memory.memory_id,),
        memory_id=memory.memory_id,
        before_content_hash=before_content_hash,
        memory_content_hash=successor.record_header.content_hash,
        state=successor.state,
        version=successor.version,
        semantic_version=successor.semantic_version,
        effect_event_type=(
            "memory_created"
            if proposal_type == "create_memory"
            else "memory_state_changed"
        ),
        store_decision_authority=True,
        proposal_before=proposal_before,
        proposal_after=proposal_after,
        output_binding_fault=output_binding_fault,
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        proposal_before.proposal_id,
        proposal_after,
    )
    return successor, decision_event, effect_event


@pytest.mark.parametrize(
    ("rejected_evidence", "expected_result"),
    ((False, "commit"), (True, "reject")),
)
def test_terminal_governor_receipt_rejects_unledgered_proposal_successor(
    database: SQLiteDatabase,
    rejected_evidence: bool,
    expected_result: str,
) -> None:
    evidence = _seed_evidence_event(database, rejected=rejected_evidence)
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
    assert first.value is not None
    assert first.value.result == expected_result

    terminal = _load(database, proposal.proposal_id)
    assert isinstance(terminal, Proposal)
    forged = reseal_update(
        terminal,
        {
            "expires_at": terminal.expires_at + timedelta(days=1),
            "version": terminal.version + 1,
        },
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        terminal.proposal_id,
        forged,
    )

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


def test_commit_receipt_rejects_unledgered_memory_successor(
    database: SQLiteDatabase,
) -> None:
    evidence = _seed_evidence_event(database)
    proposal = _proposal(
        proposal_id="prp-c2",
        memory_id="mem-c2",
        submit_event_id="evt-c4",
        evidence_refs=(evidence.event_id,),
    )
    assert ProposalService(database).submit(
        _submit_command(proposal, command_id="cmd-c3"),
        proposal,
    ).error is None
    command = _decide_command(
        proposal,
        command_id="cmd-c4",
        decision_id="gvd-c2",
        decision_event_id="evt-c5",
        effect_event_id="evt-c6",
    )
    governor = _memory_governor(database)
    first = governor.decide(command, proposal.proposal_id, NOW)
    assert first.error is None
    assert first.value is not None
    assert first.value.result == "commit"

    memory = _load(database, "mem-c2")
    assert isinstance(memory, AutobiographicalMemory)
    forged = reseal_update(
        memory,
        {
            "importance": 0.75,
            "governor_decision_id": "gvd-c9",
            "semantic_version": memory.semantic_version + 1,
            "updated_at": memory.updated_at + timedelta(hours=1),
            "version": memory.version + 1,
        },
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        forged,
    )

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


def test_defer_receipt_rejects_forged_commit_without_decision_authority(
    database: SQLiteDatabase,
) -> None:
    proposal = _proposal(
        proposal_id="prp-d1",
        memory_id="mem-d1",
        submit_event_id="evt-d1",
        evidence_refs=(),
    )
    service = ProposalService(database)
    assert service.submit(
        _submit_command(proposal, command_id="cmd-d1"),
        proposal,
    ).error is None
    command = _decide_command(
        proposal,
        command_id="cmd-d2",
        decision_id="gvd-d1",
        decision_event_id="evt-d2",
        effect_event_id="evt-d3",
    )
    governor = _memory_governor(database)
    deferred_result = governor.decide(command, proposal.proposal_id, NOW)
    assert deferred_result.error is None
    assert deferred_result.value is not None
    assert deferred_result.value.result == "defer"
    deferred = _load(database, proposal.proposal_id)
    assert isinstance(deferred, Proposal)
    evidence = _seed_evidence_event(database, event_id="evt-d4")
    reopen_at = NOW + timedelta(hours=1)
    reopened_result = service.reopen(
        _reopen_command(
            deferred,
            event_id="evt-d5",
            evidence_event_ids=(evidence.event_id,),
            now=reopen_at,
        ),
        proposal.proposal_id,
        reopen_at,
    )
    assert reopened_result.error is None
    reopened = reopened_result.value
    assert isinstance(reopened, Proposal)
    forged = reseal_update(
        reopened,
        {"status": "committed", "version": reopened.version + 1},
    )
    assert isinstance(forged, Proposal)
    _append_forged_governor_commit_pair(
        database,
        decision_id="gvd-d9",
        decision_event_id="evt-d6",
        effect_event_id="evt-d7",
        proposal_id=proposal.proposal_id,
        proposal_type="create_memory",
        proposal_target_refs=proposal.target_refs,
        memory_id="mem-d1",
        before_content_hash=None,
        memory_content_hash="f" * 64,
        state="active",
        version=1,
        semantic_version=1,
        effect_event_type="memory_created",
        store_decision_authority=False,
        proposal_before=reopened,
        proposal_after=forged,
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        proposal.proposal_id,
        forged,
    )

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


def test_commit_receipt_rejects_forged_memory_successor_without_decision_authority(
    database: SQLiteDatabase,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-e1",
        memory_id="mem-e1",
        submit_event_id="evt-e1",
        submit_command_id="cmd-e1",
        decide_command_id="cmd-e2",
        decision_id="gvd-e1",
        decision_event_id="evt-e2",
        effect_event_id="evt-e3",
    )
    forged = reseal_update(
        memory,
        {
            "state": "contested",
            "contested_by_event_ids": memory.evidence_event_refs,
            "governor_decision_id": "gvd-e9",
            "semantic_version": memory.semantic_version + 1,
            "updated_at": memory.updated_at + timedelta(hours=1),
            "version": memory.version + 1,
        },
    )
    assert isinstance(forged, AutobiographicalMemory)
    _append_forged_governor_commit_pair(
        database,
        decision_id="gvd-e9",
        decision_event_id="evt-e4",
        effect_event_id="evt-e5",
        proposal_id="prp-e9",
        proposal_type="change_memory_state",
        proposal_target_refs=(memory.memory_id,),
        memory_id=memory.memory_id,
        before_content_hash=memory.record_header.content_hash,
        memory_content_hash=forged.record_header.content_hash,
        state=forged.state,
        version=forged.version,
        semantic_version=forged.semantic_version,
        effect_event_type="memory_state_changed",
        store_decision_authority=False,
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        forged,
    )

    _assert_receipt_output_binding_valid(database, "evt-e4", "evt-e5")

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


def test_commit_receipt_rejects_later_memory_created_with_valid_decision(
    database: SQLiteDatabase,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-f1",
        memory_id="mem-f1",
        submit_event_id="evt-f1",
        submit_command_id="cmd-f1",
        decide_command_id="cmd-f2",
        decision_id="gvd-f1",
        decision_event_id="evt-f2",
        effect_event_id="evt-f3",
    )
    forged = reseal_update(
        memory,
        {
            "importance": 0.75,
            "governor_decision_id": "gvd-f9",
            "semantic_version": memory.semantic_version + 1,
            "updated_at": memory.updated_at + timedelta(hours=1),
            "version": memory.version + 1,
        },
    )
    assert isinstance(forged, AutobiographicalMemory)
    successor_proposal, successor_committed = _seed_successor_proposal_authority(
        database,
        proposal_id="prp-f9",
        proposal_type="create_memory",
        memory_id=memory.memory_id,
        submitted_event_id="evt-f6",
    )
    _append_forged_governor_commit_pair(
        database,
        decision_id="gvd-f9",
        decision_event_id="evt-f4",
        effect_event_id="evt-f5",
        proposal_id=successor_proposal.proposal_id,
        proposal_type="create_memory",
        proposal_target_refs=(memory.memory_id,),
        memory_id=memory.memory_id,
        before_content_hash=None,
        memory_content_hash=forged.record_header.content_hash,
        state=forged.state,
        version=forged.version,
        semantic_version=forged.semantic_version,
        effect_event_type="memory_created",
        store_decision_authority=True,
        proposal_before=successor_proposal,
        proposal_after=successor_committed,
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        successor_proposal.proposal_id,
        successor_committed,
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        forged,
    )

    _assert_receipt_output_binding_valid(database, "evt-f4", "evt-f5")

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


@pytest.mark.parametrize(
    ("proposal_type", "target_state"),
    (
        ("change_memory_state", "active"),
        ("set_importance", "contested"),
    ),
)
def test_commit_receipt_rejects_illegal_memory_state_semantics(
    database: SQLiteDatabase,
    proposal_type: str,
    target_state: str,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-f1",
        memory_id="mem-f1",
        submit_event_id="evt-f1",
        submit_command_id="cmd-f1",
        decide_command_id="cmd-f2",
        decision_id="gvd-f1",
        decision_event_id="evt-f2",
        effect_event_id="evt-f3",
    )
    forged = reseal_update(
        memory,
        {
            "state": target_state,
            "contested_by_event_ids": (
                memory.evidence_event_refs if target_state == "contested" else ()
            ),
            "importance": 0.75,
            "governor_decision_id": "gvd-f9",
            "semantic_version": memory.semantic_version + 1,
            "updated_at": memory.updated_at + timedelta(hours=1),
            "version": memory.version + 1,
        },
    )
    assert isinstance(forged, AutobiographicalMemory)
    successor_proposal, successor_committed = _seed_successor_proposal_authority(
        database,
        proposal_id="prp-f9",
        proposal_type=proposal_type,
        memory_id=memory.memory_id,
        submitted_event_id="evt-f6",
    )
    _append_forged_governor_commit_pair(
        database,
        decision_id="gvd-f9",
        decision_event_id="evt-f4",
        effect_event_id="evt-f5",
        proposal_id=successor_proposal.proposal_id,
        proposal_type=proposal_type,
        proposal_target_refs=(memory.memory_id,),
        memory_id=memory.memory_id,
        before_content_hash=memory.record_header.content_hash,
        memory_content_hash=forged.record_header.content_hash,
        state=forged.state,
        version=forged.version,
        semantic_version=forged.semantic_version,
        effect_event_type="memory_state_changed",
        store_decision_authority=True,
        proposal_before=successor_proposal,
        proposal_after=successor_committed,
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        successor_proposal.proposal_id,
        successor_committed,
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        forged,
    )

    _assert_receipt_output_binding_valid(database, "evt-f4", "evt-f5")

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


@pytest.mark.parametrize(
    "mismatch",
    ("target", "actor", "instance", "correlation"),
)
def test_commit_receipt_rejects_forged_effect_pair_metadata(
    database: SQLiteDatabase,
    mismatch: str,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-f1",
        memory_id="mem-f1",
        submit_event_id="evt-f1",
        submit_command_id="cmd-f1",
        decide_command_id="cmd-f2",
        decision_id="gvd-f1",
        decision_event_id="evt-f2",
        effect_event_id="evt-f3",
    )
    forged = reseal_update(
        memory,
        {
            "state": "contested",
            "contested_by_event_ids": memory.evidence_event_refs,
            "governor_decision_id": "gvd-f9",
            "semantic_version": memory.semantic_version + 1,
            "updated_at": memory.updated_at + timedelta(hours=1),
            "version": memory.version + 1,
        },
    )
    assert isinstance(forged, AutobiographicalMemory)
    successor_proposal, successor_committed = _seed_successor_proposal_authority(
        database,
        proposal_id="prp-f9",
        proposal_type="change_memory_state",
        memory_id=memory.memory_id,
        submitted_event_id="evt-f6",
    )
    _decision_event, effect_event = _append_forged_governor_commit_pair(
        database,
        decision_id="gvd-f9",
        decision_event_id="evt-f4",
        effect_event_id="evt-f5",
        proposal_id=successor_proposal.proposal_id,
        proposal_type="change_memory_state",
        proposal_target_refs=(
            ("mem-ef",) if mismatch == "target" else (memory.memory_id,)
        ),
        memory_id=memory.memory_id,
        before_content_hash=memory.record_header.content_hash,
        memory_content_hash=forged.record_header.content_hash,
        state=forged.state,
        version=forged.version,
        semantic_version=forged.semantic_version,
        effect_event_type="memory_state_changed",
        store_decision_authority=True,
        proposal_before=successor_proposal,
        proposal_after=successor_committed,
        effect_actor_id=("gov-ef" if mismatch == "actor" else GOVERNOR_ACTOR_ID),
        effect_instance_id=("ins-ef" if mismatch == "instance" else INSTANCE_ID),
    )
    _replace_authority_without_ledger(
        database,
        "proposal",
        successor_proposal.proposal_id,
        successor_committed,
    )
    if mismatch == "correlation":
        _rewrite_ledger_tail_correlation(database, effect_event.event_id, "aud-ef")
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        forged,
    )

    _assert_receipt_output_binding_valid(database, "evt-f4", "evt-f5")

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


def test_commit_receipt_rejects_signed_effect_projection_rewrite(
    database: SQLiteDatabase,
) -> None:
    governor, create_command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-aa1",
        memory_id="mem-aa1",
        submit_event_id="evt-aa1",
        submit_command_id="cmd-aa1",
        decide_command_id="cmd-aa2",
        decision_id="gvd-aa1",
        decision_event_id="evt-aa2",
        effect_event_id="evt-aa3",
    )
    _update_command, updated, effect_event_id = _commit_real_importance_successor(
        database,
        governor,
        memory,
        suffix="aa4",
    )
    forged = reseal_update(updated, {"importance": 0.99})
    assert isinstance(forged, AutobiographicalMemory)
    _rewrite_ledger_tail_payload(
        database,
        effect_event_id,
        {"memory_content_hash": forged.record_header.content_hash},
    )
    _rewrite_authority_content(database, forged.memory_id, forged)

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(create_command, proposal.proposal_id, NOW)


def test_update_receipt_rejects_disconnected_historical_before_hash(
    database: SQLiteDatabase,
) -> None:
    governor, _create_command, _proposal_before, memory = (
        _committed_memory_receipt_fixture(
            database,
            proposal_id="prp-bb1",
            memory_id="mem-bb1",
            submit_event_id="evt-bb1",
            submit_command_id="cmd-bb1",
            decide_command_id="cmd-bb2",
            decision_id="gvd-bb1",
            decision_event_id="evt-bb2",
            effect_event_id="evt-bb3",
        )
    )
    update_command, _updated, effect_event_id = _commit_real_importance_successor(
        database,
        governor,
        memory,
        suffix="bb4",
    )
    _rewrite_ledger_tail_payload(
        database,
        effect_event_id,
        {"before_content_hash": "f" * 64},
    )

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(update_command, "prp-bb4", NOW)


def test_commit_receipt_accepts_cryptographically_bound_legal_memory_successor(
    database: SQLiteDatabase,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-cc1",
        memory_id="mem-cc1",
        submit_event_id="evt-cc1",
        submit_command_id="cmd-cc1",
        decide_command_id="cmd-cc2",
        decision_id="gvd-cc1",
        decision_event_id="evt-cc2",
        effect_event_id="evt-cc3",
    )
    _update_command, successor, effect_event_id = _commit_real_importance_successor(
        database,
        governor,
        memory,
        suffix="cc4",
    )
    _assert_receipt_output_binding_valid(
        database,
        "evt-cc42",
        effect_event_id,
    )
    assert _load(database, memory.memory_id) == successor

    replayed = governor.decide(command, proposal.proposal_id, NOW)

    assert replayed.error is None
    assert replayed.replayed is True


@pytest.mark.parametrize(
    "output_binding_fault",
    (
        "binding_hash_missing",
        "binding_hash_mismatch",
        "signature_missing",
        "signature_invalid",
    ),
)
def test_commit_receipt_rejects_legal_memory_successor_without_valid_output_binding(
    database: SQLiteDatabase,
    output_binding_fault: str,
) -> None:
    governor, command, proposal, memory = _committed_memory_receipt_fixture(
        database,
        proposal_id="prp-dd1",
        memory_id="mem-dd1",
        submit_event_id="evt-dd1",
        submit_command_id="cmd-dd1",
        decide_command_id="cmd-dd2",
        decision_id="gvd-dd1",
        decision_event_id="evt-dd2",
        effect_event_id="evt-dd3",
    )
    successor, _decision_event, _effect_event = _append_authenticated_memory_effect(
        database,
        memory,
        suffix="dd4",
        before_content_hash=memory.record_header.content_hash,
        output_binding_fault=output_binding_fault,
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        successor,
    )

    with pytest.raises(ReceiptIntegrityError):
        governor.decide(command, proposal.proposal_id, NOW)


@pytest.mark.parametrize(
    "invalid_edge",
    (
        "disconnected_before_hash",
        "version_jump",
        "semantic_version_jump",
        "state_change_without_state_proposal",
        "duplicate_create_operation",
    ),
)
def test_update_receipt_rejects_authenticated_invalid_intermediate_memory_edge(
    database: SQLiteDatabase,
    invalid_edge: str,
) -> None:
    governor, _create_command, _create_proposal, memory = (
        _committed_memory_receipt_fixture(
            database,
            proposal_id="prp-ee1",
            memory_id="mem-ee1",
            submit_event_id="evt-ee1",
            submit_command_id="cmd-ee1",
            decide_command_id="cmd-ee2",
            decision_id="gvd-ee1",
            decision_event_id="evt-ee2",
            effect_event_id="evt-ee3",
        )
    )
    before_content_hash: str | None = memory.record_header.content_hash
    proposal_type = "set_importance"
    updates: dict[str, object] = {}
    if invalid_edge == "disconnected_before_hash":
        before_content_hash = "f" * 64
        assert before_content_hash != memory.record_header.content_hash
    elif invalid_edge == "version_jump":
        updates["version"] = memory.version + 2
    elif invalid_edge == "semantic_version_jump":
        updates["semantic_version"] = memory.semantic_version + 2
    elif invalid_edge == "state_change_without_state_proposal":
        updates.update(
            {
                "state": "contested",
                "contested_by_event_ids": memory.evidence_event_refs,
            }
        )
    elif invalid_edge == "duplicate_create_operation":
        before_content_hash = None
        proposal_type = "create_memory"
    else:
        raise AssertionError(f"unknown invalid edge: {invalid_edge}")
    intermediate, intermediate_decision, intermediate_effect = (
        _append_authenticated_memory_effect(
            database,
            memory,
            suffix="ee4",
            before_content_hash=before_content_hash,
            proposal_type=proposal_type,
            updates=updates,
        )
    )
    bridge: AutobiographicalMemory | None = None
    if invalid_edge == "version_jump":
        bridge = reseal_update(
            memory,
            {"version": memory.version + 1},
        )
        assert isinstance(bridge, AutobiographicalMemory)
        assert bridge.version + 1 == intermediate.version
        assert bridge.record_header.content_hash not in {
            memory.record_header.content_hash,
            intermediate.record_header.content_hash,
        }
        _replace_authority_without_ledger(
            database,
            "autobiographical_memory",
            memory.memory_id,
            bridge,
        )
        assert _load(database, memory.memory_id) == bridge
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        intermediate,
    )
    if bridge is not None:
        assert _load(database, memory.memory_id) == intermediate
    _update_command, terminal, terminal_event_id = (
        _commit_real_importance_successor(
            database,
            governor,
            intermediate,
            suffix="ee5",
            expect_memory_ancestry_error=True,
        )
    )
    if bridge is not None:
        assert memory.version + 2 == intermediate.version
        assert intermediate.version + 1 == terminal.version
        _assert_receipt_output_binding_valid(
            database,
            intermediate_decision.event_id,
            intermediate_effect.event_id,
        )
        _assert_receipt_output_binding_valid(
            database,
            "evt-ee52",
            terminal_event_id,
        )
        connection = database.connect()
        try:
            replay = AuthorityRepository(connection).validated_ledger_replay(BRANCH_ID)
        finally:
            connection.close()
        payload_by_event_id = {
            event.event_id: payload
            for event, payload in zip(
                replay.events,
                replay.resolved_inline_payloads,
                strict=True,
            )
        }
        intermediate_payload = payload_by_event_id[intermediate_effect.event_id]
        terminal_payload = payload_by_event_id[terminal_event_id]
        assert intermediate_payload is not None
        assert terminal_payload is not None
        assert (
            intermediate_payload.get("before_content_hash"),
            intermediate_payload.get("memory_content_hash"),
            intermediate_payload.get("version"),
            terminal_payload.get("before_content_hash"),
            terminal_payload.get("memory_content_hash"),
            terminal_payload.get("version"),
        ) == (
            memory.record_header.content_hash,
            intermediate.record_header.content_hash,
            intermediate.version,
            intermediate.record_header.content_hash,
            terminal.record_header.content_hash,
            terminal.version,
        )
        assert all(
            payload is None
            or bridge.record_header.content_hash
            not in (
                payload.get("before_content_hash"),
                payload.get("memory_content_hash"),
            )
            for payload in replay.resolved_inline_payloads
        )


def test_update_receipt_rejects_authenticated_intermediate_memory_fork(
    database: SQLiteDatabase,
) -> None:
    governor, _create_command, _create_proposal, memory = (
        _committed_memory_receipt_fixture(
            database,
            proposal_id="prp-ff1",
            memory_id="mem-ff1",
            submit_event_id="evt-ff1",
            submit_command_id="cmd-ff1",
            decide_command_id="cmd-ff2",
            decision_id="gvd-ff1",
            decision_event_id="evt-ff2",
            effect_event_id="evt-ff3",
        )
    )
    _competing, _first_decision, _first_effect = (
        _append_authenticated_memory_effect(
            database,
            memory,
            suffix="ff4",
            before_content_hash=memory.record_header.content_hash,
            updates={"importance": 0.61},
        )
    )
    selected, _second_decision, _second_effect = (
        _append_authenticated_memory_effect(
            database,
            memory,
            suffix="ff5",
            before_content_hash=memory.record_header.content_hash,
            updates={"importance": 0.62},
        )
    )
    _replace_authority_without_ledger(
        database,
        "autobiographical_memory",
        memory.memory_id,
        selected,
    )
    _update_command, _terminal, _terminal_event_id = (
        _commit_real_importance_successor(
            database,
            governor,
            selected,
            suffix="ff6",
            expect_memory_ancestry_error=True,
        )
    )


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        pytest.param("before_content_hash", "f" * 64, id="before-content-hash"),
        pytest.param("version", 9, id="version"),
        pytest.param("semantic_version", 9, id="semantic-version"),
        pytest.param("state", "contested", id="state"),
        pytest.param("proposal_type", "set_consolidation", id="proposal-type"),
        pytest.param(
            "event_type",
            "memory_expression_policy_changed",
            id="ledger-event-type",
        ),
    ),
)
def test_commit_receipt_rejects_unresigned_graph_field_tamper_at_binding(
    database: SQLiteDatabase,
    field_name: str,
    replacement: object,
) -> None:
    governor, create_command, create_proposal, memory = (
        _committed_memory_receipt_fixture(
            database,
            proposal_id="prp-a71",
            memory_id="mem-a71",
            submit_event_id="evt-a71",
            submit_command_id="cmd-a71",
            decide_command_id="cmd-a72",
            decision_id="gvd-a71",
            decision_event_id="evt-a72",
            effect_event_id="evt-a73",
        )
    )
    _update_command, updated, effect_event_id = _commit_real_importance_successor(
        database,
        governor,
        memory,
        suffix="a74",
    )
    decision_event_id = "evt-a742"
    if field_name == "event_type":
        _rewrite_ledger_tail_payload(
            database,
            effect_event_id,
            {},
            event_updates={"event_type": replacement},
        )
    else:
        _rewrite_ledger_tail_payload(
            database,
            effect_event_id,
            {field_name: replacement},
        )

    connection = database.connect()
    try:
        repository = AuthorityRepository(connection)
        replay = repository.validated_ledger_replay(BRANCH_ID)
        decision = repository.get_validated("gvd-a741")
    finally:
        connection.close()
    event_payloads = {
        event.event_id: (event, payload)
        for event, payload in zip(
            replay.events,
            replay.resolved_inline_payloads,
            strict=True,
        )
    }
    decision_event, decision_payload = event_payloads[decision_event_id]
    effect_event, effect_payload = event_payloads[effect_event_id]
    assert isinstance(decision, GovernorDecision)
    assert decision_payload is not None
    assert effect_payload is not None
    committed_event_ids = (decision_event_id, effect_event_id)
    binding_kwargs: dict[str, object] = {
        "result": "commit",
        "committed_event_ids": committed_event_ids,
        "memory_payload": effect_payload,
    }
    if "memory_event_type" in inspect.signature(
        receipt_output_binding_from_payloads
    ).parameters:
        binding_kwargs["memory_event_type"] = effect_event.event_type
    recomputed = receipt_output_binding_from_payloads(
        decision_payload,
        decision_payload,
        **binding_kwargs,  # type: ignore[arg-type]
    )
    stored = decision_payload.get("receipt_output_binding_hash")
    signature = decision_payload.get("receipt_output_signature")
    decision_content_hash = decision_payload.get("decision_content_hash")
    assert isinstance(recomputed, str)
    assert isinstance(stored, str)
    assert isinstance(signature, str)
    assert isinstance(decision_content_hash, str)

    assert recomputed != stored, f"output binding omitted {field_name}"
    assert not _decision_attestor().verify(
        signature,
        decision_content_hash=receipt_output_attestation_subject_hash(
            decision_content_hash=decision_content_hash,
            output_binding_hash=recomputed,
        ),
        command_hash=decision_event.mutation_command_hash,
        actor_id=decision_event.actor_id,
    )
    assert (
        receipt_ancestry._decision_event_is_authenticated(
            decision_event,
            decision_payload,
            expected_result="commit",
            expected_event_ids=committed_event_ids,
            expected_scope=(IDENTITY_ID, LINEAGE_ID, BRANCH_ID, VAULT_ID),
            expected_target_refs=(updated.memory_id,),
            target_payload=decision_payload,
            decision_authorities={decision.decision_id: decision},
            decision_attestor=_decision_attestor(),
            memory_payload=effect_payload,
            memory_event_type=effect_event.event_type,
        )
        is False
    )

    with pytest.raises(
        ReceiptIntegrityError,
        match=r"^GovernorDecision receipt does not anchor historical Memory authority$",
    ):
        governor.decide(create_command, create_proposal.proposal_id, NOW)


def test_memory_authority_replay_rejects_length_mismatch(
    database: SQLiteDatabase,
) -> None:
    _governor, _command_before, _proposal_before, memory = (
        _committed_memory_receipt_fixture(
            database,
            proposal_id="prp-a81",
            memory_id="mem-a81",
            submit_event_id="evt-a81",
            submit_command_id="cmd-a81",
            decide_command_id="cmd-a82",
            decision_id="gvd-a81",
            decision_event_id="evt-a82",
            effect_event_id="evt-a83",
        )
    )
    historical_event = _load(database, "evt-a83")
    assert isinstance(historical_event, LedgerEvent)

    assert not receipt_ancestry.memory_authority_has_ledger_ancestry(
        memory,
        historical_event=historical_event,
        historical_payload=None,
        replay_events=(),
        replay_payloads=(None,),
        decision_authorities={},
        decision_attestor=_decision_attestor(),
    )


def test_memory_authority_replay_does_not_materialize_replay_pairs() -> None:
    source = dedent(
        inspect.getsource(receipt_ancestry.memory_authority_has_ledger_ancestry)
    )
    function = ast.parse(source).body[0]
    assert isinstance(function, ast.FunctionDef)
    offenders: list[str] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"tuple", "list", "dict", "set"}:
            continue
        if any(
            isinstance(descendant, ast.Call)
            and isinstance(descendant.func, ast.Name)
            and descendant.func.id == "zip"
            and {
                argument.id
                for argument in descendant.args
                if isinstance(argument, ast.Name)
            }
            >= {"replay_events", "replay_payloads"}
            for descendant in ast.walk(node)
        ):
            offenders.append(node.func.id)

    assert offenders == [], f"materialized replay pairs via {offenders}"



def test_receipt_output_binding_compute_rejects_memory_created_predecessor_hash(
) -> None:
    memory_effect: dict[str, object] = {
        "event_type": "memory_created",
        "operation": "create",
        "decision_id": "a1000001",
        "proposal_id": "a1000002",
        "proposal_type": "create_memory",
        "memory_id": "a1000003",
        "before_content_hash": None,
        "memory_content_hash": "2" * 64,
        "state": "active",
        "semantic_version": 1,
        "version": 1,
    }
    legal_binding = compute_receipt_output_binding_hash(
        decision_id="a1000001",
        proposal_id="a1000002",
        proposal_type="create_memory",
        result="commit",
        committed_event_ids=("a1000004", "a1000005"),
        proposal_after_content_hash="1" * 64,
        memory_effect=memory_effect,
    )
    assert isinstance(legal_binding, str)
    assert len(legal_binding) == 64

    memory_effect_with_predecessor = {
        **memory_effect,
        "before_content_hash": "3" * 64,
    }
    with pytest.raises(
        ValueError,
        match=r"^invalid Governor receipt output descriptor$",
    ):
        compute_receipt_output_binding_hash(
            decision_id="a1000001",
            proposal_id="a1000002",
            proposal_type="create_memory",
            result="commit",
            committed_event_ids=("a1000004", "a1000005"),
            proposal_after_content_hash="1" * 64,
            memory_effect=memory_effect_with_predecessor,
        )


def test_receipt_output_binding_replay_rejects_memory_created_predecessor_hash(
) -> None:
    decision_payload: dict[str, object] = {
        "decision_id": "b2000001",
        "proposal_id": "b2000002",
        "proposal_type": "create_memory",
    }
    projection_payload: dict[str, object] = {
        "proposal_content_hash": "4" * 64,
    }
    memory_payload: dict[str, object] = {
        "decision_id": "b2000001",
        "proposal_id": "b2000002",
        "proposal_type": "create_memory",
        "memory_id": "b2000003",
        "before_content_hash": None,
        "memory_content_hash": "5" * 64,
        "state": "active",
        "semantic_version": 1,
        "version": 1,
    }
    legal_binding = receipt_output_binding_from_payloads(
        decision_payload,
        projection_payload,
        result="commit",
        committed_event_ids=("b2000004", "b2000005"),
        memory_payload=memory_payload,
        memory_event_type="memory_created",
    )
    assert isinstance(legal_binding, str)
    assert len(legal_binding) == 64

    memory_payload_with_predecessor = {
        **memory_payload,
        "before_content_hash": "6" * 64,
    }
    assert (
        receipt_output_binding_from_payloads(
            decision_payload,
            projection_payload,
            result="commit",
            committed_event_ids=("b2000004", "b2000005"),
            memory_payload=memory_payload_with_predecessor,
            memory_event_type="memory_created",
        )
        is None
    )
