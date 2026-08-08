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
            "proposal_reopened",
            "proposal_expired",
        ),
    ),
    "issue_vault_read_capability": (
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_issued", "vault_read_capability_denied"),
    ),
    "revoke_vault_read_capability": (
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_revoked", "vault_read_capability_denied"),
    ),
    "expire_vault_read_capability": (
        ("governor", "system"),
        ("VaultReadCapability", "LedgerEvent"),
        ("vault_read_capability_expired", "vault_read_capability_denied"),
    ),
    "record_vault_read_decision": (
        ("governor", "system"),
        ("LedgerEvent",),
        ("vault_read_capability_used", "vault_read_capability_denied"),
    ),
    "rebuild_materialized_views": (
        ("maintainer",),
        ("LedgerEvent",),
        (
            "materialized_view_rebuilt",
            "derived_view_validation_failed",
            "derived_view_fallback",
        ),
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

def test_generic_registered_event_append_is_not_a_public_write_api() -> None:
    import amadeus_core.storage as storage
    from amadeus_core.storage import ledger

    assert not hasattr(storage, "append_registered_event")
    assert not hasattr(ledger, "_append_registered_event")
    assert "append_registered_event" not in ledger.__all__
    assert "_append_registered_event" not in ledger.__all__


def test_rebuild_materialized_views_is_registered_on_closed_write_surface() -> None:
    from amadeus_core.contracts.write_api_registry_v0_1 import (
        WRITE_API_BY_NAME,
        WRITE_API_REGISTRY,
    )

    expected = (
        "maintainer",
    ), ("LedgerEvent",), (
        "materialized_view_rebuilt",
        "derived_view_validation_failed",
        "derived_view_fallback",
    )
    assert tuple(spec.api_name for spec in WRITE_API_REGISTRY) == tuple(
        EXPECTED_WRITE_SURFACE
    )
    spec = WRITE_API_BY_NAME["rebuild_materialized_views"]
    assert spec.mutation_command_parameter == "mutation_command"
    assert (spec.actor_types, spec.target_record_types, spec.emitted_event_types) == expected
    assert not set(spec.target_record_types) & {
        "MaterializedViewManifest",
        "RebuiltMaterializedViews",
        "DerivedViewFallback",
    }


def test_repository_materialized_view_authority_gate_precedes_generic_validation_and_mutation(tmp_path) -> None:
    from datetime import UTC, datetime

    from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
    from amadeus_core.contracts.views import MaterializedViewManifest
    from amadeus_core.storage import AuthorityRepository, open_database

    manifest_body = MaterializedViewManifest(
        view_id="viw-a",
        view_type="summary",
        identity_id="idn-a",
        branch_id="brn-a",
        vault_id="vlt-a",
        source_watermark_seq=0,
        source_root_hash="a" * 64,
        builder_version="view-builder-v1",
        built_at=datetime(2026, 8, 6, tzinfo=UTC),
        view_hash="b" * 64,
    ).model_dump(mode="python")
    connection = open_database(tmp_path / "authority.db")
    repository = AuthorityRepository(connection)
    try:
        for schema_root, body in (
            ("materialized_view_manifest", {}),
            ("identity", manifest_body),
        ):
            before = connection.total_changes
            with pytest.raises(CoreContractViolation) as exc:
                repository.save_authoritative(schema_root, body)
            assert exc.value.code is CoreErrorCode.MATERIALIZED_VIEW_NOT_AUTHORITY
            assert str(exc.value) == "CORE-E-MATERIALIZED-VIEW-NOT-AUTHORITY"
            assert connection.total_changes == before

        malformed_lookalike = dict(manifest_body)
        malformed_lookalike.pop("view_hash")
        before = connection.total_changes
        with pytest.raises(CoreContractViolation) as exc:
            repository.save_authoritative("identity", malformed_lookalike)
        assert exc.value.code is CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH
        assert str(exc.value) == "CORE-E-RECORD-TYPE-SCHEMA-MISMATCH"
        assert connection.total_changes == before
    finally:
        connection.close()
