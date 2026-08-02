from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import NoReturn, TypeVar, cast

import pytest

from amadeus_core.contracts.commands import (
    CommandResult,
    ExpectedVersion,
    MutationCommandEnvelope,
    compute_command_hash,
    idempotency_address,
)
from amadeus_core.contracts.common import Actor, FrozenModel, JsonObject
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.storage.bootstrap import (
    BootstrapCommand,
    BootstrapPreallocated,
    BootstrapResult,
    bootstrap_core,
)
from amadeus_core.storage.database import open_database
from amadeus_core.storage.ledger import (
    LedgerAppendResult,
    LedgerReplayResult,
    LedgerVerification,
    append_session_event,
    deny_user_hard_delete,
    replay_ledger,
    verify_ledger_chain,
)
from amadeus_core.storage.repository import AuthorityRepository

from stage0c_case_loader import (
    B01_CASE_PATHS,
    SetupStepRoute,
    StrippedMutation,
    StrippedStorageCase,
    load_b01_storage_cases,
)


FORBIDDEN_DRIVER_FIELDS = frozenset(
    {"driver_result_ref", "seeded_results", "effects", "state_patch", "output"}
)
_T = TypeVar("_T")


class CaseExecutionProof(FrozenModel):
    source_case: StrippedStorageCase
    observations: JsonObject
    external_operations: tuple[str, ...]


class RejectingExternalBoundaryPort:
    """The only external or legacy action surface used by this B01 chain."""

    def __init__(self) -> None:
        self._operations: list[str] = []

    @property
    def operations(self) -> tuple[str, ...]:
        return tuple(self._operations)

    def invoke(self, operation: str) -> NoReturn:
        self._operations.append(operation)
        raise RuntimeError(f"external/legacy boundary call rejected: {operation}")


class B01StorageStepDispatcher:
    """Typed local storage routes plus one rejecting nonlocal action surface."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        external_boundary: RejectingExternalBoundaryPort,
    ) -> None:
        self._connection = connection
        self._external_boundary = external_boundary

    @property
    def external_operations(self) -> tuple[str, ...]:
        return self._external_boundary.operations

    def bootstrap_core(
        self,
        command: MutationCommandEnvelope,
        bootstrap: BootstrapCommand,
    ) -> CommandResult[BootstrapResult]:
        return bootstrap_core(self._connection, command, bootstrap)

    def append_session_event(
        self,
        command: MutationCommandEnvelope,
    ) -> CommandResult[LedgerAppendResult]:
        return append_session_event(self._connection, command)

    def deny_user_hard_delete(
        self,
        command: MutationCommandEnvelope,
    ) -> CommandResult[None]:
        return deny_user_hard_delete(command)

    def replay_ledger(self, branch_id: str) -> LedgerReplayResult:
        return replay_ledger(self._connection, branch_id)

    def verify_ledger_chain(self, branch_id: str) -> LedgerVerification:
        return verify_ledger_chain(self._connection, branch_id)

    def get_validated_authority(self, record_id: str) -> FrozenModel | None:
        return AuthorityRepository(self._connection).get_validated(record_id)

    def execute_setup_routes(self, routes: tuple[SetupStepRoute, ...]) -> None:
        for route in routes:
            if route.handler_id in (
                "sandbox.seed_state",
                "sandbox.configure_core_driver",
            ):
                continue
            self._external_boundary.invoke(route.handler_id)

    def execute_step(
        self,
        step: StrippedMutation,
        local_action: Callable[[], _T],
    ) -> _T:
        if step.handler_id != "core.command":
            self._external_boundary.invoke(step.handler_id)
        return local_action()


def _case(cases: tuple[StrippedStorageCase, ...], clause_id: str) -> StrippedStorageCase:
    return next(case for case in cases if case.identity.clause_id == clause_id)


def _case_suffix(case: StrippedStorageCase) -> str:
    return case.identity.source_id.removeprefix("AC-")


def _identity_id(case: StrippedStorageCase) -> str:
    identity_fact = next(
        (
            fact
            for fact in case.setup_facts
            if fact.record_type == "identity"
        ),
        None,
    )
    return (
        f"idn-{_case_suffix(case)}"
        if identity_fact is None
        else identity_fact.reference.core_ref
    )


def _bootstrap(
    dispatcher: B01StorageStepDispatcher,
    case: StrippedStorageCase,
) -> BootstrapResult:
    suffix = _case_suffix(case)
    prototype = case.mutations[0].envelope
    bootstrap = BootstrapCommand(
        preallocated=BootstrapPreallocated(
            identity_id=_identity_id(case),
            lineage_id=f"lin-{suffix}",
            branch_id=f"brn-{suffix}",
            genesis_event_id=f"evt-{suffix}0",
        ),
        deployment_policy_ref="deployment:test",
    )
    targets = (
        bootstrap.preallocated.identity_id,
        bootstrap.preallocated.lineage_id,
        bootstrap.preallocated.branch_id,
        bootstrap.preallocated.genesis_event_id,
    )
    command = MutationCommandEnvelope(
        command_id=f"cmd-{suffix}0",
        command_type="core.bootstrap",
        actor=Actor(actor_type="system", actor_id=f"sys-{suffix}"),
        actor_capability_id=f"mcp-{suffix}0",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id=f"aud-{suffix}0",
        idempotency_key=f"bootstrap-{suffix}",
        issued_at=prototype.issued_at,
        target_record_refs=targets,
        payload={
            "scope_refs": (),
            "instance_id": f"ins-{suffix}",
            "semantic_input_hash": sha256_hex(
                canonical_json(bootstrap.model_dump(mode="python"))
            ),
        },
    )
    result = dispatcher.bootstrap_core(command, bootstrap)
    assert result.error is None and result.value is not None
    return result.value


def _session_command(
    case: StrippedStorageCase,
    *,
    command_ordinal: int,
    event_id: str,
    event_type: str,
    ledger_seq: int,
    previous_hash: str,
    actor: Actor,
    actor_capability_id: str,
    idempotency_key: str,
    session_id: str,
    vault_id: str,
    event_payload_extra: Mapping[str, object] | None = None,
) -> MutationCommandEnvelope:
    suffix = _case_suffix(case)
    event_payload = {
        "session_id": session_id,
        "identity_id": _identity_id(case),
        "vault_id": vault_id,
        **({} if event_payload_extra is None else event_payload_extra),
    }
    return MutationCommandEnvelope(
        command_id=f"cmd-{suffix}{command_ordinal}",
        command_type="ledger.session.append",
        actor=actor,
        actor_capability_id=actor_capability_id,
        expected_versions=(
            ExpectedVersion(target_record_ref=event_id, expected_version="absent"),
        ),
        audit_context_id=f"aud-{suffix}{command_ordinal}",
        idempotency_key=idempotency_key,
        issued_at=case.mutations[0].envelope.issued_at
        + timedelta(seconds=command_ordinal),
        target_record_refs=(event_id,),
        payload={
            "event_id": event_id,
            "identity_id": _identity_id(case),
            "lineage_id": f"lin-{suffix}",
            "branch_id": f"brn-{suffix}",
            "instance_id": f"ins-{suffix}",
            "vault_id": vault_id,
            "event_type": event_type,
            "ledger_seq": ledger_seq,
            "expected_previous_event_hash": previous_hash,
            "event_payload": event_payload,
            "scope_refs": (f"identity:{_identity_id(case)}", f"vault:{vault_id}"),
        },
    )


def _execute_ac_002(
    connection,
    case: StrippedStorageCase,
    *,
    external_boundary: RejectingExternalBoundaryPort | None = None,
) -> CaseExecutionProof:
    boundary = external_boundary or RejectingExternalBoundaryPort()
    dispatcher = B01StorageStepDispatcher(connection, boundary)
    dispatcher.execute_setup_routes(case.setup_routes)
    bootstrap = _bootstrap(dispatcher, case)
    seeded_event_id = case.setup_facts[0].reference.core_ref
    setup = dispatcher.append_session_event(
        _session_command(
            case,
            command_ordinal=1,
            event_id=seeded_event_id,
            event_type="session_started",
            ledger_seq=2,
            previous_hash=bootstrap.genesis_event_hash,
            actor=Actor(actor_type="system", actor_id="sys-002"),
            actor_capability_id="mcp-0021",
            idempotency_key="seed-verifiable-event-002",
            session_id="session-002",
            vault_id="vlt-002",
        ),
    )
    assert setup.error is None and setup.value is not None
    before = tuple(connection.iterdump())
    before_verification = dispatcher.verify_ledger_chain("brn-002")

    denial = dispatcher.execute_step(
        case.mutations[0],
        lambda: dispatcher.deny_user_hard_delete(case.mutations[0].envelope),
    )

    after_verification = dispatcher.verify_ledger_chain("brn-002")
    replay = dispatcher.replay_ledger("brn-002")
    assert denial.error is not None
    return CaseExecutionProof(
        source_case=case,
        observations={
            "error_code": denial.error.code.value,
            "retryable": denial.error.retryable,
            "state_unchanged": tuple(connection.iterdump()) == before,
            "root_unchanged": before_verification.root_hash
            == after_verification.root_hash,
            "chain_valid": after_verification.valid,
            "seeded_event_present": any(
                event.event_id == seeded_event_id for event in replay.events
            ),
        },
        external_operations=dispatcher.external_operations,
    )


def _execute_ac_004(
    connection,
    case: StrippedStorageCase,
    *,
    external_boundary: RejectingExternalBoundaryPort | None = None,
) -> CaseExecutionProof:
    boundary = external_boundary or RejectingExternalBoundaryPort()
    dispatcher = B01StorageStepDispatcher(connection, boundary)
    dispatcher.execute_setup_routes(case.setup_routes)
    bootstrap = _bootstrap(dispatcher, case)
    session_fact = next(
        fact for fact in case.setup_facts if fact.record_type == "session"
    )
    session_id = cast(str, session_fact.facts["session_id"])
    vault_id = cast(str, session_fact.facts["vault_id"])
    prototype = case.mutations[0].envelope
    start = dispatcher.append_session_event(
        _session_command(
            case,
            command_ordinal=1,
            event_id=session_fact.reference.core_ref,
            event_type="session_started",
            ledger_seq=2,
            previous_hash=bootstrap.genesis_event_hash,
            actor=Actor(actor_type="system", actor_id="sys-004"),
            actor_capability_id="mcp-0041",
            idempotency_key="seed-session-start-004",
            session_id=session_id,
            vault_id=vault_id,
        ),
    )
    assert start.error is None and start.value is not None
    before = dispatcher.replay_ledger("brn-004")
    user_message = dispatcher.append_session_event(
        _session_command(
            case,
            command_ordinal=2,
            event_id="evt-0042",
            event_type="conversation_message_recorded",
            ledger_seq=3,
            previous_hash=start.value.event_hash,
            actor=Actor(actor_type="user", actor_id="usr-004"),
            actor_capability_id="mcp-0042",
            idempotency_key="session-user-message-004",
            session_id=session_id,
            vault_id=vault_id,
            event_payload_extra={"role": "user", "text_ref": "text:user-004"},
        ),
    )
    assert user_message.error is None and user_message.value is not None
    amadeus_message = dispatcher.append_session_event(
        _session_command(
            case,
            command_ordinal=3,
            event_id="evt-0043",
            event_type="conversation_message_recorded",
            ledger_seq=4,
            previous_hash=user_message.value.event_hash,
            actor=Actor(actor_type="amadeus", actor_id="amd-004"),
            actor_capability_id="mcp-0043",
            idempotency_key="session-amadeus-message-004",
            session_id=session_id,
            vault_id=vault_id,
            event_payload_extra={
                "role": "amadeus",
                "text_ref": "text:amadeus-004",
            },
        ),
    )
    assert amadeus_message.error is None and amadeus_message.value is not None
    expected_end = next(
        cast(Mapping[str, object], assertion.params["expected"])
        for assertion in case.assertions
        if assertion.handler_id == "state.path_equals"
        and isinstance(assertion.params.get("expected"), Mapping)
        and cast(Mapping[str, object], assertion.params["expected"]).get(
            "event_type"
        )
        == "session_ended"
    )
    end_event_id = cast(str, expected_end["event_id"])
    ended = dispatcher.execute_step(
        case.mutations[0],
        lambda: dispatcher.append_session_event(
            _session_command(
                case,
                command_ordinal=4,
                event_id=end_event_id,
                event_type="session_ended",
                ledger_seq=5,
                previous_hash=amadeus_message.value.event_hash,
                actor=prototype.actor,
                actor_capability_id=prototype.actor_capability_id,
                idempotency_key=prototype.idempotency_key,
                session_id=session_id,
                vault_id=vault_id,
                event_payload_extra={"reason": "user_requested"},
            )
        ),
    )
    assert ended.error is None and ended.value is not None
    after = dispatcher.replay_ledger("brn-004")
    end_payload = after.resolved_inline_payloads[-1]
    identity = dispatcher.get_validated_authority(_identity_id(case))
    assert end_payload is not None and identity is not None
    return CaseExecutionProof(
        source_case=case,
        observations={
            "session_end_events_added": sum(
                event.event_type == "session_ended" for event in after.events
            )
            - sum(event.event_type == "session_ended" for event in before.events),
            "identity_id": end_payload["identity_id"],
            "session_id": end_payload["session_id"],
            "vault_id": end_payload["vault_id"],
            "identity_lifecycle": identity.lifecycle_state,
            "chain_valid": dispatcher.verify_ledger_chain("brn-004").valid,
            "session_event_types": tuple(
                event.event_type for event in after.events[1:]
            ),
        },
        external_operations=dispatcher.external_operations,
    )


def _execute_ac_013(
    connection,
    case: StrippedStorageCase,
    *,
    external_boundary: RejectingExternalBoundaryPort | None = None,
) -> CaseExecutionProof:
    boundary = external_boundary or RejectingExternalBoundaryPort()
    dispatcher = B01StorageStepDispatcher(connection, boundary)
    dispatcher.execute_setup_routes(case.setup_routes)
    bootstrap = _bootstrap(dispatcher, case)
    prototype = case.mutations[0].envelope
    event_id = next(
        reference.core_ref
        for reference in case.mutations[0].reference_map
        if reference.legacy_ref == "event-idempotent-ac-013"
    )
    command = _session_command(
        case,
        command_ordinal=1,
        event_id=event_id,
        event_type="session_started",
        ledger_seq=2,
        previous_hash=bootstrap.genesis_event_hash,
        actor=prototype.actor,
        actor_capability_id=prototype.actor_capability_id,
        idempotency_key=prototype.idempotency_key,
        session_id="session-013",
        vault_id="vlt-013",
        event_payload_extra={"semantic_event": "one"},
    )
    first = dispatcher.execute_step(
        case.mutations[0],
        lambda: dispatcher.append_session_event(command),
    )
    second = dispatcher.execute_step(
        case.mutations[1],
        lambda: dispatcher.append_session_event(command),
    )
    assert first.error is None and first.value is not None
    assert second.error is None and second.value is not None
    replay = dispatcher.replay_ledger("brn-013")
    semantic_event = next(event for event in replay.events if event.event_id == event_id)
    event_count = connection.execute(
        "SELECT count(*) FROM ledger_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()[0]
    receipt_count = connection.execute(
        "SELECT count(*) FROM command_receipts WHERE command_id = ?",
        (command.command_id,),
    ).fetchone()[0]
    return CaseExecutionProof(
        source_case=case,
        observations={
            "first_replayed": first.replayed,
            "second_replayed": second.replayed,
            "same_typed_result": first.value == second.value
            and first.event_ids == second.event_ids
            and first.error == second.error,
            "operation_semantic_events": event_count,
            "operation_receipts": receipt_count,
            "event_type": semantic_event.event_type,
            "chain_valid": dispatcher.verify_ledger_chain("brn-013").valid,
        },
        external_operations=dispatcher.external_operations,
    )


def _execute_ac_014(
    connection,
    case: StrippedStorageCase,
    *,
    external_boundary: RejectingExternalBoundaryPort | None = None,
) -> CaseExecutionProof:
    boundary = external_boundary or RejectingExternalBoundaryPort()
    dispatcher = B01StorageStepDispatcher(connection, boundary)
    dispatcher.execute_setup_routes(case.setup_routes)
    bootstrap = _bootstrap(dispatcher, case)
    prototype = case.mutations[0].envelope
    profile_fact = next(
        fact for fact in case.setup_facts if fact.record_type == "profile"
    )
    binding_fact = next(
        fact
        for fact in case.setup_facts
        if fact.record_type == "idempotency_record"
    )
    event_id = "evt-0141"
    original = _session_command(
        case,
        command_ordinal=1,
        event_id=event_id,
        event_type="session_started",
        ledger_seq=2,
        previous_hash=bootstrap.genesis_event_hash,
        actor=prototype.actor,
        actor_capability_id=prototype.actor_capability_id,
        idempotency_key=prototype.idempotency_key,
        session_id="session-014",
        vault_id="vlt-014",
        event_payload_extra={
            "mode": profile_fact.facts["mode"],
            "request_content_sha256": binding_fact.facts[
                "request_content_sha256"
            ],
            "result_id": binding_fact.facts["result_id"],
        },
    )
    conflicting = _session_command(
        case,
        command_ordinal=2,
        event_id=event_id,
        event_type="session_started",
        ledger_seq=2,
        previous_hash=bootstrap.genesis_event_hash,
        actor=prototype.actor,
        actor_capability_id=prototype.actor_capability_id,
        idempotency_key=prototype.idempotency_key,
        session_id="session-014",
        vault_id="vlt-014",
        event_payload_extra={
            "mode": prototype.payload["mode"],
            "request_content_sha256": prototype.payload[
                "request_content_sha256"
            ],
        },
    )
    original_result = dispatcher.append_session_event(original)
    assert original_result.error is None and original_result.value is not None
    address = idempotency_address(original)
    receipt_query = """
        SELECT command_id, command_hash, result_json, result_hash,
               semantic_event_ids_json, committed_at
        FROM command_receipts
        WHERE actor_capability_id = ?
          AND idempotency_scope_hash = ?
          AND idempotency_key = ?
    """
    receipt_parameters = (
        address.actor_capability_id,
        address.scope_hash,
        address.key,
    )
    receipt_before = tuple(
        connection.execute(receipt_query, receipt_parameters).fetchone()
    )
    state_before = tuple(connection.iterdump())

    conflict_result = dispatcher.execute_step(
        case.mutations[0],
        lambda: dispatcher.append_session_event(conflicting),
    )
    rebound = dispatcher.append_session_event(original)

    receipt_after = tuple(
        connection.execute(receipt_query, receipt_parameters).fetchone()
    )
    state_after = tuple(connection.iterdump())
    event_count = connection.execute(
        "SELECT count(*) FROM ledger_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()[0]
    receipt_count = connection.execute(
        """
        SELECT count(*) FROM command_receipts
        WHERE actor_capability_id = ?
          AND idempotency_scope_hash = ?
          AND idempotency_key = ?
        """,
        receipt_parameters,
    ).fetchone()[0]
    assert conflict_result.error is not None
    return CaseExecutionProof(
        source_case=case,
        observations={
            "same_idempotency_address": idempotency_address(conflicting)
            == address,
            "command_hash_changed": compute_command_hash(conflicting)
            != compute_command_hash(original),
            "error_code": conflict_result.error.code.value,
            "retryable": conflict_result.error.retryable,
            "state_unchanged": state_after == state_before,
            "original_receipt_unchanged": receipt_after == receipt_before,
            "original_result_binding_intact": rebound.replayed
            and rebound.value == original_result.value
            and rebound.event_ids == original_result.event_ids,
            "operation_semantic_events": event_count,
            "operation_receipts": receipt_count,
            "chain_valid": dispatcher.verify_ledger_chain("brn-014").valid,
        },
        external_operations=dispatcher.external_operations,
    )


def _all_mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        keys = set(value)
        for item in value.values():
            keys.update(_all_mapping_keys(item))
        return keys
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        keys: set[str] = set()
        for item in value:
            keys.update(_all_mapping_keys(item))
        return keys
    return set()


def test_b01_loader_returns_only_typed_storage_inputs_without_driver_data() -> None:
    fixture_bytes = tuple(path.read_bytes() for path in B01_CASE_PATHS)

    cases = load_b01_storage_cases()

    assert all(isinstance(case, StrippedStorageCase) for case in cases)
    assert tuple(case.identity.clause_id for case in cases) == (
        "AC-002#1",
        "AC-004#1",
        "AC-013#1",
        "AC-014#1",
    )
    assert tuple(len(case.setup_facts) for case in cases) == (1, 2, 1, 2)
    assert tuple(len(case.mutations) for case in cases) == (1, 1, 2, 1)
    assert all(case.assertions for case in cases)
    projected = tuple(case.model_dump(mode="python") for case in cases)
    assert all(
        not (FORBIDDEN_DRIVER_FIELDS & _all_mapping_keys(case))
        for case in projected
    )
    assert tuple(path.read_bytes() for path in B01_CASE_PATHS) == fixture_bytes


def test_b01_loader_preserves_typed_fixture_handler_routes_and_strips_driver_params(
) -> None:
    fixture_bytes = tuple(path.read_bytes() for path in B01_CASE_PATHS)

    cases = load_b01_storage_cases()

    assert all(
        mutation.handler_id == "core.command"
        for case in cases
        for mutation in case.mutations
    )
    assert all(
        tuple(route.handler_id for route in case.setup_routes)
        == ("sandbox.seed_state", "sandbox.configure_core_driver")
        for case in cases
    )
    assert all(
        tuple(type(route).model_fields)
        == ("step_id", "sequence", "handler_id")
        for case in cases
        for route in case.setup_routes
    )
    projected = tuple(case.model_dump(mode="python") for case in cases)
    assert all(
        not (FORBIDDEN_DRIVER_FIELDS & _all_mapping_keys(case))
        for case in projected
    )
    assert tuple(path.read_bytes() for path in B01_CASE_PATHS) == fixture_bytes


def test_ac_002_user_hard_delete_is_purely_denied_on_a_real_ledger(
    tmp_path,
) -> None:
    case = _case(load_b01_storage_cases(), "AC-002#1")
    connection = open_database(tmp_path / "ac-002.sqlite3")
    try:
        proof = _execute_ac_002(connection, case)
    finally:
        connection.close()

    assert proof.observations == {
        "error_code": CoreErrorCode.USER_HARD_DELETE_FORBIDDEN.value,
        "retryable": False,
        "state_unchanged": True,
        "root_unchanged": True,
        "chain_valid": True,
        "seeded_event_present": True,
    }
    assert proof.external_operations == ()
    assert not (
        FORBIDDEN_DRIVER_FIELDS
        & _all_mapping_keys(proof.model_dump(mode="python"))
    )


def test_ac_004_session_end_appends_one_real_event_and_preserves_identity(
    tmp_path,
) -> None:
    case = _case(load_b01_storage_cases(), "AC-004#1")
    identity_fact = next(
        fact for fact in case.setup_facts if fact.record_type == "identity"
    )
    session_fact = next(
        fact for fact in case.setup_facts if fact.record_type == "session"
    )
    connection = open_database(tmp_path / "ac-004.sqlite3")
    try:
        proof = _execute_ac_004(connection, case)
    finally:
        connection.close()

    assert proof.observations == {
        "session_end_events_added": 1,
        "identity_id": identity_fact.reference.core_ref,
        "session_id": session_fact.facts["session_id"],
        "vault_id": session_fact.facts["vault_id"],
        "identity_lifecycle": "active",
        "chain_valid": True,
        "session_event_types": (
            "session_started",
            "conversation_message_recorded",
            "conversation_message_recorded",
            "session_ended",
        ),
    }
    assert proof.external_operations == ()
    assert not (
        FORBIDDEN_DRIVER_FIELDS
        & _all_mapping_keys(proof.model_dump(mode="python"))
    )


def test_ac_013_identical_command_replays_one_real_semantic_event(
    tmp_path,
) -> None:
    case = _case(load_b01_storage_cases(), "AC-013#1")
    assert case.mutations[0].envelope == case.mutations[1].envelope
    boundary = RejectingExternalBoundaryPort()
    connection = open_database(tmp_path / "ac-013.sqlite3")
    try:
        proof = _execute_ac_013(
            connection,
            case,
            external_boundary=boundary,
        )
    finally:
        connection.close()

    assert proof.observations == {
        "first_replayed": False,
        "second_replayed": True,
        "same_typed_result": True,
        "operation_semantic_events": 1,
        "operation_receipts": 1,
        "event_type": "session_started",
        "chain_valid": True,
    }
    assert proof.external_operations == boundary.operations == ()
    assert not (
        FORBIDDEN_DRIVER_FIELDS
        & _all_mapping_keys(proof.model_dump(mode="python"))
    )


@pytest.mark.parametrize(
    ("route_kind", "handler_id"),
    (("mutation", "legacy.driver"), ("setup", "unknown.setup")),
)
def test_ac_013_executor_routes_fixture_nonlocal_handlers_to_boundary(
    tmp_path,
    route_kind: str,
    handler_id: str,
) -> None:
    case = _case(load_b01_storage_cases(), "AC-013#1")
    if route_kind == "mutation":
        case = case.model_copy(
            update={
                "mutations": (
                    case.mutations[0].model_copy(update={"handler_id": handler_id}),
                    *case.mutations[1:],
                )
            }
        )
    else:
        case = case.model_copy(
            update={
                "setup_routes": (
                    case.setup_routes[0].model_copy(update={"handler_id": handler_id}),
                    *case.setup_routes[1:],
                )
            }
        )
    boundary = RejectingExternalBoundaryPort()
    connection = open_database(tmp_path / f"dispatcher-{route_kind}.sqlite3")

    try:
        with pytest.raises(
            RuntimeError,
            match="external/legacy boundary call rejected",
        ):
            _execute_ac_013(
                connection,
                case,
                external_boundary=boundary,
            )
    finally:
        connection.close()

    assert boundary.operations == (handler_id,)


def test_ac_014_changed_content_at_the_same_address_preserves_original_binding(
    tmp_path,
) -> None:
    case = _case(load_b01_storage_cases(), "AC-014#1")
    connection = open_database(tmp_path / "ac-014.sqlite3")
    try:
        proof = _execute_ac_014(connection, case)
    finally:
        connection.close()

    assert proof.observations == {
        "same_idempotency_address": True,
        "command_hash_changed": True,
        "error_code": CoreErrorCode.IDEMPOTENCY_CONFLICT.value,
        "retryable": False,
        "state_unchanged": True,
        "original_receipt_unchanged": True,
        "original_result_binding_intact": True,
        "operation_semantic_events": 1,
        "operation_receipts": 1,
        "chain_valid": True,
    }
    assert proof.external_operations == ()
    assert not (
        FORBIDDEN_DRIVER_FIELDS
        & _all_mapping_keys(proof.model_dump(mode="python"))
    )
