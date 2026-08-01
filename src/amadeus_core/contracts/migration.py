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


class MigrationPlan(FrozenModel):
    record_header: RecordHeader
    migration_id: RecordId
    identity_id: RecordId
    source_branch_id: RecordId
    target_branch_id: RecordId
    lineage_id: RecordId
    source_schema_version: str
    target_schema_version: str
    compatibility: Literal['compatible', 'incompatible']
    transformation_manifest_ref: str
    pre_root_hash: HashHex
    expected_post_root_hash: HashHex
    rollback_ref: str
    capability_id: RecordId
    status: Literal['planned', 'running', 'verified', 'failed', 'rolled_back']
    version: PositiveVersion

__all__ = [
    'MigrationPlan',
]
