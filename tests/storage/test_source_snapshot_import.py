from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, cast, get_type_hints

import pytest

import amadeus_core.storage.source_snapshot_import as source_import_module

from amadeus_core.contracts.commands import (
    ExpectedVersion,
    MutationCommandEnvelope,
    compute_command_hash,
)
from amadeus_core.contracts.common import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)
from amadeus_core.contracts.source_snapshot import SourceSnapshot
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.bootstrap import (
    BootstrapCommand,
    bootstrap_core,
)
from amadeus_core.storage._records import _seal_record
from amadeus_core.storage.database import open_database
from amadeus_core.storage.ledger import append_session_event
from amadeus_core.storage.payloads import canonical_receipt_result, prepare_inline_payload
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.source_snapshot_import import (
    SourceSnapshotImportResult,
    import_source_snapshot,
)
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


GENESIS_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
IMPORT_AT = GENESIS_AT + timedelta(hours=1)
IDENTITY_ID = "idn-b1"
LINEAGE_ID = "lin-b1"
BRANCH_ID = "brn-b1"
GENESIS_EVENT_ID = "evt-b1"
SNAPSHOT_ID = "snp-b1"
IMPORT_EVENT_ID = "evt-b2"
DEPLOYMENT_POLICY_REF = "deployment:test"


def _seal(model_type: type[Any], body: dict[str, object]):
    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    header = draft.record_header.model_copy(update={"content_hash": digest})
    return draft.model_copy(update={"record_header": header})


def _header(
    record_type: str,
    record_id: str,
    *,
    event_id: str = IMPORT_EVENT_ID,
    imported_at: datetime = IMPORT_AT,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": record_type,
        "record_id": record_id,
        "identity_id": IDENTITY_ID,
        "lineage_id": LINEAGE_ID,
        "branch_id": BRANCH_ID,
        "created_at": imported_at,
        "created_by_event_id": event_id,
        "deployment_policy_ref": DEPLOYMENT_POLICY_REF,
        "canonicalization": "core-canonical-json-v1",
        "hash_algorithm": "sha256",
        "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
        "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
        "hash_scope": HASH_SCOPE_REGISTRY[(record_type, "0.1")],
        "content_hash": "0" * 64,
    }


def _bootstrap(connection):
    targets = (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, GENESIS_EVENT_ID)
    bootstrap = BootstrapCommand(
        preallocated={
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "genesis_event_id": GENESIS_EVENT_ID,
        },
        deployment_policy_ref=DEPLOYMENT_POLICY_REF,
    )
    semantic_input_hash = sha256_hex(
        canonical_json(bootstrap.model_dump(mode="python"))
    )
    command = MutationCommandEnvelope(
        command_id="cmd-b1",
        command_type="bootstrap",
        actor=Actor(actor_type="system", actor_id="sys-b1"),
        actor_capability_id="mcp-b1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-b1",
        idempotency_key="bootstrap-b1",
        issued_at=GENESIS_AT,
        target_record_refs=targets,
        payload={
            "scope_refs": (),
            "instance_id": "ins-b1",
            "semantic_input_hash": semantic_input_hash,
        },
    )
    result = bootstrap_core(connection, command, bootstrap)
    assert result.error is None
    assert result.value is not None
    return result.value


def _snapshot(
    *,
    snapshot_id: str = SNAPSHOT_ID,
    event_id: str = IMPORT_EVENT_ID,
    imported_at: datetime = IMPORT_AT,
) -> SourceSnapshot:
    return _seal(
        SourceSnapshot,
        {
            "record_header": _header(
                "SourceSnapshot",
                snapshot_id,
                event_id=event_id,
                imported_at=imported_at,
            ),
            "snapshot_id": snapshot_id,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "source_type": "import",
            "source_ref": "source:test",
            "cutoff_at": GENESIS_AT,
            "imported_at": imported_at,
            "manifest_hash": "2" * 64,
            "payload_root_hash": "3" * 64,
            "parent_snapshot_id": None,
            "deployment_policy_ref": DEPLOYMENT_POLICY_REF,
            "status": "active",
            "version": 1,
        },
    )


def _import_command(
    *,
    snapshot_id: str = SNAPSHOT_ID,
    event_id: str = IMPORT_EVENT_ID,
    identity_version: int = 1,
    lineage_version: int = 1,
    command_id: str = "cmd-b2",
    idempotency_key: str = "source-import-b1",
    issued_at: datetime = IMPORT_AT,
    actor_type: str = "system",
    actor_id: str = "sys-b1",
    semantic_snapshot: SourceSnapshot | None = None,
) -> MutationCommandEnvelope:
    targets = (snapshot_id, IDENTITY_ID, LINEAGE_ID, event_id)
    expected = ("absent", identity_version, lineage_version, "absent")
    bound_snapshot = semantic_snapshot or _snapshot(
        snapshot_id=snapshot_id,
        event_id=event_id,
        imported_at=issued_at,
    )
    semantic_input_hash = sha256_hex(
        canonical_json(bound_snapshot.model_dump(mode="python"))
    )
    return MutationCommandEnvelope(
        command_id=command_id,
        command_type="import_source_snapshot",
        actor=Actor(actor_type=actor_type, actor_id=actor_id),
        actor_capability_id="mcp-b1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version=version)
            for target, version in zip(targets, expected, strict=True)
        ),
        audit_context_id="aud-b2",
        idempotency_key=idempotency_key,
        issued_at=issued_at,
        target_record_refs=targets,
        payload={
            "scope_refs": (),
            "instance_id": "ins-b1",
            "event_id": event_id,
            "semantic_input_hash": semantic_input_hash,
        },
    )


def test_source_snapshot_import_result_has_frozen_field_order_and_signature() -> None:
    assert tuple(SourceSnapshotImportResult.model_fields) == (
        "snapshot_id",
        "identity_id",
        "lineage_id",
        "event_id",
    )
    hints = get_type_hints(import_source_snapshot)
    assert hints["connection"] is sqlite3.Connection
    assert hints["command"] is MutationCommandEnvelope
    assert hints["snapshot"] is SourceSnapshot


def _stored_state(connection) -> tuple[tuple[object, ...], ...]:
    state: list[tuple[object, ...]] = []
    for table in (
        "authority_records",
        "ledger_events",
        "identities",
        "lineages",
        "branches",
        "command_receipts",
    ):
        rows = connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
        state.append((table, *(tuple(row) for row in rows)))
    return tuple(state)


def _replace_genesis_with_unbound_reference(connection) -> None:
    stored = AuthorityRepository(connection).get_validated(GENESIS_EVENT_ID)
    assert isinstance(stored, LedgerEvent)
    body = stored.model_dump(mode="python")
    body["record_header"]["content_hash"] = "0" * 64
    body["event_hash"] = "0" * 64
    body["payload_ref"] = "reference:blob:genesis-b1"
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
            GENESIS_EVENT_ID,
        ),
    )
    connection.execute(
        """
        UPDATE ledger_events
        SET event_hash = ?,
            payload_ref = ?,
            payload_mode = 'reference',
            payload_inline_json = NULL,
            payload_external_ref = 'blob:genesis-b1',
            payload_hash = ?,
            media_type = 'application/json'
        WHERE event_id = ?
        """,
        (
            reference_event.event_hash,
            reference_event.payload_ref,
            "b" * 64,
            GENESIS_EVENT_ID,
        ),
    )


def _assert_hash_scope_zero_write(result, connection, before) -> None:
    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
    assert _stored_state(connection) == before
    assert connection.execute("SELECT max(ledger_seq) FROM ledger_events").fetchone()[0] == 1


def test_source_snapshot_import_updates_identity_lineage_and_chain_atomically(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        genesis = _bootstrap(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        assert result.error is None
        assert result.replayed is False
        assert result.event_ids == (IMPORT_EVENT_ID,)
        assert result.value is not None
        assert result.value.model_dump(mode="python") == {
            "snapshot_id": SNAPSHOT_ID,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "event_id": IMPORT_EVENT_ID,
        }
        repository = AuthorityRepository(connection)
        snapshot = repository.get(SNAPSHOT_ID)
        identity = repository.get(IDENTITY_ID)
        lineage = repository.get(LINEAGE_ID)
        event = repository.get(IMPORT_EVENT_ID)
        assert snapshot is not None and snapshot.version == 1
        assert compute_record_content_hash(snapshot) == snapshot.record_header.content_hash
        assert identity is not None
        assert identity.created_from_snapshot_id == SNAPSHOT_ID
        assert identity.version == 2
        assert compute_record_content_hash(identity) == identity.record_header.content_hash
        assert lineage is not None
        assert lineage.root_snapshot_id == SNAPSHOT_ID
        assert lineage.version == 2
        assert compute_record_content_hash(lineage) == lineage.record_header.content_hash
        assert event is not None
        assert event.ledger_seq == 2
        assert event.previous_event_hash == genesis.genesis_event_hash
        assert event.event_hash == event.record_header.content_hash
        assert compute_record_content_hash(event) == event.event_hash
        assert event.mutation_command_id == "cmd-b2"
        assert event.mutation_command_hash == compute_command_hash(_import_command())
        assert event.correlation_id == "aud-b2"
        assert event.occurred_at == event.ingested_at == IMPORT_AT
        assert event.actor_type == "system"
        assert event.actor_id == "sys-b1"
        assert connection.execute("SELECT count(*) FROM authority_records").fetchone()[0] == 6
        assert connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0] == 2
    finally:
        connection.close()


def test_source_snapshot_insert_failure_after_updates_rolls_back_every_change(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = open_database(database_path)

    def fail_event_insert(*args, **kwargs) -> None:
        del args, kwargs
        raise sqlite3.IntegrityError("injected event foreign-key failure")

    monkeypatch.setattr(
        source_import_module,
        "_append_import_event",
        fail_event_insert,
    )
    try:
        _bootstrap(connection)
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
        assert _stored_state(connection) == before
        identity = AuthorityRepository(connection).get(IDENTITY_ID)
        lineage = AuthorityRepository(connection).get(LINEAGE_ID)
        assert identity is not None and identity.created_from_snapshot_id is None
        assert lineage is not None and lineage.root_snapshot_id is None
    finally:
        connection.close()


def test_source_snapshot_import_replay_is_typed_and_has_no_duplicate_writes(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        first = import_source_snapshot(connection, _import_command(), _snapshot())
        replay = import_source_snapshot(connection, _import_command(), _snapshot())

        assert first.error is None
        assert replay.error is None
        assert replay.replayed is True
        assert isinstance(replay.value, SourceSnapshotImportResult)
        assert replay.value == first.value
        assert connection.execute("SELECT count(*) FROM authority_records").fetchone()[0] == 6
        assert connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0] == 2
    finally:
        connection.close()


def test_second_initial_source_snapshot_is_rejected_without_supersede_flow(
    database_path,
) -> None:
    second_import_at = IMPORT_AT + timedelta(hours=1)
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        first = import_source_snapshot(connection, _import_command(), _snapshot())
        assert first.error is None
        before = _stored_state(connection)
        second_command = _import_command(
            snapshot_id="snp-b2",
            event_id="evt-b3",
            identity_version=2,
            lineage_version=2,
            command_id="cmd-b3",
            idempotency_key="source-import-b2",
            issued_at=second_import_at,
        )
        second_snapshot = _snapshot(
            snapshot_id="snp-b2",
            event_id="evt-b3",
            imported_at=second_import_at,
        )

        rejected = import_source_snapshot(connection, second_command, second_snapshot)

        assert rejected.error is not None
        assert rejected.error.code is CoreErrorCode.STALE_VERSION
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_amadeus_actor_can_import_initial_source_snapshot(database_path) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        command = _import_command(actor_type="amadeus", actor_id="amd-b1")

        result = import_source_snapshot(connection, command, _snapshot())

        assert result.error is None
        event = AuthorityRepository(connection).get(IMPORT_EVENT_ID)
        assert event is not None
        assert event.actor_type == "amadeus"
        assert event.actor_id == "amd-b1"
    finally:
        connection.close()


def test_source_snapshot_hash_failure_returns_precise_error_with_zero_changes(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        before = _stored_state(connection)
        snapshot = _snapshot()
        corrupt = snapshot.model_copy(
            update={
                "record_header": snapshot.record_header.model_copy(
                    update={"content_hash": "f" * 64}
                )
            }
        )

        result = import_source_snapshot(
            connection,
            _import_command(semantic_snapshot=corrupt),
            corrupt,
        )

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_import_rejects_tampered_genesis_chain_hash(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            "UPDATE ledger_events SET event_hash = ? WHERE event_id = ?",
            ("f" * 64, GENESIS_EVENT_ID),
        )
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_import_rejects_tampered_genesis_payload_projection(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        alternate = prepare_inline_payload({"tampered": True})
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE ledger_events
            SET
                payload_ref = ?,
                payload_mode = ?,
                payload_inline_json = ?,
                payload_external_ref = ?,
                payload_hash = ?,
                media_type = ?
            WHERE event_id = ?
            """,
            (
                alternate.payload_ref,
                alternate.mode,
                alternate.inline_json,
                alternate.external_ref,
                alternate.payload_hash,
                alternate.media_type,
                GENESIS_EVENT_ID,
            ),
        )
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_import_rejects_genesis_inline_media_type_tamper(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        connection.execute("DROP TRIGGER ledger_events_reject_update")
        connection.execute(
            """
            UPDATE ledger_events
            SET media_type = 'application/vnd.tampered+json'
            WHERE event_id = ?
            """,
            (GENESIS_EVENT_ID,),
        )
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        _assert_hash_scope_zero_write(result, connection, before)
    finally:
        connection.close()


def test_source_snapshot_import_rejects_unbound_reference_genesis(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        _replace_genesis_with_unbound_reference(connection)
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        _assert_hash_scope_zero_write(result, connection, before)
    finally:
        connection.close()


def test_source_snapshot_import_rejects_authority_only_ledger_tail(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        bootstrap = _bootstrap(connection)
        tail_event_id = "evt-b3"
        tail_command = MutationCommandEnvelope(
            command_id="cmd-b3",
            command_type="ledger.session.append",
            actor=Actor(actor_type="system", actor_id="sys-b3"),
            actor_capability_id="mcp-b3",
            expected_versions=(
                ExpectedVersion(
                    target_record_ref=tail_event_id,
                    expected_version="absent",
                ),
            ),
            audit_context_id="aud-b3",
            idempotency_key="session-tail-b3",
            issued_at=GENESIS_AT + timedelta(minutes=30),
            target_record_refs=(tail_event_id,),
            payload={
                "event_id": tail_event_id,
                "identity_id": IDENTITY_ID,
                "lineage_id": LINEAGE_ID,
                "branch_id": BRANCH_ID,
                "instance_id": "ins-b1",
                "vault_id": "vlt-b1",
                "event_type": "session_started",
                "ledger_seq": 2,
                "expected_previous_event_hash": bootstrap.genesis_event_hash,
                "event_payload": {
                    "session_id": "session-b3",
                    "identity_id": IDENTITY_ID,
                    "vault_id": "vlt-b1",
                },
                "scope_refs": (
                    f"identity:{IDENTITY_ID}",
                    "vault:vlt-b1",
                ),
            },
        )
        tail = append_session_event(connection, tail_command)
        assert tail.error is None and tail.value is not None
        connection.execute("DROP TRIGGER ledger_events_reject_delete")
        connection.execute(
            "DELETE FROM ledger_events WHERE event_id = ?",
            (tail_event_id,),
        )
        assert connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_id = ?",
            (tail_event_id,),
        ).fetchone()[0] == 1
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        _assert_hash_scope_zero_write(result, connection, before)
    finally:
        connection.close()


def test_source_snapshot_import_rejects_branch_projection_divergence(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        connection.execute(
            "UPDATE branches SET status = 'inactive' WHERE branch_id = ?",
            (BRANCH_ID,),
        )
        branch = AuthorityRepository(connection).get(BRANCH_ID)
        assert branch is not None and branch.status == "active"
        assert connection.execute(
            "SELECT status FROM branches WHERE branch_id = ?",
            (BRANCH_ID,),
        ).fetchone()[0] == "inactive"
        before = _stored_state(connection)

        result = import_source_snapshot(connection, _import_command(), _snapshot())

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.ACTIVE_BRANCH_INVARIANT
        assert _stored_state(connection) == before
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("invalid_kind", "expected_code"),
    (
        ("actor", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("actor_id", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("instance", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("instance_prefix", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("event", CoreErrorCode.HEADER_BODY_MISMATCH),
        ("target", CoreErrorCode.VERSION_TARGET_SET_MISMATCH),
    ),
)
def test_source_snapshot_import_rejects_invalid_write_api_correspondence(
    database_path,
    invalid_kind: str,
    expected_code: CoreErrorCode,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        before = _stored_state(connection)
        command = _import_command()
        if invalid_kind == "actor":
            command = command.model_copy(
                update={"actor": Actor(actor_type="governor", actor_id="gov-b1")}
            )
        elif invalid_kind == "actor_id":
            command = command.model_copy(
                update={"actor": Actor(actor_type="system", actor_id="system-test")}
            )
        elif invalid_kind == "instance":
            payload = dict(command.payload)
            payload.pop("instance_id")
            command = command.model_copy(
                update={"payload": payload}
            )
        elif invalid_kind == "instance_prefix":
            payload = dict(command.payload)
            payload["instance_id"] = "abc-b1"
            command = command.model_copy(update={"payload": payload})
        elif invalid_kind == "event":
            payload = dict(command.payload)
            payload.pop("event_id")
            command = command.model_copy(
                update={"payload": payload}
            )
        else:
            wrong_targets = (SNAPSHOT_ID, IDENTITY_ID, LINEAGE_ID, "evt-bf")
            expected = ("absent", 1, 1, "absent")
            command = command.model_copy(
                update={
                    "target_record_refs": wrong_targets,
                    "expected_versions": tuple(
                        ExpectedVersion(
                            target_record_ref=target,
                            expected_version=version,
                        )
                        for target, version in zip(
                            wrong_targets, expected, strict=True
                        )
                    ),
                }
            )

        result = import_source_snapshot(connection, command, _snapshot())

        assert result.error is not None
        assert result.error.code is expected_code
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_import_preserves_uow_stale_and_conflict_semantics(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        stale_command = _import_command(identity_version=2)
        before_stale = _stored_state(connection)

        stale = import_source_snapshot(connection, stale_command, _snapshot())

        assert stale.error is not None
        assert stale.error.code is CoreErrorCode.STALE_VERSION
        assert _stored_state(connection) == before_stale

        first = import_source_snapshot(connection, _import_command(), _snapshot())
        assert first.error is None
        before_conflict = _stored_state(connection)
        conflict_command = _import_command().model_copy(
            update={
                "payload": {
                    **dict(_import_command().payload),
                    "instance_id": "ins-b2",
                }
            }
        )

        conflict = import_source_snapshot(connection, conflict_command, _snapshot())

        assert conflict.error is not None
        assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
        assert _stored_state(connection) == before_conflict
    finally:
        connection.close()


def test_source_snapshot_import_does_not_swallow_base_exception(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = open_database(database_path)

    def stop(*args, **kwargs) -> None:
        del args, kwargs
        raise SystemExit(3)

    monkeypatch.setattr(source_import_module, "_update_identity", stop)
    try:
        _bootstrap(connection)
        before = _stored_state(connection)
        with pytest.raises(SystemExit) as captured:
            import_source_snapshot(connection, _import_command(), _snapshot())
        assert captured.value.code == 3
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_import_maps_unvalidated_snapshot_contract(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        _bootstrap(connection)
        before = _stored_state(connection)
        valid = _snapshot()
        raw = {field: getattr(valid, field) for field in SourceSnapshot.model_fields}
        raw["version"] = 0
        invalid = SourceSnapshot.model_construct(**raw)

        result = import_source_snapshot(connection, _import_command(), invalid)

        assert result.error is not None
        assert result.error.code is CoreErrorCode.HEADER_BODY_MISMATCH
        assert _stored_state(connection) == before
    finally:
        connection.close()


def test_source_snapshot_semantic_input_hash_binds_external_argument_on_replay(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        command = _import_command()
        _bootstrap(connection)
        first = import_source_snapshot(connection, command, _snapshot())
        assert first.error is None
        before = _stored_state(connection)
        original = _snapshot()
        alternate_body = original.model_dump(mode="python")
        alternate_body["source_ref"] = "source:other"
        alternate_body["record_header"] = original.record_header.model_copy(
            update={"content_hash": "0" * 64}
        ).model_dump(mode="python")
        alternate = _seal(SourceSnapshot, alternate_body)

        unbound = import_source_snapshot(connection, command, alternate)

        assert unbound.error is not None
        assert unbound.error.code is CoreErrorCode.HASH_SCOPE_MISMATCH
        assert _stored_state(connection) == before

        alternate_hash = sha256_hex(
            canonical_json(alternate.model_dump(mode="python"))
        )
        rebound_payload = dict(command.payload)
        rebound_payload["semantic_input_hash"] = alternate_hash
        rebound_command = command.model_copy(update={"payload": rebound_payload})
        conflict = import_source_snapshot(connection, rebound_command, alternate)
        assert conflict.error is not None
        assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
    finally:
        connection.close()


def test_source_snapshot_replay_rejects_operation_specific_value_shape(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        command = _import_command()
        _bootstrap(connection)
        first = import_source_snapshot(connection, command, _snapshot())
        assert first.error is None
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        corrupt_result = canonical_receipt_result(
            {
                "value": {"unexpected": "shape"},
                "event_ids": [IMPORT_EVENT_ID],
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
            (corrupt_result.decode("utf-8"), sha256_hex(corrupt_result), command.command_id),
        )
        before = _stored_state(connection)

        with pytest.raises(ReceiptIntegrityError):
            import_source_snapshot(connection, command, _snapshot())

        assert _stored_state(connection) == before
    finally:
        connection.close()
