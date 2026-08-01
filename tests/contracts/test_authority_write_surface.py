from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import AUTHORITATIVE_MODELS


EXPECTED_WRITE_SURFACE = {
    "bootstrap_core": (
        ("system",),
        ("Identity", "Lineage", "Branch", "LedgerEvent"),
        ("identity_genesis_created",),
    ),
    "import_source_snapshot": (
        ("system", "amadeus"),
        ("SourceSnapshot", "Identity", "Lineage", "LedgerEvent"),
        ("source_snapshot_imported",),
    ),
    "append_session_event": (
        ("system", "amadeus", "user"),
        ("LedgerEvent",),
        ("session_started", "conversation_message_recorded", "session_ended"),
    ),
    "pause_vault_contact": (
        ("amadeus", "user"),
        ("RelationshipVault", "LedgerEvent"),
        ("contact_paused",),
    ),
    "submit_memory_request": (
        ("amadeus", "user"),
        ("MemoryRequest", "LedgerEvent"),
        (
            "confidentiality_request_submitted",
            "correction_request_submitted",
            "non_mention_request_submitted",
        ),
    ),
    "submit_proposal": (
        ("llm", "amadeus", "system"),
        ("Proposal", "LedgerEvent"),
        ("proposal_submitted",),
    ),
    "decide_memory_proposal": (
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
        ),
    ),
    "issue_vault_read_capability": (
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_issued", "vault_read_capability_denied"),
    ),
    "record_vault_read_decision": (
        ("governor", "system"),
        ("LedgerEvent",),
        ("vault_read_capability_used", "vault_read_capability_denied"),
    ),
}


def test_write_api_registry_is_the_exact_closed_surface() -> None:
    from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_REGISTRY

    assert tuple(spec.api_name for spec in WRITE_API_REGISTRY) == tuple(EXPECTED_WRITE_SURFACE)
    assert {
        spec.api_name: (
            spec.actor_types,
            spec.target_record_types,
            spec.emitted_event_types,
        )
        for spec in WRITE_API_REGISTRY
    } == EXPECTED_WRITE_SURFACE
    assert all(spec.mutation_command_parameter == "mutation_command" for spec in WRITE_API_REGISTRY)


def test_write_surface_only_uses_authoritative_types_and_frozen_events() -> None:
    from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_REGISTRY

    frozen_events = set(get_args(LedgerEvent.model_fields["event_type"].annotation))
    for spec in WRITE_API_REGISTRY:
        assert spec.target_record_types
        assert set(spec.target_record_types) <= set(AUTHORITATIVE_MODELS)
        assert spec.emitted_event_types
        assert set(spec.emitted_event_types) <= frozen_events
        assert len(spec.emitted_event_types) == len(set(spec.emitted_event_types))

    invalid_draft_events = {
        "genesis_event",
        "relationship_vault_created",
        "memory_request_recorded",
        "governor_decision_recorded",
        "vault_retrieval_completed",
        "expression_decided",
    }
    assert not invalid_draft_events & {
        event_type
        for spec in WRITE_API_REGISTRY
        for event_type in spec.emitted_event_types
    }


def test_llm_is_confined_to_proposal_submission() -> None:
    from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_REGISTRY

    llm_specs = tuple(spec for spec in WRITE_API_REGISTRY if "llm" in spec.actor_types)
    assert tuple(spec.api_name for spec in llm_specs) == ("submit_proposal",)
    assert set(llm_specs[0].target_record_types) == {"Proposal", "LedgerEvent"}
    assert not set(llm_specs[0].target_record_types) & {
        "Identity",
        "Lineage",
        "Branch",
        "AutobiographicalMemory",
        "GovernorDecision",
        "VaultReadCapability",
        "MaintenanceCapability",
        "TerminationExecutionGrant",
        "BreakGlassGrant",
    }


def test_write_registry_and_specs_are_immutable() -> None:
    from amadeus_core.contracts.write_api_registry_v0_1 import (
        WRITE_API_BY_NAME,
        WRITE_API_REGISTRY,
    )

    with pytest.raises(TypeError):
        WRITE_API_BY_NAME["injected"] = WRITE_API_REGISTRY[0]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        WRITE_API_REGISTRY[0].api_name = "injected"  # type: ignore[misc]
