"""Keyed local attestations for hash-scope-excluded Governor signatures."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from types import MappingProxyType

from amadeus_core.contracts.hashing import canonical_json


_ATTESTATION_PREFIX = "govdec-v1"
_DOMAIN = "amadeus-core/governor-decision-attestation/v1"
_KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_TOKEN_PATTERN = re.compile(
    r"govdec-v1:([A-Za-z0-9][A-Za-z0-9._-]{0,63}):([0-9a-f]{64})"
)
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
_MINIMUM_SECRET_BYTES = 32


def _validated_key_id(key_id: str) -> str:
    if not isinstance(key_id, str) or _KEY_ID_PATTERN.fullmatch(key_id) is None:
        raise ValueError("Governor decision key_id has an invalid format")
    return key_id


def _validated_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("Governor decision actor_id must be a non-empty string")
    return actor_id


def _validated_secret(secret: bytes) -> bytes:
    if type(secret) is not bytes or len(secret) < _MINIMUM_SECRET_BYTES:
        raise ValueError("Governor decision HMAC secret must contain at least 32 bytes")
    return bytes(secret)


def _validated_hash(value: str, *, label: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"Governor decision {label} must be canonical SHA-256 text")
    return value


def _preimage(
    *,
    key_id: str,
    actor_id: str,
    decision_content_hash: str,
    command_hash: str,
) -> bytes:
    return canonical_json(
        {
            "domain": _DOMAIN,
            "algorithm": "hmac-sha256",
            "key_id": key_id,
            "actor_id": actor_id,
            "decision_content_hash": decision_content_hash,
            "mutation_command_hash": command_hash,
        }
    )


def _digest(
    secret: bytes,
    *,
    key_id: str,
    actor_id: str,
    decision_content_hash: str,
    command_hash: str,
) -> str:
    return hmac.new(
        secret,
        _preimage(
            key_id=key_id,
            actor_id=actor_id,
            decision_content_hash=decision_content_hash,
            command_hash=command_hash,
        ),
        hashlib.sha256,
    ).hexdigest()


class GovernorDecisionAttestor:
    """Attest decisions with one active key and verify retained historical keys."""

    __slots__ = ("_active_key_id", "_authorities")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("GovernorDecisionAttestor is final")

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_active_key_id", "_authorities"} and hasattr(self, name):
            raise AttributeError("Governor decision authority snapshot is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("Governor decision authority snapshot is immutable")

    def __init__(
        self,
        *,
        active_key_id: str,
        authorities: Mapping[str, tuple[str, bytes]],
    ) -> None:
        validated_active_key_id = _validated_key_id(active_key_id)
        if not isinstance(authorities, Mapping) or not authorities:
            raise ValueError("At least one Governor decision authority is required")

        closed: dict[str, tuple[str, bytes]] = {}
        for raw_key_id, authority in authorities.items():
            key_id = _validated_key_id(raw_key_id)
            if not isinstance(authority, tuple) or len(authority) != 2:
                raise ValueError("Governor decision authority must be (actor_id, secret)")
            actor_id, secret = authority
            closed[key_id] = (
                _validated_actor_id(actor_id),
                _validated_secret(secret),
            )
        if validated_active_key_id not in closed:
            raise ValueError("Active Governor decision key is not configured")
        self._active_key_id = validated_active_key_id
        self._authorities = MappingProxyType(closed)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(active_key_id={self._active_key_id!r}, "
            f"key_ids={tuple(self._authorities)!r}, secrets=<redacted>)"
        )

    def attest(
        self,
        *,
        decision_content_hash: str,
        command_hash: str,
        actor_id: str,
    ) -> str:
        decision_hash = _validated_hash(
            decision_content_hash,
            label="content hash",
        )
        mutation_hash = _validated_hash(command_hash, label="command hash")
        validated_actor_id = _validated_actor_id(actor_id)
        authority_actor_id, secret = self._authorities[self._active_key_id]
        if not hmac.compare_digest(
            validated_actor_id.encode("utf-8"),
            authority_actor_id.encode("utf-8"),
        ):
            raise ValueError("Governor decision actor_id is not configured for active key")
        digest = _digest(
            secret,
            key_id=self._active_key_id,
            actor_id=validated_actor_id,
            decision_content_hash=decision_hash,
            command_hash=mutation_hash,
        )
        return f"{_ATTESTATION_PREFIX}:{self._active_key_id}:{digest}"

    def verify(
        self,
        attestation: str,
        *,
        decision_content_hash: str,
        command_hash: str,
        actor_id: str,
    ) -> bool:
        try:
            if not isinstance(attestation, str):
                return False
            parsed = _TOKEN_PATTERN.fullmatch(attestation)
            if parsed is None:
                return False
            key_id, supplied_digest = parsed.groups()
            authority = self._authorities.get(key_id)
            if authority is None:
                return False
            authority_actor_id, secret = authority
            validated_actor_id = _validated_actor_id(actor_id)
            decision_hash = _validated_hash(
                decision_content_hash,
                label="content hash",
            )
            mutation_hash = _validated_hash(command_hash, label="command hash")
            expected_digest = _digest(
                secret,
                key_id=key_id,
                actor_id=validated_actor_id,
                decision_content_hash=decision_hash,
                command_hash=mutation_hash,
            )
            actor_matches = hmac.compare_digest(
                validated_actor_id.encode("utf-8"),
                authority_actor_id.encode("utf-8"),
            )
            return actor_matches and hmac.compare_digest(
                supplied_digest,
                expected_digest,
            )
        except Exception:
            return False


__all__ = ["GovernorDecisionAttestor"]
