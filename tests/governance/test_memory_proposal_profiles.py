from __future__ import annotations

import pytest

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.governance.memory_proposal_profiles import (
    MEMORY_PROPOSAL_PROFILES,
    MEMORY_PROPOSAL_TYPES,
    memory_proposal_profile,
)


def test_memory_proposal_profiles_are_complete_frozen_and_fail_closed() -> None:
    expected = {
        "create_memory": ("create", "memory_created"),
        "change_memory_state": ("update", "memory_state_changed"),
        "change_expression_policy": (
            "update",
            "memory_expression_policy_changed",
        ),
        "set_importance": ("update", "memory_state_changed"),
        "set_consolidation": ("update", "memory_state_changed"),
    }

    assert MEMORY_PROPOSAL_TYPES == frozenset(expected)
    assert {
        proposal_type: (profile.effect_operation, profile.event_type)
        for proposal_type, profile in MEMORY_PROPOSAL_PROFILES.items()
    } == expected
    with pytest.raises(TypeError):
        MEMORY_PROPOSAL_PROFILES["create_memory"] = (  # type: ignore[index,assignment]
            "update",
            "memory_state_changed",
        )
    with pytest.raises(CoreContractViolation) as captured:
        memory_proposal_profile("future_memory_operation")
    assert captured.value.code is CoreErrorCode.GOVERNOR_POLICY_MISMATCH

