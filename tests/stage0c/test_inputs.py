import copy
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any, Callable

import pytest

from tools.stage0c_fixtures import io as fixture_io
from tools.stage0c_fixtures.constants import (
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_SOURCE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
)
from tools.stage0c_fixtures.io import (
    load_frozen_inputs,
    validate_frozen_semantics,
    canonical_id_set_sha256,
    FrozenInputs,
    FixtureInputError,
    load_strict_json_bytes,
    read_repo_regular_file,
    sha256_upper,
)


_INPUT_KEYS = tuple(INPUT_IDENTITIES)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_RAW_IDENTITY_CASES = [
    pytest.param("terminal", "delete", "frozen_input_missing", id="terminal-delete"),
    pytest.param(
        "terminal",
        "append",
        "frozen_input_size_or_hash_mismatch",
        id="terminal-append-byte",
    ),
    pytest.param(
        "terminal",
        "remove",
        "frozen_input_size_or_hash_mismatch",
        id="terminal-remove-byte",
    ),
    pytest.param(
        "terminal",
        "flip",
        "frozen_input_size_or_hash_mismatch",
        id="terminal-same-size-flip",
    ),
    pytest.param(
        "terminal",
        "directory",
        "repo_path_not_regular_file",
        id="terminal-directory",
    ),
    pytest.param(
        "terminal",
        "junction-present",
        "repo_path_reparse",
        id="terminal-junction-present",
    ),
    pytest.param(
        "terminal",
        "junction-dangling",
        "repo_path_reparse",
        id="terminal-junction-dangling",
    ),
    pytest.param(
        "ancestor",
        "delete",
        "frozen_input_missing",
        id="ancestor-missing",
    ),
    pytest.param(
        "ancestor",
        "junction-present",
        "repo_path_reparse",
        id="ancestor-junction-present",
    ),
    pytest.param(
        "ancestor",
        "junction-dangling",
        "repo_path_reparse",
        id="ancestor-junction-dangling",
    ),
]


def _identity_path(key: str) -> str:
    value = INPUT_IDENTITIES[key]["path"]
    assert type(value) is str
    return value


def _identity_size(key: str) -> int:
    value = INPUT_IDENTITIES[key]["size"]
    assert type(value) is int
    return value


def _identity_sha256(key: str) -> str:
    value = INPUT_IDENTITIES[key]["sha256"]
    assert type(value) is str
    return value


def _copy_frozen_inputs(source_root: Path, destination_root: Path) -> None:
    for key in _INPUT_KEYS:
        relative = _identity_path(key)
        source = source_root.joinpath(*relative.split("/"))
        destination = destination_root.joinpath(*relative.split("/"))
        expected = source.read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert destination.read_bytes() == expected


def _is_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _remove_windows_link(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if _is_reparse(metadata) or stat.S_ISDIR(metadata.st_mode):
        os.rmdir(path)
    else:
        path.unlink()


def _assert_real_junction(path: Path) -> None:
    metadata = path.lstat()
    assert _is_reparse(metadata)
    assert getattr(metadata, "st_reparse_tag", None) == getattr(
        stat,
        "IO_REPARSE_TAG_MOUNT_POINT",
        getattr(metadata, "st_reparse_tag", None),
    )


def _create_windows_junction_or_skip(target: Path, link: Path) -> None:
    failures: list[str] = []
    try:
        import _winapi
    except ImportError as error:
        failures.append(f"_winapi.CreateJunction unavailable: {error!r}")
    else:
        try:
            _winapi.CreateJunction(str(target), str(link))
        except OSError as error:
            failures.append(f"_winapi.CreateJunction failed: {error!r}")
            _remove_windows_link(link)
        else:
            try:
                _assert_real_junction(link)
            except BaseException:
                _remove_windows_link(link)
                raise
            return

    try:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        failures.append(f"mklink /J unavailable: {error!r}")
        _remove_windows_link(link)
        pytest.skip("real Windows junction unavailable; " + "; ".join(failures))
    if completed.returncode != 0:
        failures.append(
            "mklink /J failed: "
            f"returncode={completed.returncode}, "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        )
        _remove_windows_link(link)
        pytest.skip("real Windows junction unavailable; " + "; ".join(failures))
    try:
        _assert_real_junction(link)
    except BaseException:
        _remove_windows_link(link)
        raise


def _mutate_terminal(
    repository: Path,
    input_key: str,
    mutation: str,
    tmp_path: Path,
) -> Callable[[], None]:
    relative = _identity_path(input_key)
    target = repository.joinpath(*relative.split("/"))
    raw = target.read_bytes()
    if mutation == "delete":
        target.unlink()
    elif mutation == "append":
        target.write_bytes(raw + b"X")
    elif mutation == "remove":
        assert raw
        target.write_bytes(raw[:-1])
    elif mutation == "flip":
        changed = bytearray(raw)
        changed[len(changed) // 2] ^= 1
        target.write_bytes(changed)
        assert target.stat().st_size == len(raw)
    elif mutation == "directory":
        target.unlink()
        target.mkdir()
    elif mutation in ("junction-present", "junction-dangling"):
        if os.name != "nt":
            pytest.skip("real Windows junction contract")
        target.unlink()
        junction_target = tmp_path / f"terminal-target-{input_key}-{mutation}"
        junction_target.mkdir()
        _create_windows_junction_or_skip(junction_target, target)
        if mutation == "junction-dangling":
            shutil.rmtree(junction_target)
        return lambda: _remove_windows_link(target)
    else:
        raise AssertionError(f"unknown terminal mutation: {mutation}")
    return lambda: None


def _mutate_ancestor(
    repository: Path,
    input_key: str,
    mutation: str,
    tmp_path: Path,
) -> Callable[[], None]:
    relative = _identity_path(input_key)
    parts = relative.split("/")
    ancestor = repository.joinpath(*parts[:-1])
    if mutation == "delete":
        shutil.rmtree(ancestor)
        return lambda: None
    if mutation not in ("junction-present", "junction-dangling"):
        raise AssertionError(f"unknown ancestor mutation: {mutation}")
    if os.name != "nt":
        pytest.skip("real Windows junction contract")
    junction_target = tmp_path / f"ancestor-target-{input_key}-{mutation}"
    ancestor.rename(junction_target)
    _create_windows_junction_or_skip(junction_target, ancestor)
    if mutation == "junction-dangling":
        shutil.rmtree(junction_target)
    return lambda: _remove_windows_link(ancestor)


@pytest.mark.parametrize("input_key", _INPUT_KEYS)
@pytest.mark.parametrize(
    ("scope", "mutation", "expected_code"),
    _RAW_IDENTITY_CASES,
)
def test_raw_input_identity_precedes_semantics(
    repository_root: Path,
    tmp_path: Path,
    input_key: str,
    scope: str,
    mutation: str,
    expected_code: str,
) -> None:
    repository = tmp_path / "repository"
    _copy_frozen_inputs(repository_root, repository)
    if scope == "terminal":
        cleanup = _mutate_terminal(repository, input_key, mutation, tmp_path)
    else:
        cleanup = _mutate_ancestor(repository, input_key, mutation, tmp_path)
    try:
        with pytest.raises(FixtureInputError) as captured:
            load_frozen_inputs(repository)
        assert captured.value.code == expected_code
        if scope == "terminal":
            assert captured.value.source == _identity_path(input_key)
    finally:
        cleanup()


@pytest.mark.parametrize(
    ("late_mutation", "expected_code"),
    [
        pytest.param("delete", "frozen_input_missing", id="late-missing"),
        pytest.param(
            "directory",
            "repo_path_not_regular_file",
            id="late-not-regular",
        ),
        pytest.param("junction-present", "repo_path_reparse", id="late-reparse"),
    ],
)
def test_all_path_type_gates_precede_any_size_hash_gate(
    repository_root: Path,
    tmp_path: Path,
    late_mutation: str,
    expected_code: str,
) -> None:
    repository = tmp_path / "repository"
    _copy_frozen_inputs(repository_root, repository)
    early = repository.joinpath(*_identity_path("stage0b_manifest").split("/"))
    early.write_bytes(early.read_bytes() + b"X")
    cleanup = _mutate_terminal(repository, "adr_004", late_mutation, tmp_path)
    try:
        with pytest.raises(FixtureInputError) as captured:
            load_frozen_inputs(repository)
        assert captured.value.code == expected_code
    finally:
        cleanup()


def _load_current_parsed(repository_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = _identity_path("stage0b_manifest")
    report_path = _identity_path("stage0b_report")
    manifest = load_strict_json_bytes(
        read_repo_regular_file(repository_root, manifest_path),
        source=manifest_path,
    )
    report = load_strict_json_bytes(
        read_repo_regular_file(repository_root, report_path),
        source=report_path,
    )
    assert type(manifest) is dict
    assert type(report) is dict
    return manifest, report


def _rows(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = container[key]
    assert type(rows) is list
    assert all(type(row) is dict for row in rows)
    return rows


def _remove_kind(row: dict[str, Any], field: str, kind: str) -> None:
    kinds = row[field]
    assert type(kinds) is list
    assert kind in kinds
    kinds.remove(kind)


def _apply_semantic_mutation(
    mutation: str,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> None:
    sources = _rows(manifest, "sources")
    clauses = _rows(manifest, "clauses")
    if mutation == "manifest-schema":
        manifest["schema_version"] = "0.2"
    elif mutation == "report-schema":
        report["schema_version"] = "0.2"
    elif mutation == "manifest-source-count":
        manifest["source_count"] = 213
    elif mutation == "report-reviewed-sources":
        report["reviewed_sources"] = 213
    elif mutation == "source-list-length":
        sources.pop()
    elif mutation == "manifest-clause-count":
        manifest["clause_count"] = 258
    elif mutation == "report-clause-count":
        report["clause_count"] = 258
    elif mutation == "clause-list-length":
        clauses.pop()
    elif mutation == "s-source-count":
        row = next(row for row in sources if "S" in row["assigned_oracle_kinds"])
        _remove_kind(row, "assigned_oracle_kinds", "S")
    elif mutation == "s-clause-count":
        row = next(row for row in clauses if "S" in row["required_oracle_kinds"])
        _remove_kind(row, "required_oracle_kinds", "S")
    elif mutation == "h-or-j-clause-count":
        row = next(
            row
            for row in clauses
            if row["required_oracle_kinds"] == ["D", "H"]
        )
        _remove_kind(row, "required_oracle_kinds", "H")
    elif mutation == "h-or-j-requirement-count":
        row = next(
            row
            for row in clauses
            if row["required_oracle_kinds"] == ["H", "J"]
        )
        _remove_kind(row, "required_oracle_kinds", "J")
    elif mutation == "replace-source-id":
        sources[0]["source_id"] = "STAGE0C-REPLACED-SOURCE"
    elif mutation == "duplicate-source-id":
        sources[0]["source_id"] = sources[1]["source_id"]
    elif mutation == "replace-clause-id":
        clauses[0]["clause_id"] = "STAGE0C-REPLACED-CLAUSE#1"
    elif mutation == "duplicate-clause-id":
        clauses[0]["clause_id"] = clauses[1]["clause_id"]
    elif mutation == "clause-source-group":
        clauses[0]["source_group"] = "stage0c-mismatch"
    elif mutation == "clause-source-id":
        clauses[0]["source_id"] = "STAGE0C-MISSING-SOURCE"
    elif mutation == "clause-binding":
        clauses[0]["source_binding_sha256"] = "0" * 64
    elif mutation == "clause-decision":
        clauses[0]["decision_sha256"] = "0" * 64
    elif mutation == "ready-false":
        report["source_adjudication_ready"] = False
    elif mutation == "pending-atomicity-one":
        report["pending_atomicity_reviews"] = 1
    elif mutation == "pending-oracle-one":
        report["pending_oracle_assignments"] = 1
    elif mutation == "pending-atomicity-bool":
        report["pending_atomicity_reviews"] = False
    elif mutation == "pending-oracle-bool":
        report["pending_oracle_assignments"] = False
    elif mutation == "report-manifest-sha":
        report["source_clause_manifest_sha256"] = "0" * 64
    else:
        raise AssertionError(f"unknown semantic mutation: {mutation}")


_SEMANTIC_CASES = [
    ("manifest-schema", "frozen_schema_version_mismatch"),
    ("report-schema", "frozen_schema_version_mismatch"),
    ("manifest-source-count", "frozen_source_count_mismatch"),
    ("report-reviewed-sources", "frozen_source_count_mismatch"),
    ("source-list-length", "frozen_source_count_mismatch"),
    ("manifest-clause-count", "frozen_clause_count_mismatch"),
    ("report-clause-count", "frozen_clause_count_mismatch"),
    ("clause-list-length", "frozen_clause_count_mismatch"),
    ("s-source-count", "frozen_s_source_count_mismatch"),
    ("s-clause-count", "frozen_s_clause_count_mismatch"),
    ("h-or-j-clause-count", "frozen_h_or_j_clause_count_mismatch"),
    ("h-or-j-requirement-count", "frozen_h_or_j_requirement_count_mismatch"),
    ("replace-source-id", "frozen_source_set_mismatch"),
    ("duplicate-source-id", "frozen_source_set_mismatch"),
    ("replace-clause-id", "frozen_clause_set_mismatch"),
    ("duplicate-clause-id", "frozen_clause_set_mismatch"),
    ("clause-source-group", "frozen_clause_source_join_mismatch"),
    ("clause-source-id", "frozen_clause_source_join_mismatch"),
    ("clause-binding", "frozen_clause_source_join_mismatch"),
    ("clause-decision", "frozen_clause_source_join_mismatch"),
    ("ready-false", "stage0b_not_ready"),
    ("pending-atomicity-one", "stage0b_not_ready"),
    ("pending-oracle-one", "stage0b_not_ready"),
    ("pending-atomicity-bool", "stage0b_not_ready"),
    ("pending-oracle-bool", "stage0b_not_ready"),
    ("report-manifest-sha", "frozen_report_manifest_identity_mismatch"),
]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    _SEMANTIC_CASES,
    ids=[mutation for mutation, _code in _SEMANTIC_CASES],
)
def test_pure_semantic_mutations_have_reachable_codes(
    repository_root: Path,
    mutation: str,
    expected_code: str,
) -> None:
    current_manifest, current_report = _load_current_parsed(repository_root)
    manifest = copy.deepcopy(current_manifest)
    report = copy.deepcopy(current_report)
    _apply_semantic_mutation(mutation, manifest, report)
    with pytest.raises(FixtureInputError) as captured:
        validate_frozen_semantics(manifest, report)
    assert captured.value.code == expected_code


def test_oracle_count_gate_precedes_exact_id_set_gate(repository_root: Path) -> None:
    current_manifest, current_report = _load_current_parsed(repository_root)
    manifest = copy.deepcopy(current_manifest)
    report = copy.deepcopy(current_report)
    _apply_semantic_mutation("s-source-count", manifest, report)
    _apply_semantic_mutation("replace-source-id", manifest, report)
    with pytest.raises(FixtureInputError) as captured:
        validate_frozen_semantics(manifest, report)
    assert captured.value.code == "frozen_s_source_count_mismatch"


def test_canonical_id_set_hashes_match_frozen_constants(
    repository_root: Path,
) -> None:
    manifest, _report = _load_current_parsed(repository_root)
    source_ids = [row["source_id"] for row in _rows(manifest, "sources")]
    clause_ids = [row["clause_id"] for row in _rows(manifest, "clauses")]
    assert canonical_id_set_sha256(source_ids) == EXPECTED_SOURCE_ID_SET_SHA256
    assert canonical_id_set_sha256(clause_ids) == EXPECTED_CLAUSE_ID_SET_SHA256
    assert (
        canonical_id_set_sha256(reversed(source_ids))
        == EXPECTED_SOURCE_ID_SET_SHA256
    )
    assert (
        canonical_id_set_sha256(reversed(clause_ids))
        == EXPECTED_CLAUSE_ID_SET_SHA256
    )


def test_canonical_id_set_rejects_direct_duplicate() -> None:
    with pytest.raises(FixtureInputError) as captured:
        canonical_id_set_sha256(["ID-1", "ID-1"])
    assert captured.value.code == "frozen_id_duplicate"


def test_load_builds_frozen_indices_and_raw_hashes(repository_root: Path) -> None:
    frozen = load_frozen_inputs(repository_root)
    assert len(frozen.sources_by_id) == EXPECTED_SOURCE_COUNT
    assert len(frozen.clauses_by_id) == EXPECTED_CLAUSE_COUNT
    assert set(frozen.sources_by_id) == {
        row["source_id"] for row in _rows(frozen.manifest, "sources")
    }
    assert set(frozen.clauses_by_id) == {
        row["clause_id"] for row in _rows(frozen.manifest, "clauses")
    }
    for row in _rows(frozen.manifest, "sources"):
        assert frozen.sources_by_id[row["source_id"]] == row
    for row in _rows(frozen.manifest, "clauses"):
        assert frozen.clauses_by_id[row["clause_id"]] == row
    assert frozen.raw_sha256_by_key == {
        key: _identity_sha256(key) for key in _INPUT_KEYS
    }


def test_load_rereads_all_inputs_without_object_reuse(
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_calls: list[str] = []
    original_read = fixture_io.read_repo_regular_file

    def recording_read(root: Path, repo_relative_posix: str) -> bytes:
        read_calls.append(repo_relative_posix)
        return original_read(root, repo_relative_posix)

    monkeypatch.setattr(fixture_io, "read_repo_regular_file", recording_read)
    first = load_frozen_inputs(repository_root)
    second = load_frozen_inputs(repository_root)
    expected_read_order = [_identity_path(key) for key in _INPUT_KEYS]
    assert read_calls == expected_read_order * 2
    assert first is not second
    assert first.manifest is not second.manifest
    assert first.report is not second.report
    assert first.manifest == second.manifest
    assert first.report == second.report
    for key in _INPUT_KEYS:
        relative = _identity_path(key)
        raw = read_repo_regular_file(repository_root, relative)
        assert len(raw) == _identity_size(key)
        assert sha256_upper(raw) == _identity_sha256(key)
        assert second.raw_sha256_by_key[key] == _identity_sha256(key)


def test_frozen_inputs_is_shallow_frozen() -> None:
    manifest: dict[str, Any] = {}
    carrier = FrozenInputs(
        manifest=manifest,
        report={},
        clauses_by_id={},
        sources_by_id={},
        raw_sha256_by_key={},
    )
    with pytest.raises(FrozenInstanceError):
        carrier.manifest = {}
    manifest["inner_mutation"] = True
    assert carrier.manifest["inner_mutation"] is True
