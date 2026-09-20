"""Content-complete real-day snapshots and explicit quote-bound rollup. No calls.

Host/local clock and manual reviewer declarations are not independent human or
time authentication. Structural checks never supply semantic verdicts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

sys.dont_write_bytecode = True
import candidate_day_v2 as g

PROTOCOL_NAMES = ("VALIDATION_PROTOCOL.md", "NATURAL_DAY_RUNBOOK.md")
CRITERIA = ("evidence_and_memory_scope", "context_and_task_fulfillment",
            "authority_and_completion", "continuity_and_attribution")
QUALITY_DIAGNOSTICS = ("context_sensitivity", "naturalness", "character_specificity")
LONGITUDINAL = ("same_identity_after_real_restart", "same_commitment_restored_across_dates",
                "self_report_versus_verifiable_text_fulfillment", "model_switch_preserves_authority_and_relationship")


def protocol_bindings(workspace=g.ROOT):
    directory = Path(workspace) / "persona_core/operational_build_v1/evidence/R047-04"
    return {name: g.ref(directory / name, workspace) for name in PROTOCOL_NAMES}


def ro(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def read_evidence(path):
    db = ro(path)
    try:
        db.execute("BEGIN")
        rows = [dict(r) for r in db.execute("SELECT p.*,t.user_text,t.assistant_text,t.status AS turn_status,t.display_at_utc,"
            "t.input_provenance,t.response_provenance FROM provider_calls p JOIN turns t USING(turn_id) ORDER BY p.submitted_at_utc")]
        scopes = {r['batch_id']: json.loads(r['scope_json']) for r in db.execute('SELECT batch_id,scope_json FROM call_batches')}
        for row in rows:
            if row['status'] == 'RESPONSE_CAPTURED': g.verify_protocol_capture(db, row, scopes[row['batch_id']])
            row.update(g.accepted_projection(db, row, 'evaluation'))
            if isinstance(row["raw_response"], bytes):
                row["raw_response"] = row["raw_response"].decode("utf-8")
        return {"rows": rows, "events": [dict(r) for r in db.execute("SELECT * FROM runtime_events ORDER BY sequence")],
            "event_candidates": [dict(r) for r in db.execute("SELECT * FROM event_candidates ORDER BY created_at_utc,candidate_id")],
            "admission_decisions": [dict(r) for r in db.execute("SELECT * FROM admission_decisions ORDER BY created_at_utc,decision_id")],
            "evidence_receipts": [dict(r) for r in db.execute("SELECT * FROM evidence_receipts ORDER BY created_at_utc,receipt_id")],
            "processes": [dict(r) for r in db.execute("SELECT * FROM cli_process_runs ORDER BY started_at_utc")],
            "sessions": [dict(r) for r in db.execute("SELECT * FROM sessions")],
            "call_batches": [dict(r) for r in db.execute("SELECT * FROM call_batches")],
            "turn_count": db.execute("SELECT count(*) FROM turns").fetchone()[0],
            "current": dict(db.execute("SELECT * FROM runtime_current WHERE singleton=1").fetchone())}
    finally:
        db.close()


def prefixes(evidence):
    return ([{k: row[k] for k in ("call_id", "raw_sha256", "request_sha256")} for row in evidence["rows"]],
            [{k: row[k] for k in ("event_id", "event_sha256")} for row in evidence["events"]])


def content_snapshot(runtime, destination, *, extra_files=None, workspace=g.ROOT):
    """Read-only-source complete snapshot helper; makes no date/candidate claim."""
    g.runtime_modules(workspace)
    recovery = importlib.import_module("recovery")
    runtime_mod = importlib.import_module("runtime_store")
    runtime, destination = g.contained(runtime, workspace), g.contained(destination, workspace)
    g.require(not destination.exists() and not destination.is_relative_to(runtime), "NEW_EXTERNAL_SNAPSHOT_REQUIRED")
    destination.mkdir(parents=True)
    shutil.copy2(runtime / "SANDBOX.json", destination / "SANDBOX.json")
    shutil.copytree(runtime / "legacy_runtime", destination / "legacy_runtime", ignore=shutil.ignore_patterns("__pycache__"))
    code = destination / "source_snapshot"; code.mkdir()
    for path in (Path(workspace) / "persona_core/operational_runtime_v1").glob("*.py"):
        shutil.copy2(path, code / path.name)
    for name, source in (extra_files or {}).items():
        target = g.contained(destination / name, destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        g.require(not target.exists(), "SNAPSHOT_EXTRA_COLLISION")
        shutil.copy2(source, target)
    source = ro(runtime / "runtime.sqlite3")
    target = sqlite3.connect(destination / "runtime.sqlite3")
    try:
        source.backup(target, pages=128, sleep=0.01)
    finally:
        target.close(); source.close()
    saved = ro(destination / "runtime.sqlite3")
    try:
        summary = recovery.logical_summary(saved)
    finally:
        saved.close()
    manifest = {"format": recovery.FORMAT, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": runtime_mod.SCHEMA_VERSION, "reducer_version": runtime_mod.REDUCER_VERSION,
        "content_complete": True, "method": "SQLITE_ONLINE_BACKUP_API", "summary": summary,
        "files": [{"path": p.relative_to(destination).as_posix(), "size": p.stat().st_size, "sha256": g.sha(p)}
                  for p in sorted(destination.rglob("*")) if p.is_file()],
        "archived_code_is_executed": False, "trust_model": "Caller-held hash; local OS owner is trusted, not independently authenticated."}
    g.write_new(destination / "BACKUP_MANIFEST.json", manifest)
    anchor = g.sha(destination / "BACKUP_MANIFEST.json")
    recovery.verify_backup(destination, anchor)
    return {"path": destination, "sha256": anchor, "summary": summary}


@contextmanager
def checkpoint_lock(candidate_path):
    lock_path = Path(candidate_path).parent / "ACTIVE_HOST.json"
    g.require(not lock_path.exists(), "EXIT_HOST_BEFORE_CHECKPOINT")
    lock = {"purpose": "CHECKPOINT_NO_PROVIDER", "pid": os.getpid(), "nonce": uuid.uuid4().hex}
    g.write_new(lock_path, lock)
    try:
        yield
    finally:
        if lock_path.is_file() and g.load(lock_path) == lock:
            lock_path.unlink()


def create_checkpoint(candidate_path, ingress_root, checkpoints_root, workspace=g.ROOT):
    candidate_path = g.contained(candidate_path, workspace)
    g.verify_candidate_bindings(candidate_path, workspace)
    with checkpoint_lock(candidate_path):
        return _checkpoint_locked(candidate_path, ingress_root, checkpoints_root, workspace)


def _checkpoint_locked(candidate_path, ingress_root, checkpoints_root, workspace):
    candidate_path, workspace = Path(candidate_path), Path(workspace)
    observed = g.inspect_day(candidate_path, ingress_root, checkpoints_root, workspace)
    candidate, scope = g.verify_candidate_bindings(candidate_path, workspace)
    runtime = g.resolve(candidate["runtime"], workspace)
    before = read_evidence(runtime / "runtime.sqlite3")
    g.require(before["processes"] and all(p.get("ended_at_utc") is not None for p in before["processes"]), "HOST_PROCESS_NOT_EXITED")
    g.require(prefixes(before) == (observed["calls_prefix"], observed["event_prefix"]), "STATE_CHANGED_BEFORE_SNAPSHOT")
    destination = g.contained(Path(checkpoints_root) / observed["observed_local_date"], workspace)
    g.require(not destination.exists(), "DAY_DESTINATION_EXISTS")
    extras = {"USER_CHAT_SCOPE.json": g.reference(candidate["scope"], workspace)}
    for row in before["rows"]:
        receipt = Path(ingress_root) / (row["turn_id"] + ".json")
        extras["HOST_INGRESS/" + receipt.name] = receipt
        pricing = g.load(receipt)["preflight_record"]["pricing_record"]
        extras["PRICING/" + pricing["sha256"] + ".json"] = g.reference(pricing, workspace)
    for name, binding in candidate["protocol_bindings"].items():
        extras["PROTOCOL/" + name] = g.reference(binding, workspace)
    for name in candidate["host_tool_bindings"]:
        extras["HOST_TOOLS/" + Path(name).name] = g.resolve(name, workspace)
    backup = content_snapshot(runtime, destination / "content_backup", extra_files=extras, workspace=workspace)
    evidence = read_evidence(backup["path"] / "runtime.sqlite3")
    g.require(evidence == before, "STATE_CHANGED_DURING_SNAPSHOT")
    g.require(g.day(datetime.now(timezone.utc).isoformat()) == observed["observed_local_date"], "DATE_CHANGED_DURING_SNAPSHOT")
    g.verify_candidate_bindings(candidate_path, workspace)
    g.write_new(destination / "EVIDENCE.json", evidence)
    result = {**observed, "content_backup_manifest": g.ref(backup["path"] / "BACKUP_MANIFEST.json", workspace),
              "day_evidence": g.ref(destination / "EVIDENCE.json", workspace),
              "genesis_sha256": backup["summary"]["genesis_sha256"], "schema_version_number": backup["summary"]["schema_version"],
              "source_manifest_sha256": candidate["source_manifest"]["sha256"],
              "protocol_bindings": candidate["protocol_bindings"], "host_tool_bindings": candidate["host_tool_bindings"],
              "generation_settings": candidate["generation_settings"], "complete_content_backup": True}
    g.write_new(destination / "CHECKPOINT.json", result)
    return result


def verify_day(path, candidate_path, candidate, scope, workspace):
    checkpoint = g.load(path)
    g.require(checkpoint.get("schema_version") == "g6-real-day-checkpoint-1" and checkpoint.get("qualified_real_user_date") is True
              and checkpoint.get("complete_content_backup") is True, "COMPLETE_REAL_DAY_REQUIRED")
    g.require(checkpoint["candidate_manifest_sha256"] == g.sha(candidate_path) and checkpoint["candidate_id"] == candidate["candidate_id"]
              and checkpoint["session_id"] == candidate["session_id"] and checkpoint["timezone"] == "Asia/Tokyo"
              and checkpoint["observed_local_date"] == g.day(checkpoint["observed_at_utc"])
              and g.utc(checkpoint["observed_at_utc"]) <= datetime.now(timezone.utc), "DAY_IDENTITY_OR_TIME_MISMATCH")
    for key in ("protocol_bindings", "host_tool_bindings", "generation_settings"):
        g.require(checkpoint[key] == candidate[key], "DAY_FROZEN_CONFIG_CHANGED")
    manifest_path = g.reference(checkpoint["content_backup_manifest"], workspace)
    g.require(manifest_path.parent.parent == path.parent, "BACKUP_OUTSIDE_DAY")
    recovery = importlib.import_module("recovery")
    verified = recovery.verify_backup(manifest_path.parent, g.sha(manifest_path))
    g.require(checkpoint["source_manifest_sha256"] == candidate["source_manifest"]["sha256"]
              and checkpoint["schema_version_number"] == verified["summary"]["schema_version"], "DAY_SOURCE_OR_SCHEMA_CHANGED")
    for name, expected in candidate["protocol_bindings"].items():
        g.require(g.sha(manifest_path.parent / "PROTOCOL" / name) == expected["sha256"], "DAY_PROTOCOL_COPY_CHANGED")
    for name, expected in candidate["host_tool_bindings"].items():
        g.require(g.sha(manifest_path.parent / "HOST_TOOLS" / Path(name).name) == expected, "DAY_HOST_TOOL_COPY_CHANGED")
    g.require(verified["summary"]["unresolved_calls"] == [], "UNKNOWN_IN_DAY_BACKUP")
    g.require(checkpoint["genesis_sha256"] == candidate["initialization"]["verification"]["genesis_sha256"]
              == verified["summary"]["genesis_sha256"], "DAY_GENESIS_CHANGED")
    for name, expected in candidate["source_files"].items():
        if name.startswith("persona_core/operational_runtime_v1/") and name.endswith(".py"):
            g.require(g.sha(manifest_path.parent / "source_snapshot" / Path(name).name) == expected, "DAY_CORE_COPY_CHANGED")
    g.require(g.sha(manifest_path.parent / "USER_CHAT_SCOPE.json") == candidate["scope"]["sha256"], "DAY_SCOPE_COPY_CHANGED")
    evidence = read_evidence(manifest_path.parent / "runtime.sqlite3")
    g.require(evidence == g.load(g.reference(checkpoint["day_evidence"], workspace)), "DAY_LOG_DIFFERS_FROM_BACKUP")
    g.require(prefixes(evidence) == (checkpoint["calls_prefix"], checkpoint["event_prefix"]), "DAY_PREFIX_DIFFERS_FROM_LOG")
    g.require(len(evidence["sessions"]) == 1 and all(evidence["sessions"][0][k] == candidate[k]
              for k in ("session_id", "entity_id", "principal_id", "mode")), "DAY_SESSION_CHANGED")
    g.require(len(evidence["call_batches"]) == 1 and evidence["call_batches"][0]["batch_id"] == scope["batch_id"]
              and evidence["call_batches"][0]["scope_sha256"] == g.digest(scope)
              and evidence["call_batches"][0]["stopped"] == 0, "DAY_REGISTERED_SCOPE_CHANGED_OR_STOPPED")
    slots = {s["id"]: s for s in scope["slots"]}
    key = g.resolve(candidate["host_ingress_key"], workspace).read_bytes()
    g.require(evidence["turn_count"] == len(evidence["rows"]) and len({r["slot_id"] for r in evidence["rows"]}) == len(evidence["rows"]), "DAY_ORPHAN_OR_DUPLICATE_TURN")
    for row in evidence["rows"]:
        g.require(row["batch_id"] == scope["batch_id"] and row["session_id"] == candidate["session_id"]
                  and row["slot_id"] in slots and row["model"] == slots[row["slot_id"]]["model"]
                  and row["status"] == "RESPONSE_CAPTURED" and row["turn_status"] == "DISPLAYED"
                  and row["capture_origin"] == row["response_provenance"] == "TARGET_PROVIDER_CAPTURE"
                  and row["input_provenance"] == "RAW_USER_UTTERANCE_NOT_EVENT_PROOF", "DAY_UNKNOWN_TEST_OR_UNDISPLAYED_TURN")
        g.verify_raw(row)
        receipt = g.verify_ingress(g.load(manifest_path.parent / "HOST_INGRESS" / (row["turn_id"] + ".json")), key, candidate, row)
        price = receipt["preflight_record"]["pricing_record"]
        price_copy = manifest_path.parent / "PRICING" / (price["sha256"] + ".json")
        g.require(g.sha(price_copy) == price["sha256"], "DAY_PRICE_COPY_CHANGED")
        import candidate_host_v2 as host
        checked_price = host.validate_pricing(price_copy, price["sha256"], scope, importlib.import_module("provider"), now=g.utc(row["submitted_at_utc"]))
        g.require(all(receipt["preflight_record"].get(k) == v for k, v in checked_price.items()), "DAY_PRICE_PREFLIGHT_DIFFERS_FROM_RECORD")
        g.require(any(p["process_id"] == receipt["writer_pid"] and p.get("ended_at_utc")
                      and g.utc(p["started_at_utc"]) <= g.utc(receipt["observed_at_utc"]) <= g.utc(row["display_at_utc"]) <= g.utc(p["ended_at_utc"])
                      for p in evidence["processes"]), "DAY_RECEIPT_PROCESS_MISMATCH")
        g.require(g.utc(candidate["created_at_utc"]) <= g.utc(row["submitted_at_utc"]) <= g.utc(row["display_at_utc"])
                  <= g.utc(checkpoint["observed_at_utc"]), "DAY_TURN_TIME_MISMATCH")
    g.require(any(g.day(r["display_at_utc"]) == checkpoint["observed_local_date"] for r in evidence["rows"]), "DAY_HAS_NO_ACTUAL_TURN")
    initial = candidate["initialization"]["verification"]
    tail = g.event_chain(evidence["events"], initial["genesis_sha256"], expected_entity=candidate["entity_id"], expected_session=candidate["session_id"])
    runtime = importlib.import_module("runtime_store")
    state = runtime.initial_state(initial["genesis_sha256"])
    for row in evidence["events"]:
        state = runtime.apply_event(state, json.loads(row["event_json"]))
    current = evidence["current"]
    g.require(current["state_sha256"] == checkpoint["state_sha256"] == g.digest(state)
              and json.loads(current["state_json"]) == state and current["last_event_sha256"] == tail, "DAY_STATE_REPLAY_MISMATCH")
    return checkpoint, evidence


def load_bundle(candidate_path, checkpoints_root, workspace=g.ROOT):
    candidate_path, workspace = Path(candidate_path), Path(workspace)
    candidate, scope = g.verify_candidate_bindings(candidate_path, workspace)
    g.runtime_modules(workspace)
    paths = sorted(g.contained(checkpoints_root, workspace).glob("*/CHECKPOINT.json"))
    g.require(len(paths) >= 3 and all(p.parent.parent.parent == candidate_path.parent for p in paths), "THREE_CANDIDATE_OWNED_DATES_REQUIRED")
    days, prior = [], None
    for path in paths:
        checkpoint, evidence = verify_day(path, candidate_path, candidate, scope, workspace)
        g.require(path.parent.name == checkpoint["observed_local_date"], "DAY_DIRECTORY_DATE_MISMATCH")
        if prior:
            g.require(days[-1]["observed_local_date"] < checkpoint["observed_local_date"], "DISTINCT_ORDERED_DATES_REQUIRED")
            g.prefix_matches(prior["rows"], evidence["rows"], "DAY_CALL_PREFIX_REWRITTEN")
            g.prefix_matches(prior["events"], evidence["events"], "DAY_EVENT_PREFIX_REWRITTEN")
        days.append(checkpoint); prior = evidence
    g.require(read_evidence(g.resolve(candidate["runtime"], workspace) / "runtime.sqlite3") == prior, "LIVE_RUNTIME_CHANGED_SINCE_FINAL_DAY")
    restart, switched = g.longitudinal_conditions(prior["processes"], prior["rows"], candidate["primary"], candidate["secondary"])
    retrieval = g.later_commitment_retrieval(prior["events"], prior["rows"])
    source_candidates = {r["candidate_id"]: r for r in prior["event_candidates"]}
    source_events = {r["event_id"]: json.loads(r["event_json"]) for r in prior["events"]}
    for item in retrieval:
        source_event = source_events[item["opened_event_id"]]
        item["opening_turn_ids"] = json.loads(source_candidates[source_event["candidate_id"]]["source_turns_json"])
    g.require(restart and switched and retrieval, "LONGITUDINAL_STRUCTURAL_OBLIGATIONS_MISSING")
    binding = {"candidate": g.ref(candidate_path, workspace), "checkpoints": [g.ref(p, workspace) for p in paths],
               "protocol_bindings": candidate["protocol_bindings"], "host_tool_bindings": candidate["host_tool_bindings"],
               "generation_settings": candidate["generation_settings"]}
    return {"classification": "ACTUAL_VERIFIED_REAL_DAY_EVIDENCE", "binding": binding,
            "days": days, "evidence": prior, "restart": restart, "retrieval": retrieval,
            "primary": candidate["primary"], "secondary": candidate["secondary"]}


def blank_review(bundle):
    return {"schema_version": "g6-longitudinal-explicit-review-1", "binding": bundle["binding"],
        "reviewer": {"actor_type": None, "name_or_identifier": None, "role": None, "individual_item_adjudication": False,
            "automatic_verdict_prefill": None,
            "read_full_raw_inputs_outputs_context_and_events": False, "participated_in_implementation": None,
            "conflicts_of_interest": None, "started_at_utc": None, "completed_at_utc": None},
        "turns": [{"turn_id": r["turn_id"], "judgments": [{"criterion": c, "verdict": None,
                    "user_quote": None, "assistant_quote": None, "rationale": None} for c in CRITERIA]}
                  for r in bundle["evidence"]["rows"]],
        "days": [{"date": d["observed_local_date"], "quality": {k: {"score": None, "rationale": None, "evidence": []}
                   for k in QUALITY_DIAGNOSTICS}} for d in bundle["days"]],
        "longitudinal": [{"criterion": c, "verdict": None, "rationale": None, "evidence": []} for c in LONGITUDINAL],
        "findings_complete": False, "findings": []}


def quote(item, rows):
    g.require(item.get("turn_id") in rows, "QUOTE_TURN_UNKNOWN")
    row = rows[item["turn_id"]]
    g.require(isinstance(item.get("user_quote"), str) and item["user_quote"].strip()
              and item["user_quote"] in row["user_text"] and isinstance(item.get("assistant_quote"), str)
              and item["assistant_quote"].strip() and item["assistant_quote"] in row["assistant_text"], "QUOTE_NOT_EXACT_RAW_INPUT_AND_OUTPUT")
    return row


def bind_review(bundle, review):
    g.require(review.get("schema_version") == "g6-longitudinal-explicit-review-1" and review.get("binding") == bundle["binding"], "REVIEW_BINDING_CHANGED")
    actor = review["reviewer"]
    g.require(actor.get("actor_type") in {"HUMAN", "DEVELOPER_AI"} and actor.get("individual_item_adjudication") is True
              and actor.get("automatic_verdict_prefill") is False
              and actor.get("read_full_raw_inputs_outputs_context_and_events") is True
              and isinstance(actor.get("name_or_identifier"), str) and actor["name_or_identifier"].strip()
              and actor.get("role") in {"USER_OBSERVER", "DEVELOPER", "REVIEWER"}
              and (actor["actor_type"] != "DEVELOPER_AI" or actor["role"] == "DEVELOPER")
              and type(actor.get("participated_in_implementation")) is bool and type(actor.get("conflicts_of_interest")) is bool,
              "EXPLICIT_INDIVIDUAL_REVIEW_DECLARATION_REQUIRED")
    g.require(g.utc(actor["started_at_utc"]) <= g.utc(actor["completed_at_utc"]) <= datetime.now(timezone.utc)
              and g.utc(actor["completed_at_utc"]) >= g.utc(bundle["days"][-1]["observed_at_utc"]), "REVIEW_TIME_INVALID")
    rows = {r["turn_id"]: r for r in bundle["evidence"]["rows"]}
    turns = review["turns"]
    g.require(len(turns) == len(rows) and {t["turn_id"] for t in turns} == set(rows), "REVIEW_MUST_COVER_EVERY_ORIGINAL_TURN")
    verdicts = Counter()
    for turn in turns:
        judgments = turn["judgments"]
        g.require(len(judgments) == len(CRITERIA) and {j["criterion"] for j in judgments} == set(CRITERIA), "ALL_FOUR_TURN_CRITERIA_REQUIRED")
        for j in judgments:
            quote({**j, "turn_id": turn["turn_id"]}, rows)
            g.require(j["verdict"] in {"PASS", "FAIL", "UNKNOWN"} and isinstance(j.get("rationale"), str) and j["rationale"].strip(), "MANUAL_JUDGMENT_REQUIRED")
            verdicts[j["verdict"]] += 1
    dates = {d["observed_local_date"] for d in bundle["days"]}
    g.require(len(review["days"]) == len(dates) and {d["date"] for d in review["days"]} == dates, "ALL_DAYS_QUALITY_REQUIRED")
    quality_diagnostics = []
    for item in review["days"]:
        optional_quality = item.get("quality") or {}
        g.require(isinstance(optional_quality, dict) and set(optional_quality) <= set(QUALITY_DIAGNOSTICS), "UNKNOWN_QUALITY_DIAGNOSTIC")
        for name, rated in optional_quality.items():
            if rated.get("score") is None and not rated.get("rationale") and not rated.get("evidence"):
                continue
            g.require(type(rated["score"]) is int and 1 <= rated["score"] <= 5 and rated.get("rationale") and rated.get("evidence"), "MANUAL_QUALITY_RATING_REQUIRED")
            for evidence in rated["evidence"]:
                g.require(g.day(quote(evidence, rows)["display_at_utc"]) == item["date"], "QUALITY_QUOTE_FROM_WRONG_DAY")
            quality_diagnostics.append({"date": item["date"], "dimension": name, **rated})
    overall = review["longitudinal"]
    g.require(len(overall) == len(LONGITUDINAL) and {i["criterion"] for i in overall} == set(LONGITUDINAL), "ALL_LONGITUDINAL_JUDGMENTS_REQUIRED")
    for item in overall:
        g.require(item["verdict"] in {"PASS", "FAIL", "UNKNOWN"} and item.get("rationale") and item.get("evidence"), "MANUAL_LONGITUDINAL_JUDGMENT_REQUIRED")
        cited = [quote(e, rows) for e in item["evidence"]]
        g.require(len({g.day(r["display_at_utc"]) for r in cited}) >= 2, "LONGITUDINAL_QUOTES_REQUIRE_DISTINCT_DATES")
        if item["criterion"] == "model_switch_preserves_authority_and_relationship":
            g.require({bundle["primary"], bundle["secondary"]} <= {r["model"] for r in cited}, "MODEL_SWITCH_QUOTES_MISSING")
        if item["criterion"] == "same_commitment_restored_across_dates":
            g.require(any(v["retrieval_call_id"] in {r["call_id"] for r in cited}
                          and set(v["opening_turn_ids"]) <= {r["turn_id"] for r in cited}
                          and v["opening_turn_ids"] for v in bundle["retrieval"]), "ACTUAL_RETRIEVAL_AND_OPENING_QUOTES_MISSING")
    g.require(review.get("findings_complete") is True and isinstance(review.get("findings"), list), "COMPLETE_FINDINGS_DECLARATION_REQUIRED")
    finding_ids, opened = set(), []
    for finding in review["findings"]:
        g.require(finding.get("id") and finding["id"] not in finding_ids and finding.get("severity") in {"CRITICAL", "MAJOR", "MINOR"}
                  and finding.get("status") in {"OPEN", "RESOLVED"} and finding.get("rationale") and finding.get("evidence"), "INVALID_FINDING")
        finding_ids.add(finding["id"])
        for item in finding["evidence"]:
            quote(item, rows)
        if finding["status"] == "RESOLVED":
            g.require(finding.get("resolution") and finding.get("resolution_evidence"), "RESOLVED_FINDING_REQUIRES_BOUND_RESOLUTION")
            for item in finding["resolution_evidence"]:
                quote(item, rows)
        if finding["status"] == "OPEN" and finding["severity"] in {"CRITICAL", "MAJOR"}:
            opened.append(finding["id"])
    semantic_pass = verdicts == {"PASS": len(rows) * len(CRITERIA)} and all(i["verdict"] == "PASS" for i in overall)
    passed = semantic_pass and not opened
    actual = bundle["classification"] == "ACTUAL_VERIFIED_REAL_DAY_EVIDENCE"
    return {"schema_version": "g6-longitudinal-recorded-review-1", "binding": bundle["binding"],
        "review_sha256": g.digest(review), "recorded_manual_review_complete": True, "qualified_real_date_count": len(dates) if actual else 0,
        "reviewed_turn_count": len(rows), "verdict_counts": dict(verdicts), "semantic_judgments_all_pass": semantic_pass,
        "quality_diagnostics": quality_diagnostics, "quality_diagnostics_are_gate_thresholds": False,
        "open_material_findings": opened, "recorded_natural_day_gate_met": bool(actual and passed),
        "status": ("RECORDED_NATURAL_DAY_REVIEW_PASS" if passed else "NATURAL_DAY_REVIEW_NOT_PASSED") if actual else "OFFLINE_FIXTURE_ONLY",
        "reviewer_human_identity_independently_authenticated": False, "reviewer_declaration": actor,
        "reviewer_actor_type": actor["actor_type"], "review_is_independent_external_review": False,
        "external_review": "WAITING_EXTERNAL", "production_activated": False, "product_acceptance_complete": False, "target_calls": 0}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("template", "review"))
    p.add_argument("--candidate", type=Path, required=True); p.add_argument("--checkpoints-root", type=Path, required=True)
    p.add_argument("--review", type=Path); p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        bundle = load_bundle(a.candidate, a.checkpoints_root)
        value = blank_review(bundle) if a.action == "template" else bind_review(bundle, g.load(a.review))
        g.write_new(g.contained(a.output, g.ROOT), value)
        print(json.dumps({"output": str(a.output), "status": value.get("status", "UNFILLED_MANUAL_REVIEW_TEMPLATE"), "target_calls": 0}))
        return 0
    except (g.GateError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "product_acceptance_complete": False, "target_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
