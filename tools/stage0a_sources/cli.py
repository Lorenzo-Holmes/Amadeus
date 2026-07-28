import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from .canonical import _sha256_hex, canonical_bytes
from .compiler import compile_source_index
from .worklists import build_atomicity_worklist, build_oracle_worklist


__all__ = ["main"]

_CONFIG_PATH = Path("fixtures/stage0a/source_config_v0_1.json")
_DEFAULT_OUTPUT_DIR = Path("fixtures/stage0a/generated")
_FILES = {
    "source_index_v0_1.json": "source_index",
    "oracle_assignment_worklist_v0_1.json": "oracle_worklist",
    "atomicity_worklist_v0_1.json": "atomicity_worklist",
    "source_toolchain_report_v0_1.json": "report",
}


def _read_config(root: Path) -> tuple[dict[str, Any], str]:
    raw_config = (root / _CONFIG_PATH).read_bytes()
    config = json.loads(raw_config.decode("utf-8"))
    return config, _sha256_hex(raw_config)


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise ValueError(f"source readiness: {label}")


def _build_artifacts(root: Path) -> dict[str, bytes]:
    config, source_config_sha256 = _read_config(root)
    source_index = compile_source_index(
        root,
        config,
        source_config_sha256,
    )
    oracle_worklist = build_oracle_worklist(source_index)
    atomicity_worklist = build_atomicity_worklist(source_index)

    _require(
        source_index["source_counts"]
        == {"baseline": 53, "increment": 66, "core": 95},
        "source counts",
    )
    _require(source_index["unique_source_count"] == 214, "unique source count")
    _require(source_index["missing_source_ids"] == [], "missing source ids")
    _require(source_index["unexpected_source_ids"] == [], "unexpected source ids")
    _require(source_index["duplicate_source_ids"] == [], "duplicate source ids")
    _require(
        oracle_worklist["source_declared_count"] == 119,
        "source-declared oracle count",
    )
    _require(
        oracle_worklist["pending_assignment_count"] == 95,
        "pending oracle assignment count",
    )
    _require(
        atomicity_worklist["pending_review_count"] == 214,
        "pending atomicity review count",
    )

    report = {
        "schema_version": "0.1",
        "source_config_sha256": source_config_sha256,
        "source_toolchain_ready": True,
        "unique_source_count": 214,
        "pending_oracle_assignments": 95,
        "pending_atomicity_reviews": 214,
        "atomicity_complete": False,
        "case_coverage_complete": False,
        "catalog_ready": False,
        "release_ready": False,
    }
    values = {
        "source_index": source_index,
        "oracle_worklist": oracle_worklist,
        "atomicity_worklist": atomicity_worklist,
        "report": report,
    }
    return {
        file_name: canonical_bytes(values[value_name]) + b"\n"
        for file_name, value_name in _FILES.items()
    }


def _print_artifact_drift(
    missing: list[str],
    changed: list[str],
    unexpected: list[str],
) -> int:
    print(
        "artifact_drift="
        f"missing:{','.join(missing)};"
        f"changed:{','.join(changed)};"
        f"unexpected:{','.join(unexpected)}"
    )
    return 1


def _output_entries(output_dir: Path) -> list[Path]:
    try:
        return list(output_dir.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return []


def _path_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _staging_prefix(output_dir: Path) -> str:
    return f".{output_dir.name}.stage0a-staging-"


def _staging_residuals(output_dir: Path) -> list[Path]:
    try:
        entries = list(output_dir.parent.iterdir())
    except FileNotFoundError:
        return []
    return sorted(
        (
            entry
            for entry in entries
            if entry.name.startswith(_staging_prefix(output_dir))
        ),
        key=lambda entry: entry.name,
    )


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _validate_output_root(output_dir: Path) -> bool:
    if not _path_present(output_dir):
        return False
    if _is_link_or_junction(output_dir) or not output_dir.is_dir():
        raise OSError("output root must be a real directory")
    return True


def _output_parent_identity(output_dir: Path) -> tuple[int, int, int]:
    directory = output_dir.parent
    lineage = [directory]
    while lineage[-1].parent != lineage[-1]:
        lineage.append(lineage[-1].parent)
    for ancestor in reversed(lineage):
        if (
            not _path_present(ancestor)
            or _is_link_or_junction(ancestor)
            or not ancestor.is_dir()
        ):
            raise OSError(
                "output parent chain must contain only real directories"
            )
    status = directory.lstat()
    return status.st_dev, status.st_ino, status.st_mode


def _require_output_parent_identity(
    output_dir: Path,
    identity: tuple[int, int, int],
) -> None:
    try:
        current = _output_parent_identity(output_dir)
    except OSError as error:
        raise OSError("output parent changed during operation") from error
    if current != identity:
        raise OSError("output parent changed during operation")


def _is_plain_file(path: Path) -> bool:
    if not _path_present(path):
        return False
    return (
        not _is_link_or_junction(path)
        and path.is_file()
    )


def _write_preflight(
    output_dir: Path,
    artifacts: dict[str, bytes],
) -> tuple[bool, bool]:
    entries = _output_entries(output_dir)
    unexpected = sorted(
        entry.name
        for entry in entries
        if entry.name not in artifacts
    )
    changed: list[str] = []
    current_bytes: dict[str, bytes] = {}
    for entry in entries:
        if entry.name not in artifacts:
            continue
        if not _is_plain_file(entry):
            changed.append(entry.name)
            continue
        try:
            current_bytes[entry.name] = entry.read_bytes()
        except OSError:
            changed.append(entry.name)
    if changed or unexpected:
        _print_artifact_drift([], sorted(changed), unexpected)
        return False, False
    exact = (
        set(current_bytes) == set(artifacts)
        and all(
            current_bytes[file_name] == payload
            for file_name, payload in artifacts.items()
        )
    )
    return True, exact


def _safe_snapshot_entries(snapshot_dir: Path) -> list[Path]:
    if not _path_present(snapshot_dir):
        return []
    if (
        _is_link_or_junction(snapshot_dir)
        or not snapshot_dir.is_dir()
    ):
        raise OSError("unsafe snapshot root")
    entries = list(snapshot_dir.iterdir())
    for entry in entries:
        if not _is_plain_file(entry):
            raise OSError(f"unsafe snapshot entry: {entry.name}")
    return entries


def _validate_snapshot(
    snapshot_dir: Path,
    artifacts: dict[str, bytes],
) -> None:
    entries = _safe_snapshot_entries(snapshot_dir)
    actual_names = {entry.name for entry in entries}
    if actual_names != set(artifacts):
        raise OSError("staging file set mismatch")
    for file_name, expected in artifacts.items():
        if (snapshot_dir / file_name).read_bytes() != expected:
            raise OSError(f"staging content mismatch: {file_name}")


def _directory_identity(directory: Path) -> tuple[int, int, int]:
    if not _validate_output_root(directory):
        raise OSError("directory identity is missing")
    status = directory.lstat()
    return status.st_dev, status.st_ino, status.st_mode


def _require_directory_identity(
    directory: Path,
    identity: tuple[int, int, int],
    message: str,
) -> None:
    try:
        current = _directory_identity(directory)
    except OSError as error:
        raise OSError(message) from error
    if current != identity:
        raise OSError(message)


def _write(output_dir: Path, artifacts: dict[str, bytes]) -> int:
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    staging: Path | None = None
    old_moved = False
    new_installed = False
    parent_identity: tuple[int, int, int] | None = None
    try:
        parent_identity = _output_parent_identity(output_dir)
        output_was_present = _validate_output_root(output_dir)
        preflight_ok, output_is_exact = _write_preflight(
            output_dir,
            artifacts,
        )
        if not preflight_ok:
            return 1
        _require_output_parent_identity(output_dir, parent_identity)
        if _staging_residuals(output_dir) or _path_present(backup):
            raise OSError("transaction path already exists")
        if output_was_present and output_is_exact:
            return 0

        _require_output_parent_identity(output_dir, parent_identity)
        staging = Path(tempfile.mkdtemp(
            prefix=_staging_prefix(output_dir),
            dir=output_dir.parent,
        ))
        _require_output_parent_identity(output_dir, parent_identity)
        if _staging_residuals(output_dir) != [staging]:
            raise OSError("transaction path changed during write")
        staging_identity = _directory_identity(staging)
        artifact_items = iter(artifacts.items())
        guard_name, guard_payload = next(artifact_items)
        _require_output_parent_identity(output_dir, parent_identity)
        with (staging / guard_name).open("xb") as directory_guard:
            guard_written = directory_guard.write(guard_payload)
            directory_guard.flush()
            if guard_written != len(guard_payload):
                raise OSError(f"short staging write: {guard_name}")
            _require_output_parent_identity(output_dir, parent_identity)
            _require_directory_identity(
                staging,
                staging_identity,
                "staging root changed during write",
            )
            for file_name, payload in artifact_items:
                _require_output_parent_identity(
                    output_dir,
                    parent_identity,
                )
                with (staging / file_name).open("xb") as destination:
                    written = destination.write(payload)
                if written != len(payload):
                    raise OSError(f"short staging write: {file_name}")
                _require_output_parent_identity(
                    output_dir,
                    parent_identity,
                )
                _require_directory_identity(
                    staging,
                    staging_identity,
                    "staging root changed during write",
                )
            _validate_snapshot(staging, artifacts)
            _require_directory_identity(
                staging,
                staging_identity,
                "staging root changed during write",
            )
            _require_output_parent_identity(
                output_dir,
                parent_identity,
            )

        _require_output_parent_identity(output_dir, parent_identity)
        _require_directory_identity(
            staging,
            staging_identity,
            "staging root changed during write",
        )

        if _validate_output_root(output_dir) != output_was_present:
            raise OSError("output root changed during write")
        if output_was_present:
            _require_output_parent_identity(output_dir, parent_identity)
            output_dir.rename(backup)
            old_moved = True
            _require_output_parent_identity(output_dir, parent_identity)
        _require_output_parent_identity(output_dir, parent_identity)
        staging.rename(output_dir)
        new_installed = True
        _require_output_parent_identity(output_dir, parent_identity)
        _require_directory_identity(
            output_dir,
            staging_identity,
            "installed output root is not the staged snapshot",
        )
        _validate_snapshot(output_dir, artifacts)
        _require_directory_identity(
            output_dir,
            staging_identity,
            "installed output root changed during validation",
        )
        if old_moved:
            print(f"backup_preserved={backup}")
        return 0
    except OSError as error:
        rollback_errors: list[str] = []
        if new_installed:
            try:
                if staging is None:
                    raise OSError("staging identity is missing")
                if parent_identity is None:
                    raise OSError("output parent identity is missing")
                _require_output_parent_identity(
                    output_dir,
                    parent_identity,
                )
                output_dir.rename(staging)
                new_installed = False
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if old_moved:
            try:
                if parent_identity is None:
                    raise OSError("output parent identity is missing")
                _require_output_parent_identity(
                    output_dir,
                    parent_identity,
                )
                backup.rename(output_dir)
                old_moved = False
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        suffix = (
            f";rollback_error={';'.join(rollback_errors)}"
            if rollback_errors
            else ""
        )
        print(f"write_error={error}{suffix}")
        return 1


def _check(output_dir: Path, artifacts: dict[str, bytes]) -> int:
    missing: list[str] = []
    changed: list[str] = []
    try:
        parent_identity = _output_parent_identity(output_dir)
        output_is_present = _validate_output_root(output_dir)
        for file_name, expected in artifacts.items():
            entry = output_dir / file_name
            try:
                _require_output_parent_identity(
                    output_dir,
                    parent_identity,
                )
                if not output_is_present or not _path_present(entry):
                    missing.append(file_name)
                elif not _is_plain_file(entry):
                    changed.append(file_name)
                elif entry.read_bytes() != expected:
                    changed.append(file_name)
            except (FileNotFoundError, NotADirectoryError):
                missing.append(file_name)
            except OSError:
                changed.append(file_name)
        _require_output_parent_identity(output_dir, parent_identity)
        entries = _output_entries(output_dir)
    except OSError as error:
        print(f"check_error={error}")
        return 1
    unexpected = sorted(
        entry.name
        for entry in entries
        if entry.name not in artifacts
    )
    if missing or changed or unexpected:
        return _print_artifact_drift(
            sorted(missing),
            sorted(changed),
            unexpected,
        )
    print("source_toolchain_ready=true")
    print("pending_oracle_assignments=95")
    print("pending_atomicity_reviews=214")
    return 0


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("write", "check"))
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        root = Path(arguments.root).resolve(strict=True)
        artifacts = _build_artifacts(root)
    except (OSError, ValueError) as error:
        print(f"input_error={error}")
        return 2
    output_argument = Path(arguments.output_dir)
    output_dir = (
        output_argument
        if output_argument.is_absolute()
        else root / output_argument
    )
    if arguments.command == "write":
        return _write(output_dir, artifacts)
    return _check(output_dir, artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
