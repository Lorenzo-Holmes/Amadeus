"""Single frozen routing authority for normal Memory proposals."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, cast

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode


MemoryProposalType = Literal[
    "create_memory",
    "change_memory_state",
    "change_expression_policy",
    "set_importance",
    "set_consolidation",
]
MemoryEffectOperation = Literal["create", "update"]
MemoryEffectEventType = Literal[
    "memory_created",
    "memory_state_changed",
    "memory_expression_policy_changed",
]


@dataclass(frozen=True, slots=True)
class MemoryProposalProfile:
    effect_operation: MemoryEffectOperation
    event_type: MemoryEffectEventType


MEMORY_PROPOSAL_PROFILES = MappingProxyType(
    {
        "create_memory": MemoryProposalProfile("create", "memory_created"),
        "change_memory_state": MemoryProposalProfile(
            "update",
            "memory_state_changed",
        ),
        "change_expression_policy": MemoryProposalProfile(
            "update",
            "memory_expression_policy_changed",
        ),
        "set_importance": MemoryProposalProfile("update", "memory_state_changed"),
        "set_consolidation": MemoryProposalProfile(
            "update",
            "memory_state_changed",
        ),
    }
)
MEMORY_PROPOSAL_TYPES = frozenset(MEMORY_PROPOSAL_PROFILES)


def memory_proposal_profile(proposal_type: str) -> MemoryProposalProfile:
    profile = MEMORY_PROPOSAL_PROFILES.get(proposal_type)
    if profile is None:
        raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    return cast(MemoryProposalProfile, profile)


__all__ = [
    "MEMORY_PROPOSAL_PROFILES",
    "MEMORY_PROPOSAL_TYPES",
    "MemoryProposalProfile",
    "memory_proposal_profile",
]
