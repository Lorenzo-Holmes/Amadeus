"""Domain-separated binding between a Governor decision and its projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from amadeus_core.contracts.hashing import canonical_json, sha256_hex

from .memory_proposal_profiles import MEMORY_PROPOSAL_PROFILES


_OUTPUT_BINDING_PROFILE = "amadeus.governor-receipt-output-binding.v0.2"
_ATTESTATION_SUBJECT_PROFILE = (
    "amadeus.governor-receipt-output-attestation-subject.v0.2"
)
_RESULT_EVENT_COUNTS = {"commit": 2, "reject": 1, "defer": 2}
_MEMORY_EVENT_OPERATION = {
    "memory_created": "create",
    "memory_state_changed": "update",
    "memory_expression_policy_changed": "update",
}
_MEMORY_STATES = frozenset(
    {"active", "contested", "superseded", "archived"}
)
_MEMORY_EFFECT_PAYLOAD_FIELDS = frozenset(
    {
        "decision_id",
        "proposal_id",
        "proposal_type",
        "memory_id",
        "before_content_hash",
        "memory_content_hash",
        "state",
        "semantic_version",
        "version",
    }
)
_MEMORY_EFFECT_DESCRIPTOR_FIELDS = frozenset(
    {
        "event_type",
        "operation",
        *_MEMORY_EFFECT_PAYLOAD_FIELDS,
    }
)


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _ordered_event_ids(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    event_ids = tuple(value)
    if any(not _is_identifier(event_id) for event_id in event_ids):
        return None
    return event_ids


def _closed_memory_effect(
    value: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if (
        value is None
        or not isinstance(value, Mapping)
        or frozenset(value) != _MEMORY_EFFECT_DESCRIPTOR_FIELDS
    ):
        return None
    event_type = value.get("event_type")
    operation = value.get("operation")
    decision_id = value.get("decision_id")
    proposal_id = value.get("proposal_id")
    proposal_type = value.get("proposal_type")
    memory_id = value.get("memory_id")
    before_content_hash = value.get("before_content_hash")
    memory_content_hash = value.get("memory_content_hash")
    state = value.get("state")
    semantic_version = value.get("semantic_version")
    version = value.get("version")
    expected_operation = (
        _MEMORY_EVENT_OPERATION.get(event_type)
        if isinstance(event_type, str)
        else None
    )
    if (
        expected_operation is None
        or operation != expected_operation
        or not _is_identifier(decision_id)
        or not _is_identifier(proposal_id)
        or not isinstance(proposal_type, str)
        or proposal_type not in MEMORY_PROPOSAL_PROFILES
        or not _is_identifier(memory_id)
        or (
            before_content_hash is None
            and operation != "create"
        )
        or (
            before_content_hash is not None
            and (
                operation == "create"
                or not _is_hash(before_content_hash)
            )
        )
        or not _is_hash(memory_content_hash)
        or not isinstance(state, str)
        or state not in _MEMORY_STATES
        or not _is_positive_int(semantic_version)
        or not _is_positive_int(version)
    ):
        return None
    return {
        "event_type": event_type,
        "operation": operation,
        "decision_id": decision_id,
        "proposal_id": proposal_id,
        "proposal_type": proposal_type,
        "memory_id": memory_id,
        "before_content_hash": before_content_hash,
        "memory_content_hash": memory_content_hash,
        "state": state,
        "semantic_version": semantic_version,
        "version": version,
    }


def _closed_output_descriptor(
    *,
    decision_id: object,
    proposal_id: object,
    proposal_type: object,
    result: object,
    committed_event_ids: object,
    proposal_after_content_hash: object,
    memory_effect: Mapping[str, object] | None,
) -> dict[str, object] | None:
    event_ids = _ordered_event_ids(committed_event_ids)
    expected_event_count = (
        _RESULT_EVENT_COUNTS.get(result) if isinstance(result, str) else None
    )
    if (
        not _is_identifier(decision_id)
        or not _is_identifier(proposal_id)
        or not isinstance(proposal_type, str)
        or proposal_type not in MEMORY_PROPOSAL_PROFILES
        or expected_event_count is None
        or event_ids is None
        or len(event_ids) != expected_event_count
        or not _is_hash(proposal_after_content_hash)
    ):
        return None
    closed_effect = _closed_memory_effect(memory_effect)
    if result == "commit":
        if closed_effect is None:
            return None
    elif memory_effect is not None:
        return None
    return {
        "profile": _OUTPUT_BINDING_PROFILE,
        "decision_id": decision_id,
        "proposal_id": proposal_id,
        "proposal_type": proposal_type,
        "result": result,
        "committed_event_ids": event_ids,
        "proposal_after_content_hash": proposal_after_content_hash,
        "memory_effect": closed_effect,
    }


def compute_receipt_output_binding_hash(
    *,
    decision_id: str,
    proposal_id: str,
    proposal_type: str,
    result: Literal["commit", "reject", "defer"],
    committed_event_ids: Sequence[str],
    proposal_after_content_hash: str,
    memory_effect: Mapping[str, object] | None,
) -> str:
    """Hash the exact closed authority projection produced by one decision."""

    descriptor = _closed_output_descriptor(
        decision_id=decision_id,
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        result=result,
        committed_event_ids=committed_event_ids,
        proposal_after_content_hash=proposal_after_content_hash,
        memory_effect=memory_effect,
    )
    if descriptor is None:
        raise ValueError("invalid Governor receipt output descriptor")
    return sha256_hex(canonical_json(descriptor))


def receipt_output_binding_from_payloads(
    decision_payload: Mapping[str, object],
    projection_payload: Mapping[str, object],
    *,
    result: Literal["commit", "reject", "defer"],
    committed_event_ids: Sequence[str],
    memory_payload: Mapping[str, object] | None = None,
    memory_event_type: str | None = None,
) -> str | None:
    """Rebuild a receipt-output binding from immutable Ledger payloads."""

    decision_id = decision_payload.get("decision_id")
    proposal_id = decision_payload.get("proposal_id")
    proposal_type = decision_payload.get("proposal_type")
    proposal_hash = projection_payload.get("proposal_content_hash")
    memory_effect: dict[str, object] | None = None
    if result == "commit":
        if (
            memory_payload is None
            or not isinstance(memory_payload, Mapping)
            or frozenset(memory_payload) != _MEMORY_EFFECT_PAYLOAD_FIELDS
            or not isinstance(memory_event_type, str)
            or memory_event_type not in _MEMORY_EVENT_OPERATION
        ):
            return None
        memory_effect = {
            "event_type": memory_event_type,
            "operation": _MEMORY_EVENT_OPERATION[memory_event_type],
            "decision_id": memory_payload.get("decision_id"),
            "proposal_id": memory_payload.get("proposal_id"),
            "proposal_type": memory_payload.get("proposal_type"),
            "memory_id": memory_payload.get("memory_id"),
            "before_content_hash": memory_payload.get("before_content_hash"),
            "memory_content_hash": memory_payload.get("memory_content_hash"),
            "state": memory_payload.get("state"),
            "semantic_version": memory_payload.get("semantic_version"),
            "version": memory_payload.get("version"),
        }
    elif memory_payload is not None or memory_event_type is not None:
        return None
    descriptor = _closed_output_descriptor(
        decision_id=decision_id,
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        result=result,
        committed_event_ids=committed_event_ids,
        proposal_after_content_hash=proposal_hash,
        memory_effect=memory_effect,
    )
    if descriptor is None:
        return None
    return sha256_hex(canonical_json(descriptor))


def receipt_output_attestation_subject_hash(
    *,
    decision_content_hash: str,
    output_binding_hash: str,
) -> str:
    """Domain-separate the extra projection attestation from Decision signing."""

    return sha256_hex(
        canonical_json(
            {
                "profile": _ATTESTATION_SUBJECT_PROFILE,
                "decision_content_hash": decision_content_hash,
                "output_binding_hash": output_binding_hash,
            }
        )
    )


__all__: list[str] = []
