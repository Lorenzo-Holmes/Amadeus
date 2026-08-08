from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.records import record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository


NOW = datetime(2026, 8, 1, tzinfo=UTC)
IDENTITY_ID = "idn-a"
LINEAGE_ID = "lin-a"
BRANCH_ID = "brn-a"
PROPOSAL_ID = "prp-d1"
DECISION_ID = "gvd-d1"


def _proposal() -> Proposal:
    return seal_record(
        Proposal,
        {
            "record_header": record_header(
                "Proposal",
                PROPOSAL_ID,
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id="evt-a",
                deployment_policy_ref="deployment:test",
            ),
            "proposal_id": PROPOSAL_ID,
            "proposal_type": "create_memory",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": None,
            "proposed_by": {"actor_type": "llm", "actor_id": "llm-d1"},
            "target_refs": (),
            "evidence_refs": (),
            "proposed_patch": {},
            "created_at": NOW,
            "expires_at": NOW + timedelta(hours=1),
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


def _decision(proposal: Proposal) -> GovernorDecision:
    return seal_record(
        GovernorDecision,
        {
            "record_header": record_header(
                "GovernorDecision",
                DECISION_ID,
                identity_id=IDENTITY_ID,
                lineage_id=LINEAGE_ID,
                branch_id=BRANCH_ID,
                created_at=NOW,
                created_by_event_id="evt-d1",
                deployment_policy_ref="deployment:test",
            ),
            "decision_id": DECISION_ID,
            "proposal_id": proposal.proposal_id,
            "identity_id": proposal.identity_id,
            "lineage_id": proposal.lineage_id,
            "branch_id": proposal.branch_id,
            "vault_id": proposal.vault_id,
            "result": "defer",
            "policy_version": "governor-policy:test",
            "input_state_hash": proposal.record_header.content_hash,
            "reason_codes": ("missing_evidence",),
            "evidence_refs": (),
            "committed_event_ids": ("evt-d1", "evt-d2"),
            "output_state_hash": "2" * 64,
            "decided_at": NOW,
            "governor_signature": "governor-signature:test",
            "version": 1,
        },
    )


@pytest.mark.parametrize("projection_mutation", ("result_mismatch", "missing"))
def test_get_validated_governor_decision_fails_closed_on_projection_divergence(
    database_path: Path,
    standard_seed: Callable[..., None],
    projection_mutation: str,
) -> None:
    database = SQLiteDatabase(database_path)
    standard_seed(database)
    proposal = _proposal()
    decision = _decision(proposal)

    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(PROPOSAL_ID, DECISION_ID),
        )
        repository.save_authoritative(
            "proposal",
            proposal.model_dump(mode="python"),
        )
        repository.save_authoritative(
            "governor_decision",
            decision.model_dump(mode="python"),
        )
        connection.commit()

        assert AuthorityRepository(connection).get_validated(DECISION_ID) == decision
        if projection_mutation == "result_mismatch":
            connection.execute(
                "UPDATE governor_decisions SET result = 'reject' WHERE decision_id = ?",
                (DECISION_ID,),
            )
        else:
            connection.execute(
                "DELETE FROM governor_decisions WHERE decision_id = ?",
                (DECISION_ID,),
            )

        with pytest.raises(CoreContractViolation) as raised:
            AuthorityRepository(connection).get_validated(DECISION_ID)
        assert raised.value.code is CoreErrorCode.HEADER_BODY_MISMATCH
    finally:
        connection.close()
