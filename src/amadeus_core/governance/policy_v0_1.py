"""Pure, versioned Memory Governor policy and semantic hash profiles."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, cast

from pydantic import Field, model_validator

from amadeus_core.contracts.common import (
    DeferConditions,
    FrozenModel,
    HashHex,
    JsonObject,
    RecordId,
)
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.records import reseal_update

from .memory_proposal_profiles import MEMORY_PROPOSAL_TYPES
from .memory_transitions import require_memory_transition


POLICY_VERSION = "governor-v0.1"
GOVERNOR_INPUT_PROFILE = "governor-input-v0.1"
GOVERNOR_OUTPUT_PROFILE = "governor-output-v0.1"

_MEMORY_PROPOSAL_TYPES = MEMORY_PROPOSAL_TYPES
_REQUIRED_EVIDENCE_EVENT_TYPE = "evidence_sealed"
_EMPTY_DEFER_CONDITIONS = DeferConditions(
    missing_evidence_types=(),
    reopen_not_before=None,
)
_TRANSITION_BY_STATES: Mapping[tuple[str, str], str] = MappingProxyType(
    {
        ("active", "contested"): "accepted_correction_or_conflict",
        ("contested", "active"): "evidence_resolved_keep",
        ("contested", "superseded"): "replacement_committed",
        ("active", "superseded"): "replacement_committed",
        ("active", "archived"): "governor_archive",
        ("contested", "archived"): "governor_archive",
        ("superseded", "archived"): "governor_archive",
        ("archived", "active"): "governor_reactivate_with_new_evidence",
    }
)


class EvidenceSnapshot(FrozenModel):
    event_id: RecordId
    event_type: str
    event_hash: HashHex
    ledger_seq: Annotated[int, Field(strict=True, ge=1)]
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId | None
    payload_ref: str
    payload_hash: HashHex
    payload: JsonObject

    @model_validator(mode="after")
    def _payload_is_bound_by_authority_metadata(self) -> "EvidenceSnapshot":
        actual_payload_hash = sha256_hex(canonical_json(self.payload))
        if (
            actual_payload_hash != self.payload_hash
            or self.payload_ref != f"inline:{self.payload_hash}"
        ):
            raise ValueError("evidence payload authority binding mismatch")
        return self


class SourceEventSnapshot(FrozenModel):
    event_id: RecordId
    event_type: str
    event_hash: HashHex
    ledger_seq: Annotated[int, Field(strict=True, ge=1)]
    identity_id: RecordId
    lineage_id: RecordId
    branch_id: RecordId
    vault_id: RecordId | None


class MemoryAuthoritySnapshot(FrozenModel):
    memory_id: RecordId
    version: Annotated[int, Field(strict=True, ge=0)]
    content_hash: HashHex | None
    memory: AutobiographicalMemory | None

    @model_validator(mode="after")
    def _authority_metadata_matches_memory(self) -> "MemoryAuthoritySnapshot":
        if self.memory is None:
            if self.version != 0 or self.content_hash is not None:
                raise ValueError("absent memory must use version zero and no hash")
            return self
        if (
            self.memory.memory_id != self.memory_id
            or self.memory.version != self.version
            or self.memory.record_header.content_hash != self.content_hash
        ):
            raise ValueError("memory authority metadata mismatch")
        return self


class GovernorAuthoritySnapshot(FrozenModel):
    identity_hash: HashHex
    lineage_hash: HashHex
    branch_hash: HashHex
    vault_hash: HashHex | None
    ledger_watermark: Annotated[int, Field(strict=True, ge=0)]
    ledger_root_hash: HashHex
    target_memories: tuple[MemoryAuthoritySnapshot, ...]
    evidence_events: tuple[EvidenceSnapshot, ...]
    source_events: tuple[SourceEventSnapshot, ...]
    effective_evidence_refs: tuple[RecordId, ...] | None = None

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "GovernorAuthoritySnapshot":
        memory_ids = tuple(item.memory_id for item in self.target_memories)
        event_ids = tuple(item.event_id for item in self.evidence_events)
        source_event_ids = tuple(item.event_id for item in self.source_events)
        if len(memory_ids) != len(set(memory_ids)) or len(event_ids) != len(
            set(event_ids)
        ) or len(source_event_ids) != len(set(source_event_ids)):
            raise ValueError("Governor authority snapshot IDs must be unique")
        if set(event_ids) & set(source_event_ids):
            raise ValueError(
                "one Ledger event cannot occupy evidence and source roles"
            )
        if self.effective_evidence_refs is not None and len(
            self.effective_evidence_refs
        ) != len(set(self.effective_evidence_refs)):
            raise ValueError("effective evidence refs must be unique")
        if any(
            item.ledger_seq > self.ledger_watermark
            for item in (*self.evidence_events, *self.source_events)
        ):
            raise ValueError("event position exceeds authority ledger watermark")
        return self


class MemoryEffect(FrozenModel):
    operation: Literal["create", "update"]
    memory_id: RecordId
    before_content_hash: HashHex | None
    after_semantic: JsonObject


class GovernorPreview(FrozenModel):
    result: Literal["commit", "reject", "defer"]
    reason_codes: tuple[str, ...]
    input_state_hash: HashHex
    output_state_hash: HashHex
    defer_conditions: DeferConditions | None
    proposal_after: Proposal
    memory_effects: tuple[MemoryEffect, ...]
    evidence_refs: tuple[RecordId, ...]


def _effective_evidence_refs(
    proposal: Proposal,
    authority_state: GovernorAuthoritySnapshot,
) -> tuple[str, ...]:
    refs = authority_state.effective_evidence_refs
    return proposal.evidence_refs if refs is None else refs


def _canonical_input_descriptor(
    proposal: Proposal,
    authority_state: GovernorAuthoritySnapshot,
    *,
    policy_version: str,
    now: datetime,
) -> dict[str, object]:
    bindings: list[list[object]] = [
        ["Identity", proposal.identity_id, authority_state.identity_hash],
        ["Lineage", proposal.lineage_id, authority_state.lineage_hash],
        ["Branch", proposal.branch_id, authority_state.branch_hash],
    ]
    if proposal.vault_id is not None:
        bindings.append(
            ["RelationshipVault", proposal.vault_id, authority_state.vault_hash]
        )
    return {
        "profile": GOVERNOR_INPUT_PROFILE,
        "policy_version": policy_version,
        "evaluated_at": now,
        "proposal_content_hash": proposal.record_header.content_hash,
        "effective_evidence_refs": _effective_evidence_refs(
            proposal,
            authority_state,
        ),
        "bindings": tuple(bindings),
        "ledger": {
            "branch_id": proposal.branch_id,
            "watermark": authority_state.ledger_watermark,
            "root_hash": authority_state.ledger_root_hash,
        },
        "targets": tuple(
            (
                "AutobiographicalMemory",
                target.memory_id,
                target.version,
                target.content_hash,
            )
            for target in sorted(
                authority_state.target_memories,
                key=lambda item: item.memory_id,
            )
        ),
        "evidence": tuple(
            (
                evidence.event_id,
                evidence.event_type,
                evidence.event_hash,
                evidence.ledger_seq,
                evidence.identity_id,
                evidence.lineage_id,
                evidence.branch_id,
                evidence.vault_id,
                evidence.payload_ref,
                evidence.payload_hash,
            )
            for evidence in sorted(
                authority_state.evidence_events,
                key=lambda item: item.event_id,
            )
        ),
        "source_events": tuple(
            (
                source.event_id,
                source.event_type,
                source.event_hash,
                source.ledger_seq,
                source.identity_id,
                source.lineage_id,
                source.branch_id,
                source.vault_id,
            )
            for source in sorted(
                authority_state.source_events,
                key=lambda item: item.event_id,
            )
        ),
    }


def compute_governor_input_state_hash(
    proposal: Proposal,
    authority_state: GovernorAuthoritySnapshot,
    *,
    policy_version: str,
    now: datetime,
) -> str:
    """Hash the complete, explicitly-timed authority snapshot for preview."""

    return sha256_hex(
        canonical_json(
            _canonical_input_descriptor(
                proposal,
                authority_state,
                policy_version=policy_version,
                now=now,
            )
        )
    )


def compute_governor_output_state_hash(
    *,
    result: Literal["commit", "reject", "defer"],
    reason_codes: tuple[str, ...],
    defer_conditions: DeferConditions | None,
    proposal_after: Proposal,
    memory_effects: tuple[MemoryEffect, ...],
) -> str:
    """Hash semantic output without transport-specific decision or event IDs."""

    descriptor = {
        "profile": GOVERNOR_OUTPUT_PROFILE,
        "result": result,
        "reason_codes": reason_codes,
        "defer_conditions": (
            None
            if defer_conditions is None
            else defer_conditions.model_dump(mode="python")
        ),
        "proposal_after": {
            "proposal_id": proposal_after.proposal_id,
            "content_hash": proposal_after.record_header.content_hash,
            "status": proposal_after.status,
            "deferred_at": proposal_after.deferred_at,
            "defer_conditions": proposal_after.defer_conditions.model_dump(
                mode="python"
            ),
            "reopened_count": proposal_after.reopened_count,
            "version": proposal_after.version,
        },
        "memory_effects": tuple(
            effect.model_dump(mode="python")
            for effect in sorted(memory_effects, key=lambda item: item.memory_id)
        ),
    }
    return sha256_hex(canonical_json(descriptor))


def _project_proposal(
    proposal: Proposal,
    *,
    result: Literal["commit", "reject", "defer"],
    conditions: DeferConditions | None,
    now: datetime,
) -> Proposal:
    if result == "defer":
        updates: dict[str, object] = {
            "status": "deferred",
            "deferred_at": now,
            "defer_conditions": conditions,
            "version": proposal.version + 1,
        }
    else:
        updates = {
            "status": "committed" if result == "commit" else "rejected",
            "deferred_at": None,
            "defer_conditions": _EMPTY_DEFER_CONDITIONS,
            "version": proposal.version + 1,
        }
    return cast(Proposal, reseal_update(proposal, updates))


def _require_current_content_hash(
    record: Proposal | AutobiographicalMemory,
) -> None:
    try:
        computed_hash = compute_record_content_hash(record)
    except (TypeError, ValueError) as error:
        raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH) from error
    if not hmac.compare_digest(record.record_header.content_hash, computed_hash):
        raise CoreContractViolation(CoreErrorCode.HASH_SCOPE_MISMATCH)


def _validate_authority_content_hashes(
    proposal: Proposal,
    authority_state: GovernorAuthoritySnapshot,
) -> None:
    _require_current_content_hash(proposal)
    for target in authority_state.target_memories:
        if target.memory is not None:
            _require_current_content_hash(target.memory)


def _event_scope(
    event: EvidenceSnapshot | SourceEventSnapshot,
) -> tuple[str, str, str, str | None]:
    return (
        event.identity_id,
        event.lineage_id,
        event.branch_id,
        event.vault_id,
    )


def _proposal_scope(proposal: Proposal) -> tuple[str, str, str, str | None]:
    return (
        proposal.identity_id,
        proposal.lineage_id,
        proposal.branch_id,
        proposal.vault_id,
    )


def _validate_referenced_event_scopes(
    proposal: Proposal,
    evidence: tuple[EvidenceSnapshot, ...],
    source_events: tuple[SourceEventSnapshot, ...],
) -> None:
    expected_scope = _proposal_scope(proposal)
    source_by_id = {source.event_id: source for source in source_events}
    for item in evidence:
        if _event_scope(item) != expected_scope:
            raise CoreContractViolation(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        source_ref = item.payload.get("source_event_ref")
        source = source_by_id.get(source_ref) if isinstance(source_ref, str) else None
        if source is not None and _event_scope(source) != expected_scope:
            raise CoreContractViolation(CoreErrorCode.VAULT_SCOPE_MISMATCH)


def _source_event_is_bound(
    evidence: EvidenceSnapshot,
    source_events: tuple[SourceEventSnapshot, ...],
) -> bool:
    source_ref = evidence.payload.get("source_event_ref")
    if not isinstance(source_ref, str):
        return False
    matches = tuple(
        source for source in source_events if source.event_id == source_ref
    )
    return len(matches) == 1 and matches[0].ledger_seq < evidence.ledger_seq


def _target_memory(
    proposal: Proposal,
    authority_state: GovernorAuthoritySnapshot,
) -> MemoryAuthoritySnapshot:
    if len(proposal.target_refs) != 1:
        raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    matches = tuple(
        target
        for target in authority_state.target_memories
        if target.memory_id == proposal.target_refs[0]
    )
    if len(matches) != 1:
        raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    target = matches[0]
    if target.memory is not None and (
        target.memory.identity_id != proposal.identity_id
        or target.memory.lineage_id != proposal.lineage_id
        or target.memory.branch_id != proposal.branch_id
        or target.memory.governing_vault_id != proposal.vault_id
    ):
        raise CoreContractViolation(CoreErrorCode.VAULT_SCOPE_MISMATCH)
    return target


def _validate_memory_effect_shape(
    proposal: Proposal,
    target: MemoryAuthoritySnapshot,
    evidence_refs: tuple[str, ...],
) -> None:
    if proposal.vault_id is None:
        raise CoreContractViolation(CoreErrorCode.VAULT_SCOPE_MISMATCH)
    if proposal.proposal_type == "create_memory":
        if target.memory is not None or target.version != 0:
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        if proposal.proposed_patch.get("state") != "active":
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        patch_evidence_refs = proposal.proposed_patch.get("evidence_event_refs")
        supersedes_memory_ids = proposal.proposed_patch.get(
            "supersedes_memory_ids"
        )
        if (
            not isinstance(patch_evidence_refs, tuple)
            or not set(patch_evidence_refs) <= set(evidence_refs)
            or not isinstance(supersedes_memory_ids, tuple)
            or bool(supersedes_memory_ids)
        ):
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        require_memory_transition("absent", "governor_create", "active")
        return
    if target.memory is None:
        raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
    if proposal.proposal_type == "change_memory_state":
        target_state = proposal.proposed_patch.get("state")
        if not isinstance(target_state, str):
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        if target_state == "superseded":
            # Replacement authority is not part of the M4.2 snapshot contract.
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        transition = _TRANSITION_BY_STATES.get((target.memory.state, target_state))
        if transition is None:
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        require_memory_transition(target.memory.state, transition, target_state)
        contested_refs = proposal.proposed_patch.get("contested_by_event_ids", ())
        if not isinstance(contested_refs, tuple):
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        if target_state == "contested" and evidence_refs and (
            not contested_refs
            or not set(contested_refs) <= set(evidence_refs)
        ):
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
        new_evidence_refs = set(evidence_refs) - set(
            target.memory.evidence_event_refs
        )
        if (target.memory.state, target_state) in {
            ("archived", "active"),
            ("contested", "active"),
        } and not new_evidence_refs:
            raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)


def _build_memory_effect(
    proposal: Proposal,
    target: MemoryAuthoritySnapshot,
    *,
    evidence_refs: tuple[str, ...],
    now: datetime,
) -> MemoryEffect:
    patch = proposal.proposed_patch
    if proposal.proposal_type == "create_memory":
        after: dict[str, object] = {
            "identity_id": proposal.identity_id,
            "lineage_id": proposal.lineage_id,
            "branch_id": proposal.branch_id,
            "governing_vault_id": proposal.vault_id,
            "semantic_kind": patch["semantic_kind"],
            "state": patch["state"],
            "importance": patch["importance"],
            "consolidation_state": patch["consolidation_state"],
            "expression_policy": patch["expression_policy"],
            "evidence_event_refs": evidence_refs,
            "supersedes_memory_ids": patch["supersedes_memory_ids"],
            "contested_by_event_ids": patch["contested_by_event_ids"],
            "semantic_version": 1,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        return MemoryEffect(
            operation="create",
            memory_id=target.memory_id,
            before_content_hash=None,
            after_semantic=after,
        )

    memory = target.memory
    if memory is None:  # guarded by _validate_memory_effect_shape
        raise CoreContractViolation(CoreErrorCode.INVALID_MEMORY_TRANSITION)
    after = memory.model_dump(mode="python")
    del after["record_header"]
    del after["governor_decision_id"]
    if proposal.proposal_type == "change_memory_state":
        after.update(
            {
                "state": patch["state"],
                "supersedes_memory_ids": patch.get(
                    "supersedes_memory_ids", memory.supersedes_memory_ids
                ),
                "contested_by_event_ids": patch.get(
                    "contested_by_event_ids", memory.contested_by_event_ids
                ),
            }
        )
    elif proposal.proposal_type == "change_expression_policy":
        after["expression_policy"] = patch["expression_policy"]
    elif proposal.proposal_type == "set_importance":
        after["importance"] = patch["importance"]
    elif proposal.proposal_type == "set_consolidation":
        after["consolidation_state"] = patch["consolidation_state"]
    else:
        raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    after["evidence_event_refs"] = tuple(
        dict.fromkeys((*memory.evidence_event_refs, *evidence_refs))
    )
    after["semantic_version"] = memory.semantic_version + 1
    after["updated_at"] = now
    after["version"] = memory.version + 1
    return MemoryEffect(
        operation="update",
        memory_id=memory.memory_id,
        before_content_hash=memory.record_header.content_hash,
        after_semantic=after,
    )


def _referenced_evidence(
    evidence_refs: tuple[str, ...],
    evidence: tuple[EvidenceSnapshot, ...],
) -> tuple[EvidenceSnapshot, ...]:
    requested_ids = set(evidence_refs)
    return tuple(item for item in evidence if item.event_id in requested_ids)


def _rejection_reasons(
    evidence: tuple[EvidenceSnapshot, ...],
) -> tuple[str, ...]:
    revoked = any(item.payload.get("attestation_status") == "revoked" for item in evidence)
    invalid_source = any(
        item.payload.get("source_binding_status") == "invalid" for item in evidence
    )
    reasons: list[str] = []
    if revoked:
        reasons.append("ATTESTATION_REVOKED")
    if invalid_source:
        reasons.append("SOURCE_BINDING_INVALID")
    return tuple(reasons)


def _has_commit_evidence(
    proposal: Proposal,
    evidence_refs: tuple[str, ...],
    evidence: tuple[EvidenceSnapshot, ...],
    source_events: tuple[SourceEventSnapshot, ...],
) -> bool:
    requested_ids = set(evidence_refs)
    present_ids = {item.event_id for item in evidence}
    return bool(requested_ids) and present_ids == requested_ids and all(
        item.event_type == _REQUIRED_EVIDENCE_EVENT_TYPE
        and item.payload.get("attestation_status") == "verified"
        and item.payload.get("source_binding_status") == "valid"
        and _source_event_is_bound(item, source_events)
        and item.payload.get("vault_id") == proposal.vault_id
        for item in evidence
    )


class _ImmutablePolicyType(type):
    def __setattr__(cls, name: str, value: object) -> None:
        del name, value
        raise TypeError("Governor policy metadata is immutable")


class GovernorPolicyV01(metaclass=_ImmutablePolicyType):
    """Evaluate one immutable proposal and authority snapshot without I/O."""

    __slots__ = ()
    version: ClassVar[str] = POLICY_VERSION

    def evaluate(
        self,
        proposal: Proposal,
        authority_state: GovernorAuthoritySnapshot,
        *,
        policy_version: str,
        now: datetime,
    ) -> GovernorPreview:
        if policy_version != self.version:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        if now.utcoffset() != timedelta(0):
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        if now < proposal.created_at:
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        _validate_authority_content_hashes(proposal, authority_state)
        if proposal.vault_id is not None and authority_state.vault_hash is None:
            raise CoreContractViolation(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        if proposal.status != "pending" or now >= proposal.expires_at:
            raise CoreContractViolation(CoreErrorCode.PROPOSAL_TERMINAL)
        effective_evidence_refs = _effective_evidence_refs(
            proposal,
            authority_state,
        )
        if not set(proposal.evidence_refs) <= set(effective_evidence_refs):
            raise CoreContractViolation(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
        if proposal.proposal_type not in _MEMORY_PROPOSAL_TYPES:
            result: Literal["commit", "reject", "defer"] = "reject"
            reason_codes = ("SPECIALIZED_COMMITTER_REQUIRED",)
            conditions: DeferConditions | None = None
            effects: tuple[MemoryEffect, ...] = ()
        else:
            target = _target_memory(proposal, authority_state)
            _validate_memory_effect_shape(
                proposal,
                target,
                effective_evidence_refs,
            )
            referenced_evidence = _referenced_evidence(
                effective_evidence_refs,
                authority_state.evidence_events,
            )
            _validate_referenced_event_scopes(
                proposal,
                referenced_evidence,
                authority_state.source_events,
            )
            rejection_reasons = _rejection_reasons(referenced_evidence)
            if rejection_reasons:
                result = "reject"
                reason_codes = rejection_reasons
                conditions = None
                effects = ()
            elif not _has_commit_evidence(
                proposal,
                effective_evidence_refs,
                referenced_evidence,
                authority_state.source_events,
            ):
                result = "defer"
                reason_codes = ("REQUIRED_EVIDENCE_MISSING",)
                conditions = DeferConditions(
                    missing_evidence_types=(_REQUIRED_EVIDENCE_EVENT_TYPE,),
                    reopen_not_before=None,
                )
                effects = ()
            else:
                result = "commit"
                reason_codes = (
                    "EVIDENCE_COMPLETE",
                    "EVIDENCE_ATTESTED",
                    "SOURCE_EVENT_BOUND",
                    "VAULT_BOUND",
                )
                conditions = None
                effects = (
                    _build_memory_effect(
                        proposal,
                        target,
                        evidence_refs=effective_evidence_refs,
                        now=now,
                    ),
                )

        input_hash = compute_governor_input_state_hash(
            proposal,
            authority_state,
            policy_version=policy_version,
            now=now,
        )
        proposal_after = _project_proposal(
            proposal,
            result=result,
            conditions=conditions,
            now=now,
        )
        output_hash = compute_governor_output_state_hash(
            result=result,
            reason_codes=reason_codes,
            defer_conditions=conditions,
            proposal_after=proposal_after,
            memory_effects=effects,
        )
        return GovernorPreview(
            result=result,
            reason_codes=reason_codes,
            input_state_hash=input_hash,
            output_state_hash=output_hash,
            defer_conditions=conditions,
            proposal_after=proposal_after,
            memory_effects=effects,
            evidence_refs=effective_evidence_refs,
        )


__all__ = [
    "EvidenceSnapshot",
    "GOVERNOR_INPUT_PROFILE",
    "GOVERNOR_OUTPUT_PROFILE",
    "GovernorAuthoritySnapshot",
    "GovernorPolicyV01",
    "GovernorPreview",
    "MemoryAuthoritySnapshot",
    "MemoryEffect",
    "POLICY_VERSION",
    "SourceEventSnapshot",
    "compute_governor_input_state_hash",
    "compute_governor_output_state_hash",
]
