import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import stat
from typing import Iterable, NoReturn

from .constants import (
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
    EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
    EXPECTED_S_CLAUSE_COUNT,
    EXPECTED_S_SOURCE_COUNT,
    EXPECTED_SOURCE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
    SCHEMA_VERSION,
)
from .types import FixtureInputError, JsonObject, JsonValue


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True)
class FrozenInputs:
    manifest: dict[str, JsonValue]
    report: dict[str, JsonValue]
    clauses_by_id: dict[str, dict[str, JsonValue]]
    sources_by_id: dict[str, dict[str, JsonValue]]
    raw_sha256_by_key: dict[str, str]


def _raise_input(
    code: str,
    *,
    source: str | None = None,
    detail: str = "",
) -> NoReturn:
    raise FixtureInputError(code, source=source, detail=detail)


def _validate_json_value(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return
    if type(value) is int:
        return
    if type(value) is float:
        _raise_input("json_float_forbidden")
    if type(value) is str:
        return
    if type(value) is list:
        for item in value:
            _validate_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _raise_input("json_type_forbidden")
            _validate_json_value(item)
        return
    _raise_input("json_type_forbidden")


def canonical_bytes(value: JsonValue) -> bytes:
    try:
        _validate_json_value(value)
    except FixtureInputError:
        raise
    except RecursionError as error:
        _raise_input("json_type_forbidden", detail=str(error))
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError, TypeError) as error:
        _raise_input("json_type_forbidden", detail=str(error))
    return encoded + b"\n"


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _require_frozen(condition: bool, code: str) -> None:
    if not condition:
        raise FixtureInputError(code)


def canonical_id_set_sha256(values: Iterable[str]) -> str:
    values_list = list(values)
    _require_frozen(
        len(values_list) == len(set(values_list)),
        "frozen_id_duplicate",
    )
    return sha256_upper(canonical_bytes(sorted(values_list)))


def load_strict_json_bytes(data: bytes, *, source: str) -> JsonValue:
    if type(data) is not bytes:
        _raise_input("json_type_forbidden", source=source)
    if data.startswith(b"\xef\xbb\xbf"):
        _raise_input("json_bom_forbidden", source=source)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        _raise_input("json_non_utf8", source=source, detail=str(error))

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _raise_input(
                    "json_duplicate_key",
                    source=source,
                    detail=key,
                )
            result[key] = value
        return result

    def reject_float(_value: str) -> NoReturn:
        _raise_input("json_float_forbidden", source=source)

    def reject_non_finite(_value: str) -> NoReturn:
        _raise_input("json_non_finite_forbidden", source=source)

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_non_finite,
        )
    except FixtureInputError:
        raise
    except (ValueError, RecursionError) as error:
        _raise_input("json_invalid", source=source, detail=str(error))

    try:
        canonical = canonical_bytes(value)
    except FixtureInputError as error:
        if error.code in ("json_float_forbidden", "json_type_forbidden"):
            _raise_input("json_invalid", source=source, detail=error.detail)
        raise
    if data != canonical:
        _raise_input("json_non_canonical", source=source)
    return value


def _is_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _lstat(path: Path, *, source: str) -> os.stat_result:
    try:
        return os.lstat(path)
    except (FileNotFoundError, NotADirectoryError) as error:
        _raise_input("repo_path_missing", source=source, detail=str(error))


def _reject_reparse(metadata: os.stat_result, *, source: str) -> None:
    if _is_reparse(metadata):
        _raise_input("repo_path_reparse", source=source)


def _repo_components(repo_relative_posix: str) -> list[str]:
    if PureWindowsPath(repo_relative_posix).drive or repo_relative_posix.startswith(
        "/"
    ):
        _raise_input("repo_path_absolute", source=repo_relative_posix)
    if "\\" in repo_relative_posix:
        _raise_input("repo_path_backslash", source=repo_relative_posix)
    components = repo_relative_posix.split("/")
    if "." in components:
        _raise_input("repo_path_dot_segment", source=repo_relative_posix)
    if ".." in components:
        _raise_input("repo_path_parent_segment", source=repo_relative_posix)
    return components


def read_repo_regular_file(root: Path, repo_relative_posix: str) -> bytes:
    components = _repo_components(repo_relative_posix)
    root_path = Path(root)
    root_metadata = _lstat(root_path, source=repo_relative_posix)
    _reject_reparse(root_metadata, source=repo_relative_posix)
    if not stat.S_ISDIR(root_metadata.st_mode):
        _raise_input("repo_path_not_regular_file", source=repo_relative_posix)

    current = root_path
    for index, component in enumerate(components):
        current = current / component
        metadata = _lstat(current, source=repo_relative_posix)
        _reject_reparse(metadata, source=repo_relative_posix)
        terminal = index == len(components) - 1
        if terminal:
            if not stat.S_ISREG(metadata.st_mode):
                _raise_input(
                    "repo_path_not_regular_file",
                    source=repo_relative_posix,
                )
        elif not stat.S_ISDIR(metadata.st_mode):
            _raise_input("repo_path_not_regular_file", source=repo_relative_posix)

    try:
        with current.open("rb") as handle:
            return handle.read()
    except (FileNotFoundError, NotADirectoryError) as error:
        _raise_input("repo_path_missing", source=repo_relative_posix, detail=str(error))
    except IsADirectoryError as error:
        _raise_input(
            "repo_path_not_regular_file",
            source=repo_relative_posix,
            detail=str(error),
        )


def tree_entries(root: Path) -> list[dict[str, JsonValue]]:
    root_path = Path(root)
    root_source = root_path.as_posix()
    root_metadata = _lstat(root_path, source=root_source)
    _reject_reparse(root_metadata, source=root_source)
    if not stat.S_ISDIR(root_metadata.st_mode):
        _raise_input("repo_path_not_regular_file", source=root_source)

    entries: list[dict[str, JsonValue]] = []

    def visit(directory: Path, relative_parts: tuple[str, ...]) -> None:
        try:
            names = os.listdir(directory)
        except (FileNotFoundError, NotADirectoryError) as error:
            _raise_input("repo_path_missing", source=root_source, detail=str(error))
        except IsADirectoryError as error:
            _raise_input(
                "repo_path_not_regular_file",
                source=root_source,
                detail=str(error),
            )
        for name in names:
            path = directory / name
            parts = (*relative_parts, name)
            relative = "/".join(parts)
            metadata = _lstat(path, source=relative)
            _reject_reparse(metadata, source=relative)
            if stat.S_ISDIR(metadata.st_mode):
                visit(path, parts)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                _raise_input("repo_path_not_regular_file", source=relative)
            try:
                with path.open("rb") as handle:
                    data = handle.read()
            except (FileNotFoundError, NotADirectoryError) as error:
                _raise_input("repo_path_missing", source=relative, detail=str(error))
            except IsADirectoryError as error:
                _raise_input(
                    "repo_path_not_regular_file",
                    source=relative,
                    detail=str(error),
                )
            entry: JsonObject = {
                "path": relative,
                "size": len(data),
                "sha256": sha256_upper(data),
            }
            entries.append(entry)

    visit(root_path, ())
    entries.sort(key=lambda entry: entry["path"])
    return entries


def tree_sha256(root: Path) -> str:
    return sha256_upper(canonical_bytes(tree_entries(root)))


def validate_frozen_semantics(
    manifest: dict[str, JsonValue],
    report: dict[str, JsonValue],
) -> None:
    _require_frozen(
        manifest.get("schema_version") == SCHEMA_VERSION
        and report.get("schema_version") == SCHEMA_VERSION,
        "frozen_schema_version_mismatch",
    )
    _require_frozen(
        report.get("source_adjudication_ready") is True
        and type(report.get("pending_atomicity_reviews")) is int
        and report.get("pending_atomicity_reviews") == 0
        and type(report.get("pending_oracle_assignments")) is int
        and report.get("pending_oracle_assignments") == 0,
        "stage0b_not_ready",
    )

    sources = manifest.get("sources")
    clauses = manifest.get("clauses")
    _require_frozen(type(sources) is list, "frozen_source_count_mismatch")
    _require_frozen(type(clauses) is list, "frozen_clause_count_mismatch")
    _require_frozen(
        type(manifest.get("source_count")) is int
        and manifest.get("source_count") == EXPECTED_SOURCE_COUNT
        and type(report.get("reviewed_sources")) is int
        and report.get("reviewed_sources") == EXPECTED_SOURCE_COUNT
        and len(sources) == EXPECTED_SOURCE_COUNT,
        "frozen_source_count_mismatch",
    )
    _require_frozen(
        type(manifest.get("clause_count")) is int
        and manifest.get("clause_count") == EXPECTED_CLAUSE_COUNT
        and type(report.get("clause_count")) is int
        and report.get("clause_count") == EXPECTED_CLAUSE_COUNT
        and len(clauses) == EXPECTED_CLAUSE_COUNT,
        "frozen_clause_count_mismatch",
    )

    _require_frozen(
        sum("S" in row["assigned_oracle_kinds"] for row in sources)
        == EXPECTED_S_SOURCE_COUNT,
        "frozen_s_source_count_mismatch",
    )
    _require_frozen(
        sum("S" in row["required_oracle_kinds"] for row in clauses)
        == EXPECTED_S_CLAUSE_COUNT,
        "frozen_s_clause_count_mismatch",
    )
    _require_frozen(
        sum(
            bool({"H", "J"} & set(row["required_oracle_kinds"]))
            for row in clauses
        )
        == EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
        "frozen_h_or_j_clause_count_mismatch",
    )
    _require_frozen(
        sum(
            kind in {"H", "J"}
            for row in clauses
            for kind in row["required_oracle_kinds"]
        )
        == EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
        "frozen_h_or_j_requirement_count_mismatch",
    )

    source_ids = [row["source_id"] for row in sources]
    clause_ids = [row["clause_id"] for row in clauses]
    _require_frozen(
        len(source_ids) == len(set(source_ids))
        and canonical_id_set_sha256(source_ids)
        == EXPECTED_SOURCE_ID_SET_SHA256,
        "frozen_source_set_mismatch",
    )
    _require_frozen(
        len(clause_ids) == len(set(clause_ids))
        and canonical_id_set_sha256(clause_ids)
        == EXPECTED_CLAUSE_ID_SET_SHA256,
        "frozen_clause_set_mismatch",
    )

    sources_by_id = {row["source_id"]: row for row in sources}
    _require_frozen(
        all(
            row["source_id"] in sources_by_id
            and row["source_group"]
            == sources_by_id[row["source_id"]]["source_group"]
            and row["source_binding_sha256"]
            == sources_by_id[row["source_id"]]["source_binding_sha256"]
            and row["decision_sha256"]
            == sources_by_id[row["source_id"]]["decision_sha256"]
            for row in clauses
        ),
        "frozen_clause_source_join_mismatch",
    )
    _require_frozen(
        report.get("source_clause_manifest_sha256")
        == INPUT_IDENTITIES["stage0b_manifest"]["sha256"],
        "frozen_report_manifest_identity_mismatch",
    )


def load_frozen_inputs(root: Path) -> FrozenInputs:
    raw_by_key: dict[str, bytes] = {}
    raw_sha256_by_key: dict[str, str] = {}

    # Complete every path/type gate before considering any byte identity.
    for key, identity in INPUT_IDENTITIES.items():
        relative = identity["path"]
        assert type(relative) is str
        try:
            raw_by_key[key] = read_repo_regular_file(root, relative)
        except FixtureInputError as error:
            if error.code != "repo_path_missing":
                raise
            raise FixtureInputError(
                "frozen_input_missing",
                source=relative,
            ) from error

    # Complete size/hash identity before parsing either JSON document.
    for key, identity in INPUT_IDENTITIES.items():
        raw_value = raw_by_key[key]
        digest = sha256_upper(raw_value)
        if len(raw_value) != identity["size"] or digest != identity["sha256"]:
            relative = identity["path"]
            assert type(relative) is str
            raise FixtureInputError(
                "frozen_input_size_or_hash_mismatch",
                source=relative,
            )
        raw_sha256_by_key[key] = digest

    manifest_path = INPUT_IDENTITIES["stage0b_manifest"]["path"]
    report_path = INPUT_IDENTITIES["stage0b_report"]["path"]
    assert type(manifest_path) is str
    assert type(report_path) is str
    manifest = load_strict_json_bytes(
        raw_by_key["stage0b_manifest"],
        source=manifest_path,
    )
    report = load_strict_json_bytes(
        raw_by_key["stage0b_report"],
        source=report_path,
    )
    _require_frozen(type(manifest) is dict, "frozen_manifest_type_invalid")
    _require_frozen(type(report) is dict, "frozen_report_type_invalid")
    validate_frozen_semantics(manifest, report)

    sources = manifest["sources"]
    clauses = manifest["clauses"]
    assert type(sources) is list
    assert type(clauses) is list
    sources_by_id = {row["source_id"]: row for row in sources}
    clauses_by_id = {row["clause_id"]: row for row in clauses}
    return FrozenInputs(
        manifest=manifest,
        report=report,
        clauses_by_id=clauses_by_id,
        sources_by_id=sources_by_id,
        raw_sha256_by_key=raw_sha256_by_key,
    )
