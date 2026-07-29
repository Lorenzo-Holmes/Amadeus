import hashlib
from pathlib import Path

from tools.stage0b_adjudication.cli import main
from tools.stage0b_adjudication.compiler import generated_artifacts


ROOT = Path(__file__).resolve().parents[2]


def _hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.iterdir()
        if path.is_file()
    }


def test_write_then_check_is_deterministic_and_check_does_not_write(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "generated"
    assert main(["write", "--root", str(ROOT), "--output-dir", str(output)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "source_adjudication_ready=true",
        "reviewed_sources=214",
        "pending_oracle_assignments=0",
        "pending_atomicity_reviews=0",
        "case_coverage_complete=false",
        "catalog_ready=false",
        "release_ready=false",
    ]
    assert {path.name for path in output.iterdir()} == set(
        generated_artifacts(ROOT)
    )
    before = _hashes(output)

    assert main(["check", "--root", str(ROOT), "--output-dir", str(output)]) == 0
    capsys.readouterr()
    assert _hashes(output) == before


def test_check_reports_closed_drift_sets(tmp_path: Path, capsys) -> None:
    output = tmp_path / "generated"
    assert main(["write", "--root", str(ROOT), "--output-dir", str(output)]) == 0
    capsys.readouterr()
    (output / "source_clause_manifest_v0_1.json").write_text(
        "drift", encoding="utf-8"
    )
    (output / "stage0b_report_v0_1.json").unlink()
    (output / "unexpected.json").write_text("{}", encoding="utf-8")

    assert main(["check", "--root", str(ROOT), "--output-dir", str(output)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "artifact_drift=missing:stage0b_report_v0_1.json;"
        "changed:source_clause_manifest_v0_1.json;"
        "unexpected:unexpected.json"
    ]


def test_current_repository_generated_artifacts_pass_check(capsys) -> None:
    assert main(["check", "--root", str(ROOT)]) == 0
    assert "source_adjudication_ready=true" in capsys.readouterr().out


def test_pyproject_exposes_stage0b_console_script() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (
        'amadeus-stage0b = "tools.stage0b_adjudication.cli:main"'
        in pyproject
    )
