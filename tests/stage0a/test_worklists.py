import json
from pathlib import Path

from tools.stage0a_sources.canonical import _sha256_hex, canonical_bytes
from tools.stage0a_sources.compiler import compile_source_index
from tools.stage0a_sources.worklists import (
    build_atomicity_worklist,
    build_oracle_worklist,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fixtures" / "stage0a" / "source_config_v0_1.json"
ORACLE_ITEM_FIELDS = {
    "source_id",
    "source_group",
    "source_binding_sha256",
    "review_state",
    "source_oracle_tokens",
    "canonical_oracle_kinds",
    "assigned_oracle_kinds",
    "rationale",
}
ATOMICITY_ITEM_FIELDS = {
    "source_id",
    "source_group",
    "source_binding_sha256",
    "scenario_or_title",
    "action",
    "expected",
    "review_state",
    "atomicity_decision",
    "rationale",
    "clauses",
}


def _compiled() -> dict:
    raw_config = CONFIG_PATH.read_bytes()
    return compile_source_index(
        ROOT,
        json.loads(raw_config),
        _sha256_hex(raw_config),
    )


def test_build_oracle_worklist_maps_every_source_deterministically() -> None:
    index = _compiled()

    worklist = build_oracle_worklist(index)

    assert set(worklist) == {
        "schema_version",
        "source_declared_count",
        "pending_assignment_count",
        "items",
    }
    assert worklist["schema_version"] == "0.1"
    assert worklist["source_declared_count"] == 119
    assert worklist["pending_assignment_count"] == 95
    assert len(worklist["items"]) == 214
    assert [item["source_id"] for item in worklist["items"]] == [
        source["source_id"] for source in index["sources"]
    ]

    source_by_id = {
        source["source_id"]: source
        for source in index["sources"]
    }
    for item in worklist["items"]:
        assert set(item) == ORACLE_ITEM_FIELDS
        source = source_by_id[item["source_id"]]
        normalized = source["normalized"]
        assert item["source_group"] == source["source_group"]
        assert item["source_binding_sha256"] == source["source_binding_sha256"]
        if source["source_group"] == "core":
            assert item["review_state"] == "pending_assignment"
            assert item["source_oracle_tokens"] == []
            assert item["canonical_oracle_kinds"] == []
            assert item["assigned_oracle_kinds"] == []
            assert item["rationale"] is None
        else:
            assert item["review_state"] == "source_declared"
            assert item["source_oracle_tokens"] == normalized["raw_oracle_tokens"]
            assert (
                item["canonical_oracle_kinds"]
                == normalized["canonical_oracle_kinds"]
            )
            assert (
                item["assigned_oracle_kinds"]
                == normalized["canonical_oracle_kinds"]
            )
            assert item["rationale"] == "source table oracle column"

    assert (
        canonical_bytes(build_oracle_worklist(index))
        == canonical_bytes(worklist)
    )


def test_build_atomicity_worklist_maps_every_source_deterministically() -> None:
    index = _compiled()

    worklist = build_atomicity_worklist(index)

    assert set(worklist) == {
        "schema_version",
        "pending_review_count",
        "items",
    }
    assert worklist["schema_version"] == "0.1"
    assert worklist["pending_review_count"] == 214
    assert len(worklist["items"]) == 214
    assert [item["source_id"] for item in worklist["items"]] == [
        source["source_id"] for source in index["sources"]
    ]

    source_by_id = {
        source["source_id"]: source
        for source in index["sources"]
    }
    for item in worklist["items"]:
        assert set(item) == ATOMICITY_ITEM_FIELDS
        source = source_by_id[item["source_id"]]
        normalized = source["normalized"]
        assert item["source_group"] == source["source_group"]
        assert item["source_binding_sha256"] == source["source_binding_sha256"]
        assert item["scenario_or_title"] == (
            normalized["scenario"]
            if normalized["scenario"] is not None
            else normalized["title"]
        )
        assert item["action"] == normalized["action"]
        assert item["expected"] == normalized["expected"]
        assert item["review_state"] == "pending_review"
        assert item["atomicity_decision"] is None
        assert item["rationale"] is None
        assert item["clauses"] == []

    assert (
        canonical_bytes(build_atomicity_worklist(index))
        == canonical_bytes(worklist)
    )
