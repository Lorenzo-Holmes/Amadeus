"""Pure all-binding validation for a VaultReadCapability."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Protocol

from amadeus_core.contracts.commands import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.vault import VaultReadCapability


class AttestationVerifier(Protocol):
    def verify(self, attestation: str, payload_hash: str) -> bool: ...


class IssuerRegistry(Protocol):
    def is_trusted(self, issuer: Actor, policy_version: str) -> bool: ...


def validate_vault_read_capability(
    capability: VaultReadCapability,
    *,
    actor: Actor,
    intended_audience: str,
    identity_id: str,
    lineage_id: str,
    branch_id: str,
    vault_id: str,
    principal_id: str,
    policy_version: str,
    operation: Literal["retrieve", "express"],
    purpose: Literal["response_context", "reflection", "consolidation"],
    now: datetime,
    issuer_registry: IssuerRegistry,
    attestation_verifier: AttestationVerifier,
) -> CoreErrorCode | None:
    """Validate every capability binding without storage or command side effects."""
    if type(now) is not datetime or now.tzinfo is None:
        return CoreErrorCode.VAULT_CAPABILITY_BINDING
    try:
        utc_offset = now.utcoffset()
    except Exception:
        return CoreErrorCode.VAULT_CAPABILITY_BINDING
    if utc_offset != timedelta(0):
        return CoreErrorCode.VAULT_CAPABILITY_BINDING
    if now < capability.not_before:
        return CoreErrorCode.VAULT_CAPABILITY_BINDING
    if now >= capability.expires_at or capability.status == "expired":
        return CoreErrorCode.VAULT_CAPABILITY_EXPIRED
    issuer = Actor(
        actor_type=capability.issuer.actor_type,
        actor_id=capability.issuer.actor_id,
    )
    payload_hash = sha256_hex(
        canonical_json(capability.model_dump(mode="python", exclude={"attestation"}))
    )
    try:
        trusted_issuer = issuer_registry.is_trusted(issuer, policy_version)
    except Exception:
        trusted_issuer = False
    try:
        valid_attestation = attestation_verifier.verify(
            capability.attestation, payload_hash
        )
    except Exception:
        valid_attestation = False
    if (
        capability.status != "active"
        or capability.issued_to_actor.actor_type != actor.actor_type
        or capability.issued_to_actor.actor_id != actor.actor_id
        or capability.intended_audience != intended_audience
        or capability.identity_id != identity_id
        or capability.lineage_id != lineage_id
        or capability.branch_id != branch_id
        or capability.vault_id != vault_id
        or capability.principal_id != principal_id
        or capability.policy_version != policy_version
        or operation not in capability.allowed_operations
        or purpose not in capability.allowed_purposes
        or trusted_issuer is not True
        or valid_attestation is not True
    ):
        return CoreErrorCode.VAULT_CAPABILITY_BINDING
    return None


__all__ = [
    "AttestationVerifier",
    "IssuerRegistry",
    "validate_vault_read_capability",
]
