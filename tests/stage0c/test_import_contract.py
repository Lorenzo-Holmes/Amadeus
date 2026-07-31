import os
import stat
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from tools.stage0c_fixtures import SCHEMA_VERSION
from tools.stage0c_fixtures.constants import (
    EXPECTED_BATCH_COUNT,
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_GENERATED_FILE_COUNT,
    EXPECTED_S_CLAUSE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
    LOCK_PATH,
)
from tools.stage0c_fixtures.types import (
    FixtureInputError,
    PublicationError,
    PublicationProbeOutcome,
    PublicationProbeSpec,
    PublicationResult,
    RecoveryResult,
    Stage0CError,
    ValidationIssue,
)


def test_stage0c_import_and_constants_are_frozen() -> None:
    assert SCHEMA_VERSION == "0.1"
    assert EXPECTED_BATCH_COUNT == 13
    assert EXPECTED_CLAUSE_COUNT == 259
    assert EXPECTED_S_CLAUSE_COUNT == 98
    assert EXPECTED_GENERATED_FILE_COUNT == 265
    assert EXPECTED_SOURCE_ID_SET_SHA256 == (
        "9B771DEFE9BBD3F2025F32AB400ADE1AA4916223BE467B7EEF0135E9E3C4D39A"
    )
    assert EXPECTED_CLAUSE_ID_SET_SHA256 == (
        "0BD1579970C18D4BFB7A0F57AA53B8E30CB3DA5F50DB8F48240E16C634FD5CFC"
    )
    assert LOCK_PATH == "fixtures/stage0c/.stage0c-write.lock"
    assert INPUT_IDENTITIES == {
        "stage0b_manifest": {
            "path": "fixtures/stage0b/generated/source_clause_manifest_v0_1.json",
            "sha256": "DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C",
            "size": 252478,
        },
        "stage0b_report": {
            "path": "fixtures/stage0b/generated/stage0b_report_v0_1.json",
            "sha256": "F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8",
            "size": 585,
        },
        "core_contract": {
            "path": "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
            "sha256": "3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695",
            "size": 79488,
        },
        "adr_004": {
            "path": "outputs/ADR-004-Amadeus工具权限与执行治理.md",
            "sha256": "2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125",
            "size": 25191,
        },
    }


def _assert_empty_regular_non_reparse(path: Path) -> None:
    metadata = os.lstat(path)
    assert stat.S_ISREG(metadata.st_mode)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    assert (file_attributes & reparse_flag) == 0
    assert path.read_bytes() == b""


def test_lock_carrier_is_precreated_empty_regular_file() -> None:
    _assert_empty_regular_non_reparse(
        Path("fixtures/stage0c/.stage0c-write.lock")
    )


def test_stage0c_test_package_boundary_is_frozen() -> None:
    _assert_empty_regular_non_reparse(Path("tests/stage0c/__init__.py"))
    assert __package__ == "stage0c"


def test_shared_types_and_error_protocol_are_frozen() -> None:
    error = FixtureInputError(
        "json_non_utf8", source="fixture.json", detail="byte=0"
    )
    assert isinstance(error, Stage0CError)
    assert error.code == "json_non_utf8"
    assert error.source == "fixture.json"
    assert error.detail == "byte=0"
    assert error.args == ("json_non_utf8:fixture.json:byte=0",)
    issue = ValidationIssue(
        json_pointer="/reviewer",
        code="reviewer_missing",
        message="reviewer is required",
    )
    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"  # type: ignore[misc]
    result = PublicationResult(
        published=True,
        no_op=False,
        recovered=False,
        tree_sha256="A" * 64,
    )
    assert result.published and not result.no_op
    with pytest.raises(PublicationError, match="publication_result_invalid"):
        PublicationResult(
            published=True,
            no_op=True,
            recovered=False,
            tree_sha256="A" * 64,
        )
    spec = PublicationProbeSpec(
        case_id="publication-prepared-p-i-empty",
        journal_state="prepared",
        disk_shape="P,I,Ø",
        fault_point="none",
    )
    assert set(spec.to_json()) == {
        "case_id", "journal_state", "disk_shape", "fault_point"
    }
    outcome = PublicationProbeOutcome(
        attempt_count=1,
        executed=True,
        passed=True,
        terminal_tree_sha256="A" * 64,
        actual={"terminal": "I"},
    )
    assert outcome.executed and outcome.passed
    recovered_absent = RecoveryResult(
        terminal="absent",
        tree_sha256=None,
        changed=True,
    )
    assert recovered_absent.tree_sha256 is None
    with pytest.raises(PublicationError, match="recovery_result_invalid"):
        RecoveryResult(
            terminal="present",
            tree_sha256=None,
            changed=False,
        )


def test_publication_and_recovery_result_runtime_invariants_are_strict() -> None:
    publication_base = {
        "published": True,
        "no_op": False,
        "recovered": False,
        "tree_sha256": "A" * 64,
    }
    publication_mutations = (
        {"published": 1},
        {"no_op": 0},
        {"recovered": "false"},
        {"tree_sha256": "a" * 64},
        {"tree_sha256": "A" * 63},
    )
    for mutation in publication_mutations:
        with pytest.raises(PublicationError, match="publication_result_invalid"):
            PublicationResult(**(publication_base | mutation))  # type: ignore[arg-type]

    recovery_mutations = (
        {"terminal": "garbage", "tree_sha256": "A" * 64, "changed": False},
        {"terminal": "present", "tree_sha256": "A" * 64, "changed": 1},
        {"terminal": "present", "tree_sha256": "a" * 64, "changed": False},
        {"terminal": "present", "tree_sha256": "A" * 63, "changed": False},
        {"terminal": "absent", "tree_sha256": "A" * 64, "changed": False},
    )
    for mutation in recovery_mutations:
        with pytest.raises(PublicationError, match="recovery_result_invalid"):
            RecoveryResult(**mutation)  # type: ignore[arg-type]
