from collections import Counter
import json
from pathlib import Path

from amadeus_core.contracts.commands import (
    MutationCommandEnvelope,
    normalize_expected_versions,
)
from tools.stage0c_fixtures.checklist import build_conversion_checklist
from tools.stage0c_fixtures.io import load_frozen_inputs, load_strict_json_bytes


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _reviewed_b01_cases() -> list[dict[str, object]]:
    root = _repository_root()
    checklist = build_conversion_checklist(load_frozen_inputs(root))
    rows = tuple(row for row in checklist["cases"] if row["batch_id"] == "B01")
    assert len(rows) == 20
    cases: list[dict[str, object]] = []
    for row in rows:
        path = root / row["reviewed_path"]
        loaded = load_strict_json_bytes(path.read_bytes(), source=str(path))
        assert isinstance(loaded, dict)
        cases.append(loaded)
    return cases


def _mutation_commands(case: dict[str, object]) -> list[dict[str, object]]:
    body = case["case_body"]
    assert isinstance(body, dict)
    commands: list[dict[str, object]] = []
    for group_name in ("setup_steps", "stimulus_steps"):
        raw_steps = body[group_name]
        steps = raw_steps if isinstance(raw_steps, list) else [raw_steps]
        for step in steps:
            assert isinstance(step, dict)
            params = step.get("params", {})
            assert isinstance(params, dict)
            command = params.get("mutation_command")
            if command is not None:
                assert isinstance(command, dict)
                commands.append(command)
    return commands


def _parse_command(command: dict[str, object]) -> MutationCommandEnvelope:
    raw = json.dumps(
        command,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    parsed = MutationCommandEnvelope.model_validate_json(raw)
    normalize_expected_versions(parsed)
    return parsed


def test_all_b01_command_envelopes_satisfy_core_contract() -> None:
    cases = _reviewed_b01_cases()
    parsed = [
        _parse_command(command)
        for case in cases
        for command in _mutation_commands(case)
    ]
    counts = Counter(item.command_id for item in parsed)

    assert len(cases) == 20
    assert len(parsed) == 23
    assert len(counts) == 22
    assert {key: value for key, value in counts.items() if value > 1} == {
        "cmd-idempotent-ac-013": 2,
    }


def test_b01_bridge_reads_only_command_inputs_not_seeded_driver_results() -> None:
    commands = [
        command
        for case in _reviewed_b01_cases()
        for command in _mutation_commands(case)
    ]

    assert commands
    assert all("driver_result_ref" not in command for command in commands)
    assert all("seeded_results" not in command for command in commands)
