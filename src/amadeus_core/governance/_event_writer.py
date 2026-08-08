"""UoW-bound, narrow governance Ledger event writer."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime
from typing import cast

from pydantic import TypeAdapter, ValidationError

from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    MutationCommandEnvelope,
    compute_command_hash,
)
from amadeus_core.contracts.common import DeferConditions, HashHex, RecordId
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.vault import RelationshipVault
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.storage.payloads import prepare_inline_payload
from amadeus_core.storage.records import ZERO_HASH, record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository


_RECORD_ID = TypeAdapter(RecordId)
_HASH_HEX = TypeAdapter(HashHex)
_REQUEST_EVENT_TYPES = frozenset(
    {
        "confidentiality_request_submitted",
        "correction_request_submitted",
        "non_mention_request_submitted",
    }
)


def _datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _record_id(value: object, prefix: str) -> str:
    try:
        validated = _RECORD_ID.validate_python(value)
    except ValidationError as error:
        raise CoreContractViolation(CoreErrorCode.RECORD_ID_MISMATCH) from error
    if not validated.startswith(prefix):
        raise CoreContractViolation(CoreErrorCode.RECORD_ID_MISMATCH)
    return validated


class _GovernanceEventWriter:
    """Expose only named governance events inside one UoW handler."""

    def __init__(
        self,
        repository: AuthorityRepository,
        command: MutationCommandEnvelope,
        execution_context: CommandExecutionContext,
    ) -> None:
        if getattr(repository, "_execution_context", None) is not execution_context:
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        self._repository = repository
        self._command = command
        self._execution_context = execution_context

    def request_submitted(
        self,
        request: MemoryRequest,
        *,
        event_type: str,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
    ) -> LedgerEvent:
        if event_type not in _REQUEST_EVENT_TYPES:
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        return self._append(
            api_name="submit_memory_request",
            event_id=event_id,
            identity_id=request.identity_id,
            lineage_id=request.lineage_id,
            branch_id=request.branch_id,
            instance_id=instance_id,
            vault_id=request.vault_id,
            event_type=event_type,
            event_payload={
                "request_id": request.request_id,
                "request_type": request.request_type,
                "identity_id": request.identity_id,
                "lineage_id": request.lineage_id,
                "branch_id": request.branch_id,
                "vault_id": request.vault_id,
                "requester_id": request.requester_id,
                "target_refs": request.target_refs,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=request.submitted_at,
        )

    def proposal_submitted(
        self,
        proposal: Proposal,
        *,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
    ) -> LedgerEvent:
        return self._append(
            api_name="submit_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type="proposal_submitted",
            event_payload={
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "vault_id": proposal.vault_id,
                "proposal_content_hash": proposal.record_header.content_hash,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=proposal.created_at,
        )

    def governor_committed(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        decision: GovernorDecision,
        *,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
        receipt_output_binding_hash: str,
        receipt_output_signature: str,
    ) -> LedgerEvent:
        return self._governor_decision(
            proposal,
            stored_proposal,
            decision,
            event_type="governor_decision_committed",
            event_id=event_id,
            instance_id=instance_id,
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            receipt_output_binding_hash=receipt_output_binding_hash,
            receipt_output_signature=receipt_output_signature,
        )

    def governor_rejected(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        decision: GovernorDecision,
        *,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
        receipt_output_binding_hash: str,
        receipt_output_signature: str,
    ) -> LedgerEvent:
        return self._governor_decision(
            proposal,
            stored_proposal,
            decision,
            event_type="governor_decision_rejected",
            event_id=event_id,
            instance_id=instance_id,
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            receipt_output_binding_hash=receipt_output_binding_hash,
            receipt_output_signature=receipt_output_signature,
        )

    def _governor_decision(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        decision: GovernorDecision,
        *,
        event_type: str,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
        receipt_output_binding_hash: str,
        receipt_output_signature: str,
    ) -> LedgerEvent:
        expected_type = {
            "commit": "governor_decision_committed",
            "reject": "governor_decision_rejected",
        }.get(decision.result)
        if event_type != expected_type:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type=event_type,
            event_payload={
                "decision_id": decision.decision_id,
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "result": decision.result,
                "policy_version": decision.policy_version,
                "reason_codes": decision.reason_codes,
                "evidence_refs": decision.evidence_refs,
                "committed_event_ids": decision.committed_event_ids,
                "input_state_hash": decision.input_state_hash,
                "output_state_hash": decision.output_state_hash,
                "decision_content_hash": decision.record_header.content_hash,
                "governor_signature": decision.governor_signature,
                "receipt_output_binding_hash": receipt_output_binding_hash,
                "receipt_output_signature": receipt_output_signature,
                "before_proposal_content_hash": (
                    proposal.record_header.content_hash
                ),
                "before_proposal_version": proposal.version,
                "before_proposal_status": proposal.status,
                "proposal_content_hash": (
                    stored_proposal.record_header.content_hash
                ),
                "proposal_version": stored_proposal.version,
                "proposal_status": stored_proposal.status,
                "proposal_target_refs": stored_proposal.target_refs,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=decision.decided_at,
        )

    def memory_created(
        self,
        proposal: Proposal,
        decision: GovernorDecision,
        memory: AutobiographicalMemory,
        *,
        before_content_hash: str | None,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str,
    ) -> LedgerEvent:
        if before_content_hash is not None:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        return self._memory_effect(
            proposal,
            decision,
            memory,
            before_content_hash=before_content_hash,
            event_type="memory_created",
            event_id=event_id,
            instance_id=instance_id,
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
        )

    def memory_state_changed(
        self,
        proposal: Proposal,
        decision: GovernorDecision,
        memory: AutobiographicalMemory,
        *,
        before_content_hash: str | None,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str,
    ) -> LedgerEvent:
        if before_content_hash is None:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        return self._memory_effect(
            proposal,
            decision,
            memory,
            before_content_hash=before_content_hash,
            event_type="memory_state_changed",
            event_id=event_id,
            instance_id=instance_id,
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
        )

    def memory_expression_policy_changed(
        self,
        proposal: Proposal,
        decision: GovernorDecision,
        memory: AutobiographicalMemory,
        *,
        before_content_hash: str | None,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str,
    ) -> LedgerEvent:
        if before_content_hash is None:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        return self._memory_effect(
            proposal,
            decision,
            memory,
            before_content_hash=before_content_hash,
            event_type="memory_expression_policy_changed",
            event_id=event_id,
            instance_id=instance_id,
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
        )

    def _memory_effect(
        self,
        proposal: Proposal,
        decision: GovernorDecision,
        memory: AutobiographicalMemory,
        *,
        before_content_hash: str | None,
        event_type: str,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str,
    ) -> LedgerEvent:
        if (
            memory.memory_id not in proposal.target_refs
            or memory.governor_decision_id != decision.decision_id
            or (
                memory.identity_id,
                memory.lineage_id,
                memory.branch_id,
                memory.governing_vault_id,
            )
            != (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                proposal.vault_id,
            )
        ):
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=memory.identity_id,
            lineage_id=memory.lineage_id,
            branch_id=memory.branch_id,
            instance_id=instance_id,
            vault_id=memory.governing_vault_id,
            event_type=event_type,
            event_payload={
                "decision_id": decision.decision_id,
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "memory_id": memory.memory_id,
                "before_content_hash": before_content_hash,
                "memory_content_hash": memory.record_header.content_hash,
                "state": memory.state,
                "semantic_version": memory.semantic_version,
                "version": memory.version,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=decision.decided_at,
        )

    def governor_deferred(
        self,
        proposal: Proposal,
        decision: GovernorDecision,
        *,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str | None,
        receipt_output_binding_hash: str | None = None,
        receipt_output_signature: str | None = None,
    ) -> LedgerEvent:
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type="governor_decision_deferred",
            event_payload={
                "decision_id": decision.decision_id,
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "result": "defer",
                "policy_version": decision.policy_version,
                "reason_codes": decision.reason_codes,
                "evidence_refs": decision.evidence_refs,
                "committed_event_ids": decision.committed_event_ids,
                "input_state_hash": decision.input_state_hash,
                "output_state_hash": decision.output_state_hash,
                "decision_content_hash": decision.record_header.content_hash,
                "governor_signature": decision.governor_signature,
                **(
                    {}
                    if receipt_output_binding_hash is None
                    or receipt_output_signature is None
                    else {
                        "receipt_output_binding_hash": receipt_output_binding_hash,
                        "receipt_output_signature": receipt_output_signature,
                    }
                ),
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=decision.decided_at,
        )

    def proposal_deferred(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        decision: GovernorDecision,
        conditions: DeferConditions,
        *,
        event_id: str,
        instance_id: str,
        deployment_policy_ref: str,
        causation_id: str,
    ) -> LedgerEvent:
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type="proposal_deferred",
            event_payload={
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "decision_id": decision.decision_id,
                "missing_evidence_types": conditions.missing_evidence_types,
                "reopen_not_before": _datetime_text(conditions.reopen_not_before),
                "before_proposal_content_hash": (
                    proposal.record_header.content_hash
                ),
                "before_proposal_version": proposal.version,
                "before_proposal_status": proposal.status,
                "proposal_content_hash": (
                    stored_proposal.record_header.content_hash
                ),
                "proposal_version": stored_proposal.version,
                "proposal_status": stored_proposal.status,
                "proposal_target_refs": stored_proposal.target_refs,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=decision.decided_at,
        )

    def proposal_reopened(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        *,
        event_id: str,
        instance_id: str,
        evidence_event_ids: tuple[str, ...],
        previous_missing_evidence_types: tuple[str, ...],
        reopened_at: datetime,
        deployment_policy_ref: str,
        causation_id: str | None,
    ) -> LedgerEvent:
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type="proposal_reopened",
            event_payload={
                "proposal_id": proposal.proposal_id,
                "evidence_event_ids": evidence_event_ids,
                "previous_missing_evidence_types": previous_missing_evidence_types,
                "reopened_at": _datetime_text(reopened_at),
                "before_proposal_content_hash": (
                    proposal.record_header.content_hash
                ),
                "before_proposal_version": proposal.version,
                "before_proposal_status": proposal.status,
                "proposal_content_hash": (
                    stored_proposal.record_header.content_hash
                ),
                "proposal_version": stored_proposal.version,
                "proposal_status": stored_proposal.status,
                "proposal_target_refs": stored_proposal.target_refs,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=reopened_at,
        )

    def proposal_expired(
        self,
        proposal: Proposal,
        stored_proposal: Proposal,
        *,
        event_id: str,
        instance_id: str,
        previous_status: str,
        expired_at: datetime,
        deployment_policy_ref: str,
        causation_id: str | None,
    ) -> LedgerEvent:
        return self._append(
            api_name="decide_memory_proposal",
            event_id=event_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            instance_id=instance_id,
            vault_id=proposal.vault_id,
            event_type="proposal_expired",
            event_payload={
                "proposal_id": proposal.proposal_id,
                "previous_status": previous_status,
                "expired_at": _datetime_text(expired_at),
                "before_proposal_content_hash": (
                    proposal.record_header.content_hash
                ),
                "before_proposal_version": proposal.version,
                "before_proposal_status": proposal.status,
                "proposal_content_hash": (
                    stored_proposal.record_header.content_hash
                ),
                "proposal_version": stored_proposal.version,
                "proposal_status": stored_proposal.status,
                "proposal_target_refs": stored_proposal.target_refs,
            },
            deployment_policy_ref=deployment_policy_ref,
            causation_id=causation_id,
            occurred_at=expired_at,
        )

    def _append(
        self,
        *,
        api_name: str,
        event_id: str,
        identity_id: str,
        lineage_id: str,
        branch_id: str,
        instance_id: str,
        vault_id: str | None,
        event_type: str,
        event_payload: Mapping[str, object],
        deployment_policy_ref: str,
        causation_id: str | None,
        occurred_at: datetime,
    ) -> LedgerEvent:
        repository = self._repository
        command = self._command
        execution_context = self._execution_context
        write_spec = WRITE_API_BY_NAME.get(api_name)
        if (
            write_spec is None
            or "LedgerEvent" not in write_spec.target_record_types
            or command.actor.actor_type not in write_spec.actor_types
            or event_type not in write_spec.emitted_event_types
        ):
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)

        validated_event_id = _record_id(
            event_id,
            TYPE_REGISTRY["LedgerEvent"].id_prefix,
        )
        validated_identity_id = _record_id(
            identity_id,
            TYPE_REGISTRY["Identity"].id_prefix,
        )
        validated_lineage_id = _record_id(
            lineage_id,
            TYPE_REGISTRY["Lineage"].id_prefix,
        )
        validated_branch_id = _record_id(
            branch_id,
            TYPE_REGISTRY["Branch"].id_prefix,
        )
        validated_instance_id = _record_id(instance_id, "ins-")
        validated_vault_id = (
            None
            if vault_id is None
            else _record_id(
                vault_id,
                TYPE_REGISTRY["RelationshipVault"].id_prefix,
            )
        )
        if causation_id is None:
            validated_causation_id = None
        elif causation_id.startswith(("evt-", "cmd-")):
            validated_causation_id = _record_id(causation_id, causation_id[:4])
        else:
            raise CoreContractViolation(CoreErrorCode.RECORD_ID_MISMATCH)
        _record_id(command.command_id, "cmd-")
        try:
            _RECORD_ID.validate_python(command.actor.actor_id)
            _HASH_HEX.validate_python(execution_context.command_hash)
        except ValidationError as error:
            raise CoreContractViolation(
                CoreErrorCode.HEADER_BODY_MISMATCH
            ) from error
        if (
            execution_context.command_id != command.command_id
            or execution_context.audit_context_id != command.audit_context_id
            or not hmac.compare_digest(
                execution_context.command_hash,
                compute_command_hash(command),
            )
        ):
            raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)

        identity = repository.get_validated(validated_identity_id)
        lineage = repository.get_validated(validated_lineage_id)
        branch = repository.get_validated(validated_branch_id)
        if (
            not isinstance(identity, Identity)
            or not isinstance(lineage, Lineage)
            or not isinstance(branch, Branch)
            or identity.lineage_id != validated_lineage_id
            or identity.active_branch_id != validated_branch_id
            or lineage.root_identity_id != validated_identity_id
            or branch.identity_id != validated_identity_id
            or branch.lineage_id != validated_lineage_id
            or branch.status != "active"
            or identity.lifecycle_state != "active"
        ):
            raise CoreContractViolation(CoreErrorCode.ACTIVE_BRANCH_INVARIANT)
        if deployment_policy_ref != identity.record_header.deployment_policy_ref:
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)
        if validated_vault_id is not None:
            vault = repository.get_validated(validated_vault_id)
            if (
                not isinstance(vault, RelationshipVault)
                or (vault.identity_id, vault.lineage_id, vault.branch_id)
                != (
                    validated_identity_id,
                    validated_lineage_id,
                    validated_branch_id,
                )
            ):
                raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)

        head = repository.verified_ledger_head(validated_branch_id)
        if not isinstance(head, LedgerEvent):
            raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)
        if (head.identity_id, head.lineage_id, head.branch_id) != (
            validated_identity_id,
            validated_lineage_id,
            validated_branch_id,
        ):
            raise CoreContractViolation(CoreErrorCode.HEADER_BODY_MISMATCH)

        stored_payload = prepare_inline_payload(event_payload)
        event = cast(
            LedgerEvent,
            seal_record(
                LedgerEvent,
                {
                    "record_header": record_header(
                        "LedgerEvent",
                        validated_event_id,
                        identity_id=validated_identity_id,
                        lineage_id=validated_lineage_id,
                        branch_id=validated_branch_id,
                        created_at=occurred_at,
                        created_by_event_id=validated_event_id,
                        deployment_policy_ref=deployment_policy_ref,
                    ),
                    "event_id": validated_event_id,
                    "ledger_seq": head.ledger_seq + 1,
                    "identity_id": validated_identity_id,
                    "lineage_id": validated_lineage_id,
                    "branch_id": validated_branch_id,
                    "instance_id": validated_instance_id,
                    "vault_id": validated_vault_id,
                    "event_type": event_type,
                    "occurred_at": occurred_at,
                    "ingested_at": command.issued_at,
                    "actor_type": command.actor.actor_type,
                    "actor_id": command.actor.actor_id,
                    "mutation_command_id": execution_context.command_id,
                    "mutation_command_hash": execution_context.command_hash,
                    "payload_ref": stored_payload.payload_ref,
                    "causation_id": validated_causation_id,
                    "correlation_id": execution_context.audit_context_id,
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
            raise CoreContractViolation(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        return appended


__all__: list[str] = []
