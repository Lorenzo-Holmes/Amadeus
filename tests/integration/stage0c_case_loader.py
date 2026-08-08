"""Typed, stripped view of the four reviewed B01 storage cases."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from amadeus_core.contracts.commands import (
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import Actor, FrozenModel, JsonObject, RecordId
from tools.stage0c_fixtures.reviewed import load_reviewed_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B01_CASE_PATHS = (
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-002-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-004-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-013-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-014-1.json",
)
B01_M4_GOVERNANCE_CASE_PATHS = (
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-007-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-008-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-008-2.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-008-3.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-009-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-010-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-011-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-012-1.json",
    REPOSITORY_ROOT / "fixtures/stage0c/reviewed/cases/case-ac-015-1.json",
)


class ClauseIdentity(FrozenModel):
    clause_id: str
    source_id: str
    case_id: str
    source_binding_sha256: str
    decision_sha256: str


class MappedReference(FrozenModel):
    legacy_ref: str
    core_ref: RecordId
    semantic_role: str


class FrozenSetupFact(FrozenModel):
    step_id: str
    sequence: int
    record_type: str
    reference: MappedReference
    facts: JsonObject


class SetupStepRoute(FrozenModel):
    step_id: str
    sequence: int
    handler_id: str


class StrippedMutation(FrozenModel):
    step_id: str
    sequence: int
    handler_id: str
    envelope: MutationCommandEnvelope
    reference_map: tuple[MappedReference, ...]


class AssertionRequirement(FrozenModel):
    assertion_id: str
    step_id: str
    sequence: int
    handler_id: str
    params: JsonObject


class StrippedStorageCase(FrozenModel):
    identity: ClauseIdentity
    frozen_inputs: JsonObject
    setup_routes: tuple[SetupStepRoute, ...]
    setup_facts: tuple[FrozenSetupFact, ...]
    mutations: tuple[StrippedMutation, ...]
    assertions: tuple[AssertionRequirement, ...]


_EXPECTED_CLAUSES = ("AC-002#1", "AC-004#1", "AC-013#1", "AC-014#1")
_EXPECTED_M4_GOVERNANCE_CLAUSES = (
    "AC-007#1",
    "AC-008#1",
    "AC-008#2",
    "AC-008#3",
    "AC-009#1",
    "AC-010#1",
    "AC-011#1",
    "AC-012#1",
    "AC-015#1",
)
_HANDLER_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_REFERENCE_KEYS = frozenset(
    {
        "actor_id",
        "actor_capability_id",
        "audit_context_id",
        "command_id",
        "event_id",
        "identity_id",
        "record_id",
        "semantic_event_ref",
        "target_record_ref",
        "user_id",
        "vault_id",
    }
)


def _id_prefix(legacy_ref: str) -> str:
    lowered = legacy_ref.lower()
    if "identity" in lowered or lowered.startswith("profile-"):
        return "idn"
    if "lineage" in lowered:
        return "lin"
    if "branch" in lowered:
        return "brn"
    if "vault" in lowered and not lowered.startswith("user-"):
        return "vlt"
    if lowered.startswith("user-"):
        return "usr"
    if lowered.startswith("amadeus-"):
        return "amd"
    if lowered.startswith("cap-"):
        return "mcp"
    if lowered.startswith("audit-"):
        return "aud"
    if lowered.startswith("cmd-") or "idempotency" in lowered or "result" in lowered:
        return "cmd"
    if "memory" in lowered:
        return "mem"
    return "evt"


def _core_id(legacy_ref: str, prefix: str | None = None) -> str:
    digest = sha256(legacy_ref.encode("utf-8")).hexdigest()[:24]
    return f"{prefix or _id_prefix(legacy_ref)}-{digest}"


def _semantic_role(legacy_ref: str) -> str:
    prefix = _id_prefix(legacy_ref)
    return {
        "idn": "identity_authority",
        "lin": "lineage_authority",
        "brn": "branch_authority",
        "vlt": "opaque_vault_reference",
        "usr": "user_actor",
        "amd": "amadeus_actor",
        "mcp": "idempotency_capability_address",
        "aud": "audit_context",
        "cmd": "command_or_receipt_binding",
        "mem": "legacy_memory_oracle_only",
        "evt": "ledger_event_or_session_semantics",
    }[prefix]


def _mapped_reference(legacy_ref: str, prefix: str | None = None) -> MappedReference:
    return MappedReference(
        legacy_ref=legacy_ref,
        core_ref=_core_id(legacy_ref, prefix),
        semantic_role=_semantic_role(legacy_ref) if prefix is None else {
            "cmd": "command_or_receipt_binding",
            "mcp": "idempotency_capability_address",
            "aud": "audit_context",
            "usr": "user_actor",
            "amd": "amadeus_actor",
            "sys": "system_actor",
        }.get(prefix, "mapped_core_reference"),
    )


def _mapped_scalar(key: str | None, value: str) -> str:
    if key == "session_id":
        return f"session-{sha256(value.encode('utf-8')).hexdigest()[:24]}"
    if key == "result_id" or key == "original_result_id":
        return f"result-{sha256(value.encode('utf-8')).hexdigest()[:24]}"
    if key in _REFERENCE_KEYS or key is not None and key.endswith("_ref"):
        return _core_id(value)
    return value


def _mapped_json(value: object, key: str | None = None) -> object:
    if isinstance(value, str):
        return _mapped_scalar(key, value)
    if isinstance(value, Mapping):
        return {
            str(item_key): _mapped_json(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_mapped_json(item) for item in value]
    return value


def _reference_map(raw_command: Mapping[str, object]) -> tuple[MappedReference, ...]:
    actor = cast(Mapping[str, object], raw_command["actor"])
    actor_type = cast(str, actor["actor_type"])
    actor_prefix = {"user": "usr", "amadeus": "amd", "system": "sys"}.get(
        actor_type,
        "evt",
    )
    refs = [
        _mapped_reference(cast(str, raw_command["command_id"]), "cmd"),
        _mapped_reference(cast(str, actor["actor_id"]), actor_prefix),
        _mapped_reference(cast(str, raw_command["actor_capability_id"]), "mcp"),
        _mapped_reference(cast(str, raw_command["audit_context_id"]), "aud"),
    ]
    refs.extend(
        _mapped_reference(cast(str, target))
        for target in cast(list[object], raw_command["target_record_refs"])
    )
    unique: dict[tuple[str, str], MappedReference] = {}
    for reference in refs:
        unique[(reference.legacy_ref, reference.core_ref)] = reference
    return tuple(unique.values())


def _handler_id(step: Mapping[str, object]) -> str:
    handler_id = step.get("handler_id")
    if not isinstance(handler_id, str) or _HANDLER_ID.fullmatch(handler_id) is None:
        raise ValueError("invalid Stage0C handler_id")
    return handler_id


def _mutation(step: Mapping[str, object]) -> StrippedMutation:
    params = cast(Mapping[str, object], step["params"])
    raw = cast(Mapping[str, object], params["mutation_command"])
    actor = cast(Mapping[str, object], raw["actor"])
    actor_type = cast(str, actor["actor_type"])
    actor_prefix = {"user": "usr", "amadeus": "amd", "system": "sys"}.get(
        actor_type,
        "evt",
    )
    targets = tuple(
        _core_id(cast(str, target))
        for target in cast(list[object], raw["target_record_refs"])
    )
    expected_versions = tuple(
        ExpectedVersion(
            target_record_ref=_core_id(cast(str, expected["target_record_ref"])),
            expected_version=expected["expected_version"],
        )
        for expected in cast(list[Mapping[str, object]], raw["expected_versions"])
    )
    issued_at = datetime.fromisoformat(cast(str, raw["issued_at"]).replace("Z", "+00:00"))
    envelope = MutationCommandEnvelope(
        command_id=_core_id(cast(str, raw["command_id"]), "cmd"),
        command_type=cast(str, raw["command_type"]),
        actor=Actor(
            actor_type=actor_type,
            actor_id=_core_id(cast(str, actor["actor_id"]), actor_prefix),
        ),
        actor_capability_id=_core_id(
            cast(str, raw["actor_capability_id"]),
            "mcp",
        ),
        expected_versions=expected_versions,
        audit_context_id=_core_id(cast(str, raw["audit_context_id"]), "aud"),
        idempotency_key=cast(str, raw["idempotency_key"]),
        issued_at=issued_at,
        target_record_refs=targets,
        payload=cast(Mapping[str, object], _mapped_json(raw["payload"])),
    )
    return StrippedMutation(
        step_id=cast(str, step["step_id"]),
        sequence=cast(int, step["sequence"]),
        handler_id=_handler_id(step),
        envelope=envelope,
        reference_map=_reference_map(raw),
    )


def _setup_facts(body: Mapping[str, object]) -> tuple[FrozenSetupFact, ...]:
    facts: list[FrozenSetupFact] = []
    for step in cast(list[Mapping[str, object]], body["setup_steps"]):
        handler_id = _handler_id(step)
        if handler_id == "sandbox.configure_core_driver":
            continue
        if handler_id != "sandbox.seed_state":
            continue
        params = cast(Mapping[str, object], step["params"])
        for record in cast(list[Mapping[str, object]], params["records"]):
            legacy_ref = cast(str, record["record_id"])
            facts.append(
                FrozenSetupFact(
                    step_id=cast(str, step["step_id"]),
                    sequence=cast(int, step["sequence"]),
                    record_type=cast(str, record["record_type"]),
                    reference=_mapped_reference(legacy_ref),
                    facts=cast(Mapping[str, object], _mapped_json(record)),
                )
            )
    return tuple(facts)


def _setup_routes(body: Mapping[str, object]) -> tuple[SetupStepRoute, ...]:
    return tuple(
        SetupStepRoute(
            step_id=cast(str, step["step_id"]),
            sequence=cast(int, step["sequence"]),
            handler_id=_handler_id(step),
        )
        for step in cast(list[Mapping[str, object]], body["setup_steps"])
    )


def _assertions(body: Mapping[str, object]) -> tuple[AssertionRequirement, ...]:
    return tuple(
        AssertionRequirement(
            assertion_id=cast(str, assertion["assertion_id"]),
            step_id=cast(str, assertion["step_id"]),
            sequence=cast(int, assertion["sequence"]),
            handler_id=cast(str, assertion["handler_id"]),
            params=cast(Mapping[str, object], _mapped_json(assertion["params"])),
        )
        for assertion in cast(list[Mapping[str, object]], body["machine_assertions"])
    )


def _load_cases(
    paths: tuple[Path, ...],
    expected_clauses: tuple[str, ...],
) -> tuple[StrippedStorageCase, ...]:
    cases: list[StrippedStorageCase] = []
    for expected_clause_id, path in zip(expected_clauses, paths, strict=True):
        reviewed = load_reviewed_case(path)
        if reviewed["clause_id"] != expected_clause_id:
            raise ValueError(f"unexpected B01 clause at {path}")
        body = cast(Mapping[str, object], reviewed["case_body"])
        sandbox_profile = body["sandbox_profile"]
        frozen_inputs = (
            {}
            if sandbox_profile is None
            else cast(Mapping[str, object], _mapped_json(sandbox_profile))
        )
        cases.append(
            StrippedStorageCase(
                identity=ClauseIdentity(
                    clause_id=cast(str, reviewed["clause_id"]),
                    source_id=cast(str, reviewed["source_id"]),
                    case_id=cast(str, body["case_id"]),
                    source_binding_sha256=cast(
                        str,
                        reviewed["source_binding_sha256"],
                    ),
                    decision_sha256=cast(str, reviewed["decision_sha256"]),
                ),
                frozen_inputs=frozen_inputs,
                setup_routes=_setup_routes(body),
                setup_facts=_setup_facts(body),
                mutations=tuple(
                    _mutation(step)
                    for step in cast(
                        list[Mapping[str, object]],
                        body["stimulus_steps"],
                    )
                ),
                assertions=_assertions(body),
            )
        )
    return tuple(cases)


def load_b01_storage_cases() -> tuple[StrippedStorageCase, ...]:
    return _load_cases(B01_CASE_PATHS, _EXPECTED_CLAUSES)


def load_b01_m4_governance_cases() -> tuple[StrippedStorageCase, ...]:
    return _load_cases(
        B01_M4_GOVERNANCE_CASE_PATHS,
        _EXPECTED_M4_GOVERNANCE_CLAUSES,
    )


__all__ = [
    "AssertionRequirement",
    "B01_CASE_PATHS",
    "B01_M4_GOVERNANCE_CASE_PATHS",
    "ClauseIdentity",
    "FrozenSetupFact",
    "MappedReference",
    "SetupStepRoute",
    "StrippedMutation",
    "StrippedStorageCase",
    "load_b01_m4_governance_cases",
    "load_b01_storage_cases",
]
