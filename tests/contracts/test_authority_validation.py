from copy import deepcopy
from datetime import UTC, datetime
from typing import Callable

import pytest
from pydantic import ValidationError

from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.identity import Identity
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)


IDN_1 = "idn-00000000-0000-4000-8000-000000000001"
IDN_2 = "idn-00000000-0000-4000-8000-000000000002"
LIN_1 = "lin-00000000-0000-4000-8000-000000000001"
LIN_2 = "lin-00000000-0000-4000-8000-000000000002"
BRN_1 = "brn-00000000-0000-4000-8000-000000000001"
BRN_2 = "brn-00000000-0000-4000-8000-000000000002"
EVT_1 = "evt-00000000-0000-4000-8000-000000000001"
IDENTITY_CONTENT_HASH = "cce18e75bd799ef039b38c5def6b701ffaf1e07c0639be5b86b272ccb6e30047"


def _identity_body() -> dict[str, object]:
    scope = HASH_SCOPE_REGISTRY[("Identity", "0.1")]
    return {
        "record_header": {
            "schema_version": "0.1",
            "record_type": "Identity",
            "record_id": IDN_1,
            "identity_id": IDN_1,
            "lineage_id": LIN_1,
            "branch_id": BRN_1,
            "created_at": datetime(2026, 7, 28, tzinfo=UTC),
            "created_by_event_id": EVT_1,
            "deployment_policy_ref": "dpl-test",
            "canonicalization": "core-canonical-json-v1",
            "hash_algorithm": "sha256",
            "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
            "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
            "hash_scope": scope,
            "content_hash": "0" * 64,
        },
        "identity_id": IDN_1,
        "canonical_name": "Amadeus",
        "lineage_id": LIN_1,
        "active_branch_id": BRN_1,
        "lifecycle_state": "active",
        "created_from_snapshot_id": None,
        "deployment_policy_ref": "dpl-test",
        "version": 1,
    }


def _valid_identity_body() -> dict[str, object]:
    body = _identity_body()
    header = body["record_header"]
    assert isinstance(header, dict)
    header["content_hash"] = IDENTITY_CONTENT_HASH
    return body


def _header(body: dict[str, object]) -> dict[str, object]:
    header = body["record_header"]
    assert isinstance(header, dict)
    return header


def test_valid_authoritative_record_returns_strict_typed_model() -> None:
    from amadeus_core.contracts import validation

    record = validation.validate_authoritative_record("identity", _valid_identity_body())

    assert isinstance(record, Identity)
    assert record.identity_id == IDN_1


@pytest.mark.parametrize("invalid_version", [0, -1])
def test_authoritative_record_version_must_be_positive(invalid_version: int) -> None:
    body = _identity_body()
    body["version"] = invalid_version

    with pytest.raises(ValidationError):
        Identity.model_validate(body)


@pytest.mark.parametrize(
    ("schema_root", "mutate"),
    [
        ("lineage", lambda body: None),
        ("identity", lambda body: _header(body).__setitem__("schema_version", "0.2")),
        ("identity", lambda body: _header(body).__setitem__("record_type", "Lineage")),
    ],
    ids=("schema-root", "schema-version", "record-type"),
)
def test_record_type_and_schema_mismatch_precedes_hashing(
    schema_root: str,
    mutate: Callable[[dict[str, object]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    mutate(body)
    monkeypatch.setattr(
        validation,
        "compute_record_content_hash",
        lambda record: pytest.fail("hashing ran before type/schema validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        validation.validate_authoritative_record(schema_root, body)
    assert captured.value.code is CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: _header(body).__setitem__("record_id", IDN_2),
        lambda body: (
            _header(body).__setitem__("record_id", LIN_1),
            body.__setitem__("identity_id", LIN_1),
        ),
    ],
    ids=("header-body-id", "record-prefix"),
)
def test_record_id_mismatch_precedes_hashing(
    mutate: Callable[[dict[str, object]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    mutate(body)
    monkeypatch.setattr(
        validation,
        "compute_record_content_hash",
        lambda record: pytest.fail("hashing ran before record ID validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        validation.validate_authoritative_record("identity", body)
    assert captured.value.code is CoreErrorCode.RECORD_ID_MISMATCH


@pytest.mark.parametrize(
    "field_and_value",
    [("identity_id", IDN_2), ("lineage_id", LIN_2), ("branch_id", BRN_2)],
    ids=("identity", "lineage", "branch"),
)
def test_header_body_binding_mismatch_precedes_hashing(
    field_and_value: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    field, value = field_and_value
    _header(body)[field] = value
    monkeypatch.setattr(
        validation,
        "compute_record_content_hash",
        lambda record: pytest.fail("hashing ran before Header/body validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        validation.validate_authoritative_record("identity", body)
    assert captured.value.code is CoreErrorCode.HEADER_BODY_MISMATCH


@pytest.mark.parametrize("mutation", ["delete", "add", "reorder", "replace"])
def test_hash_scope_must_match_frozen_registry_exactly(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    header = _header(body)
    scope = list(header["hash_scope"])
    if mutation == "delete":
        scope.pop()
    elif mutation == "add":
        scope.append("/unknown")
    elif mutation == "reorder":
        scope[0], scope[1] = scope[1], scope[0]
    else:
        scope[0] = "/replacement"
    header["hash_scope"] = tuple(scope)
    monkeypatch.setattr(
        validation,
        "compute_record_content_hash",
        lambda record: pytest.fail("hashing ran before hash-scope validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        validation.validate_authoritative_record("identity", body)
    assert captured.value.code is CoreErrorCode.HASH_SCOPE_MISMATCH


def test_hash_registry_digest_mismatch_precedes_scope_and_hashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    header = _header(body)
    header["hash_scope_registry_digest"] = "f" * 64
    header["hash_scope"] = ("/also-wrong",)
    monkeypatch.setattr(
        validation,
        "compute_record_content_hash",
        lambda record: pytest.fail("hashing ran before registry digest validation"),
    )

    with pytest.raises(CoreContractViolation) as captured:
        validation.validate_authoritative_record("identity", body)
    assert captured.value.code is CoreErrorCode.HASH_SCOPE_MISMATCH


def test_content_hash_mismatch_uses_internal_non_stable_exception() -> None:
    from amadeus_core.contracts import validation

    body = _valid_identity_body()
    _header(body)["content_hash"] = "f" * 64

    with pytest.raises(validation.ContentHashMismatch):
        validation.validate_authoritative_record("identity", body)


def _valid_ledger_event_body() -> dict[str, object]:
    from amadeus_core.contracts import validation

    scope = HASH_SCOPE_REGISTRY[("LedgerEvent", "0.1")]
    body: dict[str, object] = {
        "record_header": {
            "schema_version": "0.1",
            "record_type": "LedgerEvent",
            "record_id": EVT_1,
            "identity_id": IDN_1,
            "lineage_id": LIN_1,
            "branch_id": BRN_1,
            "created_at": datetime(2026, 7, 28, tzinfo=UTC),
            "created_by_event_id": EVT_1,
            "deployment_policy_ref": "dpl-test",
            "canonicalization": "core-canonical-json-v1",
            "hash_algorithm": "sha256",
            "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
            "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
            "hash_scope": scope,
            "content_hash": "0" * 64,
        },
        "event_id": EVT_1,
        "ledger_seq": 1,
        "identity_id": IDN_1,
        "lineage_id": LIN_1,
        "branch_id": BRN_1,
        "instance_id": "ins-00000000-0000-4000-8000-000000000001",
        "vault_id": None,
        "event_type": "identity_genesis_created",
        "occurred_at": datetime(2026, 7, 28, tzinfo=UTC),
        "ingested_at": datetime(2026, 7, 28, tzinfo=UTC),
        "actor_type": "system",
        "actor_id": "sys-00000000-0000-4000-8000-000000000001",
        "mutation_command_id": "cmd-00000000-0000-4000-8000-000000000001",
        "mutation_command_hash": "a" * 64,
        "payload_ref": "inline:genesis",
        "causation_id": None,
        "correlation_id": "flow-genesis",
        "previous_event_hash": None,
        "event_hash": "0" * 64,
        "version": 1,
    }
    record = LedgerEvent.model_validate(body)
    digest = validation.compute_record_content_hash(record)
    header = _header(body)
    header["content_hash"] = digest
    body["event_hash"] = digest
    return body


def test_ledger_event_double_hash_must_match_before_success() -> None:
    from amadeus_core.contracts import validation

    body = _valid_ledger_event_body()
    body["event_hash"] = "f" * 64

    with pytest.raises(validation.ContentHashMismatch) as captured:
        validation.validate_authoritative_record("event", body)
    assert captured.value.field == "event_hash"
