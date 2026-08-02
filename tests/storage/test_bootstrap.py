from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import get_type_hints

import pytest

import amadeus_core.storage.bootstrap as bootstrap_module
from amadeus_core.contracts.commands import (
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.common import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.identity import Branch, Identity, Lineage
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.bootstrap import (
    BootstrapCommand,
    BootstrapPreallocated,
    BootstrapResult,
    bootstrap_core,
)
from amadeus_core.storage.database import open_database
from amadeus_core.storage.payloads import canonical_receipt_result
from amadeus_core.storage.repository import AuthorityRepository
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
TARGETS = (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, GENESIS_EVENT_ID)
EMPTY_TABLES = (
    "authority_records",
    "ledger_events",
    "identities",
    "lineages",
    "branches",
    "command_receipts",
)


def _bootstrap_command() -> BootstrapCommand:
    return BootstrapCommand(
        preallocated={
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "genesis_event_id": GENESIS_EVENT_ID,
        },
        deployment_policy_ref="deployment:test",
    )


def test_bootstrap_contracts_have_frozen_field_order_and_public_signature() -> None:
    assert tuple(BootstrapCommand.model_fields) == (
        "preallocated",
        "deployment_policy_ref",
    )
    assert tuple(BootstrapResult.model_fields) == (
        "identity_id",
        "lineage_id",
        "branch_id",
        "genesis_event_id",
        "genesis_event_hash",
    )
    hints = get_type_hints(bootstrap_core)
    assert hints["connection"] is sqlite3.Connection
    assert hints["command"] is MutationCommandEnvelope
    assert hints["bootstrap"] is BootstrapCommand


def _mutation_command() -> MutationCommandEnvelope:
    semantic_input_hash = sha256_hex(
        canonical_json(_bootstrap_command().model_dump(mode="python"))
    )
    return MutationCommandEnvelope(
        command_id="cmd-a1",
        command_type="bootstrap",
        actor=Actor(actor_type="system", actor_id="sys-a1"),
        actor_capability_id="mcp-a1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in TARGETS
        ),
        audit_context_id="aud-a1",
        idempotency_key="bootstrap-a1",
        issued_at=NOW,
        target_record_refs=TARGETS,
        payload={
            "scope_refs": (),
            "instance_id": "ins-a1",
            "semantic_input_hash": semantic_input_hash,
        },
    )


def test_bootstrap_creates_four_authorities_atomically(database_path) -> None:
    connection = open_database(database_path)
    try:
        result = bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert result.error is None
        assert result.replayed is False
        assert result.event_ids == (GENESIS_EVENT_ID,)
        assert result.value is not None
        assert result.value.model_dump(mode="python") == {
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "genesis_event_id": GENESIS_EVENT_ID,
            "genesis_event_hash": result.value.genesis_event_hash,
        }
        authorities = connection.execute(
            "SELECT record_id, record_type, version, content_json "
            "FROM authority_records ORDER BY record_type"
        ).fetchall()
        assert {(row["record_id"], row["record_type"]) for row in authorities} == {
            (IDENTITY_ID, "Identity"),
            (LINEAGE_ID, "Lineage"),
            (BRANCH_ID, "Branch"),
            (GENESIS_EVENT_ID, "LedgerEvent"),
        }
        assert {row["version"] for row in authorities} == {1}
        assert connection.execute("SELECT count(*) FROM identities").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM lineages").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM branches").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM branches WHERE status = 'active'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_type = 'SourceSnapshot'"
        ).fetchone()[0] == 0
        repository = AuthorityRepository(connection)
        identity = repository.get(IDENTITY_ID)
        lineage = repository.get(LINEAGE_ID)
        branch = repository.get(BRANCH_ID)
        event = repository.get(GENESIS_EVENT_ID)
        assert isinstance(identity, Identity)
        assert identity.created_from_snapshot_id is None
        assert identity.record_header.created_at == NOW
        assert isinstance(lineage, Lineage)
        assert lineage.root_snapshot_id is None
        assert lineage.lineage_hash == sha256_hex(
            canonical_json(
                {
                    "kind": "core-genesis-lineage-v0.1",
                    "identity_id": IDENTITY_ID,
                    "lineage_id": LINEAGE_ID,
                    "branch_id": BRANCH_ID,
                    "deployment_policy_ref": "deployment:test",
                }
            )
        )
        assert isinstance(branch, Branch)
        assert branch.parent_branch_ids == ()
        assert branch.fork_reason == "explicit_reconstruction"
        assert branch.fork_event_id == GENESIS_EVENT_ID
        assert branch.base_ledger_seq == 0
        assert branch.status == "active"
        assert branch.status_reason_event_id == GENESIS_EVENT_ID
        assert branch.activated_at == NOW
        assert branch.merge_policy == "explicit_only"
        assert isinstance(event, LedgerEvent)
        assert event.ledger_seq == 1
        assert event.previous_event_hash is None
        assert event.event_type == "identity_genesis_created"
        assert event.instance_id == "ins-a1"
        assert event.actor_type == "system"
        assert event.actor_id == "sys-a1"
        assert event.occurred_at == event.ingested_at == NOW
        assert event.event_hash == event.record_header.content_hash
        assert compute_record_content_hash(event) == event.event_hash
        assert event.event_hash == result.value.genesis_event_hash
    finally:
        connection.close()


@pytest.mark.parametrize(
    "insert_name",
    ("_insert_identity", "_insert_lineage", "_insert_branch", "_insert_event"),
)
def test_bootstrap_insert_failure_rolls_back_every_table_and_receipt(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
    insert_name: str,
) -> None:
    connection = open_database(database_path)

    def fail_insert(*args, **kwargs) -> None:
        del args, kwargs
        raise sqlite3.IntegrityError(f"injected failure at {insert_name}")

    monkeypatch.setattr(bootstrap_module, insert_name, fail_insert)
    try:
        result = bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert result.value is None
        assert result.event_ids == ()
        assert result.error is not None
        assert result.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_deferred_foreign_key_commit_failure_rolls_back_everything(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = open_database(database_path)

    def insert_event_with_dangling_branch(repository, event, payload) -> None:
        body = event.model_dump(mode="python")
        body["branch_id"] = "brn-dead"
        body["record_header"] = event.record_header.model_copy(
            update={"branch_id": "brn-dead", "content_hash": "0" * 64}
        ).model_dump(mode="python")
        body["event_hash"] = "0" * 64
        draft = LedgerEvent.model_validate(body)
        digest = compute_record_content_hash(draft)
        dangling = draft.model_copy(
            update={
                "record_header": draft.record_header.model_copy(
                    update={"content_hash": digest}
                ),
                "event_hash": digest,
            }
        )
        repository.append_ledger_event(
            dangling.model_dump(mode="python"), payload=payload
        )

    monkeypatch.setattr(
        bootstrap_module,
        "_insert_event",
        insert_event_with_dangling_branch,
    )
    try:
        result = bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert result.error is not None
        assert result.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_hash_failure_after_partial_writes_rolls_back_everything(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = open_database(database_path)
    original_insert = bootstrap_module._insert_branch

    def insert_corrupt_branch(repository, branch) -> None:
        corrupt = branch.model_copy(
            update={
                "record_header": branch.record_header.model_copy(
                    update={"content_hash": "f" * 64}
                )
            }
        )
        original_insert(repository, corrupt)

    monkeypatch.setattr(bootstrap_module, "_insert_branch", insert_corrupt_branch)
    try:
        result = bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert result.error is not None
        assert result.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_does_not_swallow_base_exception_and_still_rolls_back(
    database_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = open_database(database_path)

    def interrupt(*args, **kwargs) -> None:
        del args, kwargs
        raise KeyboardInterrupt

    monkeypatch.setattr(bootstrap_module, "_insert_lineage", interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            bootstrap_core(connection, _mutation_command(), _bootstrap_command())
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_replay_returns_typed_result_without_duplicate_writes(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        first = bootstrap_core(connection, _mutation_command(), _bootstrap_command())
        replay = bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert first.error is None
        assert replay.error is None
        assert replay.replayed is True
        assert isinstance(replay.value, BootstrapResult)
        assert replay.value == first.value
        assert connection.execute("SELECT count(*) FROM authority_records").fetchone()[0] == 4
        assert connection.execute("SELECT count(*) FROM ledger_events").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0] == 1
    finally:
        connection.close()


def test_bootstrap_preserves_stale_and_idempotency_error_semantics(database_path) -> None:
    connection = open_database(database_path)
    try:
        first = bootstrap_core(connection, _mutation_command(), _bootstrap_command())
        assert first.error is None
        stale_command = _mutation_command().model_copy(
            update={
                "command_id": "cmd-a2",
                "idempotency_key": "bootstrap-a2",
            }
        )
        stale = bootstrap_core(connection, stale_command, _bootstrap_command())
        conflict_command = _mutation_command().model_copy(
            update={
                "payload": {
                    **dict(_mutation_command().payload),
                    "instance_id": "ins-a2",
                },
            }
        )
        conflict = bootstrap_core(connection, conflict_command, _bootstrap_command())

        assert stale.error is not None
        assert stale.error.code is CoreErrorCode.STALE_VERSION
        assert conflict.error is not None
        assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
        assert connection.execute("SELECT count(*) FROM authority_records").fetchone()[0] == 4
        assert connection.execute("SELECT count(*) FROM command_receipts").fetchone()[0] == 1
    finally:
        connection.close()


@pytest.mark.parametrize(
    "invalid_kind",
    ("actor", "actor_id", "instance", "instance_prefix", "target"),
)
def test_bootstrap_rejects_invalid_write_api_correspondence_before_writes(
    database_path,
    invalid_kind: str,
) -> None:
    command = _mutation_command()
    if invalid_kind == "actor":
        command = command.model_copy(
            update={"actor": Actor(actor_type="amadeus", actor_id="amd-a1")}
        )
    elif invalid_kind == "actor_id":
        command = command.model_copy(
            update={"actor": Actor(actor_type="system", actor_id="system-test")}
        )
    elif invalid_kind == "instance":
        payload = dict(command.payload)
        payload.pop("instance_id")
        command = command.model_copy(update={"payload": payload})
    elif invalid_kind == "instance_prefix":
        payload = dict(command.payload)
        payload["instance_id"] = "abc-a1"
        command = command.model_copy(update={"payload": payload})
    else:
        wrong_targets = (IDENTITY_ID, LINEAGE_ID, BRANCH_ID, "evt-af")
        command = command.model_copy(
            update={
                "target_record_refs": wrong_targets,
                "expected_versions": tuple(
                    ExpectedVersion(
                        target_record_ref=target,
                        expected_version="absent",
                    )
                    for target in wrong_targets
                ),
            }
        )
    connection = open_database(database_path)
    try:
        result = bootstrap_core(connection, command, _bootstrap_command())

        assert result.error is not None
        assert result.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_maps_unvalidated_bootstrap_contract_without_beginning_writes(
    database_path,
) -> None:
    invalid_preallocated = BootstrapPreallocated.model_construct(
        identity_id="not-an-identity-id",
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        genesis_event_id=GENESIS_EVENT_ID,
    )
    invalid = BootstrapCommand.model_construct(
        preallocated=invalid_preallocated,
        deployment_policy_ref="deployment:test",
    )
    connection = open_database(database_path)
    try:
        result = bootstrap_core(connection, _mutation_command(), invalid)

        assert result.error is not None
        assert result.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        for table in EMPTY_TABLES:
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_bootstrap_semantic_input_hash_binds_external_argument_on_replay(
    database_path,
) -> None:
    connection = open_database(database_path)
    try:
        command = _mutation_command()
        first = bootstrap_core(connection, command, _bootstrap_command())
        assert first.error is None
        before = tuple(
            tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall())
            for table in EMPTY_TABLES
        )
        alternate = BootstrapCommand(
            preallocated=_bootstrap_command().preallocated,
            deployment_policy_ref="deployment:other",
        )

        unbound = bootstrap_core(connection, command, alternate)

        assert unbound.error is not None
        assert unbound.error.code is CoreErrorCode.BOOTSTRAP_FAILED
        assert tuple(
            tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall())
            for table in EMPTY_TABLES
        ) == before

        alternate_hash = sha256_hex(
            canonical_json(alternate.model_dump(mode="python"))
        )
        rebound_payload = dict(command.payload)
        rebound_payload["semantic_input_hash"] = alternate_hash
        rebound_command = command.model_copy(update={"payload": rebound_payload})
        conflict = bootstrap_core(connection, rebound_command, alternate)
        assert conflict.error is not None
        assert conflict.error.code is CoreErrorCode.IDEMPOTENCY_CONFLICT
    finally:
        connection.close()


def test_bootstrap_propagates_closed_caller_connection_error(database_path) -> None:
    connection = open_database(database_path)
    connection.close()

    with pytest.raises(sqlite3.ProgrammingError):
        bootstrap_core(connection, _mutation_command(), _bootstrap_command())


def test_bootstrap_replay_propagates_corrupted_receipt_integrity(database_path) -> None:
    connection = open_database(database_path)
    try:
        first = bootstrap_core(connection, _mutation_command(), _bootstrap_command())
        assert first.error is None
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        connection.execute("UPDATE command_receipts SET command_hash = zeroblob(64)")
        before = tuple(connection.execute("SELECT * FROM command_receipts").fetchall())

        with pytest.raises(ReceiptIntegrityError):
            bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert tuple(connection.execute("SELECT * FROM command_receipts").fetchall()) == before
    finally:
        connection.close()


def test_bootstrap_replay_rejects_operation_specific_value_shape(database_path) -> None:
    connection = open_database(database_path)
    try:
        first = bootstrap_core(connection, _mutation_command(), _bootstrap_command())
        assert first.error is None
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        corrupt_result = canonical_receipt_result(
            {
                "value": {"unexpected": "shape"},
                "event_ids": [GENESIS_EVENT_ID],
                "error": None,
                "replayed": False,
            }
        )
        connection.execute(
            "UPDATE command_receipts SET result_json = ?, result_hash = ?",
            (corrupt_result.decode("utf-8"), sha256_hex(corrupt_result)),
        )
        before = tuple(
            tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall())
            for table in EMPTY_TABLES
        )

        with pytest.raises(ReceiptIntegrityError):
            bootstrap_core(connection, _mutation_command(), _bootstrap_command())

        assert tuple(
            tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall())
            for table in EMPTY_TABLES
        ) == before
    finally:
        connection.close()
