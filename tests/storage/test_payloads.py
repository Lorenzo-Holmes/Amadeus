from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from amadeus_core.contracts.hashing import canonical_json, sha256_hex


def _database(path: Path):
    from amadeus_core.storage.database import SQLiteDatabase

    return SQLiteDatabase(path)


def _insert_ledger_payload(connection, stored_payload) -> None:
    connection.execute("BEGIN")
    connection.execute(
        """
        INSERT INTO authority_records (
            record_id,
            record_type,
            schema_version,
            identity_id,
            lineage_id,
            branch_id,
            version,
            content_json,
            content_hash,
            created_at
        ) VALUES (
            'evt-a', 'LedgerEvent', '0.1', 'idn-a', 'lin-a', 'brn-a', 1,
            '{}', ?, '2026-08-01T00:00:00Z'
        )
        """,
        ("0" * 64,),
    )
    connection.execute(
        """
        INSERT INTO ledger_events (
            event_id,
            branch_id,
            ledger_seq,
            previous_event_hash,
            event_hash,
            payload_ref,
            payload_mode,
            payload_inline_json,
            payload_external_ref,
            payload_hash,
            media_type
        ) VALUES ('evt-a', 'brn-a', 1, NULL, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0" * 64,
            stored_payload.payload_ref,
            stored_payload.mode,
            stored_payload.inline_json,
            stored_payload.external_ref,
            stored_payload.payload_hash,
            stored_payload.media_type,
        ),
    )


def test_inline_payload_uses_closed_json_canonical_hash_and_resolves(
    database_path: Path,
) -> None:
    from amadeus_core.storage.payloads import (
        SQLiteLedgerPayloadResolver,
        prepare_inline_payload,
    )

    payload = {"kind": "session", "nested": {"count": 1}, "flags": [True, None]}
    stored = prepare_inline_payload(payload)

    assert stored.mode == "inline"
    assert stored.payload_hash == sha256_hex(canonical_json(payload))
    assert stored.payload_ref == f"inline:{stored.payload_hash}"
    assert stored.external_ref is None

    connection = _database(database_path).connect()
    try:
        _insert_ledger_payload(connection, stored)
        resolved = SQLiteLedgerPayloadResolver(connection).resolve(stored.payload_ref)
        assert isinstance(resolved, Mapping)
        assert resolved["kind"] == "session"
        assert resolved["nested"]["count"] == 1
        connection.rollback()
    finally:
        connection.close()


def test_high_precision_decimal_payload_round_trips_without_float_loss(
    database_path: Path,
) -> None:
    from amadeus_core.storage.payloads import (
        SQLiteLedgerPayloadResolver,
        prepare_inline_payload,
    )

    precise = Decimal("0.12345678901234567890123456789")
    stored = prepare_inline_payload({"precise": precise})
    connection = _database(database_path).connect()
    try:
        _insert_ledger_payload(connection, stored)
        resolved = SQLiteLedgerPayloadResolver(connection).resolve(stored.payload_ref)
        assert resolved["precise"] == precise
        assert isinstance(resolved["precise"], Decimal)
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"private_key_bytes": "secret"},
        {"nested": {"raw_key": "secret"}},
        {"binary": b"secret"},
        {"not_json": {"set-value"}},
        {"not_finite": float("inf")},
    ],
)
def test_inline_payload_rejects_values_outside_closed_json(payload: object) -> None:
    from amadeus_core.storage.payloads import prepare_inline_payload

    with pytest.raises(ValueError):
        prepare_inline_payload(payload)


def test_external_payload_stores_only_reference_and_resolves_verified_content(
    database_path: Path,
) -> None:
    from amadeus_core.storage.payloads import (
        SQLiteLedgerPayloadResolver,
        prepare_external_payload,
    )

    payload = {"large": ["external", "content"]}
    payload_bytes = canonical_json(payload)
    stored = prepare_external_payload(
        "object-store:item-a",
        sha256_hex(payload_bytes),
    )

    class Adapter:
        def fetch(self, external_ref: str) -> bytes:
            assert external_ref == "object-store:item-a"
            return payload_bytes

    connection = _database(database_path).connect()
    try:
        _insert_ledger_payload(connection, stored)
        row = connection.execute(
            """
            SELECT payload_inline_json, payload_external_ref
            FROM ledger_events
            WHERE event_id = 'evt-a'
            """
        ).fetchone()
        resolved = SQLiteLedgerPayloadResolver(connection, Adapter()).resolve(
            stored.payload_ref
        )
        assert row[0] is None
        assert row[1] == "object-store:item-a"
        assert resolved["large"] == ("external", "content")
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "external_ref",
    ["missing-provider-separator", ":opaque", "UPPER:item", "provider:"],
)
def test_external_reference_uses_exact_provider_and_opaque_syntax(
    external_ref: str,
) -> None:
    from amadeus_core.storage.payloads import prepare_external_payload

    with pytest.raises(ValueError):
        prepare_external_payload(external_ref, "0" * 64)


def test_missing_or_unparseable_external_payload_raises_deterministic_missing(
    database_path: Path,
) -> None:
    from amadeus_core.storage.payloads import (
        LedgerPayloadMissing,
        SQLiteLedgerPayloadResolver,
        prepare_external_payload,
    )

    stored = prepare_external_payload("object-store:item-a", "0" * 64)

    class Adapter:
        def fetch(self, external_ref: str) -> bytes:
            del external_ref
            return b"not-json"

    connection = _database(database_path).connect()
    try:
        with pytest.raises(LedgerPayloadMissing):
            SQLiteLedgerPayloadResolver(connection, Adapter()).resolve(stored.payload_ref)
        _insert_ledger_payload(connection, stored)
        with pytest.raises(LedgerPayloadMissing):
            SQLiteLedgerPayloadResolver(connection, Adapter()).resolve(stored.payload_ref)
        connection.rollback()
    finally:
        connection.close()


def test_external_payload_rejects_duplicate_json_object_keys(
    database_path: Path,
) -> None:
    from amadeus_core.storage.payloads import (
        LedgerPayloadMissing,
        SQLiteLedgerPayloadResolver,
        prepare_external_payload,
    )

    raw = b'{"duplicate":1,"duplicate":2}'
    payload_hash = sha256_hex(canonical_json({"duplicate": 2}))
    stored = prepare_external_payload("object-store:item-a", payload_hash)

    class Adapter:
        def fetch(self, external_ref: str) -> bytes:
            del external_ref
            return raw

    connection = _database(database_path).connect()
    try:
        _insert_ledger_payload(connection, stored)
        with pytest.raises(LedgerPayloadMissing):
            SQLiteLedgerPayloadResolver(connection, Adapter()).resolve(
                stored.payload_ref
            )
        connection.rollback()
    finally:
        connection.close()


def test_payload_hash_mismatch_is_deterministic(database_path: Path) -> None:
    from amadeus_core.storage.payloads import (
        LedgerPayloadHashMismatch,
        SQLiteLedgerPayloadResolver,
        prepare_external_payload,
    )

    stored = prepare_external_payload("object-store:item-a", "0" * 64)

    class Adapter:
        def fetch(self, external_ref: str) -> bytes:
            del external_ref
            return canonical_json({"actual": "payload"})

    connection = _database(database_path).connect()
    try:
        _insert_ledger_payload(connection, stored)
        with pytest.raises(LedgerPayloadHashMismatch) as captured:
            SQLiteLedgerPayloadResolver(connection, Adapter()).resolve(stored.payload_ref)
        assert captured.value.expected == "0" * 64
        connection.rollback()
    finally:
        connection.close()


def test_repository_revalidates_directly_constructed_payload_before_any_write(
    database_path: Path,
    ledger_event_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.contracts.commands import CommandExecutionContext
    from amadeus_core.storage.payloads import StoredLedgerPayload
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    standard_seed(database)
    forged = StoredLedgerPayload(
        payload_ref=f"inline:{'0' * 64}",
        mode="inline",
        inline_json='{"private_key_bytes":"secret"}',
        external_ref=None,
        payload_hash="0" * 64,
        media_type="application/json",
    )
    event = ledger_event_factory("evt-b", forged.payload_ref)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("evt-b",),
            execution_context=CommandExecutionContext(
                command_id="cmd-a",
                command_hash="4" * 64,
                audit_context_id="correlation-test",
            ),
        )
        with pytest.raises(ValueError, match="raw key material"):
            repository.append_ledger_event(
                event.model_dump(mode="python"),
                payload=forged,
            )
        assert connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_id = 'evt-b'"
        ).fetchone()[0] == 0
        connection.rollback()
    finally:
        connection.close()


def test_repository_rejects_session_correlation_payload_mismatch_before_any_write(
    database_path: Path,
    ledger_event_factory: Callable[..., object],
    standard_seed: Callable[..., None],
) -> None:
    from amadeus_core.contracts.commands import CommandExecutionContext
    from amadeus_core.storage._records import _seal_record
    from amadeus_core.storage.payloads import prepare_inline_payload
    from amadeus_core.storage.repository import AuthorityRepository

    database = _database(database_path)
    standard_seed(database)
    payload = prepare_inline_payload(
        {
            "session_id": "session-a",
            "identity_id": "idn-a",
            "vault_id": "vlt-a",
        }
    )
    draft = ledger_event_factory(
        "evt-b",
        payload.payload_ref,
        correlation_id="aud-a",
    )
    body = draft.model_dump(mode="python")
    body["record_header"]["content_hash"] = "0" * 64
    body["event_type"] = "session_started"
    body["vault_id"] = "vlt-a"
    body["event_hash"] = "0" * 64
    forged = _seal_record(type(draft), body)
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = AuthorityRepository(
            connection,
            allowed_target_refs=("evt-b",),
            execution_context=CommandExecutionContext(
                command_id="cmd-a",
                command_hash="4" * 64,
                audit_context_id="aud-a",
            ),
        )

        with pytest.raises(ValueError, match="Session Ledger correlation"):
            repository.append_ledger_event(
                forged.model_dump(mode="python"),
                payload=payload,
            )

        assert connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_id = 'evt-b'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM ledger_events WHERE event_id = 'evt-b'"
        ).fetchone()[0] == 0
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("payload_kind", "expected_message"),
    (
        ("reference", "reference payload metadata is not authority-bound"),
        ("custom-media", "payload projection does not match authority"),
    ),
)
def test_repository_rejects_payload_that_would_invalidate_its_ledger_event(
    database_path: Path,
    command_factory: Callable[..., object],
    ledger_event_factory: Callable[..., object],
    standard_seed: Callable[..., None],
    payload_kind: str,
    expected_message: str,
) -> None:
    from amadeus_core.contracts.commands import CommandResult
    from amadeus_core.storage._records import _seal_record
    from amadeus_core.storage.payloads import (
        prepare_external_payload,
        prepare_inline_payload,
    )
    from amadeus_core.storage.unit_of_work import SQLiteUnitOfWork

    database = _database(database_path)
    standard_seed(database)
    genesis_payload = prepare_inline_payload({"genesis": True})
    genesis_command = command_factory(
        ("evt-a1",),
        ("absent",),
        command_id="cmd-a1",
        idempotency_key="genesis",
    )

    def append_genesis(repository, mutation_command, execution_context):
        del mutation_command
        event = ledger_event_factory(
            "evt-a1",
            genesis_payload.payload_ref,
            command_id=execution_context.command_id,
            command_hash=execution_context.command_hash,
            correlation_id=execution_context.audit_context_id,
        )
        repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=genesis_payload,
        )
        return CommandResult[object](
            value=None,
            event_ids=repository.event_ids,
            error=None,
        )

    genesis_result = SQLiteUnitOfWork(database).execute_command(
        genesis_command,
        append_genesis,
    )
    assert genesis_result.error is None
    genesis_connection = database.connect()
    try:
        genesis = genesis_connection.execute(
            "SELECT event_hash FROM ledger_events WHERE event_id = 'evt-a1'"
        ).fetchone()
        assert genesis is not None
        genesis_hash = genesis[0]
        before = tuple(genesis_connection.iterdump())
    finally:
        genesis_connection.close()

    stored_payload = (
        prepare_external_payload("object-store:item-b", "b" * 64)
        if payload_kind == "reference"
        else prepare_inline_payload(
            {"message": "custom media"},
            media_type="application/vnd.test+json",
        )
    )
    command = command_factory(
        ("evt-b",),
        ("absent",),
        command_id=("cmd-b1" if payload_kind == "reference" else "cmd-c1"),
        idempotency_key=f"payload-{payload_kind}",
    )

    def append_invalid(repository, mutation_command, execution_context):
        del mutation_command
        draft = ledger_event_factory(
            "evt-b",
            stored_payload.payload_ref,
            ledger_seq=2,
            command_id=execution_context.command_id,
            command_hash=execution_context.command_hash,
            correlation_id=execution_context.audit_context_id,
        )
        body = draft.model_dump(mode="python")
        body["record_header"]["content_hash"] = "0" * 64
        body["previous_event_hash"] = genesis_hash
        body["event_hash"] = "0" * 64
        event = _seal_record(type(draft), body)
        repository.append_ledger_event(
            event.model_dump(mode="python"),
            payload=stored_payload,
        )
        return CommandResult[object](
            value=None,
            event_ids=repository.event_ids,
            error=None,
        )

    with pytest.raises(ValueError, match=expected_message):
        SQLiteUnitOfWork(database).execute_command(command, append_invalid)

    after_connection = database.connect()
    try:
        assert tuple(after_connection.iterdump()) == before
        assert after_connection.execute(
            "SELECT count(*) FROM authority_records WHERE record_id = 'evt-b'"
        ).fetchone()[0] == 0
        assert after_connection.execute(
            "SELECT count(*) FROM ledger_events WHERE event_id = 'evt-b'"
        ).fetchone()[0] == 0
        assert after_connection.execute(
            "SELECT count(*) FROM command_receipts WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()[0] == 0
    finally:
        after_connection.close()
