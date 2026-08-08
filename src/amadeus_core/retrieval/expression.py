"""Capability-gated expression decisions over provenanced retrieval results."""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from pydantic import TypeAdapter, ValidationError

from amadeus_core.clock import Clock, FixedClock
from amadeus_core.contracts.commands import (
    Actor,
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import RecordId
from amadeus_core.contracts.errors import CoreError, CoreErrorCode, RETRYABLE_ERROR_CODES
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.views import ExpressionDecision, RetrievalRequest
from amadeus_core.contracts.vault import VaultReadCapability
from amadeus_core.ids import new_id
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError, execute_command_on_connection

from .capability_validator import AttestationVerifier, IssuerRegistry, validate_vault_read_capability
from .service import RetrievalResult


_RECORD_ID = TypeAdapter(RecordId)
_COMMAND_PAYLOAD_KEYS = frozenset(
    {
        "used_event_id",
        "denied_event_id",
        "instance_id",
        "operation",
        "input_hash",
        "expression_id",
        "scope_refs",
    }
)
_Mode = Literal["express", "summarize", "defer", "silent"]


def _core_error(
    command: object,
    code: CoreErrorCode,
    audit_event_id: str | None = None,
) -> CoreError:
    if isinstance(command, Mapping):
        candidate = command.get("audit_context_id")
    else:
        candidate = getattr(command, "audit_context_id", None)
    correlation_id = (
        candidate if isinstance(candidate, str) else "expression-structural"
    )
    return CoreError(
        error_id=new_id("error"),
        code=code,
        message=code.value,
        correlation_id=correlation_id,
        audit_event_id=audit_event_id,
        retryable=code in RETRYABLE_ERROR_CODES,
        details_ref=None,
    )


def _failure(
    command: object,
    code: CoreErrorCode,
) -> CommandResult[ExpressionDecision]:
    return CommandResult(
        value=None,
        event_ids=(),
        error=_core_error(command, code),
        replayed=False,
    )


def _is_exact_utc(value: object) -> bool:
    if type(value) is not datetime:
        return False
    try:
        return value.utcoffset() == timedelta(0)
    except Exception:
        return False


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


def _request_input_hash(request: RetrievalRequest) -> str:
    return sha256_hex(canonical_json(request.model_dump(mode="python")))


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


def _snapshot_retrieval(value: object) -> RetrievalResult | None:
    if not isinstance(value, RetrievalResult):
        return None
    try:
        snapshot = RetrievalResult.model_validate(value.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError, ValidationError):
        return None
    for item in snapshot.items:
        if type(item.score) is not float or not math.isfinite(item.score):
            return None
    return snapshot


def _command_matches(
    command: MutationCommandEnvelope,
    retrieval: RetrievalResult,
    capability_id: str,
    selected_evidence_refs: tuple[str, ...],
    requested_mode: str,
    now: datetime,
) -> bool:
    payload = command.payload
    if (
        command.command_type != "vault_read.express"
        or command.actor.actor_type not in {"governor", "system"}
        or set(payload) != _COMMAND_PAYLOAD_KEYS
        or len(payload) != len(_COMMAND_PAYLOAD_KEYS)
        or payload.get("operation") != "express"
        or payload.get("input_hash")
        != _input_hash(retrieval, capability_id, selected_evidence_refs, requested_mode, now)
    ):
        return False
    used_event_id = payload.get("used_event_id")
    denied_event_id = payload.get("denied_event_id")
    instance_id = payload.get("instance_id")
    expression_id = payload.get("expression_id")
    if (
        not all(isinstance(value, str) for value in (
            used_event_id, denied_event_id, instance_id, expression_id,
        ))
        or used_event_id == denied_event_id
    ):
        return False
    try:
        for value in (used_event_id, denied_event_id, instance_id, expression_id):
            _RECORD_ID.validate_python(value)
    except ValidationError:
        return False
    request = retrieval.request
    expected_scope = (
        request.identity_id,
        request.lineage_id,
        request.branch_id,
        request.vault_id,
        request.principal_id,
        capability_id,
        retrieval.retrieval_id,
        expression_id,
    )
    if payload.get("scope_refs") != expected_scope:
        return False
    targets = (used_event_id, denied_event_id)
    if command.target_record_refs != targets or len(command.expected_versions) != 2:
        return False
    return all(
        expected.target_record_ref == target
        and expected.expected_version == "absent"
        for expected, target in zip(command.expected_versions, targets, strict=True)
    )


def _semantic_closure_matches(
    retrieval: RetrievalResult,
    capability: VaultReadCapability,
) -> bool:
    request = retrieval.request
    if (
        retrieval.error is not None
        or retrieval.retrieval_id != request.retrieval_id
        or retrieval.queried_vault_ids != (request.vault_id,)
        or (
            request.identity_id,
            request.lineage_id,
            request.branch_id,
            request.vault_id,
            request.principal_id,
            request.capability_id,
        )
        != (
            capability.identity_id,
            capability.lineage_id,
            capability.branch_id,
            capability.vault_id,
            capability.principal_id,
            capability.capability_id,
        )
        or len(retrieval.items) > request.max_results
    ):
        return False
    refs: set[str] = set()
    for item in retrieval.items:
        if (
            item.evidence_ref in refs
            or item.vault_id != request.vault_id
            or item.state != "active"
            or item.source_watermark_seq != retrieval.source_watermark_seq
            or type(item.score) is not float
            or not math.isfinite(item.score)
        ):
            return False
        refs.add(item.evidence_ref)
    return tuple(sorted(retrieval.items, key=lambda item: (-item.score, item.evidence_ref))) == retrieval.items


def _provenance_matches(
    repository: AuthorityRepository,
    retrieval: RetrievalResult,
    capability: VaultReadCapability,
) -> bool:
    replay = repository.validated_ledger_replay(capability.branch_id)
    result_hash = sha256_hex(canonical_json(retrieval.model_dump(mode="python")))
    request_hash = _request_input_hash(retrieval.request)
    matches: list[LedgerEvent] = []
    for event, payload in zip(replay.events, replay.resolved_inline_payloads, strict=True):
        if not isinstance(payload, Mapping):
            continue
        if (
            event.event_type == "vault_read_capability_used"
            and (
                event.identity_id, event.lineage_id, event.branch_id, event.vault_id
            ) == (
                capability.identity_id, capability.lineage_id,
                capability.branch_id, capability.vault_id,
            )
            and payload.get("capability_id") == capability.capability_id
            and payload.get("operation") == "retrieve"
            and payload.get("retrieval_id") == retrieval.retrieval_id
            and payload.get("input_hash") == request_hash
            and type(payload.get("result_count")) is int
            and payload.get("result_count") == len(retrieval.items)
            and payload.get("retrieval_result_hash") == result_hash
        ):
            matches.append(event)
    return len(matches) == 1 and matches[0].ledger_seq == retrieval.source_watermark_seq + 1


def _selection_matches(
    retrieval: RetrievalResult,
    selected_evidence_refs: tuple[str, ...],
    requested_mode: str,
) -> bool:
    if requested_mode not in {"express", "summarize", "defer", "silent"}:
        return False
    try:
        for evidence_ref in selected_evidence_refs:
            _RECORD_ID.validate_python(evidence_ref)
    except (TypeError, ValidationError):
        return False
    available = {item.evidence_ref for item in retrieval.items}
    if len(set(selected_evidence_refs)) != len(selected_evidence_refs) or not set(selected_evidence_refs) <= available:
        return False
    return requested_mode in {"express", "summarize"} or not selected_evidence_refs


class ExpressionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        verifier: AttestationVerifier,
        issuer_registry: IssuerRegistry,
        clock: Clock,
    ) -> None:
        self._connection = connection
        self._verifier = verifier
        self._issuer_registry = issuer_registry
        self._clock = clock

    def decide(
        self,
        *,
        command: MutationCommandEnvelope,
        retrieval: RetrievalResult,
        capability_id: str,
        selected_evidence_refs: Sequence[str],
        requested_mode: Literal["express", "summarize", "defer", "silent"],
        now: datetime,
    ) -> CommandResult[ExpressionDecision]:
        snapshot = _snapshot_retrieval(retrieval)
        if isinstance(selected_evidence_refs, (str, bytes)) or not isinstance(
            selected_evidence_refs, Sequence
        ):
            return _failure(command, CoreErrorCode.HEADER_BODY_MISMATCH)
        try:
            selected_snapshot = tuple(selected_evidence_refs)
        except (TypeError, ValueError):
            return _failure(command, CoreErrorCode.HEADER_BODY_MISMATCH)
        try:
            command_snapshot = MutationCommandEnvelope.model_validate(command.model_dump(mode="python"))
        except (AttributeError, TypeError, ValueError, ValidationError):
            return _failure(command, CoreErrorCode.HEADER_BODY_MISMATCH)
        if (
            snapshot is None
            or not _is_exact_utc(now)
            or type(requested_mode) is not str
            or requested_mode not in {"express", "summarize", "defer", "silent"}
        ):
            return _failure(command_snapshot, CoreErrorCode.HEADER_BODY_MISMATCH)
        try:
            captured_now = self._clock.now()
        except Exception:
            return _failure(command_snapshot, CoreErrorCode.HEADER_BODY_MISMATCH)
        if not _is_exact_utc(captured_now):
            return _failure(command_snapshot, CoreErrorCode.HEADER_BODY_MISMATCH)
        if not _command_matches(
            command_snapshot, snapshot, capability_id, selected_snapshot, requested_mode, now
        ):
            return _failure(command_snapshot, CoreErrorCode.HEADER_BODY_MISMATCH)

        def handler(
            repository: AuthorityRepository,
            mutation: MutationCommandEnvelope,
            context: CommandExecutionContext,
        ) -> CommandResult[object]:
            capability = repository.get_validated(capability_id)
            if not isinstance(capability, VaultReadCapability):
                return CommandResult(
                    value=None,
                    event_ids=(),
                    error=_core_error(mutation, CoreErrorCode.VAULT_CAPABILITY_BINDING),
                    replayed=False,
                )
            if (
                mutation.actor_capability_id != capability_id
                or snapshot.request.capability_id != capability_id
            ):
                return self._denied(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, CoreErrorCode.VAULT_CAPABILITY_BINDING, captured_now)
            if now != captured_now:
                return self._denied(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, CoreErrorCode.VAULT_CAPABILITY_BINDING, captured_now)
            code = validate_vault_read_capability(
                capability,
                actor=Actor(actor_type=snapshot.request.actor.actor_type, actor_id=snapshot.request.actor.actor_id),
                intended_audience=snapshot.request.intended_audience,
                identity_id=snapshot.request.identity_id,
                lineage_id=snapshot.request.lineage_id,
                branch_id=snapshot.request.branch_id,
                vault_id=snapshot.request.vault_id,
                principal_id=snapshot.request.principal_id,
                policy_version=snapshot.request.policy_version,
                operation="express",
                purpose=snapshot.request.purpose,
                now=captured_now,
                issuer_registry=self._issuer_registry,
                attestation_verifier=self._verifier,
            )
            if code is not None:
                return self._denied(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, code, captured_now)
            head = repository.verified_ledger_head(capability.branch_id)
            if not isinstance(head, LedgerEvent):
                raise ReceiptIntegrityError("Ledger head is missing for expression branch")
            if not _semantic_closure_matches(snapshot, capability) or not _provenance_matches(repository, snapshot, capability):
                return self._denied(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, CoreErrorCode.VAULT_SCOPE_MISMATCH, captured_now, head=head)
            if not _selection_matches(snapshot, selected_snapshot, requested_mode):
                return self._denied(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, CoreErrorCode.VAULT_SCOPE_MISMATCH, captured_now, head=head)
            selected = tuple(item.evidence_ref for item in snapshot.items if item.evidence_ref in selected_snapshot)
            omitted = tuple(item.evidence_ref for item in snapshot.items if item.evidence_ref not in selected_snapshot)
            decision = ExpressionDecision(
                expression_id=cast(str, mutation.payload["expression_id"]),
                retrieval_id=snapshot.retrieval_id,
                actor=snapshot.request.actor,
                intended_audience=snapshot.request.intended_audience,
                identity_id=capability.identity_id,
                lineage_id=capability.lineage_id,
                branch_id=capability.branch_id,
                vault_id=capability.vault_id,
                principal_id=capability.principal_id,
                capability_id=capability.capability_id,
                operation="express",
                purpose=snapshot.request.purpose,
                policy_version=capability.policy_version,
                selected_evidence_refs=selected,
                omitted_evidence_refs=omitted,
                mode=requested_mode,
                reason_codes=(),
                decided_at=captured_now,
            )
            event = self._append_audit(repository, mutation, context, capability, snapshot, selected_snapshot, requested_mode, cast(str, mutation.payload["used_event_id"]), "vault_read_capability_used", len(selected), captured_now, head=head)
            return CommandResult(value=decision.model_dump(mode="json"), event_ids=(event.event_id,), error=None, replayed=False)

        raw = execute_command_on_connection(
            self._connection, command_snapshot, handler, clock=FixedClock(captured_now)
        )
        if raw.value is None:
            return cast(CommandResult[ExpressionDecision], raw)
        value = ExpressionDecision.model_validate_json(canonical_json(raw.value))
        return CommandResult(value=value, event_ids=raw.event_ids, error=raw.error, replayed=raw.replayed)

    def _denied(
        self,
        repository: AuthorityRepository,
        command: MutationCommandEnvelope,
        context: CommandExecutionContext,
        capability: VaultReadCapability,
        retrieval: RetrievalResult,
        selected_evidence_refs: tuple[str, ...],
        requested_mode: str,
        code: CoreErrorCode,
        occurred_at: datetime,
        *,
        head: LedgerEvent | None = None,
    ) -> CommandResult[object]:
        event = self._append_audit(repository, command, context, capability, retrieval, selected_evidence_refs, requested_mode, cast(str, command.payload["denied_event_id"]), "vault_read_capability_denied", 0, occurred_at, error_code=code, head=head)
        return CommandResult(value=None, event_ids=(event.event_id,), error=_core_error(command, code, event.event_id), replayed=False)

    def _append_audit(
        self,
        repository: AuthorityRepository,
        command: MutationCommandEnvelope,
        context: CommandExecutionContext,
        capability: VaultReadCapability,
        retrieval: RetrievalResult,
        selected_evidence_refs: tuple[str, ...],
        requested_mode: str,
        event_id: str,
        event_type: str,
        result_count: int,
        occurred_at: datetime,
        *,
        error_code: CoreErrorCode | None = None,
        head: LedgerEvent | None = None,
    ) -> LedgerEvent:
        if head is None:
            head = repository.verified_ledger_head(capability.branch_id)
        if not isinstance(head, LedgerEvent):
            raise ReceiptIntegrityError("Ledger head is missing for expression branch")
        payload: dict[str, object] = {
            "capability_id": capability.capability_id,
            "operation": "express",
            "input_hash": command.payload["input_hash"],
            "read_scope_hash": _read_scope_hash(retrieval.request),
            "retrieval_result_hash": sha256_hex(canonical_json(retrieval.model_dump(mode="python"))),
            "result_count": result_count,
            "retrieval_id": retrieval.retrieval_id,
            "expression_id": command.payload["expression_id"],
            "request_actor_type": retrieval.request.actor.actor_type,
            "request_actor_id": retrieval.request.actor.actor_id,
            "mode": requested_mode,
        }
        if error_code is not None:
            payload["error_code"] = error_code.value
        stored_payload = prepare_inline_payload(payload)
        event = cast(LedgerEvent, seal_record(LedgerEvent, {
            "record_header": record_header("LedgerEvent", event_id, identity_id=capability.identity_id, lineage_id=capability.lineage_id, branch_id=capability.branch_id, created_at=occurred_at, created_by_event_id=event_id, deployment_policy_ref=capability.record_header.deployment_policy_ref),
            "event_id": event_id,
            "ledger_seq": head.ledger_seq + 1,
            "identity_id": capability.identity_id,
            "lineage_id": capability.lineage_id,
            "branch_id": capability.branch_id,
            "instance_id": command.payload["instance_id"],
            "vault_id": capability.vault_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "ingested_at": command.issued_at,
            "actor_type": command.actor.actor_type,
            "actor_id": command.actor.actor_id,
            "mutation_command_id": context.command_id,
            "mutation_command_hash": context.command_hash,
            "payload_ref": stored_payload.payload_ref,
            "causation_id": None,
            "correlation_id": context.audit_context_id,
            "previous_event_hash": head.event_hash,
            "event_hash": ZERO_HASH,
            "version": 1,
        }))
        appended = repository.append_ledger_event(event.model_dump(mode="python"), payload=stored_payload)
        if not isinstance(appended, LedgerEvent):
            raise TypeError("expression audit append returned the wrong record type")
        return appended


__all__ = ["ExpressionService"]
