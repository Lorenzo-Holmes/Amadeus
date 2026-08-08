"""Stable read snapshots that keep SQLite details inside the storage boundary."""

from __future__ import annotations

from dataclasses import dataclass

from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.common import FrozenModel
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.contracts.vault import RelationshipVault

from .database import SQLiteDatabase
from .ledger import LedgerReplayResult, replay_ledger
from .repository import AuthorityRepository


@dataclass(frozen=True, slots=True)
class ProposalAuthorityBinding:
    proposal_id: str
    identity: Identity | None
    lineage: Lineage | None
    branch: Branch | None
    vault: RelationshipVault | None


@dataclass(frozen=True, slots=True)
class ProposalReadSnapshot:
    proposals: tuple[Proposal, ...]
    bindings: tuple[ProposalAuthorityBinding, ...]
    branch_replays: tuple[tuple[str, LedgerReplayResult], ...]

    def binding_for(self, proposal_id: str) -> ProposalAuthorityBinding | None:
        for binding in self.bindings:
            if binding.proposal_id == proposal_id:
                return binding
        return None

    def events_for(self, branch_id: str) -> tuple[LedgerEvent, ...]:
        replay = self.replay_for(branch_id)
        return () if replay is None else replay.events

    def replay_for(self, branch_id: str) -> LedgerReplayResult | None:
        for candidate_branch_id, replay in self.branch_replays:
            if candidate_branch_id == branch_id:
                return replay
        return None


class SQLiteAuthorityReader:
    """Own read transactions and return integrity-checked authority snapshots."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def get_validated(self, record_id: str) -> FrozenModel | None:
        connection = self._database.connect()
        try:
            connection.execute("BEGIN")
            return AuthorityRepository(connection).get_validated(record_id)
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()

    def proposal_snapshot(self) -> ProposalReadSnapshot:
        connection = self._database.connect()
        try:
            connection.execute("BEGIN")
            repository = AuthorityRepository(connection)
            rows = connection.execute(
                """
                SELECT record_id
                FROM authority_records
                WHERE record_type = 'Proposal'
                ORDER BY record_id
                """
            ).fetchall()
            proposals: list[Proposal] = []
            for row in rows:
                record = repository.get_validated(row["record_id"])
                if not isinstance(record, Proposal):
                    raise TypeError("Proposal authority row has the wrong model type")
                proposals.append(record)
            bindings = tuple(
                ProposalAuthorityBinding(
                    proposal_id=proposal.proposal_id,
                    identity=(
                        candidate
                        if isinstance(
                            candidate := repository.get_validated(
                                proposal.identity_id
                            ),
                            Identity,
                        )
                        else None
                    ),
                    lineage=(
                        candidate
                        if isinstance(
                            candidate := repository.get_validated(
                                proposal.lineage_id
                            ),
                            Lineage,
                        )
                        else None
                    ),
                    branch=(
                        candidate
                        if isinstance(
                            candidate := repository.get_validated(
                                proposal.branch_id
                            ),
                            Branch,
                        )
                        else None
                    ),
                    vault=(
                        None
                        if proposal.vault_id is None
                        else (
                            candidate
                            if isinstance(
                                candidate := repository.get_validated(
                                    proposal.vault_id
                                ),
                                RelationshipVault,
                            )
                            else None
                        )
                    ),
                )
                for proposal in proposals
            )
            branch_replays = tuple(
                (
                    branch_id,
                    replay_ledger(connection, branch_id),
                )
                for branch_id in sorted(
                    {proposal.branch_id for proposal in proposals}
                )
            )
            return ProposalReadSnapshot(
                proposals=tuple(proposals),
                bindings=bindings,
                branch_replays=branch_replays,
            )
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


__all__ = [
    "ProposalAuthorityBinding",
    "ProposalReadSnapshot",
    "SQLiteAuthorityReader",
]
