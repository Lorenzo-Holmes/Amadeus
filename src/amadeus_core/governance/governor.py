"""Deterministic Memory Governor orchestration boundary."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import cast

from pydantic import ValidationError

from amadeus_core.clock import Clock, FixedClock, SystemClock
from amadeus_core.contracts.commands import (
    CommandExecutionContext,
    CommandResult,
    MutationCommandEnvelope,
    compute_command_hash,
)
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Identity
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import ContentHashMismatch
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.records import record_header, seal_record
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import (
    ReceiptIntegrityError,
    SQLiteUnitOfWork,
)

from ._event_writer import _GovernanceEventWriter
from ._proposal_rules import (
    _TERMINAL_PROPOSAL_STATES,
    _assert_closed_payload,
    _assert_scope_refs,
    _event_satisfies_proposal_scope,
    _fail,
    _normalized_expected_versions,
    _validate_record_id,
    _validated_authorities,
)
from ._receipt_ancestry import (
    memory_authority_has_ledger_ancestry,
    proposal_authority_has_ledger_ancestry,
)
from ._receipt_output_binding import (
    compute_receipt_output_binding_hash,
    receipt_output_attestation_subject_hash,
)
from ._service import GovernanceViolation, failure_result, typed_result
from .governor_command_auth import GovernorCommandVerifier
from .governor_decision_attestation import GovernorDecisionAttestor
from .memory_proposal_profiles import (
    MemoryProposalProfile,
    memory_proposal_profile,
)
from .policy_v0_1 import (
    EvidenceSnapshot,
    GovernorAuthoritySnapshot,
    GovernorPolicyV01,
    GovernorPreview,
    MemoryAuthoritySnapshot,
    MemoryEffect,
    SourceEventSnapshot,
)


_DECIDE_PAYLOAD_FIELDS = frozenset(
    {
        "scope_refs",
        "instance_id",
        "proposal_id",
        "policy_version",
        "now",
        "decision_id",
        "decision_event_id",
        "effect_event_id",
        "semantic_input_hash",
    }
)
_DECIDE_OPTIONAL_PAYLOAD_FIELDS = frozenset(
    {"actor_attestation", "causation_id"}
)
_DECISION_EVENT_TYPE = {
    "commit": "governor_decision_committed",
    "reject": "governor_decision_rejected",
    "defer": "governor_decision_deferred",
}


def _validated_decide_descriptor(
    command: MutationCommandEnvelope,
    proposal_id: str,
    now: datetime,
) -> tuple[str, str, str, str, str]:
    if command.command_type != "memory_proposal.decide":
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    _assert_closed_payload(
        command,
        _DECIDE_PAYLOAD_FIELDS,
        _DECIDE_OPTIONAL_PAYLOAD_FIELDS,
    )
    validated_proposal_id = _validate_record_id(
        proposal_id,
        TYPE_REGISTRY["Proposal"].id_prefix,
    )
    decision_id = _validate_record_id(
        command.payload.get("decision_id"),
        TYPE_REGISTRY["GovernorDecision"].id_prefix,
    )
    decision_event_id = _validate_record_id(
        command.payload.get("decision_event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    effect_event_id = _validate_record_id(
        command.payload.get("effect_event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    instance_id = _validate_record_id(command.payload.get("instance_id"), "ins-")
    policy_version = command.payload.get("policy_version")
    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
        or command.payload.get("proposal_id") != validated_proposal_id
        or command.payload.get("now") != now
        or command.issued_at != now
        or decision_event_id == effect_event_id
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    descriptor = {
        "proposal_id": validated_proposal_id,
        "policy_version": policy_version,
        "now": now,
        "decision_id": decision_id,
        "decision_event_id": decision_event_id,
        "effect_event_id": effect_event_id,
    }
    supplied_hash = command.payload.get("semantic_input_hash")
    expected_hash = sha256_hex(canonical_json(descriptor))
    if not isinstance(supplied_hash, str) or not hmac.compare_digest(
        supplied_hash,
        expected_hash,
    ):
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
    return (
        decision_id,
        decision_event_id,
        effect_event_id,
        instance_id,
        policy_version,
    )


def _target_memory_snapshots(
    repository: AuthorityRepository,
    proposal: Proposal,
) -> tuple[MemoryAuthoritySnapshot, ...]:
    if len(proposal.target_refs) != 1:
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    snapshots: list[MemoryAuthoritySnapshot] = []
    for memory_id in proposal.target_refs:
        candidate = repository.get_validated(memory_id)
        if candidate is None:
            snapshots.append(
                MemoryAuthoritySnapshot(
                    memory_id=memory_id,
                    version=0,
                    content_hash=None,
                    memory=None,
                )
            )
            continue
        if not isinstance(candidate, AutobiographicalMemory):
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        snapshots.append(
            MemoryAuthoritySnapshot(
                memory_id=candidate.memory_id,
                version=candidate.version,
                content_hash=candidate.record_header.content_hash,
                memory=candidate,
            )
        )
    return tuple(snapshots)


def _evidence_snapshots(
    proposal: Proposal,
    evidence_refs: tuple[str, ...],
    replay_events: tuple[LedgerEvent, ...],
    replay_payloads: tuple[Mapping[str, object] | None, ...],
) -> tuple[tuple[EvidenceSnapshot, ...], tuple[SourceEventSnapshot, ...]]:
    available = {
        event.event_id: (event, payload)
        for event, payload in zip(replay_events, replay_payloads, strict=True)
    }
    snapshots: list[EvidenceSnapshot] = []
    source_snapshots: dict[str, SourceEventSnapshot] = {}
    for evidence_ref in evidence_refs:
        resolved = available.get(evidence_ref)
        if resolved is None:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        event, payload = resolved
        if payload is None or not _event_satisfies_proposal_scope(event, proposal):
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        payload_snapshot = dict(payload)
        payload_hash = sha256_hex(canonical_json(payload_snapshot))
        snapshots.append(
            EvidenceSnapshot(
                event_id=event.event_id,
                event_type=event.event_type,
                event_hash=event.event_hash,
                ledger_seq=event.ledger_seq,
                identity_id=event.identity_id,
                lineage_id=event.lineage_id,
                branch_id=event.branch_id,
                vault_id=event.vault_id,
                payload_ref=event.payload_ref,
                payload_hash=payload_hash,
                payload=payload_snapshot,
            )
        )
        source_ref = payload_snapshot.get("source_event_ref")
        source_resolved = (
            available.get(source_ref) if isinstance(source_ref, str) else None
        )
        if source_resolved is not None:
            source_event, _source_payload = source_resolved
            source_snapshots[source_event.event_id] = SourceEventSnapshot(
                event_id=source_event.event_id,
                event_type=source_event.event_type,
                event_hash=source_event.event_hash,
                ledger_seq=source_event.ledger_seq,
                identity_id=source_event.identity_id,
                lineage_id=source_event.lineage_id,
                branch_id=source_event.branch_id,
                vault_id=source_event.vault_id,
            )
    return tuple(snapshots), tuple(source_snapshots.values())


def _effective_evidence_refs(
    proposal: Proposal,
    replay_events: tuple[LedgerEvent, ...],
    replay_payloads: tuple[Mapping[str, object] | None, ...],
    *,
    through_ledger_seq: int | None = None,
) -> tuple[str, ...]:
    """Derive the adjudication closure from immutable Proposal/reopen authority."""

    event_by_id = {event.event_id: event for event in replay_events}
    refs = list(proposal.evidence_refs)
    last_deferred_seq: int | None = None
    for event, payload in zip(replay_events, replay_payloads, strict=True):
        if through_ledger_seq is not None and event.ledger_seq > through_ledger_seq:
            break
        if payload is None or payload.get("proposal_id") != proposal.proposal_id:
            continue
        if event.event_type == "proposal_deferred":
            if not _event_satisfies_proposal_scope(event, proposal):
                _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
            last_deferred_seq = event.ledger_seq
            continue
        if event.event_type != "proposal_reopened":
            continue
        if (
            last_deferred_seq is None
            or not _event_satisfies_proposal_scope(event, proposal)
        ):
            _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
        raw_refs = payload.get("evidence_event_ids")
        if not isinstance(raw_refs, (tuple, list)) or any(
            not isinstance(item, str) for item in raw_refs
        ):
            _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
        reopened_refs = tuple(raw_refs)
        if not reopened_refs or len(reopened_refs) != len(set(reopened_refs)):
            _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
        for evidence_ref in reopened_refs:
            evidence_event = event_by_id.get(evidence_ref)
            if (
                evidence_event is None
                or evidence_event.ledger_seq <= last_deferred_seq
                or evidence_event.ledger_seq >= event.ledger_seq
                or not _event_satisfies_proposal_scope(evidence_event, proposal)
            ):
                _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
            if evidence_ref not in refs:
                refs.append(evidence_ref)
        last_deferred_seq = None
    return tuple(refs)


def _load_authority_snapshot(
    repository: AuthorityRepository,
    proposal: Proposal,
) -> tuple[
    Identity,
    tuple[MemoryAuthoritySnapshot, ...],
    GovernorAuthoritySnapshot,
]:
    """Build the single authoritative snapshot used by preview and commit."""

    identity, lineage, branch, vault = _validated_authorities(
        repository,
        proposal,
    )
    target_snapshots = _target_memory_snapshots(repository, proposal)
    replay = repository.validated_ledger_replay(proposal.branch_id)
    if replay.root_hash is None:
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
    replay_payloads = cast(
        tuple[Mapping[str, object] | None, ...],
        replay.resolved_inline_payloads,
    )
    effective_evidence_refs = _effective_evidence_refs(
        proposal,
        replay.events,
        replay_payloads,
    )
    evidence_snapshots, source_snapshots = _evidence_snapshots(
        proposal,
        effective_evidence_refs,
        replay.events,
        replay_payloads,
    )
    return (
        identity,
        target_snapshots,
        GovernorAuthoritySnapshot(
            identity_hash=identity.record_header.content_hash,
            lineage_hash=lineage.record_header.content_hash,
            branch_hash=branch.record_header.content_hash,
            vault_hash=None if vault is None else vault.record_header.content_hash,
            ledger_watermark=replay.through_ledger_seq,
            ledger_root_hash=replay.root_hash,
            target_memories=target_snapshots,
            evidence_events=evidence_snapshots,
            source_events=source_snapshots,
            effective_evidence_refs=effective_evidence_refs,
        ),
    )


def _thaw_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_thaw_json_value(item) for item in value)
    return value


def _memory_from_effect(
    effect: MemoryEffect,
    *,
    proposal: Proposal,
    decision: GovernorDecision,
    effect_event_id: str,
    deployment_policy_ref: str,
    target_snapshot: MemoryAuthoritySnapshot,
) -> AutobiographicalMemory:
    semantic = cast(dict[str, object], _thaw_json_value(effect.after_semantic))
    if effect.operation == "create":
        header = record_header(
            "AutobiographicalMemory",
            effect.memory_id,
            identity_id=proposal.identity_id,
            lineage_id=proposal.lineage_id,
            branch_id=proposal.branch_id,
            created_at=semantic["created_at"],
            created_by_event_id=effect_event_id,
            deployment_policy_ref=deployment_policy_ref,
        )
    else:
        previous = target_snapshot.memory
        if previous is None:
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        header = previous.record_header.model_copy(
            update={"content_hash": "0" * 64}
        )
    memory = seal_record(
        AutobiographicalMemory,
        {
            "record_header": header,
            "memory_id": effect.memory_id,
            **semantic,
            "governor_decision_id": decision.decision_id,
        },
    )
    if not isinstance(memory, AutobiographicalMemory):
        raise TypeError("Memory effect materialized the wrong record type")
    materialized = memory.model_dump(mode="python")
    materialized_semantic = {
        key: materialized[key]
        for key in semantic
    }
    if not hmac.compare_digest(
        canonical_json(materialized_semantic),
        canonical_json(semantic),
    ):
        raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    return memory


class MemoryGovernor:
    """Pure preview plus the sole normal authoritative Memory committer."""

    __slots__ = (
        "_database",
        "_policy",
        "_command_verifier",
        "_decision_attestor",
        "_clock",
        "_unit_of_work",
    )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("MemoryGovernor runtime configuration is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("MemoryGovernor runtime configuration is immutable")

    def __init__(
        self,
        database: SQLiteDatabase,
        policy: GovernorPolicyV01,
        *,
        command_verifier: GovernorCommandVerifier,
        decision_attestor: GovernorDecisionAttestor,
        clock: Clock | None = None,
    ) -> None:
        if type(policy) is not GovernorPolicyV01:
            raise TypeError("MemoryGovernor requires the exact GovernorPolicyV01")
        if type(command_verifier) is not GovernorCommandVerifier:
            raise TypeError(
                "MemoryGovernor requires the concrete Governor command verifier"
            )
        if type(decision_attestor) is not GovernorDecisionAttestor:
            raise TypeError(
                "MemoryGovernor requires the concrete Governor decision attestor"
            )
        trusted_clock = SystemClock() if clock is None else clock
        if type(trusted_clock) not in (SystemClock, FixedClock):
            raise TypeError(
                "MemoryGovernor requires an exact trusted Clock implementation"
            )
        self._database = database
        self._policy = policy
        self._command_verifier = command_verifier
        self._decision_attestor = decision_attestor
        self._clock = trusted_clock
        self._unit_of_work = SQLiteUnitOfWork(database, clock=self._clock)

    def preview(
        self,
        proposal: Proposal,
        authority_state: GovernorAuthoritySnapshot,
        *,
        policy_version: str,
        now: datetime,
    ) -> GovernorPreview:
        return self._policy.evaluate(
            proposal,
            authority_state,
            policy_version=policy_version,
            now=now,
        )

    def preview_authoritative(
        self,
        proposal_id: str,
        *,
        policy_version: str,
        now: datetime,
    ) -> GovernorPreview:
        """Preview from validated persistent authority without committing writes."""

        validated_proposal_id = _validate_record_id(
            proposal_id,
            TYPE_REGISTRY["Proposal"].id_prefix,
        )
        connection = self._database.connect()
        try:
            connection.execute("BEGIN")
            repository = AuthorityRepository(connection)
            proposal = repository.get_validated(validated_proposal_id)
            if not isinstance(proposal, Proposal):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if proposal.status in _TERMINAL_PROPOSAL_STATES:
                _fail(CoreErrorCode.PROPOSAL_TERMINAL)
            if proposal.status != "pending":
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            _identity, _target_snapshots, authority_state = (
                _load_authority_snapshot(repository, proposal)
            )
            return self.preview(
                proposal,
                authority_state,
                policy_version=policy_version,
                now=now,
            )
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()

    def decide(
        self,
        mutation_command: MutationCommandEnvelope,
        proposal_id: str,
        now: datetime,
    ) -> CommandResult[GovernorDecision]:
        try:
            mutation_command = MutationCommandEnvelope.model_validate(
                mutation_command.model_dump(mode="python")
            )
        except (TypeError, ValueError):
            return cast(
                CommandResult[GovernorDecision],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        if type(mutation_command) is not MutationCommandEnvelope:
            return cast(
                CommandResult[GovernorDecision],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        if mutation_command.actor.actor_type == "llm":
            return cast(
                CommandResult[GovernorDecision],
                failure_result(
                    mutation_command,
                    CoreErrorCode.LLM_COMMIT_FORBIDDEN,
                ),
            )
        if mutation_command.actor.actor_type != "governor":
            return cast(
                CommandResult[GovernorDecision],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        if not self._command_verifier.verify(mutation_command):
            return cast(
                CommandResult[GovernorDecision],
                failure_result(
                    mutation_command,
                    CoreErrorCode.HEADER_BODY_MISMATCH,
                ),
            )
        try:
            (
                decision_id,
                decision_event_id,
                effect_event_id,
                instance_id,
                policy_version,
            ) = _validated_decide_descriptor(mutation_command, proposal_id, now)
        except GovernanceViolation as error:
            return cast(
                CommandResult[GovernorDecision],
                failure_result(mutation_command, error.code),
            )

        def handler(
            repository: AuthorityRepository,
            command: MutationCommandEnvelope,
            execution_context: CommandExecutionContext,
        ) -> CommandResult[object]:
            trusted_now = self._clock.now()
            if (
                not isinstance(trusted_now, datetime)
                or trusted_now.utcoffset() != timedelta(0)
                or trusted_now < now
            ):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            proposal = repository.get_validated(proposal_id)
            if not isinstance(proposal, Proposal):
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            if proposal.status in _TERMINAL_PROPOSAL_STATES:
                _fail(CoreErrorCode.PROPOSAL_TERMINAL)
            if proposal.status != "pending":
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)

            identity, target_snapshots, authority_state = _load_authority_snapshot(
                repository,
                proposal,
            )
            effective_evidence_refs = authority_state.effective_evidence_refs
            preview = self.preview(
                proposal,
                authority_state,
                policy_version=policy_version,
                now=trusted_now,
            )

            memory_snapshot = target_snapshots[0]
            required_targets = (
                proposal.proposal_id,
                decision_id,
                memory_snapshot.memory_id,
                decision_event_id,
                effect_event_id,
            )
            versions = _normalized_expected_versions(command)
            if command.target_record_refs != required_targets or versions != {
                proposal.proposal_id: proposal.version,
                decision_id: 0,
                memory_snapshot.memory_id: memory_snapshot.version,
                decision_event_id: 0,
                effect_event_id: 0,
            }:
                _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
            required_scope = (
                proposal.identity_id,
                proposal.lineage_id,
                proposal.branch_id,
                *((proposal.vault_id,) if proposal.vault_id is not None else ()),
                proposal.proposal_id,
                *proposal.target_refs,
                *effective_evidence_refs,
            )
            _assert_scope_refs(command, required_scope)

            committed_event_ids = (
                (decision_event_id,)
                if preview.result == "reject"
                else (decision_event_id, effect_event_id)
            )
            unsigned_decision = cast(
                GovernorDecision,
                seal_record(
                    GovernorDecision,
                    {
                        "record_header": record_header(
                            "GovernorDecision",
                            decision_id,
                            identity_id=proposal.identity_id,
                            lineage_id=proposal.lineage_id,
                            branch_id=proposal.branch_id,
                            created_at=trusted_now,
                            created_by_event_id=decision_event_id,
                            deployment_policy_ref=identity.deployment_policy_ref,
                        ),
                        "decision_id": decision_id,
                        "proposal_id": proposal.proposal_id,
                        "identity_id": proposal.identity_id,
                        "lineage_id": proposal.lineage_id,
                        "branch_id": proposal.branch_id,
                        "vault_id": proposal.vault_id,
                        "result": preview.result,
                        "policy_version": policy_version,
                        "input_state_hash": preview.input_state_hash,
                        "reason_codes": preview.reason_codes,
                        "evidence_refs": preview.evidence_refs,
                        "committed_event_ids": committed_event_ids,
                        "output_state_hash": preview.output_state_hash,
                        "decided_at": trusted_now,
                        "governor_signature": "__PENDING_GOVERNOR_ATTESTATION__",
                        "version": 1,
                    },
                ),
            )
            signature = self._decision_attestor.attest(
                decision_content_hash=(
                    unsigned_decision.record_header.content_hash
                ),
                command_hash=execution_context.command_hash,
                actor_id=command.actor.actor_id,
            )
            decision = unsigned_decision.model_copy(
                update={"governor_signature": signature}
            )

            stored_proposal = repository.save_authoritative(
                "proposal",
                preview.proposal_after.model_dump(mode="python"),
            )
            stored_decision = repository.save_authoritative(
                "governor_decision",
                decision.model_dump(mode="python"),
            )
            if not isinstance(stored_proposal, Proposal) or not isinstance(
                stored_decision,
                GovernorDecision,
            ):
                raise TypeError("Governor authority save returned wrong record type")

            stored_memory: AutobiographicalMemory | None = None
            effect: MemoryEffect | None = None
            effect_profile: MemoryProposalProfile | None = None
            if preview.result == "commit":
                if len(preview.memory_effects) != 1:
                    _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
                effect = preview.memory_effects[0]
                memory = _memory_from_effect(
                    effect,
                    proposal=proposal,
                    decision=decision,
                    effect_event_id=effect_event_id,
                    deployment_policy_ref=identity.deployment_policy_ref,
                    target_snapshot=memory_snapshot,
                )
                candidate = repository.save_authoritative(
                    "autobiographical_memory",
                    memory.model_dump(mode="python"),
                )
                if not isinstance(candidate, AutobiographicalMemory):
                    raise TypeError("Memory authority save returned wrong record type")
                stored_memory = candidate
                effect_profile = memory_proposal_profile(proposal.proposal_type)
                if effect.operation != effect_profile.effect_operation:
                    _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
            elif preview.memory_effects:
                _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)

            bound_memory_effect: dict[str, object] | None = None
            if preview.result == "commit":
                if stored_memory is None or effect is None or effect_profile is None:
                    raise TypeError("Commit preview did not materialize Memory")
                bound_memory_effect = {
                    "event_type": effect_profile.event_type,
                    "operation": effect.operation,
                    "decision_id": decision.decision_id,
                    "proposal_id": proposal.proposal_id,
                    "proposal_type": proposal.proposal_type,
                    "memory_id": stored_memory.memory_id,
                    "before_content_hash": effect.before_content_hash,
                    "memory_content_hash": stored_memory.record_header.content_hash,
                    "state": stored_memory.state,
                    "semantic_version": stored_memory.semantic_version,
                    "version": stored_memory.version,
                }
            receipt_output_binding_hash = compute_receipt_output_binding_hash(
                decision_id=decision.decision_id,
                proposal_id=decision.proposal_id,
                proposal_type=proposal.proposal_type,
                result=decision.result,
                committed_event_ids=decision.committed_event_ids,
                proposal_after_content_hash=(
                    stored_proposal.record_header.content_hash
                ),
                memory_effect=bound_memory_effect,
            )
            receipt_output_signature = self._decision_attestor.attest(
                decision_content_hash=receipt_output_attestation_subject_hash(
                    decision_content_hash=decision.record_header.content_hash,
                    output_binding_hash=receipt_output_binding_hash,
                ),
                command_hash=execution_context.command_hash,
                actor_id=command.actor.actor_id,
            )

            writer = _GovernanceEventWriter(
                repository,
                command,
                execution_context,
            )
            causation_id = cast(str | None, command.payload.get("causation_id"))
            if preview.result == "commit":
                decision_event = writer.governor_committed(
                    proposal,
                    stored_proposal,
                    decision,
                    event_id=decision_event_id,
                    instance_id=instance_id,
                    deployment_policy_ref=identity.deployment_policy_ref,
                    causation_id=causation_id,
                    receipt_output_binding_hash=receipt_output_binding_hash,
                    receipt_output_signature=receipt_output_signature,
                )
                if stored_memory is None or effect is None or effect_profile is None:
                    raise TypeError("Commit preview did not materialize Memory")
                if effect_profile.event_type == "memory_created":
                    effect_event = writer.memory_created(
                        proposal,
                        decision,
                        stored_memory,
                        before_content_hash=effect.before_content_hash,
                        event_id=effect_event_id,
                        instance_id=instance_id,
                        deployment_policy_ref=identity.deployment_policy_ref,
                        causation_id=decision_event.event_id,
                    )
                elif effect_profile.event_type == "memory_expression_policy_changed":
                    effect_event = writer.memory_expression_policy_changed(
                        proposal,
                        decision,
                        stored_memory,
                        before_content_hash=effect.before_content_hash,
                        event_id=effect_event_id,
                        instance_id=instance_id,
                        deployment_policy_ref=identity.deployment_policy_ref,
                        causation_id=decision_event.event_id,
                    )
                elif effect_profile.event_type == "memory_state_changed":
                    effect_event = writer.memory_state_changed(
                        proposal,
                        decision,
                        stored_memory,
                        before_content_hash=effect.before_content_hash,
                        event_id=effect_event_id,
                        instance_id=instance_id,
                        deployment_policy_ref=identity.deployment_policy_ref,
                        causation_id=decision_event.event_id,
                    )
                else:
                    _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
                event_ids = (decision_event.event_id, effect_event.event_id)
            elif preview.result == "reject":
                decision_event = writer.governor_rejected(
                    proposal,
                    stored_proposal,
                    decision,
                    event_id=decision_event_id,
                    instance_id=instance_id,
                    deployment_policy_ref=identity.deployment_policy_ref,
                    causation_id=causation_id,
                    receipt_output_binding_hash=receipt_output_binding_hash,
                    receipt_output_signature=receipt_output_signature,
                )
                event_ids = (decision_event.event_id,)
            else:
                conditions = preview.defer_conditions
                if conditions is None:
                    _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
                decision_event = writer.governor_deferred(
                    proposal,
                    decision,
                    event_id=decision_event_id,
                    instance_id=instance_id,
                    deployment_policy_ref=identity.deployment_policy_ref,
                    causation_id=causation_id,
                    receipt_output_binding_hash=receipt_output_binding_hash,
                    receipt_output_signature=receipt_output_signature,
                )
                proposal_event = writer.proposal_deferred(
                    proposal,
                    stored_proposal,
                    decision,
                    conditions,
                    event_id=effect_event_id,
                    instance_id=instance_id,
                    deployment_policy_ref=identity.deployment_policy_ref,
                    causation_id=decision_event.event_id,
                )
                event_ids = (decision_event.event_id, proposal_event.event_id)

            if event_ids != decision.committed_event_ids:
                raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
            return CommandResult[object](
                value=stored_decision.model_dump(mode="json"),
                event_ids=event_ids,
                error=None,
                replayed=False,
            )

        try:
            raw_result = self._unit_of_work.execute_command(
                mutation_command,
                handler,
            )
        except GovernanceViolation as error:
            raw_result = failure_result(mutation_command, error.code)
        except CoreContractViolation as error:
            raw_result = failure_result(mutation_command, error.code)
        except ContentHashMismatch:
            raw_result = failure_result(
                mutation_command,
                CoreErrorCode.HASH_SCOPE_MISMATCH,
            )
        except ValidationError:
            raw_result = failure_result(
                mutation_command,
                CoreErrorCode.GOVERNOR_POLICY_MISMATCH,
            )
        typed = typed_result(
            raw_result,
            GovernorDecision,
            receipt_label="GovernorDecision",
            schema_root="governor_decision",
            expected_record_id=decision_id,
        )
        if typed.value is None:
            return typed
        self._validate_receipt_anchor(
            typed,
            proposal_id=proposal_id,
            mutation_command=mutation_command,
        )
        return typed

    def _validate_receipt_anchor(
        self,
        result: CommandResult[GovernorDecision],
        *,
        proposal_id: str,
        mutation_command: MutationCommandEnvelope,
    ) -> None:
        decision = result.value
        if decision is None:
            return
        if (
            decision.proposal_id != proposal_id
            or result.event_ids != decision.committed_event_ids
            or not result.event_ids
            or len(result.event_ids)
            != ({"commit": 2, "reject": 1, "defer": 2}[decision.result])
        ):
            raise ReceiptIntegrityError(
                "GovernorDecision receipt does not match its declared events"
            )
        connection = self._database.connect()
        try:
            connection.execute("BEGIN")
            repository = AuthorityRepository(connection)
            current = repository.get_validated(decision.decision_id)
            proposal = repository.get_validated(decision.proposal_id)
            replay = repository.validated_ledger_replay(decision.branch_id)
            replay_payloads = cast(
                tuple[Mapping[str, object] | None, ...],
                replay.resolved_inline_payloads,
            )
            replay_decision_ids = {
                candidate_id
                for payload in replay_payloads
                if payload is not None
                for candidate_id in (payload.get("decision_id"),)
                if isinstance(candidate_id, str)
            }
            decision_authorities: dict[str, GovernorDecision] = {}
            for candidate_id in replay_decision_ids:
                candidate = repository.get_validated(candidate_id)
                if isinstance(candidate, GovernorDecision):
                    decision_authorities[candidate_id] = candidate
            target_authorities = (
                {}
                if not isinstance(proposal, Proposal)
                else {
                    target_ref: repository.get_validated(target_ref)
                    for target_ref in proposal.target_refs
                }
            )
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
        if current != decision:
            raise ReceiptIntegrityError(
                "GovernorDecision receipt value does not match authority"
            )
        if not isinstance(proposal, Proposal):
            raise ReceiptIntegrityError(
                "GovernorDecision receipt has no Proposal authority"
            )
        event_payloads = {
            event.event_id: (event, payload)
            for event, payload in zip(
                replay.events,
                replay_payloads,
                strict=True,
            )
        }
        for event_id in result.event_ids:
            if event_id not in event_payloads:
                raise ReceiptIntegrityError(
                    "GovernorDecision receipt names an absent Ledger event"
                )
        decision_event, decision_payload = event_payloads[result.event_ids[0]]
        command_hash = compute_command_hash(mutation_command)
        if not self._decision_attestor.verify(
            decision.governor_signature,
            decision_content_hash=decision.record_header.content_hash,
            command_hash=command_hash,
            actor_id=mutation_command.actor.actor_id,
        ):
            raise ReceiptIntegrityError(
                "GovernorDecision receipt has an invalid keyed attestation"
            )
        decision_scope = (
            decision.identity_id,
            decision.lineage_id,
            decision.branch_id,
            decision.vault_id,
        )
        if (
            proposal.identity_id,
            proposal.lineage_id,
            proposal.branch_id,
            proposal.vault_id,
        ) != decision_scope:
            raise ReceiptIntegrityError(
                "GovernorDecision receipt Proposal scope has changed"
            )
        try:
            historical_evidence_refs = _effective_evidence_refs(
                proposal,
                replay.events,
                replay_payloads,
                through_ledger_seq=decision_event.ledger_seq,
            )
        except GovernanceViolation as error:
            raise ReceiptIntegrityError(
                "GovernorDecision receipt has invalid evidence ancestry"
            ) from error
        if decision.evidence_refs != historical_evidence_refs:
            raise ReceiptIntegrityError(
                "GovernorDecision receipt evidence is not Ledger-anchored"
            )
        if (
            decision_payload is None
            or decision_event.event_type != _DECISION_EVENT_TYPE[decision.result]
            or decision_event.occurred_at != decision.decided_at
            or decision_event.mutation_command_id != mutation_command.command_id
            or not hmac.compare_digest(
                decision_event.mutation_command_hash,
                command_hash,
            )
            or (
                decision_event.identity_id,
                decision_event.lineage_id,
                decision_event.branch_id,
                decision_event.vault_id,
            )
            != decision_scope
            or decision_payload.get("decision_id") != decision.decision_id
            or decision_payload.get("proposal_id") != decision.proposal_id
            or decision_payload.get("result") != decision.result
            or decision_payload.get("input_state_hash")
            != decision.input_state_hash
            or decision_payload.get("output_state_hash")
            != decision.output_state_hash
            or decision_payload.get("decision_content_hash")
            != decision.record_header.content_hash
            or decision_payload.get("governor_signature")
            != decision.governor_signature
            or decision_payload.get("proposal_type") != proposal.proposal_type
            or decision_payload.get("committed_event_ids")
            != decision.committed_event_ids
        ):
            raise ReceiptIntegrityError(
                "GovernorDecision receipt has no immutable decision anchor"
            )
        if decision.result == "defer":
            if len(result.event_ids) != 2:
                raise ReceiptIntegrityError(
                    "Deferred GovernorDecision has no Proposal event"
                )
            proposal_event, proposal_payload = event_payloads[result.event_ids[1]]
            if (
                proposal_payload is None
                or proposal_event.event_type != "proposal_deferred"
                or (
                    proposal_event.identity_id,
                    proposal_event.lineage_id,
                    proposal_event.branch_id,
                    proposal_event.vault_id,
                )
                != decision_scope
                or proposal_payload.get("decision_id") != decision.decision_id
                or proposal_payload.get("proposal_id") != decision.proposal_id
            ):
                raise ReceiptIntegrityError(
                    "Deferred GovernorDecision has no immutable Proposal anchor"
                )
        else:
            proposal_event = decision_event
            proposal_payload = decision_payload
        if not proposal_authority_has_ledger_ancestry(
            proposal,
            historical_event=proposal_event,
            historical_payload=proposal_payload,
            replay_events=replay.events,
            replay_payloads=replay_payloads,
            allow_successors=decision.result == "defer",
            decision_authorities=decision_authorities,
            decision_attestor=self._decision_attestor,
        ):
            raise ReceiptIntegrityError(
                "GovernorDecision receipt does not anchor historical Proposal authority"
            )
        if len(result.event_ids) == 2:
            effect_event, effect_payload = event_payloads[result.event_ids[1]]
            try:
                expected_type = (
                    "proposal_deferred"
                    if decision.result == "defer"
                    else memory_proposal_profile(proposal.proposal_type).event_type
                )
            except CoreContractViolation as error:
                raise ReceiptIntegrityError(
                    "GovernorDecision receipt has an unknown Memory proposal type"
                ) from error
            if (
                effect_payload is None
                or effect_event.event_type != expected_type
                or effect_event.ledger_seq != decision_event.ledger_seq + 1
                or effect_event.causation_id != decision_event.event_id
                or effect_event.occurred_at != decision.decided_at
                or effect_event.mutation_command_id != mutation_command.command_id
                or not hmac.compare_digest(
                    effect_event.mutation_command_hash,
                    command_hash,
                )
                or (
                    effect_event.identity_id,
                    effect_event.lineage_id,
                    effect_event.branch_id,
                    effect_event.vault_id,
                )
                != decision_scope
                or effect_payload.get("decision_id") != decision.decision_id
                or effect_payload.get("proposal_type") != proposal.proposal_type
            ):
                raise ReceiptIntegrityError(
                    "GovernorDecision receipt has no immutable effect anchor"
                )
            if decision.result == "commit":
                memory_id = effect_payload.get("memory_id")
                memory = (
                    target_authorities.get(memory_id)
                    if isinstance(memory_id, str)
                    else None
                )
                if (
                    not isinstance(memory, AutobiographicalMemory)
                    or memory.memory_id not in proposal.target_refs
                    or (
                        memory.identity_id,
                        memory.lineage_id,
                        memory.branch_id,
                        memory.governing_vault_id,
                    )
                    != decision_scope
                    or not memory_authority_has_ledger_ancestry(
                        memory,
                        historical_event=effect_event,
                        historical_payload=effect_payload,
                        replay_events=replay.events,
                        replay_payloads=replay_payloads,
                        decision_authorities=decision_authorities,
                        decision_attestor=self._decision_attestor,
                    )
                ):
                    raise ReceiptIntegrityError(
                        "GovernorDecision receipt does not anchor historical Memory authority"
                    )


__all__ = ["MemoryGovernor"]
