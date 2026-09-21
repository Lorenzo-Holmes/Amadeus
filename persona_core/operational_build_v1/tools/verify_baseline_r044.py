"""R044-01: verify the existing content backup and preserve current entry bytes.

No generation, installation, production mutation, or semantic acceptance.
Output is exclusive-create. A timed-out run must be inspected, not retried.
"""
from __future__ import annotations
import difflib
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "persona_core/operational_build_v1"
OLD = ROOT / "persona_core/operational_recovery_20260907_r001"
OUT = PLAN / "evidence/R044-01"

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def save(name: str, value) -> None:
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def check(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)

def main() -> None:
    sys.dont_write_bytecode = True
    check(str(ROOT).casefold() == r"C:\Users\skr\Documents\Codex\Amadeus-Project.staging".casefold(), "Wrong workspace")
    OUT.mkdir(parents=True, exist_ok=False)
    save("STARTED.json", {"at": datetime.now(timezone.utc).isoformat(), "model_calls": 0})
    manifest = load(OLD / "BASELINE_CONTENT_MANIFEST.json")
    old_report = load(OLD / "BACKUP_RESTORE_REPORT.json")
    archive = OLD / "BASELINE_CONTENT.zip"
    check(sha(archive.read_bytes()) == old_report["archive_sha256"], "Backup archive changed")
    bindings, changed = [], []
    with zipfile.ZipFile(archive) as z:
        check(z.testzip() is None, "Backup CRC failed")
        check(set(z.namelist()) == {r["path"] for r in manifest["files"]}, "Backup member coverage")
        for row in manifest["files"]:
            raw = z.read(row["path"])
            check(sha(raw) == row["sha256"] and len(raw) == row["size_bytes"], "Bad backup member")
            restored = OLD / "restore_drill" / row["path"]
            check(sha(restored.read_bytes()) == row["sha256"], "Restored member changed")
            live = ROOT / row["path"]
            actual = sha(live.read_bytes())
            if actual != row["sha256"]:
                check("/" not in row["path"] and row["path"] != "AGENTS.md", "Historical Persona Core content changed")
                changed.append({"path": row["path"], "before_sha256": row["sha256"], "current_sha256": actual})
            purpose = "historical_persona_evidence"
            if row["path"].startswith("persona_core/runtime/"):
                purpose = "production_genesis_state_ledger_or_code"
            elif "/rebaseline_20260907_r033/" in row["path"]:
                purpose = "original_evaluation_input_output_rubric_validator"
            elif "/rebaseline_20260907_r034/" in row["path"]:
                purpose = "frozen_components"
            bindings.append({**row, "current_sha256": actual, "purpose": purpose})
        diffs = []
        for r in changed:
            name = r["path"]
            diffs.extend(difflib.unified_diff(z.read(name).decode("utf-8-sig").splitlines(True),
                (ROOT / name).read_text(encoding="utf-8-sig").splitlines(True),
                fromfile="baseline/" + name, tofile="current/" + name))
    with (OUT / "CURRENT_VS_ORIGINAL_ENTRY.patch").open("x", encoding="utf-8", newline="\n") as f:
        f.write("".join(diffs))
    entries = [ROOT / n for n in ("AGENTS.md", "AMADEUS_PERSONA_CORE_MASTER_GOAL.md", "PERSONA_CORE_PROGRESS.md", "PERSONA_CORE_CONTINUATION_PROTOCOL.md", "PERSONA_CORE_DECISION_LOG.md")]
    entries += [PLAN / n for n in ("TASK_STATE.json", "ACCEPTANCE_MATRIX.json", "START_HERE.md", "CHANGELOG.md")]
    supplement = OUT / "CURRENT_ENTRY_SNAPSHOT.zip"
    with zipfile.ZipFile(supplement, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for path in entries:
            z.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
    with zipfile.ZipFile(supplement) as z:
        check(z.testzip() is None, "Entry backup CRC failed")
        for path in entries:
            check(z.read(path.relative_to(ROOT).as_posix()) == path.read_bytes(), "Entry backup drift")
    package_pins = load(PLAN / "MANIFEST.json")
    package_checks = []
    for r in package_pins["files"]:
        p = PLAN / r["path"]
        check(sha(p.read_bytes()) == r["sha256"], "Original package member changed before this revision: " + r["path"])
        package_checks.append({"path": r["path"], "sha256": r["sha256"], "match": True})
    cli = OLD / "restore_drill/persona_core/runtime/runtime_cli.py"
    proc = subprocess.run([sys.executable, "-B", str(cli), "--root", str(cli.parent), "--snapshot"],
                          cwd=ROOT, capture_output=True, timeout=25)
    check(proc.returncode == 0, "Fresh restored process failed")
    state = json.loads(proc.stdout.decode("utf-8"))
    check(len(state["ledger"]) == 1 and state["relationship"]["product_entities"] == {}, "Unexpected baseline production history")
    # Output a compact reading view. Full original inputs already preserved in
    # R033 and R033_BOUND_REVIEW_INPUTS; nothing in this view is a judgment.
    r033 = ROOT / "persona_core/rebaseline_20260907_r033"
    rub = load(r033 / "PRIVATE_RUBRICS_R033.json")["cases"]
    packets = {p["case_id"]: p for p in load(r033 / "REQUESTS_R033.json")}
    captures = [json.loads(x) for x in (r033 / "capture_final_01/responses.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    lines = ["# Original R033 inputs, criteria and 42 outputs — reading view, no verdicts\n"]
    for c in rub:
        lines += ["\n## " + c["id"], "Mode: " + c["lane"], "Input: " + c["input"], "Scenario: " + json.dumps(c["scenario"], ensure_ascii=False), "History: " + json.dumps(c["history"], ensure_ascii=False)]
        lines.extend(x["criterion_id"] + " | " + x["text"] for x in c["criteria"])
        lines.append("System scope: explicit synthetic roleplay AND R029/R032 current-product presentation constraints; full packet preserved.")
        for r in captures:
            if r["case_id"] == c["id"]:
                lines += ["\n### " + r["phase"] + ":" + r["request_id"], r["response_text"], ""]
    with (OUT / "R033_REVIEW_READING.md").open("x", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    save("BASELINE_MANIFEST.json", {"created_at": datetime.now(timezone.utc).isoformat(), "files": bindings,
        "original_backup": archive.relative_to(ROOT).as_posix(), "original_backup_sha256": sha(archive.read_bytes()),
        "entry_supplement": supplement.relative_to(ROOT).as_posix(), "entry_supplement_sha256": sha(supplement.read_bytes()),
        "entry_members": [{"path": p.relative_to(ROOT).as_posix(), "size_bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in entries],
        "external_original_corpus": "NOT_INCLUDED; keep prior source-package references and documented gaps"})
    save("SNAPSHOT_READ_VERIFICATION.json", {"checked_at": datetime.now(timezone.utc).isoformat(),
        "baseline_files_read_and_restored_verified": len(bindings), "unchanged_persona_core_history": True,
        "documented_entry_changes": changed, "original_package_members_matched": package_checks,
        "fresh_process_exit_code": proc.returncode, "restored_ledger_events": len(state["ledger"]),
        "restored_product_entities": 0, "runtime_state_sha256": sha(proc.stdout),
        "local_inflight_observation": "Before this run: one node process; no python/pythonw process. No paid request initiated here.",
        "remote_unlogged_calls": "UNKNOWN; no resends; 42 R033 captures terminal per preserved audit",
        "legacy_spend_inventory": "persona_core/operational_recovery_20260907_r001/CALL_CAPTURE_INVENTORY.json",
        "new_model_calls": 0, "new_cost_cny": 0, "semantic_reviews_performed_by_script": 0,
        "production_modified": False, "result": "PASS_BASELINE_CONTENT_AND_RESTORE_ONLY"})
    save("FINISHED.json", {"at": datetime.now(timezone.utc).isoformat(), "exit_code": 0})
    print(json.dumps({"verified_files": len(bindings), "package_members": len(package_checks),
        "historical_persona_unchanged": True, "fresh_restore_process": "PASS", "new_calls": 0}))

if __name__ == "__main__":
    main()
