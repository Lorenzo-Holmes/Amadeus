import inspect

from amadeus_core.contracts import commands, common, errors, validation
from amadeus_core.contracts.registry import AUTHORITATIVE_MODELS
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_REGISTRY


FORBIDDEN_KEY_MATERIAL_NAMES = {
    "raw_key",
    "private_key_bytes",
    "default_shared_key",
}


def test_authoritative_and_command_schemas_do_not_expose_raw_key_material() -> None:
    models = (
        *AUTHORITATIVE_MODELS.values(),
        common.RecordHeader,
        common.Actor,
        common.AuditContext,
        commands.ExpectedVersion,
        commands.MutationCommandEnvelope,
        commands.CommandResult,
        errors.CoreError,
    )
    exposed = {
        field_name
        for model in models
        for field_name in model.model_fields
        if field_name in FORBIDDEN_KEY_MATERIAL_NAMES
    }

    assert exposed == set()


def test_public_contract_functions_and_write_specs_do_not_accept_raw_keys() -> None:
    functions = (
        commands.compute_command_hash,
        commands.idempotency_address,
        commands.normalize_command_for_hash,
        commands.normalize_expected_versions,
        validation.compute_record_content_hash,
        validation.validate_authoritative_record,
    )
    parameter_names = {
        parameter_name
        for function in functions
        for parameter_name in inspect.signature(function).parameters
    }
    registry_parameters = {
        spec.mutation_command_parameter for spec in WRITE_API_REGISTRY
    }

    assert not parameter_names & FORBIDDEN_KEY_MATERIAL_NAMES
    assert not registry_parameters & FORBIDDEN_KEY_MATERIAL_NAMES
    assert registry_parameters == {"mutation_command"}
