"""Candidate-only interactive host. No pipe/file/argument text becomes human input.

The live CLI requires real stdin/stdout TTYs. It uses the unmodified official
provider transport, finite scope, journal and ChatService. Tests use the explicit
AUTHOR_TEST branch, whose receipts can never qualify as real-user natural days.
TTY/HMAC establish local host provenance, not independent human authentication.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import importlib
import json
import os
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
import candidate_day_v2 as gates

_TTY_BOUNDARY = object()
HOST_NAME = "persona_core/gpt6_optimization_v2/tools/candidate_host_v2.py"


@dataclass(frozen=True)
class HostInput:
    text: str
    observed_at_utc: str
    source_kind: str
    interactive_tty: bool
    is_test: bool
    _token: object = field(repr=False, compare=False)


def read_tty_line(stdin=None, stdout=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    # Dependency arguments exist only to test rejection. A substitute object,
    # even one implementing isatty(), cannot issue a genuine console token.
    gates.require(stdin is sys.stdin and stdout is sys.stdout
                  and stdin.isatty() and stdout.isatty(), "REAL_LOCAL_TTY_INPUT_REQUIRED")
    text = stdin.readline()
    if text == "":
        return None
    return HostInput(text.rstrip("\r\n"), datetime.now(timezone.utc).isoformat(),
                     "GENUINE_LOCAL_INTERACTIVE_USER", True, False, _TTY_BOUNDARY)


def authored_test_input(text):
    """Explicit test origin; not exposed as a live CLI input option."""
    return HostInput(text, datetime.now(timezone.utc).isoformat(), "AUTHOR_TEST", False, True, None)


def validate_pricing(path, pinned_sha, scope, provider, *, now=None):
    path = Path(path)
    gates.require(gates.sha(path) == pinned_sha, "PRICING_RECORD_CHANGED_DURING_SESSION")
    value = gates.load(path)
    stamp = now or datetime.now(timezone.utc)
    local_date = stamp.astimezone(gates.TOKYO).date().isoformat()
    gates.require(value.get("observation_date_local") == local_date and value.get("timezone") == "Asia/Tokyo"
                  and not value.get("offline_only"), "CURRENT_OFFICIAL_PRICING_RECORD_REQUIRED")
    models = {s["model"] for s in scope["slots"]}
    rates = {model: {"input_miss": provider.RATES[model][0], "output": provider.RATES[model][1],
                     "input_hit": provider.RATES[model][2]} for model in models}
    documented = value.get("peak_rates_cny_per_million_tokens", {})
    gates.require(models <= set(value.get("models_confirmed", []))
                  and all(rates[m] == scope["peak_rates_cny_per_million_tokens"].get(m)
                          and isinstance(documented.get(m), dict) and set(documented[m]) == set(rates[m])
                          and all(type(documented[m][k]) in (int, float) and 0 <= documented[m][k] <= ceiling
                                  for k, ceiling in rates[m].items()) for m in models),
                  "CURRENT_MODEL_OR_PRICE_DIFFERS_FROM_SCOPE")
    thinking = scope["thinking"]["type"]
    gates.require(thinking in value.get("thinking_types_confirmed", [])
                  and (thinking != "enabled" or scope["reasoning_effort"] in value.get("reasoning_efforts_confirmed", []))
                  and value.get("reasoning_is_included_in_completion_usage") is True,
                  "CURRENT_PROVIDER_INTERFACE_NOT_CONFIRMED")
    sources = value.get("sources")
    gates.require(isinstance(sources, list) and sources and all(isinstance(s, str)
                  and s.startswith("https://api-docs.deepseek.com/") for s in sources), "OFFICIAL_PRICE_SOURCES_REQUIRED")
    provider.scope_check(scope)
    return {"pricing_record_sha256": pinned_sha, "observed_local_date": local_date,
            "models": sorted(models), "total_guard_cny": scope["total_guard_cny"],
            "official_rates_cny_per_million_tokens": {m: documented[m] for m in sorted(models)},
            "conservative_ceiling_rates_cny_per_million_tokens": {m: rates[m] for m in sorted(models)},
            "ceiling_rates_are_not_actual_billing": True,
            "documentation_identity_is_not_weight_identity": True}


def assert_no_unfinished_or_unbound_turns(service):
    db = service.store.db
    batch = db.execute("SELECT scope_sha256,stopped FROM call_batches WHERE batch_id=?",
                       (service.scope["batch_id"],)).fetchone()
    gates.require(batch and batch[0] == gates.digest(service.scope) and batch[1] == 0,
                  "CANDIDATE_BATCH_MISSING_CHANGED_OR_STOPPED")
    rows = db.execute("SELECT t.turn_id,t.status,p.status,p.batch_id,p.session_id FROM turns t "
                      "LEFT JOIN provider_calls p USING(turn_id)").fetchall()
    gates.require(all(r[1] == "DISPLAYED" and r[2] == "RESPONSE_CAPTURED"
                  and r[3] == service.scope["batch_id"] and r[4] == service.handle.session_id for r in rows),
                  "UNFINISHED_UNBOUND_OR_UNKNOWN_TURN_REQUIRES_LOCAL_RECONCILIATION")


def sign_ingress(origin, candidate, turn_id, key, *, preflight_record=None):
    gates.require(isinstance(origin, HostInput), "HOST_INPUT_OBJECT_REQUIRED")
    if not origin.is_test:
        gates.require(origin._token is _TTY_BOUNDARY and origin.interactive_tty is True
                      and origin.source_kind == "GENUINE_LOCAL_INTERACTIVE_USER", "UNTRUSTED_HUMAN_ORIGIN_DECLARATION")
        gates.require(isinstance(preflight_record, dict) and preflight_record.get("pricing_record")
                      and preflight_record.get("scope_sha256") == candidate["scope"]["sha256"],
                      "LIVE_INGRESS_REQUIRES_BOUND_PREFLIGHT_RECORD")
    else:
        gates.require(origin.source_kind == "AUTHOR_TEST" and origin.interactive_tty is False,
                      "TEST_INPUT_CANNOT_IMPERSONATE_GENUINE_ORIGIN")
    payload = {"schema_version": "g6-genuine-user-ingress-1", "source_kind": origin.source_kind,
               "interactive_tty": origin.interactive_tty, "is_test": origin.is_test,
               "observed_at_utc": origin.observed_at_utc, "turn_id": turn_id,
               "user_text_sha256": hashlib.sha256(origin.text.encode("utf-8")).hexdigest(),
               "writer_pid": os.getpid(), "host_tool_sha256": candidate["host_tool_bindings"][HOST_NAME],
               "human_presence_independently_authenticated": False,
               "preflight_record": preflight_record,
               **{k: candidate[k] for k in ("candidate_id", "session_id", "entity_id", "principal_id")}}
    payload["hmac_sha256"] = hmac.new(key, gates.canonical(payload), hashlib.sha256).hexdigest()
    return payload


def send_once(service, origin, candidate, ingress_root, key, *, preflight, display,
              transport=None, credential_reader=None):
    """Local intake -> signed origin -> unchanged journal-first send; zero retry."""
    provider = importlib.import_module("provider")
    gates.require(isinstance(origin, HostInput), "HOST_INPUT_OBJECT_REQUIRED")
    if origin.is_test:
        gates.require(transport is not None and transport is not provider.official_transport
                      and credential_reader is not None, "AUTHOR_TEST_REQUIRES_OFFLINE_TRANSPORT")
    else:
        gates.require(origin._token is _TTY_BOUNDARY and transport is None and credential_reader is None,
                      "LIVE_HOST_MUST_USE_REAL_TTY_AND_OFFICIAL_TRANSPORT")
    gates.require(origin.text.strip(), "EMPTY_INPUT")
    preflight_record = preflight()
    assert_no_unfinished_or_unbound_turns(service)
    slot = service.next_slot(origin.text)
    key_id = service.scope["batch_id"] + ":" + slot["id"]
    gates.require(service.store.db.execute("SELECT 1 FROM turns WHERE session_id=? AND idempotency_key=?",
                  (service.handle.session_id, key_id)).fetchone() is None, "SLOT_INPUT_ALREADY_EXISTS_NO_REPLAY")
    turn = service.store.begin_turn(service.handle, origin.text, key_id)
    receipt = sign_ingress(origin, candidate, turn["turn_id"], key, preflight_record=preflight_record)
    ingress_root = Path(ingress_root)
    gates.write_new(ingress_root / (turn["turn_id"] + ".json"), receipt)

    def checked_credential():
        # This hook occurs after context building, immediately before the native
        # provider journal prepares its submission. Never wrap official_transport:
        # doing so would misclassify actual paid output as authored test output.
        final_preflight = preflight()
        if not origin.is_test:
            gates.require(final_preflight == preflight_record, "PREFLIGHT_CHANGED_DURING_TURN")
        return credential_reader() if origin.is_test else provider.existing_credential()

    kwargs = {"credential_reader": checked_credential, "display": display}
    if origin.is_test:
        kwargs["transport"] = transport
    result = service.send_text(origin.text, key_id, slot_id=slot["id"], **kwargs)
    return result


def open_candidate(candidate_path, pricing_path):
    candidate, scope = gates.verify_candidate_bindings(candidate_path)
    _, _, _, provider = gates.runtime_modules(gates.ROOT)
    pricing_path = gates.contained(pricing_path, gates.ROOT)
    pricing_sha = gates.sha(pricing_path)
    candidate_sha = gates.sha(candidate_path)
    validate_pricing(pricing_path, pricing_sha, scope, provider)
    transcript = importlib.import_module("transcript_store")
    operations = importlib.import_module("operations")
    store = transcript.TranscriptStore(gates.resolve(candidate["runtime"], gates.ROOT))
    try:
        handle = store.resume(candidate["principal_id"], candidate["session_id"])
        gates.require(handle.entity_id == candidate["entity_id"] and handle.mode == "PRODUCT_RUNTIME",
                      "INITIALIZED_CANDIDATE_IDENTITY_MISMATCH")
        service = operations.open_chat(store, handle, scope)
        assert_no_unfinished_or_unbound_turns(service)
    except BaseException:
        store.close()
        raise

    def preflight():
        gates.require(gates.sha(candidate_path) == candidate_sha, "CANDIDATE_MANIFEST_CHANGED_DURING_SESSION")
        rebound, bound_scope = gates.verify_candidate_bindings(candidate_path)
        gates.require(rebound == candidate and bound_scope == scope, "CANDIDATE_OR_SCOPE_CHANGED")
        price_check = validate_pricing(pricing_path, pricing_sha, scope, provider)
        return {**price_check, "pricing_record": gates.ref(pricing_path, gates.ROOT),
                "scope_sha256": candidate["scope"]["sha256"],
                "generation_settings_sha256": gates.digest(gates.generation_settings(scope))}

    return candidate, store, service, preflight


def run_console(candidate_path, pricing_path):
    gates.require(sys.stdin.isatty() and sys.stdout.isatty(), "REAL_LOCAL_TTY_INPUT_REQUIRED")
    candidate_path = gates.contained(candidate_path, gates.ROOT)
    candidate, _ = gates.verify_candidate_bindings(candidate_path)
    parent = candidate_path.parent
    lock_path = parent / "ACTIVE_HOST.json"
    lock = {"candidate_id": candidate["candidate_id"], "pid": os.getpid(), "nonce": uuid.uuid4().hex,
            "started_at_utc": datetime.now(timezone.utc).isoformat()}
    gates.write_new(lock_path, lock)
    store = None
    run_id = None
    exit_code = 2
    try:
        candidate, store, service, preflight = open_candidate(candidate_path, pricing_path)
        store.db.execute("CREATE TABLE IF NOT EXISTS cli_process_runs(run_id TEXT PRIMARY KEY, process_id INTEGER NOT NULL, "
                         "session_id TEXT NOT NULL REFERENCES sessions(session_id), started_at_utc TEXT NOT NULL, ended_at_utc TEXT, exit_code INTEGER)")
        run_id = "g6host_" + uuid.uuid4().hex
        with store.transaction():
            store.db.execute("INSERT INTO cli_process_runs VALUES(?,?,?,?,NULL,NULL)",
                             (run_id, os.getpid(), candidate["session_id"], datetime.now(timezone.utc).isoformat()))
        key_path = gates.resolve(candidate["host_ingress_key"], gates.ROOT)
        gates.require(key_path.parent == parent, "INGRESS_KEY_NOT_CANDIDATE_OWNED")
        key = key_path.read_bytes()
        gates.require(len(key) == 32, "INGRESS_KEY_INVALID")
        print("候选文本会话。请由真实用户直接输入；/status 查看状态，/inspect 查看最后答复，/exit 退出。", flush=True)
        while True:
            print("你：", end="", flush=True)
            origin = read_tty_line()
            if origin is None or origin.text in {"/exit", "/quit"}:
                exit_code = 0
                return 0
            if not origin.text.strip():
                continue
            if origin.text == "/status":
                print(json.dumps(service.status(), ensure_ascii=False), flush=True)
                continue
            if origin.text == "/inspect":
                print(json.dumps(service.inspect_last(), ensure_ascii=False), flush=True)
                continue
            if origin.text.startswith("/"):
                print("未知本地命令。", flush=True)
                continue
            result = send_once(service, origin, candidate, parent / "HOST_INGRESS", key,
                preflight=preflight, display=lambda answer: print("Amadeus：" + answer, flush=True))
            if result["status"] != "DISPLAYED":
                print("本轮未确认展示，已停止；不会自动重发。状态：" + result["status"], flush=True)
                return 2
    finally:
        if store is not None:
            if run_id is not None:
                with store.transaction():
                    store.db.execute("UPDATE cli_process_runs SET ended_at_utc=?,exit_code=? WHERE run_id=?",
                        (datetime.now(timezone.utc).isoformat(), exit_code, run_id))
            store.close()
        if lock_path.is_file() and gates.load(lock_path) == lock:
            lock_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--pricing-record", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run_console(args.candidate, args.pricing_record)
    except (gates.GateError, OSError, ValueError, KeyError) as exc:
        print("候选入口停止：" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
