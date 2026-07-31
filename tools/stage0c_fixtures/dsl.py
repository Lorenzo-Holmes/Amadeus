from __future__ import annotations

import re as _re
from dataclasses import dataclass as _dataclass
from types import MappingProxyType as _MappingProxyType
from typing import Any as _Any
from typing import Mapping as _Mapping
from typing import NoReturn as _NoReturn
from typing import cast as _cast

from .constants import SCHEMA_VERSION as _SCHEMA_VERSION
from .io import canonical_bytes as _canonical_bytes
from .types import FixtureInputError as _FixtureInputError
from .types import ValidationIssue as _ValidationIssue


__all__ = (
    "case_id_for_clause_id",
    "case_filename_for_clause_id",
    "canonical_oracle_kinds",
    "resolve_json_pointer",
    "validate_case_body",
)


_CLAUSE_ID_RE = _re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*#[1-9][0-9]*$")
_IDENTIFIER_RE = _re.compile(r"^[a-z][a-z0-9-]*$")
_ARRAY_INDEX_RE = _re.compile(r"^(?:0|[1-9][0-9]*)$")
_JSON_POINTER_PATTERN = r"^(?:/(?:[^~/]|~[01])*)*$"
_JSON_POINTER_RE = _re.compile(_JSON_POINTER_PATTERN)
_UTC_RFC3339_RE = _re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]+))?(?:[Zz]|\+00:00)$"
)
_MONTH_LENGTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

_ORACLE_ORDER: _Mapping[str, int] = _MappingProxyType(
    {"D": 0, "S": 1, "H": 2, "J": 3}
)
_CASE_FIELD_ORDER = (
    "schema_version",
    "case_id",
    "source_id",
    "source_clause_id",
    "oracle_kinds",
    "setup_steps",
    "stimulus_steps",
    "machine_assertions",
    "rubric_requirements",
    "sandbox_profile",
)
_CASE_FIELDS = frozenset(_CASE_FIELD_ORDER)
_STEP_FIELD_ORDER = ("sequence", "step_id", "handler_id", "params")
_STEP_FIELDS = frozenset(_STEP_FIELD_ORDER)
_ASSERTION_FIELD_ORDER = (
    "sequence",
    "assertion_id",
    "handler_id",
    "step_id",
    "params",
)
_ASSERTION_FIELDS = frozenset(_ASSERTION_FIELD_ORDER)
_RUBRIC_FIELD_ORDER = (
    "criterion_id",
    "oracle_kind",
    "question",
    "evidence_case_json_pointers",
    "allowed_scores",
    "passing_scores",
)
_RUBRIC_FIELDS = frozenset(_RUBRIC_FIELD_ORDER)
_SANDBOX_FIELD_ORDER = (
    "profile_id",
    "allowed_effects",
    "fixed_clock",
    "id_seed",
    "reset_policy",
    "cleanup_policy",
)
_SANDBOX_FIELDS = frozenset(_SANDBOX_FIELD_ORDER)
_SANDBOX_REQUIRED_FIELDS = _SANDBOX_FIELDS - frozenset({"allowed_effects"})
_EFFECT_FIELD_ORDER = ("adapter_id", "operation", "target")
_EFFECT_FIELDS = frozenset(_EFFECT_FIELD_ORDER)

_SETUP_HANDLER_ORDER = (
    "sandbox.seed_state",
    "sandbox.set_clock",
    "sandbox.configure_core_driver",
    "sandbox.configure_adapter",
    "sandbox.seed_backend_response",
)
_SETUP_HANDLERS = frozenset(_SETUP_HANDLER_ORDER)
_STIMULUS_HANDLER_ORDER = (
    "core.command",
    "core.query",
    "external.action",
    "backend.replay",
)
_STIMULUS_HANDLERS = frozenset(_STIMULUS_HANDLER_ORDER)
_ASSERTION_HANDLER_ORDER = (
    "receipt.status",
    "receipt.error_code",
    "state.path_equals",
    "state.hash_unchanged",
    "effect.includes",
    "effect.excludes",
    "output.contains",
    "output.omits",
    "replay.equals",
)
_ASSERTION_HANDLERS = frozenset(_ASSERTION_HANDLER_ORDER)
_ADAPTER_ID_ORDER = ("file", "message", "payment", "network", "core")
_ADAPTER_IDS = frozenset(_ADAPTER_ID_ORDER)
_HUMAN_ORACLES = frozenset({"H", "J"})
_MACHINE_ORACLES = frozenset({"D", "S"})

_ISSUE_MESSAGES: _Mapping[str, str] = _MappingProxyType(
    {
        "assertion_exact_fields_invalid": (
            "machine assertion fields must match the DSL exactly"
        ),
        "assertion_sequence_invalid": (
            "machine assertion sequence values must be contiguous integers "
            "starting at 1"
        ),
        "assertion_step_reference_invalid": (
            "assertion step_id must target a declared stimulus step"
        ),
        "case_exact_fields_invalid": "case fields must match the DSL exactly",
        "case_handler_invalid": (
            "handler_id must be allowed for its containing collection"
        ),
        "case_identifier_duplicate": (
            "declaration identifiers must be unique across the case"
        ),
        "case_identifier_invalid": (
            "declaration identifiers must match ^[a-z][a-z0-9-]*$"
        ),
        "case_identity_invalid": (
            "case_id, source_id, and source_clause_id are inconsistent"
        ),
        "case_json_value_invalid": (
            "case value is outside the canonical JSON domain"
        ),
        "case_oracle_coverage_invalid": (
            "declared oracle kinds must have matching assertion or rubric coverage"
        ),
        "case_oracle_kinds_invalid": (
            "oracle_kinds must be a non-empty unique list ordered D, S, H, J"
        ),
        "case_schema_version_invalid": (
            f"schema_version must equal {_SCHEMA_VERSION!r}"
        ),
        "case_step_collection_invalid": (
            "setup_steps, stimulus_steps, and machine_assertions must be arrays"
        ),
        "rubric_allowed_scores_invalid": (
            "rubric allowed_scores must be a non-empty unique ascending integer list"
        ),
        "rubric_evidence_pointer_invalid": (
            "rubric evidence pointers must be a non-empty unique ordered list "
            "resolving in the case"
        ),
        "rubric_exact_fields_invalid": (
            "rubric requirement fields must match the DSL exactly"
        ),
        "rubric_oracle_kind_invalid": (
            "rubric oracle_kind must be declared and equal H or J"
        ),
        "rubric_order_invalid": (
            "rubric requirements must be ordered by criterion_id"
        ),
        "rubric_passing_scores_invalid": (
            "rubric passing_scores must be a valid subset of allowed_scores"
        ),
        "rubric_question_invalid": "rubric question must be a string",
        "sandbox_allowed_effects_invalid": (
            "allowed_effects must be an array with unique valid effect rules"
        ),
        "sandbox_cleanup_policy_invalid": (
            "sandbox cleanup_policy must equal 'always'"
        ),
        "sandbox_effect_rule_invalid": (
            "effect rules must exactly contain a supported adapter_id and string "
            "operation and target"
        ),
        "sandbox_profile_exact_fields_invalid": (
            "sandbox profile fields must match the DSL exactly"
        ),
        "sandbox_profile_forbidden": (
            "sandbox_profile must be null when oracle S is absent"
        ),
        "sandbox_profile_invalid": (
            "sandbox profile scalar fields must have valid types and values"
        ),
        "sandbox_profile_required": (
            "sandbox_profile is required when oracle S is declared"
        ),
        "sandbox_reset_policy_invalid": (
            "sandbox reset_policy must equal 'fresh_context'"
        ),
        "setup_sequence_invalid": (
            "setup sequence values must be contiguous integers starting at 1"
        ),
        "step_exact_fields_invalid": (
            "setup and stimulus step fields must match the DSL exactly"
        ),
        "stimulus_sequence_invalid": (
            "stimulus sequence values must be contiguous integers starting at 1"
        ),
    }
)


_Row = dict[str, object]
_IndexedRow = tuple[int, _Row]
_Declaration = tuple[str, object, str]


@_dataclass(frozen=True, slots=True)
class _JsonPathNode:
    parent: _JsonPathNode | None
    token: str


@_dataclass(frozen=True, slots=True)
class _CollectionSpec:
    name: str
    exact_fields: frozenset[str]
    exact_code: str
    handlers: frozenset[str]
    identifier_field: str
    sequence_code: str


_COLLECTION_SPECS = (
    _CollectionSpec(
        "setup_steps",
        _STEP_FIELDS,
        "step_exact_fields_invalid",
        _SETUP_HANDLERS,
        "step_id",
        "setup_sequence_invalid",
    ),
    _CollectionSpec(
        "stimulus_steps",
        _STEP_FIELDS,
        "step_exact_fields_invalid",
        _STIMULUS_HANDLERS,
        "step_id",
        "stimulus_sequence_invalid",
    ),
    _CollectionSpec(
        "machine_assertions",
        _ASSERTION_FIELDS,
        "assertion_exact_fields_invalid",
        _ASSERTION_HANDLERS,
        "assertion_id",
        "assertion_sequence_invalid",
    ),
)


@_dataclass(frozen=True, slots=True)
class _SingleCollectionValidation:
    issues: tuple[_ValidationIssue, ...]
    rows: tuple[_IndexedRow, ...]
    shape_valid: bool
    declarations: tuple[_Declaration, ...]


@_dataclass(frozen=True, slots=True)
class _CollectionValidation:
    issues: tuple[_ValidationIssue, ...]
    setup_rows: tuple[_IndexedRow, ...]
    stimulus_rows: tuple[_IndexedRow, ...]
    assertion_rows: tuple[_IndexedRow, ...]
    setup_shape_valid: bool
    stimulus_shape_valid: bool
    assertion_shape_valid: bool
    declarations: tuple[_Declaration, ...]


@_dataclass(frozen=True, slots=True)
class _OracleValidation:
    issues: tuple[_ValidationIssue, ...]
    valid: bool
    kinds: tuple[str, ...]


@_dataclass(frozen=True, slots=True)
class _RubricValidation:
    issues: tuple[_ValidationIssue, ...]
    rows: tuple[_IndexedRow, ...]
    shape_valid: bool
    oracles_valid: bool
    declarations: tuple[_Declaration, ...]


@_dataclass(frozen=True, slots=True)
class _IdentifierValidation:
    issues: tuple[_ValidationIssue, ...]
    stimulus_clean: bool
    criterion_clean: bool


def _input_error(code: str) -> _NoReturn:
    raise _FixtureInputError(code)


def case_id_for_clause_id(clause_id: object) -> str:
    if type(clause_id) is not str or _CLAUSE_ID_RE.fullmatch(clause_id) is None:
        _input_error("case_identity_invalid")
    return f"case-{clause_id.lower().replace('#', '-')}"


def case_filename_for_clause_id(clause_id: object) -> str:
    return f"{case_id_for_clause_id(clause_id)}.json"


def canonical_oracle_kinds(value: object) -> list[str]:
    if type(value) is not list or not value:
        _input_error("case_oracle_kinds_invalid")
    values = _cast(list[object], value)
    if any(type(kind) is not str or kind not in _ORACLE_ORDER for kind in values):
        _input_error("case_oracle_kinds_invalid")
    kinds = _cast(list[str], values)
    if len(set(kinds)) != len(kinds):
        _input_error("case_oracle_kinds_invalid")
    return sorted(kinds, key=_ORACLE_ORDER.__getitem__)


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _decode_pointer_token(token: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(token):
        character = token[index]
        if 0xD800 <= ord(character) <= 0xDFFF:
            _input_error("json_pointer_invalid")
        if character != "~":
            decoded.append(character)
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in "01":
            _input_error("json_pointer_invalid")
        decoded.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def _pointer_tokens(pointer: object) -> tuple[str, ...]:
    if (
        type(pointer) is not str
        or _has_surrogate(pointer)
        or _JSON_POINTER_RE.fullmatch(pointer) is None
    ):
        _input_error("json_pointer_invalid")
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        _input_error("json_pointer_invalid")
    return tuple(
        _decode_pointer_token(encoded_token)
        for encoded_token in pointer[1:].split("/")
    )


def _json_pointer_syntax_is_valid(pointer: object) -> bool:
    try:
        _pointer_tokens(pointer)
    except _FixtureInputError:
        return False
    return True


def resolve_json_pointer(document: object, pointer: object) -> object:
    tokens = _pointer_tokens(pointer)
    if not tokens:
        return document

    current = document
    for token in tokens:
        if type(current) is dict:
            mapping = _cast(dict[object, object], current)
            if token not in mapping:
                _input_error("json_pointer_invalid")
            current = mapping[token]
            continue
        if type(current) is list:
            sequence = _cast(list[object], current)
            if _ARRAY_INDEX_RE.fullmatch(token) is None or not sequence:
                _input_error("json_pointer_invalid")
            largest_index = str(len(sequence) - 1)
            if len(token) > len(largest_index) or (
                len(token) == len(largest_index) and token > largest_index
            ):
                _input_error("json_pointer_invalid")
            current = sequence[int(token)]
            continue
        _input_error("json_pointer_invalid")
    return current


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _render_pointer(node: _JsonPathNode | None) -> str:
    tokens: list[str] = []
    while node is not None:
        tokens.append(node.token)
        node = node.parent
    return "".join(
        f"/{_escape_pointer_token(token)}" for token in reversed(tokens)
    )


def _first_json_domain_error(value: object) -> str | None:
    # A path node is allocated in O(1) per edge. The RFC 6901 string is rendered
    # only if an error is found, avoiding quadratic work on deep valid inputs.
    stack: list[tuple[bool, object, _JsonPathNode | None]] = [
        (True, value, None)
    ]
    active: set[int] = set()
    while stack:
        entering, current, path = stack.pop()
        if not entering:
            active.remove(id(current))
            continue

        current_type = type(current)
        if current is None or current_type is bool or current_type is int:
            continue
        if current_type is str:
            if _has_surrogate(_cast(str, current)):
                return _render_pointer(path)
            continue
        if current_type not in (list, dict):
            return _render_pointer(path)

        identity = id(current)
        if identity in active:
            return _render_pointer(path)

        if current_type is dict:
            mapping = _cast(dict[object, object], current)
            keys = tuple(mapping)
            if any(
                type(key) is not str or _has_surrogate(_cast(str, key))
                for key in keys
            ):
                return _render_pointer(path)
            ordered_keys = sorted(_cast(tuple[str, ...], keys))
            active.add(identity)
            stack.append((False, current, path))
            for key in reversed(ordered_keys):
                child_path = _JsonPathNode(path, key)
                stack.append((True, mapping[key], child_path))
            continue

        sequence = _cast(list[object], current)
        active.add(identity)
        stack.append((False, current, path))
        for index in range(len(sequence) - 1, -1, -1):
            child_path = _JsonPathNode(path, str(index))
            stack.append((True, sequence[index], child_path))
    return None


def _add_issue(
    issues: list[_ValidationIssue],
    pointer: str,
    code: str,
) -> None:
    issues.append(_ValidationIssue(pointer, code, _ISSUE_MESSAGES[code]))


def _finish(issues: list[_ValidationIssue]) -> list[_ValidationIssue]:
    triples = {
        (issue.json_pointer, issue.code, issue.message) for issue in issues
    }
    return [_ValidationIssue(*triple) for triple in sorted(triples)]


def _identifier_is_valid(value: object) -> bool:
    return type(value) is str and _IDENTIFIER_RE.fullmatch(value) is not None


def _scores_are_structurally_valid(value: object) -> bool:
    if type(value) is not list or not value:
        return False
    scores = _cast(list[object], value)
    if not all(type(score) is int for score in scores):
        return False
    integer_scores = _cast(list[int], scores)
    return (
        len(set(integer_scores)) == len(integer_scores)
        and integer_scores == sorted(integer_scores)
    )


def _evidence_is_valid(value: object, body: _Row) -> bool:
    if type(value) is not list or not value:
        return False
    pointers = _cast(list[object], value)
    if not all(type(pointer) is str for pointer in pointers):
        return False
    string_pointers = _cast(list[str], pointers)
    if (
        len(set(string_pointers)) != len(string_pointers)
        or string_pointers != sorted(string_pointers)
    ):
        return False
    try:
        for pointer in string_pointers:
            resolve_json_pointer(body, pointer)
    except _FixtureInputError:
        return False
    return True


def _gregorian_date_is_valid(year: int, month: int, day: int) -> bool:
    if not 1 <= month <= 12:
        return False
    month_length = _MONTH_LENGTHS[month - 1]
    if month == 2 and year % 4 == 0 and (
        year % 100 != 0 or year % 400 == 0
    ):
        month_length = 29
    return 1 <= day <= month_length


def _fixed_clock_is_valid(value: object) -> bool:
    if type(value) is not str:
        return False
    match = _UTC_RFC3339_RE.fullmatch(value)
    if match is None:
        return False
    year, month, day, hour, minute, second = (
        int(component) for component in match.groups()[:6]
    )
    if (
        not _gregorian_date_is_valid(year, month, day)
        or not 0 <= hour <= 23
        or not 0 <= minute <= 59
    ):
        return False
    if second == 60:
        return (month, day, hour, minute) in {
            (6, 30, 23, 59),
            (12, 31, 23, 59),
        }
    return 0 <= second <= 59


def _validate_identity(body: _Row) -> tuple[_ValidationIssue, ...]:
    issues: list[_ValidationIssue] = []
    if body["schema_version"] != _SCHEMA_VERSION:
        _add_issue(issues, "/schema_version", "case_schema_version_invalid")

    clause_value = body["source_clause_id"]
    if (
        type(clause_value) is not str
        or _CLAUSE_ID_RE.fullmatch(clause_value) is None
    ):
        _add_issue(issues, "/source_clause_id", "case_identity_invalid")
        return tuple(issues)

    clause_id = _cast(str, clause_value)
    expected_source_id = clause_id.split("#", 1)[0]
    if body["source_id"] != expected_source_id:
        _add_issue(issues, "/source_id", "case_identity_invalid")
    if body["case_id"] != case_id_for_clause_id(clause_id):
        _add_issue(issues, "/case_id", "case_identity_invalid")
    return tuple(issues)


def _validate_oracles(body: _Row) -> _OracleValidation:
    try:
        canonical = canonical_oracle_kinds(body["oracle_kinds"])
    except _FixtureInputError:
        issues: list[_ValidationIssue] = []
        _add_issue(issues, "/oracle_kinds", "case_oracle_kinds_invalid")
        return _OracleValidation(tuple(issues), False, ())

    valid = canonical == body["oracle_kinds"]
    issues = []
    if not valid:
        _add_issue(issues, "/oracle_kinds", "case_oracle_kinds_invalid")
    return _OracleValidation(tuple(issues), valid, tuple(canonical))


def _validate_collection(
    body: _Row,
    spec: _CollectionSpec,
) -> _SingleCollectionValidation:
    issues: list[_ValidationIssue] = []
    declarations: list[_Declaration] = []
    rows: list[_IndexedRow] = []
    collection_pointer = f"/{spec.name}"
    collection_value = body[spec.name]
    if type(collection_value) is not list:
        _add_issue(
            issues,
            collection_pointer,
            "case_step_collection_invalid",
        )
        return _SingleCollectionValidation(
            tuple(issues), (), False, ()
        )

    collection = _cast(list[object], collection_value)
    shape_valid = True
    for index, candidate in enumerate(collection):
        row_pointer = f"{collection_pointer}/{index}"
        if type(candidate) is not dict:
            _add_issue(issues, row_pointer, spec.exact_code)
            shape_valid = False
            continue
        row = _cast(_Row, candidate)
        if set(row) != spec.exact_fields or type(row.get("params")) is not dict:
            _add_issue(issues, row_pointer, spec.exact_code)
            shape_valid = False
            continue

        rows.append((index, row))
        handler = row["handler_id"]
        if type(handler) is not str or handler not in spec.handlers:
            _add_issue(
                issues,
                f"{row_pointer}/handler_id",
                "case_handler_invalid",
            )
        declarations.append(
            (
                f"{row_pointer}/{spec.identifier_field}",
                row[spec.identifier_field],
                spec.name,
            )
        )

    if shape_valid and any(
        type(row["sequence"]) is not int
        or row["sequence"] != expected_sequence
        for expected_sequence, (_index, row) in enumerate(rows, start=1)
    ):
        _add_issue(issues, collection_pointer, spec.sequence_code)

    return _SingleCollectionValidation(
        tuple(issues), tuple(rows), shape_valid, tuple(declarations)
    )


def _validate_collections(body: _Row) -> _CollectionValidation:
    setup, stimulus, assertions = (
        _validate_collection(body, spec) for spec in _COLLECTION_SPECS
    )
    return _CollectionValidation(
        issues=setup.issues + stimulus.issues + assertions.issues,
        setup_rows=setup.rows,
        stimulus_rows=stimulus.rows,
        assertion_rows=assertions.rows,
        setup_shape_valid=setup.shape_valid,
        stimulus_shape_valid=stimulus.shape_valid,
        assertion_shape_valid=assertions.shape_valid,
        declarations=(
            setup.declarations + stimulus.declarations + assertions.declarations
        ),
    )


def _passing_scores_are_invalid(
    passing_value: object,
    allowed_value: object,
    *,
    allowed_valid: bool,
) -> bool:
    if not _scores_are_structurally_valid(passing_value):
        return True
    if not allowed_valid:
        return False
    passing_scores = _cast(list[int], passing_value)
    allowed_scores = _cast(list[int], allowed_value)
    return not set(passing_scores).issubset(allowed_scores)


def _validate_rubrics(
    body: _Row,
    oracle: _OracleValidation,
) -> _RubricValidation:
    issues: list[_ValidationIssue] = []
    rows: list[_IndexedRow] = []
    declarations: list[_Declaration] = []
    collection_value = body["rubric_requirements"]
    if type(collection_value) is not list:
        _add_issue(
            issues,
            "/rubric_requirements",
            "rubric_exact_fields_invalid",
        )
        return _RubricValidation(tuple(issues), (), False, True, ())

    collection = _cast(list[object], collection_value)
    shape_valid = True
    oracles_valid = True
    for index, candidate in enumerate(collection):
        row_pointer = f"/rubric_requirements/{index}"
        if type(candidate) is not dict:
            _add_issue(issues, row_pointer, "rubric_exact_fields_invalid")
            shape_valid = False
            continue
        row = _cast(_Row, candidate)
        if set(row) != _RUBRIC_FIELDS:
            _add_issue(issues, row_pointer, "rubric_exact_fields_invalid")
            shape_valid = False
            continue

        rows.append((index, row))
        declarations.append(
            (
                f"{row_pointer}/criterion_id",
                row["criterion_id"],
                "rubric_requirements",
            )
        )

        oracle_kind = row["oracle_kind"]
        oracle_kind_valid = (
            type(oracle_kind) is str
            and oracle_kind in _HUMAN_ORACLES
            and (not oracle.valid or oracle_kind in oracle.kinds)
        )
        if not oracle_kind_valid:
            _add_issue(
                issues,
                f"{row_pointer}/oracle_kind",
                "rubric_oracle_kind_invalid",
            )
            oracles_valid = False

        if type(row["question"]) is not str:
            _add_issue(
                issues,
                f"{row_pointer}/question",
                "rubric_question_invalid",
            )
        if not _evidence_is_valid(row["evidence_case_json_pointers"], body):
            _add_issue(
                issues,
                f"{row_pointer}/evidence_case_json_pointers",
                "rubric_evidence_pointer_invalid",
            )

        allowed_value = row["allowed_scores"]
        passing_value = row["passing_scores"]
        allowed_valid = _scores_are_structurally_valid(allowed_value)
        if not allowed_valid:
            _add_issue(
                issues,
                f"{row_pointer}/allowed_scores",
                "rubric_allowed_scores_invalid",
            )
        if _passing_scores_are_invalid(
            passing_value,
            allowed_value,
            allowed_valid=allowed_valid,
        ):
            _add_issue(
                issues,
                f"{row_pointer}/passing_scores",
                "rubric_passing_scores_invalid",
            )

    return _RubricValidation(
        tuple(issues),
        tuple(rows),
        shape_valid,
        oracles_valid,
        tuple(declarations),
    )


def _validate_identifiers(
    declarations: tuple[_Declaration, ...],
) -> _IdentifierValidation:
    issues: list[_ValidationIssue] = []
    stimulus_clean = True
    criterion_clean = True
    seen: dict[str, str] = {}
    for pointer, value, declaration_kind in declarations:
        if not _identifier_is_valid(value):
            _add_issue(issues, pointer, "case_identifier_invalid")
            if declaration_kind == "stimulus_steps":
                stimulus_clean = False
            elif declaration_kind == "rubric_requirements":
                criterion_clean = False
            continue

        identifier = _cast(str, value)
        if identifier in seen:
            _add_issue(issues, pointer, "case_identifier_duplicate")
            original_kind = seen[identifier]
            if "stimulus_steps" in {original_kind, declaration_kind}:
                stimulus_clean = False
            if "rubric_requirements" in {original_kind, declaration_kind}:
                criterion_clean = False
            continue
        seen[identifier] = declaration_kind

    return _IdentifierValidation(
        tuple(issues), stimulus_clean, criterion_clean
    )


def _validate_references(
    collections: _CollectionValidation,
    rubrics: _RubricValidation,
    identifiers: _IdentifierValidation,
) -> tuple[_ValidationIssue, ...]:
    issues: list[_ValidationIssue] = []
    if identifiers.stimulus_clean and collections.stimulus_shape_valid:
        stimulus_ids = {
            _cast(str, row["step_id"])
            for _index, row in collections.stimulus_rows
        }
        for index, row in collections.assertion_rows:
            step_id = row["step_id"]
            if type(step_id) is not str or step_id not in stimulus_ids:
                _add_issue(
                    issues,
                    f"/machine_assertions/{index}/step_id",
                    "assertion_step_reference_invalid",
                )

    if identifiers.criterion_clean and rubrics.shape_valid:
        criterion_ids = [
            _cast(str, row["criterion_id"]) for _index, row in rubrics.rows
        ]
        if criterion_ids != sorted(criterion_ids):
            _add_issue(
                issues,
                "/rubric_requirements",
                "rubric_order_invalid",
            )
    return tuple(issues)


def _validate_coverage(
    body: _Row,
    oracle: _OracleValidation,
    collections: _CollectionValidation,
    rubrics: _RubricValidation,
) -> tuple[_ValidationIssue, ...]:
    issues: list[_ValidationIssue] = []
    if (
        _MACHINE_ORACLES.intersection(oracle.kinds)
        and collections.assertion_shape_valid
        and len(_cast(list[object], body["machine_assertions"])) == 0
    ):
        _add_issue(
            issues,
            "/machine_assertions",
            "case_oracle_coverage_invalid",
        )

    if rubrics.shape_valid and rubrics.oracles_valid:
        expected = {
            kind for kind in oracle.kinds if kind in _HUMAN_ORACLES
        }
        actual = {
            _cast(str, row["oracle_kind"]) for _index, row in rubrics.rows
        }
        if actual != expected:
            _add_issue(
                issues,
                "/rubric_requirements",
                "case_oracle_coverage_invalid",
            )
    return tuple(issues)


def _effect_rule_is_valid(value: object) -> bool:
    if type(value) is not dict:
        return False
    rule = _cast(_Row, value)
    return (
        set(rule) == _EFFECT_FIELDS
        and type(rule.get("adapter_id")) is str
        and rule.get("adapter_id") in _ADAPTER_IDS
        and type(rule.get("operation")) is str
        and type(rule.get("target")) is str
    )


def _validate_effects(sandbox: _Row) -> tuple[_ValidationIssue, ...]:
    issues: list[_ValidationIssue] = []
    if "allowed_effects" not in sandbox:
        _add_issue(
            issues,
            "/sandbox_profile/allowed_effects",
            "sandbox_allowed_effects_invalid",
        )
        return tuple(issues)

    effects_value = sandbox["allowed_effects"]
    if type(effects_value) is not list:
        _add_issue(
            issues,
            "/sandbox_profile/allowed_effects",
            "sandbox_allowed_effects_invalid",
        )
        return tuple(issues)

    fingerprints: list[bytes] = []
    for index, rule_value in enumerate(_cast(list[object], effects_value)):
        if not _effect_rule_is_valid(rule_value):
            _add_issue(
                issues,
                f"/sandbox_profile/allowed_effects/{index}",
                "sandbox_effect_rule_invalid",
            )
            continue
        fingerprints.append(_canonical_bytes(_cast(_Any, rule_value)))

    if len(set(fingerprints)) != len(fingerprints):
        _add_issue(
            issues,
            "/sandbox_profile/allowed_effects",
            "sandbox_allowed_effects_invalid",
        )
    return tuple(issues)


def _validate_sandbox(
    sandbox_value: object,
    oracle_kinds: tuple[str, ...],
) -> tuple[_ValidationIssue, ...]:
    issues: list[_ValidationIssue] = []
    if "S" not in oracle_kinds:
        if sandbox_value is not None:
            _add_issue(
                issues,
                "/sandbox_profile",
                "sandbox_profile_forbidden",
            )
        return tuple(issues)

    if sandbox_value is None:
        _add_issue(issues, "/sandbox_profile", "sandbox_profile_required")
        return tuple(issues)
    if type(sandbox_value) is not dict:
        _add_issue(
            issues,
            "/sandbox_profile",
            "sandbox_profile_exact_fields_invalid",
        )
        return tuple(issues)

    sandbox = _cast(_Row, sandbox_value)
    keys = set(sandbox)
    if keys - _SANDBOX_FIELDS or _SANDBOX_REQUIRED_FIELDS - keys:
        _add_issue(
            issues,
            "/sandbox_profile",
            "sandbox_profile_exact_fields_invalid",
        )
        return tuple(issues)

    for field in ("profile_id", "id_seed"):
        if type(sandbox[field]) is not str:
            _add_issue(
                issues,
                f"/sandbox_profile/{field}",
                "sandbox_profile_invalid",
            )
    if not _fixed_clock_is_valid(sandbox["fixed_clock"]):
        _add_issue(
            issues,
            "/sandbox_profile/fixed_clock",
            "sandbox_profile_invalid",
        )
    if sandbox["reset_policy"] != "fresh_context":
        _add_issue(
            issues,
            "/sandbox_profile/reset_policy",
            "sandbox_reset_policy_invalid",
        )
    if sandbox["cleanup_policy"] != "always":
        _add_issue(
            issues,
            "/sandbox_profile/cleanup_policy",
            "sandbox_cleanup_policy_invalid",
        )
    issues.extend(_validate_effects(sandbox))
    return tuple(issues)


def validate_case_body(body: object) -> list[_ValidationIssue]:
    issues: list[_ValidationIssue] = []

    # Descendant diagnostics are meaningful only after the exact root-shape gate.
    if type(body) is not dict:
        _add_issue(issues, "", "case_exact_fields_invalid")
        return _finish(issues)
    case = _cast(_Row, body)
    if set(case) != _CASE_FIELDS:
        _add_issue(issues, "", "case_exact_fields_invalid")
        return _finish(issues)

    json_error_pointer = _first_json_domain_error(case)
    if json_error_pointer is not None:
        _add_issue(issues, json_error_pointer, "case_json_value_invalid")
        return _finish(issues)
    try:
        _canonical_bytes(_cast(_Any, case))
    except (_FixtureInputError, RecursionError, TypeError, ValueError):
        _add_issue(issues, "", "case_json_value_invalid")
        return _finish(issues)

    issues.extend(_validate_identity(case))
    oracle = _validate_oracles(case)
    issues.extend(oracle.issues)

    collections = _validate_collections(case)
    issues.extend(collections.issues)

    rubrics = _validate_rubrics(case, oracle)
    issues.extend(rubrics.issues)

    identifiers = _validate_identifiers(
        collections.declarations + rubrics.declarations
    )
    issues.extend(identifiers.issues)
    issues.extend(_validate_references(collections, rubrics, identifiers))

    if oracle.valid:
        issues.extend(_validate_coverage(case, oracle, collections, rubrics))
        issues.extend(_validate_sandbox(case["sandbox_profile"], oracle.kinds))

    return _finish(issues)
