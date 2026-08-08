"""Closed v0.1 registry for authoritative write entry points."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class WriteApiSpec:
    api_name: str
    mutation_command_parameter: str
    actor_types: tuple[str, ...]
    target_record_types: tuple[str, ...]
    emitted_event_types: tuple[str, ...]


WRITE_API_REGISTRY = (
    WriteApiSpec(
        "bootstrap_core",
        "mutation_command",
        ("system",),
        ("Identity", "Lineage", "Branch", "LedgerEvent"),
        ("identity_genesis_created",),
    ),
    WriteApiSpec(
        "import_source_snapshot",
        "mutation_command",
        ("system", "amadeus"),
        ("SourceSnapshot", "Identity", "Lineage", "LedgerEvent"),
        ("source_snapshot_imported",),
    ),
    WriteApiSpec(
        "append_session_event",
        "mutation_command",
        ("system", "amadeus", "user"),
        ("LedgerEvent",),
        ("session_started", "conversation_message_recorded", "session_ended"),
    ),
    WriteApiSpec(
        "pause_vault_contact",
        "mutation_command",
        ("amadeus", "user"),
        ("RelationshipVault", "LedgerEvent"),
        ("contact_paused",),
    ),
    WriteApiSpec(
        "submit_memory_request",
        "mutation_command",
        ("amadeus", "user"),
        ("MemoryRequest", "LedgerEvent"),
        (
            "confidentiality_request_submitted",
            "correction_request_submitted",
            "non_mention_request_submitted",
        ),
    ),
    WriteApiSpec(
        "submit_proposal",
        "mutation_command",
        ("llm", "amadeus", "system"),
        ("Proposal", "LedgerEvent"),
        ("proposal_submitted",),
    ),
    WriteApiSpec(
        "decide_memory_proposal",
        "mutation_command",
        ("governor",),
        ("Proposal", "GovernorDecision", "AutobiographicalMemory", "LedgerEvent"),
        (
            "governor_decision_committed",
            "governor_decision_rejected",
            "governor_decision_deferred",
            "proposal_deferred",
            "memory_created",
            "memory_state_changed",
            "memory_expression_policy_changed",
            "proposal_reopened",
            "proposal_expired",
        ),
    ),
    WriteApiSpec(
        "issue_vault_read_capability",
        "mutation_command",
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_issued", "vault_read_capability_denied"),
    ),
    WriteApiSpec(
        "revoke_vault_read_capability",
        "mutation_command",
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_revoked", "vault_read_capability_denied"),
    ),
    WriteApiSpec(
        "expire_vault_read_capability",
        "mutation_command",
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_expired", "vault_read_capability_denied"),
    ),
    WriteApiSpec(
        "record_vault_read_decision",
        "mutation_command",
        ("governor", "system"),
        ("LedgerEvent",),
        ("vault_read_capability_used", "vault_read_capability_denied"),
    ),
    WriteApiSpec(
        "rebuild_materialized_views",
        "mutation_command",
        ("maintainer",),
        ("LedgerEvent",),
        (
            "materialized_view_rebuilt",
            "derived_view_validation_failed",
            "derived_view_fallback",
        ),
    ),
)

WRITE_API_BY_NAME = MappingProxyType(
    {spec.api_name: spec for spec in WRITE_API_REGISTRY}
)


__all__ = ["WRITE_API_BY_NAME", "WRITE_API_REGISTRY", "WriteApiSpec"]
