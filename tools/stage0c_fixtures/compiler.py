from __future__ import annotations

import copy
from types import MappingProxyType
from typing import NoReturn, cast

from .constants import (
    EXPECTED_BATCH_COUNT,
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_GENERATED_CASE_COUNT,
    EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
    EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
    EXPECTED_S_CLAUSE_COUNT,
    EXPECTED_SOURCE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
    SCHEMA_VERSION,
)
from .dsl import case_id_for_clause_id
from .io import canonical_bytes, canonical_id_set_sha256, sha256_upper
from .reviewed import (
    REVIEWED_EXACT_FIELDS,
    validate_reviewed_closed_set,
)
from .schema import build_fixture_case_schema
from .types import FixtureInputError, JsonObject, JsonValue, ValidationIssue


__all__ = (
    "STAGE0C_REPORT_V0_1",
    "build_generated_artifacts",
    "compile_binding_manifest",
    "compile_case_file",
    "compile_stage0c_report",
    "validate_stage0c_report",
)


_STAGE0C_REPORT_ITEMS: tuple[tuple[str, JsonValue], ...] = (
    ("schema_version", "0.1"),
    ("fixture_dsl_contract_ready", True),
    ("clause_to_case_binding_complete", True),
    ("case_definition_coverage_complete", True),
    ("trusted_fixture_harness_contract_ready", True),
    ("trusted_fixture_harness_smoke_verified", False),
    ("source_count", 214),
    ("clause_count", 259),
    ("case_count", 259),
    ("s_clause_count", 98),
    ("pending_h_or_j_clause_count", 51),
    ("pending_h_or_j_oracle_requirement_count", 55),
    ("s_case_execution_complete", False),
    ("case_execution_complete", False),
    ("core_behavior_verified", False),
    ("case_coverage_complete", False),
    ("core_case_execution_coverage_complete", False),
    ("catalog_ready", False),
    ("release_ready", False),
)


def _stage0c_report_literal() -> dict[str, JsonValue]:
    return dict(_STAGE0C_REPORT_ITEMS)


STAGE0C_REPORT_V0_1: dict[str, JsonValue] = _stage0c_report_literal()
_REPORT_LITERAL_BYTES = canonical_bytes(_stage0c_report_literal())
# These bind readiness to the exact pure F04/F06 authority objects derived from
# the frozen Stage 0B input identity, rather than to caller-controlled replicas.
_EXPECTED_CONVERSION_CHECKLIST_SHA256 = (
    "E249D3E74662447AD45CCD7B0C900E2F205F7C596DEB5B76FCDB6AEFCB56A1FA"
)
_EXPECTED_FIXTURE_CASE_SCHEMA_SHA256 = (
    "406E3BB2312607193E5C84F2C9E6B631FBC85309B6DD4982D06230EEA005DACB"
)
_REVIEWED_FIELDS = frozenset(REVIEWED_EXACT_FIELDS)
_FROZEN_FIELDS = (
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
_CHECKLIST_FIELDS = frozenset(
    {
        "schema_version",
        "stage0b_manifest_sha256",
        "source_count",
        "clause_count",
        "batch_count",
        "cases",
    }
)
_CHECKLIST_ROW_FIELDS = frozenset(
    {
        "ordinal",
        "batch_id",
        "batch_ordinal",
        "case_id",
        "reviewed_path",
        "generated_path",
        *_FROZEN_FIELDS,
    }
)
_BINDING_FIELDS = (
    "stage0b_manifest_sha256",
    *_FROZEN_FIELDS,
    "case_sha256",
    "stimulus_mapping",
    "assertion_or_rubric_mapping",
    "reviewer",
    "rationale",
)
_ORACLE_ORDER = MappingProxyType({"D": 0, "S": 1, "H": 2, "J": 3})
_HUMAN_ORACLES = frozenset({"H", "J"})
_REPORT_MISMATCH_MESSAGE = (
    "Stage 0C report must equal the frozen readiness literal byte for byte"
)


def _raise_compiler(code: str, *, detail: str = "") -> NoReturn:
    raise FixtureInputError(code, detail=detail)


def _require(condition: bool, code: str, *, detail: str = "") -> None:
    if not condition:
        _raise_compiler(code, detail=detail)


def _json_equal(left: object, right: object) -> bool:
    try:
        return canonical_bytes(cast(JsonValue, left)) == canonical_bytes(
            cast(JsonValue, right)
        )
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        return False


def _require_canonical_authority(
    value: JsonObject,
    *,
    expected_sha256: str,
    code: str,
) -> None:
    try:
        actual_sha256 = sha256_upper(canonical_bytes(value))
    except (FixtureInputError, RecursionError, TypeError, ValueError) as error:
        _raise_compiler(code, detail=str(error))
    _require(
        actual_sha256 == expected_sha256,
        code,
        detail=f"expected={expected_sha256};actual={actual_sha256}",
    )


def _valid_oracle_kinds(value: object) -> bool:
    if type(value) is not list or not value:
        return False
    if any(type(kind) is not str or kind not in _ORACLE_ORDER for kind in value):
        return False
    kinds = cast(list[str], value)
    return len(kinds) == len(set(kinds)) and kinds == sorted(
        kinds,
        key=_ORACLE_ORDER.__getitem__,
    )


def _reviewed_case_body(row: object) -> JsonObject:
    _require(
        type(row) is dict and set(row) == _REVIEWED_FIELDS,
        "compiler_reviewed_exact_fields_invalid",
    )
    reviewed = cast(JsonObject, row)
    try:
        canonical_bytes(reviewed)
    except (FixtureInputError, RecursionError, TypeError, ValueError) as error:
        _raise_compiler("compiler_reviewed_json_invalid", detail=str(error))
    body = reviewed.get("case_body")
    _require(type(body) is dict, "compiler_case_body_invalid")
    body_row = cast(JsonObject, body)
    clause_id = reviewed.get("clause_id")
    try:
        expected_case_id = case_id_for_clause_id(clause_id)
    except FixtureInputError as error:
        _raise_compiler("compiler_case_identity_invalid", detail=error.code)
    _require(
        body_row.get("case_id") == expected_case_id
        and body_row.get("source_clause_id") == clause_id
        and body_row.get("source_id") == reviewed.get("source_id")
        and _json_equal(
            body_row.get("oracle_kinds"),
            reviewed.get("required_oracle_kinds"),
        ),
        "compiler_case_identity_invalid",
    )
    return body_row


def _mapping_kinds(row: JsonObject) -> set[str] | None:
    mappings = row.get("assertion_or_rubric_mapping")
    if type(mappings) is not list:
        return None
    kinds: set[str] = set()
    for mapping in mappings:
        if type(mapping) is not dict:
            return None
        kind = mapping.get("oracle_kind")
        if type(kind) is not str:
            return None
        kinds.add(kind)
    return kinds


def _validated_pairs(
    reviewed_rows: list[JsonObject],
    checklist: JsonObject,
) -> list[tuple[JsonObject, JsonObject]]:
    _require(
        type(checklist) is dict and set(checklist) == _CHECKLIST_FIELDS,
        "compiler_checklist_exact_fields_invalid",
    )
    _require(
        checklist.get("schema_version") == SCHEMA_VERSION
        and checklist.get("stage0b_manifest_sha256")
        == INPUT_IDENTITIES["stage0b_manifest"]["sha256"],
        "compiler_checklist_identity_invalid",
    )
    checklist_rows_value = checklist.get("cases")
    _require(
        type(reviewed_rows) is list and type(checklist_rows_value) is list,
        "compiler_closed_set_invalid",
    )
    checklist_rows = cast(list[object], checklist_rows_value)
    _require(
        len(reviewed_rows) == len(checklist_rows),
        "compiler_closed_set_invalid",
    )

    reviewed_by_clause: dict[str, JsonObject] = {}
    case_ids: set[str] = set()
    for row in reviewed_rows:
        body = _reviewed_case_body(row)
        clause_id = row.get("clause_id")
        case_id = body.get("case_id")
        _require(
            type(clause_id) is str and clause_id not in reviewed_by_clause,
            "compiler_closed_set_invalid",
        )
        _require(
            type(case_id) is str and case_id not in case_ids,
            "compiler_closed_set_invalid",
        )
        required = row.get("required_oracle_kinds")
        _require(
            _valid_oracle_kinds(required),
            "compiler_reviewed_oracle_invalid",
        )
        mapping_kinds = _mapping_kinds(row)
        _require(
            mapping_kinds is not None
            and mapping_kinds == set(cast(list[str], required)),
            "compiler_reviewed_oracle_invalid",
        )
        _require(
            row.get("schema_version") == SCHEMA_VERSION
            and row.get("stage0b_manifest_sha256")
            == checklist.get("stage0b_manifest_sha256"),
            "compiler_reviewed_identity_invalid",
        )
        reviewed_by_clause[clause_id] = row
        case_ids.add(case_id)

    pairs: list[tuple[JsonObject, JsonObject]] = []
    checklist_clause_ids: set[str] = set()
    checklist_sources: set[str] = set()
    for index, item in enumerate(checklist_rows, start=1):
        _require(
            type(item) is dict and set(item) == _CHECKLIST_ROW_FIELDS,
            "compiler_checklist_row_exact_fields_invalid",
        )
        checklist_row = cast(JsonObject, item)
        clause_id = checklist_row.get("clause_id")
        source_id = checklist_row.get("source_id")
        case_id = checklist_row.get("case_id")
        _require(
            type(clause_id) is str
            and clause_id not in checklist_clause_ids
            and type(source_id) is str
            and type(case_id) is str,
            "compiler_closed_set_invalid",
        )
        _require(
            type(checklist_row.get("ordinal")) is int
            and checklist_row.get("ordinal") == index
            and type(checklist_row.get("batch_ordinal")) is int
            and checklist_row.get("batch_id")
            == f"B{((index - 1) // 20) + 1:02d}"
            and checklist_row.get("batch_ordinal") == ((index - 1) % 20) + 1,
            "compiler_checklist_order_invalid",
        )
        _require(
            checklist_row.get("reviewed_path")
            == f"fixtures/stage0c/reviewed/cases/{case_id}.json"
            and checklist_row.get("generated_path") == f"cases/{case_id}.json",
            "compiler_checklist_path_invalid",
        )
        reviewed = reviewed_by_clause.get(clause_id)
        _require(reviewed is not None, "compiler_closed_set_invalid")
        _require(
            all(
                _json_equal(reviewed.get(field), checklist_row.get(field))
                for field in _FROZEN_FIELDS
            ),
            "compiler_reviewed_identity_invalid",
        )
        body = _reviewed_case_body(reviewed)
        _require(
            body.get("case_id") == case_id,
            "compiler_case_identity_invalid",
        )
        checklist_clause_ids.add(clause_id)
        checklist_sources.add(source_id)
        pairs.append((reviewed, checklist_row))

    _require(
        checklist_clause_ids == set(reviewed_by_clause),
        "compiler_closed_set_invalid",
    )
    _require(
        type(checklist.get("source_count")) is int
        and checklist.get("source_count") == len(checklist_sources)
        and type(checklist.get("clause_count")) is int
        and checklist.get("clause_count") == len(checklist_rows)
        and type(checklist.get("batch_count")) is int
        and checklist.get("batch_count") == (len(checklist_rows) + 19) // 20,
        "compiler_checklist_count_invalid",
    )
    return sorted(pairs, key=lambda pair: cast(str, pair[1]["case_id"]))


def compile_case_file(reviewed_row: JsonObject) -> tuple[str, bytes]:
    body = _reviewed_case_body(reviewed_row)
    case_id = cast(str, body["case_id"])
    return f"cases/{case_id}.json", canonical_bytes(body)


def compile_binding_manifest(
    reviewed_rows: list[JsonObject],
    checklist: JsonObject,
) -> dict[str, JsonValue]:
    pairs = _validated_pairs(reviewed_rows, checklist)
    bindings: list[JsonValue] = []
    for reviewed, _ in pairs:
        _, case_data = compile_case_file(reviewed)
        binding: dict[str, JsonValue] = {
            "stage0b_manifest_sha256": copy.deepcopy(
                reviewed["stage0b_manifest_sha256"]
            ),
            **{
                field: copy.deepcopy(reviewed[field])
                for field in _FROZEN_FIELDS
            },
            "case_sha256": sha256_upper(case_data),
            "stimulus_mapping": copy.deepcopy(reviewed["stimulus_mapping"]),
            "assertion_or_rubric_mapping": copy.deepcopy(
                reviewed["assertion_or_rubric_mapping"]
            ),
            "reviewer": copy.deepcopy(reviewed["reviewer"]),
            "rationale": copy.deepcopy(reviewed["rationale"]),
        }
        _require(
            tuple(binding) == _BINDING_FIELDS,
            "compiler_binding_internal_error",
        )
        bindings.append(binding)
    manifest: dict[str, JsonValue] = {
        "schema_version": SCHEMA_VERSION,
        "bindings": bindings,
    }
    canonical_bytes(manifest)
    return manifest


def _require_production_counts(
    pairs: list[tuple[JsonObject, JsonObject]],
    checklist: JsonObject,
) -> None:
    sources = {cast(str, reviewed["source_id"]) for reviewed, _ in pairs}
    clause_ids = [cast(str, reviewed["clause_id"]) for reviewed, _ in pairs]
    case_ids = {
        cast(str, cast(JsonObject, reviewed["case_body"])["case_id"])
        for reviewed, _ in pairs
    }
    oracle_lists = [
        cast(list[str], reviewed["required_oracle_kinds"])
        for reviewed, _ in pairs
    ]
    s_count = sum("S" in kinds for kinds in oracle_lists)
    pending_rows = sum(bool(_HUMAN_ORACLES.intersection(kinds)) for kinds in oracle_lists)
    pending_requirements = sum(
        sum(kind in _HUMAN_ORACLES for kind in kinds) for kinds in oracle_lists
    )
    checklist_rows = cast(list[JsonObject], checklist["cases"])
    checklist_case_ids = [
        cast(str, checklist_row["case_id"])
        for checklist_row in checklist_rows
    ]
    gates = (
        len(sources) == EXPECTED_SOURCE_COUNT,
        canonical_id_set_sha256(sources) == EXPECTED_SOURCE_ID_SET_SHA256,
        len(pairs) == EXPECTED_CLAUSE_COUNT,
        canonical_id_set_sha256(clause_ids) == EXPECTED_CLAUSE_ID_SET_SHA256,
        len(case_ids) == EXPECTED_GENERATED_CASE_COUNT,
        checklist_case_ids == sorted(checklist_case_ids),
        s_count == EXPECTED_S_CLAUSE_COUNT,
        pending_rows == EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
        pending_requirements == EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
        checklist.get("source_count") == EXPECTED_SOURCE_COUNT,
        checklist.get("clause_count") == EXPECTED_CLAUSE_COUNT,
        checklist.get("batch_count") == EXPECTED_BATCH_COUNT,
    )
    _require(all(gates), "stage0c_report_gate_failed")


def compile_stage0c_report(
    reviewed_rows: list[JsonObject],
    checklist: JsonObject,
) -> dict[str, JsonValue]:
    schema = build_fixture_case_schema()
    return _compile_stage0c_report_with_schema(
        reviewed_rows,
        checklist,
        schema,
    )


def validate_stage0c_report(report: JsonObject) -> list[ValidationIssue]:
    try:
        actual = canonical_bytes(report)
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        actual = None
    if actual == _REPORT_LITERAL_BYTES:
        return []
    return [
        ValidationIssue(
            json_pointer="",
            code="stage0c_report_literal_mismatch",
            message=_REPORT_MISMATCH_MESSAGE,
        )
    ]


def _frozen_clauses_from_checklist(checklist: JsonObject) -> dict[str, JsonObject]:
    rows = cast(list[JsonObject], checklist["cases"])
    return {
        cast(str, row["clause_id"]): {
            field: copy.deepcopy(row[field]) for field in _FROZEN_FIELDS
        }
        for row in rows
    }


def _compile_stage0c_report_with_schema(
    reviewed_rows: list[JsonObject],
    checklist: JsonObject,
    schema: JsonObject,
) -> dict[str, JsonValue]:
    pairs = _validated_pairs(reviewed_rows, checklist)
    _require_production_counts(pairs, checklist)
    _require_canonical_authority(
        checklist,
        expected_sha256=_EXPECTED_CONVERSION_CHECKLIST_SHA256,
        code="compiler_checklist_authority_mismatch",
    )
    _require_canonical_authority(
        schema,
        expected_sha256=_EXPECTED_FIXTURE_CASE_SCHEMA_SHA256,
        code="compiler_schema_authority_mismatch",
    )
    frozen_clauses = _frozen_clauses_from_checklist(checklist)
    issues = validate_reviewed_closed_set(
        reviewed_rows,
        checklist,
        frozen_clauses,
        schema,
    )
    if issues:
        first = issues[0]
        _raise_compiler(
            "reviewed_validation_failed",
            detail=f"{first.json_pointer}:{first.code}",
        )
    return _stage0c_report_literal()


def build_generated_artifacts(
    *,
    checklist: JsonObject,
    schema: JsonObject,
    handler_manifest: JsonObject,
    smoke_matrix: JsonObject,
    reviewed_rows: list[JsonObject],
) -> dict[str, bytes]:
    report = _compile_stage0c_report_with_schema(
        reviewed_rows,
        checklist,
        schema,
    )
    binding_manifest = compile_binding_manifest(reviewed_rows, checklist)
    artifacts: dict[str, bytes] = {
        "conversion_checklist_v0_1.json": canonical_bytes(checklist),
        "fixture_case_schema_v0_1.json": canonical_bytes(schema),
        "sandbox_handler_manifest_v0_1.json": canonical_bytes(
            handler_manifest
        ),
        "harness_smoke_test_matrix_v0_1.json": canonical_bytes(smoke_matrix),
        "case_binding_manifest_v0_1.json": canonical_bytes(binding_manifest),
        "stage0c_report_v0_1.json": canonical_bytes(report),
    }
    for reviewed in sorted(
        reviewed_rows,
        key=lambda row: cast(str, cast(JsonObject, row["case_body"])["case_id"]),
    ):
        path, data = compile_case_file(reviewed)
        _require(path not in artifacts, "compiler_artifact_path_duplicate")
        artifacts[path] = data
    return artifacts
