"""Ledger- and decision-proven ancestry for historical Governor receipts."""

from __future__ import annotations

import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from amadeus_core.contracts.errors import CoreContractViolation
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal

from .governor_decision_attestation import GovernorDecisionAttestor
from .memory_proposal_profiles import (
    MEMORY_PROPOSAL_PROFILES,
    MemoryProposalProfile,
    memory_proposal_profile,
)
from .memory_transitions import ALLOWED_MEMORY_TRANSITIONS
from ._receipt_output_binding import (
    receipt_output_attestation_subject_hash,
    receipt_output_binding_from_payloads,
)


_PROPOSAL_EVENT_STATUS = {
    "proposal_deferred": "deferred",
    "proposal_reopened": "pending",
    "proposal_expired": "expired",
    "governor_decision_committed": "committed",
    "governor_decision_rejected": "rejected",
}
_PROPOSAL_TRANSITIONS = frozenset(
    {
        ("pending", "deferred"),
        ("deferred", "pending"),
        ("pending", "expired"),
        ("deferred", "expired"),
        ("pending", "committed"),
        ("pending", "rejected"),
    }
)
_DECISION_EVENT_TYPE = {
    "commit": "governor_decision_committed",
    "reject": "governor_decision_rejected",
    "defer": "governor_decision_deferred",
}
_MEMORY_EFFECT_EVENT_TYPES = frozenset(
    profile.event_type for profile in MEMORY_PROPOSAL_PROFILES.values()
)


@dataclass(frozen=True, slots=True)
class _ProposalAnchor:
    content_hash: str
    version: int
    status: str
    target_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _MemoryAnchor:
    content_hash: str
    version: int
    semantic_version: int
    state: str
    decision_id: str


@dataclass(frozen=True, slots=True)
class _MemoryNode:
    event_id: str
    ledger_seq: int
    anchor: _MemoryAnchor
    profile: MemoryProposalProfile
    proposal_type: str
    before_hash: str | None


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_version(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _event_scope(event: LedgerEvent) -> tuple[str, str, str, str | None]:
    return (
        event.identity_id,
        event.lineage_id,
        event.branch_id,
        event.vault_id,
    )


def _decision_scope(
    decision: GovernorDecision,
) -> tuple[str, str, str, str | None]:
    return (
        decision.identity_id,
        decision.lineage_id,
        decision.branch_id,
        decision.vault_id,
    )


def _proposal_scope(proposal: Proposal) -> tuple[str, str, str, str | None]:
    return (
        proposal.identity_id,
        proposal.lineage_id,
        proposal.branch_id,
        proposal.vault_id,
    )


def _memory_scope(
    memory: AutobiographicalMemory,
) -> tuple[str, str, str, str | None]:
    return (
        memory.identity_id,
        memory.lineage_id,
        memory.branch_id,
        memory.governing_vault_id,
    )


def _sequence_of_strings(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (tuple, list)) or any(
        not isinstance(item, str) for item in value
    ):
        return None
    return tuple(value)


def _events_are_one_governor_pair(
    first: LedgerEvent,
    second: LedgerEvent,
    *,
    expected_scope: tuple[str, str, str, str | None],
) -> bool:
    return (
        first.actor_type == "governor"
        and second.actor_type == "governor"
        and second.ledger_seq == first.ledger_seq + 1
        and second.causation_id == first.event_id
        and second.occurred_at == first.occurred_at
        and second.actor_id == first.actor_id
        and second.instance_id == first.instance_id
        and second.correlation_id == first.correlation_id
        and second.mutation_command_id == first.mutation_command_id
        and hmac.compare_digest(
            second.mutation_command_hash,
            first.mutation_command_hash,
        )
        and _event_scope(first) == expected_scope
        and _event_scope(second) == expected_scope
    )


def _decision_event_is_authenticated(
    event: LedgerEvent,
    payload: Mapping[str, object] | None,
    *,
    expected_result: Literal["commit", "reject", "defer"],
    expected_event_ids: tuple[str, ...],
    expected_scope: tuple[str, str, str, str | None],
    expected_target_refs: tuple[str, ...],
    target_payload: Mapping[str, object],
    decision_authorities: Mapping[str, GovernorDecision],
    decision_attestor: GovernorDecisionAttestor,
    memory_payload: Mapping[str, object] | None = None,
    memory_event_type: str | None = None,
) -> bool:
    if payload is None:
        return False
    decision_id = payload.get("decision_id")
    decision = (
        decision_authorities.get(decision_id)
        if isinstance(decision_id, str)
        else None
    )
    committed_event_ids = _sequence_of_strings(payload.get("committed_event_ids"))
    reason_codes = _sequence_of_strings(payload.get("reason_codes"))
    evidence_refs = _sequence_of_strings(payload.get("evidence_refs"))
    target_refs = _sequence_of_strings(target_payload.get("proposal_target_refs"))
    output_binding_hash = receipt_output_binding_from_payloads(
        payload,
        target_payload,
        result=expected_result,
        committed_event_ids=expected_event_ids,
        memory_payload=memory_payload,
        memory_event_type=memory_event_type,
    )
    stored_output_binding_hash = payload.get("receipt_output_binding_hash")
    receipt_output_signature = payload.get("receipt_output_signature")
    if (
        not isinstance(decision, GovernorDecision)
        or output_binding_hash is None
        or not isinstance(stored_output_binding_hash, str)
        or not hmac.compare_digest(
            output_binding_hash,
            stored_output_binding_hash,
        )
        or not isinstance(receipt_output_signature, str)
        or event.actor_type != "governor"
        or event.event_type != _DECISION_EVENT_TYPE.get(expected_result)
        or committed_event_ids != expected_event_ids
        or target_refs != expected_target_refs
        or _event_scope(event) != expected_scope
        or _decision_scope(decision) != expected_scope
        or decision.record_header.created_by_event_id != event.event_id
        or decision.record_header.created_at != decision.decided_at
        or decision.decision_id != decision_id
        or decision.proposal_id != payload.get("proposal_id")
        or decision.result != expected_result
        or decision.result != payload.get("result")
        or decision.policy_version != payload.get("policy_version")
        or decision.input_state_hash != payload.get("input_state_hash")
        or decision.reason_codes != reason_codes
        or decision.evidence_refs != evidence_refs
        or decision.committed_event_ids != committed_event_ids
        or decision.output_state_hash != payload.get("output_state_hash")
        or decision.decided_at != event.occurred_at
        or decision.record_header.content_hash
        != payload.get("decision_content_hash")
        or decision.governor_signature != payload.get("governor_signature")
    ):
        return False
    return (
        decision_attestor.verify(
            decision.governor_signature,
            decision_content_hash=decision.record_header.content_hash,
            command_hash=event.mutation_command_hash,
            actor_id=event.actor_id,
        )
        and decision_attestor.verify(
            receipt_output_signature,
            decision_content_hash=receipt_output_attestation_subject_hash(
                decision_content_hash=decision.record_header.content_hash,
                output_binding_hash=output_binding_hash,
            ),
            command_hash=event.mutation_command_hash,
            actor_id=event.actor_id,
        )
    )


def _proposal_anchor(
    event: LedgerEvent,
    payload: Mapping[str, object] | None,
    *,
    proposal: Proposal,
) -> _ProposalAnchor | None:
    expected_status = _PROPOSAL_EVENT_STATUS.get(event.event_type)
    if (
        expected_status is None
        or payload is None
        or payload.get("proposal_id") != proposal.proposal_id
        or _event_scope(event) != _proposal_scope(proposal)
    ):
        return None
    before_hash = payload.get("before_proposal_content_hash")
    before_version = payload.get("before_proposal_version")
    before_status = payload.get("before_proposal_status")
    content_hash = payload.get("proposal_content_hash")
    version = payload.get("proposal_version")
    status = payload.get("proposal_status")
    target_refs = _sequence_of_strings(payload.get("proposal_target_refs"))
    if (
        not _is_hash(before_hash)
        or not _is_version(before_version)
        or not isinstance(before_status, str)
        or not _is_hash(content_hash)
        or not _is_version(version)
        or version != before_version + 1
        or status != expected_status
        or (before_status, status) not in _PROPOSAL_TRANSITIONS
        or target_refs is None
        or target_refs != proposal.target_refs
    ):
        return None
    return _ProposalAnchor(content_hash, version, status, target_refs)


def _committed_effect_profile(
    decision_event: LedgerEvent,
    decision_payload: Mapping[str, object] | None,
    effect_event: LedgerEvent,
    effect_payload: Mapping[str, object] | None,
    *,
    expected_scope: tuple[str, str, str, str | None],
    expected_target_refs: tuple[str, ...],
    decision_authorities: Mapping[str, GovernorDecision],
    decision_attestor: GovernorDecisionAttestor,
) -> MemoryProposalProfile | None:
    if decision_payload is None or effect_payload is None:
        return None
    if not _decision_event_is_authenticated(
        decision_event,
        decision_payload,
        expected_result="commit",
        expected_event_ids=(decision_event.event_id, effect_event.event_id),
        expected_scope=expected_scope,
        expected_target_refs=expected_target_refs,
        target_payload=decision_payload,
        decision_authorities=decision_authorities,
        decision_attestor=decision_attestor,
        memory_payload=effect_payload,
        memory_event_type=effect_event.event_type,
    ):
        return None
    proposal_type = effect_payload.get("proposal_type")
    if not isinstance(proposal_type, str):
        return None
    try:
        profile = memory_proposal_profile(proposal_type)
    except CoreContractViolation:
        return None
    if (
        len(expected_target_refs) != 1
        or effect_payload.get("memory_id") != expected_target_refs[0]
        or decision_payload.get("proposal_type") != proposal_type
        or decision_payload.get("decision_id") != effect_payload.get("decision_id")
        or decision_payload.get("proposal_id") != effect_payload.get("proposal_id")
        or effect_event.event_type != profile.event_type
        or not _events_are_one_governor_pair(
            decision_event,
            effect_event,
            expected_scope=expected_scope,
        )
    ):
        return None
    return profile


def _proposal_transition_has_authority(
    index: int,
    event_payloads: Sequence[
        tuple[LedgerEvent, Mapping[str, object] | None]
    ],
    *,
    proposal: Proposal,
    decision_authorities: Mapping[str, GovernorDecision],
    decision_attestor: GovernorDecisionAttestor,
) -> bool:
    event, payload = event_payloads[index]
    if payload is None:
        return False
    scope = _proposal_scope(proposal)
    if event.event_type in {"proposal_reopened", "proposal_expired"}:
        return event.actor_type == "governor"
    if event.event_type == "proposal_deferred":
        if index == 0:
            return False
        decision_event, decision_payload = event_payloads[index - 1]
        return (
            payload.get("decision_id")
            == (
                None
                if decision_payload is None
                else decision_payload.get("decision_id")
            )
            and _events_are_one_governor_pair(
                decision_event,
                event,
                expected_scope=scope,
            )
            and _decision_event_is_authenticated(
                decision_event,
                decision_payload,
                expected_result="defer",
                expected_event_ids=(decision_event.event_id, event.event_id),
                expected_scope=scope,
                expected_target_refs=proposal.target_refs,
                target_payload=payload,
                decision_authorities=decision_authorities,
                decision_attestor=decision_attestor,
            )
        )
    expected_result = {
        "governor_decision_committed": "commit",
        "governor_decision_rejected": "reject",
    }.get(event.event_type)
    if expected_result is None:
        return False
    if expected_result == "reject":
        return _decision_event_is_authenticated(
            event,
            payload,
            expected_result="reject",
            expected_event_ids=(event.event_id,),
            expected_scope=scope,
            expected_target_refs=proposal.target_refs,
            target_payload=payload,
            decision_authorities=decision_authorities,
            decision_attestor=decision_attestor,
        )
    if index + 1 >= len(event_payloads):
        return False
    effect_event, effect_payload = event_payloads[index + 1]
    return (
        _committed_effect_profile(
            event,
            payload,
            effect_event,
            effect_payload,
            expected_scope=scope,
            expected_target_refs=proposal.target_refs,
            decision_authorities=decision_authorities,
            decision_attestor=decision_attestor,
        )
        is not None
    )


def proposal_authority_has_ledger_ancestry(
    proposal: Proposal,
    *,
    historical_event: LedgerEvent,
    historical_payload: Mapping[str, object] | None,
    replay_events: Sequence[LedgerEvent],
    replay_payloads: Sequence[Mapping[str, object] | None],
    allow_successors: bool,
    decision_authorities: Mapping[str, GovernorDecision],
    decision_attestor: GovernorDecisionAttestor,
) -> bool:
    """Prove current Proposal authority descends from authenticated events."""

    event_payloads = tuple(zip(replay_events, replay_payloads, strict=True))
    historical_index = next(
        (
            index
            for index, (event, _payload) in enumerate(event_payloads)
            if event.event_id == historical_event.event_id
        ),
        None,
    )
    anchor = _proposal_anchor(
        historical_event,
        historical_payload,
        proposal=proposal,
    )
    if (
        historical_index is None
        or anchor is None
        or not _proposal_transition_has_authority(
            historical_index,
            event_payloads,
            proposal=proposal,
            decision_authorities=decision_authorities,
            decision_attestor=decision_attestor,
        )
    ):
        return False
    if not allow_successors:
        return (
            proposal.version == anchor.version
            and proposal.status == anchor.status
            and proposal.target_refs == anchor.target_refs
            and hmac.compare_digest(
                proposal.record_header.content_hash,
                anchor.content_hash,
            )
        )

    for index, (event, payload) in enumerate(event_payloads):
        if event.ledger_seq <= historical_event.ledger_seq:
            continue
        if (
            payload is None
            or payload.get("proposal_id") != proposal.proposal_id
            or event.event_type not in _PROPOSAL_EVENT_STATUS
        ):
            continue
        successor = _proposal_anchor(event, payload, proposal=proposal)
        before_hash = payload.get("before_proposal_content_hash")
        if (
            successor is None
            or not isinstance(before_hash, str)
            or payload.get("before_proposal_version") != anchor.version
            or payload.get("before_proposal_status") != anchor.status
            or not hmac.compare_digest(before_hash, anchor.content_hash)
            or not _proposal_transition_has_authority(
                index,
                event_payloads,
                proposal=proposal,
                decision_authorities=decision_authorities,
                decision_attestor=decision_attestor,
            )
        ):
            return False
        anchor = successor

    return (
        proposal.version == anchor.version
        and proposal.status == anchor.status
        and proposal.target_refs == anchor.target_refs
        and hmac.compare_digest(
            proposal.record_header.content_hash,
            anchor.content_hash,
        )
    )


def _memory_anchor(
    event: LedgerEvent,
    payload: Mapping[str, object] | None,
    *,
    memory: AutobiographicalMemory,
) -> _MemoryAnchor | None:
    if (
        event.event_type not in _MEMORY_EFFECT_EVENT_TYPES
        or payload is None
        or payload.get("memory_id") != memory.memory_id
        or _event_scope(event) != _memory_scope(memory)
    ):
        return None
    content_hash = payload.get("memory_content_hash")
    version = payload.get("version")
    semantic_version = payload.get("semantic_version")
    state = payload.get("state")
    decision_id = payload.get("decision_id")
    if (
        not _is_hash(content_hash)
        or not _is_version(version)
        or not _is_version(semantic_version)
        or not isinstance(state, str)
        or not isinstance(decision_id, str)
    ):
        return None
    return _MemoryAnchor(
        content_hash,
        version,
        semantic_version,
        state,
        decision_id,
    )


def _valid_memory_state_semantics(
    profile: MemoryProposalProfile,
    proposal_type: str,
    before_state: str,
    after_state: str,
) -> bool:
    if profile.effect_operation != "update":
        return False
    if proposal_type != "change_memory_state":
        return after_state == before_state
    return after_state != before_state and any(
        source == before_state and target == after_state
        for source, _transition, target in ALLOWED_MEMORY_TRANSITIONS
    )


def memory_authority_has_ledger_ancestry(
    memory: AutobiographicalMemory,
    *,
    historical_event: LedgerEvent,
    historical_payload: Mapping[str, object] | None,
    replay_events: Sequence[LedgerEvent],
    replay_payloads: Sequence[Mapping[str, object] | None],
    decision_authorities: Mapping[str, GovernorDecision],
    decision_attestor: GovernorDecisionAttestor,
) -> bool:
    """Prove current Memory authority is the authenticated terminal state."""

    if len(replay_events) != len(replay_payloads):
        return False
    expected_scope = _memory_scope(memory)
    nodes_by_hash: dict[str, _MemoryNode] = {}
    historical_occurrences = 0
    historical_node_hash: str | None = None
    previous_event: LedgerEvent | None = None
    previous_payload: Mapping[str, object] | None = None

    for event, payload in zip(replay_events, replay_payloads, strict=True):
        decision_event = previous_event
        decision_payload = previous_payload
        previous_event = event
        previous_payload = payload
        if event.event_id == historical_event.event_id:
            historical_occurrences += 1
            if event != historical_event or payload != historical_payload:
                return False
        if (
            payload is None
            or payload.get("memory_id") != memory.memory_id
            or event.event_type not in _MEMORY_EFFECT_EVENT_TYPES
        ):
            continue
        if decision_event is None:
            return False
        anchor = _memory_anchor(event, payload, memory=memory)
        profile = _committed_effect_profile(
            decision_event,
            decision_payload,
            event,
            payload,
            expected_scope=expected_scope,
            expected_target_refs=(memory.memory_id,),
            decision_authorities=decision_authorities,
            decision_attestor=decision_attestor,
        )
        proposal_type = payload.get("proposal_type")
        before_value = payload.get("before_content_hash")
        if (
            anchor is None
            or profile is None
            or not isinstance(proposal_type, str)
            or (before_value is not None and not _is_hash(before_value))
            or anchor.content_hash in nodes_by_hash
        ):
            return False
        before_hash = before_value if isinstance(before_value, str) else None
        nodes_by_hash[anchor.content_hash] = _MemoryNode(
            event.event_id,
            event.ledger_seq,
            anchor,
            profile,
            proposal_type,
            before_hash,
        )
        if event.event_id == historical_event.event_id:
            historical_node_hash = anchor.content_hash

    if (
        historical_occurrences != 1
        or historical_node_hash is None
        or not nodes_by_hash
    ):
        return False

    root_hash: str | None = None
    successor_by_before_hash: dict[str, str] = {}
    for node_hash, node in nodes_by_hash.items():
        if node.before_hash is None:
            if root_hash is not None or not (
                node.profile.effect_operation == "create"
                and node.proposal_type == "create_memory"
                and node.anchor.version == 1
                and node.anchor.semantic_version == 1
                and node.anchor.state == "active"
            ):
                return False
            root_hash = node_hash
            continue

        predecessor = nodes_by_hash.get(node.before_hash)
        if (
            node.profile.effect_operation != "update"
            or predecessor is None
            or predecessor.ledger_seq >= node.ledger_seq
            or node.anchor.version != predecessor.anchor.version + 1
            or node.anchor.semantic_version
            != predecessor.anchor.semantic_version + 1
            or not _valid_memory_state_semantics(
                node.profile,
                node.proposal_type,
                predecessor.anchor.state,
                node.anchor.state,
            )
            or node.before_hash in successor_by_before_hash
        ):
            return False
        successor_by_before_hash[node.before_hash] = node_hash

    if root_hash is None:
        return False

    terminal_hash = memory.record_header.content_hash
    terminal = nodes_by_hash.get(terminal_hash)
    if terminal is None or not (
        memory.version == terminal.anchor.version
        and memory.semantic_version == terminal.anchor.semantic_version
        and memory.state == terminal.anchor.state
        and memory.governor_decision_id == terminal.anchor.decision_id
        and hmac.compare_digest(terminal_hash, terminal.anchor.content_hash)
    ):
        return False

    visited: set[str] = set()
    historical_in_chain = False
    cursor = terminal_hash
    for _step in range(len(nodes_by_hash)):
        node = nodes_by_hash.get(cursor)
        if node is None or cursor in visited:
            return False
        visited.add(cursor)
        if node.event_id == historical_event.event_id:
            historical_in_chain = True
        if node.before_hash is None:
            if cursor != root_hash:
                return False
            break
        cursor = node.before_hash
    else:
        return False

    return historical_in_chain and len(visited) == len(nodes_by_hash)


__all__: list[str] = []
