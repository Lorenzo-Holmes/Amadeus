"""Journal-first bounded provider calls. Zero automatic paid retries.

Submitted status is committed before network I/O. Repeating a turn/slot cannot
resend a chargeable request, even after timeout or process death. No API tools
are exposed. Raw responses are data and have no event-admission authority.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from decimal import Decimal, ROUND_CEILING
from datetime import date
from pathlib import Path
from typing import Callable
from transcript_store import TranscriptStore, SessionHandle, StoreGuard, ensure, utc_now, WORKSPACE

ENDPOINT = "https://api.deepseek.com/chat/completions"
# CNY per million tokens: input miss, output (including reasoning), input hit.
# Preserve old alias rates as historical conservative bounds, never as today's
# tariff or proof that the retired V4-Flash model is still being served.
# Official pricing checked by the parent on 2026-09-13:
# https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
# Canonical deepseek-flash now serves DeepSeek-V4.1-Flash. Use peak rates even
# during off-peak hours; provider-reported usage estimates are not billing.
HISTORICAL_CONSERVATIVE_RATES = {"deepseek-v4-flash": (3, 9, 0.1)}
RATES = {**HISTORICAL_CONSERVATIVE_RATES,
         "deepseek-v4-pro": (9, 27, 0.3), "deepseek-flash": (2, 8, 0.04)}
MAX_RESPONSE_BYTES = 1_000_000
MAX_WORKER_TIMEOUT_SECONDS = 1200
WORKER_LOCAL_REJECTION_HEADER = b'AMADEUS_WORKER_NOT_SUBMITTED_V1\n'
WORKER_REMOTE_UNKNOWN_HEADER = b'AMADEUS_WORKER_REMOTE_OUTCOME_UNKNOWN_V1\n'
NETWORK_ERROR_CLASSES = frozenset({
    'URLError', 'OSError', 'TimeoutError', 'SSLError', 'SSLCertVerificationError',
    'ConnectionError', 'ConnectionResetError', 'ConnectionRefusedError',
    'ConnectionAbortedError', 'BrokenPipeError', 'gaierror', 'herror',
    'RemoteDisconnected', 'HTTPException', 'IncompleteRead', 'OTHER',
})


def _os_error_number(value) -> int | None:
    return value if type(value) is int and -(2 ** 31) <= value < 2 ** 31 else None


def network_error_details(exc: BaseException) -> dict:
    """Bounded diagnostics only; never serialize exception text or arguments."""
    reason = getattr(exc, 'reason', None)
    cause = reason if isinstance(reason, BaseException) else exc
    name = type(cause).__name__
    return {'reason_class': name if name in NETWORK_ERROR_CLASSES else 'OTHER',
            'errno': _os_error_number(getattr(cause, 'errno', None)),
            'winerror': _os_error_number(getattr(cause, 'winerror', None))}


def validate_network_error(value) -> None:
    ensure(isinstance(value, dict) and set(value) == {'reason_class', 'errno', 'winerror'},
           'PROVIDER_WORKER_NETWORK_ERROR_SHAPE_INVALID')
    ensure(isinstance(value['reason_class'], str) and value['reason_class'] in NETWORK_ERROR_CLASSES,
           'PROVIDER_WORKER_NETWORK_ERROR_CLASS_INVALID')
    ensure(all(value[k] is None or (type(value[k]) is int and _os_error_number(value[k]) == value[k])
               for k in ('errno', 'winerror')), 'PROVIDER_WORKER_NETWORK_ERROR_NUMBER_INVALID')

class WorkerNotSubmitted(StoreGuard):
    """A validated private-pipe receipt emitted before the worker's HTTP call."""
    def __init__(self, request_sha256: str, reason: str):
        super().__init__('PROVIDER_WORKER_LOCAL_INPUT_REJECTED')
        self.request_sha256 = request_sha256
        self.reason = reason

class WorkerRemoteOutcomeUnknown(StoreGuard):
    """Sanitized worker receipt after entering the HTTP path; never retryable."""
    def __init__(self, request_sha256: str, reason: str, stage: str, network_error: dict | None = None):
        super().__init__('PROVIDER_WORKER_REMOTE_OUTCOME_UNKNOWN')
        self.request_sha256 = request_sha256
        self.reason = reason
        self.stage = stage
        if network_error is not None:
            validate_network_error(network_error)
        self.network_error = network_error

# Wire-name compatibility is not immutable model identity. The old Flash alias
# is now served by V4.1-Flash too; accepting its canonical response must never
# be described as an exact repeat of the retired model. Journals retain both
# the requested `model` and the response's `provider_model` without rewriting.
# Canonical requests do not authorize the reverse legacy-name substitution.
PROVIDER_RESPONSE_BASES = {
    "deepseek-v4-flash": ("deepseek-v4-flash", "deepseek-flash"),
    "deepseek-v4-pro": ("deepseek-v4-pro",),
    "deepseek-flash": ("deepseek-flash",),
}

def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def validate_provider_model(requested: str, returned: str, *, strict_version: bool) -> None:
    """Validate allowed response identifiers, not an immutable serving snapshot."""
    ensure(isinstance(returned, str), "PROVIDER_MODEL_MISMATCH")
    if not strict_version:
        ensure(returned.casefold().startswith(requested.casefold()), "PROVIDER_MODEL_MISMATCH")
        return
    bases = PROVIDER_RESPONSE_BASES.get(requested, (requested,))
    ensure(any(returned.casefold().startswith(base.casefold()) for base in bases), "PROVIDER_MODEL_MISMATCH")
    ensure(any(re.fullmatch(re.escape(base) + r'(?:-[0-9]{4,8})?', returned, re.IGNORECASE) is not None
               for base in bases), 'PROVIDER_MODEL_VERSION_NOT_RECOGNIZED')

def existing_credential() -> str | None:
    path = WORKSPACE / "persona_core/rebaseline_20260906_r006/tools/deepseek_adapter.py"
    spec = importlib.util.spec_from_file_location("apcore_named_credential", path)
    ensure(spec is not None and spec.loader is not None, "Credential adapter missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.credential_value()[0]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)

def _worker_command() -> list[str]:
    return [sys.executable, '-B', str(Path(__file__).with_name('provider_http_worker.py'))]

def bounded_worker_transport(payload: bytes, credential: str, timeout_seconds: float) -> tuple[int, bytes]:
    """One owned HTTP worker, hard host deadline, no retry, credential via pipe.

On timeout only this call's child is terminated. The remote outcome is still
unknown; ProviderJournal keeps its intent and stops the batch.
"""
    started = time.monotonic()
    frame = canonical({'payload': payload.decode('utf-8'), 'credential': credential, 'timeout_seconds': timeout_seconds})
    child = subprocess.Popen(_worker_command(), cwd=WORKSPACE, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(child.args, timeout_seconds)
        output, error = child.communicate(frame, timeout=remaining)
    except BaseException:
        if child.poll() is None:
            child.kill()
        child.communicate()
        raise
    if child.returncode == 2 and output.startswith(WORKER_LOCAL_REJECTION_HEADER):
        ensure(len(output) <= 2048, 'PROVIDER_WORKER_INVALID_LOCAL_RECEIPT')
        receipt = json.loads(output[len(WORKER_LOCAL_REJECTION_HEADER):])
        ensure(set(receipt) == {'stage', 'network_attempted', 'frame_sha256', 'error_class'}, 'PROVIDER_WORKER_INVALID_LOCAL_RECEIPT')
        ensure(receipt['stage'] == 'INPUT_VALIDATION' and receipt['network_attempted'] is False,
               'PROVIDER_WORKER_LOCAL_RECEIPT_NOT_PRE_NETWORK')
        ensure(receipt['frame_sha256'] == hashlib.sha256(frame).hexdigest(), 'PROVIDER_WORKER_LOCAL_RECEIPT_BINDING_MISMATCH')
        ensure(receipt['error_class'] in {'StoreGuard', 'JSONDecodeError', 'UnicodeDecodeError', 'TypeError', 'ValueError'},
               'PROVIDER_WORKER_INVALID_LOCAL_RECEIPT_CLASS')
        raise WorkerNotSubmitted(hashlib.sha256(payload).hexdigest(), receipt['error_class'])
    if child.returncode == 2 and output.startswith(WORKER_REMOTE_UNKNOWN_HEADER):
        ensure(len(output) <= 2048, 'PROVIDER_WORKER_INVALID_REMOTE_UNKNOWN_RECEIPT')
        receipt = json.loads(output[len(WORKER_REMOTE_UNKNOWN_HEADER):])
        required = {'stage', 'network_phase_entered', 'remote_outcome_known', 'frame_sha256', 'error_class'}
        ensure(set(receipt) in (required, required | {'network_error'}),
               'PROVIDER_WORKER_INVALID_REMOTE_UNKNOWN_RECEIPT')
        ensure(receipt['stage'] == 'HTTP_CALL_OR_RESPONSE_READ' and receipt['network_phase_entered'] is True
               and receipt['remote_outcome_known'] is False, 'PROVIDER_WORKER_REMOTE_UNKNOWN_STAGE_INVALID')
        ensure(receipt['frame_sha256'] == hashlib.sha256(frame).hexdigest(),
               'PROVIDER_WORKER_REMOTE_UNKNOWN_BINDING_MISMATCH')
        ensure(isinstance(receipt['error_class'], str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', receipt['error_class']),
               'PROVIDER_WORKER_REMOTE_UNKNOWN_CLASS_INVALID')
        if 'network_error' in receipt:
            validate_network_error(receipt['network_error'])
        raise WorkerRemoteOutcomeUnknown(hashlib.sha256(payload).hexdigest(), receipt['error_class'],
                                         receipt['stage'], receipt.get('network_error'))
    ensure(child.returncode == 0, 'PROVIDER_WORKER_FAILED_OUTCOME_UNKNOWN')
    ensure(len(output) <= MAX_RESPONSE_BYTES + 40, 'PROVIDER_WORKER_RESPONSE_TOO_LARGE')
    header, raw = output.split(b'\n', 1)
    status = int(header)
    ensure(100 <= status <= 599, 'PROVIDER_WORKER_INVALID_STATUS')
    return status, raw

def official_transport(payload: bytes, credential: str, *, timeout_seconds: float = 55,
                       hard_deadline: bool = False) -> tuple[int, bytes]:
    if hard_deadline:
        return bounded_worker_transport(payload, credential, timeout_seconds)
    request = urllib.request.Request(ENDPOINT, data=payload, method="POST", headers={
        "Authorization": "Bearer " + credential, "Content-Type": "application/json", "User-Agent": "Amadeus-APCORE-OPERATIONS-V1"})
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_RESPONSE_BYTES + 1)

def scope_check(scope: dict) -> None:
    ensure(scope.get("automatic_paid_retries") == 0 and scope.get("endpoint") == ENDPOINT, "Unsupported endpoint or retries")
    version = scope.get('schema_version')
    ensure(version in {None, 'apcore-provider-scope-1', 'apcore-provider-scope-2', 'apcore-provider-scope-3'}, 'Unsupported provider scope version')
    extended = version == 'apcore-provider-scope-3'
    v2 = version in {'apcore-provider-scope-2', 'apcore-provider-scope-3'}
    if extended:
        ensure(scope.get('capacity_policy_id') == 'EXTENDED_MAX_REASONING_20260911', 'Explicit capacity revision policy required')
        ensure(scope.get('output_budget_includes_reasoning') is True, 'Reasoning must count inside the completion budget')
        ensure(scope.get('automatic_capacity_escalation') is False, 'Automatic capacity escalation is not allowed')
    if v2:
        try:
            date.fromisoformat(scope['pricing_verified_date'])
        except (ValueError, TypeError, KeyError):
            raise StoreGuard('Explicit ISO pricing verification date required') from None
        ensure(scope.get('stream') is False and scope.get('tools_allowed') is False, 'Only nonstream text requests without tools are allowed')
        ensure(scope.get('thinking') in ({'type': 'enabled'}, {'type': 'disabled'}), 'Explicit thinking mode required')
        if scope['thinking']['type'] == 'enabled':
            ensure(scope.get('reasoning_effort') in {'low', 'high', 'max'}, 'Unsupported reasoning effort')
        else:
            ensure(scope.get('reasoning_effort') is None, 'Disabled thinking cannot declare reasoning effort')
        ensure(type(scope.get('request_timeout_seconds')) is int and 1 <= scope['request_timeout_seconds'] <= (MAX_WORKER_TIMEOUT_SECONDS if extended else 240),
               'Finite provider deadline exceeds this versioned policy')
        expected_rates = {model: {'input_miss': values[0], 'output': values[1], 'input_hit': values[2]} for model, values in RATES.items()}
        pinned_rates = scope.get('peak_rates_cny_per_million_tokens')
        # Frozen old scopes contain only the old models. Adding a new canonical
        # model must not force their bytes or guards to change. Every used model
        # still needs its exact reviewed rates; every supplied entry is checked.
        ensure(isinstance(pinned_rates, dict) and bool(pinned_rates)
               and set(pinned_rates).issubset(expected_rates)
               and {s['model'] for s in scope['slots']}.issubset(pinned_rates)
               and all(pinned_rates[m] == expected_rates[m] for m in pinned_rates),
               'Pinned rates differ from reviewed provider rate policy')
    else:
        ensure(scope.get("pricing_verified_date") == "2026-09-07", "Legacy price verification needs an explicit new revision")
    ensure(scope.get("pricing_sources") and scope.get("purpose"), "Price sources and purpose required")
    ensure(type(scope.get("max_input_bytes")) is int and 1 <= scope["max_input_bytes"] <= 32768, "Invalid input byte bound")
    ensure(type(scope.get("max_output_tokens")) is int and 1 <= scope["max_output_tokens"] <= (131072 if extended else 16384 if v2 else 600), "Invalid output bound")
    ensure(type(scope.get("input_overhead_reserve_tokens")) is int and scope["input_overhead_reserve_tokens"] >= 4096, "Missing conservative input overhead")
    ensure(type(scope.get('total_guard_cny')) in {int, float} and math.isfinite(scope['total_guard_cny'])
           and 0 < scope['total_guard_cny'] <= (150 if extended else 50 if v2 else 5), 'Invalid finite logical batch cap')
    slots = scope["slots"]
    ensure(slots and len(slots) <= 256 and len(slots) == len({s["id"] for s in slots}), "Missing, excessive or duplicate slots")
    ensure(all(s["model"] in RATES and s.get("entity_label") and "user_text" in s for s in slots), "Slot model/entity/input scope missing")
    bound = sum((scope["max_input_bytes"] + scope["input_overhead_reserve_tokens"]) * RATES[s["model"]][0]
                + scope["max_output_tokens"] * RATES[s["model"]][1] for s in slots)
    ensure(bound <= int(Decimal(str(scope["total_guard_cny"])) * 1_000_000), "Whole batch exceeds its protection cap")
    ensure(scope["reserved_upper_micro_cny"] == bound, "Whole-batch reserve must be fixed before outputs")

class ProviderJournal:
    def __init__(self, store: TranscriptStore):
        self.store = store
        store.db.executescript("""
        CREATE TABLE IF NOT EXISTS call_batches(
          batch_id TEXT PRIMARY KEY, scope_json TEXT NOT NULL, scope_sha256 TEXT NOT NULL,
          created_at_utc TEXT NOT NULL, stopped INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS provider_calls(
          call_id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL REFERENCES turns(turn_id),
          session_id TEXT NOT NULL REFERENCES sessions(session_id),
          batch_id TEXT NOT NULL REFERENCES call_batches(batch_id), slot_id TEXT NOT NULL,
          model TEXT NOT NULL, status TEXT NOT NULL, submitted_at_utc TEXT NOT NULL,
          capture_origin TEXT NOT NULL,
          response_at_utc TEXT, request_json TEXT NOT NULL, request_sha256 TEXT NOT NULL,
          context_json TEXT NOT NULL, reserve_micro_cny INTEGER NOT NULL,
          http_status INTEGER, raw_response BLOB, raw_sha256 TEXT,
          raw_was_redacted INTEGER NOT NULL DEFAULT 0, usage_json TEXT, finish_reason TEXT,
          provider_model TEXT, error_category TEXT, estimate_peak_micro_cny INTEGER,
          UNIQUE(batch_id,slot_id));
        CREATE TABLE IF NOT EXISTS turn_lifecycle(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT NOT NULL REFERENCES turns(turn_id),
          at_utc TEXT NOT NULL, state TEXT NOT NULL, detail_json TEXT NOT NULL);
        """)

    def register_batch(self, scope: dict) -> None:
        scope_check(scope)
        text = canonical(scope).decode("utf-8")
        with self.store.transaction():
            row = self.store.db.execute("SELECT scope_sha256 FROM call_batches WHERE batch_id=?", (scope["batch_id"],)).fetchone()
            if row:
                ensure(row[0] == digest(scope), "Batch scope is immutable; use a named new revision")
            else:
                self.store.db.execute("INSERT INTO call_batches(batch_id,scope_json,scope_sha256,created_at_utc) VALUES(?,?,?,?)",
                                      (scope["batch_id"], text, digest(scope), utc_now()))

    def _transition(self, turn_id: str, state: str, detail: dict) -> None:
        self.store.db.execute("INSERT INTO turn_lifecycle(turn_id,at_utc,state,detail_json) VALUES(?,?,?,?)", (turn_id, utc_now(), state, canonical(detail).decode("utf-8")))

    def call(self, handle: SessionHandle, turn_id: str, batch_id: str, slot_id: str, context: dict,
             *, transport: Callable = official_transport, credential_reader: Callable = existing_credential) -> dict:
        self.store._authenticate(handle)
        ensure(context["turn_id"] == turn_id and context["mode"] == handle.mode, "Wrong context/turn scope")
        existing = self.store.db.execute("SELECT * FROM provider_calls WHERE turn_id=?", (turn_id,)).fetchone()
        if existing:
            ensure(existing["session_id"] == handle.session_id and existing["batch_id"] == batch_id and existing["slot_id"] == slot_id, "Turn already bound to another request")
            # Return captured or unresolved state without touching network or key.
            return self.get_call(handle, existing["call_id"])
        batch = self.store.db.execute("SELECT * FROM call_batches WHERE batch_id=?", (batch_id,)).fetchone()
        ensure(batch is not None and not batch["stopped"], "Batch missing or stopped; no automatic retry")
        scope = json.loads(batch["scope_json"])
        scope_check(scope)
        ensure(digest(scope) == batch["scope_sha256"], "Batch binding corrupted")
        slots = {s["id"]: s for s in scope["slots"]}
        ensure(slot_id in slots, "Unapproved batch slot")
        slot = slots[slot_id]
        row = self.store.get_turn(handle, turn_id)
        label = self.store.db.execute("SELECT label FROM entities WHERE entity_id=?", (handle.entity_id,)).fetchone()[0]
        ensure(handle.principal_id == scope["principal_id"] and label == slot["entity_label"], "Batch actor/entity mismatch")
        ensure(slot["user_text"] is None or slot["user_text"] == row["user_text"], "Input outside fixed batch scope")
        messages = context["messages"]
        ensure(isinstance(messages, list) and messages, "Empty model input")
        ensure(all(set(m) == {"role", "content"} and m["role"] in {"system", "user", "assistant"} and isinstance(m["content"], str) for m in messages), "Invalid provider message shape")
        ensure(messages[-1] == {"role": "user", "content": row["user_text"]}, "Latest input mismatch")
        nbytes = len(canonical(messages))
        ensure(nbytes <= scope["max_input_bytes"], "Prompt outside pinned byte budget")
        key = credential_reader()
        ensure(isinstance(key, str) and key.strip(), "Configured credential missing; no request submitted")
        ensure(key not in canonical(context).decode("utf-8"), "Credential detected in context; request refused")
        model = slot["model"]
        payload = {"model": model, "messages": messages, "max_tokens": scope["max_output_tokens"],
                   "stream": False, "thinking": {"type": "disabled"}}
        v2 = scope.get('schema_version') in {'apcore-provider-scope-2', 'apcore-provider-scope-3'}
        if v2:
            payload['thinking'] = scope['thinking']
            if scope['thinking']['type'] == 'enabled':
                payload['reasoning_effort'] = scope['reasoning_effort']
        request_bytes = canonical(payload)
        reserve = (nbytes + scope["input_overhead_reserve_tokens"]) * RATES[model][0] + scope["max_output_tokens"] * RATES[model][1]
        call_id = "call_" + uuid.uuid4().hex
        with self.store.transaction():
            # Re-check under the write lock to serialize two host processes.
            ensure(self.store.get_turn(handle, turn_id)["status"] == "RECEIVED", "Turn is not new")
            b = self.store.db.execute("SELECT stopped FROM call_batches WHERE batch_id=?", (batch_id,)).fetchone()
            ensure(b is not None and not b[0], "Batch was stopped concurrently")
            ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE batch_id=? AND status='SUBMITTED_STATUS_UNKNOWN'", (batch_id,)).fetchone() is None, "Unresolved submitted request; reconcile before another batch slot")
            if transport is official_transport:
                ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN' AND capture_origin='TARGET_PROVIDER_CAPTURE'").fetchone() is None,
                       'Unresolved real provider request in this runtime; no further chargeable submission')
            ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE batch_id=? AND slot_id=?", (batch_id, slot_id)).fetchone() is None, "Slot already consumed")
            used = self.store.db.execute("SELECT COALESCE(SUM(reserve_micro_cny),0) FROM provider_calls WHERE batch_id=?", (batch_id,)).fetchone()[0]
            ensure(used + reserve <= int(Decimal(str(scope["total_guard_cny"])) * 1_000_000), "Reserved total exceeds batch cap")
            self.store.db.execute("INSERT INTO provider_calls(call_id,turn_id,session_id,batch_id,slot_id,model,status,submitted_at_utc,capture_origin,request_json,request_sha256,context_json,reserve_micro_cny) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (call_id, turn_id, handle.session_id, batch_id, slot_id, model, "SUBMITTED_STATUS_UNKNOWN", utc_now(),
                 "TARGET_PROVIDER_CAPTURE" if transport is official_transport else "AUTHORED_PROVIDER_TEST_FIXTURE",
                 request_bytes.decode("utf-8"), hashlib.sha256(request_bytes).hexdigest(), canonical(context).decode("utf-8"), reserve))
            self.store.db.execute("UPDATE turns SET status='SUBMITTED_STATUS_UNKNOWN',request_id=? WHERE turn_id=?", (call_id, turn_id))
            self._transition(turn_id, "SUBMITTED_STATUS_UNKNOWN", {"call_id": call_id, "reserve_micro_cny": reserve, "automatic_retries": 0})
        try:
            if transport is official_transport and v2:
                status, raw = official_transport(request_bytes, key, timeout_seconds=scope['request_timeout_seconds'], hard_deadline=True)
            else:
                status, raw = transport(request_bytes, key)
        except WorkerNotSubmitted as exc:
            # Only a validated pre-HTTP receipt may avoid an UNKNOWN result.
            # It never unlocks the slot or authorizes a paid retry.
            ensure(exc.request_sha256 == hashlib.sha256(request_bytes).hexdigest(), 'Local receipt belongs to another request')
            with self.store.transaction():
                self.store.db.execute("UPDATE provider_calls SET status='LOCAL_REJECTED_BEFORE_NETWORK',response_at_utc=?,error_category=?,estimate_peak_micro_cny=0 WHERE call_id=?",
                    (utc_now(), exc.reason, call_id))
                self.store.db.execute("UPDATE turns SET status='RESPONSE_REJECTED' WHERE turn_id=?", (turn_id,))
                self.store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (batch_id,))
                self._transition(turn_id, 'LOCAL_REJECTED_BEFORE_NETWORK', {
                    'call_id': call_id, 'request_sha256': exc.request_sha256,
                    'worker_stage': 'INPUT_VALIDATION', 'network_attempted': False,
                    'local_receipt_validated': True, 'automatic_paid_retries': 0})
            key = None
            return self.get_call(handle, call_id)
        except WorkerRemoteOutcomeUnknown as exc:
            # The worker crossed into the HTTP path, so the remote effect is
            # deliberately left UNKNOWN. The sanitized receipt only improves
            # diagnosis; it never permits a retry or a zero-cost conclusion.
            ensure(exc.request_sha256 == hashlib.sha256(request_bytes).hexdigest(),
                   'Remote-unknown receipt belongs to another request')
            category = 'PROVIDER_WORKER_REMOTE_OUTCOME_UNKNOWN/' + exc.reason
            with self.store.transaction():
                self.store.db.execute("UPDATE provider_calls SET error_category=? WHERE call_id=?", (category, call_id))
                self.store.db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (batch_id,))
                self._transition(turn_id, 'SUBMITTED_STATUS_UNKNOWN', {
                    'call_id': call_id, 'request_sha256': exc.request_sha256,
                    'worker_stage': exc.stage, 'network_phase_entered': True,
                    'remote_outcome_known': False, 'child_error_class': exc.reason,
                    'network_error': exc.network_error,
                    'batch_stopped': True, 'automatic_paid_retries': 0})
            key = None
            return self.get_call(handle, call_id)
        except Exception as exc:
            # Never log exception text; it may contain request headers/secrets.
            with self.store.transaction():
                self.store.db.execute("UPDATE provider_calls SET error_category=? WHERE call_id=?", (type(exc).__name__, call_id))
                self.store.db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (batch_id,))
                self._transition(turn_id, "SUBMITTED_STATUS_UNKNOWN", {"error_category": type(exc).__name__, "batch_stopped": True})
            key = None
            return self.get_call(handle, call_id)
        raw_hash = hashlib.sha256(raw).hexdigest()
        redacted = key.encode("utf-8") in raw
        stored_raw = raw.replace(key.encode("utf-8"), b"[REDACTED_CONFIGURED_CREDENTIAL]") if redacted else raw
        key = None
        outcome, category, text, finish, usage, provider_model, estimate = "RESPONSE_REJECTED", None, None, None, None, None, None
        try:
            ensure(len(raw) <= MAX_RESPONSE_BYTES, "RESPONSE_TOO_LARGE")
            ensure(not redacted, "SECRET_ECHO_QUARANTINED")
            ensure(status == 200, "HTTP_ERROR")
            body = json.loads(raw.decode("utf-8"))
            ensure(isinstance(body, dict), 'INVALID_RESPONSE_OBJECT')
            usage = body.get("usage")
            provider_model = body.get("model")
            validate_provider_model(model, provider_model, strict_version=v2)
            ensure(isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("prompt_tokens", "completion_tokens", "total_tokens")), "INVALID_USAGE")
            ensure(usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], "USAGE_TOTAL_MISMATCH")
            details = usage.get('completion_tokens_details')
            if details is not None:
                ensure(isinstance(details, dict), 'INVALID_COMPLETION_DETAILS')
                reasoning_tokens = details.get('reasoning_tokens')
                if reasoning_tokens is not None:
                    ensure(type(reasoning_tokens) is int and 0 <= reasoning_tokens <= usage['completion_tokens'],
                           'INVALID_REASONING_TOKEN_ACCOUNTING')
            hits = usage.get("prompt_cache_hit_tokens", 0)
            misses = usage.get("prompt_cache_miss_tokens", usage["prompt_tokens"] - hits)
            ensure(type(hits) is int and type(misses) is int and hits >= 0 and misses >= 0 and hits + misses == usage["prompt_tokens"], "CACHE_USAGE_MISMATCH")
            # Valid usage remains chargeable even when final text is unusable.
            # Exact decimal arithmetic avoids rounding a binary float upward.
            amount = (Decimal(misses) * Decimal(str(RATES[model][0])) +
                      Decimal(hits) * Decimal(str(RATES[model][2])) +
                      Decimal(usage['completion_tokens']) * Decimal(str(RATES[model][1])))
            estimate = int(amount.to_integral_value(rounding=ROUND_CEILING))
            ensure(usage["prompt_tokens"] <= nbytes + scope["input_overhead_reserve_tokens"] and usage["completion_tokens"] <= scope["max_output_tokens"], "USAGE_EXCEEDS_RESERVED_BOUND")
            choices = body.get('choices')
            ensure(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict), 'INVALID_RESPONSE_CHOICES')
            choice = choices[0]
            finish = choice.get('finish_reason')
            message = choice.get('message')
            ensure(isinstance(message, dict), 'INVALID_RESPONSE_MESSAGE')
            ensure(finish == "stop", "TRUNCATED_OR_OTHER_FINISH")
            ensure(not message.get("tool_calls"), "UNEXPECTED_TOOL_CALL")
            text = message.get("content")
            ensure(isinstance(text, str) and text.strip(), "EMPTY_RESPONSE")
            outcome = "RESPONSE_CAPTURED"
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as exc:
            category = str(exc) if isinstance(exc, StoreGuard) else type(exc).__name__
        with self.store.transaction():
            self.store.db.execute("UPDATE provider_calls SET status=?,response_at_utc=?,http_status=?,raw_response=?,raw_sha256=?,raw_was_redacted=?,usage_json=?,finish_reason=?,provider_model=?,error_category=?,estimate_peak_micro_cny=? WHERE call_id=?",
                (outcome, utc_now(), status, stored_raw, raw_hash, int(redacted), json.dumps(usage) if usage is not None else None, finish, provider_model, category, estimate, call_id))
            if outcome == "RESPONSE_CAPTURED":
                self.store.db.execute("UPDATE turns SET status='RESPONSE_CAPTURED',assistant_text=?,response_at_utc=?,response_provenance=? WHERE turn_id=?", (text, utc_now(), "TARGET_PROVIDER_CAPTURE" if transport is official_transport else "AUTHORED_TEST_STUB", turn_id))
            else:
                self.store.db.execute("UPDATE turns SET status='RESPONSE_REJECTED' WHERE turn_id=?", (turn_id,))
                self.store.db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (batch_id,))
            self._transition(turn_id, outcome, {"call_id": call_id, "error_category": category, "semantic_verdict": None})
        return self.get_call(handle, call_id)

    def get_call(self, handle: SessionHandle, call_id: str) -> dict:
        self.store._authenticate(handle)
        row = self.store.db.execute("SELECT * FROM provider_calls WHERE call_id=? AND session_id=?", (call_id, handle.session_id)).fetchone()
        ensure(row is not None, "Call unavailable for this session")
        result = dict(row)
        result.pop("raw_response")
        return result

    def summary(self, batch_id: str) -> dict:
        # Host-only administrative scope, never sent to the character model.
        rows = [dict(r) for r in self.store.db.execute("SELECT call_id,slot_id,model,status,reserve_micro_cny,estimate_peak_micro_cny,usage_json,error_category FROM provider_calls WHERE batch_id=? ORDER BY submitted_at_utc", (batch_id,))]
        complete = all(r['estimate_peak_micro_cny'] is not None for r in rows)
        subtotal = sum(r['estimate_peak_micro_cny'] or 0 for r in rows) / 1_000_000
        return {"batch_id": batch_id, "calls": rows, "calls_submitted": len(rows),
                "calls_recorded": len(rows),
                "local_pre_network_rejections": sum(r['status'] == 'LOCAL_REJECTED_BEFORE_NETWORK' for r in rows),
                "remote_outcome_unknown_count": sum(r['status'] == 'SUBMITTED_STATUS_UNKNOWN' for r in rows),
                "reserved_cny": sum(r["reserve_micro_cny"] for r in rows) / 1_000_000,
                "peak_usage_estimate_cny": subtotal if complete else None,
                "known_peak_usage_subtotal_cny": subtotal,
                "unestimated_call_count": sum(r['estimate_peak_micro_cny'] is None for r in rows),
                "estimate_complete": complete,
                "billing_verified": False, "automatic_paid_retries": 0}
