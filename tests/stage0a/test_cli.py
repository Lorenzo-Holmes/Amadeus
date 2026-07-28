import hashlib
import json
import shutil
from pathlib import Path

import pytest

import tools.stage0a_sources.cli as cli_module


main = cli_module.main


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fixtures" / "stage0a" / "source_config_v0_1.json"
EXPECTED_FILES = {
    "source_index_v0_1.json",
    "oracle_assignment_worklist_v0_1.json",
    "atomicity_worklist_v0_1.json",
    "source_toolchain_report_v0_1.json",
}


def _canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") + b"\n"


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


def _staging_prefix(output_path: Path) -> str:
    return f".{output_path.name}.stage0a-staging-"


def _staging_residuals(output_path: Path) -> list[Path]:
    try:
        entries = list(output_path.parent.iterdir())
    except FileNotFoundError:
        return []
    return sorted(
        (
            entry
            for entry in entries
            if entry.name.startswith(_staging_prefix(output_path))
        ),
        key=lambda entry: entry.name,
    )


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
    monkeypatch: pytest.MonkeyPatch,
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
        assert payload == _canonical_json_bytes(parsed)

    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_rename = Path.rename
    rename_calls: list[tuple[Path, Path]] = []

    def record_rename(path: Path, target: Path) -> Path:
        rename_calls.append((path, target))
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", record_rename)
    assert main([
        "write",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 0
    assert capsys.readouterr().out == ""
    assert _artifact_bytes(output_dir) == before
    assert _staging_residuals(output_dir) == []
    assert not backup.exists()
    assert rename_calls == []

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
    config_path.write_bytes(_canonical_json_bytes(changed_config))

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
    expected = _artifact_bytes(output_dir)
    (output_dir / "source_index_v0_1.json").write_bytes(
        b"old snapshot\n"
    )
    before = _tree_snapshot(output_dir)
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_open = Path.open
    staging_writes = 0
    observed_staging: Path | None = None

    def fail_third_staging_write(
        path: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding=None,
        errors=None,
        newline=None,
    ):
        nonlocal observed_staging, staging_writes
        if (
            path.parent.name.startswith(
                _staging_prefix(output_dir)
            )
            and mode == "xb"
        ):
            if observed_staging is None:
                observed_staging = path.parent
            assert path.parent == observed_staging
            staging_writes += 1
            if staging_writes == 3:
                raise OSError("simulated staging failure")
        return original_open(
            path,
            mode,
            buffering,
            encoding,
            errors,
            newline,
        )

    monkeypatch.setattr(Path, "open", fail_third_staging_write)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=simulated staging failure"
    )
    assert staging_writes == 3
    assert _tree_snapshot(output_dir) == before
    assert observed_staging is not None
    staging = observed_staging
    assert staging.name.startswith(_staging_prefix(output_dir))
    assert staging != output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    assert staging.is_dir()
    assert _artifact_bytes(staging) == {
        "source_index_v0_1.json": expected[
            "source_index_v0_1.json"
        ],
        "oracle_assignment_worklist_v0_1.json": expected[
            "oracle_assignment_worklist_v0_1.json"
        ],
    }
    assert not backup.exists()
    residual_before_retry = _tree_snapshot(staging)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=transaction path already exists"
    )
    assert _tree_snapshot(output_dir) == before
    assert _staging_residuals(output_dir) == [staging]
    assert _tree_snapshot(staging) == residual_before_retry


def test_changed_write_preserves_complete_backup_and_blocks_next_write(
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
    (output_dir / "source_index_v0_1.json").write_bytes(
        b"previous snapshot\n"
    )
    previous = _tree_snapshot(output_dir)
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )

    def reject_automatic_delete(path: Path, *args, **kwargs) -> None:
        pytest.fail(f"transaction attempted automatic delete: {path}")

    monkeypatch.setattr(Path, "unlink", reject_automatic_delete)
    monkeypatch.setattr(Path, "rmdir", reject_automatic_delete)

    assert main(["write", *arguments]) == 0
    assert capsys.readouterr().out.strip() == (
        f"backup_preserved={backup}"
    )
    assert _artifact_bytes(output_dir) == expected
    assert _staging_residuals(output_dir) == []
    assert backup.is_dir()
    assert _tree_snapshot(backup) == previous
    output_before_retry = _tree_snapshot(output_dir)
    backup_before_retry = _tree_snapshot(backup)
    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=transaction path already exists"
    )
    assert _tree_snapshot(output_dir) == output_before_retry
    assert _tree_snapshot(backup) == backup_before_retry


def test_open_guard_blocks_staging_swap_before_artifact_creation(
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
    (output_dir / "source_index_v0_1.json").write_bytes(
        b"old output\n"
    )
    old_output = _tree_snapshot(output_dir)

    external = tmp_path / "external"
    external.mkdir()
    for file_name in EXPECTED_FILES:
        (external / file_name).write_bytes(
            f"external:{file_name}".encode("utf-8")
        )
    external_before = _tree_snapshot(external)
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_require = cli_module._require_directory_identity
    attempts = 0
    observed_staging: Path | None = None
    moved: Path | None = None

    def try_swap_after_identity_check(*args, **kwargs) -> None:
        nonlocal attempts, moved, observed_staging
        original_require(*args, **kwargs)
        directory = args[0]
        if (
            directory.name.startswith(
                _staging_prefix(output_dir)
            )
            and attempts == 0
        ):
            observed_staging = directory
            moved = directory.with_name(
                f"{directory.name}-moved"
            )
            attempts += 1
            directory.rename(moved)
            directory.symlink_to(
                external,
                target_is_directory=True,
            )

    monkeypatch.setattr(
        cli_module,
        "_require_directory_identity",
        try_swap_after_identity_check,
    )

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.startswith("write_error=")
    assert attempts == 1
    assert _tree_snapshot(output_dir) == old_output
    assert _tree_snapshot(external) == external_before
    assert observed_staging is not None
    staging = observed_staging
    assert staging.name.startswith(_staging_prefix(output_dir))
    assert staging != output_dir.with_name(
        f".{output_dir.name}.stage0a-staging"
    )
    assert staging.is_dir()
    assert not staging.is_symlink()
    assert moved is not None
    assert not moved.exists()
    assert not backup.exists()


def test_post_guard_staging_swap_is_rolled_back_without_following_link(
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
    (output_dir / "source_index_v0_1.json").write_bytes(
        b"old output\n"
    )
    old_output = _tree_snapshot(output_dir)

    external = tmp_path / "external"
    external.mkdir()
    external_before = _tree_snapshot(external)
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_validate_root = cli_module._validate_output_root
    output_checks = 0
    swaps = 0
    observed_staging: Path | None = None
    moved: Path | None = None

    def swap_after_guard_closes(path: Path) -> bool:
        nonlocal moved, observed_staging, output_checks, swaps
        if path == output_dir:
            output_checks += 1
            if output_checks == 2:
                residuals = _staging_residuals(output_dir)
                assert len(residuals) == 1
                observed_staging = residuals[0]
                moved = observed_staging.with_name(
                    f"{observed_staging.name}-moved"
                )
                staging = observed_staging
                staging.rename(moved)
                staging.symlink_to(
                    external,
                    target_is_directory=True,
                )
                swaps += 1
        return original_validate_root(path)

    monkeypatch.setattr(
        cli_module,
        "_validate_output_root",
        swap_after_guard_closes,
    )

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=installed output root is not the staged snapshot"
    )
    assert swaps == 1
    assert _tree_snapshot(output_dir) == old_output
    assert _tree_snapshot(external) == external_before
    assert observed_staging is not None
    staging = observed_staging
    assert staging.name.startswith(_staging_prefix(output_dir))
    assert staging.is_symlink()
    assert moved is not None
    assert moved.is_dir()
    assert not backup.exists()


def test_write_rejects_output_directory_symlink_without_following_it(
    tmp_path: Path,
    capsys,
) -> None:
    external_dir = tmp_path / "external"
    external_arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(external_dir),
    ]
    assert main(["write", *external_arguments]) == 0
    capsys.readouterr()
    external_before = _tree_snapshot(external_dir)

    output_link = tmp_path / "generated-link"
    output_link.symlink_to(external_dir, target_is_directory=True)
    backup = output_link.with_name(
        f".{output_link.name}.stage0a-backup"
    )
    arguments = [
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_link),
    ]

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=output root must be a real directory"
    )
    assert output_link.is_symlink()
    assert _tree_snapshot(external_dir) == external_before
    assert _staging_residuals(output_link) == []
    assert not backup.exists()


@pytest.mark.parametrize("command", ["write", "check"])
def test_command_rejects_output_parent_symlink_without_following_it(
    command: str,
    tmp_path: Path,
    capsys,
) -> None:
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_before = _tree_snapshot(external_dir)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(external_dir, target_is_directory=True)
    output_dir = linked_parent / "generated"

    assert main([
        command,
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 1
    assert capsys.readouterr().out.strip() == (
        f"{command}_error="
        "output parent chain must contain only real directories"
    )
    assert linked_parent.is_symlink()
    assert _tree_snapshot(external_dir) == external_before
    assert not (external_dir / "generated").exists()


def test_write_rejects_output_parent_junction_before_staging(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_parent = tmp_path / "output-parent"
    output_parent.mkdir()
    output_dir = output_parent / "generated"
    original_is_junction = Path.is_junction
    mkdtemp_calls = 0
    original_mkdtemp = cli_module.tempfile.mkdtemp

    def mark_parent_as_junction(path: Path) -> bool:
        if path == output_parent:
            return True
        return original_is_junction(path)

    def record_mkdtemp(*args, **kwargs) -> str:
        nonlocal mkdtemp_calls
        mkdtemp_calls += 1
        return original_mkdtemp(*args, **kwargs)

    monkeypatch.setattr(Path, "is_junction", mark_parent_as_junction)
    monkeypatch.setattr(cli_module.tempfile, "mkdtemp", record_mkdtemp)

    assert main([
        "write",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error="
        "output parent chain must contain only real directories"
    )
    assert mkdtemp_calls == 0
    assert list(output_parent.iterdir()) == []


def test_write_detects_output_parent_swap_after_staging_creation(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_parent = tmp_path / "output-parent"
    output_parent.mkdir()
    output_dir = output_parent / "generated"
    moved_parent = tmp_path / "moved-parent"
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_before = _tree_snapshot(external_dir)
    original_mkdtemp = cli_module.tempfile.mkdtemp
    observed_staging_name: str | None = None

    def swap_parent_after_mkdtemp(*args, **kwargs) -> str:
        nonlocal observed_staging_name
        staging = Path(original_mkdtemp(*args, **kwargs))
        observed_staging_name = staging.name
        output_parent.rename(moved_parent)
        output_parent.symlink_to(
            external_dir,
            target_is_directory=True,
        )
        return str(staging)

    monkeypatch.setattr(
        cli_module.tempfile,
        "mkdtemp",
        swap_parent_after_mkdtemp,
    )

    assert main([
        "write",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_dir),
    ]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=output parent changed during operation"
    )
    assert output_parent.is_symlink()
    assert _tree_snapshot(external_dir) == external_before
    assert observed_staging_name is not None
    preserved_staging = moved_parent / observed_staging_name
    assert preserved_staging.is_dir()
    assert list(preserved_staging.iterdir()) == []


def test_write_rejects_output_junction_before_any_rename(
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
    backup = output_dir.with_name(
        f".{output_dir.name}.stage0a-backup"
    )
    original_is_junction = Path.is_junction
    original_rename = Path.rename
    rename_calls: list[tuple[Path, Path]] = []

    def mark_output_as_junction(path: Path) -> bool:
        if path == output_dir:
            return True
        return original_is_junction(path)

    def record_rename(path: Path, target: Path) -> Path:
        rename_calls.append((path, target))
        return original_rename(path, target)

    monkeypatch.setattr(Path, "is_junction", mark_output_as_junction)
    monkeypatch.setattr(Path, "rename", record_rename)

    assert main(["write", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=output root must be a real directory"
    )
    assert rename_calls == []
    assert _tree_snapshot(output_dir) == before
    assert _staging_residuals(output_dir) == []
    assert not backup.exists()


def test_write_rejects_regular_output_file_without_replacing_it(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "sentinel"
    output_path.write_bytes(b"keep this sentinel")
    backup = output_path.with_name(
        f".{output_path.name}.stage0a-backup"
    )

    assert main([
        "write",
        "--root",
        str(ROOT),
        "--output-dir",
        str(output_path),
    ]) == 1
    assert capsys.readouterr().out.strip() == (
        "write_error=output root must be a real directory"
    )
    assert output_path.is_file()
    assert not output_path.is_symlink()
    assert output_path.read_bytes() == b"keep this sentinel"
    assert _staging_residuals(output_path) == []
    assert not backup.exists()


def test_check_rejects_known_artifact_symlink_without_reading_target(
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

    artifact = output_dir / "source_index_v0_1.json"
    expected = artifact.read_bytes()
    external_file = tmp_path / "external.json"
    external_file.write_bytes(expected)
    artifact.unlink()
    artifact.symlink_to(external_file)

    assert main(["check", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "artifact_drift=missing:;"
        "changed:source_index_v0_1.json;unexpected:"
    )
    assert artifact.is_symlink()
    assert external_file.read_bytes() == expected


def test_check_reports_output_enumeration_error_without_writing(
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
    original_iterdir = Path.iterdir
    denials = 0

    def deny_first_output_enumeration(path: Path):
        nonlocal denials
        if path == output_dir and denials == 0:
            denials += 1
            raise PermissionError("simulated check enumeration denial")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", deny_first_output_enumeration)

    assert main(["check", *arguments]) == 1
    assert capsys.readouterr().out.strip() == (
        "check_error=simulated check enumeration denial"
    )
    assert denials == 1
    assert _tree_snapshot(output_dir) == before
