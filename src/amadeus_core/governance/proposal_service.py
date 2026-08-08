"""Proposal submission and pre-decision lifecycle transitions."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime
from typing import cast

from pydantic import ValidationError

from amadeus_core.clock import Clock
from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import (
    ContentHashMismatch,
    validate_authoritative_record,
)
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.records import reseal_update
from amadeus_core.storage.reader import SQLiteAuthorityReader
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError, SQLiteUnitOfWork

from ._event_writer import _GovernanceEventWriter
from ._proposal_rules import (
    _EMPTY_DEFER_CONDITIONS,
    _TERMINAL_PROPOSAL_STATES,
    _assert_closed_payload,
    _assert_scope_refs,
    _event_satisfies_proposal_scope,
    _fail,
    _latest_proposal_deferred_seq,
    _normalized_expected_versions,
    _snapshot_binding_is_active,
    _validate_defer,
    _validate_record_id,
    _validate_submit,
    _validated_authorities,
    _validated_defer_inputs,
    _validated_expire_descriptor,
    _validated_reopen_descriptor,
)
from ._service import (
    GovernanceViolation,
    failure_result,
    semantic_input_hash_matches,
    typed_result,
)


def _proposal_stable_identity(proposal: Proposal) -> tuple[object, ...]:
    header = proposal.record_header.model_dump(mode="python")
    header.pop("content_hash")
    return (
        header,
        proposal.proposal_id,
        proposal.proposal_type,
        proposal.identity_id,
        proposal.lineage_id,
        proposal.branch_id,
        proposal.vault_id,
        proposal.proposed_by,
        proposal.target_refs,
        proposal.evidence_refs,
        proposal.proposed_patch,
        proposal.created_at,
        proposal.expires_at,
    )


class ProposalService:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._unit_of_work = SQLiteUnitOfWork(database, clock=clock)
        self._reader = SQLiteAuthorityReader(database)

    def submit(
        self,
        mutation_command: MutationCommandEnvelope,
        proposal: Proposal | Mapping[str, object],
    ) -> CommandResult[Proposal]:
        try:
            snapshot = Proposal.model_validate(
                proposal.model_dump(mode="python")
                if isinstance(proposal, Proposal)
                else proposal
            )
            snapshot = cast(
                Proposal,
                validate_authoritative_record(
                    "proposal",
                    snapshot.model_dump(mode="python"),
                ),
            )
        except CoreContractViolation as error:
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, error.code),
            )
        except ContentHashMismatch:
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, CoreErrorCode.HASH_SCOPE_MISMATCH),
            )
        except ValidationError:
            return cast(
                CommandResult[Proposal],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        if not semantic_input_hash_matches(mutation_command, snapshot):
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, CoreErrorCode.HASH_SCOPE_MISMATCH),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            event_id, instance_id, identity = _validate_submit(
                repository,
                command,
                snapshot,
            )
            event = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            ).proposal_submitted(
                snapshot,
                event_id=event_id,
                instance_id=instance_id,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=cast(str | None, command.payload.get("causation_id")),
            )
            stored = repository.save_authoritative(
                "proposal",
                snapshot.model_dump(mode="python"),
            )
            if not isinstance(stored, Proposal):
                raise TypeError("proposal authority save returned the wrong type")
            return CommandResult[object](
                value=stored.model_dump(mode="json"),
                event_ids=(event.event_id,),
                error=None,
                replayed=False,
            )

        return self._execute_typed(
            mutation_command,
            handler,
            expected_record_id=snapshot.proposal_id,
            expected_event_ids=(snapshot.record_header.created_by_event_id,),
            replay_expected=snapshot,
        )

    def defer(
        self,
        mutation_command: MutationCommandEnvelope,
        proposal_id: str,
        conditions: DeferConditions | Mapping[str, object],
    ) -> CommandResult[Proposal]:
        try:
            condition_snapshot, decision = _validated_defer_inputs(
                mutation_command,
                proposal_id,
                conditions,
            )
        except GovernanceViolation as error:
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, error.code),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            (
                proposal,
                updated,
                decision_event_id,
                proposal_event_id,
                instance_id,
                identity,
            ) = _validate_defer(
                repository,
                command,
                proposal_id,
                condition_snapshot,
                decision,
            )
            stored_proposal = repository.save_authoritative(
                "proposal",
                updated.model_dump(mode="python"),
            )
            stored_decision = repository.save_authoritative(
                "governor_decision",
                decision.model_dump(mode="python"),
            )
            if not isinstance(stored_proposal, Proposal) or not isinstance(
                stored_decision,
                GovernorDecision,
            ):
                raise TypeError("defer authority save returned the wrong type")
            writer = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            )
            decision_event = writer.governor_deferred(
                proposal,
                decision,
                event_id=decision_event_id,
                instance_id=instance_id,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=cast(
                    str | None,
                    command.payload.get("causation_id"),
                ),
            )
            proposal_event = writer.proposal_deferred(
                proposal,
                stored_proposal,
                decision,
                condition_snapshot,
                event_id=proposal_event_id,
                instance_id=instance_id,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=decision_event.event_id,
            )
            return CommandResult[object](
                value=stored_proposal.model_dump(mode="json"),
                event_ids=(decision_event.event_id, proposal_event.event_id),
                error=None,
                replayed=False,
            )

        return self._execute_typed(
            mutation_command,
            handler,
            expected_record_id=proposal_id,
            expected_event_ids=decision.committed_event_ids,
            replay_content_hash=decision.output_state_hash,
        )

    def reopen(
        self,
        mutation_command: MutationCommandEnvelope,
        proposal_id: str,
        now: datetime,
    ) -> CommandResult[Proposal]:
        try:
            evidence_event_ids = _validated_reopen_descriptor(
                mutation_command,
                proposal_id,
                now,
            )
            replay_event_id = _validate_record_id(
                mutation_command.payload.get("event_id"),
                TYPE_REGISTRY["LedgerEvent"].id_prefix,
            )
        except GovernanceViolation as error:
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, error.code),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            write_spec = WRITE_API_BY_NAME["decide_memory_proposal"]
            if command.actor.actor_type not in write_spec.actor_types:
                code = (
                    CoreErrorCode.LLM_COMMIT_FORBIDDEN
                    if command.actor.actor_type == "llm"
                    else CoreErrorCode.HEADER_BODY_MISMATCH
                )
                _fail(code)
            proposal = repository.get_validated(proposal_id)
            if not isinstance(proposal, Proposal):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if proposal.status in _TERMINAL_PROPOSAL_STATES:
                _fail(CoreErrorCode.PROPOSAL_TERMINAL)
            if proposal.status != "deferred":
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if command.command_type != "memory_proposal.reopen":
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            _assert_closed_payload(
                command,
                frozenset(
                    {
                        "scope_refs",
                        "event_id",
                        "instance_id",
                        "proposal_id",
                        "evidence_event_ids",
                        "now",
                        "semantic_input_hash",
                    }
                ),
                frozenset({"causation_id"}),
            )
            event_id = _validate_record_id(
                command.payload.get("event_id"),
                TYPE_REGISTRY["LedgerEvent"].id_prefix,
            )
            instance_id = _validate_record_id(
                command.payload.get("instance_id"),
                "ins-",
            )
            if command.issued_at != now:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            versions = _normalized_expected_versions(command)
            if command.target_record_refs != (proposal.proposal_id, event_id) or (
                versions
                != {proposal.proposal_id: proposal.version, event_id: 0}
            ):
                _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
            required_scope = (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                *((proposal.vault_id,) if proposal.vault_id is not None else ()),
                proposal.proposal_id,
                *evidence_event_ids,
            )
            _assert_scope_refs(command, required_scope)
            identity, _lineage, _branch, _vault = _validated_authorities(
                repository,
                proposal,
            )
            conditions = proposal.defer_conditions
            if (
                conditions.reopen_not_before is not None
                and now < conditions.reopen_not_before
            ) or now >= proposal.expires_at:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if len(set(evidence_event_ids)) != len(evidence_event_ids):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            replay = repository.validated_ledger_replay(proposal.branch_id)
            deferred_seq = _latest_proposal_deferred_seq(
                replay,
                proposal.proposal_id,
            )
            if deferred_seq is None:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            ledger_events = {
                event.event_id: event
                for event in replay.events
            }
            evidence_events: list[LedgerEvent] = []
            for evidence_event_id in evidence_event_ids:
                event = ledger_events.get(evidence_event_id)
                if (
                    event is None
                    or event.ledger_seq <= deferred_seq
                    or not _event_satisfies_proposal_scope(event, proposal)
                ):
                    _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
                evidence_events.append(event)
            available_types = {event.event_type for event in evidence_events}
            if not set(conditions.missing_evidence_types) <= available_types:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            updated = cast(
                Proposal,
                reseal_update(
                    proposal,
                    {
                        "status": "pending",
                        "deferred_at": None,
                        "defer_conditions": _EMPTY_DEFER_CONDITIONS,
                        "reopened_count": proposal.reopened_count + 1,
                        "version": proposal.version + 1,
                    },
                ),
            )
            stored = repository.save_authoritative(
                "proposal",
                updated.model_dump(mode="python"),
            )
            if not isinstance(stored, Proposal):
                raise TypeError("reopen authority save returned the wrong type")
            event = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            ).proposal_reopened(
                proposal,
                stored,
                event_id=event_id,
                instance_id=instance_id,
                evidence_event_ids=evidence_event_ids,
                previous_missing_evidence_types=(
                    conditions.missing_evidence_types
                ),
                reopened_at=now,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=cast(
                    str | None,
                    command.payload.get("causation_id"),
                ),
            )
            return CommandResult[object](
                value=stored.model_dump(mode="json"),
                event_ids=(event.event_id,),
                error=None,
                replayed=False,
            )

        return self._execute_typed(
            mutation_command,
            handler,
            expected_record_id=proposal_id,
            expected_event_ids=(replay_event_id,),
            replay_event_id=replay_event_id,
            replay_event_type="proposal_reopened",
        )

    def expire(
        self,
        mutation_command: MutationCommandEnvelope,
        proposal_id: str,
        now: datetime,
    ) -> CommandResult[Proposal]:
        try:
            _validated_expire_descriptor(mutation_command, proposal_id, now)
            replay_event_id = _validate_record_id(
                mutation_command.payload.get("event_id"),
                TYPE_REGISTRY["LedgerEvent"].id_prefix,
            )
        except GovernanceViolation as error:
            return cast(
                CommandResult[Proposal],
                failure_result(mutation_command, error.code),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            write_spec = WRITE_API_BY_NAME["decide_memory_proposal"]
            if command.actor.actor_type not in write_spec.actor_types:
                code = (
                    CoreErrorCode.LLM_COMMIT_FORBIDDEN
                    if command.actor.actor_type == "llm"
                    else CoreErrorCode.HEADER_BODY_MISMATCH
                )
                _fail(code)
            if command.command_type != "memory_proposal.expire":
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            _assert_closed_payload(
                command,
                frozenset(
                    {
                        "scope_refs",
                        "event_id",
                        "instance_id",
                        "proposal_id",
                        "now",
                        "semantic_input_hash",
                    }
                ),
                frozenset({"causation_id"}),
            )
            proposal = repository.get_validated(proposal_id)
            if not isinstance(proposal, Proposal):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if proposal.status in _TERMINAL_PROPOSAL_STATES:
                _fail(CoreErrorCode.PROPOSAL_TERMINAL)
            if proposal.status not in {"pending", "deferred"}:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if now < proposal.expires_at or command.issued_at != now:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            event_id = _validate_record_id(
                command.payload.get("event_id"),
                TYPE_REGISTRY["LedgerEvent"].id_prefix,
            )
            instance_id = _validate_record_id(
                command.payload.get("instance_id"),
                "ins-",
            )
            versions = _normalized_expected_versions(command)
            if command.target_record_refs != (proposal.proposal_id, event_id) or (
                versions
                != {proposal.proposal_id: proposal.version, event_id: 0}
            ):
                _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
            required_scope = (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                *((proposal.vault_id,) if proposal.vault_id is not None else ()),
                proposal.proposal_id,
            )
            _assert_scope_refs(command, required_scope)
            identity, _lineage, _branch, _vault = _validated_authorities(
                repository,
                proposal,
            )
            previous_status = proposal.status
            updated = cast(
                Proposal,
                reseal_update(
                    proposal,
                    {
                        "status": "expired",
                        "version": proposal.version + 1,
                    },
                ),
            )
            stored = repository.save_authoritative(
                "proposal",
                updated.model_dump(mode="python"),
            )
            if not isinstance(stored, Proposal):
                raise TypeError("expire authority save returned the wrong type")
            event = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            ).proposal_expired(
                proposal,
                stored,
                event_id=event_id,
                instance_id=instance_id,
                previous_status=previous_status,
                expired_at=now,
                deployment_policy_ref=identity.deployment_policy_ref,
                causation_id=cast(
                    str | None,
                    command.payload.get("causation_id"),
                ),
            )
            return CommandResult[object](
                value=stored.model_dump(mode="json"),
                event_ids=(event.event_id,),
                error=None,
                replayed=False,
            )

        return self._execute_typed(
            mutation_command,
            handler,
            expected_record_id=proposal_id,
            expected_event_ids=(replay_event_id,),
            replay_event_id=replay_event_id,
            replay_event_type="proposal_expired",
        )

    def find_reopenable(self, now: datetime) -> tuple[str, ...]:
        snapshot = self._reader.proposal_snapshot()
        reopenable: list[str] = []
        for proposal in snapshot.proposals:
            if (
                proposal.status != "deferred"
                or not _snapshot_binding_is_active(
                    proposal,
                    snapshot.binding_for(proposal.proposal_id),
                )
                or now >= proposal.expires_at
                or (
                    proposal.defer_conditions.reopen_not_before is not None
                    and now < proposal.defer_conditions.reopen_not_before
                )
            ):
                continue
            replay = snapshot.replay_for(proposal.branch_id)
            if replay is None:
                continue
            deferred_seq = _latest_proposal_deferred_seq(
                replay,
                proposal.proposal_id,
            )
            if deferred_seq is None:
                continue
            available_types = {
                event.event_type
                for event in replay.events
                if event.ledger_seq > deferred_seq
                and _event_satisfies_proposal_scope(event, proposal)
            }
            if set(proposal.defer_conditions.missing_evidence_types) <= (
                available_types
            ):
                reopenable.append(proposal.proposal_id)
        return tuple(reopenable)

    def find_expired(self, now: datetime) -> tuple[str, ...]:
        snapshot = self._reader.proposal_snapshot()
        return tuple(
            proposal.proposal_id
            for proposal in snapshot.proposals
            if proposal.status in {"pending", "deferred"}
            and now >= proposal.expires_at
            and _snapshot_binding_is_active(
                proposal,
                snapshot.binding_for(proposal.proposal_id),
            )
        )

    def _proposal_hash_from_event(
        self,
        *,
        proposal_id: str,
        branch_id: str,
        event_id: str,
        event_type: str,
    ) -> str:
        snapshot = self._reader.proposal_snapshot()
        replay = snapshot.replay_for(branch_id)
        if replay is not None:
            for event, payload in zip(
                replay.events,
                replay.resolved_inline_payloads,
                strict=True,
            ):
                if event.event_id != event_id:
                    continue
                if (
                    event.event_type != event_type
                    or not isinstance(payload, Mapping)
                    or payload.get("proposal_id") != proposal_id
                ):
                    break
                content_hash = payload.get("proposal_content_hash")
                if isinstance(content_hash, str) and len(content_hash) == 64:
                    return content_hash
                break
        raise ReceiptIntegrityError(
            "Proposal receipt has no immutable Ledger content-hash anchor"
        )

    def _execute_typed(
        self,
        mutation_command: MutationCommandEnvelope,
        handler,
        *,
        expected_record_id: str,
        expected_event_ids: tuple[str, ...],
        replay_expected: Proposal | None = None,
        replay_content_hash: str | None = None,
        replay_event_id: str | None = None,
        replay_event_type: str | None = None,
    ) -> CommandResult[Proposal]:
        try:
            result = self._unit_of_work.execute_command(mutation_command, handler)
        except GovernanceViolation as error:
            result = failure_result(mutation_command, error.code)
        except CoreContractViolation as error:
            result = failure_result(mutation_command, error.code)
        except ContentHashMismatch:
            result = failure_result(
                mutation_command,
                CoreErrorCode.HASH_SCOPE_MISMATCH,
            )
        except ValidationError:
            result = failure_result(
                mutation_command,
                CoreErrorCode.HEADER_BODY_MISMATCH,
            )
        typed = typed_result(
            result,
            Proposal,
            receipt_label="Proposal",
            schema_root="proposal",
            expected_record_id=expected_record_id,
        )
        if typed.value is None:
            return typed
        if typed.event_ids != expected_event_ids:
            raise ReceiptIntegrityError(
                "Proposal receipt event IDs do not match the command"
            )
        current = self._reader.get_validated(expected_record_id)
        if not isinstance(current, Proposal) or (
            _proposal_stable_identity(current)
            != _proposal_stable_identity(typed.value)
        ):
            raise ReceiptIntegrityError(
                "Proposal receipt value does not match stable authority identity"
            )
        if replay_expected is not None:
            valid_value = typed.value == replay_expected
        elif replay_content_hash is not None:
            valid_value = hmac.compare_digest(
                typed.value.record_header.content_hash,
                replay_content_hash,
            )
        elif replay_event_id is not None and replay_event_type is not None:
            valid_value = hmac.compare_digest(
                typed.value.record_header.content_hash,
                self._proposal_hash_from_event(
                    proposal_id=expected_record_id,
                    branch_id=typed.value.branch_id,
                    event_id=replay_event_id,
                    event_type=replay_event_type,
                ),
            )
        else:
            valid_value = False
        if not valid_value:
            raise ReceiptIntegrityError(
                "Proposal receipt value does not match its immutable history anchor"
            )
        return typed


__all__ = ["ProposalService"]
