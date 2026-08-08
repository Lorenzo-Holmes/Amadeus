"""Capability-gated retrieval over validated authority and Ledger evidence."""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Annotated, Protocol, cast

from pydantic import Field, TypeAdapter, ValidationError

from amadeus_core.clock import Clock
from amadeus_core.contracts.commands import (
    Actor,
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import FrozenModel, RecordId
from amadeus_core.contracts.errors import (
    CoreError,
    CoreErrorCode,
    RETRYABLE_ERROR_CODES,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.views import RetrievalRequest
from amadeus_core.contracts.vault import RelationshipVault, VaultReadCapability
from amadeus_core.ids import new_id
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import (
    ReceiptIntegrityError,
    execute_command_on_connection,
)

from .capability_validator import (
    AttestationVerifier,
    IssuerRegistry,
    validate_vault_read_capability,
)


_NonnegativeSeq = Annotated[int, Field(strict=True, ge=0)]
_RECORD_ID = TypeAdapter(RecordId)
_COMMAND_PAYLOAD_KEYS = frozenset(
    {
        "used_event_id",
        "denied_event_id",
        "instance_id",
        "operation",
        "input_hash",
        "scope_refs",
    }
)


class RetrievalItem(FrozenModel):
    evidence_ref: RecordId
    vault_id: RecordId
    state: str
    source_watermark_seq: _NonnegativeSeq
    score: float


class RetrievalResult(FrozenModel):
    retrieval_id: RecordId
    request: RetrievalRequest
    items: tuple[RetrievalItem, ...]
    queried_vault_ids: tuple[RecordId, ...]
    source_watermark_seq: _NonnegativeSeq
    error: CoreError | None


class Ranker(Protocol):
    def rank(
        self,
        candidates: Sequence[RetrievalItem],
        request: RetrievalRequest,
    ) -> RetrievalResult: ...


class _RankerViolation(ValueError):
    pass


def _core_error(
    command: MutationCommandEnvelope,
    code: CoreErrorCode,
    audit_event_id: str | None = None,
) -> CoreError:
    return CoreError(
        error_id=new_id("error"),
        code=code,
        message=code.value,
        correlation_id=command.audit_context_id,
        audit_event_id=audit_event_id,
        retryable=code in RETRYABLE_ERROR_CODES,
        details_ref=None,
    )


def _failure(
    command: MutationCommandEnvelope,
    code: CoreErrorCode,
) -> CommandResult[RetrievalResult]:
    return CommandResult[RetrievalResult](
        value=None,
        event_ids=(),
        error=_core_error(command, code),
        replayed=False,
    )


def _request_input_hash(request: RetrievalRequest) -> str:
    return sha256_hex(canonical_json(request.model_dump(mode="python")))


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


def _command_contract_matches(
    command: MutationCommandEnvelope,
    request: RetrievalRequest,
) -> bool:
    payload = command.payload
    if (
        command.command_type != "vault_read.retrieve"
        or command.actor.actor_type not in {"governor", "system"}
        or len(payload) != len(_COMMAND_PAYLOAD_KEYS)
        or set(payload) != _COMMAND_PAYLOAD_KEYS
        or payload.get("operation") != "retrieve"
        or payload.get("input_hash") != _request_input_hash(request)
    ):
        return False
    used_event_id = payload.get("used_event_id")
    denied_event_id = payload.get("denied_event_id")
    instance_id = payload.get("instance_id")
    if (
        not isinstance(used_event_id, str)
        or not isinstance(denied_event_id, str)
        or not isinstance(instance_id, str)
        or used_event_id == denied_event_id
    ):
        return False
    try:
        _RECORD_ID.validate_python(command.command_id)
        _RECORD_ID.validate_python(command.actor.actor_id)
        _RECORD_ID.validate_python(used_event_id)
        _RECORD_ID.validate_python(denied_event_id)
        _RECORD_ID.validate_python(instance_id)
    except ValidationError:
        return False
    expected_scope = (
        request.identity_id,
        request.lineage_id,
        request.branch_id,
        request.vault_id,
        request.principal_id,
        request.capability_id,
        request.retrieval_id,
    )
    if payload.get("scope_refs") != expected_scope:
        return False
    expected_targets = (used_event_id, denied_event_id)
    if command.target_record_refs != expected_targets:
        return False
    if len(command.expected_versions) != 2:
        return False
    return all(
        expected.target_record_ref == target
        and expected.expected_version == "absent"
        for expected, target in zip(
            command.expected_versions,
            expected_targets,
            strict=True,
        )
    )


def _candidate_items(
    candidates: Sequence[AutobiographicalMemory | LedgerEvent],
    request: RetrievalRequest,
    source_watermark_seq: int,
) -> tuple[RetrievalItem, ...]:
    items: list[RetrievalItem] = []
    for candidate in candidates:
        if isinstance(candidate, AutobiographicalMemory):
            if (
                candidate.state != "active"
                or candidate.state not in request.allowed_memory_states
                or candidate.expression_policy.mode != "eligible"
            ):
                continue
            evidence_ref = candidate.memory_id
            state = candidate.state
        elif isinstance(candidate, LedgerEvent):
            if (
                request.purpose == "consolidation"
                or candidate.event_type != "conversation_message_recorded"
            ):
                continue
            evidence_ref = candidate.event_id
            state = "active"
        else:
            continue
        items.append(
            RetrievalItem(
                evidence_ref=evidence_ref,
                vault_id=request.vault_id,
                state=state,
                source_watermark_seq=source_watermark_seq,
                score=0.0,
            )
        )
    return tuple(items)


def _validated_ranking(
    ranked: object,
    candidates: tuple[RetrievalItem, ...],
    request: RetrievalRequest,
    source_watermark_seq: int,
) -> RetrievalResult:
    if not isinstance(ranked, RetrievalResult):
        raise _RankerViolation("ranker returned the wrong result type")
    try:
        snapshot = RetrievalResult.model_validate(
            ranked.model_dump(mode="python")
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise _RankerViolation("ranker returned an invalid result") from error
    if (
        snapshot.error is not None
        or snapshot.retrieval_id != request.retrieval_id
        or snapshot.request != request
        or snapshot.queried_vault_ids != (request.vault_id,)
        or snapshot.source_watermark_seq != source_watermark_seq
    ):
        raise _RankerViolation("ranker changed the retrieval envelope")

    candidates_by_ref = {item.evidence_ref: item for item in candidates}
    if len(candidates_by_ref) != len(candidates):
        raise _RankerViolation("candidate evidence references are not unique")
    selected_refs: set[str] = set()
    selected: list[RetrievalItem] = []
    for item in snapshot.items:
        original = candidates_by_ref.get(item.evidence_ref)
        if original is None or item.evidence_ref in selected_refs:
            raise _RankerViolation("ranker selected forged or duplicate evidence")
        if (
            item.vault_id != original.vault_id
            or item.state != original.state
            or item.source_watermark_seq != original.source_watermark_seq
            or type(item.score) is not float
            or not math.isfinite(item.score)
        ):
            raise _RankerViolation("ranker changed protected item metadata")
        selected_refs.add(item.evidence_ref)
        selected.append(item)
    selected.sort(key=lambda item: (-item.score, item.evidence_ref))
    return RetrievalResult(
        retrieval_id=request.retrieval_id,
        request=request,
        items=tuple(selected[: request.max_results]),
        queried_vault_ids=(request.vault_id,),
        source_watermark_seq=source_watermark_seq,
        error=None,
    )


class RetrievalService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        verifier: AttestationVerifier,
        issuer_registry: IssuerRegistry,
        ranker: Ranker,
        clock: Clock,
    ) -> None:
        self._connection = connection
        self._verifier = verifier
        self._issuer_registry = issuer_registry
        self._ranker = ranker
        self._clock = clock

    def retrieve(
        self,
        command: MutationCommandEnvelope,
        request: RetrievalRequest,
    ) -> CommandResult[RetrievalResult]:
        try:
            request_snapshot = RetrievalRequest.model_validate(
                request.model_dump(mode="python")
            )
            command_snapshot = MutationCommandEnvelope.model_validate(
                command.model_dump(mode="python")
            )
        except (AttributeError, TypeError, ValueError, ValidationError):
            return _failure(command, CoreErrorCode.HEADER_BODY_MISMATCH)
        if not _command_contract_matches(command_snapshot, request_snapshot):
            return _failure(command_snapshot, CoreErrorCode.HEADER_BODY_MISMATCH)

        def handler(
            repository: AuthorityRepository,
            mutation: MutationCommandEnvelope,
            context: CommandExecutionContext,
        ) -> CommandResult[object]:
            capability = repository.get_validated(request_snapshot.capability_id)
            if not isinstance(capability, VaultReadCapability):
                return CommandResult[object](
                    value=None,
                    event_ids=(),
                    error=_core_error(
                        mutation,
                        CoreErrorCode.VAULT_CAPABILITY_BINDING,
                    ),
                    replayed=False,
                )

            now = self._clock.now()
            if mutation.actor_capability_id != request_snapshot.capability_id:
                return self._denied(
                    repository,
                    mutation,
                    context,
                    capability,
                    request_snapshot,
                    CoreErrorCode.VAULT_CAPABILITY_BINDING,
                    now,
                )
            if request_snapshot.vault_id != capability.vault_id:
                return self._denied(
                    repository,
                    mutation,
                    context,
                    capability,
                    request_snapshot,
                    CoreErrorCode.CROSS_VAULT_READ_FORBIDDEN,
                    now,
                )
            code = validate_vault_read_capability(
                capability,
                actor=Actor(
                    actor_type=request_snapshot.actor.actor_type,
                    actor_id=request_snapshot.actor.actor_id,
                ),
                intended_audience=request_snapshot.intended_audience,
                identity_id=request_snapshot.identity_id,
                lineage_id=request_snapshot.lineage_id,
                branch_id=request_snapshot.branch_id,
                vault_id=request_snapshot.vault_id,
                principal_id=request_snapshot.principal_id,
                policy_version=request_snapshot.policy_version,
                operation="retrieve",
                purpose=request_snapshot.purpose,
                now=now,
                issuer_registry=self._issuer_registry,
                attestation_verifier=self._verifier,
            )
            if code is not None:
                return self._denied(
                    repository,
                    mutation,
                    context,
                    capability,
                    request_snapshot,
                    code,
                    now,
                )

            vault = repository.get_validated(capability.vault_id)
            if not isinstance(vault, RelationshipVault) or (
                vault.identity_id,
                vault.lineage_id,
                vault.branch_id,
                vault.relationship_principal_id,
            ) != (
                capability.identity_id,
                capability.lineage_id,
                capability.branch_id,
                capability.principal_id,
            ):
                return self._denied(
                    repository,
                    mutation,
                    context,
                    capability,
                    request_snapshot,
                    CoreErrorCode.VAULT_CAPABILITY_BINDING,
                    now,
                )
            if vault.status == "sealed":
                return self._denied(
                    repository,
                    mutation,
                    context,
                    capability,
                    request_snapshot,
                    CoreErrorCode.INVALID_VAULT_TRANSITION,
                    now,
                )

            candidates = repository.validated_vault_candidates(
                request_snapshot.identity_id,
                request_snapshot.lineage_id,
                request_snapshot.branch_id,
                request_snapshot.vault_id,
            )
            head = repository.verified_ledger_head(request_snapshot.branch_id)
            if not isinstance(head, LedgerEvent):
                raise ReceiptIntegrityError(
                    "Ledger head is missing for retrieval branch"
                )
            watermark = head.ledger_seq
            candidate_items = _candidate_items(
                candidates,
                request_snapshot,
                watermark,
            )
            if not candidate_items:
                result = RetrievalResult(
                    retrieval_id=request_snapshot.retrieval_id,
                    request=request_snapshot,
                    items=(),
                    queried_vault_ids=(request_snapshot.vault_id,),
                    source_watermark_seq=watermark,
                    error=None,
                )
            else:
                try:
                    ranked = self._ranker.rank(candidate_items, request_snapshot)
                    result = _validated_ranking(
                        ranked,
                        candidate_items,
                        request_snapshot,
                        watermark,
                    )
                except Exception:
                    return self._denied(
                        repository,
                        mutation,
                        context,
                        capability,
                        request_snapshot,
                        CoreErrorCode.VAULT_SCOPE_MISMATCH,
                        now,
                        head=head,
                    )

            event = self._append_audit(
                repository,
                mutation,
                context,
                capability,
                request_snapshot,
                cast(str, mutation.payload["used_event_id"]),
                "vault_read_capability_used",
                len(result.items),
                now,
                head=head,
                retrieval_result_hash=sha256_hex(
                    canonical_json(result.model_dump(mode="python"))
                ),
            )
            return CommandResult[object](
                value=result.model_dump(mode="json"),
                event_ids=(event.event_id,),
                error=None,
                replayed=False,
            )

        raw = execute_command_on_connection(
            self._connection,
            command_snapshot,
            handler,
            clock=self._clock,
        )
        if raw.value is None:
            return cast(CommandResult[RetrievalResult], raw)
        value = RetrievalResult.model_validate_json(canonical_json(raw.value))
        return CommandResult[RetrievalResult](
            value=value,
            event_ids=raw.event_ids,
            error=raw.error,
            replayed=raw.replayed,
        )

    def _denied(
        self,
        repository: AuthorityRepository,
        command: MutationCommandEnvelope,
        context: CommandExecutionContext,
        capability: VaultReadCapability,
        request: RetrievalRequest,
        code: CoreErrorCode,
        now: object,
        *,
        head: LedgerEvent | None = None,
    ) -> CommandResult[object]:
        event = self._append_audit(
            repository,
            command,
            context,
            capability,
            request,
            cast(str, command.payload["denied_event_id"]),
            "vault_read_capability_denied",
            0,
            now,
            error_code=code,
            head=head,
        )
        return CommandResult[object](
            value=None,
            event_ids=(event.event_id,),
            error=_core_error(command, code, event.event_id),
            replayed=False,
        )

    def _append_audit(
        self,
        repository: AuthorityRepository,
        command: MutationCommandEnvelope,
        context: CommandExecutionContext,
        capability: VaultReadCapability,
        request: RetrievalRequest,
        event_id: str,
        event_type: str,
        result_count: int,
        now: object,
        *,
        error_code: CoreErrorCode | None = None,
        head: LedgerEvent | None = None,
        retrieval_result_hash: str | None = None,
    ) -> LedgerEvent:
        if head is None:
            head = repository.verified_ledger_head(capability.branch_id)
        if not isinstance(head, LedgerEvent):
            raise ReceiptIntegrityError(
                "Ledger head is missing for retrieval branch"
            )
        payload: dict[str, object] = {
            "capability_id": capability.capability_id,
            "operation": "retrieve",
            "input_hash": _request_input_hash(request),
            "read_scope_hash": _read_scope_hash(request),
            "result_count": result_count,
            "retrieval_id": request.retrieval_id,
            "request_actor_type": request.actor.actor_type,
            "request_actor_id": request.actor.actor_id,
        }
        if error_code is not None:
            payload["error_code"] = error_code.value
        if retrieval_result_hash is not None:
            payload["retrieval_result_hash"] = retrieval_result_hash
        stored_payload = prepare_inline_payload(payload)
        event = cast(
            LedgerEvent,
            seal_record(
                LedgerEvent,
                {
                    "record_header": record_header(
                        "LedgerEvent",
                        event_id,
                        identity_id=capability.identity_id,
                        lineage_id=capability.lineage_id,
                        branch_id=capability.branch_id,
                        created_at=now,
                        created_by_event_id=event_id,
                        deployment_policy_ref=(
                            capability.record_header.deployment_policy_ref
                        ),
                    ),
                    "event_id": event_id,
                    "ledger_seq": head.ledger_seq + 1,
                    "identity_id": capability.identity_id,
                    "lineage_id": capability.lineage_id,
                    "branch_id": capability.branch_id,
                    "instance_id": command.payload["instance_id"],
                    "vault_id": capability.vault_id,
                    "event_type": event_type,
                    "occurred_at": now,
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
                },
            ),
        )
        appended = repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=stored_payload,
        )
        if not isinstance(appended, LedgerEvent):
            raise TypeError("retrieval audit append returned the wrong record type")
        return appended


__all__ = [
    "Ranker",
    "RetrievalItem",
    "RetrievalResult",
    "RetrievalService",
]
