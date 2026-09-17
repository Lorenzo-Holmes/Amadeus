"""Check correction references and preservation; not a second semantic reviewer."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "persona_core/operational_build_v1"
OUT = PLAN / "evidence/R044-04"

def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def require(c, reason):
    if not c:
        raise ValueError(reason)

def main():
    state = load(PLAN / "TASK_STATE.json")
    tasks = {t["id"]: t for t in state["tasks"]}
    require(all(tasks[k]["status"] == "DONE" for k in ("R044-01", "R044-02", "R044-03")), "Dependencies incomplete")
    matrix = load(OUT / "ACCEPTANCE_CORRECTION_MATRIX.json")
    risks = load(OUT / "RISK_REGISTER.json")
    for row in matrix["rows"]:
        require(row["followup"] in tasks, "Unknown repair task")
        require(row["old_claim"] and row["new_assessment"] and row["basis"], "Incomplete correction row")
        ref = row["evidence"].split(" DEC-")[0]
        require((ROOT / ref).is_file(), "Missing correction evidence: " + ref)
    require(not matrix["historical_reports_overwritten"] and not risks["activation_allowed"], "Unsafe release claim")
    for risk in risks["risks"]:
        require(risk["task"] in tasks and risk["severity"] and risk["required_action"], "Unassigned risk")
    old = load(ROOT / "persona_core/operational_recovery_20260907_r001/BASELINE_CONTENT_MANIFEST.json")
    preserved = []
    for row in old["files"]:
        if row["path"].startswith("persona_core/"):
            actual = hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
            require(actual == row["sha256"], "Legacy evidence mutated: " + row["path"])
            preserved.append({"path": row["path"], "sha256": actual})
    named = [p for p in OUT.iterdir() if p.suffix in {".json", ".md"}]
    report = {"at_utc": datetime.now(timezone.utc).isoformat(), "reference_integrity": "PASS",
        "correction_rows": len(matrix["rows"]), "mapped_risks": len(risks["risks"]),
        "historical_persona_files_preserved": len(preserved), "preserved": preserved,
        "reviewed_documents": [{"path": p.relative_to(PLAN).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(named)],
        "new_target_calls": 0, "production_written": False, "automatic_semantic_evaluation": False,
        "scope": "Structural reference/preservation check; substantive gate review recorded separately"}
    path = OUT / ("CHECK_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report": path.relative_to(PLAN).as_posix(), "correction_rows": len(matrix["rows"]),
        "mapped_risks": len(risks["risks"]), "legacy_files_preserved": len(preserved)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
