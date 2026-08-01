"""Typed identifiers for authoritative Core records."""

from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID, uuid4


AUTHORITATIVE_PREFIXES: Mapping[str, str] = MappingProxyType({
    "source_snapshot": "snp-",
    "event": "evt-",
    "autobiographical_memory": "mem-",
    "identity": "idn-",
    "lineage": "lin-",
    "branch": "brn-",
    "relationship_vault": "vlt-",
    "memory_request": "req-",
    "proposal": "prp-",
    "governor_decision": "gvd-",
    "vault_read_capability": "vrc-",
    "amadeus_termination_confirmation": "tmc-",
    "termination_execution_grant": "teg-",
    "maintenance_capability": "mcp-",
    "emergency_unresponsive_case": "emg-",
    "break_glass_grant": "bgg-",
    "migration_plan": "mig-",
})

PREFIXES: Mapping[str, str] = MappingProxyType({
    **AUTHORITATIVE_PREFIXES,
    "error": "err-",
    "command": "cmd-",
    "audit_context": "aud-",
    "instance": "ins-",
    "retrieval": "ret-",
    "expression": "exp-",
})


def new_id(kind: str) -> str:
    try:
        prefix = PREFIXES[kind]
    except KeyError as error:
        raise ValueError(f"unknown id kind: {kind}") from error
    return f"{prefix}{uuid4()}"


def validate_id(value: str, expected_prefix: str) -> str:
    if not expected_prefix.endswith("-") or not value.startswith(expected_prefix):
        raise ValueError(f"expected id prefix: {expected_prefix}")
    raw_uuid = value[len(expected_prefix) :]
    UUID(raw_uuid)
    return value
