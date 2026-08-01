"""Compile the frozen Core hash-scope registry and digest artifacts."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

from amadeus_core.contracts.type_registry_build_spec import (
    FieldSpec,
    SchemaManifest,
    parse_schema_manifest,
)
from tools.stage0c_fixtures.io import canonical_bytes, load_strict_json_bytes
from tools.atomic_io import atomic_write_bytes


_EXCLUDED_HASH_ROLES = frozenset(
    {
        "output_hash_excluded",
        "signature_excluded",
        "registry_copy_excluded",
        "registry_integrity_excluded",
    }
)


@dataclass(frozen=True, slots=True)
class HashRegistryCompileReport:
    registry_entries: int
    digest: str
    changed_paths: tuple[str, ...]


def _pointer_segment(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _field_pointers(
    field: FieldSpec,
    prefix: str,
    value_objects: dict[str, tuple[FieldSpec, ...]],
) -> tuple[str, ...]:
    if field.hash_role in _EXCLUDED_HASH_ROLES:
        return ()
    pointer = f"{prefix}/{_pointer_segment(field.name)}"
    nested = value_objects.get(field.python_type)
    if nested is None:
        return (pointer,)
    result: list[str] = []
    for child in nested:
        result.extend(_field_pointers(child, pointer, value_objects))
    return tuple(result)


def _build_scopes(manifest: SchemaManifest) -> tuple[dict[str, object], dict[tuple[str, str], tuple[str, ...]]]:
    value_objects = {
        manifest.record_header.class_name: manifest.record_header.fields,
        **{item.class_name: item.fields for item in manifest.value_objects},
    }
    mapping: dict[tuple[str, str], tuple[str, ...]] = {}
    entries: list[dict[str, object]] = []
    for entry in manifest.entries:
        pointers: list[str] = []
        for field in entry.fields:
            pointers.extend(_field_pointers(field, "", value_objects))
        frozen = tuple(sorted(set(pointers)))
        key = (entry.record_type, manifest.schema_version)
        mapping[key] = frozen
        entries.append(
            {
                "hash_scope": list(frozen),
                "record_type": entry.record_type,
                "schema_version": manifest.schema_version,
            }
        )
    artifact = {
        "entries": entries,
        "registry_version": "core-hash-scope-registry-v0.1",
    }
    return artifact, mapping


def _render_module(
    mapping: dict[tuple[str, str], tuple[str, ...]],
    digest: str,
) -> bytes:
    lines = [
        '"""Generated static Core hash-scope registry."""',
        "",
        "from types import MappingProxyType",
        "",
        "",
        "HASH_SCOPE_REGISTRY = MappingProxyType({",
    ]
    for key, pointers in mapping.items():
        lines.append(f"    {key!r}: (")
        lines.extend(f"        {pointer!r}," for pointer in pointers)
        lines.append("    ),")
    lines.extend(
        [
            "})",
            f"HASH_SCOPE_REGISTRY_DIGEST = {digest!r}",
            "",
            '__all__ = ["HASH_SCOPE_REGISTRY", "HASH_SCOPE_REGISTRY_DIGEST"]',
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _load_manifest(path: Path) -> SchemaManifest:
    value = load_strict_json_bytes(path.read_bytes(), source=path.as_posix())
    return parse_schema_manifest(value)


def compile_hash_registry(
    *,
    manifest_path: Path,
    output_path: Path,
    digest_output_path: Path,
    module_output_path: Path,
    check: bool,
) -> HashRegistryCompileReport:
    manifest = _load_manifest(manifest_path)
    artifact, mapping = _build_scopes(manifest)
    registry_bytes = canonical_bytes(artifact)
    digest = hashlib.sha256(registry_bytes).hexdigest()
    outputs = {
        output_path: registry_bytes,
        digest_output_path: f"{digest}\n".encode("ascii"),
        module_output_path: _render_module(mapping, digest),
    }
    changed: list[str] = []
    for path, expected in outputs.items():
        actual = path.read_bytes() if path.is_file() else None
        if actual == expected:
            continue
        changed.append(path.name)
        if not check:
            atomic_write_bytes(path, expected)
    return HashRegistryCompileReport(
        registry_entries=len(mapping),
        digest=digest,
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
        "--output",
        type=Path,
        default=Path("src/amadeus_core/contracts/hash_scope_registry_v0_1.json"),
    )
    parser.add_argument(
        "--digest-output",
        type=Path,
        default=Path("src/amadeus_core/contracts/hash_scope_registry_digest.txt"),
    )
    parser.add_argument(
        "--module-output",
        type=Path,
        default=Path("src/amadeus_core/contracts/hash_scope.py"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = compile_hash_registry(
        manifest_path=args.manifest,
        output_path=args.output,
        digest_output_path=args.digest_output,
        module_output_path=args.module_output,
        check=args.check,
    )
    print(f"registry_entries={report.registry_entries}")
    print(f"registry_digest={report.digest}")
    print(f"generated_diff={len(report.changed_paths)}")
    if report.changed_paths:
        print("changed_paths=" + ",".join(report.changed_paths))
    return 1 if args.check and report.changed_paths else 0


if __name__ == "__main__":
    raise SystemExit(main())
