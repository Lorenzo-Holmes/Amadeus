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


class SourceSnapshot(FrozenModel):
    record_header: RecordHeader
    snapshot_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    source_type: Literal['import', 'reconstruction', 'migration']
    source_ref: str
    cutoff_at: UtcDatetime
    imported_at: UtcDatetime
    manifest_hash: HashHex
    payload_root_hash: HashHex
    parent_snapshot_id: RecordId | None
    deployment_policy_ref: str
    status: Literal['active', 'superseded', 'quarantined']
    version: PositiveVersion

__all__ = [
    'SourceSnapshot',
]
