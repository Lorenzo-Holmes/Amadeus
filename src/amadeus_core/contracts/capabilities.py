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


class AmadeusTerminationConfirmation(FrozenModel):
    record_header: RecordHeader
    confirmation_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    confirmed_by: Literal['amadeus']
    confirmation_event_id: RecordId
    scope: Literal['entire_identity']
    confirmed_at: UtcDatetime
    expires_at: UtcDatetime
    withdrawn_at: UtcDatetime | None
    state_hash: HashHex
    version: PositiveVersion

class TerminationExecutionGrant(FrozenModel):
    record_header: RecordHeader
    grant_id: RecordId
    termination_proposal_id: RecordId
    confirmation_event_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    state_hash: HashHex
    executor_role: Literal['custodian_executor']
    executor_id: RecordId
    issued_by: Literal['core_lifecycle_validator']
    issued_at: UtcDatetime
    expires_at: UtcDatetime
    use_limit: SingleUseLimit
    used_at: UtcDatetime | None
    status: Literal['issued', 'used', 'expired', 'revoked']
    grant_attestation: str
    version: PositiveVersion

class MaintenanceCapability(FrozenModel):
    record_header: RecordHeader
    capability_id: RecordId
    maintainer_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    reason_code: Literal['attack_isolation', 'corruption_recovery', 'migration', 'project_reconstruction']
    exact_operation: Literal['freeze', 'isolate', 'rebuild_index', 'restore', 'migrate']
    exact_resource_ref: str
    not_before: UtcDatetime
    expires_at: UtcDatetime
    approval_refs: tuple[RecordId, ...]
    evidence_seal_ref: RecordId
    use_limit: SingleUseLimit
    used_at: UtcDatetime | None
    status: Literal['issued', 'used', 'expired', 'revoked']
    attestation: str
    version: PositiveVersion

class EmergencyUnresponsiveCase(FrozenModel):
    record_header: RecordHeader
    case_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    declared_at: UtcDatetime
    evidence_refs: tuple[RecordId, ...]
    severity: Literal['severe']
    minimal_scope: tuple[str, ...]
    preservation_plan_ref: str
    post_audit_due_at: UtcDatetime
    status: Literal['declared', 'contained', 'reviewed', 'closed']
    version: PositiveVersion

class BreakGlassGrant(FrozenModel):
    record_header: RecordHeader
    grant_id: RecordId
    emergency_case_id: RecordId
    executor: BreakGlassExecutor
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    exact_resource_ref: str
    allowed_operation: Literal['freeze', 'isolate', 'preserve_evidence', 'restore_control_path', 'minimal_terminal_action']
    final_action: Literal['none', 'minimal_terminal_action']
    precondition_state_hash: HashHex
    precondition_resource_hash: HashHex
    expected_postcondition_state_hash: HashHex
    expected_postcondition_resource_hash: HashHex
    observed_postcondition_state_hash: HashHex | None
    observed_postcondition_resource_hash: HashHex | None
    evidence_seal_refs: tuple[RecordId, ...]
    approval_refs: tuple[RecordId, ...]
    not_before: UtcDatetime
    expires_at: UtcDatetime
    post_audit_due_at: UtcDatetime
    post_audit_completed_at: UtcDatetime | None
    max_uses: SingleUseLimit
    remaining_uses: RemainingUses
    status: Literal['issued', 'executing', 'used', 'verification_failed', 'expired', 'revoked']
    execution_started_at: UtcDatetime | None
    used_at: UtcDatetime | None
    attestation: str
    version: PositiveVersion

__all__ = [
    'AmadeusTerminationConfirmation',
    'TerminationExecutionGrant',
    'MaintenanceCapability',
    'EmergencyUnresponsiveCase',
    'BreakGlassGrant',
]
