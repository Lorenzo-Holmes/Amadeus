from __future__ import annotations

import json

import pytest

from amadeus_core.contracts.commands import Actor
from amadeus_core.contracts.errors import CoreErrorCode
from amadeus_core.contracts.hashing import sha256_hex
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.payloads import canonical_receipt_result
from amadeus_core.storage.unit_of_work import ReceiptIntegrityError


def _database_dump(database) -> tuple[str, ...]:
    connection = database.connect()
    try:
        return tuple(connection.iterdump())
    finally:
        connection.close()


def _rebind_statement(request: MemoryRequest) -> MemoryRequest:
    draft = request.model_copy(
        update={
            "statement": f"{request.statement} rebound",
            "record_header": request.record_header.model_copy(
                update={"content_hash": "0" * 64}
            ),
        }
    )
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": compute_record_content_hash(draft)}
            )
        }
    )


def _assert_error_code(result, code: CoreErrorCode) -> None:
    assert result.value is None
    assert result.event_ids == ()
    assert result.error is not None
    assert result.error.code == code


def test_request_submit_rejects_rebound_external_request(
    database,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    request = request_factory(
        "correction_request",
        request_id="req-b1",
        event_id="evt-b1",
    )
    command = request_command_factory(request, event_id="evt-b1")
    rebound_request = _rebind_statement(request)
    before = _database_dump(database)

    result = request_service.submit(command, rebound_request)

    _assert_error_code(result, CoreErrorCode.HASH_SCOPE_MISMATCH)
    assert _database_dump(database) == before


def test_request_submit_rejects_llm_actor_without_writes(
    database,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    request = request_factory(
        "non_mention_request",
        request_id="req-b2",
        event_id="evt-b2",
    )
    command = request_command_factory(request, event_id="evt-b2").model_copy(
        update={"actor": Actor(actor_type="llm", actor_id="llm-b2")}
    )
    before = _database_dump(database)

    result = request_service.submit(command, request)

    _assert_error_code(result, CoreErrorCode.LLM_COMMIT_FORBIDDEN)
    assert _database_dump(database) == before


@pytest.mark.parametrize(
    "scope_refs",
    (
        ("idn-a1", "lin-a1", "brn-a1", "evt-a1"),
        ("idn-a1", "lin-a1", "brn-a1", "vlt-bad", "evt-a1"),
    ),
    ids=("missing-vault", "cross-vault"),
)
def test_request_submit_rejects_invalid_vault_scope_without_writes(
    database,
    request_service,
    request_factory,
    request_command_factory,
    scope_refs: tuple[str, ...],
) -> None:
    request = request_factory(
        "confidentiality_request",
        request_id="req-b3",
        event_id="evt-b3",
    )
    original = request_command_factory(request, event_id="evt-b3")
    command = original.model_copy(
        update={"payload": {**dict(original.payload), "scope_refs": scope_refs}}
    )
    before = _database_dump(database)

    result = request_service.submit(command, request)

    _assert_error_code(result, CoreErrorCode.VAULT_SCOPE_MISMATCH)
    assert _database_dump(database) == before


def test_request_replay_rejects_rehashed_wrong_typed_receipt_value(
    database,
    request_service,
    request_factory,
    request_command_factory,
) -> None:
    request = request_factory(
        "correction_request",
        request_id="req-b4",
        event_id="evt-b4",
    )
    command = request_command_factory(request, event_id="evt-b4")
    first = request_service.submit(command, request)
    assert first.error is None

    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT result_json FROM command_receipts WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()
        assert row is not None
        result_payload = json.loads(row[0])
        result_payload["value"] = {"wrong": "authoritative shape"}
        tampered_json = canonical_receipt_result(result_payload).decode("utf-8")
        connection.execute("DROP TRIGGER command_receipts_reject_update")
        try:
            connection.execute(
                """
                UPDATE command_receipts
                SET result_json = ?, result_hash = ?
                WHERE command_id = ?
                """,
                (
                    tampered_json,
                    sha256_hex(tampered_json.encode("utf-8")),
                    command.command_id,
                ),
            )
            connection.commit()
        finally:
            connection.execute(
                "CREATE TRIGGER IF NOT EXISTS command_receipts_reject_update\n"
                "BEFORE UPDATE ON command_receipts\n"
                "BEGIN\n"
                "    SELECT RAISE(ABORT, 'command receipt is immutable');\n"
                "END;"
            )
    finally:
        connection.close()

    with pytest.raises(
        ReceiptIntegrityError,
        match="MemoryRequest receipt value has the wrong authoritative shape",
    ):
        request_service.submit(command, request)
