from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import cast

import pytest

import amadeus_core.storage.ledger as ledger_module

from amadeus_core.contracts.commands import (
    CommandResult,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.storage._records import _seal_record
from amadeus_core.storage.bootstrap import (
    BootstrapCommand,
    BootstrapPreallocated,
    bootstrap_core,
)
from amadeus_core.storage.database import open_database
from amadeus_core.storage.payloads import canonical_receipt_result
from amadeus_core.storage.ledger import (
    LedgerAppendResult,
    append_session_event,
    get_verified_ledger_head,
    replay_ledger,
    verify_ledger_chain,
)
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
INSTANCE_ID = "ins-a1"
VAULT_ID = "vlt-a1"
SESSION_ID = "session-a1"


def _bootstrap_scope(connection, suffix: str) -> str:
    identity_id = f"idn-{suffix}"
    lineage_id = f"lin-{suffix}"
    branch_id = f"brn-{suffix}"
    genesis_event_id = f"evt-{suffix}"
    instance_id = f"ins-{suffix}"
    bootstrap = BootstrapCommand(
        preallocated=BootstrapPreallocated(
            identity_id=identity_id,
            lineage_id=lineage_id,
            branch_id=branch_id,
            genesis_event_id=genesis_event_id,
        ),
        deployment_policy_ref="deployment:test",
    )
    targets = (identity_id, lineage_id, branch_id, genesis_event_id)
    command = MutationCommandEnvelope(
        command_id=f"cmd-{suffix}",
        command_type="core.bootstrap",
        actor=Actor(actor_type="system", actor_id=f"sys-{suffix}"),
        actor_capability_id=f"mcp-{suffix}",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id=f"aud-{suffix}",
        idempotency_key=f"bootstrap-{suffix}",
        issued_at=NOW,
        target_record_refs=targets,
        payload={
            "scope_refs": (),
            "instance_id": instance_id,
            "semantic_input_hash": sha256_hex(
                canonical_json(bootstrap.model_dump(mode="python"))
            ),
        },
    )
    result = bootstrap_core(connection, command, bootstrap)
    assert result.error is None
    assert result.value is not None
    return result.value.genesis_event_hash


def _bootstrap(connection) -> str:
    return _bootstrap_scope(connection, "a1")


def _session_command(
    *,
    ordinal: int,
    event_id: str,
    event_type: str,
    ledger_seq: int,
    previous_hash: str,
    actor_type: str,
    actor_id: str,
    event_payload: dict[str, object],
    identity_id: str = IDENTITY_ID,
    lineage_id: str = LINEAGE_ID,
    branch_id: str = BRANCH_ID,
    instance_id: str = INSTANCE_ID,
    vault_id: str = VAULT_ID,
) -> MutationCommandEnvelope:
    return MutationCommandEnvelope(
        command_id=f"cmd-a{ordinal}",
        command_type="ledger.session.append",
        actor=Actor(actor_type=actor_type, actor_id=actor_id),
        actor_capability_id=f"capability-session-{actor_type}",
        expected_versions=(
            ExpectedVersion(target_record_ref=event_id, expected_version="absent"),
        ),
        audit_context_id=f"aud-a{ordinal}",
        idempotency_key=f"session-event-a{ordinal}",
        issued_at=NOW + timedelta(seconds=ordinal),
        target_record_refs=(event_id,),
        payload={
            "event_id": event_id,
            "identity_id": identity_id,
            "lineage_id": lineage_id,
            "branch_id": branch_id,
            "instance_id": instance_id,
            "vault_id": vault_id,
            "event_type": event_type,
            "ledger_seq": ledger_seq,
            "expected_previous_event_hash": previous_hash,
            "event_payload": event_payload,
            "scope_refs": (f"identity:{identity_id}", f"vault:{vault_id}"),
        },
    )


def _append_test_event(
    connection,
    *,
    ordinal: int,
    event_id: str,
    event_type: str,
    ledger_seq: int,
    previous_hash: str,
    actor_type: str,
    actor_id: str,
    session_id: str = SESSION_ID,
    identity_id: str = IDENTITY_ID,
    lineage_id: str = LINEAGE_ID,
    branch_id: str = BRANCH_ID,
    instance_id: str = INSTANCE_ID,
    vault_id: str = VAULT_ID,
    event_payload_extra: dict[str, object] | None = None,
) -> CommandResult[LedgerAppendResult]:
    return append_session_event(
        connection,
        _session_command(
            ordinal=ordinal,
            event_id=event_id,
            event_type=event_type,
            ledger_seq=ledger_seq,
            previous_hash=previous_hash,
            actor_type=actor_type,
            actor_id=actor_id,
            identity_id=identity_id,
            lineage_id=lineage_id,
            branch_id=branch_id,
            instance_id=instance_id,
            vault_id=vault_id,
            event_payload={
                "session_id": session_id,
                "identity_id": identity_id,
                "vault_id": vault_id,
                **({} if event_payload_extra is None else event_payload_extra),
            },
        ),
    )


def _required_event_hash(result: CommandResult[LedgerAppendResult]) -> str:
    assert result.error is None and result.value is not None
    return result.value.event_hash


def _valid_session_head(
    connection,
    message_roles: tuple[str, ...] = (),
) -> str:
    head = _required_event_hash(
        _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=_bootstrap(connection),
            actor_type="system",
            actor_id="sys-a1",
        )
    )
    for ledger_seq, role in enumerate(message_roles, start=3):
        actor_id = "usr-a1" if role == "user" else "amd-a1"
        head = _required_event_hash(
            _append_test_event(
                connection,
                ordinal=ledger_seq,
                event_id=f"evt-a{ledger_seq}",
                event_type="conversation_message_recorded",
                ledger_seq=ledger_seq,
                previous_hash=head,
                actor_type=role,
                actor_id=actor_id,
                event_payload_extra={
                    "role": role,
                    "text_ref": f"text:{role}-a1",
                },
            )
        )
    return head


def _assert_header_body_rejection(
    result: CommandResult[LedgerAppendResult],
) -> None:
    assert result.error is not None
    assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
    assert result.event_ids == ()


def _replace_with_unbound_reference_payload(
    connection,
    event_id: str,
    payload_hash: str,
) -> LedgerEvent:
    stored = AuthorityRepository(connection).get_validated(event_id)
    assert isinstance(stored, LedgerEvent)
    body = stored.model_dump(mode="python")
    body["record_header"]["content_hash"] = "0" * 64
    body["event_hash"] = "0" * 64
    body["payload_ref"] = "reference:blob:test-a2"
    reference_event = cast(LedgerEvent, _seal_record(LedgerEvent, body))
    connection.execute("DROP TRIGGER ledger_events_reject_update")
    connection.execute("DROP TRIGGER authority_ledger_reject_update")
    connection.execute(
        """
        UPDATE authority_records
        SET content_json = ?, content_hash = ?
        WHERE record_id = ?
        """,
        (
            canonical_json(reference_event.model_dump(mode="python")).decode("utf-8"),
            reference_event.event_hash,
            event_id,
        ),
    )
    connection.execute(
        """
        UPDATE ledger_events
        SET event_hash = ?,
            payload_ref = ?,
            payload_mode = 'reference',
            payload_inline_json = NULL,
            payload_external_ref = 'blob:test-a2',
            payload_hash = ?,
            media_type = 'application/json'
        WHERE event_id = ?
        """,
        (
            reference_event.event_hash,
            reference_event.payload_ref,
            payload_hash,
            event_id,
        ),
    )
    return reference_event


def _read_ledger_with(api_name: str, connection):
    if api_name == "verify":
        return verify_ledger_chain(connection, BRANCH_ID)
    if api_name == "replay":
        return replay_ledger(connection, BRANCH_ID)
    if api_name == "head":
        return get_verified_ledger_head(connection, BRANCH_ID)
    raise AssertionError(f"unknown Ledger read API: {api_name}")


@pytest.mark.parametrize("api_name", ("verify", "replay", "head"))
def test_ledger_read_api_owns_only_its_autocommit_snapshot(
    database_path,
    api_name: str,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        trace: list[str] = []
        connection.set_trace_callback(trace.append)

        _read_ledger_with(api_name, connection)

        connection.set_trace_callback(None)
        transaction_control = tuple(
            statement.strip().upper()
            for statement in trace
            if statement.strip().upper().startswith(
                ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")
            )
        )
        assert transaction_control == ("BEGIN", "ROLLBACK")
        assert connection.in_transaction is False

        connection.execute("BEGIN")
        caller_trace: list[str] = []
        connection.set_trace_callback(caller_trace.append)

        _read_ledger_with(api_name, connection)

        connection.set_trace_callback(None)
        caller_transaction_control = tuple(
            statement.strip().upper()
            for statement in caller_trace
            if statement.strip().upper().startswith(
                ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")
            )
        )
        assert caller_transaction_control == ()
        assert connection.in_transaction is True
        connection.rollback()
    finally:
        connection.set_trace_callback(None)
        connection.close()


def test_ledger_read_snapshot_is_stable_across_a_concurrent_append(
    database_path,
) -> None:
    setup = open_database(database_path)
    try:
        genesis_hash = _bootstrap(setup)
    finally:
        setup.close()
    reader = open_database(database_path)
    writer = open_database(database_path)
    callback_state: dict[str, object] = {"fired": False}

    def append_between_projection_and_authority(statement: str) -> None:
        normalized = " ".join(statement.lower().split())
        if callback_state["fired"] or not (
            "select record_id, branch_id, content_json" in normalized
            and "from authority_records" in normalized
        ):
            return
        callback_state["fired"] = True
        try:
            callback_state["result"] = _append_test_event(
                writer,
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
            )
        except BaseException as error:
            callback_state["error"] = error

    try:
        reader.set_trace_callback(append_between_projection_and_authority)

        first = verify_ledger_chain(reader, BRANCH_ID)

        reader.set_trace_callback(None)
        assert callback_state["fired"] is True
        assert "error" not in callback_state
        appended = cast(
            CommandResult[LedgerAppendResult],
            callback_state["result"],
        )
        assert appended.error is None and appended.value is not None
        assert first.valid is True
        assert first.checked_events == 1
        assert first.root_hash == genesis_hash
        assert reader.in_transaction is False

        second = verify_ledger_chain(reader, BRANCH_ID)

        assert second.valid is True
        assert second.checked_events == 2
        assert second.root_hash == appended.value.event_hash
        assert reader.in_transaction is False
    finally:
        reader.set_trace_callback(None)
        reader.close()
        writer.close()


def test_complete_conversation_is_appended_verified_and_replayed(database_path) -> None:
    connection = open_database(database_path)
    try:
        previous_hash = _bootstrap(connection)
        event_specs = (
            (
                "evt-a2",
                "session_started",
                "system",
                "sys-a1",
                {
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                    "terminal_ref": "terminal:local-a1",
                },
            ),
            (
                "evt-a3",
                "conversation_message_recorded",
                "user",
                "usr-a1",
                {
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                    "role": "user",
                    "text_ref": "text:user-a1",
                },
            ),
            (
                "evt-a4",
                "conversation_message_recorded",
                "amadeus",
                "amd-a1",
                {
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                    "role": "amadeus",
                    "text_ref": "text:amadeus-a1",
                },
            ),
            (
                "evt-a5",
                "session_ended",
                "user",
                "usr-a1",
                {
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                    "reason": "user_requested",
                },
            ),
        )

        results = []
        for ordinal, (event_id, event_type, actor_type, actor_id, payload) in enumerate(
            event_specs,
            start=2,
        ):
            result = append_session_event(
                connection,
                _session_command(
                    ordinal=ordinal,
                    event_id=event_id,
                    event_type=event_type,
                    ledger_seq=ordinal,
                    previous_hash=previous_hash,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    event_payload=payload,
                ),
            )
            assert result.error is None
            assert result.value is not None
            previous_hash = result.value.event_hash
            results.append(result)

        verification = verify_ledger_chain(connection, BRANCH_ID)
        replay = replay_ledger(connection, BRANCH_ID)
        identity = AuthorityRepository(connection).get_validated(IDENTITY_ID)

        assert [item.value.ledger_seq for item in results if item.value] == [2, 3, 4, 5]
        assert tuple(event.event_type for event in replay.events[1:]) == (
            "session_started",
            "conversation_message_recorded",
            "conversation_message_recorded",
            "session_ended",
        )
        assert tuple(payload["text_ref"] for payload in replay.resolved_inline_payloads[2:4]) == (
            "text:user-a1",
            "text:amadeus-a1",
        )
        assert all(
            payload["session_id"] == SESSION_ID
            for payload in replay.resolved_inline_payloads[1:]
        )
        assert replay.resolved_inline_payloads[1]["terminal_ref"] == "terminal:local-a1"
        assert identity is not None and identity.lifecycle_state == "active"
        assert verification.valid is True
        assert verification.checked_events == 5
        assert verification.first_invalid_seq is None
        assert verification.root_hash == previous_hash
        assert replay.through_ledger_seq == 5
        assert replay.root_hash == verification.root_hash
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("message_roles", "attempted_event_type", "attempted_role"),
    (
        ((), "conversation_message_recorded", "amadeus"),
        (("user",), "conversation_message_recorded", "user"),
        (("user", "amadeus"), "conversation_message_recorded", "amadeus"),
        ((), "session_ended", None),
    ),
    ids=("amadeus-first", "duplicate-user", "duplicate-amadeus", "premature-end"),
)
def test_session_rejects_out_of_order_or_duplicate_transition(
    database_path,
    message_roles: tuple[str, ...],
    attempted_event_type: str,
    attempted_role: str | None,
) -> None:
    connection = open_database(database_path)
    try:
        head = _valid_session_head(connection, message_roles)
        ledger_seq = len(message_roles) + 3
        before = tuple(connection.iterdump())
        actor_type = attempted_role or "user"
        actor_id = "amd-a1" if actor_type == "amadeus" else "usr-a1"
        extra = (
            None
            if attempted_role is None
            else {
                "role": attempted_role,
                "text_ref": f"text:{attempted_role}-rejected",
            }
        )

        rejected = _append_test_event(
            connection,
            ordinal=ledger_seq,
            event_id=f"evt-a{ledger_seq}",
            event_type=attempted_event_type,
            ledger_seq=ledger_seq,
            previous_hash=head,
            actor_type=actor_type,
            actor_id=actor_id,
            event_payload_extra=extra,
        )

        _assert_header_body_rejection(rejected)
        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()


@pytest.mark.parametrize(
    "changed_binding",
    ("vault", "instance", "identity-branch"),
)
def test_session_rejects_cross_binding_without_any_write(
    database_path,
    changed_binding: str,
) -> None:
    connection = open_database(database_path)
    try:
        head = _valid_session_head(connection)
        if changed_binding == "identity-branch":
            genesis_b = _bootstrap_scope(connection, "b1")
            branches = (BRANCH_ID, "brn-b1")
            attempt = _session_command(
                ordinal=3,
                event_id="evt-b2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_b,
                actor_type="system",
                actor_id="sys-b1",
                identity_id="idn-b1",
                lineage_id="lin-b1",
                branch_id="brn-b1",
                instance_id="ins-b1",
                vault_id="vlt-b1",
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": "idn-b1",
                    "vault_id": "vlt-b1",
                },
            )
        else:
            branches = (BRANCH_ID,)
            instance_id = (
                "ins-b1" if changed_binding == "instance" else INSTANCE_ID
            )
            vault_id = "vlt-b1" if changed_binding == "vault" else VAULT_ID
            attempt = _session_command(
                ordinal=3,
                event_id="evt-a3",
                event_type="conversation_message_recorded",
                ledger_seq=3,
                previous_hash=head,
                actor_type="user",
                actor_id="usr-a1",
                instance_id=instance_id,
                vault_id=vault_id,
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": vault_id,
                    "role": "user",
                    "text_ref": "text:user-a1",
                },
            )
        before = tuple(connection.iterdump())
        roots_before = tuple(
            verify_ledger_chain(connection, branch_id).root_hash
            for branch_id in branches
        )
        receipts_before = connection.execute(
            "SELECT count(*) FROM command_receipts"
        ).fetchone()[0]

        rejected = append_session_event(connection, attempt)

        _assert_header_body_rejection(rejected)
        assert tuple(connection.iterdump()) == before
        assert tuple(
            verify_ledger_chain(connection, branch_id).root_hash
            for branch_id in branches
        ) == roots_before
        assert connection.execute(
            "SELECT count(*) FROM command_receipts"
        ).fetchone()[0] == receipts_before
    finally:
        connection.close()


def test_session_lookup_ignores_an_unrelated_damaged_branch(database_path) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap_scope(connection, "a1")
        _bootstrap_scope(connection, "b1")
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE ledger_events
            SET media_type = 'application/vnd.damaged+json'
            WHERE event_id = 'evt-b1'
            """
        )

        result = _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=genesis_hash,
            actor_type="system",
            actor_id="sys-a1",
        )

        assert result.error is None
        assert result.value is not None
    finally:
        connection.close()


def test_session_lookup_does_not_verify_an_unrelated_branch(
    database_path,
    monkeypatch,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap_scope(connection, "a1")
        _bootstrap_scope(connection, "b1")
        verified_branches: list[str] = []
        real_verified_events = ledger_module._verified_events

        def recording_verified_events(connection, branch_id):
            verified_branches.append(branch_id)
            return real_verified_events(connection, branch_id)

        monkeypatch.setattr(
            ledger_module,
            "_verified_events",
            recording_verified_events,
        )

        result = _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=genesis_hash,
            actor_type="system",
            actor_id="sys-a1",
        )

        assert result.error is None
        assert set(verified_branches) == {BRANCH_ID}
    finally:
        connection.close()


def test_authority_only_session_start_still_occupies_the_session_id(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        branch_a_genesis = _bootstrap_scope(connection, "a1")
        branch_b_genesis = _bootstrap_scope(connection, "b1")
        branch_b_start = _append_test_event(
            connection,
            ordinal=20,
            event_id="evt-b2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=branch_b_genesis,
            actor_type="system",
            actor_id="sys-b1",
            identity_id="idn-b1",
            lineage_id="lin-b1",
            branch_id="brn-b1",
            instance_id="ins-b1",
            vault_id="vlt-b1",
        )
        assert branch_b_start.error is None
        connection.execute("DROP TRIGGER ledger_events_reject_delete")
        connection.execute("DELETE FROM ledger_events WHERE event_id = 'evt-b2'")
        before = tuple(connection.iterdump())

        rejected = _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=branch_a_genesis,
            actor_type="system",
            actor_id="sys-a1",
        )

        _assert_header_body_rejection(rejected)
        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()


def test_session_and_non_session_authority_keep_their_distinct_correlations(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _valid_session_head(connection)

        correlations = {
            row["record_id"]: row["correlation_id"]
            for row in connection.execute(
                """
                SELECT
                    record_id,
                    json_extract(content_json, '$.correlation_id') AS correlation_id
                FROM authority_records
                WHERE record_id IN ('evt-a1', 'evt-a2')
                """
            )
        }

        assert correlations == {
            "evt-a1": "aud-a1",
            "evt-a2": SESSION_ID,
        }
        assert verify_ledger_chain(connection, BRANCH_ID).valid
    finally:
        connection.close()


def test_verifier_rejects_hash_valid_session_correlation_payload_mismatch(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _valid_session_head(connection)
        stored = AuthorityRepository(connection).get_validated("evt-a2")
        assert isinstance(stored, LedgerEvent)
        body = stored.model_dump(mode="python")
        body["record_header"]["content_hash"] = "0" * 64
        body["correlation_id"] = "session-forged"
        body["event_hash"] = "0" * 64
        forged = cast(LedgerEvent, _seal_record(LedgerEvent, body))
        connection.execute("DROP TRIGGER authority_ledger_reject_update")
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE authority_records
            SET content_json = ?, content_hash = ?
            WHERE record_id = 'evt-a2'
            """,
            (
                canonical_json(forged.model_dump(mode="python")).decode("utf-8"),
                forged.event_hash,
            ),
        )
        connection.execute(
            "UPDATE ledger_events SET event_hash = ? WHERE event_id = 'evt-a2'",
            (forged.event_hash,),
        )

        verification = verify_ledger_chain(connection, BRANCH_ID)

        assert not verification.valid
        assert verification.first_invalid_seq == 2
    finally:
        connection.close()


def test_two_branches_cannot_concurrently_start_the_same_session(
    database_path,
) -> None:
    setup = open_database(database_path)
    try:
        genesis_hashes = {
            "a1": _bootstrap_scope(setup, "a1"),
            "b1": _bootstrap_scope(setup, "b1"),
        }
    finally:
        setup.close()
    barrier = Barrier(2)

    def attempt(suffix: str, ordinal: int):
        connection = open_database(database_path)
        try:
            barrier.wait()
            return _append_test_event(
                connection,
                ordinal=ordinal,
                event_id=f"evt-{suffix[0]}2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hashes[suffix],
                actor_type="system",
                actor_id=f"sys-{suffix}",
                identity_id=f"idn-{suffix}",
                lineage_id=f"lin-{suffix}",
                branch_id=f"brn-{suffix}",
                instance_id=f"ins-{suffix}",
                vault_id=f"vlt-{suffix}",
            )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            future.result()
            for future in (
                executor.submit(attempt, "a1", 2),
                executor.submit(attempt, "b1", 20),
            )
        )

    assert sum(result.error is None for result in results) == 1
    assert sum(result.error is not None for result in results) == 1
    verification = open_database(database_path)
    try:
        assert verification.execute(
            """
            SELECT count(*)
            FROM authority_records
            WHERE json_extract(content_json, '$.record_header.record_type') = 'LedgerEvent'
              AND json_extract(content_json, '$.event_type') = 'session_started'
              AND json_extract(content_json, '$.correlation_id') = ?
            """,
            (SESSION_ID,),
        ).fetchone()[0] == 1
    finally:
        verification.close()


@pytest.mark.parametrize("missing_side", ("projection", "authority"))
def test_missing_ledger_side_reports_valid_prefix_and_cannot_be_extended(
    database_path,
    missing_side: str,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        start = _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=genesis_hash,
            actor_type="system",
            actor_id="sys-a1",
        )
        start_hash = _required_event_hash(start)
        if missing_side == "authority":
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER authority_ledger_reject_delete")
            connection.execute(
                "DELETE FROM authority_records WHERE record_id = 'evt-a2'"
            )
        else:
            connection.execute("DROP TRIGGER ledger_events_reject_delete")
            connection.execute("DELETE FROM ledger_events WHERE event_id = 'evt-a2'")
        before = tuple(connection.iterdump())

        verification = verify_ledger_chain(connection, BRANCH_ID)
        with pytest.raises(ReceiptIntegrityError):
            replay_ledger(connection, BRANCH_ID)
        extension = _append_test_event(
            connection,
            ordinal=3,
            event_id="evt-a3",
            event_type="conversation_message_recorded",
            ledger_seq=3,
            previous_hash=start_hash,
            actor_type="user",
            actor_id="usr-a1",
            event_payload_extra={"role": "user", "text_ref": "text:user-a1"},
        )

        assert verification.valid is False
        assert verification.checked_events == 1
        assert verification.first_invalid_seq == 2
        assert verification.root_hash == genesis_hash
        assert extension.error is not None
        assert extension.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()


def test_projection_and_authority_branch_tamper_cannot_hide_a_tail_event(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        start = append_session_event(
            connection,
            _session_command(
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                },
            ),
        )
        assert start.error is None
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute("DROP TRIGGER authority_ledger_reject_update")
        connection.execute(
            "UPDATE ledger_events SET branch_id = 'brn-b1' WHERE event_id = 'evt-a2'"
        )
        connection.execute(
            "UPDATE authority_records SET branch_id = 'brn-b1' WHERE record_id = 'evt-a2'"
        )
        before = tuple(connection.iterdump())

        verification = verify_ledger_chain(connection, BRANCH_ID)
        extension = append_session_event(
            connection,
            _session_command(
                ordinal=3,
                event_id="evt-a3",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
                event_payload={
                    "session_id": "session-b1",
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                },
            ),
        )

        assert verification.valid is False
        assert verification.checked_events == 1
        assert verification.first_invalid_seq == 2
        assert verification.root_hash == genesis_hash
        assert extension.error is not None
        assert extension.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()


def test_competing_extension_of_the_same_head_is_stale_and_has_zero_writes(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        first = append_session_event(
            connection,
            _session_command(
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                },
            ),
        )
        assert first.error is None and first.value is not None
        before = tuple(connection.iterdump())

        stale = append_session_event(
            connection,
            _session_command(
                ordinal=3,
                event_id="evt-a3",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
                event_payload={
                    "session_id": "session-b1",
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                },
            ),
        )

        assert stale.error is not None
        assert stale.error.code is CoreErrorCode.STALE_VERSION
        assert stale.error.retryable is True
        assert stale.event_ids == ()
        assert tuple(connection.iterdump()) == before
        assert verify_ledger_chain(connection, BRANCH_ID).root_hash == first.value.event_hash
    finally:
        connection.close()


def test_inline_payload_tamper_invalidates_replay_and_blocks_extension(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        start = append_session_event(
            connection,
            _session_command(
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                },
            ),
        )
        assert start.error is None and start.value is not None
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE ledger_events
            SET payload_inline_json = '{"identity_id":"idn-a1","session_id":"tampered","vault_id":"vlt-a1"}'
            WHERE event_id = 'evt-a2'
            """
        )
        before = tuple(connection.iterdump())

        verification = verify_ledger_chain(connection, BRANCH_ID)
        with pytest.raises(ReceiptIntegrityError):
            replay_ledger(connection, BRANCH_ID)
        blocked = append_session_event(
            connection,
            _session_command(
                ordinal=3,
                event_id="evt-a3",
                event_type="conversation_message_recorded",
                ledger_seq=3,
                previous_hash=start.value.event_hash,
                actor_type="user",
                actor_id="usr-a1",
                event_payload={
                    "session_id": SESSION_ID,
                    "identity_id": IDENTITY_ID,
                    "vault_id": VAULT_ID,
                    "role": "user",
                    "text_ref": "text:user-a1",
                },
            ),
        )

        assert verification.valid is False
        assert verification.checked_events == 1
        assert verification.first_invalid_seq == 2
        assert verification.root_hash == genesis_hash
        assert blocked.error is not None
        assert blocked.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()


def test_inline_media_type_tamper_is_rejected_by_the_authority_payload_ref(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        _required_event_hash(
            _append_test_event(
                connection,
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
            )
        )
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE ledger_events
            SET media_type = 'application/vnd.tampered+json'
            WHERE event_id = 'evt-a2'
            """
        )

        verification = verify_ledger_chain(connection, BRANCH_ID)

        assert verification.valid is False
        assert verification.checked_events == 1
        assert verification.first_invalid_seq == 2
        assert verification.root_hash == genesis_hash
    finally:
        connection.close()


def test_unbound_reference_payload_hash_tamper_is_rejected(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        _required_event_hash(
            _append_test_event(
                connection,
                ordinal=2,
                event_id="evt-a2",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
            )
        )
        _replace_with_unbound_reference_payload(connection, "evt-a2", "b" * 64)

        verification = verify_ledger_chain(connection, BRANCH_ID)

        assert verification.valid is False
        assert verification.checked_events == 1
        assert verification.first_invalid_seq == 2
        assert verification.root_hash == genesis_hash
    finally:
        connection.close()


def test_session_state_machine_rejects_message_before_start_role_mismatch_and_after_end(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        before_start = _append_test_event(
            connection,
            ordinal=2,
            event_id="evt-a2",
            event_type="conversation_message_recorded",
            ledger_seq=2,
            previous_hash=genesis_hash,
            actor_type="user",
            actor_id="usr-a1",
            event_payload_extra={"role": "user", "text_ref": "text:too-early"},
        )
        start_hash = _required_event_hash(
            _append_test_event(
                connection,
                ordinal=3,
                event_id="evt-a3",
                event_type="session_started",
                ledger_seq=2,
                previous_hash=genesis_hash,
                actor_type="system",
                actor_id="sys-a1",
            )
        )
        wrong_role = _append_test_event(
            connection,
            ordinal=4,
            event_id="evt-a4",
            event_type="conversation_message_recorded",
            ledger_seq=3,
            previous_hash=start_hash,
            actor_type="user",
            actor_id="usr-a1",
            event_payload_extra={
                "role": "amadeus",
                "text_ref": "text:wrong-role",
            },
        )
        user_hash = _required_event_hash(
            _append_test_event(
                connection,
                ordinal=5,
                event_id="evt-a5",
                event_type="conversation_message_recorded",
                ledger_seq=3,
                previous_hash=start_hash,
                actor_type="user",
                actor_id="usr-a1",
                event_payload_extra={
                    "role": "user",
                    "text_ref": "text:user-a1",
                },
            )
        )
        amadeus_hash = _required_event_hash(
            _append_test_event(
                connection,
                ordinal=6,
                event_id="evt-a6",
                event_type="conversation_message_recorded",
                ledger_seq=4,
                previous_hash=user_hash,
                actor_type="amadeus",
                actor_id="amd-a1",
                event_payload_extra={
                    "role": "amadeus",
                    "text_ref": "text:amadeus-a1",
                },
            )
        )
        end_hash = _required_event_hash(
            _append_test_event(
                connection,
                ordinal=7,
                event_id="evt-a7",
                event_type="session_ended",
                ledger_seq=5,
                previous_hash=amadeus_hash,
                actor_type="user",
                actor_id="usr-a1",
            )
        )
        after_end = _append_test_event(
            connection,
            ordinal=8,
            event_id="evt-a8",
            event_type="conversation_message_recorded",
            ledger_seq=6,
            previous_hash=end_hash,
            actor_type="user",
            actor_id="usr-a1",
            event_payload_extra={"role": "user", "text_ref": "text:too-late"},
        )

        for rejected in (before_start, wrong_role, after_end):
            assert rejected.error is not None
            assert rejected.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
            assert rejected.event_ids == ()
        replay = replay_ledger(connection, BRANCH_ID)
        assert tuple(event.event_type for event in replay.events) == (
            "identity_genesis_created",
            "session_started",
            "conversation_message_recorded",
            "conversation_message_recorded",
            "session_ended",
        )
    finally:
        connection.close()


def test_typed_replay_rejects_a_hash_valid_receipt_with_the_wrong_value_shape(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis_hash = _bootstrap(connection)
        command = _session_command(
            ordinal=2,
            event_id="evt-a2",
            event_type="session_started",
            ledger_seq=2,
            previous_hash=genesis_hash,
            actor_type="system",
            actor_id="sys-a1",
            event_payload={
                "session_id": SESSION_ID,
                "identity_id": IDENTITY_ID,
                "vault_id": VAULT_ID,
            },
        )
        first = append_session_event(connection, command)
        assert first.error is None and first.value is not None
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        malformed = canonical_receipt_result(
            {
                "value": {"unexpected": "shape"},
                "event_ids": ["evt-a2"],
                "error": None,
                "replayed": False,
            }
        )
        connection.execute(
            """
            UPDATE command_receipts
            SET result_json = ?, result_hash = ?
            WHERE command_id = ?
            """,
            (
                malformed.decode("utf-8"),
                sha256_hex(malformed),
                command.command_id,
            ),
        )
        before = tuple(connection.iterdump())

        with pytest.raises(ReceiptIntegrityError):
            append_session_event(connection, command)

        assert tuple(connection.iterdump()) == before
    finally:
        connection.close()
