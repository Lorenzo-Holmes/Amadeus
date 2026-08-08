"""Closed validation and read rules for Proposal lifecycle transitions."""

from __future__ import annotations

import hmac
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import cast, get_args

from pydantic import ValidationError

from amadeus_core.contracts.commands import MutationCommandEnvelope
from amadeus_core.contracts.common import DeferConditions
from amadeus_core.contracts.errors import CoreContractViolation, CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.memory import AutobiographicalMemory
from amadeus_core.contracts.proposals import GovernorDecision, Proposal
from amadeus_core.contracts.registry import TYPE_REGISTRY
from amadeus_core.contracts.validation import (
    ContentHashMismatch,
    validate_authoritative_record,
)
from amadeus_core.contracts.vault import RelationshipVault
from amadeus_core.contracts.write_api_registry_v0_1 import WRITE_API_BY_NAME
from amadeus_core.storage.ledger import LedgerReplayResult
from amadeus_core.storage.records import reseal_update
from amadeus_core.storage.reader import ProposalAuthorityBinding
from amadeus_core.storage.repository import AuthorityRepository

from ._service import GovernanceViolation
from .memory_proposal_profiles import MEMORY_PROPOSAL_TYPES

_TERMINAL_PROPOSAL_STATES = frozenset({"committed", "rejected", "expired"})
_MEMORY_PROPOSAL_TYPES = MEMORY_PROPOSAL_TYPES
_EMPTY_DEFER_CONDITIONS = DeferConditions(
    missing_evidence_types=(),
    reopen_not_before=None,
)
_PATCH_FIELDS_BY_TYPE = {
    "create_memory": frozenset(
        {
            "memory_id",
            "semantic_kind",
            "state",
            "importance",
            "consolidation_state",
            "expression_policy",
            "evidence_event_refs",
            "supersedes_memory_ids",
            "contested_by_event_ids",
        }
    ),
    "change_memory_state": frozenset(
        {"state", "supersedes_memory_ids", "contested_by_event_ids"}
    ),
    "change_expression_policy": frozenset({"expression_policy"}),
    "set_importance": frozenset({"importance"}),
    "set_consolidation": frozenset({"consolidation_state"}),
    "lifecycle_transition": frozenset(
        {"lifecycle_state", "requested_action", "reason_refs"}
    ),
    "maintenance_trigger": frozenset(
        {"requested_action", "reason_code", "scope_refs"}
    ),
}
_TARGET_TYPES_BY_PROPOSAL = {
    "create_memory": (AutobiographicalMemory,),
    "change_memory_state": (AutobiographicalMemory,),
    "change_expression_policy": (AutobiographicalMemory,),
    "set_importance": (AutobiographicalMemory,),
    "set_consolidation": (AutobiographicalMemory,),
    "lifecycle_transition": (Identity, Branch, RelationshipVault),
    "maintenance_trigger": (Identity, Branch),
}
_LEDGER_EVENT_TYPES = frozenset(
    get_args(LedgerEvent.model_fields["event_type"].annotation)
)
_FORBIDDEN_PATCH_KEYS = frozenset(
    {
        "command",
        "credential",
        "database_command",
        "private_key",
        "query",
        "raw_key",
        "sql",
        "token",
    }
)


def _datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _fail(code: CoreErrorCode) -> None:
    raise GovernanceViolation(code)


def _validate_record_id(value: object, prefix: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        _fail(CoreErrorCode.RECORD_ID_MISMATCH)
    return value


def _sequence_of_strings(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or any(not isinstance(item, str) for item in value)
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    return tuple(cast(Sequence[str], value))


def _assert_closed_payload(
    command: MutationCommandEnvelope,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    fields = frozenset(command.payload)
    if not required <= fields or not fields <= required | optional:
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)


def _normalized_expected_versions(
    command: MutationCommandEnvelope,
) -> dict[str, int]:
    normalized = {
        item.target_record_ref: (
            0 if item.expected_version == "absent" else item.expected_version
        )
        for item in command.expected_versions
    }
    if (
        len(normalized) != len(command.expected_versions)
        or len(set(command.target_record_refs)) != len(command.target_record_refs)
        or set(normalized) != set(command.target_record_refs)
    ):
        _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    return normalized


def _assert_scope_refs(
    command: MutationCommandEnvelope,
    required: tuple[str, ...],
) -> None:
    supplied = _sequence_of_strings(command.payload.get("scope_refs"))
    if supplied != required:
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)


def _validated_authorities(
    repository: AuthorityRepository,
    proposal: Proposal,
) -> tuple[Identity, Lineage, Branch, RelationshipVault | None]:
    identity = repository.get_validated(proposal.identity_id)
    lineage = repository.get_validated(proposal.lineage_id)
    branch = repository.get_validated(proposal.branch_id)
    if (
        not isinstance(identity, Identity)
        or not isinstance(lineage, Lineage)
        or not isinstance(branch, Branch)
        or identity.lineage_id != proposal.lineage_id
        or identity.active_branch_id != proposal.branch_id
        or identity.lifecycle_state != "active"
        or lineage.root_identity_id != proposal.identity_id
        or branch.identity_id != proposal.identity_id
        or branch.lineage_id != proposal.lineage_id
        or branch.status != "active"
    ):
        _fail(CoreErrorCode.ACTIVE_BRANCH_INVARIANT)
    vault: RelationshipVault | None = None
    if proposal.vault_id is not None:
        candidate = repository.get_validated(proposal.vault_id)
        if (
            not isinstance(candidate, RelationshipVault)
            or candidate.identity_id != proposal.identity_id
            or candidate.lineage_id != proposal.lineage_id
            or candidate.branch_id != proposal.branch_id
            or candidate.status == "sealed"
        ):
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        vault = candidate
    if (
        proposal.record_header.deployment_policy_ref
        != identity.deployment_policy_ref
    ):
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    return identity, lineage, branch, vault


def _validate_reference(
    repository: AuthorityRepository,
    proposal: Proposal,
    reference: str,
    *,
    must_be_event: bool,
    allow_absent_memory: bool,
) -> None:
    record = repository.get_validated(reference)
    if record is None:
        if allow_absent_memory and reference.startswith(
            TYPE_REGISTRY["AutobiographicalMemory"].id_prefix
        ):
            return
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if must_be_event and not isinstance(record, LedgerEvent):
        _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
    if not must_be_event and not isinstance(
        record,
        _TARGET_TYPES_BY_PROPOSAL[proposal.proposal_type],
    ):
        _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
    if (
        record.record_header.identity_id != proposal.identity_id
        or record.record_header.lineage_id != proposal.lineage_id
        or record.record_header.branch_id != proposal.branch_id
    ):
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
    record_vault_id = getattr(record, "vault_id", None)
    governing_vault_id = getattr(record, "governing_vault_id", None)
    effective_vault_id = (
        governing_vault_id if governing_vault_id is not None else record_vault_id
    )
    if effective_vault_id not in (None, proposal.vault_id):
        _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)


def _contains_forbidden_patch_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = key.casefold().replace("-", "_")
            if normalized in _FORBIDDEN_PATCH_KEYS or (
                any(part in _FORBIDDEN_PATCH_KEYS for part in normalized.split("_"))
            ):
                return True
            if _contains_forbidden_patch_key(item):
                return True
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return any(_contains_forbidden_patch_key(item) for item in value)
    return False


def _validate_patch(
    proposal: Proposal,
    command: MutationCommandEnvelope,
) -> None:
    keys = frozenset(proposal.proposed_patch)
    allowed = _PATCH_FIELDS_BY_TYPE[proposal.proposal_type]
    if (
        not keys
        or not keys <= allowed
        or _contains_forbidden_patch_key(proposal.proposed_patch)
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)

    scope_refs = set(_sequence_of_strings(command.payload.get("scope_refs")))
    evidence_refs = set(proposal.evidence_refs)
    target_refs = set(proposal.target_refs)

    def references(
        field_name: str,
        *,
        prefix: str,
        required: bool = False,
    ) -> tuple[str, ...]:
        if field_name not in proposal.proposed_patch:
            if required:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            return ()
        values = _sequence_of_strings(proposal.proposed_patch.get(field_name))
        if any(not value.startswith(prefix) for value in values):
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        return values

    def evidence_references(value: object) -> tuple[str, ...]:
        values = _sequence_of_strings(value)
        if any(not value.startswith("evt-") for value in values):
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        if not set(values) <= evidence_refs:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if not set(values) <= scope_refs:
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        return values

    proposal_type = proposal.proposal_type
    if proposal_type == "create_memory":
        required = _PATCH_FIELDS_BY_TYPE["create_memory"]
        if keys != required:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        memory_id = proposal.proposed_patch.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id.startswith(
            TYPE_REGISTRY["AutobiographicalMemory"].id_prefix
        ):
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        if proposal.target_refs != (memory_id,):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        evidence = evidence_references(
            proposal.proposed_patch.get("evidence_event_refs")
        )
        supersedes = references("supersedes_memory_ids", prefix="mem-", required=True)
        contested = references("contested_by_event_ids", prefix="evt-", required=True)
        if not set(contested) <= evidence_refs:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        expression_policy = proposal.proposed_patch.get("expression_policy")
        if not isinstance(expression_policy, Mapping):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        reason_refs = evidence_references(expression_policy.get("reason_refs"))
        if frozenset(expression_policy) != {"mode", "reason_refs"} or (
            expression_policy.get("mode")
            not in {"eligible", "restricted", "non_mention", "silent"}
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        patch_refs = {
            memory_id,
            *evidence,
            *supersedes,
            *contested,
            *reason_refs,
        }
        if not patch_refs <= scope_refs:
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        importance = proposal.proposed_patch.get("importance")
        if (
            isinstance(importance, bool)
            or not isinstance(importance, (int, float))
            or not math.isfinite(float(importance))
            or not 0.0 <= float(importance) <= 1.0
            or proposal.proposed_patch.get("state") != "active"
            or proposal.proposed_patch.get("semantic_kind")
            not in {
                "episode",
                "relationship",
                "preference",
                "commitment",
                "self_model",
                "other",
            }
            or proposal.proposed_patch.get("consolidation_state")
            not in {"candidate", "consolidated", "stable", "decayed"}
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        return

    if proposal_type == "change_memory_state":
        if "state" not in keys or proposal.proposed_patch.get("state") not in {
            "active",
            "contested",
            "superseded",
            "archived",
        }:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        supersedes = references("supersedes_memory_ids", prefix="mem-")
        contested = references("contested_by_event_ids", prefix="evt-")
        if not set(supersedes) <= target_refs or not set(contested) <= evidence_refs:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if not set((*supersedes, *contested)) <= scope_refs:
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        return

    if proposal_type == "change_expression_policy":
        if keys != {"expression_policy"}:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        expression_policy = proposal.proposed_patch.get("expression_policy")
        if (
            not isinstance(expression_policy, Mapping)
            or frozenset(expression_policy) != {"mode", "reason_refs"}
            or expression_policy.get("mode")
            not in {"eligible", "restricted", "non_mention", "silent"}
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        evidence_references(expression_policy.get("reason_refs"))
        return

    if proposal_type == "set_importance":
        importance = proposal.proposed_patch.get("importance")
        if (
            keys != {"importance"}
            or isinstance(importance, bool)
            or not isinstance(importance, (int, float))
            or not math.isfinite(float(importance))
            or not 0.0 <= float(importance) <= 1.0
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        return

    if proposal_type == "set_consolidation":
        if keys != {"consolidation_state"} or proposal.proposed_patch.get(
            "consolidation_state"
        ) not in {"candidate", "consolidated", "stable", "decayed"}:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        return

    if proposal_type == "lifecycle_transition":
        if len(proposal.target_refs) != 1:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        target_ref = proposal.target_refs[0]
        lifecycle_state = proposal.proposed_patch.get("lifecycle_state")
        requested_action = proposal.proposed_patch.get("requested_action")
        if lifecycle_state is None and requested_action is None:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if (
            lifecycle_state is not None
            and requested_action is not None
            and lifecycle_state != requested_action
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        desired_state = (
            lifecycle_state if lifecycle_state is not None else requested_action
        )
        if target_ref.startswith("idn-"):
            allowed_states = {
                "active",
                "maintenance_paused",
                "termination_pending",
                "emergency_unresponsive",
                "terminated",
            }
        elif target_ref.startswith("brn-"):
            if lifecycle_state is not None:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            allowed_states = {
                "active",
                "candidate",
                "inactive",
                "quarantined",
                "terminated",
            }
        elif target_ref.startswith("vlt-"):
            if lifecycle_state is not None:
                _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
            allowed_states = {"active", "contact_paused", "sealed"}
        else:
            _fail(CoreErrorCode.RECORD_TYPE_SCHEMA_MISMATCH)
        if desired_state not in allowed_states:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if "reason_refs" in keys:
            evidence_references(proposal.proposed_patch.get("reason_refs"))
        return

    if proposal_type == "maintenance_trigger":
        if keys != _PATCH_FIELDS_BY_TYPE["maintenance_trigger"]:
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        requested_action = proposal.proposed_patch.get("requested_action")
        reason_code = proposal.proposed_patch.get("reason_code")
        trigger_scope = _sequence_of_strings(
            proposal.proposed_patch.get("scope_refs")
        )
        if (
            requested_action
            not in {"freeze", "isolate", "rebuild_index", "restore", "migrate"}
            or reason_code
            not in {
                "attack_isolation",
                "corruption_recovery",
                "migration",
                "project_reconstruction",
            }
            or not trigger_scope
            or not set(trigger_scope) <= target_refs
        ):
            _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
        if not set(trigger_scope) <= scope_refs:
            _fail(CoreErrorCode.VAULT_SCOPE_MISMATCH)
        return

    _fail(CoreErrorCode.HEADER_BODY_MISMATCH)


def _validate_submit(
    repository: AuthorityRepository,
    command: MutationCommandEnvelope,
    proposal: Proposal,
) -> tuple[str, str, Identity]:
    write_spec = WRITE_API_BY_NAME["submit_proposal"]
    if command.actor.actor_type not in write_spec.actor_types:
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if command.command_type != "memory_proposal.submit":
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    _assert_closed_payload(
        command,
        frozenset(
            {"scope_refs", "event_id", "instance_id", "semantic_input_hash"}
        ),
        frozenset({"causation_id"}),
    )
    event_id = _validate_record_id(
        command.payload.get("event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    instance_id = _validate_record_id(command.payload.get("instance_id"), "ins-")
    causation_id = command.payload.get("causation_id")
    if causation_id is not None and (
        not isinstance(causation_id, str)
        or not causation_id.startswith(("evt-", "cmd-"))
    ):
        _fail(CoreErrorCode.RECORD_ID_MISMATCH)
    _validate_record_id(proposal.proposal_id, TYPE_REGISTRY["Proposal"].id_prefix)

    expected_targets = (proposal.proposal_id, event_id)
    versions = _normalized_expected_versions(command)
    if command.target_record_refs != expected_targets or versions != {
        proposal.proposal_id: 0,
        event_id: 0,
    }:
        _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)

    if (
        proposal.status != "pending"
        or proposal.version != 1
        or proposal.deferred_at is not None
        or proposal.defer_conditions != _EMPTY_DEFER_CONDITIONS
        or proposal.reopened_count != 0
        or proposal.created_at != command.issued_at
        or proposal.expires_at <= proposal.created_at
        or proposal.record_header.record_type != "Proposal"
        or proposal.record_header.record_id != proposal.proposal_id
        or proposal.record_header.identity_id != proposal.identity_id
        or proposal.record_header.lineage_id != proposal.lineage_id
        or proposal.record_header.branch_id != proposal.branch_id
        or proposal.record_header.created_at != proposal.created_at
        or proposal.record_header.created_by_event_id != event_id
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    expected_proposer_type = {
        "llm": "llm",
        "system": "system_detector",
        "amadeus": "user_adapter",
    }[command.actor.actor_type]
    if (
        proposal.proposed_by.actor_type != expected_proposer_type
        or proposal.proposed_by.actor_id != command.actor.actor_id
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    _validate_patch(proposal, command)

    identity, _lineage, _branch, _vault = _validated_authorities(
        repository,
        proposal,
    )
    for target_ref in proposal.target_refs:
        _validate_reference(
            repository,
            proposal,
            target_ref,
            must_be_event=False,
            allow_absent_memory=proposal.proposal_type == "create_memory",
        )
    for evidence_ref in proposal.evidence_refs:
        _validate_reference(
            repository,
            proposal,
            evidence_ref,
            must_be_event=True,
            allow_absent_memory=False,
        )
    nested_target_refs: tuple[str, ...] = ()
    if proposal.proposal_type == "create_memory":
        nested_target_refs = _sequence_of_strings(
            proposal.proposed_patch.get("supersedes_memory_ids")
        )
        for nested_target_ref in nested_target_refs:
            _validate_reference(
                repository,
                proposal,
                nested_target_ref,
                must_be_event=False,
                allow_absent_memory=False,
            )
    required_scope = (
        proposal.identity_id,
        proposal.lineage_id,
        proposal.branch_id,
        *((proposal.vault_id,) if proposal.vault_id is not None else ()),
        *proposal.target_refs,
        *nested_target_refs,
        *proposal.evidence_refs,
    )
    _assert_scope_refs(command, required_scope)
    return event_id, instance_id, identity


def _validated_defer_inputs(
    command: MutationCommandEnvelope,
    proposal_id: str,
    conditions: DeferConditions | Mapping[str, object],
) -> tuple[DeferConditions, GovernorDecision]:
    try:
        condition_snapshot = DeferConditions.model_validate(
            conditions.model_dump(mode="python")
            if isinstance(conditions, DeferConditions)
            else conditions
        )
        decision = GovernorDecision.model_validate_json(
            canonical_json(command.payload.get("decision"))
        )
        decision = cast(
            GovernorDecision,
            validate_authoritative_record(
                "governor_decision",
                decision.model_dump(mode="python"),
            ),
        )
    except (ValidationError, ContentHashMismatch, CoreContractViolation) as error:
        raise GovernanceViolation(CoreErrorCode.HASH_SCOPE_MISMATCH) from error
    descriptor = {
        "proposal_id": proposal_id,
        "decision": decision.model_dump(mode="python"),
        "defer_conditions": condition_snapshot.model_dump(mode="python"),
    }
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(descriptor))
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
    if command.payload.get("proposal_id") != proposal_id:
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    try:
        payload_conditions = DeferConditions.model_validate_json(
            canonical_json(command.payload.get("defer_conditions"))
        )
    except ValidationError as error:
        raise GovernanceViolation(CoreErrorCode.HEADER_BODY_MISMATCH) from error
    if payload_conditions != condition_snapshot:
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
    if (
        not condition_snapshot.missing_evidence_types
        and condition_snapshot.reopen_not_before is None
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if (
        len(set(condition_snapshot.missing_evidence_types))
        != len(condition_snapshot.missing_evidence_types)
        or any(
            not evidence_type.strip()
            for evidence_type in condition_snapshot.missing_evidence_types
        )
        or not set(condition_snapshot.missing_evidence_types)
        <= _LEDGER_EVENT_TYPES
    ):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    return condition_snapshot, decision


def _validate_defer(
    repository: AuthorityRepository,
    command: MutationCommandEnvelope,
    proposal_id: str,
    conditions: DeferConditions,
    decision: GovernorDecision,
) -> tuple[Proposal, Proposal, str, str, str, Identity]:
    write_spec = WRITE_API_BY_NAME["decide_memory_proposal"]
    if command.actor.actor_type != "governor" or (
        command.actor.actor_type not in write_spec.actor_types
    ):
        code = (
            CoreErrorCode.LLM_COMMIT_FORBIDDEN
            if command.actor.actor_type == "llm"
            else CoreErrorCode.HEADER_BODY_MISMATCH
        )
        _fail(code)
    if command.command_type != "memory_proposal.defer":
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    _assert_closed_payload(
        command,
        frozenset(
            {
                "scope_refs",
                "decision_event_id",
                "proposal_event_id",
                "instance_id",
                "proposal_id",
                "decision",
                "defer_conditions",
                "semantic_input_hash",
            }
        ),
        frozenset({"causation_id"}),
    )
    decision_event_id = _validate_record_id(
        command.payload.get("decision_event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    proposal_event_id = _validate_record_id(
        command.payload.get("proposal_event_id"),
        TYPE_REGISTRY["LedgerEvent"].id_prefix,
    )
    instance_id = _validate_record_id(command.payload.get("instance_id"), "ins-")
    proposal = repository.get_validated(proposal_id)
    if not isinstance(proposal, Proposal):
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if proposal.status in _TERMINAL_PROPOSAL_STATES:
        _fail(CoreErrorCode.PROPOSAL_TERMINAL)
    if proposal.status != "pending":
        _fail(CoreErrorCode.HEADER_BODY_MISMATCH)
    if proposal.proposal_type in _MEMORY_PROPOSAL_TYPES:
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    updated = cast(
        Proposal,
        reseal_update(
            proposal,
            {
                "status": "deferred",
                "deferred_at": decision.decided_at,
                "defer_conditions": conditions,
                "version": proposal.version + 1,
            },
        ),
    )
    if (
        decision.decision_id != decision.record_header.record_id
        or decision.proposal_id != proposal.proposal_id
        or decision.identity_id != proposal.identity_id
        or decision.lineage_id != proposal.lineage_id
        or decision.branch_id != proposal.branch_id
        or decision.vault_id != proposal.vault_id
        or decision.result != "defer"
        or decision.input_state_hash != proposal.record_header.content_hash
        or decision.output_state_hash != updated.record_header.content_hash
        or decision.committed_event_ids
        != (decision_event_id, proposal_event_id)
        or decision.record_header.created_by_event_id != decision_event_id
        or decision.record_header.created_at != decision.decided_at
        or decision.decided_at != command.issued_at
        or decision.decided_at >= proposal.expires_at
        or decision.version != 1
        or not decision.reason_codes
        or not decision.governor_signature.strip()
    ):
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    identity, _lineage, _branch, _vault = _validated_authorities(
        repository,
        proposal,
    )
    if (
        decision.record_header.deployment_policy_ref
        != identity.deployment_policy_ref
    ):
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    for evidence_ref in decision.evidence_refs:
        _validate_reference(
            repository,
            proposal,
            evidence_ref,
            must_be_event=True,
            allow_absent_memory=False,
        )
    replay = repository.validated_ledger_replay(proposal.branch_id)
    currently_available_types = {
        event.event_type
        for event in replay.events
        if _event_satisfies_proposal_scope(event, proposal)
    }
    if set(conditions.missing_evidence_types) & currently_available_types:
        _fail(CoreErrorCode.GOVERNOR_POLICY_MISMATCH)
    required_targets = (
        proposal.proposal_id,
        decision.decision_id,
        decision_event_id,
        proposal_event_id,
    )
    versions = _normalized_expected_versions(command)
    if command.target_record_refs != required_targets or versions != {
        proposal.proposal_id: proposal.version,
        decision.decision_id: 0,
        decision_event_id: 0,
        proposal_event_id: 0,
    }:
        _fail(CoreErrorCode.VERSION_TARGET_SET_MISMATCH)
    required_scope = (
        proposal.identity_id,
        proposal.lineage_id,
        proposal.branch_id,
        *((proposal.vault_id,) if proposal.vault_id is not None else ()),
        proposal.proposal_id,
        *proposal.evidence_refs,
        *(
            evidence_ref
            for evidence_ref in decision.evidence_refs
            if evidence_ref not in proposal.evidence_refs
        ),
    )
    _assert_scope_refs(command, required_scope)
    return (
        proposal,
        updated,
        decision_event_id,
        proposal_event_id,
        instance_id,
        identity,
    )


def _validated_reopen_descriptor(
    command: MutationCommandEnvelope,
    proposal_id: str,
    now: datetime,
) -> tuple[str, ...]:
    evidence_event_ids = _sequence_of_strings(
        command.payload.get("evidence_event_ids")
    )
    descriptor = {
        "proposal_id": proposal_id,
        "evidence_event_ids": evidence_event_ids,
        "now": now,
    }
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(descriptor))
    if (
        command.payload.get("proposal_id") != proposal_id
        or command.payload.get("now") != now
        or not isinstance(supplied, str)
        or not hmac.compare_digest(supplied, expected)
    ):
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)
    return evidence_event_ids


def _validated_expire_descriptor(
    command: MutationCommandEnvelope,
    proposal_id: str,
    now: datetime,
) -> None:
    descriptor = {"proposal_id": proposal_id, "now": now}
    supplied = command.payload.get("semantic_input_hash")
    expected = sha256_hex(canonical_json(descriptor))
    if (
        command.payload.get("proposal_id") != proposal_id
        or command.payload.get("now") != now
        or not isinstance(supplied, str)
        or not hmac.compare_digest(supplied, expected)
    ):
        _fail(CoreErrorCode.HASH_SCOPE_MISMATCH)


def _event_satisfies_proposal_scope(
    event: LedgerEvent,
    proposal: Proposal,
) -> bool:
    return (
        event.identity_id == proposal.identity_id
        and event.lineage_id == proposal.lineage_id
        and event.branch_id == proposal.branch_id
        and event.vault_id == proposal.vault_id
    )


def _latest_proposal_deferred_seq(
    replay: LedgerReplayResult,
    proposal_id: str,
) -> int | None:
    matching = [
        event.ledger_seq
        for event, payload in zip(
            replay.events,
            replay.resolved_inline_payloads,
            strict=True,
        )
        if event.event_type == "proposal_deferred"
        and isinstance(payload, Mapping)
        and payload.get("proposal_id") == proposal_id
    ]
    return None if not matching else max(matching)


def _snapshot_binding_is_active(
    proposal: Proposal,
    binding: ProposalAuthorityBinding | None,
) -> bool:
    if binding is None:
        return False
    identity = binding.identity
    lineage = binding.lineage
    branch = binding.branch
    vault = binding.vault
    return (
        identity is not None
        and lineage is not None
        and branch is not None
        and identity.lineage_id == proposal.lineage_id
        and identity.active_branch_id == proposal.branch_id
        and identity.lifecycle_state == "active"
        and lineage.root_identity_id == proposal.identity_id
        and branch.identity_id == proposal.identity_id
        and branch.lineage_id == proposal.lineage_id
        and branch.status == "active"
        and (
            proposal.vault_id is None
            or (
                vault is not None
                and vault.identity_id == proposal.identity_id
                and vault.lineage_id == proposal.lineage_id
                and vault.branch_id == proposal.branch_id
                and vault.status != "sealed"
            )
        )
        and proposal.record_header.deployment_policy_ref
        == identity.deployment_policy_ref
    )
