from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from amadeus_core.contracts.commands import (
    Actor,
    ExpectedVersion,
    MutationCommandEnvelope,
)
from amadeus_core.contracts.hashing import canonical_json, sha256_hex
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)
from amadeus_core.contracts.requests import MemoryRequest
from amadeus_core.contracts.validation import compute_record_content_hash
from amadeus_core.storage.bootstrap import (
    BootstrapCommand,
    BootstrapPreallocated,
    bootstrap_core,
)
from amadeus_core.storage.database import SQLiteDatabase
from amadeus_core.storage.repository import AuthorityRepository


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
IDENTITY_ID = "idn-a1"
LINEAGE_ID = "lin-a1"
BRANCH_ID = "brn-a1"
GENESIS_EVENT_ID = "evt-a1"
INSTANCE_ID = "ins-a1"
VAULT_ID = "vlt-a1"
REQUESTER_ID = "usr-a1"
DEPLOYMENT_POLICY_REF = "deployment:test"


def _record_header(
    record_type: str,
    record_id: str,
    *,
    created_by_event_id: str,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": record_type,
        "record_id": record_id,
        "identity_id": IDENTITY_ID,
        "lineage_id": LINEAGE_ID,
        "branch_id": BRANCH_ID,
        "created_at": NOW,
        "created_by_event_id": created_by_event_id,
        "deployment_policy_ref": DEPLOYMENT_POLICY_REF,
        "canonicalization": "core-canonical-json-v1",
        "hash_algorithm": "sha256",
        "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
        "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
        "hash_scope": HASH_SCOPE_REGISTRY[(record_type, "0.1")],
        "content_hash": "0" * 64,
    }


def _seal(model_type: type[Any], body: dict[str, object]):
    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": digest}
            )
        }
    )


def _bootstrap(database: SQLiteDatabase) -> None:
    preallocated = BootstrapPreallocated(
        identity_id=IDENTITY_ID,
        lineage_id=LINEAGE_ID,
        branch_id=BRANCH_ID,
        genesis_event_id=GENESIS_EVENT_ID,
    )
    bootstrap = BootstrapCommand(
        preallocated=preallocated,
        deployment_policy_ref=DEPLOYMENT_POLICY_REF,
    )
    targets = (
        IDENTITY_ID,
        LINEAGE_ID,
        BRANCH_ID,
        GENESIS_EVENT_ID,
    )
    command = MutationCommandEnvelope(
        command_id="cmd-a1",
        command_type="core.bootstrap",
        actor=Actor(actor_type="system", actor_id="sys-a1"),
        actor_capability_id="mcp-a1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id="aud-a1",
        idempotency_key="bootstrap-a1",
        issued_at=NOW,
        target_record_refs=targets,
        payload={
            "scope_refs": (),
            "instance_id": INSTANCE_ID,
            "semantic_input_hash": sha256_hex(
                canonical_json(bootstrap.model_dump(mode="python"))
            ),
        },
    )
    connection = database.connect()
    try:
        result = bootstrap_core(connection, command, bootstrap)
        assert result.error is None
        assert result.value is not None
    finally:
        connection.close()


def _seed_vault(database: SQLiteDatabase) -> None:
    from amadeus_core.contracts.vault import RelationshipVault

    vault = _seal(
        RelationshipVault,
        {
            "record_header": _record_header(
                "RelationshipVault",
                VAULT_ID,
                created_by_event_id=GENESIS_EVENT_ID,
            ),
            "vault_id": VAULT_ID,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "relationship_principal_id": REQUESTER_ID,
            "status": "active",
            "visibility_policy_ref": "visibility:test",
            "created_at": NOW,
            "version": 1,
        },
    )
    connection = database.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        AuthorityRepository(
            connection,
            allowed_target_refs=(VAULT_ID,),
        ).save_authoritative(
            "relationship_vault",
            vault.model_dump(mode="python"),
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def _make_request(
    request_type: str,
    *,
    request_id: str,
    event_id: str,
) -> MemoryRequest:
    return _seal(
        MemoryRequest,
        {
            "record_header": _record_header(
                "MemoryRequest",
                request_id,
                created_by_event_id=event_id,
            ),
            "request_id": request_id,
            "request_type": request_type,
            "identity_id": IDENTITY_ID,
            "lineage_id": LINEAGE_ID,
            "branch_id": BRANCH_ID,
            "vault_id": VAULT_ID,
            "requester_id": REQUESTER_ID,
            "submitted_at": NOW,
            "target_refs": (GENESIS_EVENT_ID,),
            "statement": f"{request_type} test statement",
            "requested_scope": "current_vault",
            "status": "submitted",
            "resulting_proposal_ids": (),
            "resulting_decision_ids": (),
            "version": 1,
        },
    )


def _make_request_command(
    request: MemoryRequest,
    *,
    event_id: str,
) -> MutationCommandEnvelope:
    targets = (request.request_id, event_id)
    return MutationCommandEnvelope(
        command_id=f"cmd-{request.request_id.removeprefix('req-')}",
        command_type="memory_request.submit",
        actor=Actor(actor_type="user", actor_id=REQUESTER_ID),
        actor_capability_id="cap-a1",
        expected_versions=tuple(
            ExpectedVersion(target_record_ref=target, expected_version="absent")
            for target in targets
        ),
        audit_context_id=f"aud-{request.request_id.removeprefix('req-')}",
        idempotency_key=f"request-{request.request_id}",
        issued_at=NOW,
        target_record_refs=targets,
        payload={
            "scope_refs": (
                IDENTITY_ID,
                LINEAGE_ID,
                BRANCH_ID,
                VAULT_ID,
                *request.target_refs,
            ),
            "event_id": event_id,
            "instance_id": INSTANCE_ID,
            "semantic_input_hash": sha256_hex(
                canonical_json(request.model_dump(mode="python"))
            ),
        },
    )


class AuthorityProbe:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def count(self, record_type: str) -> int:
        connection = self._database.connect()
        try:
            return int(
                connection.execute(
                    "SELECT count(*) FROM authority_records WHERE record_type = ?",
                    (record_type,),
                ).fetchone()[0]
            )
        finally:
            connection.close()

    def request(self, request_id: str) -> MemoryRequest:
        connection = self._database.connect()
        try:
            record = AuthorityRepository(connection).get_validated(request_id)
            assert isinstance(record, MemoryRequest)
            return record
        finally:
            connection.close()

    def semantic_event(self, event_id: str) -> tuple[str, dict[str, object]]:
        from amadeus_core.storage.ledger import replay_ledger

        connection = self._database.connect()
        try:
            replay = replay_ledger(connection, BRANCH_ID)
            for event, payload in zip(
                replay.events,
                replay.resolved_inline_payloads,
                strict=True,
            ):
                if event.event_id == event_id:
                    assert payload is not None
                    return event.event_type, dict(payload)
        finally:
            connection.close()
        raise AssertionError(f"missing Ledger event: {event_id}")

    def receipt_event_ids(self, command_id: str) -> tuple[str, ...]:
        import json

        connection = self._database.connect()
        try:
            row = connection.execute(
                """
                SELECT semantic_event_ids_json
                FROM command_receipts
                WHERE command_id = ?
                """,
                (command_id,),
            ).fetchone()
            assert row is not None
            return tuple(json.loads(row[0]))
        finally:
            connection.close()


@pytest.fixture
def database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "governance.sqlite3")
    _bootstrap(database)
    _seed_vault(database)
    return database


@pytest.fixture
def request_service(database: SQLiteDatabase):
    from amadeus_core.governance.request_service import RequestService

    return RequestService(database)


@pytest.fixture
def authority_probe(database: SQLiteDatabase) -> AuthorityProbe:
    return AuthorityProbe(database)


@pytest.fixture
def request_factory() -> Callable[..., MemoryRequest]:
    return _make_request


@pytest.fixture
def request_command_factory() -> Callable[..., MutationCommandEnvelope]:
    return _make_request_command

