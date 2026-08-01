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


class Proposal(FrozenModel):
    record_header: RecordHeader
    proposal_id: RecordId
    proposal_type: Literal['create_memory', 'change_memory_state', 'change_expression_policy', 'set_importance', 'set_consolidation', 'lifecycle_transition', 'maintenance_trigger']
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId | None
    proposed_by: ProposalActor
    target_refs: tuple[RecordId, ...]
    evidence_refs: tuple[RecordId, ...]
    proposed_patch: JsonObject
    created_at: UtcDatetime
    expires_at: UtcDatetime
    status: Literal['pending', 'committed', 'rejected', 'deferred', 'expired']
    deferred_at: UtcDatetime | None
    defer_conditions: DeferConditions
    reopened_count: int
    version: PositiveVersion

class GovernorDecision(FrozenModel):
    record_header: RecordHeader
    decision_id: RecordId
    proposal_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId | None
    result: Literal['commit', 'reject', 'defer']
    policy_version: str
    input_state_hash: HashHex
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[RecordId, ...]
    committed_event_ids: tuple[RecordId, ...]
    output_state_hash: HashHex
    decided_at: UtcDatetime
    governor_signature: str
    version: PositiveVersion

__all__ = [
    'Proposal',
    'GovernorDecision',
]
