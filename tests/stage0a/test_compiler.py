import json
from pathlib import Path

import pytest

from tools.stage0a_sources.canonical import _sha256_hex, canonical_bytes
from tools.stage0a_sources.compiler import compile_source_index


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fixtures" / "stage0a" / "source_config_v0_1.json"


def _compiled() -> dict:
    raw_config = CONFIG_PATH.read_bytes()
    return compile_source_index(ROOT, json.loads(raw_config), _sha256_hex(raw_config))


def _ids(prefix: str, first: int, last: int, width: int = 2) -> set[str]:
    return {f"{prefix}-{number:0{width}d}" for number in range(first, last + 1)}


EXPECTED_SOURCE_IDS = {
    "baseline": (_ids("ID", 1, 6) | _ids("SRC", 1, 6) | _ids("GROW", 1, 6)
                 | _ids("MEM", 1, 8) | _ids("TIME", 1, 6) | _ids("USE", 1, 5)
                 | _ids("SEC", 1, 6) | _ids("DEL", 1, 5) | _ids("BR", 1, 5)),
    "increment": (_ids("PRO", 1, 12) | _ids("COR", 1, 8) | _ids("TOOL", 1, 14)
                  | _ids("INJ", 1, 10) | _ids("REL", 1, 12) | _ids("EXIT", 1, 10)),
    "core": _ids("AC", 1, 95, 3),
}


def test_compiles_exact_frozen_source_set() -> None:
    index = _compiled()
    assert index["schema_version"] == "0.1"
    assert index["source_config_sha256"] == _sha256_hex(CONFIG_PATH.read_bytes())
    assert index["source_counts"] == {"baseline": 53, "increment": 66, "core": 95}
    assert index["unique_source_count"] == 214
    assert index["missing_source_ids"] == []
    assert index["unexpected_source_ids"] == []
    assert index["duplicate_source_ids"] == []
    actual_by_group = {
        group: {source["source_id"] for source in index["sources"] if source["source_group"] == group}
        for group in EXPECTED_SOURCE_IDS
    }
    assert actual_by_group == EXPECTED_SOURCE_IDS
    assert set().union(*actual_by_group.values()) == set().union(*EXPECTED_SOURCE_IDS.values())
    assert len(set().union(*actual_by_group.values())) == 214
    assert [source["source_id"] for source in index["sources"]] == sorted(source["source_id"] for source in index["sources"])


def test_preserves_raw_source_evidence_and_binding() -> None:
    for source in _compiled()["sources"]:
        original = (ROOT / source["document_path"]).read_text(encoding="utf-8").splitlines()[source["line_number"] - 1]
        assert source["raw_line"] == original
        assert source["raw_cells"] == original[1:-1].split("|")
        assert source["raw_row_sha256"] == _sha256_hex(original.encode("utf-8"))
        assert source["source_binding_sha256"] == _sha256_hex(canonical_bytes({
            "document_sha256": source["document_sha256"],
            "line_number": source["line_number"], "raw_line": original,
        }))
        assert source["raw_row_sha256"] != _sha256_hex((original + " ").encode("utf-8"))


def test_core_oracle_is_undeclared_and_normalized() -> None:
    core_sources = [source for source in _compiled()["sources"] if source["source_group"] == "core"]
    assert len(core_sources) == 95
    for source in core_sources:
        normalized = source["normalized"]
        assert normalized["raw_oracle_tokens"] == []
        assert normalized["canonical_oracle_kinds"] == []
        assert normalized["oracle_provenance"] == "undeclared"
        assert normalized["title"] == source["raw_cells"][1].replace("[FRAME]", "").strip()
        assert normalized["scenario"] is None
        assert normalized["action"] == source["raw_cells"][2].replace("[FRAME]", "").strip()
        assert normalized["expected"] == source["raw_cells"][3].replace("[FRAME]", "").strip()


def test_behavior_oracle_distributions_and_aliases() -> None:
    index = _compiled()
    assert index["behavior_oracle_combinations"] == {
        "baseline": {"D": 30, "D+H": 20, "H": 2, "H+L": 1},
        "increment": {"D": 18, "D+H": 18, "D+S": 23, "H": 4, "H+J": 3},
    }
    for group, expected in index["behavior_oracle_combinations"].items():
        actual: dict[str, int] = {}
        for source in (item for item in index["sources"] if item["source_group"] == group):
            normalized = source["normalized"]
            assert normalized["title"] is None
            assert normalized["scenario"] == source["raw_cells"][1].replace("[FRAME]", "").strip()
            assert normalized["action"] is None
            assert normalized["expected"] == source["raw_cells"][2].replace("[FRAME]", "").strip()
            assert normalized["oracle_provenance"] == "source_declared"
            raw = "+".join(normalized["raw_oracle_tokens"])
            actual[raw] = actual.get(raw, 0) + 1
        assert actual == expected
    legacy = next(source for source in index["sources"] if source["normalized"]["raw_oracle_tokens"] == ["H", "L"])
    assert legacy["normalized"]["canonical_oracle_kinds"] == ["H", "J"]


def test_rejects_document_change_between_verification_and_source_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = json.loads(CONFIG_PATH.read_bytes())
    baseline_path = (ROOT / next(
        item["path"] for item in config["documents"] if item["key"] == "baseline"
    )).resolve()
    original_read_bytes = Path.read_bytes
    reads = 0

    def changed_on_second_baseline_read(path: Path) -> bytes:
        nonlocal reads
        payload = original_read_bytes(path)
        if path.resolve() == baseline_path:
            reads += 1
            if reads == 2:
                return payload + b" "
        return payload

    monkeypatch.setattr(Path, "read_bytes", changed_on_second_baseline_read)
    with pytest.raises(ValueError, match=r"document drift: key=baseline"):
        compile_source_index(ROOT, config, _sha256_hex(CONFIG_PATH.read_bytes()))
