import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat
from typing import NoReturn

from .types import FixtureInputError, JsonObject, JsonValue


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


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
