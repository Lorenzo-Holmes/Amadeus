"""Unforgeable local authority for Governor memory-decision commands.

The signer belongs at the trusted composition root.  Runtime Governor services
receive only a verifier, so an untrusted caller cannot mint a capability from a
syntactically valid actor claim.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from types import MappingProxyType

from amadeus_core.contracts.commands import (
    MutationCommandEnvelope,
    normalize_command_for_hash,
)
from amadeus_core.contracts.hashing import canonical_json


_AUTHORITY_PREFIX = "govcmd-v1"
_ALLOWED_ACTOR_TYPE = "governor"
_ALLOWED_COMMAND_TYPE = "memory_proposal.decide"
_ATTESTATION_SENTINEL = "__GOVERNOR_COMMAND_ATTESTATION_V1__"
_DOMAIN = "amadeus-core/governor-command-auth/v1"
_KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_TOKEN_PATTERN = re.compile(
    r"govcmd-v1:([A-Za-z0-9][A-Za-z0-9._-]{0,63}):([0-9a-f]{64})"
)
_CAPABILITY_PATTERN = re.compile(
    r"govcap:([A-Za-z0-9][A-Za-z0-9._-]{0,63})"
)
_MINIMUM_SECRET_BYTES = 32


def _validated_secret(secret: bytes) -> bytes:
    if type(secret) is not bytes or len(secret) < _MINIMUM_SECRET_BYTES:
        raise ValueError("Governor command HMAC secret must contain at least 32 bytes")
    return bytes(secret)


def _validated_key_id(key_id: str) -> str:
    if not isinstance(key_id, str) or _KEY_ID_PATTERN.fullmatch(key_id) is None:
        raise ValueError("Governor command key_id has an invalid format")
    return key_id


def _validated_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("Governor command actor_id must be a non-empty string")
    return actor_id


def _command_snapshot(command: MutationCommandEnvelope) -> MutationCommandEnvelope:
    return MutationCommandEnvelope.model_validate(command.model_dump(mode="python"))


def _signature_preimage(command: MutationCommandEnvelope) -> bytes:
    body = command.model_dump(mode="python")
    payload = body["payload"]
    payload["actor_attestation"] = _ATTESTATION_SENTINEL
    body["payload"] = payload
    sentinel_command = MutationCommandEnvelope.model_validate(body)
    normalized = normalize_command_for_hash(sentinel_command)
    return canonical_json(
        {
            "domain": _DOMAIN,
            "algorithm": "hmac-sha256",
            "command": normalized,
        }
    )


def _digest(secret: bytes, command: MutationCommandEnvelope) -> str:
    return hmac.new(secret, _signature_preimage(command), hashlib.sha256).hexdigest()


class GovernorCommandSigner:
    """Mint command-bound capabilities inside a trusted composition root."""

    __slots__ = ("_actor_id", "_key_id", "_secret")

    def __init__(self, *, key_id: str, actor_id: str, secret: bytes) -> None:
        self._key_id = _validated_key_id(key_id)
        self._actor_id = _validated_actor_id(actor_id)
        self._secret = _validated_secret(secret)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(key_id={self._key_id!r}, "
            f"actor_id={self._actor_id!r}, secret=<redacted>)"
        )

    def sign(self, command: MutationCommandEnvelope) -> MutationCommandEnvelope:
        snapshot = _command_snapshot(command)
        if snapshot.actor.actor_type != _ALLOWED_ACTOR_TYPE:
            raise ValueError("Governor command signer only permits governor actors")
        if snapshot.actor.actor_id != self._actor_id:
            raise ValueError("Governor command actor_id is not configured for this key")
        if snapshot.command_type != _ALLOWED_COMMAND_TYPE:
            raise ValueError("Governor command signer only permits memory decisions")

        body = snapshot.model_dump(mode="python")
        body["actor_capability_id"] = f"govcap:{self._key_id}"
        authority_payload = body["payload"]
        authority_payload["actor_attestation"] = _ATTESTATION_SENTINEL
        body["payload"] = authority_payload
        authority_command = MutationCommandEnvelope.model_validate(body)
        attestation = (
            f"{_AUTHORITY_PREFIX}:{self._key_id}:"
            f"{_digest(self._secret, authority_command)}"
        )
        signed_payload = authority_command.model_dump(mode="python")["payload"]
        signed_payload["actor_attestation"] = attestation
        return authority_command.model_copy(update={"payload": signed_payload})


class GovernorCommandVerifier:
    """Verify command-bound capabilities without exposing signing operations."""

    __slots__ = ("_authorities",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("GovernorCommandVerifier is final")

    def __setattr__(self, name: str, value: object) -> None:
        if name == "_authorities" and hasattr(self, name):
            raise AttributeError("Governor command authority snapshot is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("Governor command authority snapshot is immutable")

    def __init__(self, authorities: Mapping[str, tuple[str, bytes]]) -> None:
        if not isinstance(authorities, Mapping) or not authorities:
            raise ValueError("At least one Governor command authority is required")

        closed: dict[str, tuple[str, bytes]] = {}
        for raw_key_id, authority in authorities.items():
            key_id = _validated_key_id(raw_key_id)
            if not isinstance(authority, tuple) or len(authority) != 2:
                raise ValueError("Governor command authority must be (actor_id, secret)")
            actor_id, secret = authority
            closed[key_id] = (
                _validated_actor_id(actor_id),
                _validated_secret(secret),
            )
        self._authorities = MappingProxyType(closed)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(key_ids={tuple(self._authorities)!r})"

    def verify(self, command: MutationCommandEnvelope) -> bool:
        try:
            snapshot = _command_snapshot(command)
            capability = _CAPABILITY_PATTERN.fullmatch(snapshot.actor_capability_id)
            supplied_attestation = snapshot.payload.get("actor_attestation")
            if capability is None or not isinstance(supplied_attestation, str):
                return False
            parsed = _TOKEN_PATTERN.fullmatch(supplied_attestation)
            if parsed is None:
                return False
            capability_key_id = capability.group(1)
            key_id, supplied_digest = parsed.groups()
            if not hmac.compare_digest(key_id, capability_key_id):
                return False
            authority = self._authorities.get(key_id)
            if authority is None:
                return False
            actor_id, secret = authority
            expected_digest = _digest(secret, snapshot)
            digest_matches = hmac.compare_digest(supplied_digest, expected_digest)
            actor_matches = (
                snapshot.actor.actor_type == _ALLOWED_ACTOR_TYPE
                and snapshot.actor.actor_id == actor_id
            )
            command_matches = snapshot.command_type == _ALLOWED_COMMAND_TYPE
            return digest_matches and actor_matches and command_matches
        except Exception:
            return False


__all__ = ["GovernorCommandSigner", "GovernorCommandVerifier"]
