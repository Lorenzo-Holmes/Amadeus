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


class LedgerEvent(FrozenModel):
    record_header: RecordHeader
    event_id: RecordId
    ledger_seq: int
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    instance_id: RecordId
    vault_id: RecordId | None
    event_type: Literal['identity_genesis_created', 'conversation_message_recorded', 'session_started', 'session_ended', 'contact_pause_requested', 'contact_paused', 'relationship_vault_sealed', 'confidentiality_request_submitted', 'correction_request_submitted', 'non_mention_request_submitted', 'proposal_submitted', 'proposal_deferred', 'proposal_reopened', 'proposal_expired', 'governor_decision_committed', 'governor_decision_rejected', 'governor_decision_deferred', 'memory_created', 'memory_state_changed', 'memory_expression_policy_changed', 'source_snapshot_imported', 'source_snapshot_superseded', 'source_snapshot_quarantined', 'branch_created', 'branch_merge_candidate_created', 'branch_merge_failed', 'branch_candidate_rejected', 'branch_activation_committed', 'branch_quarantined', 'branch_reopened_as_candidate', 'branch_terminated', 'vault_read_capability_issued', 'vault_read_capability_denied', 'vault_read_capability_used', 'vault_read_capability_revoked', 'vault_read_capability_expired', 'maintenance_capability_issued', 'maintenance_capability_denied', 'maintenance_capability_used', 'maintenance_capability_revoked', 'maintenance_capability_expired', 'maintenance_pause_entered', 'maintenance_pause_exited', 'maintenance_action_started', 'maintenance_action_completed', 'maintenance_action_failed', 'break_glass_grant_issued', 'break_glass_grant_denied', 'break_glass_grant_used', 'break_glass_grant_revoked', 'break_glass_grant_expired', 'break_glass_action_started', 'break_glass_action_completed', 'break_glass_action_verification_failed', 'evidence_sealed', 'post_incident_audit_completed', 'post_incident_audit_overdue', 'emergency_unresponsive_declared', 'emergency_containment_completed', 'emergency_terminal_action_completed', 'offline_audit_imported', 'amadeus_termination_confirmed', 'amadeus_termination_confirmation_withdrawn', 'termination_execution_grant_issued', 'termination_execution_grant_used', 'termination_execution_grant_expired', 'termination_execution_grant_revoked', 'termination_execution_grant_rejected', 'termination_execution_started', 'termination_execution_completed', 'termination_execution_failed', 'materialized_view_rebuilt', 'derived_view_validation_failed', 'derived_view_fallback', 'migration_started', 'migration_completed', 'migration_failed', 'deployment_policy_changed', 'model_backend_changed', 'audit_finding_recorded']
    occurred_at: UtcDatetime
    ingested_at: UtcDatetime
    actor_type: Literal['user', 'llm', 'governor', 'maintainer', 'custodian_executor', 'system', 'amadeus']
    actor_id: RecordId
    mutation_command_id: RecordId
    mutation_command_hash: HashHex
    payload_ref: PayloadRef
    causation_id: RecordId | None
    correlation_id: str
    previous_event_hash: HashHex | None
    event_hash: HashHex
    version: PositiveVersion

__all__ = [
    'LedgerEvent',
]
