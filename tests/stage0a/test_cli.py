import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tools.stage0a_sources.canonical import canonical_bytes
from tools.stage0a_sources.cli import main


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fixtures" / "stage0a" / "source_config_v0_1.json"
EXPECTED_FILES = {
    "source_index_v0_1.json",
    "oracle_assignment_worklist_v0_1.json",
    "atomicity_worklist_v0_1.json",
    "source_toolchain_report_v0_1.json",
}


def _artifact_bytes(output_dir: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in output_dir.iterdir()
    }


def _tree_snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): (
            None
            if path.is_dir()
            else path.read_bytes()
        )
        for path in root.rglob("*")
    }


def _copy_frozen_root(destination: Path) -> Path:
    frozen_root = destination / "frozen"
    raw_config = CONFIG_PATH.read_bytes()
    target_config = (
        frozen_root
        / "fixtures"
        / "stage0a"
        / "source_config_v0_1.json"
    )
    target_config.parent.mkdir(parents=True, exist_ok=True)
    target_config.write_bytes(raw_config)
    for document in json.loads(raw_config)["documents"]:
        source = ROOT / document["path"]
        target = frozen_root / document["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return frozen_root


def test_write_then_check_preserves_exact_canonical_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "generated"

    assert main([
        "write",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 0
    capsys.readouterr()

    assert {path.name for path in output_dir.iterdir()} == EXPECTED_FILES
    before = _artifact_bytes(output_dir)
    for payload in before.values():
        parsed = json.loads(payload)
        assert payload == canonical_bytes(parsed) + b"\n"

    assert main([
        "check",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "source_toolchain_ready=true",
        "pending_oracle_assignments=95",
        "pending_atomicity_reviews=214",
    ]
    assert _artifact_bytes(output_dir) == before


def test_check_reports_changed_artifact_bytes(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    (output_dir / "source_index_v0_1.json").write_bytes(b"{}\n")

    assert main(["check", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;changed:source_index_v0_1.json;"
        "unexpected:"
    )


def test_check_reports_unexpected_output_entries(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    (output_dir / "unexpected.txt").write_text(
        "unexpected",
        encoding="utf-8",
    )

    assert main(["check", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;changed:;unexpected:unexpected.txt"
    )


def test_raw_config_bytes_are_part_of_artifact_identity(
    tmp_path: Path,
    capsys,
) -> None:
    frozen_root = _copy_frozen_root(tmp_path)
    output_dir = frozen_root / "artifacts"
    arguments = [
        "--root",
        str(frozen_root),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    before = _artifact_bytes(output_dir)

    config_path = (
        frozen_root
        / "fixtures"
        / "stage0a"
        / "source_config_v0_1.json"
    )
    semantic_config = json.loads(config_path.read_bytes())
    config_path.write_bytes(config_path.read_bytes() + b"\n")
    changed_raw_config = config_path.read_bytes()
    assert json.loads(changed_raw_config) == semantic_config

    assert main(["check", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;"
        "changed:source_index_v0_1.json,"
        "source_toolchain_report_v0_1.json;"
        "unexpected:"
    )
    assert _artifact_bytes(output_dir) == before

    assert main(["write", *arguments]) == 0
    expected_hash = hashlib.sha256(changed_raw_config).hexdigest().upper()
    report = json.loads(
        (output_dir / "source_toolchain_report_v0_1.json").read_bytes()
    )
    source_index = json.loads(
        (output_dir / "source_index_v0_1.json").read_bytes()
    )
    assert report["source_config_sha256"] == expected_hash
    assert source_index["source_config_sha256"] == expected_hash


@pytest.mark.parametrize("command", ["write", "check"])
def test_document_input_drift_returns_2_without_changing_outputs(
    tmp_path: Path,
    capsys,
    command: str,
) -> None:
    frozen_root = _copy_frozen_root(tmp_path)
    output_dir = frozen_root / "artifacts"
    arguments = [
        "--root",
        str(frozen_root),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    before = _artifact_bytes(output_dir)

    config = json.loads(
        (
            frozen_root
            / "fixtures"
            / "stage0a"
            / "source_config_v0_1.json"
        ).read_bytes()
    )
    baseline = next(
        document
        for document in config["documents"]
        if document["key"] == "baseline"
    )
    changed_document = frozen_root / baseline["path"]
    changed_document.write_bytes(changed_document.read_bytes() + b"\x00")

    assert main([command, *arguments]) == 2
    assert capsys.readouterr().out.startswith(
        "input_error=document drift: key=baseline "
    )
    assert _artifact_bytes(output_dir) == before


@pytest.mark.parametrize("command", ["write", "check"])
def test_config_identity_drift_returns_2_without_changing_outputs(
    tmp_path: Path,
    capsys,
    command: str,
) -> None:
    frozen_root = _copy_frozen_root(tmp_path)
    output_dir = frozen_root / "artifacts"
    arguments = [
        "--root",
        str(frozen_root),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    before = _artifact_bytes(output_dir)

    config_path = (
        frozen_root
        / "fixtures"
        / "stage0a"
        / "source_config_v0_1.json"
    )
    changed_config = json.loads(config_path.read_bytes())
    changed_config["schema_version"] = "0.2"
    config_path.write_bytes(canonical_bytes(changed_config) + b"\n")

    assert main([command, *arguments]) == 2
    assert capsys.readouterr().out.strip() == (
        "input_error=configuration contract: schema_version identity"
    )
    assert _artifact_bytes(output_dir) == before


def test_write_rejects_unexpected_directory_without_changing_output(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    unexpected = output_dir / "unexpected-dir"
    unexpected.mkdir()
    (unexpected / "sentinel.txt").write_bytes(b"keep")
    before = _tree_snapshot(output_dir)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;changed:;unexpected:unexpected-dir"
    )
    assert _tree_snapshot(output_dir) == before


def test_write_rejects_target_directory_without_changing_output(
    tmp_path: Path,
    capsys,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    occupied = output_dir / "source_index_v0_1.json"
    occupied.unlink()
    occupied.mkdir()
    (occupied / "sentinel.txt").write_bytes(b"keep")
    before = _tree_snapshot(output_dir)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;"
        "changed:source_index_v0_1.json;"
        "unexpected:"
    )
    assert _tree_snapshot(output_dir) == before


def test_staging_write_failure_preserves_original_snapshot(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    before = _tree_snapshot(output_dir)
    staging = output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_write_bytes = Path.write_bytes
    staging_writes = 0

    def fail_third_staging_write(path: Path, payload: bytes) -> int:
        nonlocal staging_writes
        if path.parent == staging:
            staging_writes += 1
            if staging_writes == 3:
                raise OSError("simulated staging failure")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", fail_third_staging_write)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=simulated staging failure"
    )
    assert staging_writes == 3
    assert _tree_snapshot(output_dir) == before
    assert not staging.exists()
    assert not backup.exists()


def test_backup_unlink_failure_keeps_committed_output_complete(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    expected = _artifact_bytes(output_dir)
    staging = output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_unlink = Path.unlink
    backup_unlinks = 0

    def fail_second_backup_unlink(
        path: Path,
        missing_ok: bool = False,
    ) -> None:
        nonlocal backup_unlinks
        if path.parent == backup:
            backup_unlinks += 1
            if backup_unlinks == 2:
                raise OSError("simulated backup unlink failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_second_backup_unlink)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=simulated backup unlink failure"
    )
    assert backup_unlinks == 2
    assert _artifact_bytes(output_dir) == expected
    assert not staging.exists()
    assert backup.is_dir()
    assert len(list(backup.iterdir())) == 3


def test_backup_rmdir_failure_keeps_committed_output_complete(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]
    assert main(["write", *arguments]) == 0
    capsys.readouterr()
    expected = _artifact_bytes(output_dir)
    staging = output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_rmdir = Path.rmdir

    def fail_backup_rmdir(path: Path) -> None:
        if path == backup:
            raise OSError("simulated backup rmdir failure")
        original_rmdir(path)

    monkeypatch.setattr(Path, "rmdir", fail_backup_rmdir)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=simulated backup rmdir failure"
    )
    assert _artifact_bytes(output_dir) == expected
    assert not staging.exists()
    assert backup.is_dir()
    assert list(backup.iterdir()) == []
