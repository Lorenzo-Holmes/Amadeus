"""Pure validation for authoritative Core record envelopes."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from .common import FrozenModel
from .errors import CoreContractViolation, CoreErrorCode
from .hashing import canonical_json, sha256_hex
from .registry import (
    AUTHORITATIVE_MODELS,
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
    TYPE_REGISTRY,
)


@dataclass(frozen=True, slots=True)
class ContentHashMismatch(ValueError):
    field: str
    expected: str
    actual: str

    def __str__(self) -> str:
        return f"{self.field}: expected {self.expected}, got {self.actual}"


def _contract_violation(code: CoreErrorCode) -> CoreContractViolation:
    return CoreContractViolation(code)


def _pointer_tokens(pointer: str) -> tuple[str, ...]:
    if not pointer.startswith("/") or pointer == "/":
        raise ValueError(f"invalid frozen JSON Pointer: {pointer}")
    tokens: list[str] = []
    for raw_token in pointer[1:].split("/"):
        token: list[str] = []
        index = 0
        while index < len(raw_token):
            character = raw_token[index]
            if character != "~":
                token.append(character)
                index += 1
                continue
            if index + 1 >= len(raw_token) or raw_token[index + 1] not in {"0", "1"}:
                raise ValueError(f"invalid frozen JSON Pointer escape: {pointer}")
            token.append("~" if raw_token[index + 1] == "0" else "/")
            index += 2
        tokens.append("".join(token))
    return tuple(tokens)


def _project_hash_scope(
    body: Mapping[str, object],
    scope: tuple[str, ...],
) -> dict[str, object]:
    projected: dict[str, object] = {}
    for pointer in scope:
        tokens = _pointer_tokens(pointer)
        source: object = body
        for token in tokens:
            if not isinstance(source, Mapping) or token not in source:
                raise _contract_violation(CoreErrorCode.HASH_SCOPE_MISMATCH)
            source = source[token]

        destination = projected
        for token in tokens[:-1]:
            if token not in destination:
                destination[token] = {}
            child = destination[token]
            if not isinstance(child, dict):
                raise ValueError(f"overlapping frozen JSON Pointer: {pointer}")
            destination = cast(dict[str, object], child)
        leaf = tokens[-1]
        if leaf in destination:
            raise ValueError(f"duplicate frozen JSON Pointer: {pointer}")
        destination[leaf] = source
    return projected


def compute_record_content_hash(record: FrozenModel) -> str:
    record_type = type(record).__name__
    model = AUTHORITATIVE_MODELS.get(record_type)
    if model is None or not isinstance(record, model):
        raise TypeError(f"unregistered authoritative model: {record_type}")
    header = getattr(record, "record_header")
    registry_key = (record_type, header.schema_version)
    try:
        scope = HASH_SCOPE_REGISTRY[registry_key]
    except KeyError as error:
        raise ValueError(f"unregistered hash scope: {registry_key}") from error
    body = record.model_dump(mode="python")
    preimage = _project_hash_scope(body, scope)
    return sha256_hex(canonical_json(preimage))


def validate_authoritative_record(
    schema_root: str,
    body: Mapping[str, object],
) -> FrozenModel:
    raw_header = body.get("record_header")
    if not isinstance(raw_header, Mapping):
        raise _contract_violation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
    record_type = raw_header.get("record_type")
    schema_version = raw_header.get("schema_version")
    if not isinstance(record_type, str) or schema_version != "0.1":
        raise _contract_violation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
    spec = TYPE_REGISTRY.get(record_type)
    if spec is None or spec.schema_root != schema_root:
        raise _contract_violation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)

    model = AUTHORITATIVE_MODELS[record_type]
    record = model.model_validate(body)
    header = record.record_header

    body_record_id = getattr(record, spec.primary_key)
    if header.record_id != body_record_id or not body_record_id.startswith(spec.id_prefix):
        raise _contract_violation(CoreErrorCode.RECORD_ID_MISMATCH)

    bindings = (
        (header.identity_id, getattr(record, spec.identity_binding)),
        (header.lineage_id, getattr(record, spec.lineage_binding)),
        (header.branch_id, getattr(record, spec.branch_binding)),
    )
    if any(header_value != body_value for header_value, body_value in bindings):
        raise _contract_violation(CoreErrorCode.HEADER_BODY_MISMATCH)

    if not hmac.compare_digest(
        header.hash_scope_registry_digest,
        HASH_SCOPE_REGISTRY_DIGEST,
    ):
        raise _contract_violation(CoreErrorCode.HASH_SCOPE_MISMATCH)
    expected_scope = HASH_SCOPE_REGISTRY[(record_type, header.schema_version)]
    if header.hash_scope != expected_scope:
        raise _contract_violation(CoreErrorCode.HASH_SCOPE_MISMATCH)

    computed_hash = compute_record_content_hash(record)
    if not hmac.compare_digest(header.content_hash, computed_hash):
        raise ContentHashMismatch("record_header.content_hash", computed_hash, header.content_hash)
    if record_type == "LedgerEvent" and not hmac.compare_digest(
        record.event_hash,
        header.content_hash,
    ):
        raise ContentHashMismatch("event_hash", header.content_hash, record.event_hash)
    return record


__all__ = [
    "ContentHashMismatch",
    "compute_record_content_hash",
    "validate_authoritative_record",
]
