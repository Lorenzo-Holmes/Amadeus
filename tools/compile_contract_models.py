"""Generate frozen Pydantic contracts and a static type registry."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from amadeus_core.contracts.type_registry_build_spec import (
    FieldSpec,
    ModelSpec,
    SchemaManifest,
    parse_schema_manifest,
)
from tools.stage0c_fixtures.io import load_strict_json_bytes
from tools.atomic_io import atomic_write_bytes


@dataclass(frozen=True, slots=True)
class CompileReport:
    models_generated: int
    registry_entries: int
    changed_paths: tuple[str, ...]


_DIRECT_TYPES = {
    "RecordHeader": "RecordHeader",
    "RecordId": "RecordId",
    "RecordId|None": "RecordId | None",
    "datetime": "UtcDatetime",
    "datetime|None": "UtcDatetime | None",
    "int": "int",
    "float": "float",
    "str": "str",
    "HashHex": "HashHex",
    "HashHex|None": "HashHex | None",
    "dict[str,object]": "JsonObject",
    "tuple[str,...]": "tuple[str, ...]",
    "tuple[RecordId,...]": "tuple[RecordId, ...]",
    "PayloadRef": "PayloadRef",
    "ExpressionPolicy": "ExpressionPolicy",
    "ProposalActor": "ProposalActor",
    "DeferConditions": "DeferConditions",
    "VaultIssuer": "VaultIssuer",
    "IssuedToActor": "IssuedToActor",
    "BreakGlassExecutor": "BreakGlassExecutor",
}


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


def _render_type(field: FieldSpec) -> str:
    if field.name in {"use_limit", "max_uses"} and field.python_type == "int":
        return "SingleUseLimit"
    if field.name == "remaining_uses" and field.python_type == "int":
        return "RemainingUses"
    if field.name == "version" and field.python_type == "int":
        return "PositiveVersion"
    if field.python_type == "Literal":
        if not field.enum_values:
            raise ValueError(f"{field.name}: Literal requires enum_values")
        return f"Literal[{_quoted_values(field.enum_values)}]"
    if field.python_type == "tuple[str,...]" and field.enum_values:
        return f"tuple[Literal[{_quoted_values(field.enum_values)}], ...]"
    try:
        return _DIRECT_TYPES[field.python_type]
    except KeyError as error:
        raise ValueError(f"{field.name}: unknown python_type {field.python_type}") from error


def _render_class(class_name: str, fields: Iterable[FieldSpec]) -> list[str]:
    lines = [f"class {class_name}(FrozenModel):"]
    for field in fields:
        lines.append(f"    {field.name}: {_render_type(field)}")
    lines.append("")
    return lines


def _render_common(manifest: SchemaManifest) -> str:
    lines = [
        '"""Generated common value objects for Core v0.1."""',
        "",
        "from collections.abc import Mapping",
        "from datetime import datetime, timedelta",
        "from decimal import Decimal",
        "import math",
        "from types import MappingProxyType",
        "from typing import Annotated, Literal, Self",
        "",
        "from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints, model_validator",
        "",
        "",
        "_FORBIDDEN_KEY_MATERIAL_NAMES = frozenset({",
        '    "raw_key",',
        '    "private_key_bytes",',
        '    "default_shared_key",',
        "})",
        "",
        "",
        "class FrozenMapping(Mapping[str, object]):",
        '    __slots__ = ("_values",)',
        "",
        "    def __init__(self, values: Mapping[str, object]) -> None:",
        '        object.__setattr__(self, "_values", MappingProxyType(dict(values)))',
        "",
        "    def __getitem__(self, key: str) -> object:",
        "        return self._values[key]",
        "",
        "    def __iter__(self):",
        "        return iter(self._values)",
        "",
        "    def __len__(self) -> int:",
        "        return len(self._values)",
        "",
        "    def __setattr__(self, name: str, value: object) -> None:",
        '        raise TypeError("frozen contract mapping is immutable")',
        "",
        '    def __deepcopy__(self, memo: dict[int, object]) -> "FrozenMapping":',
        "        return self",
        "",
        "    def __repr__(self) -> str:",
        "        return repr(dict(self._values))",
        "",
        "",
        "def _freeze_contract_value(value: object) -> object:",
        "    if isinstance(value, FrozenModel):",
        "        return value",
        "    if isinstance(value, (bytes, bytearray, memoryview)):",
        '        raise ValueError("binary values are outside the contract JSON domain")',
        "    if value is None or isinstance(value, (bool, int)):",
        "        return value",
        "    if isinstance(value, str):",
        "        try:",
        '            value.encode("utf-8")',
        "        except UnicodeEncodeError as error:",
        '            raise ValueError("contract strings must be valid UTF-8") from error',
        "        return value",
        "    if isinstance(value, float):",
        "        if not math.isfinite(value):",
        '            raise ValueError("contract numbers must be finite")',
        "        return value",
        "    if isinstance(value, Decimal):",
        "        if not value.is_finite():",
        '            raise ValueError("contract numbers must be finite")',
        "        return value",
        "    if isinstance(value, datetime):",
        "        if value.utcoffset() != timedelta(0):",
        '            raise ValueError("contract datetime must use UTC")',
        "        return value",
        "    if isinstance(value, Mapping):",
        "        frozen: dict[str, object] = {}",
        "        for key, item in value.items():",
        "            if not isinstance(key, str):",
        '                raise ValueError("contract JSON object keys must be strings")',
        "            try:",
        '                key.encode("utf-8")',
        "            except UnicodeEncodeError as error:",
        '                raise ValueError("contract keys must be valid UTF-8") from error',
        "            if key in _FORBIDDEN_KEY_MATERIAL_NAMES:",
        '                raise ValueError(f"raw key material field is forbidden: {key}")',
        "            frozen[key] = _freeze_contract_value(item)",
        "        return FrozenMapping(frozen)",
        "    if isinstance(value, (list, tuple)):",
        "        return tuple(_freeze_contract_value(item) for item in value)",
        '    raise ValueError(f"value is outside the contract JSON domain: {type(value).__qualname__}")',
        "",
        "",
        "def _thaw_contract_value(value: object) -> object:",
        "    if isinstance(value, Mapping):",
        "        return {key: _thaw_contract_value(item) for key, item in value.items()}",
        "    if isinstance(value, tuple):",
        "        return tuple(_thaw_contract_value(item) for item in value)",
        "    return value",
        "",
        "",
        "def _serialize_json_object(value: Mapping[str, object]) -> dict[str, object]:",
        "    return {key: _thaw_contract_value(item) for key, item in value.items()}",
        "",
        "",
        "def _require_utc_datetime(value: datetime) -> datetime:",
        "    if value.utcoffset() != timedelta(0):",
        '        raise ValueError("datetime must use UTC")',
        "    return value",
        "",
        "",
        "UtcDatetime = Annotated[datetime, AfterValidator(_require_utc_datetime)]",
        'RecordId = Annotated[str, StringConstraints(min_length=5, pattern=r"^[a-z]{3}-[0-9a-f]+(?:-[0-9a-f]+)*$")]',
        'HashHex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]',
        "PositiveVersion = Annotated[int, Field(strict=True, ge=1)]",
        "SingleUseLimit = Annotated[int, Field(strict=True, ge=1, le=1)]",
        "RemainingUses = Annotated[int, Field(strict=True, ge=0, le=1)]",
        "JsonObject = Annotated[",
        "    Mapping[str, object],",
        "    PlainSerializer(_serialize_json_object, return_type=dict[str, object]),",
        "]",
        "PayloadRef = str",
        "",
        "",
        "class FrozenModel(BaseModel):",
        '    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)',
        "",
        '    @model_validator(mode="after")',
        "    def _freeze_nested_contract_values(self) -> Self:",
        "        for field_name in type(self).model_fields:",
        "            value = getattr(self, field_name)",
        "            frozen = _freeze_contract_value(value)",
        "            if frozen is not value:",
        "                object.__setattr__(self, field_name, frozen)",
        "        return self",
        "",
        "    def model_copy(",
        "        self,",
        "        *,",
        "        update: Mapping[str, object] | None = None,",
        "        deep: bool = False,",
        "    ) -> Self:",
        "        del deep",
        '        data = self.model_dump(mode="python")',
        "        if update:",
        "            data.update(update)",
        "        return type(self).model_validate(data)",
        "",
        "    def copy(",
        "        self,",
        "        *,",
        "        include: object = None,",
        "        exclude: object = None,",
        "        update: Mapping[str, object] | None = None,",
        "        deep: bool = False,",
        "    ) -> Self:",
        "        if include is not None or exclude is not None:",
        '            raise TypeError("partial copies are outside the frozen contract")',
        "        return self.model_copy(update=update, deep=deep)",
        "",
        "",
    ]
    lines.extend(_render_class(manifest.record_header.class_name, manifest.record_header.fields))
    for value_object in manifest.value_objects:
        lines.extend(_render_class(value_object.class_name, value_object.fields))
    exports = [
        "FrozenModel",
        "RecordId",
        "HashHex",
        "PositiveVersion",
        "SingleUseLimit",
        "RemainingUses",
        "JsonObject",
        "PayloadRef",
        "UtcDatetime",
        manifest.record_header.class_name,
        *(item.class_name for item in manifest.value_objects),
    ]
    lines.extend(
        [
            "__all__ = [",
            *(f"    {name!r}," for name in exports),
            "]",
            "",
        ]
    )
    return "\n".join(lines)


def _render_model_module(entries: list[ModelSpec]) -> str:
    lines = [
        '"""Generated authoritative Core v0.1 models."""',
        "",
        "from typing import Literal",
        "",
        "from .common import (",
        "    BreakGlassExecutor,",
        "    DeferConditions,",
        "    ExpressionPolicy,",
        "    FrozenModel,",
        "    HashHex,",
        "    IssuedToActor,",
        "    JsonObject,",
        "    PayloadRef,",
        "    PositiveVersion,",
        "    RemainingUses,",
        "    ProposalActor,",
        "    RecordHeader,",
        "    RecordId,",
        "    SingleUseLimit,",
        "    UtcDatetime,",
        "    VaultIssuer,",
        ")",
        "",
        "",
    ]
    for entry in entries:
        lines.extend(_render_class(entry.class_name, entry.fields))
    lines.extend(
        [
            "__all__ = [",
            *(f"    {entry.class_name!r}," for entry in entries),
            "]",
            "",
        ]
    )
    return "\n".join(lines)


def _render_field_spec(field: FieldSpec, indent: str) -> list[str]:
    return [
        f"{indent}FieldSpec(",
        f"{indent}    name={field.name!r},",
        f"{indent}    python_type={field.python_type!r},",
        f"{indent}    required={field.required!r},",
        f"{indent}    default={field.default!r},",
        f"{indent}    hash_role={field.hash_role!r},",
        f"{indent}    enum_values={field.enum_values!r},",
        f"{indent}    nullable={field.nullable!r},",
        f"{indent}    binding={field.binding!r},",
        f"{indent}),",
    ]


def _render_model_spec(entry: ModelSpec) -> list[str]:
    lines = [
        f"    {entry.class_name!r}: ModelSpec(",
        f"        class_name={entry.class_name!r},",
        f"        record_type={entry.record_type!r},",
        f"        schema_root={entry.schema_root!r},",
        f"        module={entry.module!r},",
        f"        primary_key={entry.primary_key!r},",
        f"        id_prefix={entry.id_prefix!r},",
        f"        identity_binding={entry.identity_binding!r},",
        f"        lineage_binding={entry.lineage_binding!r},",
        f"        branch_binding={entry.branch_binding!r},",
        f"        source_section={entry.source_section!r},",
        "        fields=(",
    ]
    for field in entry.fields:
        lines.extend(_render_field_spec(field, "            "))
    lines.extend(["        ),", "    ),"])
    return lines


def _render_registry(manifest: SchemaManifest) -> str:
    lines = [
        '"""Generated static authoritative type registry."""',
        "",
        "from types import MappingProxyType",
        "",
    ]
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for entry in manifest.entries:
        grouped.setdefault(entry.module.rsplit(".", 1)[-1], []).append(entry.class_name)
    for module_name, class_names in grouped.items():
        lines.append(f"from .{module_name} import {', '.join(class_names)}")
    lines.extend(
        [
            "from .hash_scope import HASH_SCOPE_REGISTRY, HASH_SCOPE_REGISTRY_DIGEST",
            "from .type_registry_build_spec import FieldSpec, ModelSpec",
            "",
            "",
            "TYPE_REGISTRY = MappingProxyType({",
        ]
    )
    for entry in manifest.entries:
        lines.extend(_render_model_spec(entry))
    lines.extend(["})", "", "AUTHORITATIVE_MODELS = MappingProxyType({"])
    for entry in manifest.entries:
        lines.append(f"    {entry.class_name!r}: {entry.class_name},")
    lines.extend(
        [
            "})",
            "",
            '__all__ = [',
            '    "AUTHORITATIVE_MODELS",',
            '    "HASH_SCOPE_REGISTRY",',
            '    "HASH_SCOPE_REGISTRY_DIGEST",',
            '    "TYPE_REGISTRY",',
            ']',
            "",
        ]
    )
    return "\n".join(lines)


def _render_outputs(manifest: SchemaManifest) -> OrderedDict[str, str]:
    grouped: OrderedDict[str, list[ModelSpec]] = OrderedDict()
    for entry in manifest.entries:
        module_name = entry.module.rsplit(".", 1)[-1]
        grouped.setdefault(module_name, []).append(entry)
    outputs: OrderedDict[str, str] = OrderedDict()
    outputs["common.py"] = _render_common(manifest)
    for module_name, entries in grouped.items():
        outputs[f"{module_name}.py"] = _render_model_module(entries)
    outputs["registry.py"] = _render_registry(manifest)
    return outputs


def _load_manifest(path: Path) -> SchemaManifest:
    value = load_strict_json_bytes(path.read_bytes(), source=path.as_posix())
    return parse_schema_manifest(value)


def compile_contract_models(
    manifest_path: Path,
    package_root: Path,
    *,
    check: bool,
) -> CompileReport:
    manifest = _load_manifest(manifest_path)
    outputs = _render_outputs(manifest)
    changed: list[str] = []
    resolved_root = package_root.resolve()
    for relative_path, rendered in outputs.items():
        destination = (package_root / relative_path).resolve()
        if not destination.is_relative_to(resolved_root):
            raise ValueError(f"generated output escapes package root: {relative_path}")
        expected = rendered.encode("utf-8")
        actual = destination.read_bytes() if destination.is_file() else None
        if actual == expected:
            continue
        changed.append(relative_path)
        if not check:
            atomic_write_bytes(destination, expected)
    return CompileReport(
        models_generated=len(manifest.entries),
        registry_entries=len(manifest.entries),
        changed_paths=tuple(changed),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("src/amadeus_core/contracts/schema_manifest_v0_1.json"),
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("src/amadeus_core/contracts"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = compile_contract_models(
        args.manifest,
        args.package_root,
        check=args.check,
    )
    print(f"models_generated={report.models_generated}")
    print(f"registry_entries={report.registry_entries}")
    print(f"generated_diff={len(report.changed_paths)}")
    if report.changed_paths:
        print("changed_paths=" + ",".join(report.changed_paths))
    return 1 if args.check and report.changed_paths else 0


if __name__ == "__main__":
    raise SystemExit(main())
