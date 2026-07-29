from pathlib import Path
from typing import Any

from .constants import CHECKLIST_PATH, INPUT_ARTIFACTS
from .io import canonical_bytes, load_stage0a_inputs


def _items_by_id(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if type(value) is not dict or type(value.get("items")) is not list:
        raise ValueError(f"stage0b checklist {label} items")
    result: dict[str, dict[str, Any]] = {}
    for item in value["items"]:
        if type(item) is not dict or type(item.get("source_id")) is not str:
            raise ValueError(f"stage0b checklist {label} item")
        source_id = item["source_id"]
        if source_id in result:
            raise ValueError(f"stage0b checklist {label} source id set")
        result[source_id] = item
    return result


def build_checklist(inputs: dict[str, Any]) -> dict[str, Any]:
    if set(inputs) != set(INPUT_ARTIFACTS):
        raise ValueError("stage0b checklist input artifact set")
    source_index = inputs["source_index_v0_1.json"]
    if type(source_index.get("sources")) is not list:
        raise ValueError("stage0b checklist source index items")
    sources: dict[str, dict[str, Any]] = {}
    source_order: list[str] = []
    for source in source_index["sources"]:
        if type(source) is not dict or type(source.get("source_id")) is not str:
            raise ValueError("stage0b checklist source index item")
        source_id = source["source_id"]
        if source_id in sources:
            raise ValueError("stage0b checklist source index source id set")
        sources[source_id] = source
        source_order.append(source_id)
    if source_order != sorted(source_order) or len(source_order) != 214:
        raise ValueError("stage0b checklist source index order")

    oracle_items = _items_by_id(
        inputs["oracle_assignment_worklist_v0_1.json"], "oracle"
    )
    atomicity_items = _items_by_id(
        inputs["atomicity_worklist_v0_1.json"], "atomicity"
    )
    expected_ids = set(source_order)
    if set(oracle_items) != expected_ids:
        raise ValueError("stage0b checklist oracle source id set")
    if set(atomicity_items) != expected_ids:
        raise ValueError("stage0b checklist atomicity source id set")

    items = []
    for source_id in source_order:
        source = sources[source_id]
        oracle = oracle_items[source_id]
        atomicity = atomicity_items[source_id]
        binding = source.get("source_binding_sha256")
        if oracle.get("source_binding_sha256") != binding:
            raise ValueError(f"stage0b checklist oracle binding mismatch: {source_id}")
        if atomicity.get("source_binding_sha256") != binding:
            raise ValueError(
                f"stage0b checklist atomicity binding mismatch: {source_id}"
            )
        if oracle.get("source_group") != source.get("source_group"):
            raise ValueError(f"stage0b checklist oracle group mismatch: {source_id}")
        if atomicity.get("source_group") != source.get("source_group"):
            raise ValueError(
                f"stage0b checklist atomicity group mismatch: {source_id}"
            )
        items.append({
            "source_id": source_id,
            "source_group": source["source_group"],
            "source_binding_sha256": binding,
            "scenario_or_title": atomicity["scenario_or_title"],
            "action": atomicity["action"],
            "expected": atomicity["expected"],
            "source_declared_oracle_kinds": list(
                oracle["canonical_oracle_kinds"]
            ),
            "assigned_oracle_kinds": list(oracle["assigned_oracle_kinds"]),
            "oracle_review_state": oracle["review_state"],
            "oracle_rationale": oracle["rationale"],
            "atomicity_review_state": atomicity["review_state"],
            "atomicity_decision": atomicity["atomicity_decision"],
            "atomicity_rationale": atomicity["rationale"],
            "clauses": list(atomicity["clauses"]),
        })

    oracle_worklist = inputs["oracle_assignment_worklist_v0_1.json"]
    atomicity_worklist = inputs["atomicity_worklist_v0_1.json"]
    report = inputs["source_toolchain_report_v0_1.json"]
    if source_index.get("source_counts") != {
        "baseline": 53,
        "core": 95,
        "increment": 66,
    }:
        raise ValueError("stage0b checklist source counts")
    if oracle_worklist.get("source_declared_count") != 119:
        raise ValueError("stage0b checklist source-declared count")
    if oracle_worklist.get("pending_assignment_count") != 95:
        raise ValueError("stage0b checklist pending assignment count")
    if atomicity_worklist.get("pending_review_count") != 214:
        raise ValueError("stage0b checklist pending atomicity count")
    if report.get("source_toolchain_ready") is not True:
        raise ValueError("stage0b checklist source toolchain readiness")

    return {
        "schema_version": "0.1",
        "input_artifacts": {
            name: contract["sha256"] for name, contract in INPUT_ARTIFACTS.items()
        },
        "source_counts": dict(source_index["source_counts"]),
        "source_declared_count": oracle_worklist["source_declared_count"],
        "pending_assignment_count": oracle_worklist["pending_assignment_count"],
        "pending_review_count": atomicity_worklist["pending_review_count"],
        "items": items,
    }


def checklist_bytes(root: str | Path) -> bytes:
    return canonical_bytes(build_checklist(load_stage0a_inputs(root))) + b"\n"


def write_checklist(root: str | Path) -> Path:
    root_path = Path(root).resolve(strict=True)
    output_path = root_path / CHECKLIST_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(checklist_bytes(root_path))
    return output_path
