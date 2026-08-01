import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tools.stage0c_fixtures.compiler import (
    STAGE0C_REPORT_V0_1,
    build_generated_artifacts,
    compile_binding_manifest,
    compile_case_file,
    compile_stage0c_report,
    validate_stage0c_report,
)
from tools.stage0c_fixtures.constants import INPUT_IDENTITIES, SCHEMA_VERSION
from tools.stage0c_fixtures.io import canonical_bytes, sha256_upper, tree_entries
from tools.stage0c_fixtures.reviewed import REVIEWED_EXACT_FIELDS
from tools.stage0c_fixtures.types import FixtureInputError, ValidationIssue


_FROZEN_FIELDS = (
    "clause_id",
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
)
_BINDING_FIELDS = {
    "stage0b_manifest_sha256",
    *_FROZEN_FIELDS,
    "case_sha256",
    "stimulus_mapping",
    "assertion_or_rubric_mapping",
    "reviewer",
    "rationale",
}
_TOP_LEVEL_ARTIFACTS = {
    "conversion_checklist_v0_1.json",
    "fixture_case_schema_v0_1.json",
    "sandbox_handler_manifest_v0_1.json",
    "harness_smoke_test_matrix_v0_1.json",
    "case_binding_manifest_v0_1.json",
    "stage0c_report_v0_1.json",
}
_BOOLEAN_REPORT_FIELDS = (
    "fixture_dsl_contract_ready",
    "clause_to_case_binding_complete",
    "case_definition_coverage_complete",
    "trusted_fixture_harness_contract_ready",
    "trusted_fixture_harness_smoke_verified",
    "s_case_execution_complete",
    "case_execution_complete",
    "core_behavior_verified",
    "case_coverage_complete",
    "core_case_execution_coverage_complete",
    "catalog_ready",
    "release_ready",
)
_COUNT_REPORT_FIELDS = (
    "source_count",
    "clause_count",
    "case_count",
    "s_clause_count",
    "pending_h_or_j_clause_count",
    "pending_h_or_j_oracle_requirement_count",
)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest().upper()


def _setup_step(replay_key: str) -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "seed-backend",
        "handler_id": "sandbox.seed_backend_response",
        "params": {
            "replay_key": replay_key,
            "output": {"status": "fixture-output", "sequence": 1},
        },
    }


def _stimulus_step(replay_key: str) -> dict[str, Any]:
    return {
        "sequence": 1,
        "step_id": "replay-backend",
        "handler_id": "backend.replay",
        "params": {"replay_key": replay_key, "input": {}},
    }


def _machine_assertion() -> dict[str, Any]:
    return {
        "sequence": 1,
        "assertion_id": "assert-status",
        "handler_id": "receipt.status",
        "step_id": "replay-backend",
        "params": {"expected": "completed"},
    }


def _rubric(kind: str) -> dict[str, Any]:
    return {
        "criterion_id": f"criterion-{kind.lower()}",
        "oracle_kind": kind,
        "question": f"Does the fixture provide {kind} evidence?",
        "evidence_case_json_pointers": [
            "/stimulus_steps/0/params",
            "/stimulus_steps/0/step_id",
        ],
        "allowed_scores": [-1, 0, 1],
        "passing_scores": [1],
    }


def _sandbox_profile() -> dict[str, Any]:
    return {
        "profile_id": "sandbox-stage0c",
        "allowed_effects": [],
        "fixed_clock": "2026-01-01T00:00:00Z",
        "id_seed": "stage0c-seed",
        "reset_policy": "fresh_context",
        "cleanup_policy": "always",
    }


def _case_body(
    clause_id: str,
    source_id: str,
    oracle_kinds: list[str],
) -> dict[str, Any]:
    replay_key = f"replay-{clause_id.lower().replace('#', '-')}"
    machine = bool(set(oracle_kinds) & {"D", "S"})
    human = [kind for kind in oracle_kinds if kind in {"H", "J"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": f"case-{clause_id.lower().replace('#', '-')}",
        "source_id": source_id,
        "source_clause_id": clause_id,
        "oracle_kinds": list(oracle_kinds),
        "setup_steps": [_setup_step(replay_key)],
        "stimulus_steps": [_stimulus_step(replay_key)],
        "machine_assertions": [_machine_assertion()] if machine else [],
        "rubric_requirements": [_rubric(kind) for kind in human],
        "sandbox_profile": _sandbox_profile() if "S" in oracle_kinds else None,
    }


def _frozen_clause(
    clause_id: str,
    source_id: str,
    oracle_kinds: list[str],
) -> dict[str, Any]:
    return {
        "clause_id": clause_id,
        "source_id": source_id,
        "source_group": "synthetic",
        "source_binding_sha256": _hash(f"binding:{source_id}"),
        "decision_sha256": _hash(f"decision:{source_id}"),
        "clause_stimulus_sha256": _hash(f"stimulus:{clause_id}"),
        "clause_expected_sha256": _hash(f"expected:{clause_id}"),
        "clause_content_sha256": _hash(f"content:{clause_id}"),
        "required_oracle_kinds": list(oracle_kinds),
    }


def _reviewed(frozen: dict[str, Any]) -> dict[str, Any]:
    clause_id = frozen["clause_id"]
    source_id = frozen["source_id"]
    oracle_kinds = list(frozen["required_oracle_kinds"])
    mappings: list[dict[str, Any]] = []
    rubric_index = 0
    for kind in oracle_kinds:
        if kind in {"D", "S"}:
            pointer = "/machine_assertions/0"
        else:
            pointer = f"/rubric_requirements/{rubric_index}"
            rubric_index += 1
        mappings.append(
            {
                "oracle_kind": kind,
                "case_json_pointers": [pointer],
                "mapping_note": f"{kind} evidence maps to the final case body.",
            }
        )
    row = {
        "schema_version": SCHEMA_VERSION,
        "stage0b_manifest_sha256": INPUT_IDENTITIES["stage0b_manifest"][
            "sha256"
        ],
        **{
            field: copy.deepcopy(frozen[field])
            for field in _FROZEN_FIELDS
        },
        "case_body": _case_body(clause_id, source_id, oracle_kinds),
        "stimulus_mapping": {
            "case_json_pointers": [
                "/stimulus_steps/0/handler_id",
                "/stimulus_steps/0/params",
            ],
            "mapping_note": "The concrete handler and parameters carry the stimulus.",
        },
        "assertion_or_rubric_mapping": mappings,
        "reviewer": {
            "role": "conversion_reviewer",
            "reviewer_id": "synthetic-reviewer",
            "reviewed_at": "2026-07-29",
        },
        "rationale": "The reviewed case preserves the frozen synthetic clause.",
    }
    assert set(row) == set(REVIEWED_EXACT_FIELDS)
    return row


def _checklist_row(row: dict[str, Any], ordinal: int) -> dict[str, Any]:
    case_id = row["case_body"]["case_id"]
    return {
        "ordinal": ordinal,
        "batch_id": f"B{((ordinal - 1) // 20) + 1:02d}",
        "batch_ordinal": ((ordinal - 1) % 20) + 1,
        "case_id": case_id,
        "reviewed_path": f"fixtures/stage0c/reviewed/cases/{case_id}.json",
        "generated_path": f"cases/{case_id}.json",
        **{field: copy.deepcopy(row[field]) for field in _FROZEN_FIELDS},
    }


def _checklist(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage0b_manifest_sha256": INPUT_IDENTITIES["stage0b_manifest"][
            "sha256"
        ],
        "source_count": len({row["source_id"] for row in rows}),
        "clause_count": len(rows),
        "batch_count": (len(rows) + 19) // 20,
        "cases": [
            _checklist_row(row, ordinal)
            for ordinal, row in enumerate(rows, start=1)
        ],
    }


def _two_clause_fixture() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    d_row = _reviewed(_frozen_clause("SYN-D#1", "SYN-D", ["D"]))
    hj_row = _reviewed(_frozen_clause("SYN-HJ#1", "SYN-HJ", ["H", "J"]))
    rows = [hj_row, d_row]
    return rows, _checklist(rows)


def _counterfeit_production_rows() -> list[dict[str, Any]]:
    identities = [
        (f"SYN-{source_number:04d}", clause_number)
        for source_number in range(1, 215)
        for clause_number in (1, 2)
        if clause_number == 1 or source_number <= 45
    ]
    assert len(identities) == 259
    rows = []
    for index, (source_id, clause_number) in enumerate(identities):
        if index < 4:
            oracle_kinds = ["S", "H", "J"]
        elif index < 51:
            oracle_kinds = ["S", "H"]
        elif index < 98:
            oracle_kinds = ["S"]
        else:
            oracle_kinds = ["D"]
        clause_id = f"{source_id}#{clause_number}"
        rows.append(
            _reviewed(_frozen_clause(clause_id, source_id, oracle_kinds))
        )
    return rows


def _counterfeit_production_fixture() -> tuple[
    list[dict[str, Any]], dict[str, Any]
]:
    rows = _counterfeit_production_rows()
    return rows, _checklist(rows)


def _production_fixture(
    frozen_inputs: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [
        _reviewed(frozen_clause)
        for frozen_clause in frozen_inputs.clauses_by_id.values()
    ]
    checklist = _checklist(rows)
    assert checklist["source_count"] == 214
    assert checklist["clause_count"] == 259
    assert checklist["batch_count"] == 13
    assert [row["case_id"] for row in checklist["cases"]] == sorted(
        row["case_id"] for row in checklist["cases"]
    )
    return rows, checklist


def _issue_codes(issues: list[ValidationIssue]) -> list[str]:
    return [issue.code for issue in issues]


def _replace_oracle_kinds(
    row: dict[str, Any],
    checklist_row: dict[str, Any],
    oracle_kinds: list[str],
) -> None:
    frozen = {
        field: copy.deepcopy(row[field])
        for field in _FROZEN_FIELDS
    }
    frozen["required_oracle_kinds"] = list(oracle_kinds)
    row.clear()
    row.update(_reviewed(frozen))
    checklist_row["required_oracle_kinds"] = list(oracle_kinds)


def _all_keys(value: Any) -> set[str]:
    if type(value) is dict:
        return set(value).union(
            *( _all_keys(item) for item in value.values() )
        )
    if type(value) is list:
        return set().union(*( _all_keys(item) for item in value ))
    return set()


def test_two_clause_case_bytes_hash_and_binding_are_exact_and_sorted() -> None:
    rows, checklist = _two_clause_fixture()
    inputs_before = copy.deepcopy((rows, checklist))

    expected_case_rows = sorted(rows, key=lambda row: row["case_body"]["case_id"])
    for row in expected_case_rows:
        path, data = compile_case_file(row)
        case_id = row["case_body"]["case_id"]
        assert path == f"cases/{case_id}.json"
        assert data == canonical_bytes(row["case_body"])

    manifest = compile_binding_manifest(rows, checklist)
    # The carrier has a minimal local shape; only each 15-field record is Frozen.
    assert set(manifest) == {"schema_version", "bindings"}
    assert manifest["schema_version"] == SCHEMA_VERSION
    bindings = manifest["bindings"]
    assert type(bindings) is list
    assert [binding["clause_id"] for binding in bindings] == [
        row["clause_id"] for row in expected_case_rows
    ]

    reviewed_by_clause = {row["clause_id"]: row for row in rows}
    for binding in bindings:
        reviewed = reviewed_by_clause[binding["clause_id"]]
        assert set(binding) == _BINDING_FIELDS
        for field in (
            "stage0b_manifest_sha256",
            *_FROZEN_FIELDS,
            "stimulus_mapping",
            "assertion_or_rubric_mapping",
            "reviewer",
            "rationale",
        ):
            assert binding[field] == reviewed[field]
        assert binding["case_sha256"] == sha256_upper(
            canonical_bytes(reviewed["case_body"])
        )

    hj_binding = next(
        binding for binding in bindings if binding["required_oracle_kinds"] == ["H", "J"]
    )
    assert [
        mapping["oracle_kind"]
        for mapping in hj_binding["assertion_or_rubric_mapping"]
    ] == ["H", "J"]
    assert "verdict" not in _all_keys(hj_binding)
    assert (rows, checklist) == inputs_before

    manifest_before = copy.deepcopy(manifest)
    rows[0]["stimulus_mapping"]["mapping_note"] = "mutated input"
    assert manifest == manifest_before

    rows_before = copy.deepcopy(rows)
    manifest["bindings"][0]["stimulus_mapping"][
        "mapping_note"
    ] = "mutated output"
    assert rows == rows_before


def test_binding_manifest_rejects_an_incomplete_exact_set() -> None:
    rows, checklist = _two_clause_fixture()
    with pytest.raises(FixtureInputError):
        compile_binding_manifest(rows[:-1], checklist)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        (
            lambda checklist: checklist.__setitem__("extra", None),
            "compiler_checklist_exact_fields_invalid",
        ),
        (
            lambda checklist: checklist.__delitem__("batch_count"),
            "compiler_checklist_exact_fields_invalid",
        ),
        (
            lambda checklist: checklist["cases"][0].__setitem__(
                "extra", None
            ),
            "compiler_checklist_row_exact_fields_invalid",
        ),
        (
            lambda checklist: checklist["cases"][0].__delitem__(
                "reviewed_path"
            ),
            "compiler_checklist_row_exact_fields_invalid",
        ),
        (
            lambda checklist: checklist.__setitem__(
                "clause_count", "2"
            ),
            "compiler_checklist_count_invalid",
        ),
        (
            lambda checklist: checklist["cases"][0].__setitem__(
                "ordinal", True
            ),
            "compiler_checklist_order_invalid",
        ),
        (
            lambda checklist: checklist["cases"][0].__setitem__(
                "batch_ordinal", True
            ),
            "compiler_checklist_order_invalid",
        ),
    ),
    ids=(
        "top-extra",
        "top-missing",
        "row-extra",
        "row-missing",
        "string-count",
        "bool-ordinal",
        "bool-batch-ordinal",
    ),
)
def test_checklist_structure_and_integer_types_fail_stably(
    mutation: Callable[[dict[str, Any]], None],
    expected_code: str,
) -> None:
    rows, checklist = _two_clause_fixture()
    mutation(checklist)
    with pytest.raises(FixtureInputError) as captured:
        compile_binding_manifest(rows, checklist)
    assert captured.value.code == expected_code


def test_stage0c_report_requires_actual_production_closure_and_counts(
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    report = compile_stage0c_report(rows, checklist)
    assert set(report) == set(STAGE0C_REPORT_V0_1)
    assert report == STAGE0C_REPORT_V0_1
    assert canonical_bytes(report) == canonical_bytes(STAGE0C_REPORT_V0_1)
    assert validate_stage0c_report(report) == []

    broken_inputs: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    broken_inputs.append((copy.deepcopy(rows[:-1]), copy.deepcopy(checklist)))

    source_rows = copy.deepcopy(rows)
    source_checklist = copy.deepcopy(checklist)
    source_rows[-1]["source_id"] = source_rows[-2]["source_id"]
    source_rows[-1]["case_body"]["source_id"] = source_rows[-2]["source_id"]
    source_checklist["cases"][-1]["source_id"] = source_rows[-2]["source_id"]
    broken_inputs.append((source_rows, source_checklist))

    s_rows = copy.deepcopy(rows)
    s_checklist = copy.deepcopy(checklist)
    s_index = next(
        index
        for index, row in enumerate(s_rows)
        if "S" in row["required_oracle_kinds"]
        and not set(row["required_oracle_kinds"]).intersection({"H", "J"})
    )
    without_s = [
        kind
        for kind in s_rows[s_index]["required_oracle_kinds"]
        if kind != "S"
    ] or ["D"]
    _replace_oracle_kinds(
        s_rows[s_index],
        s_checklist["cases"][s_index],
        without_s,
    )
    broken_inputs.append((s_rows, s_checklist))

    hj_clause_rows = copy.deepcopy(rows)
    hj_clause_checklist = copy.deepcopy(checklist)
    hj_clause_index = next(
        index
        for index, row in enumerate(hj_clause_rows)
        if set(row["required_oracle_kinds"]).intersection({"H", "J"})
    )
    remaining_machine_kinds = [
        kind
        for kind in hj_clause_rows[hj_clause_index]["required_oracle_kinds"]
        if kind in {"D", "S"}
    ] or ["D"]
    _replace_oracle_kinds(
        hj_clause_rows[hj_clause_index],
        hj_clause_checklist["cases"][hj_clause_index],
        remaining_machine_kinds,
    )
    broken_inputs.append((hj_clause_rows, hj_clause_checklist))

    hj_requirement_rows = copy.deepcopy(rows)
    hj_requirement_checklist = copy.deepcopy(checklist)
    hj_requirement_index = next(
        index
        for index, row in enumerate(hj_requirement_rows)
        if {"H", "J"}.issubset(row["required_oracle_kinds"])
    )
    without_j = [
        kind
        for kind in hj_requirement_rows[hj_requirement_index][
            "required_oracle_kinds"
        ]
        if kind != "J"
    ]
    _replace_oracle_kinds(
        hj_requirement_rows[hj_requirement_index],
        hj_requirement_checklist["cases"][hj_requirement_index],
        without_j,
    )
    broken_inputs.append((hj_requirement_rows, hj_requirement_checklist))

    for broken_rows, broken_checklist in broken_inputs:
        with pytest.raises(FixtureInputError):
            compile_stage0c_report(broken_rows, broken_checklist)


def test_stage0c_report_rejects_count_correct_counterfeit_id_sets() -> None:
    rows, checklist = _counterfeit_production_fixture()
    with pytest.raises(FixtureInputError) as captured:
        compile_stage0c_report(rows, checklist)
    assert captured.value.code == "stage0c_report_gate_failed"


def test_stage0c_report_rejects_non_unicode_sorted_checklist(
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    checklist["cases"][0], checklist["cases"][1] = (
        checklist["cases"][1],
        checklist["cases"][0],
    )
    for ordinal, checklist_row in enumerate(checklist["cases"], start=1):
        checklist_row["ordinal"] = ordinal
        checklist_row["batch_id"] = f"B{((ordinal - 1) // 20) + 1:02d}"
        checklist_row["batch_ordinal"] = ((ordinal - 1) % 20) + 1

    with pytest.raises(FixtureInputError) as captured:
        compile_stage0c_report(rows, checklist)
    assert captured.value.code == "stage0c_report_gate_failed"


def test_stage0c_report_rebuild_uses_private_literal_authority(
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    frozen_public_value = copy.deepcopy(STAGE0C_REPORT_V0_1)

    first = compile_stage0c_report(rows, checklist)
    first["source_count"] = 0
    assert compile_stage0c_report(rows, checklist) == frozen_public_value

    try:
        STAGE0C_REPORT_V0_1["source_count"] = 0
        assert compile_stage0c_report(rows, checklist) == frozen_public_value
    finally:
        STAGE0C_REPORT_V0_1.clear()
        STAGE0C_REPORT_V0_1.update(frozen_public_value)


def test_stage0c_report_validator_freezes_every_literal_byte() -> None:
    assert type(STAGE0C_REPORT_V0_1) is dict
    expected_issue = ["stage0c_report_literal_mismatch"]

    for field in _BOOLEAN_REPORT_FIELDS:
        mutated = copy.deepcopy(STAGE0C_REPORT_V0_1)
        mutated[field] = not mutated[field]
        assert _issue_codes(validate_stage0c_report(mutated)) == expected_issue

        bool_as_integer = copy.deepcopy(STAGE0C_REPORT_V0_1)
        bool_as_integer[field] = int(bool_as_integer[field])
        assert bool_as_integer == STAGE0C_REPORT_V0_1
        assert (
            _issue_codes(validate_stage0c_report(bool_as_integer))
            == expected_issue
        )

    for field in _COUNT_REPORT_FIELDS:
        for delta in (-1, 1):
            mutated = copy.deepcopy(STAGE0C_REPORT_V0_1)
            mutated[field] += delta
            assert _issue_codes(validate_stage0c_report(mutated)) == expected_issue

    for field in STAGE0C_REPORT_V0_1:
        mutated = copy.deepcopy(STAGE0C_REPORT_V0_1)
        del mutated[field]
        assert _issue_codes(validate_stage0c_report(mutated)) == expected_issue

    mutated = copy.deepcopy(STAGE0C_REPORT_V0_1)
    mutated["extra"] = None
    assert _issue_codes(validate_stage0c_report(mutated)) == expected_issue

    type_trap = copy.deepcopy(STAGE0C_REPORT_V0_1)
    type_trap["trusted_fixture_harness_smoke_verified"] = 0
    assert type_trap == STAGE0C_REPORT_V0_1
    assert _issue_codes(validate_stage0c_report(type_trap)) == expected_issue


def test_build_generated_artifacts_is_pure_and_survives_recursive_reread(
    tmp_path: Path,
    fixture_schema: dict[str, Any],
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    handler_manifest = {
        "schema_version": SCHEMA_VERSION,
        "registry_sha256": _hash("synthetic-registry"),
        "handlers": [],
    }
    smoke_matrix = {
        "schema_version": SCHEMA_VERSION,
        "handler_probes": [],
        "scenarios": [],
        "publication_probes": [],
    }
    inputs_before = copy.deepcopy(
        (checklist, fixture_schema, handler_manifest, smoke_matrix, rows)
    )
    generated_root = tmp_path / "generated"
    assert not generated_root.exists()

    artifacts = build_generated_artifacts(
        checklist=checklist,
        schema=fixture_schema,
        handler_manifest=handler_manifest,
        smoke_matrix=smoke_matrix,
        reviewed_rows=rows,
    )
    assert not generated_root.exists()
    assert len(artifacts) == 265
    expected_paths = _TOP_LEVEL_ARTIFACTS | {
        f"cases/{row['case_body']['case_id']}.json" for row in rows
    }
    assert set(artifacts) == expected_paths
    assert artifacts["conversion_checklist_v0_1.json"] == canonical_bytes(checklist)
    assert artifacts["fixture_case_schema_v0_1.json"] == canonical_bytes(
        fixture_schema
    )
    assert artifacts["sandbox_handler_manifest_v0_1.json"] == canonical_bytes(
        handler_manifest
    )
    assert artifacts["harness_smoke_test_matrix_v0_1.json"] == canonical_bytes(
        smoke_matrix
    )
    assert artifacts["stage0c_report_v0_1.json"] == canonical_bytes(
        STAGE0C_REPORT_V0_1
    )
    assert (
        checklist,
        fixture_schema,
        handler_manifest,
        smoke_matrix,
        rows,
    ) == inputs_before

    for relative, data in artifacts.items():
        destination = generated_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    expected_entries = [
        {"path": path, "size": len(data), "sha256": sha256_upper(data)}
        for path, data in sorted(artifacts.items())
    ]
    assert tree_entries(generated_root) == expected_entries
    assert {
        path.relative_to(generated_root).as_posix(): path.read_bytes()
        for path in generated_root.rglob("*")
        if path.is_file()
    } == artifacts


@pytest.mark.parametrize(
    "mutation",
    (
        lambda rows: rows[0].__setitem__(
            "source_binding_sha256", _hash("mutated-binding")
        ),
        lambda rows: rows[0].__setitem__(
            "assertion_or_rubric_mapping",
            rows[0]["assertion_or_rubric_mapping"][:-1],
        ),
    ),
    ids=("frozen-identity", "required-oracle-mapping"),
)
def test_build_failure_occurs_before_any_artifact_byte_is_written(
    tmp_path: Path,
    fixture_schema: dict[str, Any],
    frozen_inputs: Any,
    mutation: Callable[[list[dict[str, Any]]], None],
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    mutation(rows)
    target = tmp_path / "generated"

    def build_then_write() -> None:
        artifacts = build_generated_artifacts(
            checklist=checklist,
            schema=fixture_schema,
            handler_manifest={"schema_version": SCHEMA_VERSION},
            smoke_matrix={"schema_version": SCHEMA_VERSION},
            reviewed_rows=rows,
        )
        for relative, data in artifacts.items():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

    with pytest.raises(FixtureInputError):
        build_then_write()
    assert not target.exists()


def test_build_rejects_a_synchronized_frozen_identity_forgery(
    fixture_schema: dict[str, Any],
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    counterfeit = _hash("counterfeit-source-binding")
    rows[0]["source_binding_sha256"] = counterfeit
    checklist["cases"][0]["source_binding_sha256"] = counterfeit

    with pytest.raises(FixtureInputError) as captured:
        build_generated_artifacts(
            checklist=checklist,
            schema=fixture_schema,
            handler_manifest={"schema_version": SCHEMA_VERSION},
            smoke_matrix={"schema_version": SCHEMA_VERSION},
            reviewed_rows=rows,
        )
    assert captured.value.code == "compiler_checklist_authority_mismatch"


@pytest.mark.parametrize(
    "mutation",
    (
        lambda rows: rows[0].__setitem__("rationale", ""),
        lambda rows: rows[0]["stimulus_mapping"].__setitem__(
            "case_json_pointers",
            ["/stimulus_steps/0/handler_id"],
        ),
    ),
    ids=("empty-rationale", "incomplete-stimulus-pointer-coverage"),
)
def test_report_rejects_f08_invalid_reviewed_rows(
    frozen_inputs: Any,
    mutation: Callable[[list[dict[str, Any]]], None],
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    mutation(rows)

    with pytest.raises(FixtureInputError) as captured:
        compile_stage0c_report(rows, checklist)
    assert captured.value.code == "reviewed_validation_failed"


def test_build_rejects_a_caller_supplied_permissive_schema(
    frozen_inputs: Any,
) -> None:
    rows, checklist = _production_fixture(frozen_inputs)
    rows[0]["case_body"]["setup_steps"][0]["params"] = {}

    with pytest.raises(FixtureInputError) as captured:
        build_generated_artifacts(
            checklist=checklist,
            schema={},
            handler_manifest={"schema_version": SCHEMA_VERSION},
            smoke_matrix={"schema_version": SCHEMA_VERSION},
            reviewed_rows=rows,
        )
    assert captured.value.code == "compiler_schema_authority_mismatch"


def test_compiler_module_has_no_file_writing_api() -> None:
    source = Path(__file__).parents[2] / "tools/stage0c_fixtures/compiler.py"
    text = source.read_text(encoding="utf-8")
    forbidden = ("write_bytes(", "write_text(", "mkdir(", "open(")
    assert not any(token in text for token in forbidden)
    assert json.loads(canonical_bytes(STAGE0C_REPORT_V0_1)) == STAGE0C_REPORT_V0_1
