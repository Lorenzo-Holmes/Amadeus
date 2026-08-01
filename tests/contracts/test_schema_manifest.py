from pathlib import Path
from importlib import import_module
import json

import pytest

from tools.stage0c_fixtures.io import canonical_bytes

EXPECTED_CLASS_ORDER = (
    "SourceSnapshot",
    "LedgerEvent",
    "AutobiographicalMemory",
    "Identity",
    "Lineage",
    "Branch",
    "RelationshipVault",
    "MemoryRequest",
    "Proposal",
    "GovernorDecision",
    "VaultReadCapability",
    "AmadeusTerminationConfirmation",
    "TerminationExecutionGrant",
    "MaintenanceCapability",
    "EmergencyUnresponsiveCase",
    "BreakGlassGrant",
    "MigrationPlan",
)

EXPECTED_FIELDS = {
    "SourceSnapshot": "record_header snapshot_id identity_id lineage_id branch_id source_type source_ref cutoff_at imported_at manifest_hash payload_root_hash parent_snapshot_id deployment_policy_ref status version".split(),
    "LedgerEvent": "record_header event_id ledger_seq identity_id lineage_id branch_id instance_id vault_id event_type occurred_at ingested_at actor_type actor_id mutation_command_id mutation_command_hash payload_ref causation_id correlation_id previous_event_hash event_hash version".split(),
    "AutobiographicalMemory": "record_header memory_id identity_id lineage_id branch_id governing_vault_id semantic_kind state importance consolidation_state expression_policy evidence_event_refs supersedes_memory_ids contested_by_event_ids governor_decision_id semantic_version created_at updated_at version".split(),
    "Identity": "record_header identity_id canonical_name lineage_id active_branch_id lifecycle_state created_from_snapshot_id deployment_policy_ref version".split(),
    "Lineage": "record_header lineage_id root_snapshot_id root_identity_id root_branch_id created_at lineage_hash version".split(),
    "Branch": "record_header branch_id lineage_id identity_id parent_branch_ids fork_reason fork_event_id base_ledger_seq status status_reason_event_id activated_at deactivated_at terminated_at merge_policy version".split(),
    "RelationshipVault": "record_header vault_id identity_id lineage_id branch_id relationship_principal_id status visibility_policy_ref created_at version".split(),
    "MemoryRequest": "record_header request_id request_type identity_id lineage_id branch_id vault_id requester_id submitted_at target_refs statement requested_scope status resulting_proposal_ids resulting_decision_ids version".split(),
    "Proposal": "record_header proposal_id proposal_type identity_id lineage_id branch_id vault_id proposed_by target_refs evidence_refs proposed_patch created_at expires_at status deferred_at defer_conditions reopened_count version".split(),
    "GovernorDecision": "record_header decision_id proposal_id identity_id lineage_id branch_id vault_id result policy_version input_state_hash reason_codes evidence_refs committed_event_ids output_state_hash decided_at governor_signature version".split(),
    "VaultReadCapability": "record_header capability_id identity_id lineage_id branch_id vault_id principal_id issuer issued_to_actor intended_audience allowed_operations allowed_purposes not_before issued_at expires_at policy_version nonce status attestation version".split(),
    "AmadeusTerminationConfirmation": "record_header confirmation_id identity_id lineage_id branch_id confirmed_by confirmation_event_id scope confirmed_at expires_at withdrawn_at state_hash version".split(),
    "TerminationExecutionGrant": "record_header grant_id termination_proposal_id confirmation_event_id identity_id lineage_id branch_id state_hash executor_role executor_id issued_by issued_at expires_at use_limit used_at status grant_attestation version".split(),
    "MaintenanceCapability": "record_header capability_id maintainer_id identity_id lineage_id branch_id reason_code exact_operation exact_resource_ref not_before expires_at approval_refs evidence_seal_ref use_limit used_at status attestation version".split(),
    "EmergencyUnresponsiveCase": "record_header case_id identity_id lineage_id branch_id declared_at evidence_refs severity minimal_scope preservation_plan_ref post_audit_due_at status version".split(),
    "BreakGlassGrant": "record_header grant_id emergency_case_id executor identity_id lineage_id branch_id exact_resource_ref allowed_operation final_action precondition_state_hash precondition_resource_hash expected_postcondition_state_hash expected_postcondition_resource_hash observed_postcondition_state_hash observed_postcondition_resource_hash evidence_seal_refs approval_refs not_before expires_at post_audit_due_at post_audit_completed_at max_uses remaining_uses status execution_started_at used_at attestation version".split(),
    "MigrationPlan": "record_header migration_id identity_id source_branch_id target_branch_id lineage_id source_schema_version target_schema_version compatibility transformation_manifest_ref pre_root_hash expected_post_root_hash rollback_ref capability_id status version".split(),
}


def _load_schema_manifest():
    from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest

    return load_schema_manifest()


def test_manifest_freezes_all_authoritative_models_in_order() -> None:
    manifest = _load_schema_manifest()

    assert tuple(entry.class_name for entry in manifest.entries) == EXPECTED_CLASS_ORDER
    assert all(entry.fields[0].name == "record_header" for entry in manifest.entries)
    assert all(entry.fields[-1].name == "version" for entry in manifest.entries)


def test_manifest_freezes_exact_field_order() -> None:
    manifest = _load_schema_manifest()

    assert {
        entry.class_name: [field.name for field in entry.fields]
        for entry in manifest.entries
    } == EXPECTED_FIELDS


def test_manifest_field_metadata_is_explicit() -> None:
    manifest = _load_schema_manifest()

    for entry in manifest.entries:
        assert entry.source_section.startswith("Amadeus-Core-v0.1-数据契约与状态机规范.md §")
        for field in entry.fields:
            assert field.python_type
            assert field.required is True
            assert field.default == "__MISSING__"
            assert field.hash_role in {
                "body_semantic",
                "header_semantic",
                "output_hash_excluded",
                "signature_excluded",
                "registry_copy_excluded",
                "registry_integrity_excluded",
            }


def test_manifest_freezes_actor_and_audit_context_value_objects() -> None:
    manifest = _load_schema_manifest()
    value_objects = {
        item.class_name: tuple(field.name for field in item.fields)
        for item in manifest.value_objects
    }

    assert value_objects["Actor"] == ("actor_type", "actor_id")
    assert value_objects["AuditContext"] == (
        "context_id",
        "correlation_id",
        "actor_id",
        "actor_type",
        "capability_id",
        "purpose_code",
        "source_instance_id",
        "source_terminal_ref",
        "started_at",
    )


def test_generated_contract_modules_are_present() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = _load_schema_manifest()

    for entry in manifest.entries:
        module_path = root / "src" / Path(*entry.module.split("."))
        module_file = module_path.with_suffix(".py")
        assert module_file.is_file(), entry.class_name
        assert f"class {entry.class_name}(" in module_file.read_text(encoding="utf-8")


def test_generated_authoritative_models_import() -> None:
    manifest = _load_schema_manifest()

    imported = tuple(
        getattr(import_module(entry.module), entry.class_name)
        for entry in manifest.entries
    )
    assert tuple(model.__name__ for model in imported) == EXPECTED_CLASS_ORDER


def test_contract_generator_check_has_zero_diff() -> None:
    from tools.compile_contract_models import compile_contract_models

    root = Path(__file__).resolve().parents[2]
    report = compile_contract_models(
        root / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json",
        root / "src" / "amadeus_core" / "contracts",
        check=True,
    )
    assert report.models_generated == 17
    assert report.registry_entries == 17
    assert report.changed_paths == ()


def test_manifest_loader_rejects_noncanonical_bytes(tmp_path: Path) -> None:
    from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest

    source = Path(__file__).resolve().parents[2] / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="non-canonical"):
        load_schema_manifest(candidate)


def test_manifest_loader_rejects_untrusted_python_type(tmp_path: Path) -> None:
    from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest

    source = Path(__file__).resolve().parents[2] / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["entries"][0]["fields"][1]["python_type"] = "__import__('os').system('exit 1')"
    candidate = tmp_path / "manifest.json"
    candidate.write_bytes(canonical_bytes(value))

    with pytest.raises(ValueError, match="python_type"):
        load_schema_manifest(candidate)


def test_manifest_loader_rejects_reordered_authoritative_classes(tmp_path: Path) -> None:
    from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest

    source = Path(__file__).resolve().parents[2] / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["entries"] = [*value["entries"][1:], value["entries"][0]]
    candidate = tmp_path / "manifest.json"
    candidate.write_bytes(canonical_bytes(value))

    with pytest.raises(ValueError, match="authoritative class order"):
        load_schema_manifest(candidate)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["entries"][0].__setitem__(
                "module", "C:\\outside\\contract_escape"
            ),
            "module",
        ),
        (
            lambda value: value["entries"][0].__setitem__(
                "class_name", "SourceSnapshot; injected"
            ),
            "class_name",
        ),
        (
            lambda value: value["entries"][0]["fields"][1].__setitem__(
                "name", "snapshot_id; injected"
            ),
            "field",
        ),
    ],
    ids=("absolute-module", "class-identifier", "field-identifier"),
)
def test_manifest_loader_rejects_code_and_path_injection(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest

    source = Path(__file__).resolve().parents[2] / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    mutation(value)
    candidate = tmp_path / "manifest.json"
    candidate.write_bytes(canonical_bytes(value))

    with pytest.raises(ValueError, match=message):
        load_schema_manifest(candidate)
