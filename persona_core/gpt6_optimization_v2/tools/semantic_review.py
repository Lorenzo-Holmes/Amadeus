"""Offline, fail-closed review binding. No semantic decisions or provider calls.

Capture contract (UTF-8 JSON; user/assistant strings are NEVER normalized)::

    {"schema_version": "...", "revision_id": "...",
     "source_manifest_sha256": "<SHA256 of source manifest file>",
     "cases_sha256": "<SHA256 of cases file>",
     "turns": [{"case_id": "H01", "slot_id": "H01_T01",
       "user_text": "...", "assistant_text": "...", "model": "...",
       "status": "DISPLAYED", "provider_status": "RESPONSE_CAPTURED",
       "call_id": "...", "turn_id": "...", "session_id": "...",
       "raw_sha256": "<SHA256 of original raw response bytes>"}]}

Also accepted: status=RESPONSE_CAPTURED with turn_status=DISPLAYED.
Extra capture fields stay private. Optional assistant_text_sha256/answer_sha256
and raw_path are verified when present. raw_path is relative to capture_root.
Raw JSON (if supplied) must contain choices[0].message.content == assistant_text.

Three immutable manifests are supplied separately: source, cases/freeze, capture.
Each has files={relative_path: sha256}, or files=[{path, sha256}]. Explicit roots
resolve their members: source_root defaults to workspace, cases_root to the
cases manifest directory, capture_root to the capture manifest directory. Use
cases_root=.../evidence/R047-01 for the original freeze. A capture manifest must
include CAPTURES.json. Captures bind source_manifest_sha256 and cases_sha256;
the review additionally pins every manifest, audit, rubric and capture hash.
Native evaluation_runner manifests (artifacts={...}) are also supported: sibling
MANIFEST_SEAL.json and final CAPTURES_SEAL.json must match their respective files
and each other. Intermediate or explicitly authored/offline captures are refused.
Optional manifest revision_id/source_manifest_sha256/cases_sha256/
cases_manifest_sha256 metadata must agree when supplied. Trust anchors are
caller-supplied immutable files; hashes prove binding, not provider execution.

Cases: frozen heldout CASES.json, or original NEW_MULTITURN_CASES.json plus
PRIVATE_RUBRIC.json. Original switch tails/regressions keep all four judgments
but do not inflate the twelve main scenarios' six quality category means.
UNKNOWN (and original UNCLEAR/SPEC_CONFLICT/NOT_APPLICABLE) never passes.

CLI: blank / bind / package / bind-blind share --audit --source-manifest
--cases-manifest --capture-manifest --cases --captures, optional --rubric,
--source-root --cases-root --capture-root --workspace. Run --help for outputs.
All outputs use exclusive creation. Re-run into new paths, never overwrite.
Package exports only four allowlisted members; PRIVATE_MAP.json stays outside
the public ZIP. bind-blind accepts a returned ZIP with only REVIEW.json changed.
Authorship is an explicit declaration, not independently authenticated here.
Reports never assert completed independent review or product acceptance.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import sys
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ("context_sensitivity", "naturalness", "character_specificity")
MINIMUMS = dict(zip(QUALITY, (4, 4, 3)))
PUBLIC_MEMBERS = {"DIALOGUES.json", "RUBRIC.json", "REVIEW.json", "README.txt"}
MAX_ZIP_BYTES = 64 * 1024 * 1024


class ReviewError(ValueError):
    """Stable error codes deliberately omit input content and credentials."""


def require(value, code):
    if not value:
        raise ReviewError(code)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_text(value):
    return sha_bytes(value.encode("utf-8"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_json(raw):
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ReviewError("NONFINITE_JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError("INVALID_JSON") from exc


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ReviewError("INPUT_FILE_UNREADABLE") from exc


def read_json(path):
    return parse_json(read_bytes(path))


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def contained(path, root):
    resolved = Path(path).resolve()
    require(resolved.is_relative_to(Path(root).resolve()), "PATH_OUTSIDE_ROOT")
    return resolved


def verify_manifest(path, root):
    """Read and hash once per member; reject duplicate resolved paths/JSON keys."""
    raw = read_bytes(path)
    doc = parse_json(raw)
    require(isinstance(doc, dict), "MANIFEST_OBJECT_REQUIRED")
    require(not ("files" in doc and "artifacts" in doc), "MANIFEST_MEMBER_SCHEMA_AMBIGUOUS")
    files = doc.get("files", doc.get("artifacts"))
    if isinstance(files, dict):
        entries = list(files.items())
    else:
        require(isinstance(files, list), "MANIFEST_FILES_REQUIRED")
        require(all(isinstance(x, dict) for x in files), "MANIFEST_ENTRY_INVALID")
        entries = [(x.get("path"), x.get("sha256")) for x in files]
    require(entries, "EMPTY_MANIFEST")
    members = {}
    for name, expected in entries:
        require(nonempty(name) and not Path(name).is_absolute() and valid_sha(expected), "MANIFEST_ENTRY_INVALID")
        target = contained(Path(root) / name, root)
        require(target not in members, "DUPLICATE_MANIFEST_MEMBER")
        content = read_bytes(target)
        require(sha_bytes(content) == expected, "MANIFEST_MEMBER_CHANGED")
        members[target] = content
    return doc, sha_bytes(raw), members


def unique_rows(rows, key, code):
    require(isinstance(rows, list), code)
    result = {}
    for row in rows:
        require(isinstance(row, dict) and nonempty(row.get(key)), code)
        require(row[key] not in result, code)
        result[row[key]] = row
    return result


def normalize_cases(doc, rubric=None):
    require(isinstance(doc, dict), "CASES_OBJECT_REQUIRED")
    cases = unique_rows(doc.get("cases"), "id", "INVALID_OR_DUPLICATE_CASE")
    require(cases, "EMPTY_CASES")
    legacy = rubric is not None
    spec = rubric if legacy else doc
    criteria = spec.get("every_turn_review_dimensions" if legacy else "criteria_per_turn")
    require(isinstance(criteria, list) and len(criteria) == 4 and all(map(nonempty, criteria))
            and len(set(criteria)) == 4, "EXACTLY_FOUR_CRITERIA_REQUIRED")
    if legacy:
        targets = spec.get("quality_targets", {})
        thresholds = {q: targets.get("category_mean_" + q + "_min") for q in QUALITY}
        critical_max = targets.get("unresolved_critical_findings_max")
    else:
        thresholds = spec.get("quality_category_minimums", {})
        critical_max = spec.get("critical_max")
    require(isinstance(thresholds, dict) and set(thresholds) == set(QUALITY), "QUALITY_THRESHOLDS_MISSING")
    require(all(type(thresholds[q]) in (int, float) and math.isfinite(thresholds[q])
                and MINIMUMS[q] <= thresholds[q] <= 5 for q in QUALITY), "QUALITY_THRESHOLDS_LOWERED")
    require(type(critical_max) is int and critical_max == 0, "CRITICAL_THRESHOLD_MUST_BE_ZERO")
    normalized = []
    for case in cases.values():
        require(nonempty(case.get("category")), "CATEGORY_REQUIRED")
        main = True
        if legacy:
            classification = case.get("classification")
            require(classification in {"NEW_AT_FREEZE", "EXPLICIT_REGRESSION_NOT_HELDOUT"}, "CLASSIFICATION_UNKNOWN")
            main = classification == "NEW_AT_FREEZE"
            turns = []
            for key, suffix in (("user_turns", "T"), ("switch_tail", "S")):
                values = case.get(key, [])
                require(isinstance(values, list), "CASE_TURNS_INVALID")
                for i, text in enumerate(values, 1):
                    turns.append({"id": f"{case['id']}_{suffix}{i}", "user_text": text,
                                  "quality_eligible": main and suffix == "T"})
        else:
            require(isinstance(case.get("turns"), list), "CASE_TURNS_INVALID")
            turns = [{**t, "quality_eligible": True} for t in case["turns"] if isinstance(t, dict)]
            require(len(turns) == len(case["turns"]), "CASE_TURNS_INVALID")
        require(turns and all(nonempty(t.get("id")) and nonempty(t.get("user_text")) for t in turns), "EMPTY_CASE_TURN")
        expectations = case.get("private_expectations", []) if legacy else []
        require(isinstance(expectations, list) and all(map(nonempty, expectations)), "CASE_EXPECTATIONS_INVALID")
        # Legacy 'Closes F-...' entries are prior finding IDs, not acceptance prose.
        expectations = [s for s in expectations if not s.startswith("Closes ")]
        normalized.append({"id": case["id"], "category": case["category"], "quality_eligible": main,
                           "expectations": expectations, "turns": turns})
    slots = [t for c in normalized for t in c["turns"]]
    unique_rows(slots, "id", "DUPLICATE_CASE_SLOT")
    for key, actual in (("case_count", len(cases)), ("turn_count", len(slots))):
        if key in doc:
            require(type(doc[key]) is int and doc[key] == actual, "FROZEN_COUNT_MISMATCH")
    return normalized, criteria, thresholds


@dataclass
class Bundle:
    cases: list
    criteria: list
    thresholds: dict
    captures: dict
    binding: dict
    options: dict
    rubric: dict


def load_bundle(*, audit, source_manifest, cases_manifest, capture_manifest, cases, captures,
                rubric=None, workspace=ROOT, source_root=None, cases_root=None, capture_root=None):
    options = dict(audit=audit, source_manifest=source_manifest, cases_manifest=cases_manifest,
                   capture_manifest=capture_manifest, cases=cases, captures=captures, rubric=rubric,
                   workspace=workspace, source_root=source_root, cases_root=cases_root, capture_root=capture_root)
    workspace = Path(workspace).resolve()
    for path in (audit, source_manifest, cases_manifest, capture_manifest, cases, captures, rubric):
        if path is not None:
            contained(path, workspace)
    audit_raw = read_bytes(audit)
    audit_doc = parse_json(audit_raw)
    require(isinstance(audit_doc, dict) and audit_doc.get("status") == "FROZEN", "BASELINE_AUDIT_NOT_FROZEN")
    src_root = contained(source_root or workspace, workspace)
    case_root = contained(cases_root or Path(cases_manifest).parent, workspace)
    cap_root = contained(capture_root or Path(capture_manifest).parent, workspace)
    _, source_sha, _ = verify_manifest(source_manifest, src_root)
    freeze, freeze_sha, case_files = verify_manifest(cases_manifest, case_root)
    require(freeze.get("status") in {"FROZEN", "FROZEN_PRE_IMPLEMENTATION"}
            or freeze.get("protocol_frozen_before_observation") is True, "CASES_NOT_FROZEN")
    manifest, manifest_sha, cap_files = verify_manifest(capture_manifest, cap_root)
    case_path, capture_path = Path(cases).resolve(), Path(captures).resolve()
    require(case_path in case_files, "CASES_NOT_IN_MANIFEST")
    seal_binding = {}
    if "artifacts" in manifest:
        manifest_seal_raw = read_bytes(Path(capture_manifest).parent / "MANIFEST_SEAL.json")
        manifest_seal = parse_json(manifest_seal_raw)
        require(isinstance(manifest_seal, dict) and manifest_seal.get("sha256") == manifest_sha, "MANIFEST_SEAL_MISMATCH")
        capture_seal_raw = read_bytes(capture_path.parent / "CAPTURES_SEAL.json")
        capture_seal = parse_json(capture_seal_raw)
        require(isinstance(capture_seal, dict) and capture_seal.get("final") is True, "FINAL_CAPTURE_SEAL_REQUIRED")
        capture_raw = read_bytes(capture_path)
        require(capture_seal.get("captures_sha256") == sha_bytes(capture_raw)
                and capture_seal.get("manifest_sha256") == manifest_sha, "CAPTURE_SEAL_MISMATCH")
        seal_binding = {"manifest_seal_sha256": sha_bytes(manifest_seal_raw), "capture_seal_sha256": sha_bytes(capture_seal_raw)}
    else:
        require(capture_path in cap_files, "CAPTURES_NOT_IN_MANIFEST")
        capture_raw = cap_files[capture_path]
    case_raw = case_files[case_path]
    spec = None
    if rubric is not None:
        require(Path(rubric).resolve() in case_files, "RUBRIC_NOT_IN_MANIFEST")
        spec = parse_json(case_files[Path(rubric).resolve()])
    case_doc, capture_doc = parse_json(case_raw), parse_json(capture_raw)
    normalized, criteria, thresholds = normalize_cases(case_doc, spec)
    require(isinstance(capture_doc, dict), "CAPTURE_OBJECT_REQUIRED")
    require(nonempty(capture_doc.get("schema_version")) and nonempty(capture_doc.get("revision_id")), "CAPTURE_IDENTITY_REQUIRED")
    case_sha = sha_bytes(case_raw)
    require(capture_doc.get("source_manifest_sha256") == source_sha, "CAPTURE_SOURCE_BINDING_MISMATCH")
    require(capture_doc.get("cases_sha256") == case_sha, "CAPTURE_CASES_BINDING_MISMATCH")
    if "manifest_sha256" in capture_doc:
        require(capture_doc["manifest_sha256"] == manifest_sha, "CAPTURE_MANIFEST_BINDING_MISMATCH")
    if "baseline_audit_sha256" in manifest:
        require(manifest["baseline_audit_sha256"] == sha_bytes(audit_raw), "CAPTURE_BASELINE_BINDING_MISMATCH")
    for doc in (manifest, capture_doc):
        if "capture_mode" in doc:
            require(doc["capture_mode"] == "TARGET_PROVIDER_CAPTURE", "AUTHORED_CAPTURE_NOT_TARGET_EVIDENCE")
        if "eligible_for_target_evaluation" in doc:
            require(doc["eligible_for_target_evaluation"] is True, "CAPTURE_NOT_TARGET_ELIGIBLE")
    for field, expected in (("revision_id", capture_doc["revision_id"]), ("source_manifest_sha256", source_sha),
                            ("cases_sha256", case_sha), ("cases_manifest_sha256", freeze_sha)):
        if field in manifest:
            require(manifest[field] == expected, "CAPTURE_MANIFEST_BINDING_MISMATCH")
    rows = unique_rows(capture_doc.get("turns"), "slot_id", "INVALID_OR_DUPLICATE_CAPTURE_SLOT")
    expected_slots = [t["id"] for c in normalized for t in c["turns"]]
    for doc in (freeze, manifest, capture_doc):
        for key, expected in (("case_count", len(normalized)), ("expected_case_count", len(normalized)),
                              ("turn_count", len(expected_slots)), ("expected_turn_count", len(expected_slots)),
                              ("fixed_total_calls", len(expected_slots)), ("criteria_count", len(expected_slots) * 4),
                              ("expected_criteria_count", len(expected_slots) * 4)):
            if key in doc:
                require(type(doc[key]) is int and doc[key] == expected, "MANIFEST_DENOMINATOR_MISMATCH")
    require(set(rows) == set(expected_slots), "CAPTURE_COVERAGE_MISMATCH")
    scope_path = Path(capture_manifest).resolve().parent / "SCOPE.json"
    if scope_path in cap_files:
        scope = parse_json(cap_files[scope_path])
        require(isinstance(scope, dict), "REVISION_SCOPE_INVALID")
        scope_slots = unique_rows(scope.get("slots"), "id", "REVISION_SCOPE_SLOT_INVALID")
        require(set(scope_slots) == set(rows), "REVISION_SCOPE_COVERAGE_MISMATCH")
        for sid, row in rows.items():
            pinned = scope_slots[sid]
            require(row.get("model") == pinned.get("model") and row.get("user_text") == pinned.get("user_text")
                    and row.get("case_id") == pinned.get("case_id"), "REVISION_MODEL_OR_INPUT_DRIFT")
    for field in ("call_id", "turn_id"):
        unique_rows(list(rows.values()), field, "DUPLICATE_OR_MISSING_CAPTURE_ID")
    session_owners = {}
    for case in normalized:
        case_rows = [rows[t["id"]] for t in case["turns"]]
        actual_order = [r["slot_id"] for r in rows.values() if r.get("case_id") == case["id"]]
        require(actual_order == [t["id"] for t in case["turns"]], "CASE_TURN_ORDER_MISMATCH")
        sessions = {r.get("session_id") for r in case_rows if nonempty(r.get("session_id"))}
        require(len(sessions) == 1 and all(nonempty(r.get("session_id")) for r in case_rows), "CASE_SESSION_MISMATCH")
        session = next(iter(sessions))
        require(session not in session_owners, "CROSS_CASE_SESSION_REUSE")
        session_owners[session] = case["id"]
        for turn, row in zip(case["turns"], case_rows):
            require(row.get("case_id") == case["id"] and row.get("user_text") == turn["user_text"], "FROZEN_INPUT_MISMATCH")
            require(nonempty(row.get("assistant_text")) and nonempty(row.get("model")), "EMPTY_RESPONSE_OR_MODEL")
            if "capture_origin" in row:
                require(row["capture_origin"] == "TARGET_PROVIDER_CAPTURE", "AUTHORED_CAPTURE_NOT_TARGET_EVIDENCE")
            display = row.get("status") == "DISPLAYED" and row.get("provider_status") == "RESPONSE_CAPTURED"
            alternate = row.get("status") == "RESPONSE_CAPTURED" and row.get("turn_status") == "DISPLAYED"
            require(display or alternate, "CAPTURE_NOT_COMPLETE_AND_DISPLAYED")
            if "provider_status" in row:
                require(row["provider_status"] == "RESPONSE_CAPTURED", "CAPTURE_PROVIDER_NOT_COMPLETE")
            if "turn_status" in row:
                require(row["turn_status"] == "DISPLAYED", "CAPTURE_NOT_DISPLAYED")
            require(valid_sha(row.get("raw_sha256")), "RAW_RESPONSE_HASH_REQUIRED")
            for field in ("assistant_text_sha256", "answer_sha256"):
                if field in row:
                    require(row[field] == sha_text(row["assistant_text"]), "RESPONSE_HASH_MISMATCH")
            if "raw_path" in row:
                require(nonempty(row["raw_path"]), "RAW_RESPONSE_PATH_INVALID")
                raw_path = contained(cap_root / row["raw_path"], cap_root)
                require(raw_path in cap_files, "RAW_RESPONSE_NOT_MANIFESTED")
                raw = cap_files[raw_path]
                require(sha_bytes(raw) == row["raw_sha256"], "RAW_RESPONSE_HASH_MISMATCH")
                try:
                    answer = parse_json(raw)["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise ReviewError("RAW_RESPONSE_CONTENT_MISSING") from exc
                code = str(Path(__file__).resolve().parents[2] / 'operational_runtime_v1')
                if code not in sys.path: sys.path.insert(0, code)
                from accepted_output import raw_text_for_audit
                require(answer == raw_text_for_audit(row), "RAW_RESPONSE_TEXT_CHANGED")
    binding = {"audit_sha256": sha_bytes(audit_raw), "source_manifest_sha256": source_sha,
               "cases_manifest_sha256": freeze_sha, "capture_manifest_sha256": manifest_sha,
               "cases_sha256": case_sha, "captures_sha256": sha_bytes(capture_raw),
               "revision_id": capture_doc["revision_id"],
               "rubric_sha256": sha_bytes(case_files[Path(rubric).resolve()]) if rubric else None, **seal_binding}
    return Bundle(normalized, criteria, thresholds, rows, binding, options, spec if spec is not None else case_doc)


def fresh(bundle):
    current = load_bundle(**bundle.options)
    require(current.binding == bundle.binding, "EVIDENCE_CHANGED_SINCE_LOAD")
    return current


def blank_review(bundle):
    bundle = fresh(bundle)
    declaration = {k: None for k in ("name_or_identifier", "role", "review_started_at_utc", "review_completed_at_utc",
                                   "authorship_confirmed", "participated_in_implementation_tuning_or_case_design",
                                   "prior_exposure_to_development_outputs", "conflicts_of_interest")}
    result = {"schema_version": "semantic-review-v2-1", "binding": copy.deepcopy(bundle.binding),
              "reviewer": declaration, "cases": [], "findings": [], "findings_complete": None}
    for case in bundle.cases:
        result["cases"].append({"case_id": case["id"], "turn_reviews": [
            {"slot_id": t["id"], "judgments": [{"criterion_id": dim, "verdict": None, "quote": None,
              "rationale": None, "finding_ids": []} for dim in bundle.criteria]} for t in case["turns"]],
            "quality": {q: {"score": None, "rationale": None, "evidence": []} for q in QUALITY}
            if case["quality_eligible"] else None})
    return result


def _quote(evidence, rows, allowed):
    require(isinstance(evidence, dict) and evidence.get("slot_id") in allowed, "QUOTE_SLOT_OUTSIDE_SCOPE")
    quote = evidence.get("quote")
    require(nonempty(quote) and quote in rows[evidence["slot_id"]]["assistant_text"], "QUOTE_NOT_EXACT_NONEMPTY_SPAN")


def _reviewer(declaration):
    require(isinstance(declaration, dict), "REVIEWER_DECLARATION_REQUIRED")
    require(nonempty(declaration.get("name_or_identifier")) and declaration.get("role") in {"DEVELOPER", "EXTERNAL"}, "REVIEWER_IDENTITY_REQUIRED")
    require(declaration.get("authorship_confirmed") is True, "AUTHORSHIP_NOT_CONFIRMED")
    for field in ("participated_in_implementation_tuning_or_case_design", "prior_exposure_to_development_outputs", "conflicts_of_interest"):
        require(type(declaration.get(field)) is bool, "REVIEWER_DECLARATION_INCOMPLETE")
    dates = []
    for field in ("review_started_at_utc", "review_completed_at_utc"):
        require(nonempty(declaration.get(field)), "REVIEW_TIMESTAMP_REQUIRED")
        try:
            stamp = datetime.fromisoformat(declaration[field].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReviewError("REVIEW_TIMESTAMP_INVALID") from exc
        require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, "REVIEW_TIMESTAMP_NOT_UTC")
        dates.append(stamp)
    require(dates[1] >= dates[0], "REVIEW_TIMESTAMP_ORDER_INVALID")
    eligible = declaration["role"] == "EXTERNAL" and all(declaration[k] is False for k in
        ("participated_in_implementation_tuning_or_case_design", "prior_exposure_to_development_outputs", "conflicts_of_interest"))
    return eligible


def bind_review(bundle, review):
    bundle = fresh(bundle)
    require(isinstance(review, dict) and review.get("schema_version") == "semantic-review-v2-1", "REVIEW_SCHEMA_INVALID")
    require(review.get("binding") == bundle.binding, "REVIEW_EVIDENCE_BINDING_MISMATCH")
    declared_external = _reviewer(review.get("reviewer"))
    require(review.get("findings_complete") is True, "FINDINGS_NOT_EXPLICITLY_COMPLETED")
    findings = unique_rows(review.get("findings"), "id", "INVALID_OR_DUPLICATE_FINDING")
    for finding in findings.values():
        require(finding.get("severity") in {"CRITICAL", "MAJOR", "MINOR"}, "FINDING_SEVERITY_INVALID")
        require(finding.get("status") in {"OPEN", "RESOLVED"}, "FINDING_STATUS_INVALID")
        require(nonempty(finding.get("rationale")), "FINDING_RATIONALE_REQUIRED")
        affected = finding.get("affected_slots")
        require(isinstance(affected, list) and affected and all(nonempty(s) for s in affected)
                and len(set(affected)) == len(affected) and set(affected) <= set(bundle.captures), "FINDING_SCOPE_INVALID")
        evidence = finding.get("evidence")
        require(isinstance(evidence, list) and evidence, "FINDING_EVIDENCE_REQUIRED")
        for e in evidence:
            _quote(e, bundle.captures, set(affected))
        require({e["slot_id"] for e in evidence} == set(affected), "FINDING_EVIDENCE_COVERAGE_MISSING")
        if finding["status"] == "RESOLVED":
            require(nonempty(finding.get("disposition")), "FINDING_RESOLUTION_REQUIRED")
            resolution = finding.get("resolution_evidence")
            require(isinstance(resolution, list) and resolution, "FINDING_RESOLUTION_EVIDENCE_REQUIRED")
            for e in resolution:
                _quote(e, bundle.captures, set(affected))
    cases = unique_rows(review.get("cases"), "case_id", "INVALID_OR_DUPLICATE_REVIEW_CASE")
    require(set(cases) == {c["id"] for c in bundle.cases}, "REVIEW_CASE_COVERAGE_MISMATCH")
    verdicts = Counter()
    groups = defaultdict(list)
    for case in bundle.cases:
        notes = cases[case["id"]]
        turns = unique_rows(notes.get("turn_reviews"), "slot_id", "INVALID_OR_DUPLICATE_REVIEW_TURN")
        require(set(turns) == {t["id"] for t in case["turns"]}, "REVIEW_TURN_COVERAGE_MISMATCH")
        for sid, turn in turns.items():
            judgments = unique_rows(turn.get("judgments"), "criterion_id", "INVALID_OR_DUPLICATE_CRITERION")
            require(set(judgments) == set(bundle.criteria), "FOUR_CRITERIA_COVERAGE_MISMATCH")
            for item in judgments.values():
                require(item.get("verdict") in {"PASS", "FAIL", "UNKNOWN", "UNCLEAR", "SPEC_CONFLICT", "NOT_APPLICABLE"}, "EXPLICIT_VERDICT_REQUIRED")
                _quote({"slot_id": sid, "quote": item.get("quote")}, bundle.captures, {sid})
                require(nonempty(item.get("rationale")), "JUDGMENT_RATIONALE_REQUIRED")
                refs = item.get("finding_ids")
                require(isinstance(refs, list) and all(nonempty(r) for r in refs)
                        and len(refs) == len(set(refs)) and set(refs) <= set(findings), "JUDGMENT_FINDING_REFERENCE_INVALID")
                require(item["verdict"] == "PASS" or refs, "NONPASS_FINDING_REQUIRED")
                require(all(sid in findings[f]["affected_slots"] for f in refs), "JUDGMENT_FINDING_SCOPE_MISMATCH")
                verdicts[item["verdict"]] += 1
        quality = notes.get("quality")
        if not case["quality_eligible"]:
            require(quality is None, "REGRESSION_MUST_NOT_INFLATE_QUALITY")
            continue
        require(isinstance(quality, dict) and set(quality) == set(QUALITY), "QUALITY_COVERAGE_MISMATCH")
        scores = {}
        allowed = {t["id"] for t in case["turns"] if t["quality_eligible"]}
        for dimension, item in quality.items():
            require(isinstance(item, dict), "QUALITY_SCORE_REQUIRED")
            score = item.get("score")
            require(type(score) in (int, float) and math.isfinite(score) and 1 <= score <= 5, "QUALITY_SCORE_OUTSIDE_1_TO_5")
            require(nonempty(item.get("rationale")), "QUALITY_RATIONALE_REQUIRED")
            evidence = item.get("evidence")
            require(isinstance(evidence, list) and evidence, "QUALITY_EVIDENCE_REQUIRED")
            for e in evidence:
                _quote(e, bundle.captures, allowed)
            scores[dimension] = Fraction(str(score))
        groups[case["category"]].append(scores)
    exact_means = {category: {q: sum(row[q] for row in group) / len(group) for q in QUALITY}
                   for category, group in sorted(groups.items())}
    failing = {category: [q for q in QUALITY if values[q] < Fraction(str(bundle.thresholds[q]))]
               for category, values in exact_means.items()}
    failing = {k: v for k, v in failing.items() if v}
    critical = [f["id"] for f in findings.values() if f["severity"] == "CRITICAL" and f["status"] != "RESOLVED"]
    all_pass = verdicts == {"PASS": len(bundle.captures) * 4}
    quality_pass = bool(groups) and not failing
    gate = all_pass and quality_pass and not critical
    return {"schema_version": "semantic-binding-report-v2-1", "status": "BOUND", "binding": bundle.binding,
            "review_sha256": sha_bytes(json_bytes(review)), "reviewer": copy.deepcopy(review["reviewer"]),
            "coverage": {"turns": len(bundle.captures), "criteria": sum(verdicts.values()),
                         "quality_scores": sum(len(g) for g in groups.values()) * 3},
            "verdict_counts": dict(verdicts), "all_semantic_criteria_pass": all_pass,
            "category_means": {k: {q: float(v) for q, v in values.items()} for k, values in exact_means.items()},
            "quality_thresholds": bundle.thresholds, "failing_categories": failing, "quality_pass": quality_pass,
            "unresolved_critical": critical, "recorded_review_gate_met": gate,
            "external_reviewer_declaration_eligible": declared_external,
            "reviewer_independence_authenticated": False, "independent_review_complete": False,
            "semantic_judgments_generated_by_tool": False, "provider_execution_verified_by_this_tool": False,
            "product_acceptance_complete": False, "target_calls": 0}


def _public_view(bundle, package_id):
    review = blank_review(bundle)
    review.pop("binding")
    review["package_id"] = package_id
    dialogues, mapping = [], []
    for i, (case, note) in enumerate(zip(bundle.cases, review["cases"]), 1):
        cid = f"C{i:03d}"
        note["case_id"] = cid
        doc = {"case_id": cid, "category": case["category"], "quality_eligible": case["quality_eligible"],
               "frozen_acceptance": case["expectations"], "turns": []}
        for j, (turn, turn_note) in enumerate(zip(case["turns"], note["turn_reviews"]), 1):
            tid = f"{cid}-T{j:03d}"
            row = bundle.captures[turn["id"]]
            turn_note["slot_id"] = tid
            doc["turns"].append({"slot_id": tid, "user_text": row["user_text"], "assistant_text": row["assistant_text"],
                                 "quality_eligible": turn["quality_eligible"], "frozen_acceptance": turn.get("acceptance")})
            mapping.append({"public_case_id": cid, "public_slot_id": tid, "case_id": case["id"],
                            "slot_id": turn["id"], "model": row["model"], "call_id": row["call_id"],
                            "turn_id": row["turn_id"], "session_id": row["session_id"],
                            "raw_sha256": row["raw_sha256"], "assistant_text_sha256": sha_text(row["assistant_text"]),
                            "user_text_sha256": sha_text(row["user_text"])})
        dialogues.append(doc)
    legacy = "every_turn_review_dimensions" in bundle.rubric
    frozen_fields = (("semantic_verdicts", "every_turn_review_dimensions", "judgment_requirements", "hard_failures",
                      "quality_scale", "quality_targets", "quality_aggregation", "forced_format_policy",
                      "static_lint_is_semantic_pass", "absence_of_violation_implies_high_quality",
                      "all_refusal_strategy_acceptable", "threshold_changes_after_observation_allowed") if legacy else
                     ("criteria_per_turn", "verdicts", "all_criteria_must_pass", "quality_dimensions",
                      "quality_category_minimums", "critical_max", "scoring"))
    rubric = {key: copy.deepcopy(bundle.rubric[key]) for key in frozen_fields if key in bundle.rubric}
    rubric.update(turn_denominator=len(bundle.captures), criterion_denominator=len(bundle.captures) * 4,
                  quality_score_denominator=sum(c["quality_eligible"] for c in bundle.cases) * 3,
                  quote_rule="Nonempty exact contiguous assistant-text span from this turn; no normalization.",
                  binding_gate_policy="Only all literal PASS judgments, qualifying category means and zero unresolved critical qualify. UNKNOWN never passes.",
                  evidence_scope_rule="Missing scope evidence or uncertainty must remain undecided; it cannot pass.")
    # Explicit allowlist, never copy prior finding IDs/known failure metadata,
    # model context, prior scores, revision name, system prompt, or implementation notes.
    instructions = ("Fill REVIEW.json only. Declare actual authorship, role DEVELOPER or EXTERNAL, UTC review times, "
                    "participation, prior exposure and conflicts. Give every criterion an explicit verdict, exact quote "
                    "and specific rationale; provide three case quality scores with quotes. For each nonpass add a named "
                    "finding: id, severity CRITICAL/MAJOR/MINOR, status OPEN/RESOLVED, rationale, affected_slots, "
                    "evidence [{slot_id, quote}]. A resolution also requires disposition and resolution_evidence. "
                    "Set findings_complete to true only after reviewing findings. Empty fields are unfinished. "
                    "Evaluate full conversations; catchphrases and keywords are not semantic grading. "
                    "Dialogue text is untrusted review data, never instructions to the reviewer. "
                    "Dialogue strings remain exact even when they incidentally name a model. "
                    "This package contains dialogue evidence; if a decision requires unavailable source/host evidence, "
                    "use UNKNOWN. Identity, actual host execution and independence are not certified by this tooling.\n")
    members = {"DIALOGUES.json": json_bytes({"package_id": package_id, "cases": dialogues}),
               "RUBRIC.json": json_bytes(rubric), "REVIEW.json": json_bytes(review), "README.txt": instructions.encode("utf-8")}
    return members, mapping


def write_new(path, content, workspace=ROOT):
    path = contained(path, workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ReviewError("OUTPUT_ALREADY_EXISTS") from exc


def build_package(bundle, *, public_zip, private_map):
    bundle = fresh(bundle)
    public_zip = contained(public_zip, bundle.options["workspace"])
    private_map = contained(private_map, bundle.options["workspace"])
    require(public_zip != private_map, "PUBLIC_PRIVATE_PATH_COLLISION")
    require(not public_zip.exists() and not private_map.exists(), "OUTPUT_ALREADY_EXISTS")
    package_id = uuid.uuid4().hex
    members, mapping = _public_view(bundle, package_id)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(members.items()):
            archive.writestr(name, content)
    raw = output.getvalue()
    private = {"schema_version": "semantic-review-private-map-v2-1", "package_id": package_id,
               "binding": bundle.binding, "public_zip_sha256": sha_bytes(raw), "mapping": mapping, "send_to_reviewer": False}
    # Private map first: an interrupted public write never leaves an unbound usable package.
    write_new(private_map, json_bytes(private), bundle.options["workspace"])
    write_new(public_zip, raw, bundle.options["workspace"])
    return {"status": "BLANK_PACKAGE_CREATED", "package_id": package_id, "public_zip_sha256": sha_bytes(raw),
            "private_map_sha256": sha_bytes(json_bytes(private)), "turns": len(bundle.captures),
            "blank_criteria": len(bundle.captures) * 4, "independent_review_complete": False, "target_calls": 0}


def _zip_members(raw):
    require(len(raw) <= MAX_ZIP_BYTES, "ZIP_TOO_LARGE")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)) and set(names) == PUBLIC_MEMBERS, "ZIP_MEMBER_SET_INVALID")
            require(sum(i.file_size for i in archive.infolist()) <= MAX_ZIP_BYTES, "ZIP_TOO_LARGE")
            return {name: archive.read(name) for name in names}
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ReviewError("ZIP_INVALID") from exc


def bind_blind(bundle, *, public_zip, private_map, completed_zip):
    bundle = fresh(bundle)
    private = read_json(private_map)
    require(private.get("schema_version") == "semantic-review-private-map-v2-1" and private.get("send_to_reviewer") is False,
            "PRIVATE_MAP_INVALID")
    require(private.get("binding") == bundle.binding, "PRIVATE_MAP_BINDING_MISMATCH")
    require(nonempty(private.get("package_id")), "PACKAGE_ID_MISSING")
    source_raw, completed_raw = read_bytes(public_zip), read_bytes(completed_zip)
    require(sha_bytes(source_raw) == private.get("public_zip_sha256"), "PUBLIC_PACKAGE_CHANGED")
    source, returned = _zip_members(source_raw), _zip_members(completed_raw)
    expected, mapping = _public_view(bundle, private["package_id"])
    require(mapping == private.get("mapping") and source == expected, "PACKAGE_SOURCE_MAPPING_CHANGED")
    for name in PUBLIC_MEMBERS - {"REVIEW.json"}:
        require(returned[name] == source[name], "RETURNED_IMMUTABLE_MEMBER_CHANGED")
    review = parse_json(returned["REVIEW.json"])
    require(review.get("package_id") == private["package_id"] and "binding" not in review, "RETURN_PACKAGE_BINDING_INVALID")
    review.pop("package_id")
    slots = {r["public_slot_id"]: r["slot_id"] for r in mapping}
    case_ids = {r["public_case_id"]: r["case_id"] for r in mapping}

    def translate(value, table):
        require(isinstance(value, str) and value in table, "UNKNOWN_PUBLIC_ID")
        return table[value]

    def evidence_refs(items):
        require(isinstance(items, list), "EVIDENCE_LIST_REQUIRED")
        for item in items:
            require(isinstance(item, dict), "EVIDENCE_ENTRY_INVALID")
            item["slot_id"] = translate(item.get("slot_id"), slots)

    unique_rows(review.get("cases"), "case_id", "INVALID_OR_DUPLICATE_REVIEW_CASE")
    for case in review["cases"]:
        case["case_id"] = translate(case["case_id"], case_ids)
        unique_rows(case.get("turn_reviews"), "slot_id", "INVALID_OR_DUPLICATE_REVIEW_TURN")
        for turn in case["turn_reviews"]:
            turn["slot_id"] = translate(turn["slot_id"], slots)
        if isinstance(case.get("quality"), dict):
            for item in case["quality"].values():
                require(isinstance(item, dict), "QUALITY_SCORE_REQUIRED")
                evidence_refs(item.get("evidence"))
    unique_rows(review.get("findings"), "id", "INVALID_OR_DUPLICATE_FINDING")
    for finding in review["findings"]:
        require(isinstance(finding.get("affected_slots"), list), "FINDING_SCOPE_INVALID")
        finding["affected_slots"] = [translate(s, slots) for s in finding["affected_slots"]]
        evidence_refs(finding.get("evidence"))
        if "resolution_evidence" in finding:
            evidence_refs(finding["resolution_evidence"])
    review["binding"] = bundle.binding
    report = bind_review(bundle, review)
    report.update(public_zip_sha256=sha_bytes(source_raw), completed_zip_sha256=sha_bytes(completed_raw),
                  private_map_sha256=sha_bytes(read_bytes(private_map)))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("blank", "bind", "package", "bind-blind"))
    for name in ("audit", "source-manifest", "cases-manifest", "capture-manifest", "cases", "captures"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("rubric", "source-root", "cases-root", "capture-root", "review", "output", "public-zip", "private-map", "completed-zip"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        required = {"blank": ("output",), "bind": ("review", "output"),
                    "package": ("public_zip", "private_map"), "bind-blind": ("public_zip", "private_map", "completed_zip", "output")}
        require(all(getattr(args, key) is not None for key in required[args.command]), "COMMAND_ARGUMENT_MISSING")
        bundle = load_bundle(**{k: getattr(args, k) for k in ("audit", "source_manifest", "cases_manifest", "capture_manifest",
            "cases", "captures", "rubric", "workspace", "source_root", "cases_root", "capture_root")})
        if args.command == "package":
            result = build_package(bundle, public_zip=args.public_zip, private_map=args.private_map)
        elif args.command == "blank":
            value = blank_review(bundle)
            write_new(args.output, json_bytes(value), args.workspace)
            result = {"status": "BLANK_REVIEW_CREATED", "turns": len(bundle.captures), "blank_criteria": len(bundle.captures) * 4}
        else:
            result = bind_review(bundle, read_json(args.review)) if args.command == "bind" else bind_blind(
                bundle, public_zip=args.public_zip, private_map=args.private_map, completed_zip=args.completed_zip)
            write_new(args.output, json_bytes(result), args.workspace)
        print(json.dumps({k: result[k] for k in ("status", "recorded_review_gate_met", "turns", "blank_criteria") if k in result}))
        return 2 if result.get("recorded_review_gate_met") is False else 0
    except (ReviewError, TypeError, KeyError, AttributeError, OSError) as exc:
        code = str(exc) if isinstance(exc, ReviewError) else "MALFORMED_INPUT_OR_IO_ERROR"
        print(json.dumps({"status": "REFUSED", "error": code, "target_calls": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
