from __future__ import annotations

import subprocess

from tools.stage0c_fixtures.io import load_strict_json_bytes
from tools.stage0c_fixtures.reviewed import (
    load_reviewed_case,
    validate_batch_review_record,
)


def _git(repository_root, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def test_b01_review_record_proves_exact_data_commit(
    repository_root,
    checklist,
) -> None:
    record_path = (
        repository_root
        / "outputs"
        / "verification"
        / "stage0c-reviewed-batches"
        / "B01.json"
    )
    loaded = load_strict_json_bytes(
        record_path.read_bytes(),
        source="outputs/verification/stage0c-reviewed-batches/B01.json",
    )
    assert isinstance(loaded, dict)
    record = loaded
    checklist_rows = checklist["cases"][:20]
    reviewed_by_clause_id = {
        row["clause_id"]: load_reviewed_case(
            repository_root / row["reviewed_path"]
        )
        for row in checklist_rows
    }
    assert (
        validate_batch_review_record(
            record,
            checklist_rows,
            reviewed_by_clause_id,
        )
        == []
    )

    commit = record["reviewed_commit"]
    _git(repository_root, "cat-file", "-e", f"{commit}^{{commit}}")
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repository_root,
        check=False,
    )
    assert reachable.returncode == 0

    expected_paths = [
        record["test_path"],
        *(row["reviewed_path"] for row in checklist_rows),
    ]
    actual_paths = _git(
        repository_root,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "-r",
        commit,
    ).stdout.decode("utf-8").splitlines()
    assert sorted(actual_paths) == sorted(expected_paths)

    for relative in expected_paths:
        committed = _git(
            repository_root,
            "show",
            f"{commit}:{relative}",
        ).stdout
        assert committed == (repository_root / relative).read_bytes()
