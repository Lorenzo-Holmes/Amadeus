"""Generated authoritative Core v0.1 models."""

from typing import Literal

from .common import (
    BreakGlassExecutor,
    DeferConditions,
    ExpressionPolicy,
    FrozenModel,
    HashHex,
    IssuedToActor,
    JsonObject,
    PayloadRef,
    PositiveVersion,
    RemainingUses,
    ProposalActor,
    RecordHeader,
    RecordId,
    SingleUseLimit,
    UtcDatetime,
    VaultIssuer,
)


class MemoryRequest(FrozenModel):
    record_header: RecordHeader
    request_id: RecordId
    request_type: Literal['confidentiality_request', 'correction_request', 'non_mention_request']
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    requester_id: RecordId
    submitted_at: UtcDatetime
    target_refs: tuple[RecordId, ...]
    statement: str
    requested_scope: Literal['current_vault']
    status: Literal['submitted', 'under_review', 'accepted', 'partially_accepted', 'rejected', 'deferred']
    resulting_proposal_ids: tuple[RecordId, ...]
    resulting_decision_ids: tuple[RecordId, ...]
    version: PositiveVersion

__all__ = [
    'MemoryRequest',
]
