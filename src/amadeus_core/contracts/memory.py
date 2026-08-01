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


class AutobiographicalMemory(FrozenModel):
    record_header: RecordHeader
    memory_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    governing_vault_id: RecordId
    semantic_kind: Literal['episode', 'relationship', 'preference', 'commitment', 'self_model', 'other']
    state: Literal['active', 'contested', 'superseded', 'archived']
    importance: float
    consolidation_state: Literal['candidate', 'consolidated', 'stable', 'decayed']
    expression_policy: ExpressionPolicy
    evidence_event_refs: tuple[RecordId, ...]
    supersedes_memory_ids: tuple[RecordId, ...]
    contested_by_event_ids: tuple[RecordId, ...]
    governor_decision_id: RecordId
    semantic_version: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
    version: PositiveVersion

__all__ = [
    'AutobiographicalMemory',
]
