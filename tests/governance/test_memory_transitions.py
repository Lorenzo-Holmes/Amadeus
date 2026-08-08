import pytest

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode


EXPECTED_MEMORY_TRANSITIONS = frozenset(
    {
        ("absent", "governor_create", "active"),
        ("active", "accepted_correction_or_conflict", "contested"),
        ("contested", "evidence_resolved_keep", "active"),
        ("contested", "replacement_committed", "superseded"),
        ("active", "replacement_committed", "superseded"),
        ("active", "governor_archive", "archived"),
        ("contested", "governor_archive", "archived"),
        ("superseded", "governor_archive", "archived"),
        ("archived", "governor_reactivate_with_new_evidence", "active"),
    }
)


def test_allowed_memory_transitions_are_the_exact_frozen_nine_edges() -> None:
    from amadeus_core.governance.memory_transitions import (
        ALLOWED_MEMORY_TRANSITIONS,
    )

    assert ALLOWED_MEMORY_TRANSITIONS == EXPECTED_MEMORY_TRANSITIONS


def test_archived_cannot_transition_directly_to_superseded() -> None:
    from amadeus_core.governance.memory_transitions import require_memory_transition

    with pytest.raises(CoreContractViolation) as captured:
        require_memory_transition(
            "archived",
            "replacement_committed",
            "superseded",
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION
