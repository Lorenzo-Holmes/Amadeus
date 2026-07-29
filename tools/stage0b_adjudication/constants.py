from pathlib import Path


INPUT_ARTIFACTS = {
    "source_index_v0_1.json": {
        "path": Path("fixtures/stage0a/generated/source_index_v0_1.json"),
        "sha256": "D29855B5F8ED870608CF52B91A9997E4D41922E4085FBAE41E385610D87DE25C",
        "size": 229060,
    },
    "oracle_assignment_worklist_v0_1.json": {
        "path": Path(
            "fixtures/stage0a/generated/oracle_assignment_worklist_v0_1.json"
        ),
        "sha256": "7BD9350A108B4274FA07D83A1315FC33226504DCD998DAA17AE3ED83C917DE51",
        "size": 62790,
    },
    "atomicity_worklist_v0_1.json": {
        "path": Path(
            "fixtures/stage0a/generated/atomicity_worklist_v0_1.json"
        ),
        "sha256": "D93342C7E93F4C368DF44989BB3B341AAB364B472E9B6150FC7B97E469D0BFD2",
        "size": 85569,
    },
    "source_toolchain_report_v0_1.json": {
        "path": Path(
            "fixtures/stage0a/generated/source_toolchain_report_v0_1.json"
        ),
        "sha256": "3154019197C1B6C16E951F278E9688F1DD6D18459BD5D2B3AD71A87C92BBD3F0",
        "size": 337,
    },
}

CHECKLIST_PATH = Path(
    "fixtures/stage0b/generated/adjudication_checklist_v0_1.json"
)
REVIEWED_PATH = Path(
    "fixtures/stage0b/reviewed/source_decisions_v0_1.json"
)
MANIFEST_PATH = Path(
    "fixtures/stage0b/generated/source_clause_manifest_v0_1.json"
)
REPORT_PATH = Path("fixtures/stage0b/generated/stage0b_report_v0_1.json")
ORACLE_ORDER = ("D", "S", "H", "J")
