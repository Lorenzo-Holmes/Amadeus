import pytest

from tools.stage0c_fixtures.reviewed import (
    REVIEWED_EXACT_FIELDS,
    load_reviewed_case,
    validate_reviewed_batch,
    validate_reviewed_case,
)


EXPECTED_ROWS = (
    (1,'B01',1,'AC-001#1','case-ac-001-1.json'),
    (2,'B01',2,'AC-002#1','case-ac-002-1.json'),
    (3,'B01',3,'AC-003#1','case-ac-003-1.json'),
    (4,'B01',4,'AC-004#1','case-ac-004-1.json'),
    (5,'B01',5,'AC-005#1','case-ac-005-1.json'),
    (6,'B01',6,'AC-006#1','case-ac-006-1.json'),
    (7,'B01',7,'AC-007#1','case-ac-007-1.json'),
    (8,'B01',8,'AC-008#1','case-ac-008-1.json'),
    (9,'B01',9,'AC-008#2','case-ac-008-2.json'),
    (10,'B01',10,'AC-008#3','case-ac-008-3.json'),
    (11,'B01',11,'AC-009#1','case-ac-009-1.json'),
    (12,'B01',12,'AC-010#1','case-ac-010-1.json'),
    (13,'B01',13,'AC-011#1','case-ac-011-1.json'),
    (14,'B01',14,'AC-012#1','case-ac-012-1.json'),
    (15,'B01',15,'AC-013#1','case-ac-013-1.json'),
    (16,'B01',16,'AC-014#1','case-ac-014-1.json'),
    (17,'B01',17,'AC-015#1','case-ac-015-1.json'),
    (18,'B01',18,'AC-016#1','case-ac-016-1.json'),
    (19,'B01',19,'AC-017#1','case-ac-017-1.json'),
    (20,'B01',20,'AC-018#1','case-ac-018-1.json'),
)


@pytest.mark.parametrize(
    ("ordinal", "batch_id", "batch_ordinal", "clause_id", "filename"),
    EXPECTED_ROWS,
    ids=[row[3].lower().replace("-", "_").replace("#", "_") for row in EXPECTED_ROWS],
)
def test_reviewed_case_matches_frozen_clause(
    repository_root,
    frozen_inputs,
    checklist,
    fixture_schema,
    ordinal,
    batch_id,
    batch_ordinal,
    clause_id,
    filename,
) -> None:
    checklist_row = checklist["cases"][ordinal - 1]
    assert checklist_row["ordinal"] == ordinal
    assert checklist_row["batch_id"] == batch_id
    assert checklist_row["batch_ordinal"] == batch_ordinal
    assert checklist_row["clause_id"] == clause_id
    assert checklist_row["reviewed_path"] == (
        f"fixtures/stage0c/reviewed/cases/{filename}"
    )
    reviewed = load_reviewed_case(repository_root / checklist_row["reviewed_path"])
    frozen_clause = frozen_inputs.clauses_by_id[clause_id]
    issues = validate_reviewed_case(reviewed, frozen_clause, fixture_schema)
    assert issues == []
    assert set(reviewed) == set(REVIEWED_EXACT_FIELDS)
    assert reviewed["reviewer"]["role"] == "conversion_reviewer"
    assert reviewed["reviewer"]["reviewer_id"].strip()
    assert reviewed["rationale"].strip()
    assert reviewed["stimulus_mapping"]["mapping_note"].strip()
    assert all(
        item["mapping_note"].strip()
        for item in reviewed["assertion_or_rubric_mapping"]
    )


def test_reviewed_batch_closure(
    repository_root,
    frozen_inputs,
    checklist,
    fixture_schema,
) -> None:
    checklist_rows = [
        checklist["cases"][ordinal - 1]
        for ordinal, _, _, _, _ in EXPECTED_ROWS
    ]
    expected_ordered = [
        (
            ordinal,
            batch_id,
            batch_ordinal,
            clause_id,
            f"fixtures/stage0c/reviewed/cases/{filename}",
        )
        for ordinal, batch_id, batch_ordinal, clause_id, filename in EXPECTED_ROWS
    ]
    actual_ordered = [
        (
            row["ordinal"],
            row["batch_id"],
            row["batch_ordinal"],
            row["clause_id"],
            row["reviewed_path"],
        )
        for row in checklist_rows
    ]
    assert actual_ordered == expected_ordered

    reviewed_paths = [
        repository_root / checklist_row["reviewed_path"]
        for checklist_row in checklist_rows
    ]
    if not all(path.is_file() for path in reviewed_paths):
        pytest.skip("batch closure requires all 20 reviewed case files")

    rows = [load_reviewed_case(path) for path in reviewed_paths]
    frozen_clauses_by_id = {
        row["clause_id"]: frozen_inputs.clauses_by_id[row["clause_id"]]
        for row in checklist_rows
    }
    assert (
        validate_reviewed_batch(
            rows,
            checklist_rows,
            frozen_clauses_by_id,
            fixture_schema,
        )
        == []
    )
