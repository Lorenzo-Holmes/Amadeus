import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text_attribute(path: str) -> str:
    result = subprocess.run(
        ["git", "check-attr", "text", "--", path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().rsplit(": ", 1)[-1]


def test_canonical_fixture_json_is_never_line_ending_normalized() -> None:
    assert _text_attribute(
        "fixtures/stage0a/generated/source_index_v0_1.json"
    ) == "unset"
    assert _text_attribute(
        "fixtures/stage0b/reviewed/source_decisions_v0_1.json"
    ) == "unset"
    assert _text_attribute(
        "fixtures/stage0c/generated/example.json"
    ) == "unset"
