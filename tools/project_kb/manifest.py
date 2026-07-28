import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "0.1"

_MANIFEST_PATH = "knowledge/manifest.json"
_POLICY_PATH = "knowledge/index-policy.json"
_REQUIRED_INCLUDES = {
    "README.md",
    "knowledge/data_structure.md",
    "outputs/**/*.md",
    "knowledge/30_research/legacy/*.md",
    "knowledge/40_history/legacy/*.md",
}
_REQUIRED_EXCLUDES = {
    "knowledge/90_raw/**",
    ".git/**",
    ".local/**",
    ".worktrees/**",
}
_RAW_OR_LOCAL_COMPONENTS = {
    ".git",
    ".local",
    ".worktrees",
}
_DOCUMENT_FIELDS = {
    "doc_id",
    "title",
    "path",
    "kind",
    "authority",
    "status",
    "stage",
    "index",
    "sensitivity",
    "sha256",
}
_POLICY_FIELDS = {
    "version",
    "path_style",
    "glob_syntax",
    "exclude_precedence",
    "default_index",
    "follow_gitignore",
    "include",
    "exclude",
}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_DRIVE_PATH_PATTERN = re.compile(r"[A-Za-z]:")
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "conin$",
    "conout$",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
    "com¹",
    "com²",
    "com³",
    "lpt¹",
    "lpt²",
    "lpt³",
}
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class _DuplicateJSONKey(ValueError):
    pass


class ProjectKBError(Exception):
    """A user-facing validation failure with a stable category."""

    def __init__(self, category: str, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail


@dataclass(frozen=True)
class IndexedDocument:
    doc_id: str
    title: str
    path: str
    kind: str
    authority: str
    status: str
    stage: str
    sensitivity: str
    sha256: str
    text: str


@dataclass(frozen=True)
class ProjectIndex:
    root: Path
    documents: tuple[IndexedDocument, ...]


def _fail(category: str, detail: str) -> None:
    raise ProjectKBError(category, detail)


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    status = path.lstat()
    is_reparse = bool(
        getattr(status, "st_file_attributes", 0) & _REPARSE_POINT
    )
    return stat.S_ISLNK(status.st_mode) or is_reparse or (
        is_junction is not None and is_junction()
    )


def _path_present(path: Path) -> bool:
    try:
        path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def _real_root(root: Path | str) -> Path:
    candidate = Path(root).absolute()
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if _path_present(current) and _is_link_or_junction(current):
            _fail("path_error", "root lineage must contain real directories")
    if (
        not _path_present(candidate)
        or _is_link_or_junction(candidate)
        or not candidate.is_dir()
    ):
        _fail("path_error", "root must be a real directory")
    try:
        return candidate.resolve(strict=True)
    except OSError as error:
        _fail("path_error", f"root resolution failed: {error}")


def _lexical_path(path: Any, *, markdown: bool) -> tuple[str, ...]:
    if not isinstance(path, str) or not path:
        _fail("path_error", "path must be a non-empty string")
    if path.startswith("/") or _DRIVE_PATH_PATTERN.match(path):
        _fail("path_error", f"absolute path: {path}")
    if "\\" in path:
        _fail("path_error", f"path is not POSIX: {path}")
    parts = tuple(path.split("/"))
    if ".." in parts:
        _fail("path_error", f"parent traversal: {path}")
    if any(part in {"", "."} for part in parts):
        _fail("path_error", f"path is not canonical: {path}")
    folded_parts = tuple(part.casefold() for part in parts)
    if any(
        part in _RAW_OR_LOCAL_COMPONENTS
        for part in folded_parts
    ) or (
        len(parts) >= 2
        and folded_parts[0] == "knowledge"
        and folded_parts[1] == "90_raw"
    ):
        _fail("path_error", f"raw or hidden-local path: {path}")
    if any(part.startswith(".") for part in parts):
        _fail("path_error", f"raw or hidden-local path: {path}")
    for part in parts:
        if (
            ":" in part
            or part.endswith((".", " "))
            or any(
                ord(character) < 32 or character in '<>"|?*'
                for character in part
            )
        ):
            _fail("path_error", f"Windows alias syntax: {path}")
        device_name = part.split(".", 1)[0].casefold()
        if device_name in _WINDOWS_RESERVED_NAMES:
            _fail(
                "path_error",
                f"reserved Windows path component: {part}",
            )
    if markdown and PurePosixPath(path).suffix != ".md":
        _fail("path_error", f"document must use .md: {path}")
    return parts


def _secure_file(root: Path, relative_path: str, *, markdown: bool) -> Path:
    parts = _lexical_path(relative_path, markdown=markdown)
    current = root
    for index, part in enumerate(parts):
        current = current / part
        displayed = "/".join(parts[: index + 1])
        if not _path_present(current):
            _fail("path_error", f"missing path: {displayed}")
        status = current.lstat()
        if _is_link_or_junction(current):
            _fail("path_error", f"link or junction: {displayed}")
        if (
            index < len(parts) - 1
            and not stat.S_ISDIR(status.st_mode)
        ):
            _fail("path_error", f"non-directory path component: {displayed}")
    if not stat.S_ISREG(status.st_mode):
        _fail("path_error", f"document is not a regular file: {relative_path}")
    if status.st_nlink != 1:
        _fail("path_error", f"hard link: {relative_path}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        _fail("path_error", f"path escapes project root: {relative_path}")
    return current


def _read_file(root: Path, relative_path: str, *, markdown: bool) -> bytes:
    path = _secure_file(root, relative_path, markdown=markdown)
    before = path.lstat()
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        before_identity = (before.st_dev, before.st_ino, before.st_mode)
        opened_identity = (opened.st_dev, opened.st_ino, opened.st_mode)
        if opened_identity != before_identity:
            _fail("path_error", f"path changed before read: {relative_path}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            data = handle.read()
    except OSError as error:
        _fail("io_error", f"read failed: {relative_path}: {error}")
    finally:
        if descriptor is not None:
            os.close(descriptor)
    verified = _secure_file(root, relative_path, markdown=markdown)
    after = verified.lstat()
    before_identity = (before.st_dev, before.st_ino, before.st_mode)
    after_identity = (after.st_dev, after.st_ino, after.st_mode)
    if before_identity != after_identity:
        _fail("path_error", f"path changed during read: {relative_path}")
    return data


def _read_json(root: Path, relative_path: str, category: str) -> Any:
    data = _read_file(root, relative_path, markdown=False)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        _fail(category, f"invalid UTF-8: {relative_path}")
    try:
        def reject_duplicates(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise _DuplicateJSONKey(key)
                value[key] = item
            return value

        return json.loads(text, object_pairs_hook=reject_duplicates)
    except _DuplicateJSONKey as error:
        _fail(category, f"duplicate JSON key: {error}")
    except json.JSONDecodeError:
        _fail(category, f"invalid JSON: {relative_path}")


def _require_exact_keys(value: dict[str, Any], expected: set[str]) -> None:
    missing = sorted(expected - set(value))
    if missing:
        _fail("policy_error", f"missing field: {missing[0]}")
    unexpected = sorted(set(value) - expected)
    if unexpected:
        _fail("policy_error", f"unexpected field: {unexpected[0]}")


def _validate_pattern(pattern: Any, field: str) -> str:
    if not isinstance(pattern, str) or not pattern:
        _fail("policy_error", f"{field} entries must be non-empty strings")
    if (
        pattern.startswith("/")
        or _DRIVE_PATH_PATTERN.match(pattern)
        or "\\" in pattern
        or ".." in pattern.split("/")
    ):
        _fail("policy_error", f"unsafe {field} pattern: {pattern}")
    return pattern


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail("policy_error", f"{field} must be a list")
    entries = tuple(_validate_pattern(entry, field) for entry in value)
    if len(entries) != len(set(entries)):
        _fail("policy_error", f"duplicate {field} pattern")
    return entries


def _validate_policy(value: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(value, dict):
        _fail("policy_error", "policy root must be an object")
    _require_exact_keys(value, _POLICY_FIELDS)
    expected_scalars = {
        "version": 1,
        "path_style": "repo-relative-posix",
        "glob_syntax": "gitwildmatch",
        "exclude_precedence": True,
        "default_index": False,
        "follow_gitignore": False,
    }
    for field, expected in expected_scalars.items():
        if value[field] != expected or type(value[field]) is not type(expected):
            rendered = (
                str(expected).lower()
                if isinstance(expected, bool)
                else expected
            )
            _fail("policy_error", f"{field} must be {rendered}")
    includes = _string_list(value["include"], "include")
    excludes = _string_list(value["exclude"], "exclude")
    missing_includes = sorted(_REQUIRED_INCLUDES - set(includes))
    if missing_includes:
        _fail(
            "policy_error",
            f"missing required include: {missing_includes[0]}",
        )
    unexpected_includes = sorted(set(includes) - _REQUIRED_INCLUDES)
    if unexpected_includes:
        _fail(
            "policy_error",
            f"unexpected include pattern: {unexpected_includes[0]}",
        )
    missing_excludes = sorted(_REQUIRED_EXCLUDES - set(excludes))
    if missing_excludes:
        _fail(
            "policy_error",
            f"missing required exclude: {missing_excludes[0]}",
        )
    unexpected_excludes = sorted(set(excludes) - _REQUIRED_EXCLUDES)
    if unexpected_excludes:
        _fail(
            "policy_error",
            f"unexpected exclude pattern: {unexpected_excludes[0]}",
        )
    return includes, excludes


def _gitwildmatch(path: str, pattern: str) -> bool:
    # This is the small gitwildmatch subset used by index-policy.json.
    pieces: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            pieces.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            pieces.append(".*")
            index += 2
        elif pattern[index] == "*":
            pieces.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(pattern[index]))
            index += 1
    pieces.append("$")
    return re.match("".join(pieces), path) is not None


def _path_allowed(
    path: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
) -> bool:
    if any(_gitwildmatch(path, pattern) for pattern in excludes):
        return False
    return any(_gitwildmatch(path, pattern) for pattern in includes)


def _required_string(
    document: dict[str, Any],
    doc_id: str,
    field: str,
) -> str:
    if field not in document:
        _fail("manifest_error", f"missing field: {doc_id}.{field}")
    value = document[field]
    if not isinstance(value, str) or not value.strip():
        _fail("manifest_error", f"invalid field: {doc_id}.{field}")
    return value


def _manifest_documents(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        _fail("manifest_error", "manifest root must be an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        _fail(
            "manifest_error",
            f"schema_version must be {SCHEMA_VERSION}",
        )
    documents = value.get("documents")
    if not isinstance(documents, list) or not documents:
        _fail("manifest_error", "documents must be a non-empty list")
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            _fail(
                "manifest_error",
                f"document {index} must be an object",
            )
    return documents


def load_index(root: Path | str) -> ProjectIndex:
    """Load and fully validate the manifest-bound read-only index."""

    real_root = _real_root(root)
    policy = _read_json(real_root, _POLICY_PATH, "policy_error")
    includes, excludes = _validate_policy(policy)
    manifest = _read_json(real_root, _MANIFEST_PATH, "manifest_error")
    raw_documents = _manifest_documents(manifest)

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    indexed: list[IndexedDocument] = []
    for position, document in enumerate(raw_documents):
        provisional_id = document.get("doc_id")
        doc_id = (
            provisional_id
            if isinstance(provisional_id, str) and provisional_id
            else f"document-{position}"
        )
        missing = sorted(_DOCUMENT_FIELDS - set(document))
        if missing:
            _fail(
                "manifest_error",
                f"missing field: {doc_id}.{missing[0]}",
            )
        doc_id = _required_string(document, doc_id, "doc_id")
        normalized_id = doc_id.casefold()
        if normalized_id in seen_ids:
            _fail("manifest_error", f"duplicate doc_id: {doc_id}")
        seen_ids.add(normalized_id)

        path = _required_string(document, doc_id, "path")
        normalized_path = path.casefold()
        if normalized_path in seen_paths:
            _fail("manifest_error", f"duplicate path: {path}")
        seen_paths.add(normalized_path)
        _lexical_path(path, markdown=True)
        if not _path_allowed(path, includes, excludes):
            _fail("policy_error", f"path is not allowed: {path}")
        if document["index"] is not True:
            _fail("manifest_error", f"index must be true: {doc_id}")

        title = _required_string(document, doc_id, "title")
        kind = _required_string(document, doc_id, "kind")
        authority = _required_string(document, doc_id, "authority")
        status = _required_string(document, doc_id, "status")
        stage = _required_string(document, doc_id, "stage")
        sensitivity = _required_string(document, doc_id, "sensitivity")
        sha256 = _required_string(document, doc_id, "sha256")
        if _SHA256_PATTERN.fullmatch(sha256) is None:
            _fail("manifest_error", f"invalid sha256: {doc_id}")

        data = _read_file(real_root, path, markdown=True)
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if actual_sha256 != sha256:
            _fail("content_error", f"sha256 mismatch: {path}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            _fail("content_error", f"invalid UTF-8: {path}")
        indexed.append(
            IndexedDocument(
                doc_id=doc_id,
                title=title,
                path=path,
                kind=kind,
                authority=authority,
                status=status,
                stage=stage,
                sensitivity=sensitivity,
                sha256=sha256,
                text=text,
            )
        )
    return ProjectIndex(root=real_root, documents=tuple(indexed))


__all__ = [
    "IndexedDocument",
    "ProjectIndex",
    "ProjectKBError",
    "SCHEMA_VERSION",
    "load_index",
]
