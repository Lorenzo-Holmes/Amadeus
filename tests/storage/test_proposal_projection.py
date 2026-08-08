from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.records import record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository


NOW = datetime(2026, 8, 1, tzinfo=UTC)
IDENTITY_ID = "idn-a"
LINEAGE_ID = "lin-a"
BRANCH_ID = "brn-a"
PROPOSAL_ID = "prp-a"


def _pending_proposal() -> Proposal:
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
            "proposed_by": {"actor_type": "llm", "actor_id": "mdl-a"},
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


@pytest.mark.parametrize("projection_mutation", ("status_mismatch", "missing"))
def test_get_validated_proposal_fails_closed_on_projection_divergence(
    database_path: Path,
    standard_seed: Callable[..., None],
    projection_mutation: str,
) -> None:
    database = SQLiteDatabase(database_path)
    standard_seed(database)
    proposal = _pending_proposal()

    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(PROPOSAL_ID,),
        ).save_authoritative("proposal", proposal.model_dump(mode="python"))
        connection.commit()

        assert AuthorityRepository(connection).get_validated(PROPOSAL_ID) == proposal
        if projection_mutation == "status_mismatch":
            connection.execute(
                "UPDATE proposals SET status = 'deferred' WHERE proposal_id = ?",
                (PROPOSAL_ID,),
            )
        else:
            connection.execute(
                "DELETE FROM proposals WHERE proposal_id = ?",
                (PROPOSAL_ID,),
            )

        with pytest.raises(CoreContractViolation) as raised:
            AuthorityRepository(connection).get_validated(PROPOSAL_ID)
        assert raised.value.code is CoreErrorCode.HEADER_BODY_MISMATCH
    finally:
        connection.close()
