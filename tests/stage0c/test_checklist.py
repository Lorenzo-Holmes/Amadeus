import builtins
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from tools.stage0c_fixtures.checklist import (
    build_conversion_checklist,
    checklist_bytes,
)
from tools.stage0c_fixtures.types import FixtureInputError


_TOP_LEVEL_FIELDS = {
    "schema_version",
    "stage0b_manifest_sha256",
    "source_count",
    "clause_count",
    "batch_count",
    "cases",
}
_ROW_FIELDS = {
    "ordinal",
    "batch_id",
    "batch_ordinal",
    "case_id",
    "reviewed_path",
    "generated_path",
    "clause_id",
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
}
_FROZEN_ROW_FIELDS = (
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
_SOURCE_AUTHORITY_FIELDS = (
    "source_id",
    "source_group",
    "source_binding_sha256",
    "decision_sha256",
)
_CLAUSE_ONLY_FIELDS = (
    "clause_stimulus_sha256",
    "clause_expected_sha256",
    "clause_content_sha256",
    "required_oracle_kinds",
)
_STAGE0B_MANIFEST_SHA256 = (
    "DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C"
)
_ROW_15 = {
    "ordinal": 15,
    "batch_id": "B01",
    "batch_ordinal": 15,
    "case_id": "case-ac-013-1",
    "reviewed_path": (
        "fixtures/stage0c/reviewed/cases/case-ac-013-1.json"
    ),
    "generated_path": "cases/case-ac-013-1.json",
    "clause_id": "AC-013#1",
    "source_id": "AC-013",
    "source_group": "core",
    "source_binding_sha256": (
        "E133666BCAA65C6E3FECCE3DEE6AC69DB107A496471E2DE59E8FC9CA026EF61E"
    ),
    "decision_sha256": (
        "2F68504B4FCB86857243567FB8E860DFEF4145DF0A3284BA93F567DAA7497EA9"
    ),
    "clause_stimulus_sha256": (
        "8B3ABFDA4D767CB79DBD1BC712E7138B23FE1FB51D08F352665CDF61F2B20725"
    ),
    "clause_expected_sha256": (
        "1C3193E01C56CFC400A4AC40B20FCA18A9CF795018330DD7A2ECD921F8603AEB"
    ),
    "clause_content_sha256": (
        "83FD00A4C127064E697054466861CCD85C8F249D88EBEEBB117055DA1B0CF892"
    ),
    "required_oracle_kinds": ["D", "S"],
}


def _manifest_clauses(inputs: Any) -> list[dict[str, Any]]:
    clauses = inputs.manifest["clauses"]
    assert type(clauses) is list
    assert all(type(row) is dict for row in clauses)
    return clauses


def _case_id_for_frozen_clause(clause_id: str) -> str:
    clause_id.encode("ascii")
    return f"case-{clause_id.lower().replace('#', '-')}"


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _assert_builder_code(inputs: Any, expected_code: str) -> None:
    with pytest.raises(FixtureInputError) as captured:
        build_conversion_checklist(inputs)
    assert captured.value.code == expected_code


def _with_manifest_mutation(
    inputs: Any,
    mutation: Callable[[list[dict[str, Any]]], None],
) -> Any:
    manifest = copy.deepcopy(inputs.manifest)
    clauses = manifest["clauses"]
    assert type(clauses) is list
    mutation(clauses)
    return replace(inputs, manifest=manifest)


def _namespace_snapshot(path: Path) -> tuple[Any, ...]:
    if not os.path.lexists(path):
        return ("absent",)
    entries: list[tuple[Any, ...]] = []
    for entry in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        relative = entry.relative_to(path).as_posix()
        if entry.is_dir():
            entries.append(("directory", relative))
        elif entry.is_file():
            entries.append(
                ("file", relative, hashlib.sha256(entry.read_bytes()).digest())
            )
        else:
            entries.append(("other", relative))
    return ("present", *entries)


def test_checklist_uses_manifest_ordinal_windows(frozen_inputs: Any) -> None:
    checklist = build_conversion_checklist(frozen_inputs)
    rows = checklist["cases"]
    assert type(rows) is list
    assert len(rows) == 259 == (20 * 12) + 19
    assert checklist["batch_count"] == 13

    for ordinal, row in enumerate(rows, start=1):
        assert row["ordinal"] == ordinal
        assert row["batch_id"] == f"B{((ordinal - 1) // 20) + 1:02d}"
        assert row["batch_ordinal"] == ((ordinal - 1) % 20) + 1

    assert [
        sum(row["batch_id"] == f"B{batch_number:02d}" for row in rows)
        for batch_number in range(1, 14)
    ] == ([20] * 12) + [19]
    assert [
        (
            rows[index]["ordinal"],
            rows[index]["batch_id"],
            rows[index]["batch_ordinal"],
        )
        for index in (19, 20, 239, 240, 258)
    ] == [
        (20, "B01", 20),
        (21, "B02", 1),
        (240, "B12", 20),
        (241, "B13", 1),
        (259, "B13", 19),
    ]
    assert rows[119]["clause_id"] == "AC-093#3"
    assert rows[120]["clause_id"] == "AC-094#1"
    assert rows[258]["clause_id"] == "USE-05#1"


def test_checklist_has_exact_top_and_case_fields(frozen_inputs: Any) -> None:
    checklist = build_conversion_checklist(frozen_inputs)
    assert type(checklist) is dict
    assert set(checklist) == _TOP_LEVEL_FIELDS
    assert {key: value for key, value in checklist.items() if key != "cases"} == {
        "schema_version": "0.1",
        "stage0b_manifest_sha256": _STAGE0B_MANIFEST_SHA256,
        "source_count": 214,
        "clause_count": 259,
        "batch_count": 13,
    }
    assert (
        checklist["stage0b_manifest_sha256"]
        == frozen_inputs.raw_sha256_by_key["stage0b_manifest"]
    )
    assert type(checklist["schema_version"]) is str
    assert type(checklist["stage0b_manifest_sha256"]) is str
    for field in ("source_count", "clause_count", "batch_count"):
        assert type(checklist[field]) is int

    rows = checklist["cases"]
    clauses = _manifest_clauses(frozen_inputs)
    assert type(rows) is list
    assert len(rows) == len(clauses)
    assert tuple(row["clause_id"] for row in rows) == tuple(
        frozen_inputs.clauses_by_id
    )
    for field in ("case_id", "reviewed_path", "generated_path"):
        assert len({row[field] for row in rows}) == 259

    for row, clause in zip(rows, clauses, strict=True):
        assert type(row) is dict
        assert set(row) == _ROW_FIELDS
        for field in ("ordinal", "batch_ordinal"):
            assert type(row[field]) is int
        for field in (
            "batch_id",
            "case_id",
            "reviewed_path",
            "generated_path",
            "clause_id",
            "source_id",
            "source_group",
            "source_binding_sha256",
            "decision_sha256",
            "clause_stimulus_sha256",
            "clause_expected_sha256",
            "clause_content_sha256",
        ):
            assert type(row[field]) is str
        for field in (
            "source_binding_sha256",
            "decision_sha256",
            "clause_stimulus_sha256",
            "clause_expected_sha256",
            "clause_content_sha256",
        ):
            assert len(row[field]) == 64
            assert all(
                character in "0123456789ABCDEF"
                for character in row[field]
            )
        assert type(row["required_oracle_kinds"]) is list
        assert all(type(kind) is str for kind in row["required_oracle_kinds"])
        clause_id = clause["clause_id"]
        assert type(clause_id) is str
        case_id = _case_id_for_frozen_clause(clause_id)
        assert row["case_id"] == case_id
        assert row["reviewed_path"] == (
            f"fixtures/stage0c/reviewed/cases/{case_id}.json"
        )
        assert row["generated_path"] == f"cases/{case_id}.json"
        assert "\\" not in row["reviewed_path"]
        assert "\\" not in row["generated_path"]
        for field in _FROZEN_ROW_FIELDS:
            assert row[field] == clause[field]

        source = frozen_inputs.sources_by_id[clause["source_id"]]
        for field in _SOURCE_AUTHORITY_FIELDS:
            assert row[field] == clause[field] == source[field]

    assert rows[14] == _ROW_15


def test_checklist_rejects_closed_set_and_order_mutations(
    frozen_inputs: Any,
) -> None:
    def missing(clauses: list[dict[str, Any]]) -> None:
        clauses.pop()

    def duplicate(clauses: list[dict[str, Any]]) -> None:
        clauses.append(copy.deepcopy(clauses[-1]))

    def unexpected(clauses: list[dict[str, Any]]) -> None:
        added = copy.deepcopy(clauses[-1])
        added["clause_id"] = "STAGE0C-UNEXPECTED#1"
        clauses.append(added)

    def reordered(clauses: list[dict[str, Any]]) -> None:
        clauses[0], clauses[1] = clauses[1], clauses[0]

    cases = (
        (missing, "checklist_clause_missing"),
        (duplicate, "checklist_clause_duplicate"),
        (unexpected, "checklist_clause_unexpected"),
        (reordered, "checklist_manifest_order_mismatch"),
    )
    for mutation, expected_code in cases:
        carrier = _with_manifest_mutation(frozen_inputs, mutation)
        _assert_builder_code(carrier, expected_code)


@pytest.mark.parametrize(
    "field",
    _SOURCE_AUTHORITY_FIELDS,
)
@pytest.mark.parametrize(
    "surface",
    ("manifest-vs-index", "clause-vs-source"),
)
@pytest.mark.parametrize(
    "clause_index",
    (0, 129, -1),
    ids=("first", "middle", "last"),
)
def test_checklist_rejects_binding_mutations(
    frozen_inputs: Any,
    field: str,
    surface: str,
    clause_index: int,
) -> None:
    manifest = copy.deepcopy(frozen_inputs.manifest)
    clauses = manifest["clauses"]
    assert type(clauses) is list
    clause = clauses[clause_index]
    assert type(clause) is dict
    clause_id = clause["clause_id"]
    assert type(clause_id) is str
    replacement_value = (
        "STAGE0C-MISSING-SOURCE"
        if field == "source_id"
        else "stage0c-mutated-group"
        if field == "source_group"
        else "0" * 64
    )
    assert clause[field] != replacement_value
    clause[field] = replacement_value

    if surface == "manifest-vs-index":
        carrier = replace(frozen_inputs, manifest=manifest)
    else:
        clauses_by_id = copy.deepcopy(frozen_inputs.clauses_by_id)
        clauses_by_id[clause_id][field] = replacement_value
        carrier = replace(
            frozen_inputs,
            manifest=manifest,
            clauses_by_id=clauses_by_id,
        )

    _assert_builder_code(carrier, "checklist_clause_binding_mismatch")


@pytest.mark.parametrize("field", _CLAUSE_ONLY_FIELDS)
@pytest.mark.parametrize(
    "clause_index",
    (0, 129, -1),
    ids=("first", "middle", "last"),
)
def test_checklist_rejects_clause_identity_mutations(
    frozen_inputs: Any,
    field: str,
    clause_index: int,
) -> None:
    manifest = copy.deepcopy(frozen_inputs.manifest)
    clauses = manifest["clauses"]
    assert type(clauses) is list
    clause = clauses[clause_index]
    assert type(clause) is dict
    replacement_value: Any = (
        ["STAGE0C-MUTATED-ORACLE"]
        if field == "required_oracle_kinds"
        else "0" * 64
    )
    assert clause[field] != replacement_value
    clause[field] = replacement_value
    carrier = replace(frozen_inputs, manifest=manifest)
    _assert_builder_code(carrier, "checklist_clause_binding_mismatch")


def test_checklist_validation_precedence_is_stable(frozen_inputs: Any) -> None:
    def duplicate_and_missing(clauses: list[dict[str, Any]]) -> None:
        clauses.pop(0)
        clauses.append(copy.deepcopy(clauses[0]))

    def missing_and_unexpected(clauses: list[dict[str, Any]]) -> None:
        clauses.pop(0)
        added = copy.deepcopy(clauses[-1])
        added["clause_id"] = "STAGE0C-UNEXPECTED#1"
        clauses.append(added)

    def unexpected_and_reordered(clauses: list[dict[str, Any]]) -> None:
        clauses[0], clauses[1] = clauses[1], clauses[0]
        added = copy.deepcopy(clauses[-1])
        added["clause_id"] = "STAGE0C-UNEXPECTED#1"
        clauses.append(added)

    def reordered_and_unbound(clauses: list[dict[str, Any]]) -> None:
        clauses[0], clauses[1] = clauses[1], clauses[0]
        clauses[-1]["source_binding_sha256"] = "0" * 64

    cases = (
        (duplicate_and_missing, "checklist_clause_duplicate"),
        (missing_and_unexpected, "checklist_clause_missing"),
        (unexpected_and_reordered, "checklist_clause_unexpected"),
        (reordered_and_unbound, "checklist_manifest_order_mismatch"),
    )
    for mutation, expected_code in cases:
        carrier = _with_manifest_mutation(frozen_inputs, mutation)
        _assert_builder_code(carrier, expected_code)


def test_checklist_bytes_are_canonical_and_repeatable(
    tmp_path: Path,
    frozen_inputs: Any,
) -> None:
    first = checklist_bytes(frozen_inputs)
    assert type(first) is bytes
    assert first.endswith(b"\n")
    assert not first.startswith(b"\xef\xbb\xbf")

    decoded = json.loads(first.decode("utf-8"))
    assert decoded == build_conversion_checklist(frozen_inputs)
    expected = _canonical_json_bytes(decoded)
    assert first == expected

    path = tmp_path / "conversion_checklist_v0_1.json"
    path.write_bytes(first)
    reread = path.read_bytes()
    second = checklist_bytes(frozen_inputs)
    assert reread == first == second
    assert hashlib.sha256(reread).digest() == hashlib.sha256(second).digest()


def test_repeated_builds_do_not_reuse_mutable_objects(
    frozen_inputs: Any,
) -> None:
    manifest_before = _canonical_json_bytes(frozen_inputs.manifest)
    first = build_conversion_checklist(frozen_inputs)
    second = build_conversion_checklist(frozen_inputs)
    manifest_after = _canonical_json_bytes(frozen_inputs.manifest)
    first_rows = first["cases"]
    second_rows = second["cases"]
    clauses = _manifest_clauses(frozen_inputs)
    assert type(first_rows) is list
    assert type(second_rows) is list
    assert first == second
    assert first is not second
    assert first_rows is not second_rows
    assert manifest_after == manifest_before

    for first_row, second_row, clause in zip(
        first_rows,
        second_rows,
        clauses,
        strict=True,
    ):
        assert first_row == second_row
        assert first_row is not second_row
        assert first_row is not clause
        assert second_row is not clause
        assert (
            first_row["required_oracle_kinds"]
            is not second_row["required_oracle_kinds"]
        )
        assert (
            first_row["required_oracle_kinds"]
            is not clause["required_oracle_kinds"]
        )
        assert (
            second_row["required_oracle_kinds"]
            is not clause["required_oracle_kinds"]
        )

    second_snapshot = copy.deepcopy(second)
    first_rows[0]["source_group"] = "stage0c-output-mutation"
    first_rows[0]["required_oracle_kinds"].append("STAGE0C-OUTPUT-MUTATION")
    assert second == second_snapshot
    assert _canonical_json_bytes(frozen_inputs.manifest) == manifest_before


def test_checklist_builders_do_not_write_repository_generated(
    repository_root: Path,
    frozen_inputs: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = repository_root / "fixtures" / "stage0c" / "generated"
    before = _namespace_snapshot(generated)

    def forbidden_filesystem_call(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("pure checklist builder accessed the filesystem")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden_filesystem_call)
        guard.setattr(Path, "open", forbidden_filesystem_call)
        guard.setattr(Path, "write_bytes", forbidden_filesystem_call)
        guard.setattr(Path, "write_text", forbidden_filesystem_call)
        guard.setattr(Path, "mkdir", forbidden_filesystem_call)
        guard.setattr(Path, "touch", forbidden_filesystem_call)
        for name in (
            "open",
            "mkdir",
            "makedirs",
            "remove",
            "unlink",
            "rename",
            "replace",
            "rmdir",
        ):
            guard.setattr(os, name, forbidden_filesystem_call)
        build_conversion_checklist(frozen_inputs)
        checklist_bytes(frozen_inputs)
    after = _namespace_snapshot(generated)
    assert after == before


def test_shared_checklist_fixture_matches_pure_builder(
    checklist: Any,
    frozen_inputs: Any,
) -> None:
    assert checklist == build_conversion_checklist(frozen_inputs)
