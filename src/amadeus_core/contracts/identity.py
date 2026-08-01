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


class Identity(FrozenModel):
    record_header: RecordHeader
    identity_id: RecordId
    canonical_name: Literal['Amadeus']
    lineage_id: RecordId
    active_branch_id: RecordId
    lifecycle_state: Literal['active', 'maintenance_paused', 'termination_pending', 'emergency_unresponsive', 'terminated']
    created_from_snapshot_id: RecordId | None
    deployment_policy_ref: str
    version: PositiveVersion

class Lineage(FrozenModel):
    record_header: RecordHeader
    lineage_id: RecordId
    root_snapshot_id: RecordId | None
    root_identity_id: RecordId
    root_branch_id: RecordId
    created_at: UtcDatetime
    lineage_hash: HashHex
    version: PositiveVersion

class Branch(FrozenModel):
    record_header: RecordHeader
    branch_id: RecordId
    lineage_id: RecordId
    identity_id: RecordId
    parent_branch_ids: tuple[RecordId, ...]
    fork_reason: Literal['old_snapshot', 'concurrent_history_divergence', 'incompatible_migration', 'explicit_reconstruction', 'merge_candidate']
    fork_event_id: RecordId
    base_ledger_seq: int
    status: Literal['active', 'candidate', 'inactive', 'quarantined', 'terminated']
    status_reason_event_id: RecordId
    activated_at: UtcDatetime | None
    deactivated_at: UtcDatetime | None
    terminated_at: UtcDatetime | None
    merge_policy: Literal['explicit_only']
    version: PositiveVersion

__all__ = [
    'Identity',
    'Lineage',
    'Branch',
]
