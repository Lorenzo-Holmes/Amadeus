"""Closed-JSON Ledger payload storage and resolution boundaries."""

from __future__ import annotations

import hmac
import json
import math
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from amadeus_core.contracts.hashing import canonical_json, sha256_hex


_FORBIDDEN_KEY_MATERIAL_NAMES = frozenset(
    {"raw_key", "private_key_bytes", "default_shared_key"}
)
_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXTERNAL_REF = re.compile(r"^[a-z0-9][a-z0-9._-]*:[^\s:][^\s]*$")
MAX_RECEIPT_RESULT_BYTES = 64 * 1024


class LedgerPayloadMissing(LookupError):
    """The referenced payload is absent or cannot be parsed as closed JSON."""

    def __init__(self, payload_ref: str) -> None:
        self.payload_ref = payload_ref
        super().__init__(f"ledger payload missing: {payload_ref}")


class LedgerPayloadHashMismatch(ValueError):
    """Resolved payload content does not match its stored canonical hash."""

    def __init__(self, payload_ref: str, expected: str, actual: str) -> None:
        self.payload_ref = payload_ref
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"ledger payload hash mismatch for {payload_ref}: "
            f"expected {expected}, got {actual}"
        )


class ReceiptResultTooLarge(ValueError):
    """A command result must use an external reference instead of raw content."""

    def __init__(self, actual_bytes: int) -> None:
        self.actual_bytes = actual_bytes
        self.maximum_bytes = MAX_RECEIPT_RESULT_BYTES
        super().__init__(
            "receipt result exceeds canonical JSON byte limit: "
            f"{actual_bytes} > {MAX_RECEIPT_RESULT_BYTES}"
        )


@dataclass(frozen=True, slots=True)
class StoredLedgerPayload:
    payload_ref: str
    mode: str
    inline_json: str | None
    external_ref: str | None
    payload_hash: str
    media_type: str


@runtime_checkable
class ExternalPayloadAdapter(Protocol):
    def fetch(self, external_ref: str) -> bytes:
        """Fetch the raw JSON bytes at an opaque external reference."""


@runtime_checkable
class LedgerPayloadResolver(Protocol):
    def resolve(self, payload_ref: str) -> Mapping[str, object]:
        """Resolve and integrity-check one Ledger payload reference."""


def _closed_json(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("closed JSON strings must be valid UTF-8") from error
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("closed JSON numbers must be finite")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("closed JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        closed: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("closed JSON object keys must be strings")
            try:
                key.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("closed JSON keys must be valid UTF-8") from error
            if key in _FORBIDDEN_KEY_MATERIAL_NAMES:
                raise ValueError(f"raw key material field is forbidden: {key}")
            closed[key] = _closed_json(item)
        return MappingProxyType(closed)
    if isinstance(value, (list, tuple)):
        return tuple(_closed_json(item) for item in value)
    raise ValueError(f"value is outside the closed JSON domain: {type(value).__qualname__}")


def closed_json_object(value: object) -> Mapping[str, object]:
    closed = _closed_json(value)
    if not isinstance(closed, Mapping):
        raise ValueError("Ledger payload must be a closed JSON object")
    return closed


def _validate_lower_sha256(payload_hash: str) -> str:
    if not _LOWER_SHA256.fullmatch(payload_hash):
        raise ValueError("payload hash must be lowercase SHA-256 hex")
    return payload_hash


def _validate_external_ref(external_ref: str) -> str:
    if not _EXTERNAL_REF.fullmatch(external_ref):
        raise ValueError("external payload ref must be <provider-id>:<opaque-id>")
    return external_ref


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_non_finite_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _load_closed_json(raw: str) -> object:
    return json.loads(
        raw,
        parse_float=Decimal,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite_constant,
    )


def prepare_inline_payload(
    payload: object,
    *,
    media_type: str = "application/json",
) -> StoredLedgerPayload:
    closed = closed_json_object(payload)
    encoded = canonical_json(closed)
    payload_hash = sha256_hex(encoded)
    return StoredLedgerPayload(
        payload_ref=f"inline:{payload_hash}",
        mode="inline",
        inline_json=encoded.decode("utf-8"),
        external_ref=None,
        payload_hash=payload_hash,
        media_type=media_type,
    )


def prepare_external_payload(
    external_ref: str,
    payload_hash: str,
    *,
    media_type: str = "application/json",
) -> StoredLedgerPayload:
    validated_ref = _validate_external_ref(external_ref)
    validated_hash = _validate_lower_sha256(payload_hash)
    return StoredLedgerPayload(
        payload_ref=f"reference:{validated_ref}",
        mode="reference",
        inline_json=None,
        external_ref=validated_ref,
        payload_hash=validated_hash,
        media_type=media_type,
    )


def validate_stored_payload(payload: StoredLedgerPayload) -> StoredLedgerPayload:
    """Rebuild caller-supplied metadata from its trusted canonical inputs."""

    if payload.mode == "inline":
        if payload.inline_json is None or payload.external_ref is not None:
            raise ValueError("invalid inline payload storage metadata")
        try:
            decoded = _load_closed_json(payload.inline_json)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("inline payload is not valid JSON") from error
        validated = prepare_inline_payload(decoded, media_type=payload.media_type)
    elif payload.mode == "reference":
        if payload.inline_json is not None or payload.external_ref is None:
            raise ValueError("invalid reference payload storage metadata")
        validated = prepare_external_payload(
            payload.external_ref,
            payload.payload_hash,
            media_type=payload.media_type,
        )
    else:
        raise ValueError("unknown Ledger payload storage mode")
    if validated != payload:
        raise ValueError("Ledger payload storage metadata does not match canonical form")
    return validated


def validate_authority_bound_payload(
    payload: StoredLedgerPayload,
    authority_payload_ref: str,
) -> StoredLedgerPayload:
    """Validate the M3 inline descriptor anchored by immutable authority."""

    validated = validate_stored_payload(payload)
    prefix, separator, authority_hash = authority_payload_ref.partition(":")
    if prefix != "inline" or separator != ":":
        raise ValueError("Ledger reference payload metadata is not authority-bound")
    authority_hash = _validate_lower_sha256(authority_hash)
    if (
        validated.payload_ref != authority_payload_ref
        or validated.mode != "inline"
        or not hmac.compare_digest(validated.payload_hash, authority_hash)
        or validated.media_type != "application/json"
    ):
        raise ValueError("Ledger payload projection does not match authority")
    return validated


def canonical_closed_json(value: object) -> bytes:
    """Validate a value recursively and encode it with Core canonical JSON."""

    return canonical_json(_closed_json(value))


def canonical_receipt_result(value: object) -> bytes:
    encoded = canonical_closed_json(value)
    if len(encoded) > MAX_RECEIPT_RESULT_BYTES:
        raise ReceiptResultTooLarge(len(encoded))
    return encoded


class SQLiteLedgerPayloadResolver:
    def __init__(
        self,
        connection: sqlite3.Connection,
        external_adapter: ExternalPayloadAdapter | None = None,
    ) -> None:
        self._connection = connection
        self._external_adapter = external_adapter

    def resolve(self, payload_ref: str) -> Mapping[str, object]:
        row = self._connection.execute(
            """
            SELECT
                payload_mode,
                payload_inline_json,
                payload_external_ref,
                payload_hash
            FROM ledger_events
            WHERE payload_ref = ?
            ORDER BY event_id
            LIMIT 1
            """,
            (payload_ref,),
        ).fetchone()
        if row is None:
            raise LedgerPayloadMissing(payload_ref)

        mode = row["payload_mode"]
        if mode == "inline":
            raw = row["payload_inline_json"]
            if not isinstance(raw, str):
                raise LedgerPayloadMissing(payload_ref)
            raw_bytes = raw.encode("utf-8")
        elif mode == "reference":
            external_ref = row["payload_external_ref"]
            if not isinstance(external_ref, str) or self._external_adapter is None:
                raise LedgerPayloadMissing(payload_ref)
            try:
                raw_bytes = self._external_adapter.fetch(external_ref)
            except Exception as error:
                raise LedgerPayloadMissing(payload_ref) from error
            if not isinstance(raw_bytes, bytes):
                raise LedgerPayloadMissing(payload_ref)
        else:
            raise LedgerPayloadMissing(payload_ref)

        try:
            decoded = _load_closed_json(raw_bytes.decode("utf-8"))
            closed = closed_json_object(decoded)
            actual_hash = sha256_hex(canonical_json(closed))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise LedgerPayloadMissing(payload_ref) from error

        expected_hash = row["payload_hash"]
        if not isinstance(expected_hash, str) or not hmac.compare_digest(
            expected_hash,
            actual_hash,
        ):
            raise LedgerPayloadHashMismatch(payload_ref, str(expected_hash), actual_hash)
        return closed


__all__ = [
    "ExternalPayloadAdapter",
    "LedgerPayloadHashMismatch",
    "LedgerPayloadMissing",
    "LedgerPayloadResolver",
    "MAX_RECEIPT_RESULT_BYTES",
    "ReceiptResultTooLarge",
    "SQLiteLedgerPayloadResolver",
    "StoredLedgerPayload",
    "canonical_closed_json",
    "canonical_receipt_result",
    "closed_json_object",
    "prepare_external_payload",
    "prepare_inline_payload",
    "validate_authority_bound_payload",
    "validate_stored_payload",
]
