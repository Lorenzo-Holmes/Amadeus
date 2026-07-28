from typing import Any


def build_oracle_worklist(index: dict[str, Any]) -> dict[str, Any]:
    items = []
    for source in index["sources"]:
        normalized = source["normalized"]
        source_declared = source["source_group"] != "core"
        canonical_kinds = (
            list(normalized["canonical_oracle_kinds"])
            if source_declared
            else []
        )
        items.append({
            "source_id": source["source_id"],
            "source_group": source["source_group"],
            "source_binding_sha256": source["source_binding_sha256"],
            "review_state": (
                "source_declared"
                if source_declared
                else "pending_assignment"
            ),
            "source_oracle_tokens": (
                list(normalized["raw_oracle_tokens"])
                if source_declared
                else []
            ),
            "canonical_oracle_kinds": canonical_kinds,
            "assigned_oracle_kinds": list(canonical_kinds),
            "rationale": (
                "source table oracle column"
                if source_declared
                else None
            ),
        })
    return {
        "schema_version": "0.1",
        "source_declared_count": sum(
            item["review_state"] == "source_declared"
            for item in items
        ),
        "pending_assignment_count": sum(
            item["review_state"] == "pending_assignment"
            for item in items
        ),
        "items": items,
    }


def build_atomicity_worklist(index: dict[str, Any]) -> dict[str, Any]:
    items = []
    for source in index["sources"]:
        normalized = source["normalized"]
        items.append({
            "source_id": source["source_id"],
            "source_group": source["source_group"],
            "source_binding_sha256": source["source_binding_sha256"],
            "scenario_or_title": (
                normalized["scenario"]
                if normalized["scenario"] is not None
                else normalized["title"]
            ),
            "action": normalized["action"],
            "expected": normalized["expected"],
            "review_state": "pending_review",
            "atomicity_decision": None,
            "rationale": None,
            "clauses": [],
        })
    return {
        "schema_version": "0.1",
        "pending_review_count": len(items),
        "items": items,
    }
