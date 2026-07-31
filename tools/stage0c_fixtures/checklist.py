from typing import NoReturn

from .constants import (
    BATCH_SIZE,
    EXPECTED_BATCH_COUNT,
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_SOURCE_COUNT,
    REVIEWED_CASES_PATH,
    SCHEMA_VERSION,
)
from .io import FrozenInputs, canonical_bytes
from .types import FixtureInputError, JsonValue


_FROZEN_CLAUSE_FIELDS = (
    "clause_id",
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
)
_SOURCE_AUTHORITY_FIELDS = (
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
)


def _raise_checklist(code: str) -> NoReturn:
    raise FixtureInputError(code)


def _case_id_for_clause_id(clause_id: str) -> str:
    return f"case-{clause_id.lower().replace('#', '-')}"


def _validated_manifest_clauses(
    inputs: FrozenInputs,
) -> list[dict[str, JsonValue]]:
    clauses = inputs.manifest["clauses"]
    assert type(clauses) is list
    clause_ids = [clause["clause_id"] for clause in clauses]
    expected_ids = tuple(inputs.clauses_by_id)

    if len(clause_ids) != len(set(clause_ids)):
        _raise_checklist("checklist_clause_duplicate")

    actual_id_set = set(clause_ids)
    expected_id_set = set(expected_ids)
    if expected_id_set - actual_id_set:
        _raise_checklist("checklist_clause_missing")
    if actual_id_set - expected_id_set:
        _raise_checklist("checklist_clause_unexpected")
    if tuple(clause_ids) != expected_ids:
        _raise_checklist("checklist_manifest_order_mismatch")

    for clause in clauses:
        clause_id = clause["clause_id"]
        indexed_clause = inputs.clauses_by_id[clause_id]
        source_id = clause["source_id"]
        source = inputs.sources_by_id.get(source_id)
        if any(
            clause[field] != indexed_clause[field]
            for field in _FROZEN_CLAUSE_FIELDS
        ):
            _raise_checklist("checklist_clause_binding_mismatch")
        if source is None:
            _raise_checklist("checklist_clause_binding_mismatch")
        if any(
            clause[field] != source[field]
            for field in _SOURCE_AUTHORITY_FIELDS
        ):
            _raise_checklist("checklist_clause_binding_mismatch")

    return clauses


def build_conversion_checklist(
    inputs: FrozenInputs,
) -> dict[str, JsonValue]:
    clauses = _validated_manifest_clauses(inputs)
    cases: list[dict[str, JsonValue]] = []

    for ordinal, clause in enumerate(clauses, start=1):
        clause_id = clause["clause_id"]
        source_id = clause["source_id"]
        assert type(clause_id) is str
        assert type(source_id) is str
        source = inputs.sources_by_id[source_id]
        case_id = _case_id_for_clause_id(clause_id)
        filename = f"{case_id}.json"
        cases.append(
            {
                "ordinal": ordinal,
                "batch_id": f"B{((ordinal - 1) // BATCH_SIZE) + 1:02d}",
                "batch_ordinal": ((ordinal - 1) % BATCH_SIZE) + 1,
                "case_id": case_id,
                "reviewed_path": f"{REVIEWED_CASES_PATH}/{filename}",
                "generated_path": f"cases/{filename}",
                "clause_id": clause_id,
                "source_id": source_id,
                "source_group": source["source_group"],
                "source_binding_sha256": source["source_binding_sha256"],
                "decision_sha256": source["decision_sha256"],
                "clause_stimulus_sha256": clause["clause_stimulus_sha256"],
                "clause_expected_sha256": clause["clause_expected_sha256"],
                "clause_content_sha256": clause["clause_content_sha256"],
                "required_oracle_kinds": list(
                    clause["required_oracle_kinds"]
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "stage0b_manifest_sha256": inputs.raw_sha256_by_key[
            "stage0b_manifest"
        ],
        "source_count": EXPECTED_SOURCE_COUNT,
        "clause_count": EXPECTED_CLAUSE_COUNT,
        "batch_count": EXPECTED_BATCH_COUNT,
        "cases": cases,
    }


def checklist_bytes(inputs: FrozenInputs) -> bytes:
    return canonical_bytes(build_conversion_checklist(inputs))
