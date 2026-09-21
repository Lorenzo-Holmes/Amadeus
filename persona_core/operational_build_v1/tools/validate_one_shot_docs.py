"""Validate the one-shot execution documentation against the canonical plan.

This is documentation/contract validation only. It never calls a model, changes
task status, judges Persona semantics, or declares build/product acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent

DOCS = {
    "ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md",
    "TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md",
    "QUALITY_ASSURANCE_PROTOCOL_V1.md",
    "FAILURE_RECOVERY_RUNBOOK_V1.md",
    "NEW_SESSION_MAX_CAPABILITY_PROMPT.md",
}


def need(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path) -> dict:
    state = load(root / "TASK_STATE.json")
    matrix = load(root / "ACCEPTANCE_MATRIX.json")
    need(state["plan_id"] == matrix["plan_id"] == "APCORE-OPERATIONS-V1", "plan mismatch")
    need(all((root / name).is_file() for name in DOCS), "one-shot document missing")

    tasks = {t["id"]: t for t in state["tasks"]}
    gates = {g["task_id"]: g for g in matrix["gates"]}
    need(len(tasks) == len(gates) == 20, "20-task/gate contract changed")
    need(set(tasks) == set(gates), "task/gate coverage mismatch")
    need(tasks["R047-04"]["required_for_build_scope"] is False, "R047-04 must remain external/real-time")
    need(all(t["required_for_build_scope"] for tid, t in tasks.items() if tid != "R047-04"), "unexpected build-scope exclusion")

    one = (root / "ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md").read_text(encoding="utf-8")
    tech = (root / "TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md").read_text(encoding="utf-8")
    qa = (root / "QUALITY_ASSURANCE_PROTOCOL_V1.md").read_text(encoding="utf-8")
    recovery = (root / "FAILURE_RECOVERY_RUNBOOK_V1.md").read_text(encoding="utf-8")
    prompt = (root / "NEW_SESSION_MAX_CAPABILITY_PROMPT.md").read_text(encoding="utf-8")

    remaining = [tid for tid in tasks if tid.startswith(("R045", "R046", "R047")) and tid not in {"R045-01", "R045-02", "R045-03"}]
    for tid in remaining:
        if tid == "R047-04":
            continue
        need(tid in one or tid in prompt, f"remaining task absent from execution docs: {tid}")

    for phrase in (
        "BUILD_SCOPE_COMPLETE_VALIDATION_PENDING", "PRODUCT_ACCEPTANCE_COMPLETE",
        "adapter_check", "A1–A4/B1–B4", "0自动付费重试", "TASK_STATE.json",
    ):
        need(phrase in one + prompt, f"critical execution policy missing: {phrase}")
    need("PRODUCT_ACCEPTANCE_COMPLETE=false" in prompt, "prompt must preserve external acceptance boundary")

    for phrase in (
        "AdmissionController", "SQLite", "BEGIN IMMEDIATE", "runtime_events",
        "event_candidates", "120 条", "SOURCE_FACT_ONLY", "HOLD",
    ):
        need(phrase in tech, f"technical architecture missing: {phrase}")

    need("120条" in qa or "120 条" in qa, "QA protocol missing: 120 distractors")
    for phrase in (
        "SUBMITTED_STATUS_UNKNOWN", "critical finding=0", "R047-05",
        "故障注入", "长期检索",
    ):
        need(phrase in qa, f"QA protocol missing: {phrase}")

    for phrase in (
        "DevSpace 502", "收费请求未知状态", "PARTIAL_OR_UNKNOWN", "LAST_COMPLETED",
        "IN_FLIGHT", "SPEND",
    ):
        need(phrase in recovery, f"recovery runbook missing: {phrase}")

    current = {
        "active_task": state["active_task"],
        "phase_status": state["phase_status"],
        "completed_tasks": [tid for tid, t in tasks.items() if t["status"] == "DONE"],
        "build_scope_complete": state["completion"]["build_scope_complete"],
        "product_acceptance_complete": state["completion"]["product_acceptance_complete"],
    }
    need(current["product_acceptance_complete"] is False,
         "external/real-time product acceptance must remain pending until R047-04 passes")

    required_tasks = {tid: task for tid, task in tasks.items() if task["required_for_build_scope"]}
    required_gates = {tid: gates[tid] for tid in required_tasks}
    required_complete = (
        len(required_tasks) == 19
        and all(task["status"] == "DONE" for task in required_tasks.values())
        and all(gate["status"] == "PASS" for gate in required_gates.values())
    )
    completion_record_path = root / "evidence/R047-05/BUILD_SCOPE_COMPLETE_VALIDATION_PENDING.json"

    if current["build_scope_complete"]:
        need(required_complete,
             "build-scope completion may only be recorded after all 19 required tasks/gates pass")
        need(completion_record_path.is_file(),
             "build-scope completion record is missing")
        completion = load(completion_record_path)
        need(completion.get("status") == "BUILD_SCOPE_COMPLETE_VALIDATION_PENDING"
             and completion.get("plan_id") == state["plan_id"]
             and completion.get("build_scope_complete") is True
             and completion.get("product_acceptance_complete") is False,
             "build-scope completion record has incompatible status/boundaries")
        need(completion.get("completed_required_tasks") == 19
             and completion.get("total_required_tasks") == 19,
             "build-scope completion record does not bind the required denominator")
        for section, path_key, hash_key in (
            ("r047_03", "capture_audit", "capture_audit_sha256"),
            ("r047_03", "review_report", "review_report_sha256"),
            ("r047_03", "current_regression", "current_regression_sha256"),
            ("r047_05", "release_manifest", "release_manifest_sha256"),
            ("r047_05", "release_acceptance_record", "release_acceptance_record_sha256"),
            ("r047_05", "launch_and_recovery_guide", "launch_and_recovery_guide_sha256"),
        ):
            target = root.parent.parent / completion[section][path_key]
            need(target.is_file() and sha256(target) == completion[section][hash_key],
                 f"completion evidence binding failed: {section}.{path_key}")
        need(completion["r047_03"]["captured_and_displayed"] == 82
             and completion["r047_03"]["criteria_pass"] == 328
             and completion["r047_03"]["criteria_total"] == 328
             and completion["r047_03"]["quality_pass"] is True
             and completion["r047_03"]["unresolved_critical_findings"] == 0
             and completion["r047_03"]["unresolved_major_findings"] == 0,
             "completion record does not bind the final R047-03 quality gate")
        need(completion["r047_05"]["engineering_release_gate"] == "PASS"
             and completion["r047_05"]["production_activated"] is False
             and completion["r047_05"]["clean_runtime_verified"] is True
             and completion["r047_05"]["real_cli_restart_passed"] is True,
             "completion record does not bind the controlled release gate")
    else:
        need(not required_complete,
             "all required tasks/gates pass but build_scope_complete remains false")
    return {
        "one_shot_document_contract": "PASS",
        "plan_id": state["plan_id"],
        "documents": sorted(DOCS),
        "canonical_tasks": 20,
        "canonical_gates": 20,
        "parallel_task_system_created": False,
        "current_state_observed_not_modified": current,
        "runtime_tests_executed": 0,
        "semantic_reviews_executed": 0,
        "target_model_calls": 0,
        "scope": "DOCUMENTATION_ONLY_NOT_BUILD_ACCEPTANCE",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = ap.parse_args()
    try:
        print(json.dumps(validate(args.root.resolve()), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"one_shot_document_contract": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
