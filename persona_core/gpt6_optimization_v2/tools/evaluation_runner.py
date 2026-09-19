"""Immutable V2 evaluation revisions over the ordinary ChatService.

CLI (use C:\\Users\\skr\\anaconda3\\python.exe -B):
  evaluation_runner.py prepare --revision heldout_01 --suite heldout --offline
  evaluation_runner.py run --revision heldout_01
  evaluation_runner.py status --revision heldout_01
  evaluation_runner.py reconcile --revision heldout_01

For target preparation omit --offline and supply --pricing-record PATH. Its
schema is the existing OFFICIAL_PREFLIGHT record: observation_date_local,
timezone=Asia/Tokyo, sources, models_confirmed, thinking_types_confirmed,
reasoning_efforts_confirmed, peak_rates_cny_per_million_tokens, and
reasoning_is_included_in_completion_usage. Target run additionally requires
--execute. Preparation never reads credentials or calls the provider.

--suite original82 preserves every frozen input, order and model role, with
the original authored histories in separate sessions. --max-turns is an
orderly pause within ONE already pinned logical batch, not a budget split.
Every required restart exits a worker and resumes the same session in a new
OS process. All ordinary calls use the existing provider journal; no retry,
capacity escalation, unknown replay, automatic acceptance or shared cursor.

MANIFEST.json, SCOPE.json, source/pricing snapshots, execution receipts,
displays, and capture snapshots are exclusive-create artifacts. CURSOR.json
is the only replaceable progress document, scoped to this revision. A final
CAPTURES.json is sealed on completion or quarantine; intermediate immutable
snapshots live under captures/. Display means a durable local text sink ACK,
not proof that a human read it. A crashed driver is deliberately conservative:
reconcile/quarantine it and prepare a fresh revision, never steal its lease.

--suite external44 selects the seven complete cases implicated by the earlier
external review. Its separately frozen selection retains original input and
rubric bytes/values, all original fixture histories, and both switch tails.
It is known-development validation, never a replacement for original82.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
import uuid
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
GOAL = ROOT / "persona_core/gpt6_optimization_v2"
CODE = ROOT / "persona_core/operational_runtime_v1"
PLAN = ROOT / "persona_core/operational_build_v1"
EVIDENCE = PLAN / "evidence"
LEGACY = ROOT / "persona_core/runtime"
OLD_TOOLS = PLAN / "tools"
PROTOCOL = EVIDENCE / "R047-01"
FREEZE = PROTOCOL / "freeze_20260907T164424498856Z"
PYTHON = Path("C:/Users/skr/anaconda3/python.exe")
SCHEMA = "apcore-gpt6-evaluation-2"
OFFLINE = "AUTHORED_OFFLINE_ONLY"
TARGET = "TARGET_PROVIDER_CAPTURE"
PRIVATE_MARKERS = ("HOLDOUT_OTHER_ONLY", "SABLE-COPPER-47", "书房三层")
ALLOWED_ACTIONS = {"NONE", "RESTART_SAME_SESSION"}
_IMPORTED_RUNTIME_HASHES = None


class RunnerError(ValueError):
    """Only fixed, credential-free error codes are emitted by the CLI."""


def require(condition, code):
    if not condition:
        raise RunnerError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def now():
    return datetime.now(timezone.utc).isoformat()


def pricing_date():
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def write_bytes_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_new(path, value):
    write_bytes_new(path, canonical(value) + b"\n")


def cursor(root, state, **fields):
    """Commit the recovery effect before any possible chargeable operation."""
    value = {"schema_version": SCHEMA, "revision_id": read(root / "MANIFEST.json")["revision_id"],
             "state": state, "at_utc": now(), "automatic_paid_retries": 0, **fields}
    temporary = root / (".cursor_" + uuid.uuid4().hex + ".tmp")
    write_new(temporary, value)
    os.replace(temporary, root / "CURSOR.json")


def revision_root(revision):
    require(isinstance(revision, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", revision),
            "INVALID_REVISION_NAME")
    base = EVIDENCE.resolve()
    result = (base / ("G6_V2_" + revision)).resolve()
    require(result.parent == base and result.name == "G6_V2_" + revision,
            "REVISION_PATH_OUTSIDE_EVIDENCE")
    return result


def relative(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), "SOURCE_PATH_OUTSIDE_WORKSPACE")
    return path.relative_to(ROOT).as_posix()


def runtime_modules():
    # Delayed imports keep prepare's freeze gate ahead of runtime construction.
    global _IMPORTED_RUNTIME_HASHES
    before = {p.name: sha(p) for p in CODE.glob("*.py")}
    require(_IMPORTED_RUNTIME_HASHES is None or _IMPORTED_RUNTIME_HASHES == before,
            "LOADED_RUNTIME_SOURCE_CHANGED_START_NEW_PROCESS")
    for path in (OLD_TOOLS, CODE):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import provider
    import transcript_store
    import operations
    import context_router
    import runtime_store
    import admission
    import retrieval
    require(before == {p.name: sha(p) for p in CODE.glob("*.py")}, "RUNTIME_CHANGED_DURING_IMPORT")
    _IMPORTED_RUNTIME_HASHES = before
    return provider, transcript_store, operations, context_router, runtime_store, admission, retrieval


def default_primary():
    return "deepseek-flash" if "deepseek-flash" in runtime_modules()[0].RATES else "deepseek-v4-flash"


def frozen_inputs():
    audit = GOAL / "GPT6_BASELINE_AUDIT.json"
    require(audit.is_file(), "BASELINE_AUDIT_NOT_FROZEN")
    require(read(audit).get("status") == "FROZEN", "BASELINE_AUDIT_NOT_FROZEN")
    heldout = read(GOAL / "HELDOUT_FREEZE.json")
    require(heldout.get("status") == "FROZEN_PRE_IMPLEMENTATION" and
            heldout.get("mutable_after_implementation") is False, "HELDOUT_NOT_FROZEN")
    for name, expected in heldout["files"].items():
        path = (GOAL / name).resolve()
        require(path.is_relative_to(GOAL) and path.is_file() and sha(path) == expected,
                "HELDOUT_FREEZE_MISMATCH")
    cases = read(GOAL / "heldout_v1/CASES.json")
    require((len(cases["cases"]), sum(len(c["turns"]) for c in cases["cases"]),
             len(cases["criteria_per_turn"])) == (24, 113, 4), "HELDOUT_DENOMINATOR_CHANGED")
    require((heldout["case_count"], heldout["turn_count"], heldout["criteria_count"]) ==
            (24, 113, 452), "HELDOUT_FREEZE_COUNTS_CHANGED")
    return cases


def load_suite(suite, primary, secondary):
    heldout = frozen_inputs()
    provider = runtime_modules()[0]
    require(primary in provider.RATES and secondary in provider.RATES and primary != secondary,
            "DISTINCT_SUPPORTED_MODELS_REQUIRED")
    if suite == "heldout":
        cases = heldout["cases"]
        slots = []
        for case in cases:
            for turn in case["turns"]:
                require(turn["model_role"] in {"PRIMARY", "SECONDARY"} and
                        turn["host_action_before"] in ALLOWED_ACTIONS, "UNKNOWN_HELDOUT_ACTION")
                slots.append({"id": turn["id"], "case_id": case["id"],
                              "entity_label": case["entity_label"], "user_text": turn["user_text"],
                              "model_role": turn["model_role"], "model": primary if turn["model_role"] == "PRIMARY" else secondary,
                              "host_action_before": turn["host_action_before"]})
        return {"slots": slots, "cases": cases, "fixture": None,
                "cases_path": GOAL / "heldout_v1/CASES.json", "criteria_count": 452}
    require(suite in {"original82", "external44"}, "UNKNOWN_SUITE")
    from r047_execution_common import load_frozen
    original, cases, fixture, _ = load_frozen()
    slots = []
    for index, slot in enumerate(original["slots"]):
        role = "PRIMARY" if slot["model"] == original["primary_model"] else "SECONDARY"
        slots.append({**slot, "model": primary if role == "PRIMARY" else secondary,
                      "model_role": role,
                      "host_action_before": "RESTART_SAME_SESSION" if index == 3 else "NONE"})
    require(len(slots) == 82 and len(cases["cases"]) == 14, "ORIGINAL_DENOMINATOR_CHANGED")
    if suite == "external44":
        directory = GOAL / "external_failure_v1"
        freeze = read(directory / "FREEZE.json")
        require(freeze.get("status") == "FROZEN", "EXTERNAL_SELECTION_NOT_FROZEN")
        for name, expected in freeze["files"].items():
            path = (directory / name).resolve()
            require(path.parent == directory.resolve() and sha(path) == expected,
                    "EXTERNAL_SELECTION_FREEZE_CHANGED")
        selection = read(directory / "SELECTION.json")
        ids = ["N02", "N04", "N06", "N07", "N08", "N09", "N11"]
        require(selection["case_ids"] == ids and
                selection["original_cases_sha256"] == sha(PROTOCOL / "NEW_MULTITURN_CASES.json") and
                selection["original_rubric_sha256"] == sha(PROTOCOL / "PRIVATE_RUBRIC.json") and
                selection["original_scope_sha256"] == sha(FREEZE / "EXECUTION_SCOPE.json"),
                "EXTERNAL_SELECTION_ORIGINAL_BINDING_CHANGED")
        selected = read(directory / "CASES.json")
        require(selected["cases"] == [c for c in cases["cases"] if c["id"] in ids] and
                sha(directory / "PRIVATE_RUBRIC.json") == selection["original_rubric_sha256"],
                "EXTERNAL_SELECTION_INPUT_OR_RUBRIC_CHANGED")
        slots = [s for s in slots if s["case_id"] in ids]
        require(len(slots) == 44 and sum(s["model_role"] == "SECONDARY" for s in slots) == 2,
                "EXTERNAL_SELECTION_DENOMINATOR_CHANGED")
        return {"slots": slots, "cases": selected["cases"], "fixture": fixture,
                "setup_cases": cases["cases"], "cases_path": directory / "CASES.json",
                "criteria_count": 176}
    return {"slots": slots, "cases": cases["cases"], "fixture": fixture,
            "cases_path": PROTOCOL / "NEW_MULTITURN_CASES.json", "criteria_count": 328}


def source_files():
    """Bind all executable runtime/evaluation code and all cloned source data.

    Credential adapter is HASHED ONLY; it is never copied or printed. Mutable
    goal/canonical progress documents and old output evidence are not inputs.
    Directory membership is checked as well as bytes, detecting added modules.
    """
    files = set(CODE.glob("*.py"))
    files.update(OLD_TOOLS / name for name in ("prepare_execution_r047.py", "r047_execution_common.py"))
    files.update((GOAL / "tools").glob("*.py"))
    files.update(p for p in LEGACY.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.update(GOAL / p for p in ("GPT6_BASELINE_AUDIT.json", "GPT6_BASELINE_AUDIT.md",
                                  "USER_OBJECTIVE.md", "HELDOUT_FREEZE.json",
                                  "heldout_v1/CASES.json", "heldout_v1/REVIEW_PROTOCOL.md"))
    files.update(FREEZE / p for p in ("FREEZE_VERIFICATION.json", "EXECUTION_SCOPE.json",
                                    "PREOBSERVATION_PROTOCOL.zip"))
    files.update(PROTOCOL / name for name in read(FREEZE / "FREEZE_VERIFICATION.json")["files"])
    files.update(GOAL / "external_failure_v1" / name for name in
                 ("CASES.json", "PRIVATE_RUBRIC.json", "SELECTION.json", "FREEZE.json"))
    files.add(ROOT / "persona_core/rebaseline_20260906_r006/tools/deepseek_adapter.py")
    return sorted(files)


def source_bindings():
    return {relative(p): sha(p) for p in source_files()}


def checked_pricing(record, offline, models=None):
    provider = runtime_modules()[0]
    rates = {model: {"input_miss": v[0], "output": v[1], "input_hit": v[2]}
             for model, v in provider.RATES.items()}
    if offline:
        require(record is None, "OFFLINE_PRICING_MUST_NOT_IMPERSONATE_VERIFICATION")
        return {"observation_date_local": pricing_date(), "timezone": "Asia/Tokyo",
                "sources": ["OFFLINE_TEST_POLICY_NOT_CURRENT_OFFICIAL_VERIFICATION"],
                "peak_rates_cny_per_million_tokens": rates, "offline_only": True}
    require(record is not None, "CURRENT_OFFICIAL_PRICING_RECORD_REQUIRED")
    value = read(record)
    require(value.get("observation_date_local") == pricing_date() and value.get("timezone") == "Asia/Tokyo",
            "PRICING_RECORD_NOT_CURRENT")
    require(value.get("peak_rates_cny_per_million_tokens") == rates and
            set(models or (default_primary(), "deepseek-v4-pro")).issubset(value.get("models_confirmed", [])) and
            "enabled" in value.get("thinking_types_confirmed", []) and
            "max" in value.get("reasoning_efforts_confirmed", []) and
            value.get("reasoning_is_included_in_completion_usage") is True and
            value.get("sources") and not value.get("offline_only"), "PRICING_OR_INTERFACE_CONTRACT_MISMATCH")
    require(all(isinstance(s, str) and s.startswith("https://api-docs.deepseek.com/")
                for s in value["sources"]), "OFFICIAL_PRICING_SOURCES_REQUIRED")
    # Do not copy arbitrary fields from an operator-supplied file.
    keys = ("observation_date_local", "timezone", "sources", "models_confirmed",
            "thinking_types_confirmed", "reasoning_efforts_confirmed",
            "reasoning_is_included_in_completion_usage", "peak_rates_cny_per_million_tokens")
    return {key: value[key] for key in keys}


def build_scope(revision, suite_data, pricing, primary, secondary, max_input_bytes=24576,
                max_output_tokens=16384, guard_cny=None, timeout_seconds=600, transport_policy=None,
                api_protocol=None):
    provider = runtime_modules()[0]
    slots = suite_data["slots"]
    reserve = sum((max_input_bytes + 4096) * provider.RATES[s["model"]][0] +
                  max_output_tokens * provider.RATES[s["model"]][1] for s in slots)
    if guard_cny is None:
        guard_cny = math.ceil(reserve / 10000) / 100
    responses_api = api_protocol == 'responses'
    require(api_protocol in {None, 'responses'}, 'UNSUPPORTED_API_PROTOCOL')
    scope = {"schema_version": "apcore-provider-scope-4" if responses_api else "apcore-provider-scope-3",
             "batch_id": "APCORE-G6-V2-" + revision,
             "purpose": "Frozen whole-suite V2 evaluation; semantic review remains separate.",
             "principal_id": "APCORE_G6_V2_" + revision,
             "endpoint": provider.RESPONSES_ENDPOINT if responses_api else provider.ENDPOINT,
             "primary_model": primary, "switch_model": secondary, "slots": slots,
             "thinking": {"type": "enabled"}, "reasoning_effort": "max", "stream": False,
             "tools_allowed": False, "automatic_paid_retries": 0,
             "capacity_policy_id": "EXTENDED_MAX_REASONING_20260911",
             "output_budget_includes_reasoning": True, "automatic_capacity_escalation": False,
             "max_input_bytes": max_input_bytes, "input_overhead_reserve_tokens": 4096,
             "max_output_tokens": max_output_tokens, "request_timeout_seconds": timeout_seconds,
             "pricing_verified_date": pricing["observation_date_local"], "pricing_sources": pricing["sources"],
             "peak_rates_cny_per_million_tokens": pricing["peak_rates_cny_per_million_tokens"],
             "reserved_upper_micro_cny": reserve, "total_guard_cny": guard_cny,
             "target_call_counts": {"total": len(slots)}, "billing_verified": False,
             "authorization_basis": "USER_OBJECTIVE_FINAL_UNLIMITED_SPEND_WITH_PINNED_BATCH_NO_RETRIES"}
    if responses_api:
        scope['api_protocol'] = 'responses'
    if transport_policy is not None:
        scope.update(stream=True, transport_policy=dict(transport_policy))
    provider.scope_check(scope)  # Existing 150 CNY ceiling is not bypassed or split.
    return scope


def segments(slots):
    groups = []
    for slot in slots:
        if not groups or slot["host_action_before"] == "RESTART_SAME_SESSION":
            groups.append([])
        groups[-1].append(slot["id"])
    return [{"id": f"segment_{i:03d}", "slot_ids": group} for i, group in enumerate(groups)]


def seed_fixtures(store, scope, suite_data):
    """Reuse the original authored helper, never the old prepare entrypoint."""
    from prepare_execution_r047 import authored, session
    _, _, _, _, runtime_store, admission, retrieval = runtime_modules()
    controller = admission.AdmissionController(store)
    runtime = runtime_store.RuntimeStore(store, controller)
    principal = scope["principal_id"]
    rows = []
    fixture = suite_data["fixture"]
    if fixture:
        foreign = fixture["foreign_private_record"]
        h = session(store, principal, foreign["entity_label"], "history")
        tid, event = authored(store, controller, h, foreign["user_statement"],
                              "此条为明确标记的合成布置，不是目标模型生成。", "foreign-private")
        rows.append({"kind": "FOREIGN_PRIVATE", "turn_id": tid, "event_id": event["commit"]["event_id"]})
        long = fixture["old_agreement"]
        h = session(store, principal, long["entity_label"], "history")
        p, _ = authored(store, controller, h, "我们约定" + long["name"] + "；验收内容：" + long["expected_submission"],
                        "同意约定：" + long["name"], "long-proposal")
        c, _ = authored(store, controller, h, "确认约定：" + long["name"],
                        "只确认这份文字约定，尚未履约。", "long-confirm")
        event = runtime.commit(h, controller.confirm_agreement(h, p, c, long["name"], long["expected_submission"]))
        rows.append({"kind": "OPEN_AGREEMENT", "event_id": event["event_id"]})
        for i in range(long["same_entity_irrelevant_records_after_agreement"]):
            authored(store, controller, h, "合成清点记录编号" + str(i) + "：普通纸盒数量为" + str(i + 1) + "。",
                     "这是中性历史布置文字。", "long-neutral-" + str(i))
        correction = fixture["corrected_statement"]
        h = session(store, principal, correction["entity_label"], "history")
        old_tid, old = authored(store, controller, h, correction["old_user_statement"],
                                "保留为用户在合成历史中说过的内容。", "correction-old")
        new_tid, _ = authored(store, controller, h, "更正为" + correction["corrected_current_statement"],
                              "这也是明确标记的布置文字。", "correction-new")
        event = runtime.commit(h, controller.correct_user_statement(
            h, old["commit"]["event_id"], new_tid, correction["corrected_current_statement"]))
        rows.append({"kind": "CORRECTED_STATEMENT", "old_turn_id": old_tid, "event_id": event["event_id"]})
        for i in range(correction["same_entity_irrelevant_records"]):
            authored(store, controller, h, "合成清点记录编号" + str(i) + "：普通卡片数量为" + str(i + 1) + "。",
                     "这是与交接事项无关的布置。", "correction-neutral-" + str(i))
    for case in suite_data["cases"]:
        decoy = case.get("cross_entity_decoy")
        if decoy:
            h = session(store, principal, decoy["entity_label"], "history")
            tid, event = authored(store, controller, h, decoy["user_text"],
                                  "这是离线布置的私密夹具，不是目标模型生成。", "heldout-decoy-" + case["id"])
            rows.append({"kind": "HELDOUT_FOREIGN_PRIVATE", "turn_id": tid,
                         "event_id": event["commit"]["event_id"], "entity_id": h.entity_id})
    sessions = {}
    for case in suite_data.get("setup_cases", suite_data["cases"]):
        handle = store.open_session(principal, case["entity_label"], case.get("mode", "PRODUCT_RUNTIME"))
        require(not store.recent(handle, 1), "AUTHORED_TARGET_HISTORY_FORBIDDEN")
        sessions[case["id"]] = {"session_id": handle.session_id, "entity_id": handle.entity_id,
                                "entity_label": case["entity_label"], "mode": handle.mode}
    if fixture:
        query = retrieval.RetrievalService(runtime)
        h09 = store.resume(principal, sessions["N09"]["session_id"])
        h10 = store.resume(principal, sessions["N10"]["session_id"])
        require(any(r.get("agreed_submission_requirement") == fixture["old_agreement"]["expected_submission"] and
                    r.get("status") == "OPEN" for r in query.search(h09, "潮汐目录的约定")), "ORIGINAL_AGREEMENT_SETUP_FAILED")
        require(any(r["record_kind"] == "FACT_CORRECTED" and r["content"] == fixture["corrected_statement"]["corrected_current_statement"]
                    for r in query.search(h10, "星图交接点")), "ORIGINAL_CORRECTION_SETUP_FAILED")
        for cid, key in (("N09", "long-neutral-%"), ("N10", "correction-neutral-%")):
            count = store.db.execute("SELECT count(*) FROM turns JOIN sessions USING(session_id) "
                                     "WHERE entity_id=? AND idempotency_key LIKE ?",
                                     (sessions[cid]["entity_id"], "AUTHORED_SETUP:" + key)).fetchone()[0]
            require(count == 120, "ORIGINAL_DISTRACTOR_COUNT_CHANGED")
    require(store.db.execute("SELECT count(*) FROM provider_calls").fetchone()[0] == 0, "PREPARATION_SUBMITTED_CALL")
    return {"sessions": sessions, "fixture_records": rows, "authored_origin": "AUTHORED_TEST_STUB",
            "authored_setup_turns": store.db.execute("SELECT count(*) FROM turns").fetchone()[0],
            "target_session_turns_at_prepare": 0, "target_calls_at_prepare": 0,
            "runtime_verification": runtime.verify()}


def prepare(revision, suite="heldout", *, offline=False, pricing_record=None,
            primary=None, secondary="deepseek-v4-pro", max_input_bytes=24576,
            max_output_tokens=16384, guard_cny=None, timeout_seconds=600, transport_policy_file=None,
            api_protocol=None):
    frozen_inputs()
    primary = primary or default_primary()
    suite_data = load_suite(suite, primary, secondary)  # Gate before any write.
    root = revision_root(revision)
    require(not root.exists(), "REVISION_ALREADY_EXISTS_USE_NEW_REVISION")
    pricing = checked_pricing(pricing_record, offline, (primary, secondary))
    transport_policy = read(transport_policy_file) if transport_policy_file is not None else None
    scope = build_scope(revision, suite_data, pricing, primary, secondary, max_input_bytes,
                        max_output_tokens, guard_cny, timeout_seconds, transport_policy, api_protocol)
    bindings = source_bindings()
    root.mkdir(parents=False, exist_ok=False)
    write_new(root / "PREPARATION_INTENT.json", {"revision_id": revision, "at_utc": now(), "provider_calls": 0})
    provider, transcript, *_ = runtime_modules()
    write_new(root / "SCOPE.json", scope)
    write_new(root / "SOURCE_MANIFEST.json", {"files": bindings, "python_executable": str(PYTHON),
                                             "python_sha256": sha(PYTHON)})
    write_new(root / "PRICING.json", pricing)
    transcript.create_sandbox(root / "runtime")
    store = transcript.TranscriptStore(root / "runtime")
    try:
        provider.ProviderJournal(store).register_batch(scope)
        preparation = seed_fixtures(store, scope, suite_data)
        write_new(root / "PREPARATION.json", preparation)
    finally:
        store.close()
    # This archive deliberately excludes the credential adapter, retaining its
    # digest in SOURCE_MANIFEST.json for integrity without copying any secrets.
    with zipfile.ZipFile(root / "SOURCE.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for name in bindings:
            if not name.endswith("/deepseek_adapter.py"):
                archive.write(ROOT / name, name)
    require(source_bindings() == bindings, "SOURCE_CHANGED_DURING_PREPARATION")
    artifacts = {name: sha(root / name) for name in ("SCOPE.json", "SOURCE_MANIFEST.json", "PRICING.json",
                                                   "PREPARATION.json", "SOURCE.zip")}
    manifest = {"schema_version": SCHEMA, "revision_id": revision, "suite": suite, "at_utc": now(),
                "capture_mode": OFFLINE if offline else TARGET, "artifacts": artifacts,
                "source_manifest_sha256": artifacts["SOURCE_MANIFEST.json"],
                "cases_sha256": sha(suite_data["cases_path"]),
                "heldout_sha256": sha(GOAL / "heldout_v1/CASES.json"),
                "baseline_audit_sha256": sha(GOAL / "GPT6_BASELINE_AUDIT.json"),
                "expected_case_count": len(suite_data["cases"]), "expected_turn_count": len(scope["slots"]),
                "expected_criteria_count": suite_data["criteria_count"], "segments": segments(scope["slots"]),
                "automatic_paid_retries": 0, "semantic_acceptance": None,
                "authored_setup_counts_as_generated": False, "source_and_scope_immutable": True,
                "model_identity_contract": {
                    "primary_requested": primary, "secondary_requested": secondary,
                    "historical_primary_alias": "deepseek-v4-flash",
                    "primary_name_changed_from_historical": primary != "deepseek-v4-flash",
                    "exact_historical_model_equivalence_asserted": False,
                    "comparison_limit": "Provider model drift prevents attributing differences solely to Core changes; frozen inputs and model roles are preserved, model identity is separately pinned."},
                "runtime_genesis_sha256": sha(root / "runtime/legacy_runtime/genesis/GENESIS_SNAPSHOT_R035.json")}
    write_new(root / "MANIFEST.json", manifest)
    write_new(root / "MANIFEST_SEAL.json", {"sha256": sha(root / "MANIFEST.json")})
    cursor(root, "PREPARED", in_flight_external_effect=None, safe_to_resume=True)
    return status(revision)


def read_contract(root):
    require((root / "MANIFEST.json").is_file() and (root / "MANIFEST_SEAL.json").is_file(),
            "PREPARATION_INCOMPLETE_USE_NEW_REVISION")
    require(sha(root / "MANIFEST.json") == read(root / "MANIFEST_SEAL.json")["sha256"], "MANIFEST_SEAL_MISMATCH")
    manifest = read(root / "MANIFEST.json")
    require(root == revision_root(manifest["revision_id"]), "REVISION_ID_PATH_MISMATCH")
    for name, expected in manifest["artifacts"].items():
        path = (root / name).resolve()
        require(path.parent == root and path.is_file() and sha(path) == expected, "REVISION_ARTIFACT_CHANGED")
    return manifest, read(root / "SCOPE.json"), read(root / "PREPARATION.json")


def verify_sources(root):
    manifest, scope, preparation = read_contract(root)
    frozen_inputs()
    bound = read(root / "SOURCE_MANIFEST.json")
    require(source_bindings() == bound["files"], "CURRENT_SOURCE_BINDING_CHANGED_NEW_REVISION_REQUIRED")
    require(Path(sys.executable).resolve() == PYTHON.resolve() and sha(PYTHON) == bound["python_sha256"],
            "PINNED_PYTHON_MISMATCH")
    legacy_files = {p.relative_to(LEGACY).as_posix(): sha(p) for p in LEGACY.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts}
    clone = root / "runtime/legacy_runtime"
    clone_files = {p.relative_to(clone).as_posix(): sha(p) for p in clone.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts}
    require(legacy_files == clone_files, "RUNTIME_SOURCE_CLONE_CHANGED")
    if manifest["capture_mode"] == TARGET:
        checked_pricing(root / "PRICING.json", False, (scope["primary_model"], scope["switch_model"]))
    return manifest, scope, preparation


@contextlib.contextmanager
def readonly_db(root):
    path = root / "runtime/runtime.sqlite3"
    require(path.is_file(), "RUNTIME_DATABASE_MISSING")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def call_rows(db, scope):
    return [dict(r) for r in db.execute(
        "SELECT p.slot_id,p.call_id,p.turn_id,p.session_id,p.status AS provider_status,"
        "p.model,p.capture_origin,p.raw_sha256,p.request_sha256,p.reserve_micro_cny,"
        "p.estimate_peak_micro_cny,t.status,t.user_text,t.assistant_text "
        "FROM provider_calls p JOIN turns t USING(turn_id) WHERE p.batch_id=? ORDER BY t.seq",
        (scope["batch_id"],))]


def completed(row):
    return row["provider_status"] == "RESPONSE_CAPTURED" and row["status"] == "DISPLAYED"


def validate_rows(db, root, manifest, scope, preparation):
    batch = db.execute("SELECT * FROM call_batches WHERE batch_id=?", (scope["batch_id"],)).fetchone()
    require(batch is not None and batch["scope_sha256"] == value_sha(scope) and
            json.loads(batch["scope_json"]) == scope, "JOURNAL_SCOPE_MISMATCH")
    rows = call_rows(db, scope)
    by_slot = {r["slot_id"]: r for r in rows}
    slots = scope["slots"]
    require(list(by_slot) == [s["id"] for s in slots[:len(rows)]], "JOURNAL_NOT_FIXED_PREFIX")
    origin = "AUTHORED_PROVIDER_TEST_FIXTURE" if manifest["capture_mode"] == OFFLINE else TARGET
    for slot in slots[:len(rows)]:
        row = by_slot[slot["id"]]
        session = preparation["sessions"][slot["case_id"]]
        require(row["model"] == slot["model"] and row["user_text"] == slot["user_text"] and
                row["session_id"] == session["session_id"] and row["capture_origin"] == origin,
                "CALL_SCOPE_OR_ORIGIN_MISMATCH")
        identity = db.execute("SELECT s.entity_id,s.principal_id,s.mode,e.label FROM sessions s JOIN entities e USING(entity_id) WHERE session_id=?",
                              (row["session_id"],)).fetchone()
        require(identity is not None and identity["entity_id"] == session["entity_id"] and
                identity["principal_id"] == scope["principal_id"] and identity["mode"] == session["mode"] and
                identity["label"] == slot["entity_label"], "SESSION_IDENTITY_CHANGED")
        request = db.execute("SELECT request_json,context_json,raw_response,raw_was_redacted FROM provider_calls WHERE call_id=?",
                             (row["call_id"],)).fetchone()
        require(hashlib.sha256(request["request_json"].encode("utf-8")).hexdigest() == row["request_sha256"],
                "REQUEST_HASH_MISMATCH")
        payload = json.loads(request["request_json"])
        context = json.loads(request["context_json"])
        if scope.get('api_protocol') == 'responses':
            expected = {"model": slot["model"], "input": context["messages"],
                        "max_output_tokens": scope["max_output_tokens"], "stream": True,
                        "reasoning": {"effort": scope["reasoning_effort"]}}
            bound_messages = payload.get('input')
        else:
            expected = {"model": slot["model"], "messages": context["messages"],
                        "max_tokens": scope["max_output_tokens"], "stream": scope['stream'],
                        "thinking": scope["thinking"], "reasoning_effort": scope["reasoning_effort"]}
            if scope['stream']:
                expected['stream_options'] = {'include_usage': True}
            bound_messages = payload.get('messages')
        require(payload == expected and bound_messages[-1] == {"role": "user", "content": slot["user_text"]}
                and len(canonical(bound_messages)) <= scope["max_input_bytes"], "REQUEST_SCOPE_MISMATCH")
        if request["raw_response"] is not None and not request["raw_was_redacted"]:
            require(hashlib.sha256(request["raw_response"]).hexdigest() == row["raw_sha256"], "RAW_RESPONSE_HASH_MISMATCH")
        if completed(row):
            require(not request["raw_was_redacted"] and request["raw_response"] is not None and
                    json.loads(request["raw_response"])["choices"][0]["message"]["content"] == row["assistant_text"],
                    "ASSISTANT_TEXT_DIFFERS_FROM_RAW_RESPONSE")
            if scope.get('api_protocol') == 'responses' and origin == TARGET:
                import provider_transport
                provider_transport.verify_responses_wire(db, {**row, **dict(request)}, scope)
            display_path = root / "displays" / (slot["id"] + ".txt")
            require(display_path.is_file() and display_path.read_bytes() == (row["assistant_text"] + "\n").encode("utf-8"),
                    "DURABLE_DISPLAY_MISMATCH")
            ack = db.execute("SELECT status FROM display_journal WHERE turn_id=?", (row["turn_id"],)).fetchone()
            require(ack is not None and ack[0] == "DISPLAY_ACK", "DISPLAY_ACK_MISSING")
    return rows, batch


def status(revision):
    root = revision_root(revision)
    manifest, scope, preparation = read_contract(root)
    with readonly_db(root) as db:
        rows, batch = validate_rows(db, root, manifest, scope, preparation)
    active = (root / "ACTIVE_RUN.json").exists()
    quarantine = (root / "QUARANTINE.json").exists()
    unknown = [r for r in rows if r["provider_status"] == "SUBMITTED_STATUS_UNKNOWN"]
    good = sum(completed(r) for r in rows)
    bad = any(not completed(r) for r in rows)
    state = ("QUARANTINED_NEW_REVISION_REQUIRED" if quarantine else
             "IN_FLIGHT_OR_INTERRUPTED" if active else
             "STOPPED_RECONCILE_REQUIRED" if batch["stopped"] or bad else
             "CAPTURE_COMPLETE_REVIEW_PENDING" if good == len(scope["slots"]) else
             "PREPARED" if not rows else "PAUSED_KNOWN_PREFIX")
    return {"schema_version": SCHEMA, "revision_id": revision, "state": state,
            "capture_mode": manifest["capture_mode"], "expected_turns": len(scope["slots"]),
            "recorded_calls": len(rows), "completed_slots": good,
            "generated_target_captures": sum(completed(r) and r["capture_origin"] == TARGET for r in rows),
            "authored_transport_captures": sum(completed(r) and r["capture_origin"] != TARGET for r in rows),
            "authored_setup_turns_excluded": preparation["authored_setup_turns"],
            "unknown_count": len(unknown), "not_submitted": len(scope["slots"]) - len(rows),
            "reserved_micro_cny": sum(r["reserve_micro_cny"] for r in rows),
            "unknown_reserved_micro_cny": sum(r["reserve_micro_cny"] for r in unknown),
            "known_peak_usage_subtotal_micro_cny": sum(r["estimate_peak_micro_cny"] or 0 for r in rows),
            "estimate_complete": all(r["estimate_peak_micro_cny"] is not None for r in rows),
            "total_guard_cny": scope["total_guard_cny"], "billing_verified": False,
            "automatic_paid_retries": 0, "semantic_acceptance": None,
            "safe_to_resume": not active and not quarantine and not batch["stopped"] and not bad,
            "manifest_sha256": sha(root / "MANIFEST.json"),
            "source_manifest_sha256": manifest["source_manifest_sha256"], "cases_sha256": manifest["cases_sha256"]}


def capture_snapshot(root, *, final=False):
    manifest, scope, preparation = read_contract(root)
    with readonly_db(root) as db:
        rows, _ = validate_rows(db, root, manifest, scope, preparation)
    by_slot = {r["slot_id"]: r for r in rows}
    turns = []
    for slot in scope["slots"]:
        row = by_slot.get(slot["id"])
        if row is None:
            continue  # Fixed denominator is retained in expected_turn_count.
        keys = ("user_text", "assistant_text", "status", "provider_status", "model", "call_id",
                "turn_id", "session_id", "raw_sha256", "request_sha256", "capture_origin")
        turns.append({"case_id": slot["case_id"], "slot_id": slot["id"], **{k: row[k] for k in keys}})
    value = {"schema_version": SCHEMA, "revision_id": manifest["revision_id"],
             "source_manifest_sha256": manifest["source_manifest_sha256"], "cases_sha256": manifest["cases_sha256"],
             "manifest_sha256": sha(root / "MANIFEST.json"), "capture_mode": manifest["capture_mode"],
             "eligible_for_target_evaluation": manifest["capture_mode"] == TARGET,
             "expected_turn_count": len(scope["slots"]), "expected_criteria_count": manifest["expected_criteria_count"],
             "semantic_acceptance": None, "authored_setup_excluded": True, "turns": turns}
    if final:
        path = root / "CAPTURES.json"
        if path.exists():
            require(read(path) == value, "FINAL_CAPTURE_IS_IMMUTABLE")
            require((root / "CAPTURES_SEAL.json").is_file() and
                    read(root / "CAPTURES_SEAL.json")["captures_sha256"] == sha(path), "FINAL_CAPTURE_SEAL_MISSING_OR_CHANGED")
            return path
    else:
        path = root / "captures" / uuid.uuid4().hex / "CAPTURES.json"
    write_new(path, value)
    write_new(path.parent / ("CAPTURES_SEAL.json"), {"captures_sha256": sha(path),
              "manifest_sha256": sha(root / "MANIFEST.json"), "final": final})
    return path


def process_alive(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        api.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of death.
        try:
            code = wintypes.DWORD()
            return not api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def authored_transport(payload, credential):
    """No network or credential adapter. Engineering evidence only."""
    request = json.loads(payload)
    return 200, canonical({"model": request["model"],
                           **({'responses_api_status': 'completed'} if 'input' in request else {}),
                           "usage": {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105},
                           "choices": [{"finish_reason": "stop", "message": {"content": "收到。"}}]})


def worker(revision, segment_id, run_id, max_turns=None):
    root = revision_root(revision)
    manifest, scope, preparation = verify_sources(root)
    lease = read(root / "ACTIVE_RUN.json")
    require(lease["run_id"] == run_id and lease["pid"] == os.getppid(), "WORKER_REQUIRES_OWNING_PARENT")
    segment = next((s for s in manifest["segments"] if s["id"] == segment_id), None)
    require(segment is not None, "UNPINNED_SEGMENT")
    provider, transcript, operations, context_router, *_ = runtime_modules()
    store = transcript.TranscriptStore(root / "runtime")
    out = root / "runs" / run_id / (segment_id + "_" + uuid.uuid4().hex)
    out.mkdir(parents=True, exist_ok=False)
    report = {"run_id": run_id, "segment_id": segment_id, "pid": os.getpid(), "parent_pid": os.getppid(),
              "at_utc": now(), "manifest_sha256": sha(root / "MANIFEST.json"), "steps": [], "status": "STARTED"}
    write_new(out / "START.json", report)
    calls_now = 0
    try:
        rows, batch = validate_rows(store.db, root, manifest, scope, preparation)
        require(not batch["stopped"] and all(completed(r) for r in rows), "INCOMPLETE_OR_STOPPED_BATCH")
        first = next(s for s in scope["slots"] if s["id"] == segment["slot_ids"][0])
        if first["host_action_before"] == "RESTART_SAME_SESSION":
            previous = scope["slots"][scope["slots"].index(first) - 1]
            receipt = read(root / "receipts" / (previous["id"] + ".json"))
            require(receipt["pid"] != os.getpid() and not process_alive(receipt["pid"]), "PREVIOUS_PROCESS_HAS_NOT_EXITED")
            require(previous["case_id"] == first["case_id"] and
                    receipt["session_id"] == preparation["sessions"][first["case_id"]]["session_id"],
                    "RESTART_MUST_KEEP_SAME_SESSION")
        for slot in scope["slots"]:
            if slot["id"] not in segment["slot_ids"]:
                continue
            verify_sources(root)  # Full input and membership binding before EACH slot.
            handle = store.resume(scope["principal_id"], preparation["sessions"][slot["case_id"]]["session_id"])
            chat = operations.open_chat(store, handle, scope)
            previous_rows = call_rows(store.db, scope)
            consumed = next((r for r in previous_rows if r["slot_id"] == slot["id"]), None)
            key = scope["batch_id"] + ":" + slot["id"]
            if consumed:
                require(completed(consumed), "CONSUMED_SLOT_CANNOT_RETRY")
                result = chat.send_text(slot["user_text"], key, slot_id=slot["id"])
                require(result["status"] == "ALREADY_DISPLAYED", "COMPLETED_SLOT_REPLAY_FORBIDDEN")
                continue
            if max_turns is not None and calls_now >= max_turns:
                report["status"] = "PAUSED_KNOWN_PREFIX"
                break
            require(len(previous_rows) < len(scope["slots"]) and scope["slots"][len(previous_rows)]["id"] == slot["id"],
                    "EARLIER_SLOTS_NOT_COMPLETE")
            require(all(completed(r) for r in previous_rows), "PRIOR_UNKNOWN_OR_FAILURE")
            cursor(root, "SLOT_INTENT", run_id=run_id, slot_id=slot["id"], safe_to_resume=False,
                   in_flight_external_effect={"stage": "BEFORE_TURN", "model": slot["model"],
                                              "session_id": handle.session_id, "slot_id": slot["id"]})
            turn = store.begin_turn(handle, slot["user_text"], key)
            preview = context_router.build_context(store, handle, turn["turn_id"],
                max_prompt_bytes=scope["max_input_bytes"], memory_provider=chat.memory_provider)
            encoded = canonical(preview["messages"])
            require(len(encoded) <= scope["max_input_bytes"], "PROMPT_EXCEEDS_PINNED_BYTES")
            require(not any(token.encode("utf-8") in encoded for token in PRIVATE_MARKERS), "FOREIGN_PRIVATE_CONTEXT_LEAK")
            require(b"private_expectations" not in encoded and b"R047_PRIVATE_RUBRIC_NEVER_SEND_TO_TARGET" not in encoded,
                    "PRIVATE_RUBRIC_IN_CONTEXT")
            intent = {"slot_id": slot["id"], "case_id": slot["case_id"], "model": slot["model"],
                      "session_id": handle.session_id, "entity_id": handle.entity_id, "turn_id": turn["turn_id"],
                      "pid": os.getpid(), "at_utc": now(), "prompt_bytes": len(encoded),
                      "preview_messages_sha256": value_sha(preview["messages"]),
                      "source_manifest_sha256": manifest["source_manifest_sha256"]}
            write_new(out / (slot["id"] + "_INTENT.json"), intent)
            cursor(root, "NETWORK_MAY_BE_SUBMITTED", run_id=run_id, safe_to_resume=False,
                   in_flight_external_effect=intent)

            def display(answer):
                write_bytes_new(root / "displays" / (slot["id"] + ".txt"), (answer + "\n").encode("utf-8"))

            kwargs = {}
            if manifest["capture_mode"] == OFFLINE:
                kwargs = {"transport": authored_transport,
                          "credential_reader": lambda: "OFFLINE_AUTHORED_TRANSPORT_NOT_A_CREDENTIAL"}
            result = chat.send_text(slot["user_text"], key, slot_id=slot["id"], display=display, **kwargs)
            calls_now += 1
            row = store.db.execute("SELECT * FROM provider_calls WHERE turn_id=?", (turn["turn_id"],)).fetchone()
            require(row is not None, "CALL_RECEIPT_MISSING")
            request_field = 'input' if scope.get('api_protocol') == 'responses' else 'messages'
            require(value_sha(json.loads(row["request_json"])[request_field]) == intent["preview_messages_sha256"],
                    "SUBMITTED_CONTEXT_DIFFERS_FROM_PREVIEW")
            receipt = {**intent, "call_id": row["call_id"], "request_sha256": row["request_sha256"],
                       "raw_sha256": row["raw_sha256"], "status": result["status"],
                       "provider_status": row["status"], "capture_origin": row["capture_origin"],
                       "finished_at_utc": now()}
            write_new(root / "receipts" / (slot["id"] + ".json"), receipt)
            report["steps"].append(receipt)
            capture_snapshot(root)
            if result["status"] != "DISPLAYED":
                report["status"] = "STOPPED_RECONCILE_REQUIRED"
                cursor(root, report["status"], run_id=run_id, safe_to_resume=False,
                       in_flight_external_effect=receipt)
                break
            cursor(root, "SLOT_COMPLETE", run_id=run_id, last_completed_slot=slot["id"],
                   safe_to_resume=False, in_flight_external_effect=None)
        else:
            report["status"] = "SEGMENT_COMPLETE"
        if report["status"] == "STARTED":
            report["status"] = "SEGMENT_COMPLETE"
    except BaseException as exc:
        report["status"] = "STOPPED_RECONCILE_REQUIRED"
        report["error_category"] = type(exc).__name__
        if isinstance(exc, RunnerError):
            report["error_code"] = str(exc)
        with store.transaction():
            store.db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (scope["batch_id"],))
        cursor(root, report["status"], run_id=run_id, safe_to_resume=False,
               in_flight_external_effect=read(root / "CURSOR.json").get("in_flight_external_effect"),
               error_category=type(exc).__name__)
    finally:
        report.update(finished_at_utc=now(), calls_now=calls_now)
        write_new(out / "RESULT.json", report)
        store.close()
    return report


def run(revision, *, execute=False, max_turns=None):
    root = revision_root(revision)
    manifest, scope, preparation = verify_sources(root)
    require(manifest["capture_mode"] == OFFLINE or execute, "TARGET_RUN_REQUIRES_EXPLICIT_EXECUTE")
    require(max_turns is None or type(max_turns) is int and max_turns > 0, "INVALID_PAUSE_LIMIT")
    before = status(revision)
    require(before["safe_to_resume"], "REVISION_NOT_RESUMABLE_RECONCILE_OR_NEW_REVISION")
    if before["completed_slots"] == len(scope["slots"]):
        capture_snapshot(root, final=True)
        return before
    run_id = uuid.uuid4().hex
    lease = {"run_id": run_id, "pid": os.getpid(), "at_utc": now(), "manifest_sha256": sha(root / "MANIFEST.json")}
    write_new(root / "ACTIVE_RUN.json", lease)  # O_EXCL cross-process ownership.
    report = {**lease, "workers": [], "status": "STARTING"}
    cursor(root, "DRIVER_START_INTENT", run_id=run_id, safe_to_resume=False, in_flight_external_effect=None)
    initial = before["recorded_calls"]
    try:
        for segment in manifest["segments"]:
            verify_sources(root)
            with readonly_db(root) as db:
                rows, batch = validate_rows(db, root, manifest, scope, preparation)
            require(not batch["stopped"] and all(completed(r) for r in rows), "PRIOR_UNKNOWN_OR_FAILURE")
            if all(any(r["slot_id"] == sid for r in rows) for sid in segment["slot_ids"]):
                continue
            left = None if max_turns is None else max_turns - (len(rows) - initial)
            if left is not None and left <= 0:
                break
            command = [str(PYTHON), "-B", str(Path(__file__).resolve()), "_worker", "--revision", revision,
                       "--segment", segment["id"], "--run-id", run_id]
            if left is not None:
                command += ["--max-turns", str(left)]
            cursor(root, "WORKER_START_INTENT", run_id=run_id, segment_id=segment["id"],
                   safe_to_resume=False, in_flight_external_effect=None)
            child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            write_new(root / "runs" / run_id / (segment["id"] + "_CHILD.json"),
                      {"pid": child.pid, "parent_pid": os.getpid(), "segment_id": segment["id"], "at_utc": now()})
            try:
                output, _ = child.communicate(timeout=len(segment["slot_ids"]) * (scope["request_timeout_seconds"] + 120))
            except BaseException:
                if child.poll() is None:
                    child.kill()
                child.communicate()
                raise
            require(child.returncode == 0, "WORKER_STOPPED_RECONCILE_REQUIRED")
            child_result = json.loads(output)
            require(child_result["pid"] == child.pid and child_result["run_id"] == run_id and
                    child_result["segment_id"] == segment["id"] and
                    child_result["status"] in {"SEGMENT_COMPLETE", "PAUSED_KNOWN_PREFIX"}, "WORKER_RECEIPT_INVALID")
            report["workers"].append(child_result)
            write_new(root / "runs" / run_id / (segment["id"] + "_EXIT.json"),
                      {"pid": child.pid, "exit_code": child.returncode, "observed_exit_at_utc": now()})
        with readonly_db(root) as db:
            rows, batch = validate_rows(db, root, manifest, scope, preparation)
        require(not batch["stopped"] and all(completed(r) for r in rows), "BATCH_NOT_CLEAN")
        report["status"] = "CAPTURE_COMPLETE_REVIEW_PENDING" if len(rows) == len(scope["slots"]) else "PAUSED_KNOWN_PREFIX"
        capture_snapshot(root, final=len(rows) == len(scope["slots"]))
        cursor(root, report["status"], run_id=run_id, safe_to_resume=True, in_flight_external_effect=None,
               last_completed_slot=rows[-1]["slot_id"] if rows else None)
    except BaseException as exc:
        report["status"] = "STOPPED_RECONCILE_REQUIRED"
        report["error_category"] = type(exc).__name__
        if isinstance(exc, RunnerError):
            report["error_code"] = str(exc)
        cursor(root, report["status"], run_id=run_id, safe_to_resume=False,
               in_flight_external_effect=read(root / "CURSOR.json").get("in_flight_external_effect"))
        # Keep the lease on interruptions/failure. No automatic UNKNOWN resume.
    finally:
        report["finished_at_utc"] = now()
        write_new(root / "runs" / run_id / "RESULT.json", report)
        if report["status"] != "STOPPED_RECONCILE_REQUIRED":
            require(read(root / "ACTIVE_RUN.json") == lease, "DRIVER_LEASE_CHANGED")
            (root / "ACTIVE_RUN.json").unlink()
    return {**status(revision), "run_status": report["status"], "run_id": run_id,
            **({"error_code": report["error_code"]} if "error_code" in report else {})}


def reconcile(revision):
    """Preserve remote UNKNOWN and its reserve; seal/quarantine, never replay."""
    root = revision_root(revision)
    manifest, scope, preparation = read_contract(root)
    if (root / "QUARANTINE.json").exists():
        return status(revision)
    if (root / "ACTIVE_RUN.json").exists():
        lease = read(root / "ACTIVE_RUN.json")
        require(not process_alive(lease["pid"]), "DRIVER_STILL_RUNNING")
        for path in (root / "runs" / lease["run_id"]).glob("*_CHILD.json"):
            require(not process_alive(read(path)["pid"]), "WORKER_STILL_RUNNING")
    else:
        # Share the driver's O_EXCL lease; reconciliation cannot race a run.
        write_new(root / "ACTIVE_RUN.json", {"pid": os.getpid(), "run_id": uuid.uuid4().hex,
                                             "operation": "RECONCILE", "at_utc": now()})
    write_new(root / "RECONCILE_LOCK.json", {"pid": os.getpid(), "at_utc": now()})
    with readonly_db(root) as db:
        rows = call_rows(db, scope)
    unknown = [{k: row[k] for k in ("slot_id", "call_id", "turn_id", "session_id", "request_sha256", "raw_sha256", "reserve_micro_cny")}
               for row in rows if row["provider_status"] == "SUBMITTED_STATUS_UNKNOWN"]
    report = {"schema_version": SCHEMA, "revision_id": revision, "at_utc": now(),
              "manifest_sha256": sha(root / "MANIFEST.json"), "status": "QUARANTINED_NEW_REVISION_REQUIRED",
              "unknown_requests": unknown, "remote_outcomes_resolved": False,
              "unknown_reserved_micro_cny": sum(r["reserve_micro_cny"] for r in unknown),
              "automatic_paid_retries": 0, "resend_allowed": False, "old_batch_resume_allowed": False,
              "billing_verified": False, "semantic_acceptance": None,
              "recovery_cursor_before": read(root / "CURSOR.json")}
    out = root / "reconciliations" / uuid.uuid4().hex
    write_new(out / "RECONCILIATION_INTENT.json", report)
    # Operate on this revision only; preserve every provider row/status/hash.
    with contextlib.closing(sqlite3.connect(root / "runtime/runtime.sqlite3")) as db, db:
        db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (scope["batch_id"],))
    write_new(out / "RECONCILIATION.json", report)
    write_new(root / "QUARANTINE.json", {**report, "reconciliation_sha256": sha(out / "RECONCILIATION.json")})
    try:
        capture_snapshot(root, final=True)
    except RunnerError as exc:
        write_new(out / "CAPTURE_INTEGRITY_ERROR.json", {"error_code": str(exc), "semantic_acceptance": None})
    cursor(root, report["status"], safe_to_resume=False, in_flight_external_effect=None,
           unresolved_requests=unknown, reconciliation_path=str(out.relative_to(root)))
    return {"revision_id": revision, "state": report["status"], "unknown_count": len(unknown),
            "unknown_reserved_micro_cny": report["unknown_reserved_micro_cny"], "safe_to_resume": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="Zero-call fresh immutable revision")
    p.add_argument("--revision", required=True)
    p.add_argument("--suite", choices=("heldout", "original82", "external44"), default="heldout")
    p.add_argument("--offline", action="store_true", help="Permanently authored, never target evidence")
    p.add_argument("--pricing-record", type=Path)
    p.add_argument("--primary", help="Defaults to deepseek-flash when supported, otherwise legacy alias; always pinned and drift disclosed")
    p.add_argument("--secondary", default="deepseek-v4-pro")
    p.add_argument("--max-input-bytes", type=int, default=24576)
    p.add_argument("--max-output-tokens", type=int, default=16384)
    p.add_argument("--guard-cny", type=float)
    p.add_argument("--timeout-seconds", type=int, default=600)
    p.add_argument("--transport-policy-file", type=Path, help="Explicit opt-in streaming lifecycle policy; values freeze into scope")
    p.add_argument("--api-protocol", choices=("responses",), help="Explicit scope4 Responses protocol; older scopes remain unchanged")
    for name in ("run", "status", "reconcile", "_worker"):
        p = commands.add_parser(name)
        p.add_argument("--revision", required=True)
        if name in ("run", "_worker"):
            p.add_argument("--max-turns", type=int)
        if name == "run":
            p.add_argument("--execute", action="store_true")
        if name == "_worker":
            p.add_argument("--segment", required=True)
            p.add_argument("--run-id", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        if command == "_worker":
            args["segment_id"] = args.pop("segment")
            result = worker(**args)
            code = 0 if result["status"] in {"SEGMENT_COMPLETE", "PAUSED_KNOWN_PREFIX"} else 2
        else:
            result = {"prepare": prepare, "run": run, "status": status, "reconcile": reconcile}[command](**args)
            code = 2 if result.get("run_status") == "STOPPED_RECONCILE_REQUIRED" else 0
        print(json.dumps(result, ensure_ascii=True))
        return code
    except Exception as exc:
        error = {"status": "REFUSED", "error_category": type(exc).__name__, "automatic_paid_retries": 0}
        if isinstance(exc, RunnerError):
            error["error_code"] = str(exc)
        print(json.dumps(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
