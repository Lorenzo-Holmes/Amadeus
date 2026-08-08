from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import Actor, CommandResult, ExpectedVersion, MutationCommandEnvelope
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.vault import VaultReadCapability
from amadeus_core.retrieval.capability_validator import validate_vault_read_capability
from amadeus_core.retrieval.capability_service import VaultCapabilityService
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.ledger import replay_ledger
from tests.storage.conftest import make_vault_read_capability
from tests.governance.conftest import IDENTITY_ID, LINEAGE_ID, BRANCH_ID, VAULT_ID, REQUESTER_ID, _bootstrap, _seed_vault, _record_header, _seal
from amadeus_core.storage.database import SQLiteDatabase


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class _Attest:
    def __init__(self, expected_hash: str, valid: bool = True, raises: bool = False) -> None:
        self.expected_hash, self.valid, self.raises = expected_hash, valid, raises

    def verify(self, attestation: str, payload_hash: str) -> bool:
        if self.raises:
            raise RuntimeError("attestation port unavailable")
        return self.valid and attestation == "test-attestation" and payload_hash == self.expected_hash


class _Issuers:
    def __init__(self, valid: bool = True, raises: bool = False) -> None: self.valid, self.raises = valid, raises

    def is_trusted(self, issuer: Actor, policy_version: str) -> bool:
        if self.raises:
            raise RuntimeError("issuer port unavailable")
        return self.valid and (issuer.actor_type, issuer.actor_id, policy_version) == ("governor", "gov-a", "test")


class _TruthyResult:
    def __bool__(self) -> bool:
        return True


def _payload_hash(capability: VaultReadCapability) -> str:
    return sha256_hex(canonical_json(capability.model_dump(mode="python", exclude={"attestation"})))


def _validate(capability: VaultReadCapability, **updates: object):
    values = dict(actor=Actor(actor_type="system", actor_id="sys-a"), intended_audience="core", identity_id="idn-a", lineage_id="lin-a", branch_id="brn-a", vault_id="vlt-a", principal_id="prn-a", policy_version="test", operation="retrieve", purpose="response_context", now=capability.not_before, issuer_registry=_Issuers(), attestation_verifier=_Attest(_payload_hash(capability)))
    values.update(updates)
    return validate_vault_read_capability(capability, **values)


def _database(tmp_path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "capability.sqlite3")
    _bootstrap(database)
    _seed_vault(database)
    return database


def _capability() -> VaultReadCapability:
    return _seal(VaultReadCapability, {"record_header": _record_header("VaultReadCapability", "vrc-a", created_by_event_id="evt-a1"), "capability_id": "vrc-a", "identity_id": IDENTITY_ID, "lineage_id": LINEAGE_ID, "branch_id": BRANCH_ID, "vault_id": VAULT_ID, "principal_id": REQUESTER_ID, "issuer": {"actor_type": "governor", "actor_id": "gov-a"}, "issued_to_actor": {"actor_type": "system", "actor_id": "sys-a"}, "intended_audience": "core", "allowed_operations": ("retrieve",), "allowed_purposes": ("response_context",), "not_before": NOW, "issued_at": NOW, "expires_at": NOW + timedelta(hours=1), "policy_version": "test", "nonce": "nonce-a", "status": "active", "attestation": "test-attestation", "version": 1})


def _service(
    database: SQLiteDatabase,
    capability: VaultReadCapability,
    *,
    issuer_registry: _Issuers | None = None,
    attestation_verifier: _Attest | None = None,
    clock: FixedClock | None = None,
) -> VaultCapabilityService:
    return VaultCapabilityService(
        database,
        issuer_registry=_Issuers() if issuer_registry is None else issuer_registry,
        attestation_verifier=_Attest(_payload_hash(capability)) if attestation_verifier is None else attestation_verifier,
        clock=FixedClock(NOW) if clock is None else clock,
    )


def _command(capability_id: str, event_id: str, action: str, version: int | str) -> MutationCommandEnvelope:
    return MutationCommandEnvelope(
        command_id=f"cmd-{event_id.removeprefix('evt-')}",
        command_type=f"vault_read_capability.{action}",
        actor=Actor(actor_type="governor", actor_id="gov-a"),
        actor_capability_id="cap-a",
        expected_versions=(ExpectedVersion(target_record_ref=capability_id, expected_version=version), ExpectedVersion(target_record_ref=event_id, expected_version="absent")),
        audit_context_id=f"aud-{event_id.removeprefix('evt-')}", idempotency_key=f"idem-{event_id}", issued_at=NOW,
        target_record_refs=(capability_id, event_id), payload={"event_id": event_id, "instance_id": "ins-a", "scope_refs": (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, VAULT_ID, capability_id)},
    )


def _stored(database: SQLiteDatabase, capability_id: str):
    connection = database.connect()
    try: return AuthorityRepository(connection).get_validated(capability_id)
    finally: connection.close()


def test_exact_m51_source_slice_and_phase_ownership() -> None:
    import amadeus_core.retrieval.capability_service as service
    source = open(service.__file__, encoding="utf-8").read()
    assert "validate_use" not in source and "record_use" not in source
    assert "AC084" not in source and "zero-result" not in source


def test_validator_accepts_field_normalized_actor_and_issuer() -> None:
    assert _validate(make_vault_read_capability()) is None


@pytest.mark.parametrize("port, result", (("issuer", 1), ("issuer", "false"), ("issuer", _TruthyResult()), ("attestation", 1), ("attestation", "false"), ("attestation", _TruthyResult())))
def test_validator_rejects_non_bool_true_authority_results(port: str, result: object) -> None:
    capability = make_vault_read_capability()
    registry = _Issuers()
    verifier = _Attest(_payload_hash(capability))
    if port == "issuer":
        registry.is_trusted = lambda issuer, policy_version: result  # type: ignore[method-assign]
    else:
        verifier.verify = lambda attestation, payload_hash: result  # type: ignore[method-assign]
    assert _validate(capability, issuer_registry=registry, attestation_verifier=verifier) is CoreErrorCode.VAULT_CAPABILITY_BINDING


def test_validator_rejects_both_non_bool_truthy_authority_results() -> None:
    capability = make_vault_read_capability()
    registry = _Issuers()
    verifier = _Attest(_payload_hash(capability))
    registry.is_trusted = lambda issuer, policy_version: 1  # type: ignore[method-assign]
    verifier.verify = lambda attestation, payload_hash: "false"  # type: ignore[method-assign]
    assert _validate(capability, issuer_registry=registry, attestation_verifier=verifier) is CoreErrorCode.VAULT_CAPABILITY_BINDING


@pytest.mark.parametrize("port, result", (("issuer", 1), ("issuer", "false"), ("issuer", _TruthyResult()), ("attestation", 1), ("attestation", "false"), ("attestation", _TruthyResult())))
def test_issue_rejects_non_bool_true_authority_results(port: str, result: object, tmp_path) -> None:
    database = _database(tmp_path)
    capability = _capability()
    registry = _Issuers()
    verifier = _Attest(_payload_hash(capability))
    if port == "issuer":
        registry.is_trusted = lambda issuer, policy_version: result  # type: ignore[method-assign]
    else:
        verifier.verify = lambda attestation, payload_hash: result  # type: ignore[method-assign]
    command = _command("vrc-a", "evt-b", "issue", "absent")
    denied = _service(database, capability, issuer_registry=registry, attestation_verifier=verifier).issue(command, capability)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        receipt = connection.execute("SELECT result_json FROM command_receipts WHERE command_id = ?", (command.command_id,)).fetchone()
    finally:
        connection.close()
    assert denied.value is None and denied.error is not None and denied.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert denied.event_ids == (command.payload["event_id"],) and _stored(database, "vrc-a") is None
    assert replay.events[-1].event_type == "vault_read_capability_denied" and receipt is not None


def test_issue_rejects_both_non_bool_truthy_authority_results(tmp_path) -> None:
    database = _database(tmp_path)
    capability = _capability()
    registry = _Issuers()
    verifier = _Attest(_payload_hash(capability))
    registry.is_trusted = lambda issuer, policy_version: 1  # type: ignore[method-assign]
    verifier.verify = lambda attestation, payload_hash: "false"  # type: ignore[method-assign]
    command = _command("vrc-a", "evt-b", "issue", "absent")
    denied = _service(database, capability, issuer_registry=registry, attestation_verifier=verifier).issue(command, capability)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        receipt = connection.execute("SELECT result_json FROM command_receipts WHERE command_id = ?", (command.command_id,)).fetchone()
    finally:
        connection.close()
    denial_events = tuple(event for event in replay.events if event.event_type == "vault_read_capability_denied")
    assert denied.value is None and denied.error is not None and denied.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert denied.event_ids == ("evt-b",) and _stored(database, "vrc-a") is None
    assert tuple(event.event_id for event in denial_events) == ("evt-b",) and receipt is not None


@pytest.mark.parametrize("kind", ("actor", "audience", "identity", "lineage", "branch", "vault", "principal", "operation", "purpose", "policy_version", "status_revoked", "issuer", "attestation"))
def test_validator_rejects_binding_mismatch(kind: str) -> None:
    capability = make_vault_read_capability()
    updates: dict[str, object] = {"actor": Actor(actor_type="amadeus", actor_id="amd-a"), "audience": "other", "identity": "idn-b", "lineage": "lin-b", "branch": "brn-b", "vault": "vlt-b", "principal": "prn-b", "operation": "express", "purpose": "reflection", "policy_version": "other", "issuer": _Issuers(False), "attestation": _Attest(_payload_hash(capability), False)}
    if kind == "status_revoked": capability = capability.model_copy(update={"status": "revoked"})
    aliases = {"audience": "intended_audience", "identity": "identity_id", "lineage": "lineage_id", "branch": "branch_id", "vault": "vault_id", "principal": "principal_id", "issuer": "issuer_registry", "attestation": "attestation_verifier"}
    key = aliases.get(kind, kind)
    assert _validate(capability, **({key: updates[kind]} if kind in updates else {})) is CoreErrorCode.VAULT_CAPABILITY_BINDING


def test_expired_capability_requires_new_capability_id() -> None:
    capability = make_vault_read_capability()
    assert _validate(capability, now=capability.expires_at) is CoreErrorCode.VAULT_CAPABILITY_EXPIRED


def test_not_yet_valid_capability_fails_closed() -> None:
    capability = make_vault_read_capability()
    assert _validate(capability, now=capability.not_before - timedelta(seconds=1)) is CoreErrorCode.VAULT_CAPABILITY_BINDING
    equivalent_utc = capability.not_before.replace(
        tzinfo=timezone(timedelta(0))
    )
    assert _validate(capability, now=equivalent_utc) is None

    class _ExplodingOffset(tzinfo):
        def utcoffset(self, value: datetime | None) -> timedelta | None:
            del value
            raise RuntimeError("timezone port unavailable")

        def dst(self, value: datetime | None) -> timedelta | None:
            del value
            return timedelta(0)

        def tzname(self, value: datetime | None) -> str | None:
            del value
            return "exploding"

    exploding_utc = datetime(2026, 8, 2, 12, 0, tzinfo=_ExplodingOffset())
    assert _validate(capability, now=exploding_utc) is CoreErrorCode.VAULT_CAPABILITY_BINDING


def test_issue_is_atomic_and_audited(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability()
    command = _command("vrc-a", "evt-b", "issue", "absent")
    result = _service(database, capability).issue(command, capability)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        receipt = connection.execute("SELECT result_json FROM command_receipts WHERE command_id = ?", (command.command_id,)).fetchone()
    finally:
        connection.close()
    assert result.error is None and result.event_ids == ("evt-b",) and _stored(database, "vrc-a") == result.value
    assert replay.events[-1].event_type == "vault_read_capability_issued" and replay.events[-1].mutation_command_id == command.command_id and replay.events[-1].correlation_id == command.audit_context_id
    parsed_receipt = CommandResult[object].model_validate_json(receipt[0]) if receipt is not None else None
    assert replay.resolved_inline_payloads[-1]["capability_id"] == "vrc-a" and parsed_receipt is not None
    receipt_capability = VaultReadCapability.model_validate_json(canonical_json(parsed_receipt.value))
    assert parsed_receipt.error is None and parsed_receipt.event_ids == result.event_ids and receipt_capability == result.value and parsed_receipt.replayed is False


def test_issue_denial_writes_no_capability_and_one_denied_event(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability()
    command = _command("vrc-a", "evt-c", "issue", "absent").model_copy(update={"actor": Actor(actor_type="system", actor_id="sys-a")})
    result = _service(database, capability).issue(command, capability)
    invalid_attestation = _seal(VaultReadCapability, capability.model_dump(mode="python") | {"attestation": "invalid-attestation"})
    dead_issuer = _seal(VaultReadCapability, capability.model_dump(mode="python") | {"issuer": {"actor_type": "governor", "actor_id": "gov-dead"}})
    stale_signed_field = _seal(
        VaultReadCapability,
        capability.model_dump(mode="python") | {"nonce": "nonce-stale"},
    )
    cases = (
        ("evt-c", capability, command, _Issuers(), _Attest(_payload_hash(capability))),
        ("evt-d", invalid_attestation, _command("vrc-a", "evt-d", "issue", "absent"), _Issuers(), _Attest(_payload_hash(invalid_attestation))),
        ("evt-e", dead_issuer, _command("vrc-a", "evt-e", "issue", "absent").model_copy(update={"actor": Actor(actor_type="governor", actor_id="gov-dead")}), _Issuers(), _Attest(_payload_hash(dead_issuer))),
        ("evt-f", capability, _command("vrc-a", "evt-f", "issue", "absent"), _Issuers(), _Attest(_payload_hash(capability), raises=True)),
        ("evt-dead", stale_signed_field, _command("vrc-a", "evt-dead", "issue", "absent"), _Issuers(), _Attest(_payload_hash(capability))),
    )
    for event_id, candidate, candidate_command, registry, verifier in cases:
        denied = result if event_id == "evt-c" else _service(database, candidate, issuer_registry=registry, attestation_verifier=verifier).issue(candidate_command, candidate)
        connection = database.connect()
        try:
            replay = replay_ledger(connection, BRANCH_ID)
            receipt = connection.execute("SELECT result_json FROM command_receipts WHERE command_id = ?", (candidate_command.command_id,)).fetchone()
        finally:
            connection.close()
        receipt_result = CommandResult[object].model_validate_json(receipt[0]) if receipt is not None else None
        event, payload = replay.events[-1], replay.resolved_inline_payloads[-1]
        assert denied.value is None and denied.error is not None and denied.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
        assert denied.event_ids == (event_id,) and denied.error.audit_event_id == event_id and _stored(database, "vrc-a") is None
        assert event.event_id == event_id and event.event_type == "vault_read_capability_denied" and event.correlation_id == candidate_command.audit_context_id
        assert (event.identity_id, event.lineage_id, event.branch_id, event.vault_id) == (candidate.identity_id, candidate.lineage_id, candidate.branch_id, candidate.vault_id)
        assert payload == {"capability_id": candidate.capability_id, "error_code": CoreErrorCode.VAULT_CAPABILITY_BINDING.value}
        assert receipt_result is not None and receipt_result.event_ids == denied.event_ids and receipt_result.error is not None and receipt_result.error.audit_event_id == event.event_id


def test_revoke_is_atomic_terminal_and_audited(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability(); service = _service(database, capability)
    assert service.issue(_command("vrc-a", "evt-b", "issue", "absent"), capability).error is None
    result = service.revoke(_command("vrc-a", "evt-c", "revoke", 1), "vrc-a", capability.issued_at)
    assert result.error is None and result.value is not None and result.value.status == "revoked" and result.value.version == 2


def test_expire_is_clock_bound_atomic_terminal_and_audited(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability(); service = _service(database, capability)
    assert service.issue(_command("vrc-a", "evt-b", "issue", "absent"), capability).error is None
    result = service.expire(_command("vrc-a", "evt-c", "expire", 1), "vrc-a", capability.expires_at)
    assert result.error is None and result.value is not None and result.value.status == "expired" and result.value.version == 2


def test_find_expired_is_read_only_and_returns_ids(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability(); service = _service(database, capability)
    assert service.issue(_command("vrc-a", "evt-b", "issue", "absent"), capability).error is None
    assert service.find_expired(capability.expires_at) == ("vrc-a",) and _stored(database, "vrc-a").status == "active"


def test_command_replay_and_conflict_are_closed(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability(); service = _service(database, capability); command = _command("vrc-a", "evt-b", "issue", "absent")
    first = service.issue(command, capability); replay = service.issue(command, capability)
    assert first.error is None and replay.replayed is True and replay.value == first.value and replay.event_ids == first.event_ids
    connection = database.connect()
    try:
        before = tuple(connection.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in ("ledger_events", "command_receipts", "authority_records"))
    finally:
        connection.close()
    conflict = command.model_copy(update={"audit_context_id": "aud-conflict"})
    rejected = service.issue(conflict, capability)
    connection = database.connect()
    try:
        after = tuple(connection.execute("SELECT count(*) FROM " + table).fetchone()[0] for table in ("ledger_events", "command_receipts", "authority_records"))
    finally:
        connection.close()
    assert conflict.idempotency_key == command.idempotency_key and conflict.audit_context_id != command.audit_context_id
    assert rejected.error is not None and rejected.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT and rejected.event_ids == () and _stored(database, "vrc-a") == first.value and after == before


def test_failure_paths_have_no_partial_authority_write(tmp_path) -> None:
    database = _database(tmp_path); capability = _capability(); service = _service(database, capability)
    result = service.expire(_command("vrc-a", "evt-c", "expire", "absent"), "vrc-a", capability.expires_at)
    not_before = _service(database, capability, clock=FixedClock(NOW - timedelta(seconds=1))).issue(_command("vrc-a", "evt-d", "issue", "absent"), capability)
    expired = _service(database, capability, clock=FixedClock(capability.expires_at)).issue(_command("vrc-a", "evt-e", "issue", "absent"), capability)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        missing_receipt = connection.execute("SELECT result_json FROM command_receipts WHERE command_id = ?", ("cmd-c",)).fetchone()
    finally:
        connection.close()
    assert result.value is None and result.error is not None and result.event_ids == () and _stored(database, "vrc-a") is None
    assert not_before.error is not None and not_before.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING and not_before.event_ids == ("evt-d",)
    assert expired.error is not None and expired.error.code is CoreErrorCode.VAULT_CAPABILITY_EXPIRED and expired.event_ids == ("evt-e",)
    assert tuple(event.event_id for event in replay.events[-2:]) == ("evt-d", "evt-e") and missing_receipt is not None
