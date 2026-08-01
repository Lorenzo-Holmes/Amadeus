import pytest

from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.type_registry_build_spec import load_schema_manifest
from amadeus_core.ids import AUTHORITATIVE_PREFIXES


def test_registry_is_exactly_the_manifest_closed_set() -> None:
    manifest = load_schema_manifest()

    assert tuple(TYPE_REGISTRY) == tuple(entry.class_name for entry in manifest.entries)
    assert len(TYPE_REGISTRY) == 17


def test_registry_freezes_primary_key_prefix_and_bindings() -> None:
    assert {
        spec.schema_root: spec.id_prefix
        for spec in TYPE_REGISTRY.values()
    } == dict(AUTHORITATIVE_PREFIXES)

    for spec in TYPE_REGISTRY.values():
        field_names = {field.name for field in spec.fields}
        assert spec.primary_key in field_names
        assert spec.identity_binding in field_names
        assert spec.lineage_binding in field_names
        assert spec.branch_binding in field_names


def test_registry_models_match_manifest_field_order_and_are_strict() -> None:
    from amadeus_core.contracts import registry

    manifest = load_schema_manifest()
    authoritative_models = registry.AUTHORITATIVE_MODELS

    assert tuple(authoritative_models) == tuple(TYPE_REGISTRY)
    for entry in manifest.entries:
        model = authoritative_models[entry.class_name]
        assert tuple(model.model_fields) == tuple(field.name for field in entry.fields)
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["frozen"] is True
        assert model.model_config["strict"] is True


def test_registry_mappings_are_immutable() -> None:
    from amadeus_core.contracts import registry

    authoritative_models = registry.AUTHORITATIVE_MODELS
    with pytest.raises(TypeError):
        TYPE_REGISTRY["Injected"] = TYPE_REGISTRY["Identity"]  # type: ignore[index]
    with pytest.raises(TypeError):
        authoritative_models["Injected"] = authoritative_models["Identity"]
