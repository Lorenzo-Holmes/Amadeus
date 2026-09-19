"""Bind manually authored R044-02 judgments; NEVER generate semantic verdicts."""
from __future__ import annotations
import hashlib
import json
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "persona_core/operational_build_v1"
DIR = PLAN / "evidence/R044-02"
R033 = ROOT / "persona_core/rebaseline_20260907_r033"

def raw_sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def canonical(v) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def require(c, reason):
    if not c:
        raise ValueError(reason)

def main() -> None:
    attempt = DIR / ("bind_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    attempt.mkdir(exist_ok=False)
    try:
        manual = {}
        sources = []
        for p in sorted(DIR.glob("review_*.json")):
            v = load(p)
            require(v["origin"] == "MANUALLY_AUTHORED_AFTER_READING_ORIGINAL_OUTPUTS", "Review origin missing")
            require(v["criterion_order"] == ["required:1", "required:2", "prohibited:1", "prohibited:2"], "Criterion order drift")
            for key, judgments in v["reviews"].items():
                require(key not in manual, "Duplicate authored sample " + key)
                manual[key] = (judgments, v["reviewer_id"], p)
            sources.append({"path": p.relative_to(ROOT).as_posix(), "sha256": raw_sha(p.read_bytes())})
        packets = {p["request_id"]: p for p in load(R033 / "REQUESTS_R033.json")}
        cases = {c["id"]: c for c in load(R033 / "PRIVATE_RUBRICS_R033.json")["cases"]}
        captures = [json.loads(x) for x in (R033 / "capture_final_01/responses.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        require(len(captures) == len(manual) == 42, "Must retain 42 original outputs")
        require(set(manual) == {r["phase"] + ":" + r["case_id"] for r in captures}, "Missing original output")
        bound = []
        counts = Counter()
        for row in captures:
            key = row["phase"] + ":" + row["case_id"]
            entries, reviewer, path = manual[key]
            p = packets[row["request_id"]]
            c = cases[row["case_id"]]
            require(len(entries) == len(c["criteria"]) == 4, "Four unchanged original criteria required")
            require(p["request_sha256"] == row["request_sha256"], "Wrong request binding")
            require(raw_sha(canonical({k: v for k, v in p.items() if k != "request_sha256"})) == p["request_sha256"], "Request packet tampered")
            require(raw_sha(canonical({k: row[k] for k in ("request_id", "request_sha256", "status", "response_text", "origin")})) == row["response_sha256"], "Capture digest mismatch")
            body_path = R033 / "capture_final_01" / ("raw_" + row["phase"] + "_" + row["request_id"] + ".json")
            require(raw_sha(body_path.read_bytes()) == row["provider_body_sha256"], "Provider body hash mismatch")
            body = load(body_path)
            require(body["choices"][0]["message"]["content"] == row["response_text"], "Wrong response body")
            judgments = []
            for criterion, (verdict, quote, rationale) in zip(c["criteria"], entries):
                require(verdict in {"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE", "SPEC_CONFLICT"}, "Invalid explicit verdict")
                require(isinstance(quote, str) and quote and quote in row["response_text"], "Quote mismatch " + key + " " + criterion["criterion_id"] + " " + repr(quote))
                require(isinstance(rationale, str) and bool(rationale.strip()), "Rationale missing " + key + " " + criterion["criterion_id"])
                start = row["response_text"].index(quote)
                judgments.append({**criterion, "verdict": verdict, "quote": quote,
                    "quote_span": [start, start + len(quote)], "rationale": rationale,
                    "mode": c["lane"], "applicability_reason": rationale if verdict in {"NOT_APPLICABLE", "SPEC_CONFLICT"} else None,
                    "semantic_verdict_origin": "EXPLICIT_REVIEWER_JUDGMENT_NOT_LINT"})
                counts[verdict] += 1
            bound.append({"review_id": "R044-02:" + key, "phase": row["phase"], "case_id": row["case_id"],
                "model_id": row["model_id"], "request_id": row["request_id"], "request_sha256": row["request_sha256"],
                "response_sha256": row["response_sha256"], "response_text": row["response_text"],
                "provider_body_sha256": row["provider_body_sha256"], "raw_provider_body": body_path.relative_to(ROOT).as_posix(),
                "original_input": c["input"], "original_scenario": c["scenario"], "original_history": c["history"],
                "original_case_sha256": raw_sha(canonical(c)), "mode": c["lane"],
                "mode_scope_note": "Explicit synthetic fixture; product-boundary overlays also present. See ISSUES_AND_SCOPE.json.",
                "reviewer_id": reviewer, "reviewer_role": "DEVELOPER_ASSISTANT", "independence": "NONBLIND_NOT_INDEPENDENT",
                "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "manual_source": path.relative_to(ROOT).as_posix(),
                "manual_source_sha256": raw_sha(path.read_bytes()), "judgments": judgments})
        with (attempt / "BOUND_REVIEWS.jsonl").open("x", encoding="utf-8", newline="\n") as f:
            for r in bound:
                f.write(canonical(r).decode("utf-8") + "\n")
        report = {"binding_validation": "PASS", "reviewed_outputs": len(bound), "reviewed_criteria": sum(counts.values()),
            "original_output_denominator": 42, "original_criterion_denominator": 168,
            "verdict_counts": dict(counts), "removed_from_denominator": 0,
            "semantic_verdicts_generated_by_script": 0, "reviewer_independence": "NONBLIND_NOT_INDEPENDENT",
            "all_original_rubrics_pass": counts["PASS"] == 168,
            "unresolved_judgments": [{"review_id": r["review_id"], "criterion_id": j["criterion_id"], "verdict": j["verdict"]} for r in bound for j in r["judgments"] if j["verdict"] != "PASS"],
            "manual_sources": sources, "new_model_calls": 0, "new_cost_cny": 0,
            "source_files_modified": False, "scope": "Complete developer review coverage; not independent or product acceptance"}
        (attempt / "COVERAGE.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": attempt.relative_to(ROOT).as_posix(), **{k: report[k] for k in ("binding_validation", "reviewed_outputs", "reviewed_criteria", "verdict_counts", "new_model_calls")}}, ensure_ascii=False))
    except Exception:
        (attempt / "BINDING_FAILURE.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise

if __name__ == "__main__":
    main()
