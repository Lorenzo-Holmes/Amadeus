import argparse
import json
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


def _write_preflight(
    output_dir: Path,
    artifacts: dict[str, bytes],
) -> bool:
    entries = _output_entries(output_dir)
    unexpected = sorted(
        entry.name
        for entry in entries
        if entry.name not in artifacts
    )
    changed: list[str] = []
    for entry in entries:
        if entry.name not in artifacts:
            continue
        try:
            entry.read_bytes()
        except OSError:
            changed.append(entry.name)
    if changed or unexpected:
        _print_artifact_drift([], sorted(changed), unexpected)
        return False
    return True


def _remove_snapshot(snapshot_dir: Path) -> None:
    try:
        entries = list(snapshot_dir.iterdir())
    except FileNotFoundError:
        return
    for entry in entries:
        entry.unlink()
    snapshot_dir.rmdir()


def _validate_snapshot(
    snapshot_dir: Path,
    artifacts: dict[str, bytes],
) -> None:
    actual_names = {
        entry.name
        for entry in snapshot_dir.iterdir()
    }
    if actual_names != set(artifacts):
        raise OSError("staging file set mismatch")
    for file_name, expected in artifacts.items():
        if (snapshot_dir / file_name).read_bytes() != expected:
            raise OSError(f"staging content mismatch: {file_name}")


def _write(output_dir: Path, artifacts: dict[str, bytes]) -> int:
    staging = output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    old_moved = False
    new_installed = False
    staging_created = False
    committed = False
    try:
        if not _write_preflight(output_dir, artifacts):
            return 1
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        if staging.exists() or backup.exists():
            raise OSError("transaction path already exists")
        staging.mkdir()
        staging_created = True
        for file_name, payload in artifacts.items():
            (staging / file_name).write_bytes(payload)
        _validate_snapshot(staging, artifacts)

        if output_dir.exists():
            output_dir.rename(backup)
            old_moved = True
        staging.rename(output_dir)
        new_installed = True
        staging_created = False
        committed = True
        if old_moved:
            _remove_snapshot(backup)
            old_moved = False
        return 0
    except OSError as error:
        rollback_errors: list[str] = []
        if not committed:
            if new_installed:
                try:
                    output_dir.rename(staging)
                    new_installed = False
                    staging_created = True
                except OSError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            if old_moved:
                try:
                    backup.rename(output_dir)
                    old_moved = False
                except OSError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            if staging_created:
                try:
                    _remove_snapshot(staging)
                    staging_created = False
                except OSError as cleanup_error:
                    rollback_errors.append(str(cleanup_error))
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
    for file_name, expected in artifacts.items():
        try:
            actual = (output_dir / file_name).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            missing.append(file_name)
        except OSError:
            changed.append(file_name)
        else:
            if actual != expected:
                changed.append(file_name)
    unexpected = sorted(
        entry.name
        for entry in _output_entries(output_dir)
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
