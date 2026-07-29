import re
from typing import Any

from .constants import ORACLE_ORDER


_TOP_FIELDS = {"schema_version", "input_artifacts", "decisions"}
_DECISION_FIELDS = {
    "source_id",
    "source_group",
    "source_binding_sha256",
    "assigned_oracle_kinds",
    "oracle_rationale",
    "atomicity_decision",
    "atomicity_rationale",
    "clauses",
}
_CLAUSE_FIELDS = {
    "clause_id",
    "stimulus_scope",
    "expected_scope",
    "required_oracle_kinds",
}
_SHA256 = re.compile(r"^[0-9A-F]{64}$")


def _nonempty_text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"stage0b reviewed {label}")
    return value


def _oracle_kinds(value: Any, label: str) -> list[str]:
    if type(value) is not list or not value:
        raise ValueError(f"stage0b reviewed {label} oracle kinds")
    if any(type(item) is not str or item not in ORACLE_ORDER for item in value):
        raise ValueError(f"stage0b reviewed {label} oracle kinds")
    if len(value) != len(set(value)):
        raise ValueError(f"stage0b reviewed {label} oracle kinds")
    if value != sorted(value, key=ORACLE_ORDER.index):
        raise ValueError(f"stage0b reviewed {label} oracle kinds")
    return value


def _checklist_by_id(
    checklist: Any,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if type(checklist) is not dict or type(checklist.get("items")) is not list:
        raise ValueError("stage0b reviewed checklist contract")
    order: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for item in checklist["items"]:
        if type(item) is not dict or type(item.get("source_id")) is not str:
            raise ValueError("stage0b reviewed checklist item")
        source_id = item["source_id"]
        if source_id in by_id:
            raise ValueError("stage0b reviewed checklist duplicate source id")
        order.append(source_id)
        by_id[source_id] = item
    return order, by_id


def validate_reviewed_manifest(
    reviewed: Any,
    checklist: Any,
) -> dict[str, Any]:
    if type(reviewed) is not dict or set(reviewed) != _TOP_FIELDS:
        raise ValueError("stage0b reviewed top-level fields")
    if reviewed["schema_version"] != "0.1":
        raise ValueError("stage0b reviewed schema version")
    if reviewed["input_artifacts"] != checklist.get("input_artifacts"):
        raise ValueError("stage0b reviewed input artifact identity")
    if type(reviewed["decisions"]) is not list:
        raise ValueError("stage0b reviewed decisions type")

    expected_order, checklist_items = _checklist_by_id(checklist)
    decisions_by_id: dict[str, dict[str, Any]] = {}
    actual_order: list[str] = []
    for decision in reviewed["decisions"]:
        if type(decision) is not dict or set(decision) != _DECISION_FIELDS:
            raise ValueError("stage0b reviewed decision fields")
        source_id = decision["source_id"]
        if type(source_id) is not str:
            raise ValueError("stage0b reviewed source id type")
        if source_id in decisions_by_id:
            raise ValueError("stage0b reviewed duplicate source id")
        actual_order.append(source_id)
        decisions_by_id[source_id] = decision

    if set(decisions_by_id) != set(checklist_items):
        raise ValueError("stage0b reviewed source id set")
    if actual_order != expected_order:
        raise ValueError("stage0b reviewed source order")

    for source_id in expected_order:
        decision = decisions_by_id[source_id]
        source = checklist_items[source_id]
        if decision["source_group"] != source["source_group"]:
            raise ValueError(f"stage0b reviewed group identity: {source_id}")
        binding = decision["source_binding_sha256"]
        if (
            type(binding) is not str
            or _SHA256.fullmatch(binding) is None
            or binding != source["source_binding_sha256"]
        ):
            raise ValueError(f"stage0b reviewed binding identity: {source_id}")

        assigned = _oracle_kinds(
            decision["assigned_oracle_kinds"], source_id
        )
        declared = source["source_declared_oracle_kinds"]
        if not set(declared).issubset(assigned):
            raise ValueError(
                f"stage0b reviewed declared oracle downgrade: {source_id}"
            )
        _nonempty_text(decision["oracle_rationale"], "oracle rationale")
        _nonempty_text(
            decision["atomicity_rationale"], "atomicity rationale"
        )

        atomicity = decision["atomicity_decision"]
        if atomicity not in {"atomic", "composite"}:
            raise ValueError(
                f"stage0b reviewed atomicity decision: {source_id}"
            )
        clauses = decision["clauses"]
        if type(clauses) is not list:
            raise ValueError(f"stage0b reviewed clauses type: {source_id}")
        if atomicity == "atomic" and len(clauses) != 1:
            raise ValueError(f"stage0b reviewed atomic clause count: {source_id}")
        if atomicity == "composite" and len(clauses) < 2:
            raise ValueError(
                f"stage0b reviewed composite clause count: {source_id}"
            )

        clause_oracles: set[str] = set()
        for index, clause in enumerate(clauses, 1):
            if type(clause) is not dict or set(clause) != _CLAUSE_FIELDS:
                raise ValueError(
                    f"stage0b reviewed clause fields: {source_id}#{index}"
                )
            if clause["clause_id"] != f"{source_id}#{index}":
                raise ValueError(
                    f"stage0b reviewed clause id sequence: {source_id}"
                )
            _nonempty_text(clause["stimulus_scope"], "stimulus scope")
            _nonempty_text(clause["expected_scope"], "expected scope")
            clause_oracles.update(
                _oracle_kinds(
                    clause["required_oracle_kinds"],
                    f"clause {source_id}#{index}",
                )
            )
        if not set(assigned).issubset(clause_oracles):
            raise ValueError(
                f"stage0b reviewed clause oracle coverage: {source_id}"
            )

    return reviewed
