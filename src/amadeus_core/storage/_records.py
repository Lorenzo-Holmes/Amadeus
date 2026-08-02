"""Private deterministic builders for authoritative storage records."""

from __future__ import annotations

from collections.abc import Mapping

from amadeus_core.contracts.common import FrozenModel
from amadeus_core.contracts.ledger import LedgerEvent
from amadeus_core.contracts.registry import (
    HASH_SCOPE_REGISTRY,
    HASH_SCOPE_REGISTRY_DIGEST,
)
from amadeus_core.contracts.validation import compute_record_content_hash


_ZERO_HASH = "0" * 64
_SESSION_LEDGER_EVENT_TYPES = frozenset(
    {
        "session_started",
        "conversation_message_recorded",
        "session_ended",
    }
)


def _record_header(
    record_type: str,
    record_id: str,
    *,
    identity_id: str,
    lineage_id: str,
    branch_id: str,
    created_at: object,
    created_by_event_id: str,
    deployment_policy_ref: str,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": record_type,
        "record_id": record_id,
        "identity_id": identity_id,
        "lineage_id": lineage_id,
        "branch_id": branch_id,
        "created_at": created_at,
        "created_by_event_id": created_by_event_id,
        "deployment_policy_ref": deployment_policy_ref,
        "canonicalization": "core-canonical-json-v1",
        "hash_algorithm": "sha256",
        "hash_scope_registry_version": "core-hash-scope-registry-v0.1",
        "hash_scope_registry_digest": HASH_SCOPE_REGISTRY_DIGEST,
        "hash_scope": HASH_SCOPE_REGISTRY[(record_type, "0.1")],
        "content_hash": _ZERO_HASH,
    }


def _seal_record(
    model_type: type[FrozenModel],
    body: Mapping[str, object],
) -> FrozenModel:
    draft = model_type.model_validate(body)
    digest = compute_record_content_hash(draft)
    header = draft.record_header.model_copy(update={"content_hash": digest})
    updates: dict[str, object] = {"record_header": header}
    if isinstance(draft, LedgerEvent):
        updates["event_hash"] = digest
    return draft.model_copy(update=updates)


def _reseal_update(
    record: FrozenModel,
    updates: Mapping[str, object],
) -> FrozenModel:
    header = record.record_header.model_copy(update={"content_hash": _ZERO_HASH})
    draft = record.model_copy(update={**updates, "record_header": header})
    digest = compute_record_content_hash(draft)
    return draft.model_copy(
        update={
            "record_header": draft.record_header.model_copy(
                update={"content_hash": digest}
            )
        }
    )
