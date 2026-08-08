from __future__ import annotations

import importlib
import inspect
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal, cast, get_type_hints

import pytest
from pydantic import TypeAdapter

from amadeus_core.clock import FixedClock
from amadeus_core.contracts.commands import Actor, CommandExecutionContext, ExpectedVersion, MutationCommandEnvelope
from amadeus_core.contracts.common import RecordId
from amadeus_core.contracts.errors import CoreError, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.vault import VaultReadCapability
from amadeus_core.contracts.views import ExpressionDecision
from amadeus_core.retrieval.service import RetrievalResult
from amadeus_core.storage.ledger import replay_ledger
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, reseal_update, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError
from tests.governance.conftest import BRANCH_ID, DEPLOYMENT_POLICY_REF, IDENTITY_ID, INSTANCE_ID, LINEAGE_ID, REQUESTER_ID, VAULT_ID
from tests.retrieval.test_retrieval import (
    CAPABILITY_ID,
    READ_AT,
    RETRIEVAL_ID,
    _AttestationVerifier,
    _IssuerRegistry,
    _NeverRanker,
    _RecordingRanker,
    _capability,
    _command as _retrieval_command,
    _database,
    _request,
    _seed_authorities,
    _memory,
    _service as _retrieval_service,
)


EXPRESSION_ID = "exp-a1"
USED_EVENT_ID = "evt-b2"
DENIED_EVENT_ID = "evt-c2"


def _expression_service_type():
    return importlib.import_module("amadeus_core.retrieval.expression").ExpressionService


def _state_counts(database) -> tuple[int, int]:
    connection = database.connect()
    try:
        return (
            connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0],
            connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0],
        )
    finally:
        connection.close()


class _ValueClock:
    def __init__(self, value: object) -> None:
        self._value = value
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return cast(datetime, self._value)


class _RaisingClock:
    def __init__(self) -> None:
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        raise RuntimeError("clock unavailable")


def test_expression_red_fixtures_use_valid_ids_and_integrity_valid_mutations(tmp_path) -> None:
    adapter = TypeAdapter(RecordId)
    for identifier in (USED_EVENT_ID, DENIED_EVENT_ID, EXPRESSION_ID, INSTANCE_ID):
        assert adapter.validate_python(identifier) == identifier
    database, capability, retrieval = _successful_retrieval(tmp_path)
    duplicate = _append_matching_retrieval_used(database, retrieval, "evt-e2")
    replacement = _replace_capability(database, policy_version="policy-b1")
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert duplicate.event_id == "evt-e2"
    assert replay.events[-1] == duplicate
    assert replacement.version == capability.version + 1


def _input_hash(
    retrieval: RetrievalResult,
    capability_id: str,
    selected_evidence_refs: tuple[str, ...],
    requested_mode: str,
    now: datetime,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "retrieval": retrieval.model_dump(mode="python"),
                "capability_id": capability_id,
                "selected_evidence_refs": selected_evidence_refs,
                "requested_mode": requested_mode,
                "now": now,
            }
        )
    )


def _command(
    retrieval: RetrievalResult,
    *,
    capability_id: str = CAPABILITY_ID,
    selected_evidence_refs: tuple[str, ...] = (),
    requested_mode: Literal["express", "summarize", "defer", "silent"] = "express",
    now: datetime = READ_AT,
    command_id: str = "cmd-b2",
    idempotency_key: str = "express-a1",
    actor_capability_id: str | None = None,
) -> MutationCommandEnvelope:
    targets = (USED_EVENT_ID, DENIED_EVENT_ID)
    return MutationCommandEnvelope(
        command_id=command_id,
        command_type="vault_read.express",
        actor=Actor(actor_type="governor", actor_id="gov-a1"),
        actor_capability_id=(
            capability_id if actor_capability_id is None else actor_capability_id
        ),
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-u2",
        idempotency_key=idempotency_key,
        issued_at=READ_AT,
        target_record_refs=targets,
        payload={
            "used_event_id": USED_EVENT_ID,
            "denied_event_id": DENIED_EVENT_ID,
            "instance_id": INSTANCE_ID,
            "operation": "express",
            "input_hash": _input_hash(
                retrieval,
                capability_id,
                selected_evidence_refs,
                requested_mode,
                now,
            ),
            "expression_id": EXPRESSION_ID,
            "scope_refs": (
                retrieval.request.identity_id,
                retrieval.request.lineage_id,
                retrieval.request.branch_id,
                retrieval.request.vault_id,
                retrieval.request.principal_id,
                capability_id,
                retrieval.retrieval_id,
                EXPRESSION_ID,
            ),
        },
    )


def _successful_retrieval(
    tmp_path,
    *,
    operation: tuple[str, ...] = ("retrieve", "express"),
    memory_ids: tuple[str, ...] = ("mem-a1",),
):
    capability = _capability(allowed_operations=operation)
    database = _database(tmp_path, capability=capability)
    _seed_authorities(database, *(_memory(memory_id) for memory_id in memory_ids))
    request = _request()
    connection = database.connect()
    try:
        result = _retrieval_service(
            connection,
            capability,
            _RecordingRanker({memory_id: 1.0 for memory_id in memory_ids}),
        ).retrieve(_retrieval_command(request), request)
    finally:
        connection.close()
    assert result.error is None and result.value is not None
    return database, capability, result.value


def _replace_capability(
    database,
    **updates: object,
) -> VaultReadCapability:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection, allowed_target_refs=(CAPABILITY_ID,)
        )
        current = repository.get_validated(CAPABILITY_ID)
        assert isinstance(current, VaultReadCapability)
        replacement = cast(
            VaultReadCapability,
            reseal_update(
                current,
                updates | {"version": current.version + 1},
            ),
        )
        stored = repository.save_authoritative(
            "vault_read_capability", replacement.model_dump(mode="python")
        )
        connection.commit()
        assert isinstance(stored, VaultReadCapability)
        return stored
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _retrieval_used_payload(retrieval: RetrievalResult) -> dict[str, object]:
    request = retrieval.request
    return {
        "capability_id": request.capability_id,
        "operation": "retrieve",
        "input_hash": sha256_hex(canonical_json(request.model_dump(mode="python"))),
        "read_scope_hash": sha256_hex(canonical_json({
            "actor": request.actor.model_dump(mode="python"),
            "intended_audience": request.intended_audience,
            "identity_id": request.identity_id,
            "lineage_id": request.lineage_id,
            "branch_id": request.branch_id,
            "vault_id": request.vault_id,
            "principal_id": request.principal_id,
            "purpose": request.purpose,
            "policy_version": request.policy_version,
        })),
        "retrieval_result_hash": sha256_hex(
            canonical_json(retrieval.model_dump(mode="python"))
        ),
        "result_count": len(retrieval.items),
        "retrieval_id": retrieval.retrieval_id,
        "request_actor_type": request.actor.actor_type,
        "request_actor_id": request.actor.actor_id,
    }


def _append_matching_retrieval_used(
    database,
    retrieval: RetrievalResult,
    event_id: str,
    *,
    payload_updates: dict[str, object] | None = None,
) -> LedgerEvent:
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        context = CommandExecutionContext(
            command_id="cmd-a2",
            command_hash="a" * 64,
            audit_context_id="aud-provenance-a1",
        )
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=(event_id,),
            execution_context=context,
        )
        head = repository.verified_ledger_head(BRANCH_ID)
        assert head is not None
        payload = prepare_inline_payload(
            _retrieval_used_payload(retrieval) | (payload_updates or {})
        )
        event = cast(LedgerEvent, seal_record(LedgerEvent, {
            "record_header": record_header("LedgerEvent", event_id, identity_id=IDENTITY_ID, lineage_id=LINEAGE_ID, branch_id=BRANCH_ID, created_at=READ_AT, created_by_event_id=event_id, deployment_policy_ref=DEPLOYMENT_POLICY_REF),
            "event_id": event_id, "ledger_seq": head.ledger_seq + 1,
            "identity_id": IDENTITY_ID, "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID, "instance_id": INSTANCE_ID,
            "vault_id": VAULT_ID, "event_type": "vault_read_capability_used",
            "occurred_at": READ_AT, "ingested_at": READ_AT,
            "actor_type": "governor", "actor_id": "gov-a1",
            "mutation_command_id": context.command_id,
            "mutation_command_hash": context.command_hash,
            "payload_ref": payload.payload_ref, "causation_id": None,
            "correlation_id": context.audit_context_id,
            "previous_event_hash": head.event_hash,
            "event_hash": ZERO_HASH, "version": 1,
        }))
        repository.append_ledger_event(
            event.model_dump(mode="python"), payload=payload
        )
        connection.commit()
        return event
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _decide(
    database,
    capability,
    retrieval: RetrievalResult,
    *,
    selected: tuple[str, ...] = (),
    mode: Literal["express", "summarize", "defer", "silent"] = "express",
    now: datetime = READ_AT,
    capability_id: str = CAPABILITY_ID,
    verifier=None,
    issuer_registry=None,
    clock=None,
    actor_capability_id: str | None = None,
    command: MutationCommandEnvelope | None = None,
):
    service_type = _expression_service_type()
    connection = database.connect()
    try:
        return service_type(
            connection,
            _AttestationVerifier(capability) if verifier is None else verifier,
            _IssuerRegistry() if issuer_registry is None else issuer_registry,
            FixedClock(READ_AT) if clock is None else clock,
        ).decide(
            command=(
                _command(
                    retrieval,
                    capability_id=capability_id,
                    selected_evidence_refs=selected,
                    requested_mode=mode,
                    now=now,
                    actor_capability_id=actor_capability_id,
                )
                if command is None else command
            ),
            retrieval=retrieval,
            capability_id=capability_id,
            selected_evidence_refs=selected,
            requested_mode=mode,
            now=now,
        )
    finally:
        connection.close()


def test_expression_interface_and_decision_shape_are_frozen() -> None:
    service_type = _expression_service_type()
    source = inspect.getsource(importlib.import_module("amadeus_core.retrieval.expression"))
    assert tuple(inspect.signature(service_type.__init__).parameters) == (
        "self", "connection", "verifier", "issuer_registry", "clock",
    )
    assert tuple(inspect.signature(service_type.decide).parameters) == (
        "self", "command", "retrieval", "capability_id",
        "selected_evidence_refs", "requested_mode", "now",
    )
    signature = inspect.signature(service_type.decide)
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for name, parameter in signature.parameters.items()
        if name != "self"
    )
    assert get_type_hints(service_type.decide)["selected_evidence_refs"] == Sequence[str]
    assert tuple(ExpressionDecision.model_fields) == (
        "expression_id", "retrieval_id", "actor", "intended_audience",
        "identity_id", "lineage_id", "branch_id", "vault_id", "principal_id",
        "capability_id", "operation", "purpose", "policy_version",
        "selected_evidence_refs", "omitted_evidence_refs", "mode", "reason_codes",
        "decided_at",
    )
    assert "ViewBuilder" not in source
    assert "connection.execute(" not in source


@pytest.mark.parametrize(
    ("mode", "selected"),
    (
        ("express", ()),
        ("express", ("mem-b1", "mem-a1")),
        ("express", ("mem-b1",)),
        ("summarize", ()),
        ("summarize", ("mem-b1", "mem-a1")),
        ("defer", ()),
        ("silent", ()),
    ),
)
def test_expression_modes_are_provenanced_and_audited(tmp_path, mode: str, selected: tuple[str, ...]) -> None:
    database, capability, retrieval = _successful_retrieval(
        tmp_path, memory_ids=("mem-a1", "mem-b1")
    )
    command = _command(
        retrieval,
        selected_evidence_refs=selected,
        requested_mode=mode,
    )
    clock = _ValueClock(READ_AT)
    result = _decide(
        database, capability, retrieval, selected=selected, mode=mode,
        command=command, clock=clock,
    )
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert result.error is None and result.value is not None
    assert result.value.mode == mode and result.value.reason_codes == ()
    assert result.value.decided_at == READ_AT and clock.calls == 1
    assert result.value.selected_evidence_refs == tuple(
        item.evidence_ref for item in retrieval.items if item.evidence_ref in selected
    )
    assert result.value.omitted_evidence_refs == tuple(
        item.evidence_ref for item in retrieval.items if item.evidence_ref not in selected
    )
    assert result.value.operation == "express" and not hasattr(result.value, "text")
    assert replay.events[-1].event_type == "vault_read_capability_used"
    assert replay.events[-1].occurred_at == READ_AT
    assert (
        replay.events[-1].identity_id,
        replay.events[-1].lineage_id,
        replay.events[-1].branch_id,
        replay.events[-1].vault_id,
        replay.events[-1].actor_type,
        replay.events[-1].actor_id,
    ) == (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, VAULT_ID, "governor", "gov-a1")
    payload = replay.resolved_inline_payloads[-1]
    assert {
        "capability_id", "operation", "input_hash", "read_scope_hash",
        "retrieval_result_hash", "result_count", "retrieval_id", "expression_id",
        "request_actor_type", "request_actor_id", "mode",
    } <= set(payload)
    assert payload["capability_id"] == CAPABILITY_ID
    assert payload["input_hash"] == command.payload["input_hash"]
    assert payload["read_scope_hash"] == _retrieval_used_payload(retrieval)["read_scope_hash"]
    assert payload["operation"] == "express" and payload["mode"] == mode
    assert payload["retrieval_id"] == RETRIEVAL_ID
    assert payload["expression_id"] == EXPRESSION_ID
    assert payload["retrieval_result_hash"] == sha256_hex(
        canonical_json(retrieval.model_dump(mode="python"))
    )
    assert payload["result_count"] == len(selected)
    assert payload["request_actor_type"] == retrieval.request.actor.actor_type
    assert payload["request_actor_id"] == retrieval.request.actor.actor_id
    assert not {"text", "query_ref", "selected_evidence_refs"} & set(payload)


@pytest.mark.parametrize(
    "selected,mode,expected",
    [
        (("mem-a1",), "silent", CoreErrorCode.VAULT_SCOPE_MISMATCH),
        (("mem-a1",), "defer", CoreErrorCode.VAULT_SCOPE_MISMATCH),
        (("mem-a1", "mem-a1"), "express", CoreErrorCode.VAULT_SCOPE_MISMATCH),
        (("mem-b1",), "express", CoreErrorCode.VAULT_SCOPE_MISMATCH),
        (("not-a-record-id",), "express", CoreErrorCode.VAULT_SCOPE_MISMATCH),
    ],
)
def test_expression_rejects_invalid_selection_without_candidate_text(tmp_path, selected, mode, expected) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    result = _decide(database, capability, retrieval, selected=selected, mode=mode)
    assert result.value is None and result.error is not None and result.error.code is expected
    assert not hasattr(result.value, "text")


@pytest.mark.parametrize("invalid_mode", ("mem-a1", "opaque:query-a1"))
def test_expression_invalid_mode_is_pre_uow_unaudited_failure(tmp_path, invalid_mode: str) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    command = _command(
        retrieval,
        requested_mode=cast(Literal["express", "summarize", "defer", "silent"], invalid_mode),
    )
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        retrieval,
        mode=cast(Literal["express", "summarize", "defer", "silent"], invalid_mode),
        command=command,
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


@pytest.mark.parametrize(
    "kind",
    (
        "missing", "duplicate", "hash", "request", "watermark",
        "foreign_item", "too_many", "wrong_order",
    ),
)
def test_expression_rejects_forged_or_unprovenanced_retrieval(tmp_path, kind: str) -> None:
    database, capability, retrieval = _successful_retrieval(
        tmp_path, memory_ids=("mem-a1", "mem-b1")
    )
    if kind == "missing":
        request = _request(retrieval_id="ret-b1")
        retrieval = retrieval.model_copy(update={"retrieval_id": "ret-b1", "request": request})
    elif kind == "duplicate":
        _append_matching_retrieval_used(database, retrieval, "evt-e2")
    elif kind == "hash":
        retrieval = retrieval.model_copy(update={
            "items": (retrieval.items[0].model_copy(update={"score": 2.0}), retrieval.items[1]),
        })
    elif kind == "request":
        # query_ref is outside the fresh-capability scope, so this reaches
        # retrieval provenance rather than failing an earlier binding check.
        retrieval = retrieval.model_copy(update={"request": _request(query_ref="opaque:other")})
    elif kind == "watermark":
        retrieval = retrieval.model_copy(update={"source_watermark_seq": retrieval.source_watermark_seq + 1})
    elif kind == "foreign_item":
        retrieval = retrieval.model_copy(update={"items": (retrieval.items[0].model_copy(update={"vault_id": "vlt-b1"}),)})
    elif kind == "too_many":
        items = tuple(
            item.model_copy(update={"evidence_ref": f"mem-{index:02x}"})
            for index, item in enumerate(retrieval.items * 11)
        )
        object.__setattr__(retrieval, "items", items)
    else:
        retrieval = retrieval.model_copy(update={"items": tuple(reversed(retrieval.items))})
    result = _decide(database, capability, retrieval)
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_SCOPE_MISMATCH


@pytest.mark.parametrize("forged_count", (True, "1"))
def test_expression_rejects_provenance_result_count_type_confusion(tmp_path, forged_count) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    request = _request(retrieval_id="ret-b1")
    forged = retrieval.model_copy(update={
        "retrieval_id": "ret-b1",
        "request": request,
        "source_watermark_seq": retrieval.source_watermark_seq + 1,
        "items": tuple(
            item.model_copy(update={
                "source_watermark_seq": retrieval.source_watermark_seq + 1,
            })
            for item in retrieval.items
        ),
    })
    _append_matching_retrieval_used(
        database,
        forged,
        "evt-e2",
        payload_updates={"result_count": forged_count},
    )
    result = _decide(database, capability, forged)
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_SCOPE_MISMATCH
    assert result.event_ids == (DENIED_EVENT_ID,)


@pytest.mark.parametrize(
    "kind",
    (
        "error", "retrieval_id", "request", "queried_vault", "state",
        "item_watermark", "duplicate_ref", "too_many", "score_descending",
        "score_tie_break",
    ),
)
def test_expression_revalidates_retrieval_semantic_closure_before_provenance(tmp_path, kind: str) -> None:
    memory_ids = (
        tuple(f"mem-{index:02x}" for index in range(21))
        if kind == "too_many" else ("mem-a1", "mem-b1")
    )
    database, capability, retrieval = _successful_retrieval(
        tmp_path, memory_ids=memory_ids
    )
    if kind == "error":
        retrieval = retrieval.model_copy(update={"error": CoreError(
            error_id="err-a1", code=CoreErrorCode.VAULT_SCOPE_MISMATCH,
            message="forged", correlation_id="aud-u2", audit_event_id=None,
            retryable=False, details_ref=None,
        )})
    elif kind == "retrieval_id":
        retrieval = retrieval.model_copy(update={"retrieval_id": "ret-b1"})
    elif kind == "request":
        # This field is deliberately outside capability binding, isolating
        # result/request closure from the earlier capability gate.
        retrieval = retrieval.model_copy(update={"request": _request(query_ref="opaque:other")})
    elif kind == "queried_vault":
        retrieval = retrieval.model_copy(update={"queried_vault_ids": ("vlt-b1",)})
    elif kind == "state":
        retrieval = retrieval.model_copy(update={"items": (
            retrieval.items[0].model_copy(update={"state": "archived"}),
            *retrieval.items[1:],
        )})
    elif kind == "item_watermark":
        retrieval = retrieval.model_copy(update={"items": (
            retrieval.items[0].model_copy(update={
                "source_watermark_seq": retrieval.items[0].source_watermark_seq + 1,
            }),
            *retrieval.items[1:],
        )})
    elif kind == "duplicate_ref":
        retrieval = retrieval.model_copy(update={"items": (
            retrieval.items[0],
            retrieval.items[1].model_copy(update={"evidence_ref": retrieval.items[0].evidence_ref}),
        )})
    elif kind == "too_many":
        retrieval = retrieval.model_copy(update={"items": (
            *retrieval.items,
            retrieval.items[0].model_copy(update={"evidence_ref": "mem-14"}),
        )})
    elif kind == "score_descending":
        retrieval = retrieval.model_copy(update={"items": (
            retrieval.items[0].model_copy(update={"score": 1.0}),
            retrieval.items[1].model_copy(update={"score": 2.0}),
        )})
    else:
        retrieval = retrieval.model_copy(update={"items": tuple(reversed(retrieval.items))})
    _append_matching_retrieval_used(database, retrieval, "evt-e2")
    result = _decide(database, capability, retrieval)
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_SCOPE_MISMATCH


@pytest.mark.parametrize("score", (float("nan"), float("inf"), float("-inf")))
def test_expression_nonfinite_result_is_pre_uow_header_failure(tmp_path, score: float) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    command = _command(retrieval)
    object.__setattr__(retrieval.items[0], "score", score)
    before_counts = _state_counts(database)
    service_type = _expression_service_type()
    connection = database.connect()
    try:
        result = service_type(connection, _AttestationVerifier(capability), _IssuerRegistry(), FixedClock(READ_AT)).decide(
            command=command,
            retrieval=retrieval,
            capability_id=CAPABILITY_ID,
            selected_evidence_refs=(),
            requested_mode="express",
            now=READ_AT,
        )
    finally:
        connection.close()
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


@pytest.mark.parametrize(
    "supplied_now",
    (
        datetime(2026, 8, 2, 12, 1),
        datetime(2026, 8, 2, 20, 1, tzinfo=timezone(timedelta(hours=8))),
        cast(datetime, "not-a-datetime"),
    ),
)
def test_expression_invalid_supplied_now_is_pre_uow_header_failure(tmp_path, supplied_now) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        retrieval,
        now=supplied_now,
        command=_command(retrieval, now=READ_AT),
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


@pytest.mark.parametrize(
    "clock",
    (
        _ValueClock(datetime(2026, 8, 2, 12, 1)),
        _ValueClock("not-a-datetime"),
        _ValueClock(datetime(2026, 8, 2, 20, 1, tzinfo=timezone(timedelta(hours=8)))),
        _RaisingClock(),
    ),
)
def test_expression_malformed_clock_fails_pre_uow_without_audit(tmp_path, clock) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    before_counts = _state_counts(database)
    result = _decide(database, capability, retrieval, clock=clock)
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts
    if isinstance(clock, _ValueClock):
        assert clock.calls == 1
    else:
        assert clock.calls == 1


def test_expression_now_clock_mismatch_denies_once_at_captured_clock_time(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    trusted_now = READ_AT + timedelta(seconds=1)
    clock = _ValueClock(trusted_now)
    before_counts = _state_counts(database)
    result = _decide(database, capability, retrieval, clock=clock)
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert result.event_ids == (DENIED_EVENT_ID,) and clock.calls == 1
    assert replay.events[-1].event_type == "vault_read_capability_denied"
    assert replay.events[-1].occurred_at == trusted_now
    assert _state_counts(database) == (before_counts[0] + 1, before_counts[1] + 1)


@pytest.mark.parametrize(
    ("kind", "expected"),
    (
        ("operation", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("expired", CoreErrorCode.VAULT_CAPABILITY_EXPIRED),
        ("not_before", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("revoked", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("attestation", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("issuer", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("policy", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("actor", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("audience", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("identity", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("lineage", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("branch", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("vault", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("principal", CoreErrorCode.VAULT_CAPABILITY_BINDING),
        ("purpose", CoreErrorCode.VAULT_CAPABILITY_BINDING),
    ),
)
def test_expression_existing_capability_failures_write_exactly_one_denial(tmp_path, kind: str, expected) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    verifier = None
    clock = None
    issuer_registry = None
    if kind == "operation":
        capability = _replace_capability(database, allowed_operations=("retrieve",))
    elif kind == "expired":
        capability = _replace_capability(database, expires_at=READ_AT)
    elif kind == "not_before":
        capability = _replace_capability(database, not_before=READ_AT + timedelta(seconds=1))
    elif kind == "revoked":
        capability = _replace_capability(database, status="revoked")
    elif kind == "attestation":
        verifier = _AttestationVerifier(capability, valid=False)
    elif kind == "issuer":
        issuer_registry = _IssuerRegistry(trusted=False)
    elif kind == "policy":
        capability = _replace_capability(database, policy_version="policy-b1")
    elif kind == "actor":
        capability = _replace_capability(database, issued_to_actor={"actor_type": "llm", "actor_id": "llm-a1"})
    elif kind == "audience":
        capability = _replace_capability(database, intended_audience="other")
    elif kind == "principal":
        capability = _replace_capability(database, principal_id="usr-b1")
    elif kind == "purpose":
        capability = _replace_capability(database, allowed_purposes=("reflection",))
    elif kind in {"identity", "lineage", "branch", "vault"}:
        request_updates = {f"{kind}_id": f"{kind[:3]}-b1"}
        retrieval = retrieval.model_copy(update={"request": _request(**request_updates)})
    now = READ_AT
    if kind != "attestation":
        verifier = _AttestationVerifier(capability)
    command = _command(retrieval)
    before_counts = _state_counts(database)
    result = _decide(
        database, capability, retrieval, now=now, verifier=verifier,
        issuer_registry=issuer_registry, clock=clock, command=command,
    )
    assert result.value is None and result.error is not None and result.error.code is expected
    assert result.event_ids == (DENIED_EVENT_ID,)
    assert result.error.audit_event_id == DENIED_EVENT_ID
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
    finally:
        connection.close()
    event, payload = replay.events[-1], replay.resolved_inline_payloads[-1]
    assert event.event_type == "vault_read_capability_denied"
    assert (
        event.identity_id, event.lineage_id, event.branch_id, event.vault_id,
        event.actor_type, event.actor_id, event.occurred_at,
    ) == (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, VAULT_ID, "governor", "gov-a1", READ_AT)
    assert {"capability_id", "operation", "input_hash", "read_scope_hash", "retrieval_result_hash", "result_count", "retrieval_id", "expression_id", "request_actor_type", "request_actor_id", "mode", "error_code"} <= set(payload)
    assert payload["capability_id"] == CAPABILITY_ID
    assert payload["operation"] == "express" and payload["result_count"] == 0
    assert payload["input_hash"] == command.payload["input_hash"]
    assert payload["read_scope_hash"] == _retrieval_used_payload(retrieval)["read_scope_hash"]
    assert payload["retrieval_result_hash"] == sha256_hex(canonical_json(retrieval.model_dump(mode="python")))
    assert payload["retrieval_id"] == retrieval.retrieval_id
    assert payload["expression_id"] == EXPRESSION_ID
    assert payload["request_actor_type"] == retrieval.request.actor.actor_type
    assert payload["request_actor_id"] == retrieval.request.actor.actor_id
    assert payload["mode"] == "express" and payload["error_code"] == expected.value
    assert "text" not in payload
    assert _state_counts(database) == (before_counts[0] + 1, before_counts[1] + 1)
    connection = database.connect()
    try:
        stored = AuthorityRepository(connection).get_validated(CAPABILITY_ID)
    finally:
        connection.close()
    assert stored == capability


@pytest.mark.parametrize("mismatch", ("actor_capability", "retrieval_request"))
def test_expression_three_capability_ids_mismatch_is_existing_capability_denial(tmp_path, mismatch: str) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    actor_capability_id = None
    if mismatch == "actor_capability":
        actor_capability_id = "vrc-b1"
    else:
        retrieval = retrieval.model_copy(update={
            "request": _request(capability_id="vrc-b1"),
        })
    result = _decide(
        database,
        capability,
        retrieval,
        actor_capability_id=actor_capability_id,
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert result.event_ids == (DENIED_EVENT_ID,)


def test_expression_missing_ledger_head_raises_without_partial_write(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    connection = database.connect()
    try:
        connection.execute("DROP TRIGGER ledger_events_reject_delete")
        connection.execute("DROP TRIGGER authority_ledger_reject_delete")
        connection.execute("DELETE FROM ledger_events")
        connection.execute("DELETE FROM authority_records WHERE record_type = 'LedgerEvent'")
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS ledger_events_reject_delete\n"
            "BEFORE DELETE ON ledger_events\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS authority_ledger_reject_delete\n"
            "BEFORE DELETE ON authority_records\n"
            "WHEN OLD.record_type = 'LedgerEvent'\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'ledger is append-only');\n"
            "END;"
        )
        connection.commit()
    finally:
        connection.close()
    before_counts = _state_counts(database)
    with pytest.raises(ReceiptIntegrityError, match="Ledger head is missing"):
        _decide(database, capability, retrieval)
    assert _state_counts(database) == before_counts


def test_expression_missing_capability_has_receipt_and_no_fabricated_event(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    missing_request = _request(capability_id="vrc-b1")
    missing_retrieval = retrieval.model_copy(update={
        "request": missing_request,
        "source_watermark_seq": retrieval.source_watermark_seq + 1,
    })
    _append_matching_retrieval_used(database, missing_retrieval, "evt-e2")
    result = _decide(
        database, capability, missing_retrieval, capability_id="vrc-b1"
    )
    connection = database.connect()
    try:
        replay = replay_ledger(connection, BRANCH_ID)
        receipt = connection.execute(
            "SELECT result_json FROM command_receipts WHERE command_id = ?", ("cmd-b2",)
        ).fetchone()
    finally:
        connection.close()
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert result.event_ids == () and receipt is not None
    assert all(event.event_id != DENIED_EVENT_ID for event in replay.events)


def test_expression_missing_explicit_capability_beats_existing_other_capability_ids(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    command = _command(
        retrieval,
        capability_id="vrc-b1",
        actor_capability_id=CAPABILITY_ID,
    )
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        retrieval,
        capability_id="vrc-b1",
        actor_capability_id=CAPABILITY_ID,
        command=command,
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert result.event_ids == ()
    assert _state_counts(database) == (before_counts[0], before_counts[1] + 1)


def test_expression_missing_capability_beats_valid_now_clock_mismatch(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    missing_retrieval = retrieval.model_copy(update={
        "request": _request(capability_id="vrc-b1"),
        "source_watermark_seq": retrieval.source_watermark_seq + 1,
    })
    _append_matching_retrieval_used(database, missing_retrieval, "evt-e2")
    clock = _ValueClock(READ_AT + timedelta(seconds=1))
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        missing_retrieval,
        capability_id="vrc-b1",
        clock=clock,
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.VAULT_CAPABILITY_BINDING
    assert result.event_ids == () and clock.calls == 1
    assert _state_counts(database) == (before_counts[0], before_counts[1] + 1)


@pytest.mark.parametrize(
    "kind",
    (
        "command_type", "actor", "payload_keys", "input_hash", "operation",
        "used_event_id", "denied_event_id", "instance_id", "expression_id",
        "scope_refs", "target_order", "target_duplicate", "expected_version",
    ),
)
def test_expression_structural_command_failures_are_unaudited(tmp_path, kind: str) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    command = _command(retrieval)
    before_counts = _state_counts(database)
    payload = dict(command.payload)
    if kind == "command_type":
        command = command.model_copy(update={"command_type": "vault_read.retrieve"})
    elif kind == "actor":
        command = command.model_copy(update={"actor": Actor(actor_type="user", actor_id="usr-a1")})
    elif kind == "payload_keys":
        command = command.model_copy(update={"payload": payload | {"unexpected": "x"}})
    elif kind == "input_hash":
        command = command.model_copy(update={"payload": payload | {"input_hash": "0" * 64}})
    elif kind == "operation":
        command = command.model_copy(update={"payload": payload | {"operation": "retrieve"}})
    elif kind == "used_event_id":
        command = command.model_copy(update={"payload": payload | {"used_event_id": "bad"}})
    elif kind == "denied_event_id":
        command = command.model_copy(update={"payload": payload | {"denied_event_id": "bad"}})
    elif kind == "instance_id":
        command = command.model_copy(update={"payload": payload | {"instance_id": "bad"}})
    elif kind == "expression_id":
        command = command.model_copy(update={"payload": payload | {"expression_id": "bad"}})
    elif kind == "scope_refs":
        command = command.model_copy(update={"payload": payload | {"scope_refs": payload["scope_refs"][:-1]}})
    elif kind == "target_order":
        command = command.model_copy(update={"target_record_refs": tuple(reversed(command.target_record_refs))})
    elif kind == "target_duplicate":
        command = command.model_copy(update={"target_record_refs": (USED_EVENT_ID, USED_EVENT_ID)})
    else:
        command = command.model_copy(update={"expected_versions": (
            ExpectedVersion(target_record_ref=USED_EVENT_ID, expected_version=1),
            ExpectedVersion(target_record_ref=DENIED_EVENT_ID, expected_version="absent"),
        )})
    result = _decide(database, capability, retrieval, command=command)
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


def test_expression_non_result_input_is_pre_uow_header_failure(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        cast(RetrievalResult, object()),
        command=_command(retrieval),
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


def test_expression_non_command_input_is_pre_uow_header_failure(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    before_counts = _state_counts(database)
    result = _decide(
        database,
        capability,
        retrieval,
        command=cast(MutationCommandEnvelope, object()),
    )
    assert result.value is None and result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == () and _state_counts(database) == before_counts


def test_expression_append_failure_rolls_back_event_and_receipt(tmp_path, monkeypatch) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    before_counts = _state_counts(database)
    original_append = AuthorityRepository.append_ledger_event

    def append_then_fail(repository, *args, **kwargs):
        original_append(repository, *args, **kwargs)
        raise RuntimeError("forced append failure")

    monkeypatch.setattr(AuthorityRepository, "append_ledger_event", append_then_fail)
    with pytest.raises(RuntimeError, match="forced append failure"):
        _decide(database, capability, retrieval)
    assert _state_counts(database) == before_counts


def test_expression_replay_conflict_and_failure_do_not_mutate_capability(tmp_path) -> None:
    database, capability, retrieval = _successful_retrieval(tmp_path)
    first = _decide(database, capability, retrieval)
    replay = _decide(database, capability, retrieval)
    assert first.error is None and replay.replayed is True and replay.event_ids == first.event_ids
    assert replay.value == first.value
    before_conflict_counts = _state_counts(database)
    conflict = _command(retrieval).model_copy(update={"audit_context_id": "aud-conflict"})
    rejected = _decide(database, capability, retrieval, command=conflict)
    assert rejected.value is None and rejected.error is not None
    assert rejected.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
    assert rejected.event_ids == ()
    assert _state_counts(database) == before_conflict_counts
    connection = database.connect()
    try:
        stored = AuthorityRepository(connection).get_validated(CAPABILITY_ID)
    finally:
        connection.close()
    assert stored == capability
