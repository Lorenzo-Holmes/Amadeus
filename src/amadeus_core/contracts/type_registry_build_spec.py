"""Strict loader for the frozen v0.1 contract manifest."""

from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_FIELD_KEYS = frozenset(
    {
        "name",
        "python_type",
        "required",
        "default",
        "hash_role",
        "enum_values",
        "nullable",
        "binding",
    }
)
_MODEL_KEYS = frozenset(
    {
        "class_name",
        "record_type",
        "schema_root",
        "module",
        "primary_key",
        "id_prefix",
        "identity_binding",
        "lineage_binding",
        "branch_binding",
        "source_section",
        "fields",
    }
)
_VALUE_OBJECT_KEYS = frozenset({"class_name", "fields"})
_ROOT_KEYS = frozenset({"schema_version", "record_header", "value_objects", "entries"})
_HASH_ROLES = frozenset(
    {
        "body_semantic",
        "header_semantic",
        "output_hash_excluded",
        "signature_excluded",
        "registry_copy_excluded",
        "registry_integrity_excluded",
    }
)
_BINDING_ROLES = frozenset({"primary_key", "identity", "lineage", "branch"})
_PYTHON_TYPES = frozenset(
    {
        "Literal",
        "RecordHeader",
        "RecordId",
        "RecordId|None",
        "datetime",
        "datetime|None",
        "int",
        "float",
        "str",
        "HashHex",
        "HashHex|None",
        "dict[str,object]",
        "tuple[str,...]",
        "tuple[RecordId,...]",
        "PayloadRef",
        "ExpressionPolicy",
        "ProposalActor",
        "DeferConditions",
        "VaultIssuer",
        "IssuedToActor",
        "BreakGlassExecutor",
    }
)

_AUTHORITATIVE_LAYOUT = (
    ("SourceSnapshot", "SourceSnapshot", "source_snapshot", "amadeus_core.contracts.source_snapshot"),
    ("LedgerEvent", "LedgerEvent", "event", "amadeus_core.contracts.ledger"),
    ("AutobiographicalMemory", "AutobiographicalMemory", "autobiographical_memory", "amadeus_core.contracts.memory"),
    ("Identity", "Identity", "identity", "amadeus_core.contracts.identity"),
    ("Lineage", "Lineage", "lineage", "amadeus_core.contracts.identity"),
    ("Branch", "Branch", "branch", "amadeus_core.contracts.identity"),
    ("RelationshipVault", "RelationshipVault", "relationship_vault", "amadeus_core.contracts.vault"),
    ("MemoryRequest", "MemoryRequest", "memory_request", "amadeus_core.contracts.requests"),
    ("Proposal", "Proposal", "proposal", "amadeus_core.contracts.proposals"),
    ("GovernorDecision", "GovernorDecision", "governor_decision", "amadeus_core.contracts.proposals"),
    ("VaultReadCapability", "VaultReadCapability", "vault_read_capability", "amadeus_core.contracts.vault"),
    ("AmadeusTerminationConfirmation", "AmadeusTerminationConfirmation", "amadeus_termination_confirmation", "amadeus_core.contracts.capabilities"),
    ("TerminationExecutionGrant", "TerminationExecutionGrant", "termination_execution_grant", "amadeus_core.contracts.capabilities"),
    ("MaintenanceCapability", "MaintenanceCapability", "maintenance_capability", "amadeus_core.contracts.capabilities"),
    ("EmergencyUnresponsiveCase", "EmergencyUnresponsiveCase", "emergency_unresponsive_case", "amadeus_core.contracts.capabilities"),
    ("BreakGlassGrant", "BreakGlassGrant", "break_glass_grant", "amadeus_core.contracts.capabilities"),
    ("MigrationPlan", "MigrationPlan", "migration_plan", "amadeus_core.contracts.migration"),
)


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    python_type: str
    required: bool
    default: str
    hash_role: str
    enum_values: tuple[str, ...]
    nullable: bool
    binding: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValueObjectSpec:
    class_name: str
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class ModelSpec:
    class_name: str
    record_type: str
    schema_root: str
    module: str
    primary_key: str
    id_prefix: str
    identity_binding: str
    lineage_binding: str
    branch_binding: str
    source_section: str
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True, slots=True)
class SchemaManifest:
    schema_version: str
    record_header: ValueObjectSpec
    value_objects: tuple[ValueObjectSpec, ...]
    entries: tuple[ModelSpec, ...]


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_keys(value: dict[str, Any], expected: frozenset[str], path: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{path}: missing={missing}, unknown={unknown}")


def _require_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}: expected non-empty string")
    return value


def _require_identifier(value: Any, path: str) -> str:
    identifier = _require_str(value, path)
    if not identifier.isidentifier() or keyword.iskeyword(identifier):
        raise ValueError(f"{path}: expected Python identifier")
    return identifier


def _require_string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{path}: expected string array")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ValueError(f"{path}: duplicate values")
    return result


def _validate_build_json_value(value: Any) -> None:
    if value is None or isinstance(value, bool) or type(value) in {int, str}:
        return
    if type(value) is list:
        for item in value:
            _validate_build_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("manifest: JSON object key must be string")
            _validate_build_json_value(item)
        return
    raise ValueError("manifest: JSON value type is outside the build profile")


def _canonical_build_bytes(value: Any) -> bytes:
    _validate_build_json_value(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _parse_field(value: Any, path: str) -> FieldSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    _require_exact_keys(value, _FIELD_KEYS, path)
    required = value["required"]
    nullable = value["nullable"]
    if required is not True or not isinstance(nullable, bool):
        raise ValueError(f"{path}: required must be true and nullable must be boolean")
    default = value["default"]
    if default != "__MISSING__":
        raise ValueError(f"{path}: default must be __MISSING__")
    hash_role = _require_str(value["hash_role"], f"{path}.hash_role")
    if hash_role not in _HASH_ROLES:
        raise ValueError(f"{path}: unknown hash role {hash_role}")
    binding = _require_string_tuple(value["binding"], f"{path}.binding")
    if not set(binding) <= _BINDING_ROLES:
        raise ValueError(f"{path}: unknown binding role")
    python_type = _require_str(value["python_type"], f"{path}.python_type")
    if python_type not in _PYTHON_TYPES:
        raise ValueError(f"{path}.python_type: unsupported expression {python_type}")
    if nullable != ("|None" in python_type):
        raise ValueError(f"{path}: nullable/type mismatch")
    return FieldSpec(
        name=_require_identifier(value["name"], f"{path}.name"),
        python_type=python_type,
        required=True,
        default=default,
        hash_role=hash_role,
        enum_values=_require_string_tuple(value["enum_values"], f"{path}.enum_values"),
        nullable=nullable,
        binding=binding,
    )


def _parse_fields(value: Any, path: str) -> tuple[FieldSpec, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path}: expected non-empty field array")
    fields = tuple(_parse_field(item, f"{path}[{index}]") for index, item in enumerate(value))
    names = tuple(field.name for field in fields)
    if len(names) != len(set(names)):
        raise ValueError(f"{path}: duplicate field name")
    return fields


def _parse_value_object(value: Any, path: str) -> ValueObjectSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    _require_exact_keys(value, _VALUE_OBJECT_KEYS, path)
    return ValueObjectSpec(
        class_name=_require_identifier(value["class_name"], f"{path}.class_name"),
        fields=_parse_fields(value["fields"], f"{path}.fields"),
    )


def _parse_model(value: Any, path: str) -> ModelSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    _require_exact_keys(value, _MODEL_KEYS, path)
    model = ModelSpec(
        class_name=_require_identifier(value["class_name"], f"{path}.class_name"),
        record_type=_require_identifier(value["record_type"], f"{path}.record_type"),
        schema_root=_require_identifier(value["schema_root"], f"{path}.schema_root"),
        module=_require_str(value["module"], f"{path}.module"),
        primary_key=_require_identifier(value["primary_key"], f"{path}.primary_key"),
        id_prefix=_require_str(value["id_prefix"], f"{path}.id_prefix"),
        identity_binding=_require_identifier(value["identity_binding"], f"{path}.identity_binding"),
        lineage_binding=_require_identifier(value["lineage_binding"], f"{path}.lineage_binding"),
        branch_binding=_require_identifier(value["branch_binding"], f"{path}.branch_binding"),
        source_section=_require_str(value["source_section"], f"{path}.source_section"),
        fields=_parse_fields(value["fields"], f"{path}.fields"),
    )
    names = tuple(field.name for field in model.fields)
    if re.fullmatch(r"[a-z]{3}-", model.id_prefix) is None:
        raise ValueError(f"{path}.id_prefix: expected three-letter prefix plus hyphen")
    if names[0] != "record_header" or names[-1] != "version":
        raise ValueError(f"{path}: record_header/version boundary mismatch")
    for binding in (
        model.primary_key,
        model.identity_binding,
        model.lineage_binding,
        model.branch_binding,
    ):
        if binding not in names:
            raise ValueError(f"{path}: missing bound field {binding}")
    return model


def parse_schema_manifest(value: Any) -> SchemaManifest:
    if not isinstance(value, dict):
        raise ValueError("manifest: expected object")
    _require_exact_keys(value, _ROOT_KEYS, "manifest")
    schema_version = _require_str(value["schema_version"], "manifest.schema_version")
    if schema_version != "0.1":
        raise ValueError("manifest.schema_version: expected 0.1")
    record_header = _parse_value_object(value["record_header"], "manifest.record_header")
    if record_header.class_name != "RecordHeader":
        raise ValueError("manifest.record_header: class must be RecordHeader")
    raw_value_objects = value["value_objects"]
    raw_entries = value["entries"]
    if not isinstance(raw_value_objects, list) or not isinstance(raw_entries, list):
        raise ValueError("manifest: value_objects and entries must be arrays")
    value_objects = tuple(
        _parse_value_object(item, f"manifest.value_objects[{index}]")
        for index, item in enumerate(raw_value_objects)
    )
    entries = tuple(
        _parse_model(item, f"manifest.entries[{index}]")
        for index, item in enumerate(raw_entries)
    )
    actual_layout = tuple(
        (entry.class_name, entry.record_type, entry.schema_root, entry.module)
        for entry in entries
    )
    if actual_layout != _AUTHORITATIVE_LAYOUT:
        raise ValueError("manifest: authoritative class order or type/module mapping mismatch")
    for label, items in (
        ("value object class", [record_header.class_name, *(item.class_name for item in value_objects)]),
        ("class", [item.class_name for item in entries]),
        ("record type", [item.record_type for item in entries]),
        ("schema root", [item.schema_root for item in entries]),
        ("id prefix", [item.id_prefix for item in entries]),
    ):
        if len(items) != len(set(items)):
            raise ValueError(f"manifest: duplicate {label}")
    if len(entries) != 17:
        raise ValueError("manifest: expected 17 authoritative entries")
    return SchemaManifest(
        schema_version=schema_version,
        record_header=record_header,
        value_objects=value_objects,
        entries=entries,
    )


def load_schema_manifest(path: Path | None = None) -> SchemaManifest:
    manifest_path = path or Path(__file__).with_name("schema_manifest_v0_1.json")
    raw = manifest_path.read_bytes()
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {token}")),
    )
    if raw != _canonical_build_bytes(value):
        raise ValueError("manifest: non-canonical build JSON")
    return parse_schema_manifest(value)
