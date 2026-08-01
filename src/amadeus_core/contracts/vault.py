"""Generated authoritative Core v0.1 models."""

from typing import Literal

from .common import (
    BreakGlassExecutor,
    DeferConditions,
    ExpressionPolicy,
    FrozenModel,
    HashHex,
    IssuedToActor,
    JsonObject,
    PayloadRef,
    PositiveVersion,
    RemainingUses,
    ProposalActor,
    RecordHeader,
    RecordId,
    SingleUseLimit,
    UtcDatetime,
    VaultIssuer,
)


class RelationshipVault(FrozenModel):
    record_header: RecordHeader
    vault_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    relationship_principal_id: RecordId
    status: Literal['active', 'contact_paused', 'sealed']
    visibility_policy_ref: str
    created_at: UtcDatetime
    version: PositiveVersion

class VaultReadCapability(FrozenModel):
    record_header: RecordHeader
    capability_id: RecordId
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId
    principal_id: RecordId
    issuer: VaultIssuer
    issued_to_actor: IssuedToActor
    intended_audience: str
    allowed_operations: tuple[Literal['retrieve', 'express'], ...]
    allowed_purposes: tuple[Literal['response_context', 'reflection', 'consolidation'], ...]
    not_before: UtcDatetime
    issued_at: UtcDatetime
    expires_at: UtcDatetime
    policy_version: str
    nonce: str
    status: Literal['active', 'expired', 'revoked']
    attestation: str
    version: PositiveVersion

__all__ = [
    'RelationshipVault',
    'VaultReadCapability',
]
