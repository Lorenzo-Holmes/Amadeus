from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from amadeus_core.contracts.commands import (
    Actor,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.governance.proposal_service import ProposalService
from amadeus_core.storage.payloads import canonical_receipt_result
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
INSTANCE_ID = "ins-a1"
VAULT_ID = "vlt-a1"
LLM_ID = "llm-a1"
DEPLOYMENT_POLICY_REF = "deployment:test"


def _seal(model_type: type[Any], body: dict[str, object]):
    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": digest}
            )
        }
    )


def _proposal() -> Proposal:
    proposal_id = "prp-c1"
    event_id = "evt-c1"
    return _seal(
        Proposal,
        {
            "record_header": {
                "schema_version": "0.1",
                "record_type": "Proposal",
                "record_id": proposal_id,
                "identity_id": IDENTITY_ID,
                "lineage_id": LINEAGE_ID,
                "branch_id": BRANCH_ID,
                "created_at": NOW,
                "created_by_event_id": event_id,
                "deployment_policy_ref": DEPLOYMENT_POLICY_REF,
                "canonicalization": "core-canonical-json-v1",
                "hash_algorithm": "sha256",
                "hash_scope_registry_version": (
                    "core-hash-scope-registry-v0.1"
                ),
                "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
                "hash_scope": HASH_SCOPE_REGISTRY[("Proposal", "0.1")],
                "content_hash": "0" * 64,
            },
            "proposal_id": proposal_id,
            "proposal_type": "lifecycle_transition",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": LLM_ID},
            "target_refs": (IDENTITY_ID,),
            "evidence_refs": (GENESIS_EVENT_ID,),
            "proposed_patch": {"requested_action": "maintenance_paused"},
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=1),
            "status": "pending",
            "deferred_at": None,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": None,
            },
            "reopened_count": 0,
            "version": 1,
        },
    )


def _proposal_command(proposal: Proposal) -> MutationCommandEnvelope:
    event_id = proposal.record_header.created_by_event_id
    targets = (proposal.proposal_id, event_id)
    return MutationCommandEnvelope(
        command_id="cmd-c1",
        command_type="memory_proposal.submit",
        actor=Actor(actor_type="llm", actor_id=LLM_ID),
        actor_capability_id="cap-c1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-c1",
        idempotency_key="proposal-receipt-c1",
        issued_at=NOW,
        target_record_refs=targets,
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                *proposal.target_refs,
                *proposal.evidence_refs,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            "semantic_input_hash": sha256_hex(
                canonical_json(proposal.model_dump(mode="python"))
            ),
        },
    )


def _replace_receipt_value(database, command_id: str, value: object) -> None:
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT result_json FROM command_receipts WHERE command_id = ?",
            (command_id,),
        ).fetchone()
        assert row is not None
        result_payload = json.loads(row[0])
        result_payload["value"] = value
        tampered_json = canonical_receipt_result(result_payload).decode("utf-8")
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        try:
            connection.execute(
                """
                UPDATE command_receipts
                SET result_json = ?, result_hash = ?
                WHERE command_id = ?
                """,
                (
                    tampered_json,
                    sha256_hex(tampered_json.encode("utf-8")),
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
    finally:
        connection.close()


@pytest.mark.parametrize(
    "tamper_kind",
    ("wrong_record_id_resealed", "wrong_content_hash"),
)
def test_request_replay_rejects_receipt_value_not_matching_authority(
    tamper_kind: str,
    database,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    request = request_factory(
        "correction_request",
        request_id="req-c1",
        event_id="evt-c2",
    )
    command = request_command_factory(request, event_id="evt-c2")
    first = request_service.submit(command, request)
    assert first.error is None

    if tamper_kind == "wrong_record_id_resealed":
        draft = request.model_copy(
            update={
                "request_id": "req-c2",
                "record_header": request.record_header.model_copy(
                    update={
                        "record_id": "req-c2",
                        "content_hash": "0" * 64,
                    }
                ),
            }
        )
        tampered = draft.model_copy(
            update={
                "record_header": draft.record_header.model_copy(
                    update={"content_hash": compute_record_content_hash(draft)}
                )
            }
        )
    else:
        tampered = request.model_copy(
            update={
                "record_header": request.record_header.model_copy(
                    update={"content_hash": "f" * 64}
                )
            }
        )
    _replace_receipt_value(
        database,
        command.command_id,
        tampered.model_dump(mode="json"),
    )

    with pytest.raises(ReceiptIntegrityError):
        request_service.submit(command, request)


def test_proposal_replay_rejects_resealed_wrong_authority_id(database) -> None:
    service = ProposalService(database)
    proposal = _proposal()
    command = _proposal_command(proposal)
    first = service.submit(command, proposal)
    assert first.error is None

    draft = proposal.model_copy(
        update={
            "proposal_id": "prp-c2",
            "record_header": proposal.record_header.model_copy(
                update={"record_id": "prp-c2", "content_hash": "0" * 64}
            ),
        }
    )
    tampered = draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": compute_record_content_hash(draft)}
            )
        }
    )
    _replace_receipt_value(
        database,
        command.command_id,
        tampered.model_dump(mode="json"),
    )

    with pytest.raises(ReceiptIntegrityError):
        service.submit(command, proposal)
