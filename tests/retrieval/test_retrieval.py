from __future__ import annotations

import inspect
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import (
    Actor,
    CommandExecutionContext,
    CommandResult,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.errors import CoreError, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.views import RetrievalRequest
from amadeus_core.contracts.vault import RelationshipVault, VaultReadCapability
from amadeus_core.retrieval.service import (
    Ranker,
    RetrievalItem,
    RetrievalResult,
    RetrievalService,
)
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError
from tests.governance.conftest import (
    BRANCH_ID,
    DEPLOYMENT_POLICY_REF,
    GENESIS_EVENT_ID,
    IDENTITY_ID,
    INSTANCE_ID,
    LINEAGE_ID,
    NOW,
    REQUESTER_ID,
    VAULT_ID,
    _bootstrap,
    _record_header,
    _seal,
    _seed_vault,
)


CAPABILITY_ID = "vrc-a1"
RETRIEVAL_ID = "ret-a1"
USED_EVENT_ID = "evt-b1"
DENIED_EVENT_ID = "evt-c1"
READ_AT = NOW + timedelta(minutes=1)


class _IssuerRegistry:
    def __init__(self, trusted: bool = True) -> None:
        self.trusted = trusted

    def is_trusted(self, issuer: Actor, policy_version: str) -> bool:
        return self.trusted and (
            issuer.actor_type,
            issuer.actor_id,
            policy_version,
        ) == ("governor", "gov-a1", "policy-a1")


class _AttestationVerifier:
    def __init__(self, capability: VaultReadCapability, valid: bool = True) -> None:
        self.expected_hash = sha256_hex(
            canonical_json(
                capability.model_dump(mode="python", exclude={"attestation"})
            )
        )
        self.valid = valid

    def verify(self, attestation: str, payload_hash: str) -> bool:
        return (
            self.valid
            and attestation == "attestation-a1"
            and payload_hash == self.expected_hash
        )


class _RecordingRanker:
    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self.scores = {} if scores is None else scores
        self.calls: list[tuple[tuple[RetrievalItem, ...], RetrievalRequest]] = []

    def rank(
        self,
        candidates: Sequence[RetrievalItem],
        request: RetrievalRequest,
    ) -> RetrievalResult:
        snapshot = tuple(candidates)
        self.calls.append((snapshot, request))
        return RetrievalResult(
            retrieval_id=request.retrieval_id,
            request=request,
            items=tuple(
                item.model_copy(update={"score": self.scores.get(item.evidence_ref, 1.0)})
                for item in snapshot
            ),
            queried_vault_ids=(request.vault_id,),
            source_watermark_seq=(
                0 if not snapshot else snapshot[0].source_watermark_seq
            ),
            error=None,
        )


class _NeverRanker:
    def rank(
        self,
        candidates: Sequence[RetrievalItem],
        request: RetrievalRequest,
    ) -> RetrievalResult:
        del candidates, request
        raise AssertionError("zero-candidate retrieval must not call the ranker")


class _FunctionRanker:
    def __init__(self, function) -> None:
        self.function = function

    def rank(
        self,
        candidates: Sequence[RetrievalItem],
        request: RetrievalRequest,
    ) -> RetrievalResult:
        return self.function(tuple(candidates), request)


def _capability(**updates: object) -> VaultReadCapability:
    body: dict[str, object] = {
        "record_header": _record_header(
            "VaultReadCapability",
            CAPABILITY_ID,
            created_by_event_id=GENESIS_EVENT_ID,
        ),
        "capability_id": CAPABILITY_ID,
        "identity_id": IDENTITY_ID,
        "lineage_id": LINEAGE_ID,
        "branch_id": BRANCH_ID,
        "vault_id": VAULT_ID,
        "principal_id": REQUESTER_ID,
        "issuer": {"actor_type": "governor", "actor_id": "gov-a1"},
        "issued_to_actor": {"actor_type": "system", "actor_id": "sys-a1"},
        "intended_audience": "core",
        "allowed_operations": ("retrieve",),
        "allowed_purposes": ("response_context", "reflection", "consolidation"),
        "not_before": NOW,
        "issued_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "policy_version": "policy-a1",
        "nonce": "nonce-a1",
        "status": "active",
        "attestation": "attestation-a1",
        "version": 1,
    }
    body.update(updates)
    return cast(VaultReadCapability, _seal(VaultReadCapability, body))


def _request(**updates: object) -> RetrievalRequest:
    body: dict[str, object] = {
        "retrieval_id": RETRIEVAL_ID,
        "actor": {"actor_type": "system", "actor_id": "sys-a1"},
        "intended_audience": "core",
        "identity_id": IDENTITY_ID,
        "lineage_id": LINEAGE_ID,
        "branch_id": BRANCH_ID,
        "vault_id": VAULT_ID,
        "principal_id": REQUESTER_ID,
        "capability_id": CAPABILITY_ID,
        "operation": "retrieve",
        "query_ref": "opaque:query-a1",
        "allowed_memory_states": ("active",),
        "max_results": 20,
        "purpose": "response_context",
        "policy_version": "policy-a1",
        "requested_at": READ_AT,
    }
    body.update(updates)
    return RetrievalRequest.model_validate(body)


def _command(
    request: RetrievalRequest,
    *,
    command_id: str = "cmd-b1",
    idempotency_key: str = "retrieve-a1",
    actor_capability_id: str | None = None,
) -> MutationCommandEnvelope:
    input_hash = sha256_hex(canonical_json(request.model_dump(mode="python")))
    targets = (USED_EVENT_ID, DENIED_EVENT_ID)
    return MutationCommandEnvelope(
        command_id=command_id,
        command_type="vault_read.retrieve",
        actor=Actor(actor_type="governor", actor_id="gov-a1"),
        actor_capability_id=(
            request.capability_id
            if actor_capability_id is None
            else actor_capability_id
        ),
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-b1",
        idempotency_key=idempotency_key,
        issued_at=READ_AT,
        target_record_refs=targets,
        payload={
            "used_event_id": USED_EVENT_ID,
            "denied_event_id": DENIED_EVENT_ID,
            "instance_id": INSTANCE_ID,
            "operation": "retrieve",
            "input_hash": input_hash,
            "scope_refs": (
                request.identity_id,
                request.lineage_id,
                request.branch_id,
                request.vault_id,
                request.principal_id,
                request.capability_id,
                request.retrieval_id,
            ),
        },
    )


def _memory(
    memory_id: str,
    *,
    state: str = "active",
    expression_mode: str = "eligible",
    vault_id: str = VAULT_ID,
    branch_id: str = BRANCH_ID,
) -> AutobiographicalMemory:
    header = _record_header(
        "AutobiographicalMemory",
        memory_id,
        created_by_event_id=GENESIS_EVENT_ID,
    )
    header["branch_id"] = branch_id
    return cast(
        AutobiographicalMemory,
        _seal(
            AutobiographicalMemory,
            {
                "record_header": header,
                "memory_id": memory_id,
                "identity_id": IDENTITY_ID,
                "lineage_id": LINEAGE_ID,
                "branch_id": branch_id,
                "governing_vault_id": vault_id,
                "semantic_kind": "episode",
                "state": state,
                "importance": 0.5,
                "consolidation_state": "stable",
                "expression_policy": {
                    "mode": expression_mode,
                    "reason_refs": (),
                },
                "evidence_event_refs": (GENESIS_EVENT_ID,),
                "supersedes_memory_ids": (),
                "contested_by_event_ids": (),
                "governor_decision_id": "gvd-a1",
                "semantic_version": 1,
                "created_at": NOW,
                "updated_at": NOW,
                "version": 1,
            },
        ),
    )


def _database(tmp_path, *, capability: VaultReadCapability | None = None) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "retrieval.sqlite3")
    _bootstrap(database)
    _seed_vault(database)
    if capability is not None:
        _seed_authorities(database, capability)
    return database


def _seed_authorities(database: SQLiteDatabase, *records: object) -> None:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=tuple(
                cast(str, getattr(record, "capability_id", getattr(record, "memory_id", "")))
                for record in records
            ),
        )
        for record in records:
            if isinstance(record, VaultReadCapability):
                schema_root = "vault_read_capability"
            elif isinstance(record, AutobiographicalMemory):
                schema_root = "autobiographical_memory"
            else:
                raise TypeError(type(record).__name__)
            repository.save_authoritative(
                schema_root,
                record.model_dump(mode="python"),
            )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _append_event(
    database: SQLiteDatabase,
    event_id: str,
    *,
    event_type: str = "conversation_message_recorded",
    vault_id: str | None = VAULT_ID,
) -> LedgerEvent:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        context = CommandExecutionContext(
            command_id="cmd-d1",
            command_hash="d" * 64,
            audit_context_id="aud-d1",
        )
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(event_id,),
            execution_context=context,
        )
        head = repository.verified_ledger_head(BRANCH_ID)
        payload = prepare_inline_payload({"session_id": "session:a1"})
        event = cast(
            LedgerEvent,
            seal_record(
                LedgerEvent,
                {
                    "record_header": record_header(
                        "LedgerEvent",
                        event_id,
                        identity_id=IDENTITY_ID,
                        lineage_id=LINEAGE_ID,
                        branch_id=BRANCH_ID,
                        created_at=NOW,
                        created_by_event_id=event_id,
                        deployment_policy_ref=DEPLOYMENT_POLICY_REF,
                    ),
                    "event_id": event_id,
                    "ledger_seq": 1 if head is None else head.ledger_seq + 1,
                    "identity_id": IDENTITY_ID,
                    "lineage_id": LINEAGE_ID,
                    "branch_id": BRANCH_ID,
                    "instance_id": INSTANCE_ID,
                    "vault_id": vault_id,
                    "event_type": event_type,
                    "occurred_at": NOW,
                    "ingested_at": NOW,
                    "actor_type": "system",
                    "actor_id": "sys-a1",
                    "mutation_command_id": context.command_id,
                    "mutation_command_hash": context.command_hash,
                    "payload_ref": payload.payload_ref,
                    "causation_id": None,
                    "correlation_id": (
                        "session:a1"
                        if event_type == "conversation_message_recorded"
                        else context.audit_context_id
                    ),
                    "previous_event_hash": None if head is None else head.event_hash,
                    "event_hash": ZERO_HASH,
                    "version": 1,
                },
            ),
        )
        repository.append_ledger_event(event.model_dump(mode="python"), payload=payload)
        connection.commit()
        return event
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _service(
    connection,
    capability: VaultReadCapability,
    ranker: Ranker,
    *,
    trusted: bool = True,
    attested: bool = True,
) -> RetrievalService:
    return RetrievalService(
        connection,
        _AttestationVerifier(capability, attested),
        _IssuerRegistry(trusted),
        ranker,
        FixedClock(READ_AT),
    )


def _read_scope_hash(request: RetrievalRequest) -> str:
    return sha256_hex(
        canonical_json(
            {
                "actor": request.actor.model_dump(mode="python"),
                "intended_audience": request.intended_audience,
                "identity_id": request.identity_id,
                "lineage_id": request.lineage_id,
                "branch_id": request.branch_id,
                "vault_id": request.vault_id,
                "principal_id": request.principal_id,
                "purpose": request.purpose,
                "policy_version": request.policy_version,
            }
        )
    )


def _set_vault(
    database: SQLiteDatabase,
    *,
    status: str = "active",
    principal_id: str = REQUESTER_ID,
) -> RelationshipVault:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(VAULT_ID,),
        )
        current = repository.get_validated(VAULT_ID)
        assert isinstance(current, RelationshipVault)
        updated = cast(
            RelationshipVault,
            reseal_update(
                current,
                {
                    "status": status,
                    "relationship_principal_id": principal_id,
                    "version": current.version + 1,
                },
            ),
        )
        stored = repository.save_authoritative(
            "relationship_vault",
            updated.model_dump(mode="python"),
        )
        connection.commit()
        assert isinstance(stored, RelationshipVault)
        return stored
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def test_retrieval_contracts_have_exact_fields() -> None:
    assert tuple(RetrievalItem.model_fields) == (
        "evidence_ref",
        "vault_id",
        "state",
        "source_watermark_seq",
        "score",
    )
    assert tuple(RetrievalResult.model_fields) == (
        "retrieval_id",
        "request",
        "items",
        "queried_vault_ids",
        "source_watermark_seq",
        "error",
    )
    assert Ranker is not None
    assert RetrievalService is not None


def test_retrieval_interfaces_have_exact_signatures_and_are_frozen() -> None:
    assert tuple(inspect.signature(RetrievalService.__init__).parameters) == (
        "self",
        "connection",
        "verifier",
        "issuer_registry",
        "ranker",
        "clock",
    )
    assert tuple(inspect.signature(RetrievalService.retrieve).parameters) == (
        "self",
        "command",
        "request",
    )
    assert tuple(inspect.signature(Ranker.rank).parameters) == (
        "self",
        "candidates",
        "request",
    )
    repository_parameters = tuple(
        inspect.signature(AuthorityRepository.validated_vault_candidates).parameters
    )
    assert repository_parameters == (
        "self",
        "identity_id",
        "lineage_id",
        "branch_id",
        "vault_id",
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in inspect.signature(RetrievalService.__init__).parameters.values()
    )
    item = RetrievalItem(
        evidence_ref="mem-a1",
        vault_id=VAULT_ID,
        state="active",
        source_watermark_seq=0,
        score=0.0,
    )
    assert item.model_config["extra"] == "forbid"
    assert item.model_config["frozen"] is True
    assert item.model_config["strict"] is True
    result = RetrievalResult(
        retrieval_id=RETRIEVAL_ID,
        request=_request(),
        items=(item,),
        queried_vault_ids=(VAULT_ID,),
        source_watermark_seq=0,
        error=None,
    )
    assert result.model_config["extra"] == "forbid"
    assert result.model_config["frozen"] is True
    assert result.model_config["strict"] is True
    for invalid in (-1, True):
        with pytest.raises(ValidationError):
            RetrievalItem.model_validate(
                item.model_dump(mode="python") | {"source_watermark_seq": invalid}
            )
        with pytest.raises(ValidationError):
            RetrievalResult.model_validate(
                result.model_dump(mode="python") | {"source_watermark_seq": invalid}
            )


def test_repository_returns_validated_exact_scope_candidates_in_frozen_order(tmp_path) -> None:
    database = _database(tmp_path)
    _seed_authorities(
        database,
        _memory("mem-b1"),
        _memory("mem-a1"),
        _memory("mem-c1", vault_id="vlt-b1"),
        _memory("mem-d1", branch_id="brn-b1"),
    )
    first_event = _append_event(database, "evt-d1")
    _append_event(database, "evt-e1", vault_id="vlt-b1")
    second_event = _append_event(database, "evt-f1")
    connection = database.connect()
    try:
        candidates = AuthorityRepository(connection).validated_vault_candidates(
            IDENTITY_ID,
            LINEAGE_ID,
            BRANCH_ID,
            VAULT_ID,
        )
    finally:
        connection.close()
    assert tuple(type(candidate) for candidate in candidates) == (
        AutobiographicalMemory,
        AutobiographicalMemory,
        LedgerEvent,
        LedgerEvent,
    )
    assert tuple(
        candidate.memory_id if isinstance(candidate, AutobiographicalMemory) else candidate.event_id
        for candidate in candidates
    ) == ("mem-a1", "mem-b1", first_event.event_id, second_event.event_id)


def test_repository_candidate_read_fails_closed_on_ledger_tamper(tmp_path) -> None:
    database = _database(tmp_path)
    _append_event(database, "evt-d1")
    connection = database.connect()
    try:
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            "UPDATE ledger_events SET event_hash = ? WHERE event_id = ?",
            ("f" * 64, "evt-d1"),
        )
        with pytest.raises(ReceiptIntegrityError):
            AuthorityRepository(connection).validated_vault_candidates(
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
            )
    finally:
        connection.close()


def test_success_prefilters_current_vault_and_writes_exact_used_audit(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(
        database,
        _memory("mem-a1"),
        _memory("mem-b1", expression_mode="restricted"),
        _memory("mem-c1", expression_mode="non_mention"),
        _memory("mem-d1", expression_mode="silent"),
        _memory("mem-e1", state="archived"),
        _memory("mem-f1", vault_id="vlt-b1"),
    )
    conversation = _append_event(database, "evt-d1")
    _append_event(database, "evt-e1", event_type="memory_created")
    request = _request(query_ref="' OR 1=1 --")
    command = _command(request)
    ranker = _RecordingRanker({"mem-a1": 2.0, conversation.event_id: 1.0})
    connection = database.connect()
    try:
        before = AuthorityRepository(connection).get_validated(CAPABILITY_ID)
        result = _service(connection, capability, ranker).retrieve(command, request)
        after = AuthorityRepository(connection).get_validated(CAPABILITY_ID)
        replay = replay_ledger(connection, BRANCH_ID)
        receipt_count = connection.execute(
            "SELECT count(*) FROM command_receipts WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert result.error is None
    assert result.value is not None
    assert result.event_ids == (USED_EVENT_ID,)
    assert result.value.retrieval_id == request.retrieval_id
    assert result.value.request == request
    assert result.value.queried_vault_ids == (VAULT_ID,)
    assert tuple(item.evidence_ref for item in result.value.items) == (
        "mem-a1",
        conversation.event_id,
    )
    assert len(ranker.calls) == 1
    seen, seen_request = ranker.calls[0]
    assert seen_request.query_ref == "' OR 1=1 --"
    assert tuple(item.evidence_ref for item in seen) == ("mem-a1", conversation.event_id)
    assert all(item.vault_id == VAULT_ID and item.state == "active" for item in seen)
    assert all(item.score == 0.0 for item in seen)
    assert all(
        item.source_watermark_seq == result.value.source_watermark_seq
        for item in seen
    )
    assert before == after == capability
    assert receipt_count == 1
    event = replay.events[-1]
    payload = replay.resolved_inline_payloads[-1]
    assert event.event_type == "vault_read_capability_used"
    assert event.event_id == USED_EVENT_ID
    assert event.occurred_at == READ_AT
    assert event.ingested_at == command.issued_at
    assert (event.identity_id, event.lineage_id, event.branch_id, event.vault_id) == (
        capability.identity_id,
        capability.lineage_id,
        capability.branch_id,
        capability.vault_id,
    )
    assert payload == {
        "capability_id": CAPABILITY_ID,
        "operation": "retrieve",
        "input_hash": command.payload["input_hash"],
        "read_scope_hash": _read_scope_hash(request),
        "retrieval_result_hash": sha256_hex(
            canonical_json(result.value.model_dump(mode="python"))
        ),
        "result_count": 2,
        "retrieval_id": RETRIEVAL_ID,
        "request_actor_type": "system",
        "request_actor_id": "sys-a1",
    }


def test_zero_candidates_skips_ranker_and_succeeds_at_current_watermark(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    request = _request()
    connection = database.connect()
    try:
        result = _service(connection, capability, _NeverRanker()).retrieve(
            _command(request), request
        )
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert result.error is None and result.value is not None
    assert result.value.items == ()
    assert result.value.queried_vault_ids == (VAULT_ID,)
    assert result.value.source_watermark_seq == 1
    assert replay.events[-1].event_type == "vault_read_capability_used"
    assert replay.resolved_inline_payloads[-1]["result_count"] == 0


def test_missing_ledger_head_raises_integrity_error_without_partial_write(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    request = _request()
    command = _command(request)
    connection = database.connect()
    try:
        connection.execute("DROP TRIGGER ledger_events_reject_delete")
        connection.execute("DROP TRIGGER authority_ledger_reject_delete")
        connection.execute("DELETE FROM ledger_events")
        connection.execute(
            "DELETE FROM authority_records WHERE record_type = 'LedgerEvent'"
        )
        with pytest.raises(ReceiptIntegrityError, match="Ledger head is missing"):
            _service(connection, capability, _NeverRanker()).retrieve(
                command,
                request,
            )
        assert connection.execute(
            "SELECT count(*) FROM ledger_events"
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT count(*)
            FROM authority_records
            WHERE record_id IN (?, ?)
            """,
            (USED_EVENT_ID, DENIED_EVENT_ID),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM command_receipts WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_consolidation_excludes_ledger_events_before_ranker(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(database, _memory("mem-a1"))
    _append_event(database, "evt-d1")
    request = _request(purpose="consolidation")
    ranker = _RecordingRanker()
    connection = database.connect()
    try:
        result = _service(connection, capability, ranker).retrieve(
            _command(request), request
        )
    finally:
        connection.close()
    assert result.error is None
    assert len(ranker.calls) == 1
    assert tuple(item.evidence_ref for item in ranker.calls[0][0]) == ("mem-a1",)


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    (
        ("expired", CoreErrorCode.VAULT_CAPABILITY_EXPIRED),
        ("actor", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("audience", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("purpose", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("policy", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("operation", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("attestation", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("issuer", CoreErrorCode.VAULT_CAPABILITY_BINDING),
    ),
)
def test_existing_capability_refusals_write_one_denial(
    tmp_path, kind: str, expected_code: CoreErrorCode
) -> None:
    capability_updates: dict[str, object] = {}
    request_updates: dict[str, object] = {}
    trusted = True
    attested = True
    if kind == "expired":
        capability_updates["expires_at"] = READ_AT
    elif kind == "actor":
        request_updates["actor"] = {"actor_type": "amadeus", "actor_id": "amd-a1"}
    elif kind == "audience":
        request_updates["intended_audience"] = "other"
    elif kind == "purpose":
        capability_updates["allowed_purposes"] = ("reflection",)
    elif kind == "policy":
        request_updates["policy_version"] = "policy-b1"
    elif kind == "operation":
        capability_updates["allowed_operations"] = ("express",)
    elif kind == "attestation":
        attested = False
    elif kind == "issuer":
        trusted = False
    capability = _capability(**capability_updates)
    database = _database(tmp_path, capability=capability)
    request = _request(**request_updates)
    connection = database.connect()
    try:
        result = _service(
            connection,
            capability,
            _NeverRanker(),
            trusted=trusted,
            attested=attested,
        ).retrieve(_command(request), request)
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert result.value is None
    assert result.error is not None and result.error.code is expected_code
    assert result.event_ids == (DENIED_EVENT_ID,)
    assert result.error.audit_event_id == DENIED_EVENT_ID
    assert replay.events[-1].event_type == "vault_read_capability_denied"
    assert replay.resolved_inline_payloads[-1] == {
        "capability_id": CAPABILITY_ID,
        "operation": "retrieve",
        "input_hash": _command(request).payload["input_hash"],
        "read_scope_hash": _read_scope_hash(request),
        "result_count": 0,
        "retrieval_id": RETRIEVAL_ID,
        "request_actor_type": request.actor.actor_type,
        "request_actor_id": request.actor.actor_id,
        "error_code": expected_code.value,
    }


def test_cross_vault_actor_capability_and_vault_state_fail_closed(tmp_path) -> None:
    cases = (
        ("cross-vault", _request(vault_id="vlt-b1"), None, CoreErrorCode.CROSS_VAULT_READ_FORBIDDEN),
        ("actor-capability", _request(), "vrc-b1", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("sealed", _request(), None, CoreErrorCode.INVALID_VAULT_TRANSITION),
        ("principal", _request(), None, CoreErrorCode.VAULT_CAPABILITY_BINDING),
    )
    for index, (kind, request, actor_capability_id, expected) in enumerate(cases):
        case_path = tmp_path / f"case-{index}"
        case_path.mkdir()
        capability = _capability()
        database = _database(case_path, capability=capability)
        if kind == "sealed":
            _set_vault(database, status="sealed")
        elif kind == "principal":
            _set_vault(database, principal_id="usr-b1")
        connection = database.connect()
        try:
            result = _service(connection, capability, _NeverRanker()).retrieve(
                _command(request, actor_capability_id=actor_capability_id),
                request,
            )
            replay = replay_ledger(connection, BRANCH_ID)
        finally:
            connection.close()
        assert result.error is not None and result.error.code is expected
        assert result.event_ids == (DENIED_EVENT_ID,)
        assert replay.events[-1].vault_id == capability.vault_id


def test_missing_capability_persists_unaudited_failure_receipt(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path)
    request = _request()
    command = _command(request)
    connection = database.connect()
    try:
        service = _service(connection, capability, _NeverRanker())
        first = service.retrieve(command, request)
        replayed = service.retrieve(command, request)
        ledger = replay_ledger(connection, BRANCH_ID)
        receipt_count = connection.execute(
            "SELECT count(*) FROM command_receipts WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert first.value is None and first.event_ids == ()
    assert first.error is not None
    assert first.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert first.error.audit_event_id is None
    assert replayed.replayed is True and replayed.error == first.error
    assert tuple(event.event_id for event in ledger.events) == (GENESIS_EVENT_ID,)
    assert receipt_count == 1


@pytest.mark.parametrize(
    "kind",
    (
        "exception",
        "error",
        "forged-ref",
        "wrong-vault",
        "wrong-state",
        "wrong-watermark",
        "duplicate",
        "nan",
        "inf",
        "wrong-request",
        "wrong-retrieval",
        "wrong-queried-vaults",
    ),
)
def test_malicious_or_failed_ranker_is_audited_scope_denial(tmp_path, kind: str) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(database, _memory("mem-a1"))
    request = _request()

    def malicious(
        candidates: tuple[RetrievalItem, ...],
        candidate_request: RetrievalRequest,
    ) -> RetrievalResult:
        item = candidates[0]
        if kind == "exception":
            raise RuntimeError("ranker unavailable")
        error = None
        items = (item.model_copy(update={"score": 1.0}),)
        retrieval_id = candidate_request.retrieval_id
        result_request = candidate_request
        queried = (candidate_request.vault_id,)
        watermark = item.source_watermark_seq
        if kind == "error":
            error = CoreError(
                error_id="err-a1",
                code=CoreErrorCode.VAULT_SCOPE_MISMATCH,
                message=CoreErrorCode.VAULT_SCOPE_MISMATCH.value,
                correlation_id="aud-ranker",
                audit_event_id=None,
                retryable=False,
                details_ref=None,
            )
        elif kind == "forged-ref":
            items = (item.model_copy(update={"evidence_ref": "mem-f1"}),)
        elif kind == "wrong-vault":
            items = (item.model_copy(update={"vault_id": "vlt-b1"}),)
        elif kind == "wrong-state":
            items = (item.model_copy(update={"state": "archived"}),)
        elif kind == "wrong-watermark":
            items = (item.model_copy(update={"source_watermark_seq": watermark + 1}),)
        elif kind == "duplicate":
            items = (items[0], items[0])
        elif kind in {"nan", "inf"}:
            bad_item = RetrievalItem.model_construct(
                evidence_ref=item.evidence_ref,
                vault_id=item.vault_id,
                state=item.state,
                source_watermark_seq=item.source_watermark_seq,
                score=float(kind),
            )
            return RetrievalResult.model_construct(
                retrieval_id=retrieval_id,
                request=result_request,
                items=(bad_item,),
                queried_vault_ids=queried,
                source_watermark_seq=watermark,
                error=None,
            )
        elif kind == "wrong-request":
            result_request = _request(query_ref="opaque:forged")
        elif kind == "wrong-retrieval":
            retrieval_id = "ret-b1"
        elif kind == "wrong-queried-vaults":
            queried = (candidate_request.vault_id, "vlt-b1")
        return RetrievalResult(
            retrieval_id=retrieval_id,
            request=result_request,
            items=items,
            queried_vault_ids=queried,
            source_watermark_seq=watermark,
            error=error,
        )

    connection = database.connect()
    try:
        result = _service(
            connection, capability, _FunctionRanker(malicious)
        ).retrieve(_command(request), request)
        ledger = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert result.value is None
    assert result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_SCOPE_MISMATCH
    assert result.event_ids == (DENIED_EVENT_ID,)
    assert ledger.events[-1].event_type == "vault_read_capability_denied"
    assert ledger.resolved_inline_payloads[-1]["error_code"] == (
        CoreErrorCode.VAULT_SCOPE_MISMATCH.value
    )
    assert all(event.event_id != USED_EVENT_ID for event in ledger.events)


def test_final_sort_tie_break_and_max_results_are_service_owned(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(
        database,
        _memory("mem-a1"),
        _memory("mem-b1"),
        _memory("mem-c1"),
    )
    event = _append_event(database, "evt-d1")
    request = _request(max_results=2)
    ranker = _RecordingRanker(
        {
            "mem-a1": 2.0,
            "mem-b1": 2.0,
            "mem-c1": 3.0,
            event.event_id: 4.0,
        }
    )
    connection = database.connect()
    try:
        result = _service(connection, capability, ranker).retrieve(
            _command(request), request
        )
    finally:
        connection.close()
    assert result.error is None and result.value is not None
    assert tuple(item.evidence_ref for item in result.value.items) == (
        event.event_id,
        "mem-c1",
    )


def test_equal_scores_sort_by_evidence_ref_ascending(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(database, _memory("mem-b1"), _memory("mem-a1"))
    request = _request(max_results=2)
    connection = database.connect()
    try:
        result = _service(connection, capability, _RecordingRanker()).retrieve(
            _command(request), request
        )
    finally:
        connection.close()
    assert result.value is not None
    assert tuple(item.evidence_ref for item in result.value.items) == (
        "mem-a1",
        "mem-b1",
    )


@pytest.mark.parametrize(
    "kind",
    (
        "command-type",
        "command-actor",
        "payload-extra",
        "payload-operation",
        "input-hash",
        "scope-order",
        "same-events",
        "targets",
        "expected-version",
    ),
)
def test_malformed_command_contract_is_unaudited_and_does_not_execute(
    tmp_path, kind: str
) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    request = _request()
    command = _command(request)
    update: dict[str, object] = {}
    if kind == "command-type":
        update["command_type"] = "vault_read.express"
    elif kind == "command-actor":
        update["actor"] = Actor(actor_type="llm", actor_id="llm-a1")
    elif kind in {"payload-extra", "payload-operation", "input-hash", "scope-order", "same-events"}:
        payload = dict(command.payload)
        if kind == "payload-extra":
            payload["query_ref"] = request.query_ref
        elif kind == "payload-operation":
            payload["operation"] = "express"
        elif kind == "input-hash":
            payload["input_hash"] = "0" * 64
        elif kind == "scope-order":
            payload["scope_refs"] = tuple(reversed(cast(tuple[str, ...], payload["scope_refs"])))
        else:
            payload["denied_event_id"] = USED_EVENT_ID
        update["payload"] = payload
    elif kind == "targets":
        update["target_record_refs"] = (USED_EVENT_ID,)
        update["expected_versions"] = (
            ExpectedVersion(target_record_ref=USED_EVENT_ID, expected_version="absent"),
        )
    elif kind == "expected-version":
        update["expected_versions"] = (
            ExpectedVersion(target_record_ref=USED_EVENT_ID, expected_version=0),
            ExpectedVersion(target_record_ref=DENIED_EVENT_ID, expected_version="absent"),
        )
    malformed = command.model_copy(update=update)
    connection = database.connect()
    try:
        result = _service(connection, capability, _NeverRanker()).retrieve(
            malformed, request
        )
        ledger = replay_ledger(connection, BRANCH_ID)
        receipt_count = connection.execute(
            "SELECT count(*) FROM command_receipts WHERE command_id = ?",
            (malformed.command_id,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert result.value is None and result.event_ids == ()
    assert result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.error.audit_event_id is None
    assert tuple(event.event_id for event in ledger.events) == (GENESIS_EVENT_ID,)
    assert receipt_count == 0


def test_replay_conflict_and_receipt_preserve_single_audit_event(tmp_path) -> None:
    capability = _capability()
    database = _database(tmp_path, capability=capability)
    _seed_authorities(database, _memory("mem-a1"))
    request = _request()
    command = _command(request)
    connection = database.connect()
    try:
        service = _service(connection, capability, _RecordingRanker())
        first = service.retrieve(command, request)
        replayed = service.retrieve(command, request)
        before_conflict = replay_ledger(connection, BRANCH_ID)
        conflict = service.retrieve(
            command.model_copy(update={"audit_context_id": "aud-f1"}),
            request,
        )
        after_conflict = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert first.error is None and first.value is not None
    assert replayed.replayed is True
    assert replayed.value == first.value and replayed.event_ids == first.event_ids
    assert conflict.value is None and conflict.event_ids == ()
    assert conflict.error is not None
    assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
    assert tuple(event.event_id for event in before_conflict.events) == tuple(
        event.event_id for event in after_conflict.events
    )
    assert sum(event.event_id == USED_EVENT_ID for event in after_conflict.events) == 1


def test_service_contains_no_direct_sql_or_expression_view_builder_scope() -> None:
    import amadeus_core.retrieval.service as service_module

    source = open(service_module.__file__, encoding="utf-8").read()
    assert ".execute(" not in source
    assert "SELECT " not in source
    assert "query_ref" not in source
    assert "SourceSnapshot" not in source
    assert "ExpressionDecision" not in source
    assert "ViewBuilder" not in source
