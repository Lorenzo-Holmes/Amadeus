"""Frozen deterministic Autobiographical Memory state transitions."""

from typing import Literal, TypeAlias

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode


MemoryState: TypeAlias = Literal["active", "contested", "superseded", "archived"]
MemorySourceState: TypeAlias = Literal[
    "absent",
    "active",
    "contested",
    "superseded",
    "archived",
]
MemoryTransition: TypeAlias = Literal[
    "governor_create",
    "accepted_correction_or_conflict",
    "evidence_resolved_keep",
    "replacement_committed",
    "governor_archive",
    "governor_reactivate_with_new_evidence",
]
MemoryTransitionEdge: TypeAlias = tuple[
    MemorySourceState,
    MemoryTransition,
    MemoryState,
]


ALLOWED_MEMORY_TRANSITIONS: frozenset[MemoryTransitionEdge] = frozenset(
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


def require_memory_transition(
    current_state: MemorySourceState,
    transition: MemoryTransition,
    target_state: MemoryState,
) -> None:
    """Require one exact frozen transition edge, failing closed otherwise."""

    if (current_state, transition, target_state) not in ALLOWED_MEMORY_TRANSITIONS:
        raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)


__all__ = [
    "ALLOWED_MEMORY_TRANSITIONS",
    "MemorySourceState",
    "MemoryState",
    "MemoryTransition",
    "MemoryTransitionEdge",
    "require_memory_transition",
]
