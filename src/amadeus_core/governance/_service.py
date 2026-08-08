"""Shared closed-result helpers for governance services."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar, cast

from pydantic import ValidationError

from amadeus_core.contracts.commands import CommandResult, MutationCommandEnvelope
from amadeus_core.contracts.common import FrozenModel
from amadeus_core.contracts.errors import (
    CoreContractViolation,
    CoreError,
    CoreErrorCode,
    RETRYABLE_ERROR_CODES,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import (
    ContentHashMismatch,
    validate_authoritative_record,
)
from amadeus_core.ids import new_id
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


@dataclass(frozen=True, slots=True)
class GovernanceViolation(ValueError):
    code: CoreErrorCode


ResultModel = TypeVar("ResultModel", bound=FrozenModel)


def failure_result(
    command: MutationCommandEnvelope,
    code: CoreErrorCode,
) -> CommandResult[object]:
    return CommandResult[object](
        value=None,
        event_ids=(),
        error=CoreError(
            error_id=new_id("error"),
            code=code,
            message=code.value,
            correlation_id=command.audit_context_id,
            audit_event_id=None,
            retryable=code in RETRYABLE_ERROR_CODES,
            details_ref=None,
        ),
        replayed=False,
    )


def semantic_input_hash_matches(
    command: MutationCommandEnvelope,
    value: FrozenModel,
) -> bool:
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(value.model_dump(mode="python")))
    return isinstance(supplied, str) and hmac.compare_digest(supplied, expected)


def typed_result(
    result: CommandResult[object],
    model_type: type[ResultModel],
    *,
    receipt_label: str,
    schema_root: str,
    expected_record_id: str,
) -> CommandResult[ResultModel]:
    try:
        if result.value is None:
            value = None
        elif isinstance(result.value, model_type):
            value = model_type.model_validate(result.value.model_dump(mode="python"))
        else:
            value = model_type.model_validate_json(
                canonical_json(
                    dict(cast(Mapping[str, object], result.value))
                )
            )
        if value is not None:
            value = model_type.model_validate(
                validate_authoritative_record(
                    schema_root,
                    value.model_dump(mode="python"),
                ).model_dump(mode="python")
            )
            spec = TYPE_REGISTRY[type(value).__name__]
            if (
                getattr(value, spec.primary_key) != expected_record_id
                or value.record_header.record_id != expected_record_id
            ):
                raise ValueError("receipt value record id mismatch")
    except (
        ContentHashMismatch,
        CoreContractViolation,
        TypeError,
        ValueError,
        ValidationError,
    ) as error:
        if result.replayed:
            raise ReceiptIntegrityError(
                f"{receipt_label} receipt value has the wrong authoritative shape"
            ) from error
        raise
    return CommandResult[ResultModel](
        value=value,
        event_ids=result.event_ids,
        error=result.error,
        replayed=result.replayed,
    )


__all__ = [
    "GovernanceViolation",
    "failure_result",
    "semantic_input_hash_matches",
    "typed_result",
]
