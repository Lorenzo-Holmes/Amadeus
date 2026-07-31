# tools/stage0c_fixtures/constants.py
SCHEMA_VERSION = "0.1"
EXPECTED_SOURCE_COUNT = 214
EXPECTED_CLAUSE_COUNT = 259
EXPECTED_S_SOURCE_COUNT = 75
EXPECTED_S_CLAUSE_COUNT = 98
EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT = 51
EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT = 55
EXPECTED_BATCH_COUNT = 13
EXPECTED_GENERATED_CASE_COUNT = 259
EXPECTED_GENERATED_TOP_LEVEL_COUNT = 6
EXPECTED_GENERATED_FILE_COUNT = 265
BATCH_SIZE = 20
EXPECTED_SOURCE_ID_SET_SHA256 = (
    "9B771DEFE9BBD3F2025F32AB400ADE1AA4916223BE467B7EEF0135E9E3C4D39A"
)
EXPECTED_CLAUSE_ID_SET_SHA256 = (
    "0BD1579970C18D4BFB7A0F57AA53B8E30CB3DA5F50DB8F48240E16C634FD5CFC"
)

LOCK_PATH = "fixtures/stage0c/.stage0c-write.lock"
GENERATED_PATH = "fixtures/stage0c/generated"
REVIEWED_CASES_PATH = "fixtures/stage0c/reviewed/cases"
JOURNAL_PATH = "fixtures/stage0c/.stage0c-publication.json"
SMOKE_EVIDENCE_PATH = (
    "outputs/verification/"
    "Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json"
)

INPUT_IDENTITIES = {
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
