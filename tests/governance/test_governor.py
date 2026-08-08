from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

import amadeus_core.governance.policy_v0_1 as policy_module
from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import Proposal
from amadeus_core.governance.policy_v0_1 import (
    POLICY_VERSION,
    EvidenceSnapshot,
    GovernorAuthoritySnapshot,
    GovernorPolicyV01,
    MemoryAuthoritySnapshot,
    SourceEventSnapshot,
    compute_governor_input_state_hash,
    compute_governor_output_state_hash,
)
from amadeus_core.storage.records import record_header, reseal_update, seal_record


NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
VAULT_ID = "vlt-a1"
MEMORY_ID = "mem-a1"
EVIDENCE_EVENT_ID = "evt-a2"


def _header(record_type: str, record_id: str, created_by: str) -> dict[str, object]:
    return record_header(
        record_type,
        record_id,
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        created_at=NOW,
        created_by_event_id=created_by,
        deployment_policy_ref="deployment:test",
    )


def _active_memory() -> AutobiographicalMemory:
    return seal_record(
        AutobiographicalMemory,
        {
            "record_header": _header(
                "AutobiographicalMemory",
                MEMORY_ID,
                "evt-a1",
            ),
            "memory_id": MEMORY_ID,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "governing_vault_id": VAULT_ID,
            "semantic_kind": "episode",
            "state": "active",
            "importance": 0.5,
            "consolidation_state": "candidate",
            "expression_policy": {"mode": "eligible", "reason_refs": ()},
            "evidence_event_refs": ("evt-a1",),
            "supersedes_memory_ids": (),
            "contested_by_event_ids": (),
            "governor_decision_id": "gvd-a1",
            "semantic_version": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "version": 1,
        },
    )


def _proposal(*, evidence_refs: tuple[str, ...]) -> Proposal:
    return seal_record(
        Proposal,
        {
            "record_header": _header("Proposal", "prp-a1", "evt-a1"),
            "proposal_id": "prp-a1",
            "proposal_type": "change_memory_state",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": "llm-a1"},
            "target_refs": (MEMORY_ID,),
            "evidence_refs": evidence_refs,
            "proposed_patch": {
                "state": "contested",
                "supersedes_memory_ids": (),
                "contested_by_event_ids": evidence_refs,
            },
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=1),
            "status": "pending",
            "deferred_at": None,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": None,
            },
            "reopened_count": 0,
            "version": 1,
        },
    )


def _create_proposal(
    *,
    patch_evidence_refs: tuple[str, ...] = (EVIDENCE_EVENT_ID,),
    supersedes_memory_ids: tuple[str, ...] = (),
) -> Proposal:
    memory_id = "mem-ca1"
    return seal_record(
        Proposal,
        {
            "record_header": _header("Proposal", "prp-ca1", "evt-a1"),
            "proposal_id": "prp-ca1",
            "proposal_type": "create_memory",
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "proposed_by": {"actor_type": "llm", "actor_id": "llm-a1"},
            "target_refs": (memory_id,),
            "evidence_refs": (EVIDENCE_EVENT_ID,),
            "proposed_patch": {
                "memory_id": memory_id,
                "semantic_kind": "episode",
                "state": "active",
                "importance": 0.5,
                "consolidation_state": "candidate",
                "expression_policy": {"mode": "eligible", "reason_refs": ()},
                "evidence_event_refs": patch_evidence_refs,
                "supersedes_memory_ids": supersedes_memory_ids,
                "contested_by_event_ids": (),
            },
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=1),
            "status": "pending",
            "deferred_at": None,
            "defer_conditions": {
                "missing_evidence_types": (),
                "reopen_not_before": None,
            },
            "reopened_count": 0,
            "version": 1,
        },
    )


def _evidence(
    *,
    rejected: bool = False,
    event_id: str = EVIDENCE_EVENT_ID,
    ledger_seq: int = 2,
    source_event_ref: str = "evt-a1",
) -> EvidenceSnapshot:
    payload = (
        {
            "attestation_status": "revoked",
            "source_binding_status": "invalid",
            "source_event_ref": source_event_ref,
            "vault_id": VAULT_ID,
        }
        if rejected
        else {
            "attestation_status": "verified",
            "source_binding_status": "valid",
            "source_event_ref": source_event_ref,
            "vault_id": VAULT_ID,
        }
    )
    payload_hash = sha256_hex(canonical_json(payload))
    return EvidenceSnapshot(
        event_id=event_id,
        event_type="evidence_sealed",
        event_hash=payload_hash,
        ledger_seq=ledger_seq,
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        vault_id=VAULT_ID,
        payload_ref=f"inline:{payload_hash}",
        payload_hash=payload_hash,
        payload=payload,
    )


def _source_event(
    *,
    event_id: str = "evt-a1",
    ledger_seq: int = 1,
    vault_id: str | None = VAULT_ID,
) -> SourceEventSnapshot:
    return SourceEventSnapshot(
        event_id=event_id,
        event_type="conversation_message_recorded",
        event_hash="6" * 64,
        ledger_seq=ledger_seq,
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        vault_id=vault_id,
    )


def _snapshot(
    *,
    evidence: tuple[EvidenceSnapshot, ...],
    memory: AutobiographicalMemory | None = None,
    source_events: tuple[SourceEventSnapshot, ...] | None = None,
    ledger_watermark: int = 3,
) -> GovernorAuthoritySnapshot:
    memory = memory or _active_memory()
    if source_events is None:
        source_events = (_source_event(),)
    return GovernorAuthoritySnapshot(
        identity_hash="1" * 64,
        lineage_hash="2" * 64,
        branch_hash="3" * 64,
        vault_hash="4" * 64,
        ledger_watermark=ledger_watermark,
        ledger_root_hash="5" * 64,
        target_memories=(
            MemoryAuthoritySnapshot(
                memory_id=memory.memory_id,
                version=memory.version,
                content_hash=memory.record_header.content_hash,
                memory=memory,
            ),
        ),
        evidence_events=evidence,
        source_events=source_events,
    )


def _absent_memory_snapshot(
    proposal: Proposal,
    *,
    evidence: tuple[EvidenceSnapshot, ...],
) -> GovernorAuthoritySnapshot:
    return GovernorAuthoritySnapshot(
        identity_hash="1" * 64,
        lineage_hash="2" * 64,
        branch_hash="3" * 64,
        vault_hash="4" * 64,
        ledger_watermark=3,
        ledger_root_hash="5" * 64,
        target_memories=(
            MemoryAuthoritySnapshot(
                memory_id=proposal.target_refs[0],
                version=0,
                content_hash=None,
                memory=None,
            ),
        ),
        evidence_events=evidence,
        source_events=(_source_event(),),
    )


def test_create_commit_closes_authoritative_evidence_into_memory_provenance() -> None:
    proposal = _create_proposal(patch_evidence_refs=())

    preview = GovernorPolicyV01().evaluate(
        proposal,
        _absent_memory_snapshot(proposal, evidence=(_evidence(),)),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert preview.result == "commit"
    assert tuple(preview.memory_effects[0].after_semantic["evidence_event_refs"]) == (
        EVIDENCE_EVENT_ID,
    )


def test_create_policy_rejects_unatomic_replacement() -> None:
    proposal = _create_proposal(supersedes_memory_ids=("mem-da1",))

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _absent_memory_snapshot(proposal, evidence=(_evidence(),)),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION


def test_commit_reject_defer_matrix_is_derived_from_authority_evidence() -> None:
    policy = GovernorPolicyV01()
    evidenced = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    incomplete = _proposal(evidence_refs=())

    committed = policy.evaluate(
        evidenced,
        _snapshot(evidence=(_evidence(),)),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    rejected = policy.evaluate(
        evidenced,
        _snapshot(evidence=(_evidence(rejected=True),)),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    deferred = policy.evaluate(
        incomplete,
        _snapshot(evidence=()),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert (committed.result, rejected.result, deferred.result) == (
        "commit",
        "reject",
        "defer",
    )
    assert committed.reason_codes == (
        "EVIDENCE_COMPLETE",
        "EVIDENCE_ATTESTED",
        "SOURCE_EVENT_BOUND",
        "VAULT_BOUND",
    )
    assert rejected.reason_codes == (
        "ATTESTATION_REVOKED",
        "SOURCE_BINDING_INVALID",
    )
    assert deferred.reason_codes == ("REQUIRED_EVIDENCE_MISSING",)
    assert deferred.defer_conditions == DeferConditions(
        missing_evidence_types=("evidence_sealed",),
        reopen_not_before=None,
    )


def test_preview_is_pure_deterministic_and_uses_versioned_hash_profiles() -> None:
    policy = GovernorPolicyV01()
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    snapshot = _snapshot(evidence=(_evidence(),))
    proposal_before = proposal.model_dump(mode="python")
    snapshot_before = snapshot.model_dump(mode="python")

    first = policy.evaluate(
        proposal,
        snapshot,
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    second = policy.evaluate(
        proposal,
        snapshot,
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert first == second
    assert proposal.model_dump(mode="python") == proposal_before
    assert snapshot.model_dump(mode="python") == snapshot_before
    assert first.input_state_hash == compute_governor_input_state_hash(
        proposal,
        snapshot,
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    assert first.output_state_hash == compute_governor_output_state_hash(
        result=first.result,
        reason_codes=first.reason_codes,
        defer_conditions=first.defer_conditions,
        proposal_after=first.proposal_after,
        memory_effects=first.memory_effects,
    )
    assert first.proposal_after.status == "committed"
    assert first.proposal_after.version == proposal.version + 1
    assert first.memory_effects[0].memory_id == MEMORY_ID
    assert first.memory_effects[0].after_semantic["state"] == "contested"
    assert first.output_state_hash != first.proposal_after.record_header.content_hash


def test_evidence_payload_must_match_its_authority_bound_hash() -> None:
    valid = _evidence()
    rebound = valid.model_dump(mode="python")
    rebound["payload"] = {
        "attestation_status": "revoked",
        "source_binding_status": "invalid",
        "source_event_ref": "evt-a1",
        "vault_id": VAULT_ID,
    }

    with pytest.raises(ValidationError):
        EvidenceSnapshot.model_validate(rebound)


def test_unreferenced_revoked_evidence_cannot_poison_a_commit() -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    preview = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(
            evidence=(
                _evidence(),
                _evidence(rejected=True, event_id="evt-a3"),
            )
        ),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert preview.result == "commit"


def test_every_referenced_evidence_event_must_be_present_before_commit() -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID, "evt-a3"))
    preview = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(evidence=(_evidence(),)),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert preview.result == "defer"
    assert preview.reason_codes == ("REQUIRED_EVIDENCE_MISSING",)


def test_policy_version_is_immutable() -> None:
    policy = GovernorPolicyV01()

    with pytest.raises((AttributeError, TypeError)):
        policy.version = "attacker-policy"  # type: ignore[misc]


def test_contested_commit_requires_a_contesting_evidence_reference() -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    invalid = reseal_update(
        proposal,
        {
            "proposed_patch": {
                "state": "contested",
                "supersedes_memory_ids": (),
                "contested_by_event_ids": (),
            }
        },
    )

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            invalid,
            _snapshot(evidence=(_evidence(),)),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION


def test_memory_update_merges_new_evidence_into_authority_effect() -> None:
    preview = GovernorPolicyV01().evaluate(
        _proposal(evidence_refs=(EVIDENCE_EVENT_ID,)),
        _snapshot(evidence=(_evidence(),)),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert preview.result == "commit"
    assert tuple(preview.memory_effects[0].after_semantic["evidence_event_refs"]) == (
        "evt-a1",
        EVIDENCE_EVENT_ID,
    )


def test_archived_reactivation_requires_evidence_new_to_the_memory() -> None:
    archived = reseal_update(_active_memory(), {"state": "archived"})
    proposal = reseal_update(
        _proposal(evidence_refs=("evt-a1",)),
        {
            "proposed_patch": {
                "state": "active",
                "supersedes_memory_ids": (),
                "contested_by_event_ids": (),
            }
        },
    )

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _snapshot(
                evidence=(
                    _evidence(
                        event_id="evt-a1",
                        source_event_ref="evt-a0",
                    ),
                ),
                memory=archived,
                source_events=(_source_event(event_id="evt-a0"),),
            ),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION


def test_authority_snapshot_rejects_one_event_in_evidence_and_source_roles() -> None:
    with pytest.raises(ValidationError):
        GovernorAuthoritySnapshot(
            identity_hash="1" * 64,
            lineage_hash="2" * 64,
            branch_hash="3" * 64,
            vault_hash="4" * 64,
            ledger_watermark=3,
            ledger_root_hash="5" * 64,
            target_memories=(),
            evidence_events=(_evidence(event_id="evt-a1"),),
            source_events=(_source_event(),),
        )


@pytest.mark.parametrize("tampered_record", ("proposal", "memory"))
def test_policy_recomputes_proposal_and_memory_authority_hashes(
    tampered_record: str,
) -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    memory = _active_memory()
    if tampered_record == "proposal":
        body = proposal.model_dump(mode="python")
        body["expires_at"] = proposal.expires_at + timedelta(days=1)
        proposal = Proposal.model_validate(body)
    else:
        body = memory.model_dump(mode="python")
        body["importance"] = 0.75
        memory = AutobiographicalMemory.model_validate(body)

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _snapshot(evidence=(_evidence(),), memory=memory),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.HASH_SCOPE_MISMATCH


def test_source_event_must_exist_and_match_proposal_scope() -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    missing = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(evidence=(_evidence(),), source_events=()),
        policy_version=POLICY_VERSION,
        now=NOW,
    )

    assert missing.result == "defer"
    assert "SOURCE_EVENT_BOUND" not in missing.reason_codes

    cross_scope_source = SourceEventSnapshot(
        event_id="evt-a1",
        event_type="conversation_message_recorded",
        event_hash="6" * 64,
        ledger_seq=1,
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        vault_id="vlt-b1",
    )
    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _snapshot(
                evidence=(_evidence(),),
                source_events=(cross_scope_source,),
            ),
            policy_version=POLICY_VERSION,
            now=NOW,
    )

    assert captured.value.code is CoreErrorCode.VAULT_SCOPE_MISMATCH

    late_source = _source_event(ledger_seq=2)
    late = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(
            evidence=(_evidence(ledger_seq=2),),
            source_events=(late_source,),
        ),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    assert late.result == "defer"
    assert "SOURCE_EVENT_BOUND" not in late.reason_codes

    initial_positions = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(
            evidence=(_evidence(ledger_seq=2),),
            source_events=(_source_event(ledger_seq=1),),
            ledger_watermark=3,
        ),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    evidence_position_changed = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(
            evidence=(_evidence(ledger_seq=3),),
            source_events=(_source_event(ledger_seq=1),),
            ledger_watermark=3,
        ),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    source_position_changed = GovernorPolicyV01().evaluate(
        proposal,
        _snapshot(
            evidence=(_evidence(ledger_seq=3),),
            source_events=(_source_event(ledger_seq=2),),
            ledger_watermark=3,
        ),
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    assert (
        initial_positions.result,
        evidence_position_changed.result,
        source_position_changed.result,
    ) == ("commit", "commit", "commit")
    assert initial_positions.input_state_hash != evidence_position_changed.input_state_hash
    assert (
        evidence_position_changed.input_state_hash
        != source_position_changed.input_state_hash
    )


def test_vault_bound_proposal_requires_vault_authority_hash() -> None:
    snapshot = _snapshot(evidence=(_evidence(),))
    missing_vault = snapshot.model_copy(update={"vault_hash": None})

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            _proposal(evidence_refs=(EVIDENCE_EVENT_ID,)),
            missing_vault,
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.VAULT_SCOPE_MISMATCH


def test_runtime_policy_metadata_mutation_cannot_change_a_decision() -> None:
    proposal = _proposal(evidence_refs=(EVIDENCE_EVENT_ID,))
    snapshot = _snapshot(evidence=(_evidence(),))
    baseline = GovernorPolicyV01().evaluate(
        proposal,
        snapshot,
        policy_version=POLICY_VERSION,
        now=NOW,
    )
    original_version = GovernorPolicyV01.version
    edge = ("active", "contested")
    original_transition = policy_module._TRANSITION_BY_STATES[edge]
    version_mutated = False
    transition_mutated = False
    try:
        try:
            GovernorPolicyV01.version = "attacker-policy"  # type: ignore[misc]
            version_mutated = True
        except (AttributeError, TypeError):
            pass
        try:
            policy_module._TRANSITION_BY_STATES[edge] = "governor_archive"
            transition_mutated = True
        except TypeError:
            pass

        repeated = GovernorPolicyV01().evaluate(
            proposal,
            snapshot,
            policy_version=POLICY_VERSION,
            now=NOW,
        )
    finally:
        if version_mutated:
            GovernorPolicyV01.version = original_version  # type: ignore[misc]
        if transition_mutated:
            policy_module._TRANSITION_BY_STATES[edge] = original_transition

    assert repeated == baseline


def test_active_to_superseded_rejects_generic_evidence_without_replacement() -> None:
    proposal = reseal_update(
        _proposal(evidence_refs=(EVIDENCE_EVENT_ID,)),
        {
            "proposed_patch": {
                "state": "superseded",
                "supersedes_memory_ids": (),
                "contested_by_event_ids": (),
            }
        },
    )

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _snapshot(evidence=(_evidence(),)),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION


def test_contested_resolution_requires_evidence_new_to_the_memory() -> None:
    contested = reseal_update(
        _active_memory(),
        {
            "state": "contested",
            "evidence_event_refs": ("evt-a1", EVIDENCE_EVENT_ID),
            "contested_by_event_ids": (EVIDENCE_EVENT_ID,),
        },
    )
    proposal = reseal_update(
        _proposal(evidence_refs=(EVIDENCE_EVENT_ID,)),
        {
            "proposed_patch": {
                "state": "active",
                "supersedes_memory_ids": (),
                "contested_by_event_ids": (),
            }
        },
    )

    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            proposal,
            _snapshot(evidence=(_evidence(),), memory=contested),
            policy_version=POLICY_VERSION,
            now=NOW,
        )

    assert captured.value.code is CoreErrorCode.INVALID_MEMORY_TRANSITION


def test_policy_rejects_evaluation_before_proposal_creation() -> None:
    with pytest.raises(CoreContractViolation) as captured:
        GovernorPolicyV01().evaluate(
            _proposal(evidence_refs=(EVIDENCE_EVENT_ID,)),
            _snapshot(evidence=(_evidence(),)),
            policy_version=POLICY_VERSION,
            now=NOW - timedelta(seconds=1),
        )

    assert captured.value.code is CoreErrorCode.GOVERNOR_POLICY_MISMATCH
