from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import pytest
from pydantic import TypeAdapter, ValidationError

from amadeus_core.contracts import common


def test_record_id_requires_frozen_lowercase_prefixed_shape() -> None:
    adapter = TypeAdapter(common.RecordId)

    assert adapter.validate_python("idn-00000000-0000-4000-8000-000000000001")
    for invalid in (
        "IDN-00000000-0000-4000-8000-000000000001",
        "id-0001",
        "idn_0001",
        "idn-value",
        "idn-----",
    ):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_hash_hex_requires_exact_lowercase_sha256_shape() -> None:
    adapter = TypeAdapter(common.HashHex)

    assert adapter.validate_python("a" * 64) == "a" * 64
    for invalid in ("a" * 63, "A" * 64, "g" * 64):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_record_header_actor_and_audit_context_are_strict_frozen_models() -> None:
    assert tuple(common.RecordHeader.model_fields) == (
        "schema_version",
        "record_type",
        "record_id",
        "identity_id",
        "lineage_id",
        "branch_id",
        "created_at",
        "created_by_event_id",
        "deployment_policy_ref",
        "canonicalization",
        "hash_algorithm",
        "hash_scope_registry_version",
        "hash_scope_registry_digest",
        "hash_scope",
        "content_hash",
    )
    assert tuple(common.Actor.model_fields) == ("actor_type", "actor_id")
    assert tuple(common.AuditContext.model_fields) == (
        "context_id",
        "correlation_id",
        "actor_id",
        "actor_type",
        "capability_id",
        "purpose_code",
        "source_instance_id",
        "source_terminal_ref",
        "started_at",
    )
    for model in (common.RecordHeader, common.Actor, common.AuditContext):
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["frozen"] is True
        assert model.model_config["strict"] is True

    actor = common.Actor(actor_type="system", actor_id="system-test")
    audit = common.AuditContext(
        context_id="aud-1",
        correlation_id="flow-1",
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        capability_id="cap-1",
        purpose_code="bootstrap",
        source_instance_id="instance-1",
        source_terminal_ref="terminal-1",
        started_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        audit.started_at = datetime(2026, 8, 2, tzinfo=UTC)


@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 8, 1),
        datetime(2026, 8, 1, tzinfo=timezone(timedelta(hours=8))),
    ],
    ids=("naive", "non-utc"),
)
def test_contract_datetime_fields_require_utc(invalid_time: datetime) -> None:
    with pytest.raises(ValidationError):
        common.AuditContext(
            context_id="aud-1",
            correlation_id="flow-1",
            actor_id="system-test",
            actor_type="system",
            capability_id="cap-1",
            purpose_code="bootstrap",
            source_instance_id="instance-1",
            source_terminal_ref="terminal-1",
            started_at=invalid_time,
        )


def test_single_use_capability_counters_have_exact_ranges() -> None:
    from amadeus_core.contracts.capabilities import (
        BreakGlassGrant,
        MaintenanceCapability,
        TerminationExecutionGrant,
    )

    for model in (TerminationExecutionGrant, MaintenanceCapability):
        field = model.model_fields["use_limit"]
        adapter = TypeAdapter(Annotated[field.annotation, *field.metadata])
        assert adapter.validate_python(1) == 1
        for invalid in (0, 2, True):
            with pytest.raises(ValidationError):
                adapter.validate_python(invalid)

    max_field = BreakGlassGrant.model_fields["max_uses"]
    remaining_field = BreakGlassGrant.model_fields["remaining_uses"]
    max_uses = TypeAdapter(Annotated[max_field.annotation, *max_field.metadata])
    remaining_uses = TypeAdapter(
        Annotated[remaining_field.annotation, *remaining_field.metadata]
    )
    assert max_uses.validate_python(1) == 1
    assert remaining_uses.validate_python(0) == 0
    assert remaining_uses.validate_python(1) == 1
    for invalid in (0, 2, True):
        with pytest.raises(ValidationError):
            max_uses.validate_python(invalid)
    for invalid in (-1, 2, True):
        with pytest.raises(ValidationError):
            remaining_uses.validate_python(invalid)
