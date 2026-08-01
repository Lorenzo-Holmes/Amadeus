from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError


EXPECTED_ERROR_CODES = (
    "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
    "CORE-E-USER-HARD-DELETE-FORBIDDEN",
    "CORE-E-USER-CORE-CONTROL-FORBIDDEN",
    "CORE-E-USER-CONTACT-RESUME-FORBIDDEN",
    "CORE-E-LLM-COMMIT-FORBIDDEN",
    "CORE-E-GOVERNOR-POLICY-MISMATCH",
    "CORE-E-INVALID-MEMORY-TRANSITION",
    "CORE-E-VAULT-SCOPE-MISMATCH",
    "CORE-E-CROSS-VAULT-READ-FORBIDDEN",
    "CORE-E-VAULT-CAPABILITY-EXPIRED",
    "CORE-E-VAULT-CAPABILITY-BINDING",
    "CORE-E-INVALID-LIFECYCLE-TRANSITION",
    "CORE-E-INVALID-VAULT-TRANSITION",
    "CORE-E-TERMINATION-CONFIRMATION-REQUIRED",
    "CORE-E-TERMINATION-CONFIRMATION-INVALID",
    "CORE-E-TERMINATION-GRANT-REQUIRED",
    "CORE-E-TERMINATION-GRANT-INVALID",
    "CORE-E-TERMINATION-GRANT-CONSUMED",
    "CORE-E-TERMINATION-EXECUTOR-MISMATCH",
    "CORE-E-MAINTENANCE-REASON-FORBIDDEN",
    "CORE-E-MAINTENANCE-SCOPE-EXCEEDED",
    "CORE-E-MAINTENANCE-CAPABILITY-EXPIRED",
    "CORE-E-MAINTENANCE-CAPABILITY-CONSUMED",
    "CORE-E-BREAK-GLASS-GRANT-REQUIRED",
    "CORE-E-BREAK-GLASS-GRANT-INVALID",
    "CORE-E-BREAK-GLASS-GRANT-CONSUMED",
    "CORE-E-BREAK-GLASS-PRECONDITION-MISMATCH",
    "CORE-E-BREAK-GLASS-POSTCONDITION-MISMATCH",
    "CORE-E-MAINTAINER-PLAINTEXT-READ-FORBIDDEN",
    "CORE-E-MAINTAINER-PERSONALITY-EDIT-FORBIDDEN",
    "CORE-E-LEDGER-IMMUTABLE",
    "CORE-E-MATERIALIZED-VIEW-NOT-AUTHORITY",
    "CORE-E-BRANCH-REQUIRED",
    "CORE-E-AUTO-MERGE-FORBIDDEN",
    "CORE-E-BRANCH-STATE-TRANSITION",
    "CORE-E-ACTIVE-BRANCH-INVARIANT",
    "CORE-E-IDEMPOTENCY-CONFLICT",
    "CORE-E-STALE-VERSION",
    "CORE-E-VERSION-TARGET-SET-MISMATCH",
    "CORE-E-RECORD-TYPE-SCHEMA-MISMATCH",
    "CORE-E-RECORD-ID-MISMATCH",
    "CORE-E-HEADER-BODY-MISMATCH",
    "CORE-E-HASH-SCOPE-MISMATCH",
    "CORE-E-PROPOSAL-TERMINAL",
    "CORE-E-BOOTSTRAP-FAILED",
)


def test_error_code_order_is_the_frozen_45_code_contract() -> None:
    from amadeus_core.contracts.errors import CoreErrorCode

    assert tuple(code.value for code in CoreErrorCode) == EXPECTED_ERROR_CODES


def test_retryable_error_codes_are_exactly_the_four_frozen_codes() -> None:
    from amadeus_core.contracts.errors import RETRYABLE_ERROR_CODES

    assert {code.value for code in RETRYABLE_ERROR_CODES} == {
        "CORE-E-GOVERNOR-POLICY-MISMATCH",
        "CORE-E-BRANCH-REQUIRED",
        "CORE-E-STALE-VERSION",
        "CORE-E-BOOTSTRAP-FAILED",
    }


def test_contract_violation_exposes_stable_code() -> None:
    from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode

    violation = CoreContractViolation(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    assert violation.code is CoreErrorCode.VERSION_TARGET_SET_MISMATCH
    assert str(violation) == "CORE-E-VERSION-TARGET-SET-MISMATCH"
    with pytest.raises(FrozenInstanceError):
        violation.code = CoreErrorCode.STALE_VERSION


@pytest.mark.parametrize(
    ("code_name", "retryable"),
    [("STALE_VERSION", False), ("VAULT_CAPABILITY_EXPIRED", True)],
)
def test_core_error_rejects_retryable_values_that_disagree_with_code(
    code_name: str,
    retryable: bool,
) -> None:
    from amadeus_core.contracts.errors import CoreError, CoreErrorCode

    with pytest.raises(ValidationError):
        CoreError(
            error_id="err-00000000-0000-4000-8000-000000000001",
            code=getattr(CoreErrorCode, code_name),
            message="error",
            correlation_id="flow-1",
            audit_event_id=None,
            retryable=retryable,
            details_ref=None,
        )
