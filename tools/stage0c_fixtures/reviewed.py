from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from .constants import INPUT_IDENTITIES, SCHEMA_VERSION
from .dsl import case_id_for_clause_id, resolve_json_pointer, validate_case_body
from .io import canonical_bytes, load_strict_json_bytes
from .types import FixtureInputError, JsonObject, JsonValue, ValidationIssue


__all__ = (
    "REVIEWED_EXACT_FIELDS",
    "load_reviewed_case",
    "validate_batch_review_record",
    "validate_reviewed_batch",
    "validate_reviewed_case",
    "validate_reviewed_closed_set",
)


REVIEWED_EXACT_FIELDS = (
    "schema_version",
    "stage0b_manifest_sha256",
    "clause_id",
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
    "case_body",
    "stimulus_mapping",
    "assertion_or_rubric_mapping",
    "reviewer",
    "rationale",
)

_REVIEWED_FIELDS = frozenset(REVIEWED_EXACT_FIELDS)
_REVIEWED_WITHOUT_REVIEWER = _REVIEWED_FIELDS - {"reviewer"}
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
_STIMULUS_MAPPING_FIELDS = frozenset({"case_json_pointers", "mapping_note"})
_ORACLE_MAPPING_FIELDS = frozenset(
    {"oracle_kind", "case_json_pointers", "mapping_note"}
)
_REVIEWER_FIELDS = frozenset({"role", "reviewer_id", "reviewed_at"})
_ORACLE_KINDS = frozenset({"D", "S", "H", "J"})
_MACHINE_ORACLES = frozenset({"D", "S"})
_HUMAN_ORACLES = frozenset({"H", "J"})

_BATCH_RECORD_FIELDS = frozenset(
    {"schema_version", "batch_id", "reviewed_commit", "test_path", "case_reviews"}
)
_BATCH_CASE_REVIEW_FIELDS = frozenset(
    {
        "ordinal",
        "batch_ordinal",
        "clause_id",
        "case_path",
        "author_id",
        "reviewer_id",
        "reviewed_at",
    }
)

_UPPER_SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
_LOWER_GIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")
_DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_BATCH_ID_RE = re.compile(r"^B(0[1-9]|1[0-3])$")
_ARRAY_INDEX = r"(0|[1-9][0-9]*)"
_STIMULUS_TARGET_RE = re.compile(
    rf"^/stimulus_steps/{_ARRAY_INDEX}(?:/|$)"
)
_STIMULUS_HANDLER_RE = re.compile(
    rf"^/stimulus_steps/{_ARRAY_INDEX}/handler_id$"
)
_STIMULUS_PARAMS_RE = re.compile(
    rf"^/stimulus_steps/{_ARRAY_INDEX}/params(?:/|$)"
)
_MACHINE_TARGET_RE = re.compile(
    rf"^/machine_assertions/{_ARRAY_INDEX}(?:/|$)"
)
_RUBRIC_TARGET_RE = re.compile(
    rf"^/rubric_requirements/{_ARRAY_INDEX}(?:/|$)"
)

_ISSUE_MESSAGES = MappingProxyType(
    {
        "batch_review_case_exact_fields_invalid": (
            "batch case review fields must match the tracked record schema exactly"
        ),
        "batch_review_case_invalid": (
            "batch case review scalar values are invalid"
        ),
        "batch_review_case_order_invalid": (
            "batch case reviews must match checklist order and identity"
        ),
        "batch_review_record_exact_fields_invalid": (
            "batch review record fields must match the tracked schema exactly"
        ),
        "batch_review_record_invalid": (
            "batch review record scalar values are invalid"
        ),
        "batch_review_record_size_invalid": (
            "batch review record must contain the exact checklist window"
        ),
        "batch_review_reviewer_mismatch": (
            "tracked reviewer identity and date must match the reviewed case"
        ),
        "batch_review_role_separation_invalid": (
            "conversion author and reviewer must be nonblank distinct roles"
        ),
        "batch_reviewed_case_missing": (
            "tracked review references a reviewed case that is not available"
        ),
        "machine_oracle_target_invalid": (
            "D and S mappings must resolve inside a concrete machine assertion"
        ),
        "oracle_mapping_exact_fields_invalid": (
            "oracle mapping fields must match the reviewed schema exactly"
        ),
        "oracle_mapping_invalid": "oracle mappings must be an array of objects",
        "oracle_mapping_kind_invalid": (
            "oracle mapping kind must be a required D, S, H, or J oracle"
        ),
        "oracle_mapping_pointer_invalid": (
            "oracle mapping pointers must be nonempty, unique, sorted, and resolvable"
        ),
        "required_oracle_unmapped": (
            "every required oracle kind must have a same-kind reviewed mapping"
        ),
        "review_explanation_empty": (
            "mapping notes, rationale, and reviewer_id must contain non-whitespace text"
        ),
        "reviewed_batch_order_mismatch": (
            "reviewed rows must follow the supplied checklist order"
        ),
        "reviewed_batch_size_mismatch": (
            "reviewed row count must equal the supplied checklist row count"
        ),
        "reviewed_case_identity_mismatch": (
            "case body identity and oracle kinds must match the frozen clause"
        ),
        "reviewed_case_schema_invalid": (
            "case body does not satisfy the supplied fixture case schema"
        ),
        "reviewed_closed_set_invalid": (
            "reviewed rows, checklist rows, and frozen clauses must form one closed set"
        ),
        "reviewed_exact_fields_invalid": (
            "reviewed conversion fields must match the frozen schema exactly"
        ),
        "reviewed_frozen_clause_missing": (
            "the checklist clause is absent from the frozen clause map"
        ),
        "reviewed_frozen_identity_mismatch": (
            "reviewed frozen identity fields must equal their frozen authorities"
        ),
        "reviewed_json_value_invalid": (
            "reviewed conversion must remain in the canonical JSON value domain"
        ),
        "reviewer_invalid": (
            "reviewer must have exact fields, role conversion_reviewer, and a valid date"
        ),
        "reviewer_missing": (
            "reviewer is required before a reviewed conversion can pass"
        ),
        "rubric_oracle_target_invalid": (
            "H and J mappings must resolve inside a same-kind rubric requirement"
        ),
        "stimulus_mapping_exact_fields_invalid": (
            "stimulus mapping fields must match the reviewed schema exactly"
        ),
        "stimulus_mapping_pointer_invalid": (
            "stimulus pointers must resolve inside a concrete stimulus step"
        ),
        "stimulus_mapping_pointer_set_invalid": (
            "stimulus pointers must be a nonempty unique Unicode-sorted string array"
        ),
    }
)


def _add_issue(
    issues: list[ValidationIssue],
    pointer: str,
    code: str,
) -> None:
    issues.append(ValidationIssue(pointer, code, _ISSUE_MESSAGES[code]))


def _finish(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    triples = {
        (issue.json_pointer, issue.code, issue.message) for issue in issues
    }
    return [ValidationIssue(*triple) for triple in sorted(triples)]


def _prefixed(issue: ValidationIssue, prefix: str) -> ValidationIssue:
    return ValidationIssue(
        f"{prefix}{issue.json_pointer}",
        issue.code,
        issue.message,
    )


def _is_nonblank(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _is_date(value: object) -> bool:
    if type(value) is not str:
        return False
    match = _DATE_RE.fullmatch(value)
    if match is None:
        return False
    try:
        date(*(int(part) for part in match.groups()))
    except ValueError:
        return False
    return True


def _pointer_array_is_valid(value: object) -> bool:
    if type(value) is not list or not value:
        return False
    pointers = cast(list[object], value)
    if any(type(pointer) is not str for pointer in pointers):
        return False
    string_pointers = cast(list[str], pointers)
    return (
        len(set(string_pointers)) == len(string_pointers)
        and string_pointers == sorted(string_pointers)
    )


def _resolves(document: object, pointer: str) -> bool:
    try:
        resolve_json_pointer(document, pointer)
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        return False
    return True


def _target_index(pattern: re.Pattern[str], pointer: str) -> int | None:
    match = pattern.match(pointer)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _fallback_frozen_clause(row: object) -> JsonObject:
    if type(row) is not dict:
        return {}
    return {
        field: cast(dict[str, JsonValue], row).get(field)
        for field in _FROZEN_CLAUSE_FIELDS
    }


def _json_equal(left: object, right: object) -> bool:
    try:
        return canonical_bytes(cast(JsonValue, left)) == canonical_bytes(
            cast(JsonValue, right)
        )
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        return False


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _resolve_schema_ref(root: dict[str, Any], reference: object) -> object:
    if type(reference) is not str or not reference.startswith("#/"):
        raise ValueError("only local JSON Schema references are supported")
    current: object = root
    for encoded in reference[2:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if type(current) is not dict or token not in current:
            raise ValueError("unresolvable JSON Schema reference")
        current = current[token]
    return current


def _type_matches(expected: object, value: object) -> bool:
    if type(expected) is list:
        return any(_type_matches(item, value) for item in expected)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return type(value) is bool
    if expected == "integer":
        return type(value) is int
    if expected == "string":
        return type(value) is str
    if expected == "array":
        return type(value) is list
    if expected == "object":
        return type(value) is dict
    return False


def _schema_errors(
    schema: object,
    value: object,
    root: dict[str, Any],
    pointer: str = "",
) -> list[str]:
    if schema is True:
        return []
    if schema is False or type(schema) is not dict:
        return [pointer]
    node = cast(dict[str, Any], schema)
    errors: list[str] = []

    if "$ref" in node:
        referenced = _resolve_schema_ref(root, node["$ref"])
        errors.extend(_schema_errors(referenced, value, root, pointer))

    all_of = node.get("allOf")
    if type(all_of) is list:
        for branch in all_of:
            errors.extend(_schema_errors(branch, value, root, pointer))

    any_of = node.get("anyOf")
    if type(any_of) is list and not any(
        not _schema_errors(branch, value, root, pointer) for branch in any_of
    ):
        errors.append(pointer)

    one_of = node.get("oneOf")
    if type(one_of) is list:
        matches = sum(
            not _schema_errors(branch, value, root, pointer) for branch in one_of
        )
        if matches != 1:
            errors.append(pointer)

    if "not" in node and not _schema_errors(node["not"], value, root, pointer):
        errors.append(pointer)

    if_schema = node.get("if")
    if type(if_schema) is dict:
        branch_name = (
            "then"
            if not _schema_errors(if_schema, value, root, pointer)
            else "else"
        )
        if branch_name in node:
            errors.extend(_schema_errors(node[branch_name], value, root, pointer))

    if "const" in node and not _json_equal(value, node["const"]):
        errors.append(pointer)
    enum = node.get("enum")
    if type(enum) is list and not any(_json_equal(value, item) for item in enum):
        errors.append(pointer)

    expected_type = node.get("type")
    if expected_type is not None and not _type_matches(expected_type, value):
        return sorted(set((*errors, pointer)))

    if type(value) is str:
        minimum_length = node.get("minLength")
        if type(minimum_length) is int and len(value) < minimum_length:
            errors.append(pointer)
        pattern = node.get("pattern")
        if type(pattern) is str and re.search(pattern, value) is None:
            errors.append(pointer)

    if type(value) is int:
        minimum = node.get("minimum")
        if type(minimum) is int and value < minimum:
            errors.append(pointer)

    if type(value) is list:
        minimum_items = node.get("minItems")
        maximum_items = node.get("maxItems")
        if type(minimum_items) is int and len(value) < minimum_items:
            errors.append(pointer)
        if type(maximum_items) is int and len(value) > maximum_items:
            errors.append(pointer)
        if node.get("uniqueItems") is True:
            fingerprints = [canonical_bytes(cast(JsonValue, item)) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                errors.append(pointer)
        if "items" in node:
            for index, item in enumerate(value):
                errors.extend(
                    _schema_errors(
                        node["items"],
                        item,
                        root,
                        f"{pointer}/{index}",
                    )
                )

    if type(value) is dict:
        required = node.get("required")
        if type(required) is list:
            for field in required:
                if type(field) is str and field not in value:
                    errors.append(f"{pointer}/{_escape_pointer_token(field)}")
        properties = node.get("properties")
        property_schemas = properties if type(properties) is dict else {}
        for field, item in value.items():
            child_pointer = f"{pointer}/{_escape_pointer_token(field)}"
            if field in property_schemas:
                errors.extend(
                    _schema_errors(
                        property_schemas[field],
                        item,
                        root,
                        child_pointer,
                    )
                )
                continue
            additional = node.get("additionalProperties", True)
            if additional is False:
                errors.append(child_pointer)
            elif type(additional) is dict:
                errors.extend(
                    _schema_errors(additional, item, root, child_pointer)
                )

    return sorted(set(errors))


def load_reviewed_case(path: Path) -> JsonObject:
    data = Path(path).read_bytes()
    value = load_strict_json_bytes(data, source=Path(path).as_posix())
    if type(value) is not dict:
        raise FixtureInputError(
            "reviewed_json_object_required",
            source=Path(path).as_posix(),
        )
    return cast(JsonObject, value)


def _validate_reviewer(row: JsonObject, issues: list[ValidationIssue]) -> None:
    reviewer = row["reviewer"]
    if type(reviewer) is not dict or set(reviewer) != _REVIEWER_FIELDS:
        _add_issue(issues, "/reviewer", "reviewer_invalid")
        return
    reviewer_row = cast(dict[str, object], reviewer)
    reviewer_id = reviewer_row["reviewer_id"]
    if type(reviewer_id) is str and not reviewer_id.strip():
        _add_issue(
            issues,
            "/reviewer/reviewer_id",
            "review_explanation_empty",
        )
    elif type(reviewer_id) is not str:
        _add_issue(issues, "/reviewer", "reviewer_invalid")
    if (
        reviewer_row["role"] != "conversion_reviewer"
        or not _is_date(reviewer_row["reviewed_at"])
    ):
        _add_issue(issues, "/reviewer", "reviewer_invalid")


def _validate_frozen_identity(
    row: JsonObject,
    frozen_clause: JsonObject,
    issues: list[ValidationIssue],
) -> None:
    expected: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "stage0b_manifest_sha256": INPUT_IDENTITIES["stage0b_manifest"][
            "sha256"
        ],
    }
    expected.update(
        {field: frozen_clause.get(field) for field in _FROZEN_CLAUSE_FIELDS}
    )
    for field, expected_value in expected.items():
        value = row[field]
        if not _json_equal(value, expected_value):
            _add_issue(
                issues,
                f"/{field}",
                "reviewed_frozen_identity_mismatch",
            )

    for field in (
        "stage0b_manifest_sha256",
        "source_binding_sha256",
        "decision_sha256",
        "clause_stimulus_sha256",
        "clause_expected_sha256",
        "clause_content_sha256",
    ):
        value = row[field]
        if type(value) is not str or _UPPER_SHA256_RE.fullmatch(value) is None:
            _add_issue(
                issues,
                f"/{field}",
                "reviewed_frozen_identity_mismatch",
            )


def _validate_case_body_binding(
    row: JsonObject,
    frozen_clause: JsonObject,
    schema: JsonObject,
    issues: list[ValidationIssue],
) -> None:
    body = row["case_body"]
    if type(body) is dict:
        body_row = cast(dict[str, object], body)
        frozen_clause_id = frozen_clause.get("clause_id")
        expected_case_id: object = None
        try:
            expected_case_id = case_id_for_clause_id(frozen_clause_id)
        except FixtureInputError:
            pass
        expected_fields = {
            "source_clause_id": frozen_clause_id,
            "case_id": expected_case_id,
            "source_id": frozen_clause.get("source_id"),
            "oracle_kinds": frozen_clause.get("required_oracle_kinds"),
        }
        for field, expected in expected_fields.items():
            if field not in body_row or not _json_equal(body_row[field], expected):
                _add_issue(
                    issues,
                    f"/case_body/{field}",
                    "reviewed_case_identity_mismatch",
                )

    try:
        schema_root = cast(dict[str, Any], schema)
        schema_errors = _schema_errors(schema_root, body, schema_root)
    except (FixtureInputError, KeyError, RecursionError, TypeError, ValueError):
        schema_errors = [""]
    for pointer in schema_errors:
        _add_issue(
            issues,
            f"/case_body{pointer}",
            "reviewed_case_schema_invalid",
        )

    try:
        body_issues = validate_case_body(body)
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        body_issues = []
        _add_issue(
            issues,
            "/case_body",
            "reviewed_case_schema_invalid",
        )
    issues.extend(
        _prefixed(issue, "/case_body")
        for issue in body_issues
        if issue.code != "case_identity_invalid"
    )


def _validate_stimulus_mapping(
    row: JsonObject,
    issues: list[ValidationIssue],
) -> None:
    mapping = row["stimulus_mapping"]
    if type(mapping) is not dict or set(mapping) != _STIMULUS_MAPPING_FIELDS:
        _add_issue(
            issues,
            "/stimulus_mapping",
            "stimulus_mapping_exact_fields_invalid",
        )
        return
    mapping_row = cast(dict[str, object], mapping)
    if not _is_nonblank(mapping_row["mapping_note"]):
        _add_issue(
            issues,
            "/stimulus_mapping/mapping_note",
            "review_explanation_empty",
        )

    pointers = mapping_row["case_json_pointers"]
    if not _pointer_array_is_valid(pointers):
        _add_issue(
            issues,
            "/stimulus_mapping/case_json_pointers",
            "stimulus_mapping_pointer_set_invalid",
        )
        return
    body = row["case_body"]
    valid_step_indices: set[int] = set()
    for index, pointer in enumerate(cast(list[str], pointers)):
        step_index = _target_index(_STIMULUS_TARGET_RE, pointer)
        if step_index is None or not _resolves(body, pointer):
            _add_issue(
                issues,
                f"/stimulus_mapping/case_json_pointers/{index}",
                "stimulus_mapping_pointer_invalid",
            )
            continue
        valid_step_indices.add(step_index)

    handler_indices = {
        index
        for pointer in cast(list[str], pointers)
        if (index := _target_index(_STIMULUS_HANDLER_RE, pointer)) is not None
    }
    params_indices = {
        index
        for pointer in cast(list[str], pointers)
        if (index := _target_index(_STIMULUS_PARAMS_RE, pointer)) is not None
    }
    if any(
        index not in handler_indices or index not in params_indices
        for index in valid_step_indices
    ):
        _add_issue(
            issues,
            "/stimulus_mapping/case_json_pointers",
            "stimulus_mapping_pointer_invalid",
        )


def _rubric_kind_at(body: object, index: int) -> object:
    if type(body) is not dict:
        return None
    rubrics = body.get("rubric_requirements")
    if type(rubrics) is not list or index >= len(rubrics):
        return None
    rubric = rubrics[index]
    if type(rubric) is not dict:
        return None
    return rubric.get("oracle_kind")


def _validate_oracle_mappings(
    row: JsonObject,
    frozen_clause: JsonObject,
    issues: list[ValidationIssue],
) -> None:
    mappings = row["assertion_or_rubric_mapping"]
    if type(mappings) is not list:
        _add_issue(
            issues,
            "/assertion_or_rubric_mapping",
            "oracle_mapping_invalid",
        )
        return

    required_value = frozen_clause.get("required_oracle_kinds")
    required = (
        set(cast(list[str], required_value))
        if type(required_value) is list
        and all(type(kind) is str for kind in required_value)
        else set()
    )
    declared_mapping_kinds: set[str] = set()
    body = row["case_body"]

    for mapping_index, mapping in enumerate(cast(list[object], mappings)):
        mapping_pointer = f"/assertion_or_rubric_mapping/{mapping_index}"
        if type(mapping) is not dict or set(mapping) != _ORACLE_MAPPING_FIELDS:
            _add_issue(
                issues,
                mapping_pointer,
                "oracle_mapping_exact_fields_invalid",
            )
            continue
        mapping_row = cast(dict[str, object], mapping)
        kind = mapping_row["oracle_kind"]
        kind_valid = type(kind) is str and kind in _ORACLE_KINDS
        if kind_valid:
            declared_mapping_kinds.add(cast(str, kind))
        if not kind_valid or kind not in required:
            _add_issue(
                issues,
                f"{mapping_pointer}/oracle_kind",
                "oracle_mapping_kind_invalid",
            )

        if not _is_nonblank(mapping_row["mapping_note"]):
            _add_issue(
                issues,
                f"{mapping_pointer}/mapping_note",
                "review_explanation_empty",
            )

        pointers = mapping_row["case_json_pointers"]
        if not _pointer_array_is_valid(pointers):
            _add_issue(
                issues,
                f"{mapping_pointer}/case_json_pointers",
                "oracle_mapping_pointer_invalid",
            )
            continue

        for pointer_index, pointer in enumerate(cast(list[str], pointers)):
            target_pointer = (
                f"{mapping_pointer}/case_json_pointers/{pointer_index}"
            )
            if not _resolves(body, pointer):
                _add_issue(
                    issues,
                    target_pointer,
                    "oracle_mapping_pointer_invalid",
                )
                continue
            if kind in _MACHINE_ORACLES:
                if _target_index(_MACHINE_TARGET_RE, pointer) is None:
                    _add_issue(
                        issues,
                        target_pointer,
                        "machine_oracle_target_invalid",
                    )
            elif kind in _HUMAN_ORACLES:
                rubric_index = _target_index(_RUBRIC_TARGET_RE, pointer)
                if (
                    rubric_index is None
                    or _rubric_kind_at(body, rubric_index) != kind
                ):
                    _add_issue(
                        issues,
                        target_pointer,
                        "rubric_oracle_target_invalid",
                    )

    for kind in sorted(required - declared_mapping_kinds):
        _add_issue(
            issues,
            "/assertion_or_rubric_mapping",
            "required_oracle_unmapped",
        )


def validate_reviewed_case(
    row: JsonObject,
    frozen_clause: JsonObject,
    schema: JsonObject,
) -> list[ValidationIssue]:
    if type(row) is not dict:
        issues: list[ValidationIssue] = []
        _add_issue(issues, "", "reviewed_exact_fields_invalid")
        return _finish(issues)

    actual_fields = set(row)
    if actual_fields == _REVIEWED_WITHOUT_REVIEWER:
        issues = []
        _add_issue(issues, "/reviewer", "reviewer_missing")
        return _finish(issues)
    if actual_fields != _REVIEWED_FIELDS:
        issues = []
        _add_issue(issues, "", "reviewed_exact_fields_invalid")
        return _finish(issues)

    try:
        canonical_bytes(row)
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        issues = []
        _add_issue(issues, "", "reviewed_json_value_invalid")
        return _finish(issues)

    issues = []
    _validate_reviewer(row, issues)
    _validate_frozen_identity(row, frozen_clause, issues)
    _validate_case_body_binding(row, frozen_clause, schema, issues)
    _validate_stimulus_mapping(row, issues)
    _validate_oracle_mappings(row, frozen_clause, issues)
    if not _is_nonblank(row["rationale"]):
        _add_issue(issues, "/rationale", "review_explanation_empty")
    return _finish(issues)


def validate_reviewed_batch(
    rows: list[JsonObject],
    checklist_rows: list[JsonObject],
    frozen_clauses_by_id: dict[str, JsonObject],
    schema: JsonObject,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if type(rows) is not list or type(checklist_rows) is not list:
        _add_issue(issues, "", "reviewed_batch_size_mismatch")
        return _finish(issues)
    if len(rows) != len(checklist_rows):
        _add_issue(issues, "", "reviewed_batch_size_mismatch")

    for index, row in enumerate(rows):
        prefix = f"/rows/{index}"
        if index >= len(checklist_rows):
            actual_clause_id = (
                row.get("clause_id") if type(row) is dict else None
            )
            if (
                type(actual_clause_id) is not str
                or actual_clause_id not in frozen_clauses_by_id
            ):
                _add_issue(
                    issues,
                    prefix,
                    "reviewed_frozen_clause_missing",
                )
                frozen_clause = _fallback_frozen_clause(row)
            else:
                frozen_clause = frozen_clauses_by_id[actual_clause_id]
            case_issues = validate_reviewed_case(row, frozen_clause, schema)
            issues.extend(_prefixed(issue, prefix) for issue in case_issues)
            continue

        checklist_row = checklist_rows[index]
        expected_clause_id = (
            checklist_row.get("clause_id")
            if type(checklist_row) is dict
            else None
        )
        actual_clause_id = row.get("clause_id") if type(row) is dict else None
        if not _json_equal(actual_clause_id, expected_clause_id):
            _add_issue(
                issues,
                f"{prefix}/clause_id",
                "reviewed_batch_order_mismatch",
            )
        if type(expected_clause_id) is not str or expected_clause_id not in frozen_clauses_by_id:
            _add_issue(
                issues,
                prefix,
                "reviewed_frozen_clause_missing",
            )
            frozen_clause = _fallback_frozen_clause(row)
        else:
            frozen_clause = frozen_clauses_by_id[expected_clause_id]
        case_issues = validate_reviewed_case(row, frozen_clause, schema)
        issues.extend(_prefixed(issue, prefix) for issue in case_issues)
    return _finish(issues)


def validate_reviewed_closed_set(
    rows: list[JsonObject],
    checklist: JsonObject,
    frozen_clauses_by_id: dict[str, JsonObject],
    schema: JsonObject,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    checklist_rows_value = checklist.get("cases") if type(checklist) is dict else None
    if type(checklist_rows_value) is not list:
        _add_issue(issues, "", "reviewed_closed_set_invalid")
        return _finish(issues)
    checklist_rows = cast(list[JsonObject], checklist_rows_value)

    checklist_ids = [
        row.get("clause_id") if type(row) is dict else None
        for row in checklist_rows
    ]
    valid_ids = [value for value in checklist_ids if type(value) is str]
    row_ids = [
        row.get("clause_id") if type(row) is dict else None for row in rows
    ]
    declared_count = checklist.get("clause_count")
    if (
        len(valid_ids) != len(checklist_ids)
        or len(valid_ids) != len(set(valid_ids))
        or row_ids != checklist_ids
        or set(valid_ids) != set(frozen_clauses_by_id)
        or (
            type(declared_count) is int
            and declared_count != len(checklist_rows)
        )
    ):
        _add_issue(issues, "", "reviewed_closed_set_invalid")

    issues.extend(
        validate_reviewed_batch(
            rows,
            checklist_rows,
            frozen_clauses_by_id,
            schema,
        )
    )
    return _finish(issues)


def validate_batch_review_record(
    record: JsonObject,
    checklist_rows: list[JsonObject],
    reviewed_by_clause_id: dict[str, JsonObject],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if type(record) is not dict or set(record) != _BATCH_RECORD_FIELDS:
        _add_issue(issues, "", "batch_review_record_exact_fields_invalid")
        return _finish(issues)
    try:
        canonical_bytes(record)
    except (FixtureInputError, RecursionError, TypeError, ValueError):
        _add_issue(issues, "", "batch_review_record_invalid")
        return _finish(issues)

    batch_id = record["batch_id"]
    batch_id_valid = (
        type(batch_id) is str and _BATCH_ID_RE.fullmatch(batch_id) is not None
    )
    if record["schema_version"] != SCHEMA_VERSION:
        _add_issue(
            issues,
            "/schema_version",
            "batch_review_record_invalid",
        )
    if not batch_id_valid:
        _add_issue(issues, "/batch_id", "batch_review_record_invalid")
    commit = record["reviewed_commit"]
    if type(commit) is not str or _LOWER_GIT_OID_RE.fullmatch(commit) is None:
        _add_issue(
            issues,
            "/reviewed_commit",
            "batch_review_record_invalid",
        )
    expected_test_path = (
        f"tests/stage0c/reviewed_batches/test_batch_{batch_id}.py"
        if type(batch_id) is str
        else None
    )
    if record["test_path"] != expected_test_path:
        _add_issue(issues, "/test_path", "batch_review_record_invalid")

    case_reviews = record["case_reviews"]
    if type(case_reviews) is not list:
        _add_issue(
            issues,
            "/case_reviews",
            "batch_review_record_size_invalid",
        )
        return _finish(issues)
    expected_size = 19 if batch_id == "B13" else 20
    if (
        len(case_reviews) != len(checklist_rows)
        or len(case_reviews) != expected_size
    ):
        _add_issue(
            issues,
            "/case_reviews",
            "batch_review_record_size_invalid",
        )

    for index, (case_review, checklist_row) in enumerate(
        zip(cast(list[object], case_reviews), checklist_rows, strict=False)
    ):
        pointer = f"/case_reviews/{index}"
        if (
            type(case_review) is not dict
            or set(case_review) != _BATCH_CASE_REVIEW_FIELDS
        ):
            _add_issue(
                issues,
                pointer,
                "batch_review_case_exact_fields_invalid",
            )
            continue
        review = cast(dict[str, object], case_review)
        if type(checklist_row) is not dict:
            _add_issue(
                issues,
                pointer,
                "batch_review_case_order_invalid",
            )
            continue

        expected_values = {
            "ordinal": checklist_row.get("ordinal"),
            "batch_ordinal": checklist_row.get("batch_ordinal"),
            "clause_id": checklist_row.get("clause_id"),
            "case_path": checklist_row.get("reviewed_path"),
        }
        if (
            checklist_row.get("batch_id") != batch_id
            or any(
                not _json_equal(review[field], expected)
                for field, expected in expected_values.items()
            )
        ):
            _add_issue(
                issues,
                pointer,
                "batch_review_case_order_invalid",
            )

        author_id = review["author_id"]
        reviewer_id = review["reviewer_id"]
        if (
            not _is_nonblank(author_id)
            or not _is_nonblank(reviewer_id)
            or author_id == reviewer_id
        ):
            _add_issue(
                issues,
                pointer,
                "batch_review_role_separation_invalid",
            )
        if not _is_date(review["reviewed_at"]):
            _add_issue(
                issues,
                pointer,
                "batch_review_case_invalid",
            )

        clause_id = review["clause_id"]
        reviewed = (
            reviewed_by_clause_id.get(clause_id)
            if type(clause_id) is str
            else None
        )
        if type(reviewed) is not dict:
            _add_issue(
                issues,
                pointer,
                "batch_reviewed_case_missing",
            )
            continue
        reviewer = reviewed.get("reviewer")
        if (
            type(reviewer) is not dict
            or reviewer.get("reviewer_id") != reviewer_id
            or reviewer.get("reviewed_at") != review["reviewed_at"]
        ):
            _add_issue(
                issues,
                pointer,
                "batch_review_reviewer_mismatch",
            )

    return _finish(issues)
