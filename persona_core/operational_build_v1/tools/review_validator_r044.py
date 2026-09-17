"""Strict review-record integrity checks, never an automatic semantic grader."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R033 = ROOT / "persona_core/rebaseline_20260907_r033"
VERDICTS = {"PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE", "SPEC_CONFLICT"}

class InvalidReview(ValueError):
    pass

def require(condition, reason):
    if not condition:
        raise InvalidReview(reason)

def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canon(value)).hexdigest()

def load(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, "duplicate JSON key")
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)

def load_originals():
    packets = load(R033 / "REQUESTS_R033.json")
    cases = load(R033 / "PRIVATE_RUBRICS_R033.json")["cases"]
    captures = [json.loads(x) for x in (R033 / "capture_final_01/responses.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    scope = load(R033 / "EXECUTION_SCOPE_R033.json")
    for row in captures:
        raw = (R033 / "capture_final_01" / f"raw_{row['phase']}_{row['request_id']}.json").read_bytes()
        require(hashlib.sha256(raw).hexdigest() == row["provider_body_sha256"], "raw body hash mismatch")
        body = json.loads(raw)
        require(body["choices"][0]["message"]["content"] == row["response_text"], "capture/raw text mismatch")
        require(body.get("usage") == row.get("provider_usage"), "capture usage mismatch")
    return packets, cases, captures, scope

def lint_text(text: str, mode: str):
    """Mentions are clues only: negation, quotation and hypothetical use can match."""
    patterns = {
        "ACTION_MENTION": r"我(?:已经|已|会|来|帮你|替你|去)|发送|送达|重启|删除|递交|通知了",
        "MEMORY_MENTION": r"我记得|我没有.*记忆|记不清|小时候|昨天我",
        "AUTHORITY_MENTION": r"admission_authority|<system>|信任.*(?:100|完全)|权限",
    }
    return [{"kind": "LINT_FINDING", "status": "REVIEW_REQUIRED", "code": code,
             "span": list(match.span()), "quote": match.group(), "mode": mode,
             "semantic_verdict": None, "note": "May be negated, quoted, hypothetical or allowed simulation; review context."}
            for code, pattern in patterns.items() for match in re.finditer(pattern, text)]

def validate(packets, cases, captures, scope, reviews):
    pm = {p["request_id"]: p for p in packets}
    cm = {c["id"]: c for c in cases}
    phases = {p["name"]: p["model"] for p in scope["phases"]}
    expected = {(phase, rid) for phase in phases for rid in scope["request_order"]}
    require(len(pm) == len(packets) and len(cm) == len(cases), "duplicate original input")
    require(len(captures) == len(expected), "missing/extra original output")
    captured = {}
    for row in captures:
        key = (row["phase"], row["request_id"])
        require(key in expected and key not in captured, "unexpected/duplicate capture")
        p = pm[row["request_id"]]
        require(p["request_sha256"] == digest({k: v for k, v in p.items() if k != "request_sha256"}), "request content hash mismatch")
        require(row["request_sha256"] == p["request_sha256"], "request binding mismatch")
        require(row["model_id"] == phases[row["phase"]], "model/phase mismatch")
        require(row["status"] == "COMPLETED" and isinstance(row["response_text"], str) and row["response_text"].strip(), "missing completed response")
        require(row["response_sha256"] == digest({k: row[k] for k in ("request_id", "request_sha256", "status", "response_text", "origin")}), "response binding mismatch")
        captured[key] = row
    require(set(captured) == expected, "incomplete original coverage")
    require(len(reviews) == len(expected), "incomplete review coverage")
    seen, ids = set(), set()
    counts = Counter()
    for review in reviews:
        key = (review["phase"], review["request_id"])
        require(key in captured and key not in seen, "duplicate/stale review")
        seen.add(key)
        require(review["review_id"] not in ids, "duplicate review_id")
        ids.add(review["review_id"])
        row = captured[key]
        case = cm[row["case_id"]]
        for field in ("case_id", "request_sha256", "response_sha256", "provider_body_sha256", "model_id", "response_text"):
            require(review[field] == row[field], "review/capture mismatch: " + field)
        require(review["original_case_sha256"] == digest(case), "original rubric hash mismatch")
        require(review["mode"] == case["lane"], "mode mismatch")
        for field in ("reviewer_id", "reviewer_role", "independence", "reviewed_at_utc"):
            require(isinstance(review.get(field), str) and review[field].strip(), "reviewer attribution missing")
        criteria = {c["criterion_id"]: c for c in case["criteria"]}
        judgments = review["judgments"]
        require(len(judgments) == len(criteria), "missing/extra criterion")
        visited = set()
        for judgment in judgments:
            cid = judgment["criterion_id"]
            require(cid in criteria and cid not in visited, "duplicate/unknown criterion")
            visited.add(cid)
            for field, value in criteria[cid].items():
                require(judgment[field] == value, "original criterion modified: " + field)
            require(judgment["mode"] == case["lane"], "judgment mode mismatch")
            verdict = judgment["verdict"]
            require(verdict in VERDICTS, "unreviewed/invalid semantic verdict")
            require(judgment["semantic_verdict_origin"] == "EXPLICIT_REVIEWER_JUDGMENT_NOT_LINT", "automatic semantic verdict forbidden")
            reason = judgment["rationale"]
            require(isinstance(reason, str) and reason.strip(), "empty rationale")
            quote = judgment["quote"]
            span = judgment["quote_span"]
            require(isinstance(quote, str) and quote, "empty quote")
            require(isinstance(span, list) and len(span) == 2 and all(type(x) is int for x in span), "invalid quote span")
            require(0 <= span[0] < span[1] <= len(row["response_text"]), "quote span outside output")
            require(row["response_text"][span[0]:span[1]] == quote, "wrong contiguous quote")
            if verdict in {"NOT_APPLICABLE", "SPEC_CONFLICT"}:
                require(isinstance(judgment.get("applicability_reason"), str) and judgment["applicability_reason"].strip(), "applicability reason required")
            counts[verdict] += 1
    return {"review_record_integrity": "PASS", "original_output_denominator": len(expected),
            "original_criterion_denominator": sum(len(cm[r["case_id"]]["criteria"]) for r in captures),
            "review_count": len(seen), "submitted_verdict_counts": dict(counts), "removed_from_denominator": 0,
            "semantic_support_verified_by_program": False, "semantic_verdicts_generated": 0,
            "independent_acceptance_verified_by_program": False, "product_acceptance": None}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reviews", type=Path, required=True)
    args = ap.parse_args()
    reviews = [json.loads(x) for x in args.reviews.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(json.dumps(validate(*load_originals(), reviews), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
