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
import provider_transport as lifecycle_transport
from provider_network_route import check_route_policy
import provider_contract as adapter_contract
import provider_adapters

CHAT_COMPLETIONS_ENDPOINT = "https://api.deepseek.com/chat/completions"
RESPONSES_ENDPOINT = "https://api.deepseek.com/responses"
ENDPOINT = CHAT_COMPLETIONS_ENDPOINT
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
                       hard_deadline: bool = False, transport_policy: dict | None = None,
                       on_lifecycle: Callable = lambda event: None) -> tuple[int, bytes]:
    if transport_policy is not None:
        ensure(hard_deadline, 'Lifecycle transport requires an owned worker')
        return lifecycle_transport.worker_exchange(payload, credential, timeout_seconds,
            transport_policy, _worker_command(), WORKSPACE, on_lifecycle)
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
    version = scope.get('schema_version')
    if version == adapter_contract.FORMAL_SCOPE_VERSION:
        adapter_contract.check_formal_scope(scope, provider_adapters.select(scope))
        return
    if version == adapter_contract.SCOPE_VERSION:
        adapter_contract.check_scope(scope, provider_adapters.select(scope))
        return
    adapter_contract.guard_legacy_identity(scope)
    ensure(scope.get("automatic_paid_retries") == 0, "Automatic provider retries are forbidden")
    ensure(version in {None, 'apcore-provider-scope-1', 'apcore-provider-scope-2', 'apcore-provider-scope-3', 'apcore-provider-scope-4', 'apcore-provider-scope-5'}, 'Unsupported provider scope version')
    if version == 'apcore-provider-scope-5':
        check_route_policy(scope.get('network_route_policy'))
    else:
        ensure('network_route_policy' not in scope, 'Explicit network route requires scope5')
    responses_api = version in {'apcore-provider-scope-4', 'apcore-provider-scope-5'}
    if responses_api:
        ensure(scope.get('endpoint') == RESPONSES_ENDPOINT and scope.get('api_protocol') == 'responses',
               'Responses scope endpoint/protocol mismatch')
    else:
        ensure(scope.get('endpoint') == ENDPOINT and 'api_protocol' not in scope,
               'Unsupported endpoint/protocol for legacy scope')
    extended = version in {'apcore-provider-scope-3', 'apcore-provider-scope-4', 'apcore-provider-scope-5'}
    v2 = version in {'apcore-provider-scope-2', 'apcore-provider-scope-3', 'apcore-provider-scope-4', 'apcore-provider-scope-5'}
    if extended:
        ensure(scope.get('capacity_policy_id') == 'EXTENDED_MAX_REASONING_20260911', 'Explicit capacity revision policy required')
        ensure(scope.get('output_budget_includes_reasoning') is True, 'Reasoning must count inside the completion budget')
        ensure(scope.get('automatic_capacity_escalation') is False, 'Automatic capacity escalation is not allowed')
    if v2:
        try:
            date.fromisoformat(scope['pricing_verified_date'])
        except (ValueError, TypeError, KeyError):
            raise StoreGuard('Explicit ISO pricing verification date required') from None
        ensure(scope.get('tools_allowed') is False, 'Only text requests without tools are allowed')
        if 'transport_policy' in scope:
            lifecycle_transport.check_policy(scope['transport_policy'], scope['request_timeout_seconds'])
            ensure(type(scope.get('stream')) is bool, 'Explicit streaming policy required')
        else:
            ensure(scope.get('stream') is False, 'Streaming requires a versioned lifecycle policy')
        if responses_api:
            ensure(scope.get('stream') is True and 'transport_policy' in scope,
                   'Responses API validation requires lifecycle streaming')
            ensure(scope.get('thinking') == {'type': 'enabled'} and scope.get('reasoning_effort') == 'max',
                   'Responses scope requires enabled max reasoning')
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
        CREATE TABLE IF NOT EXISTS transport_wire_captures(
          call_id TEXT PRIMARY KEY REFERENCES provider_calls(call_id),
          wire_format TEXT NOT NULL, wire_bytes BLOB NOT NULL, wire_sha256 TEXT NOT NULL,
          complete INTEGER NOT NULL, credential_redacted INTEGER NOT NULL);
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

    def _capture_wire(self, call_id, wire, key, stream, complete, wire_format=None):
        secret = key.encode('utf-8')
        redacted = secret in wire
        saved = wire.replace(secret, b'[REDACTED_CONFIGURED_CREDENTIAL]') if redacted else wire
        self.store.db.execute('INSERT INTO transport_wire_captures VALUES(?,?,?,?,?,?)',
            (call_id, wire_format or ('SSE' if stream else 'JSON'), saved, hashlib.sha256(saved).hexdigest(), int(complete), int(redacted)))

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
        formal = scope.get('schema_version') == adapter_contract.FORMAL_SCOPE_VERSION
        generic = formal or scope.get('schema_version') == adapter_contract.SCOPE_VERSION
        adapter = provider_adapters.select(scope) if generic else None
        actual_provider = transport is official_transport and (adapter is None or adapter.capabilities.network_access)
        if generic and not formal:
            ensure(handle.mode == 'CHARACTER_SIMULATION', 'INDEPENDENT_VALIDATION_REQUIRES_SIMULATION_MODE')
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
        model = slot["model"]
        v2 = scope.get('schema_version') in {'apcore-provider-scope-2', 'apcore-provider-scope-3', 'apcore-provider-scope-4', 'apcore-provider-scope-5'}
        responses_api = scope.get('schema_version') in {'apcore-provider-scope-4', 'apcore-provider-scope-5'}
        if generic:
            payload = adapter.serialize(scope, model, messages)
        elif responses_api:
            payload = {"model": model, "input": messages, "max_output_tokens": scope["max_output_tokens"],
                       "stream": True, "reasoning": {"effort": scope['reasoning_effort']}}
        else:
            payload = {"model": model, "messages": messages, "max_tokens": scope["max_output_tokens"],
                       "stream": False, "thinking": {"type": "disabled"}}
            if v2:
                payload['thinking'] = scope['thinking']
                if scope['thinking']['type'] == 'enabled':
                    payload['reasoning_effort'] = scope['reasoning_effort']
                payload['stream'] = scope['stream']
                if scope['stream']:
                    payload['stream_options'] = {'include_usage': True}
        request_bytes = canonical(payload)
        input_receipt = None
        if formal:
            from provider_openai import local_input_bound, verify_input_receipt
            input_receipt = local_input_bound(scope, request_bytes)
        # All formal identity, serialization and local proof checks precede any
        # credential access, journal allocation or network action.
        key = (adapter.credential() if generic and (not adapter.capabilities.network_access
               or credential_reader is existing_credential) else credential_reader())
        ensure(isinstance(key, str) and key.strip(), "Configured credential missing; no request submitted")
        ensure(key not in canonical(context).decode("utf-8"), "Credential detected in context; request refused")
        reserve = (adapter.reserve(scope, model, nbytes) if generic else
            (nbytes + scope["input_overhead_reserve_tokens"]) * RATES[model][0] + scope["max_output_tokens"] * RATES[model][1])
        call_id = "call_" + uuid.uuid4().hex
        with self.store.transaction():
            if formal:
                verify_input_receipt(scope, request_bytes, input_receipt)
            # Re-check under the write lock to serialize two host processes.
            ensure(self.store.get_turn(handle, turn_id)["status"] == "RECEIVED", "Turn is not new")
            b = self.store.db.execute("SELECT stopped FROM call_batches WHERE batch_id=?", (batch_id,)).fetchone()
            ensure(b is not None and not b[0], "Batch was stopped concurrently")
            ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE batch_id=? AND status='SUBMITTED_STATUS_UNKNOWN'", (batch_id,)).fetchone() is None, "Unresolved submitted request; reconcile before another batch slot")
            if actual_provider:
                ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE status='SUBMITTED_STATUS_UNKNOWN' AND capture_origin='TARGET_PROVIDER_CAPTURE'").fetchone() is None,
                       'Unresolved real provider request in this runtime; no further chargeable submission')
            ensure(self.store.db.execute("SELECT call_id FROM provider_calls WHERE batch_id=? AND slot_id=?", (batch_id, slot_id)).fetchone() is None, "Slot already consumed")
            used = self.store.db.execute("SELECT COALESCE(SUM(reserve_micro_cny),0) FROM provider_calls WHERE batch_id=?", (batch_id,)).fetchone()[0]
            if reserve is not None:
                ensure(used + reserve <= int(Decimal(str(scope["total_guard_cny"])) * 1_000_000), "Reserved total exceeds batch cap")
            self.store.db.execute("INSERT INTO provider_calls(call_id,turn_id,session_id,batch_id,slot_id,model,status,submitted_at_utc,capture_origin,request_json,request_sha256,context_json,reserve_micro_cny) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (call_id, turn_id, handle.session_id, batch_id, slot_id, model, "SUBMITTED_STATUS_UNKNOWN", utc_now(),
                 "TARGET_PROVIDER_CAPTURE" if actual_provider else "AUTHORED_PROVIDER_TEST_FIXTURE",
                 request_bytes.decode("utf-8"), hashlib.sha256(request_bytes).hexdigest(), canonical(context).decode("utf-8"), reserve if reserve is not None else 0))
            if generic:
                # Legacy non-null money column is only a compatibility placeholder.
                # The additive contract row carries the actual nullable reserve.
                self.store.db.execute('CREATE TABLE IF NOT EXISTS provider_call_contracts('
                    'call_id TEXT PRIMARY KEY REFERENCES provider_calls(call_id),contract_json TEXT NOT NULL)')
                binding = {'provider_id': scope['provider_id'], 'model_id': model, 'api_protocol': scope['api_protocol'],
                    'generation_identity': adapter_contract.generation_identity(scope, model, messages),
                    'scope_sha256': batch['scope_sha256'], 'source_binding': scope['source_binding'],
                    'reserve': {'micro_cny': reserve, 'input_tokens': nbytes + scope['input_overhead_reserve_tokens'],
                                'output_tokens': scope['max_output_tokens']},
                    'spend_policy': scope['spend_policy'], 'billing_certified': False, 'semantic_acceptance': False}
                if formal:
                    binding.update(input_bound_receipt=input_receipt, request_sha256=hashlib.sha256(request_bytes).hexdigest(),
                        native_receipt_version='APCORE_OPENAI_NATIVE_RECEIPT_1')
                    binding['reserve']['input_tokens']=28672
                self.store.db.execute('INSERT INTO provider_call_contracts VALUES(?,?)', (call_id, canonical(binding).decode()))
            self.store.db.execute("UPDATE turns SET status='SUBMITTED_STATUS_UNKNOWN',request_id=? WHERE turn_id=?", (call_id, turn_id))
            self._transition(turn_id, "SUBMITTED_STATUS_UNKNOWN", {"call_id": call_id, "reserve_micro_cny": reserve, "automatic_retries": 0})
        try:
            if generic:
                def record_adapter_lifecycle(event):
                    lifecycle_transport.check_event(event)
                    with self.store.transaction():
                        self._transition(turn_id, 'TRANSPORT_LIFECYCLE', {'call_id': call_id, **event})
                result = (adapter.exchange(scope, request_bytes, key, record_adapter_lifecycle, _worker_command())
                          if transport is official_transport else transport(request_bytes, key))
                provider_adapters.verified_result(adapter, scope, result)
                status, raw = result
                with self.store.transaction():
                    self._capture_wire(call_id, result.wire, key, scope['stream'], True, getattr(adapter, 'wire_format', None))
            elif transport is official_transport and v2:
                if 'transport_policy' in scope:
                    def record_lifecycle(event):
                        lifecycle_transport.check_event(event)
                        with self.store.transaction():
                            self._transition(turn_id, 'TRANSPORT_LIFECYCLE', {'call_id': call_id, **event})
                    if responses_api:
                        route_args = ({'network_route_policy': scope['network_route_policy']}
                                      if 'network_route_policy' in scope else {})
                        result = lifecycle_transport.worker_exchange(request_bytes, key, scope['request_timeout_seconds'],
                            scope['transport_policy'], _worker_command(), WORKSPACE, record_lifecycle, responses=True, **route_args)
                    else:
                        result = official_transport(request_bytes, key, timeout_seconds=scope['request_timeout_seconds'],
                            hard_deadline=True, transport_policy=scope['transport_policy'], on_lifecycle=record_lifecycle)
                    if responses_api:
                        lifecycle_transport.verify_responses_result(result)
                    status, raw = result
                    with self.store.transaction():
                        self._capture_wire(call_id, result.wire, key, scope['stream'], True)
                else:
                    status, raw = official_transport(request_bytes, key, timeout_seconds=scope['request_timeout_seconds'], hard_deadline=True)
            else:
                status, raw = transport(request_bytes, key)
        except lifecycle_transport.TransportFault as exc:
            with self.store.transaction():
                self.store.db.execute('UPDATE provider_calls SET error_category=?,http_status=? WHERE call_id=?',
                    (exc.reason, exc.status, call_id))
                self.store.db.execute('UPDATE call_batches SET stopped=1 WHERE batch_id=?', (batch_id,))
                self._capture_wire(call_id, exc.wire, key, scope.get('stream', False), False, getattr(adapter, 'wire_format', None))
                self._transition(turn_id, 'SUBMITTED_STATUS_UNKNOWN', {'call_id': call_id,
                    'timeout_source': exc.reason if exc.reason in lifecycle_transport.TIMEOUTS else None,
                    'error_category': exc.reason, 'batch_stopped': True, 'remote_outcome_known': False,
                    'automatic_paid_retries': 0, 'partial_response_is_reply': False,
                    **({'transport_diagnostics': exc.diagnostics} if exc.diagnostics is not None else {})})
            key = None
            return self.get_call(handle, call_id)
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
        terminal_known = False
        terminal_status = None
        terminal_rejection = None
        validated_terminal_rejection = False
        native_terminal_event = None
        generic_rejection = None
        formal_usage = None
        if generic:
            terminal_status, native_terminal_event, generic_rejection = adapter.terminal(scope, json.loads(raw))
            terminal_known = True  # Native wire was revalidated before this layer.
        try:
            ensure(len(raw) <= MAX_RESPONSE_BYTES, "RESPONSE_TOO_LARGE")
            ensure(not redacted, "SECRET_ECHO_QUARANTINED")
            ensure(status == 200, "HTTP_ERROR")
            body = json.loads(raw.decode("utf-8"))
            ensure(isinstance(body, dict), 'INVALID_RESPONSE_OBJECT')
            if generic:
                terminal_status, native_terminal_event, generic_rejection = adapter.terminal(scope, body)
                terminal_known = True
            if responses_api:
                terminal_status=body.get('responses_api_status')
                terminal_known=terminal_status in ('completed','incomplete','failed')
                terminal_rejection=body.get('responses_terminal_rejection')
                if terminal_rejection is not None:
                    ensure(isinstance(terminal_rejection,dict)
                           and terminal_rejection.get('version')=='apcore-responses-terminal-1'
                           and terminal_rejection.get('terminal_event')=='response.'+str(terminal_status)
                           and terminal_rejection.get('response_id')==body.get('id')
                           and isinstance(terminal_rejection.get('reason'),str)
                           and terminal_rejection['reason'].startswith('RESPONSES_'),
                           'INVALID_RESPONSES_TERMINAL_REJECTION')
                    validated_terminal_rejection = True
            usage = body.get("usage")
            provider_model = body.get("model")
            observed_choices = body.get('choices')
            if (isinstance(observed_choices, list) and len(observed_choices) == 1
                    and isinstance(observed_choices[0], dict)):
                observed_finish = observed_choices[0].get('finish_reason')
                if observed_finish in lifecycle_transport.FINISHES:
                    finish = observed_finish
            if formal:
                formal_usage = adapter_contract.formal_accounting(body.get('native_usage'),scope,model,
                    input_receipt['input_upper_tokens'],body['choices'][0]['message']['content'])
                estimate = formal_usage['estimate_micro_cny']
                adapter.verify_effective_identity(scope,body,model)
                ensure(formal_usage['rejection'] is None, formal_usage['rejection'] or 'OPENAI_USAGE_REJECTED')
            if generic:
                adapter.validate_model(model, provider_model)
            else:
                validate_provider_model(model, provider_model, strict_version=v2)
            # Valid usage remains chargeable even when final text is unusable.
            # Exact decimal arithmetic avoids rounding a binary float upward.
            if not formal:
                estimate = adapter_contract.estimate_usage(usage, adapter.rates(scope, model) if generic else RATES[model])
                ensure(usage["prompt_tokens"] <= nbytes + scope["input_overhead_reserve_tokens"] and usage["completion_tokens"] <= scope["max_output_tokens"], "USAGE_EXCEEDS_RESERVED_BOUND")
            if terminal_rejection is not None:
                raise StoreGuard(terminal_rejection['reason'])
            if generic_rejection is not None:
                raise StoreGuard(generic_rejection)
            if isinstance(observed_choices, list) and len(observed_choices) == 1 and isinstance(observed_choices[0], dict):
                finish = observed_choices[0].get('finish_reason')
            text, finish = adapter_contract.usable_reply(body, responses_api=responses_api or formal)
            if generic:
                ensure(terminal_status == 'completed', 'PROVIDER_NOT_COMPLETED')
            outcome = "RESPONSE_CAPTURED"
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as exc:
            category = str(exc) if isinstance(exc, StoreGuard) else type(exc).__name__
        if validated_terminal_rejection and category == 'INVALID_USAGE':
            category = terminal_rejection['reason']
        if generic_rejection and category == 'INVALID_USAGE':
            category = generic_rejection
        if outcome != 'RESPONSE_CAPTURED' and terminal_known:
            outcome = 'RESPONSE_REJECTED_TERMINAL_KNOWN'
        with self.store.transaction():
            if formal:
                bound = json.loads(self.store.db.execute('SELECT contract_json FROM provider_call_contracts WHERE call_id=?',(call_id,)).fetchone()[0])
                safe_body = json.loads(stored_raw)
                bound.update(native_response_sha256=digest(safe_body.get('native_response')),accounting=formal_usage,
                    native_usage=safe_body.get('native_usage'),raw_sha256=raw_hash,
                    remote_outcome='KNOWN_TERMINAL',response_usable=outcome=='RESPONSE_CAPTURED',
                    wire_sha256=self.store.db.execute('SELECT wire_sha256 FROM transport_wire_captures WHERE call_id=?',(call_id,)).fetchone()[0])
                self.store.db.execute('UPDATE provider_call_contracts SET contract_json=? WHERE call_id=?',(canonical(bound).decode(),call_id))
            self.store.db.execute("UPDATE provider_calls SET status=?,response_at_utc=?,http_status=?,raw_response=?,raw_sha256=?,raw_was_redacted=?,usage_json=?,finish_reason=?,provider_model=?,error_category=?,estimate_peak_micro_cny=? WHERE call_id=?",
                (outcome, utc_now(), status, stored_raw, raw_hash, int(redacted), json.dumps(usage) if usage is not None else None, finish, provider_model, category, estimate, call_id))
            if outcome == "RESPONSE_CAPTURED":
                self.store.db.execute("UPDATE turns SET status='RESPONSE_CAPTURED',assistant_text=?,response_at_utc=?,response_provenance=? WHERE turn_id=?", (text, utc_now(), "TARGET_PROVIDER_CAPTURE" if actual_provider else "AUTHORED_TEST_STUB", turn_id))
            else:
                self.store.db.execute("UPDATE turns SET status='RESPONSE_REJECTED' WHERE turn_id=?", (turn_id,))
                self.store.db.execute("UPDATE call_batches SET stopped=1 WHERE batch_id=?", (batch_id,))
            detail={"call_id":call_id,"error_category":category,"semantic_verdict":None}
            if terminal_known:
                detail.update(remote_outcome_known=True,response_usable=outcome=='RESPONSE_CAPTURED',
                    terminal_event=native_terminal_event or 'response.'+terminal_status,terminal_status=terminal_status,
                    batch_stopped=outcome!='RESPONSE_CAPTURED',automatic_paid_retries=0,slot_consumed=True)
                if validated_terminal_rejection:
                    detail['usage_validation_error']=terminal_rejection.get('usage_error')
            self._transition(turn_id, outcome, detail)
        return self.get_call(handle, call_id)

    def get_call(self, handle: SessionHandle, call_id: str) -> dict:
        self.store._authenticate(handle)
        row = self.store.db.execute("SELECT * FROM provider_calls WHERE call_id=? AND session_id=?", (call_id, handle.session_id)).fetchone()
        ensure(row is not None, "Call unavailable for this session")
        result = dict(row)
        result.pop("raw_response")
        scope = json.loads(self.store.db.execute('SELECT scope_json FROM call_batches WHERE batch_id=?', (row['batch_id'],)).fetchone()[0])
        if scope.get('schema_version') in (adapter_contract.SCOPE_VERSION, adapter_contract.FORMAL_SCOPE_VERSION):
            bound = self.store.db.execute('SELECT contract_json FROM provider_call_contracts WHERE call_id=?', (call_id,)).fetchone()
            ensure(bound is not None, 'PROVIDER_CALL_CONTRACT_MISSING')
            binding = json.loads(bound[0])
            ensure(binding['scope_sha256'] == digest(scope)
                   and binding['provider_id'] == scope['provider_id'] and binding['model_id'] == row['model']
                   and binding['api_protocol'] == scope['api_protocol'] and binding['source_binding'] == scope['source_binding']
                   and binding['generation_identity'] == adapter_contract.generation_identity(scope, row['model'], json.loads(row['context_json'])['messages']),
                   'PROVIDER_CALL_CONTRACT_CHANGED')
            result.update(provider_binding=binding, reserve_micro_cny=binding['reserve']['micro_cny'], billing_certified=False,
                          usage_status='KNOWN' if adapter_contract.usage_known(row['usage_json']) else 'UNKNOWN',
                          estimate_status='ESTIMATED' if row['estimate_peak_micro_cny'] is not None else 'UNESTIMATED')
            if scope.get('schema_version') == adapter_contract.FORMAL_SCOPE_VERSION:
                ensure(binding['request_sha256']==row['request_sha256'], 'OPENAI_CALL_REQUEST_CHANGED')
                accounting=binding.get('accounting') or {}
                result.update(native_usage=binding.get('native_usage'),
                    usage_status=accounting.get('accounting_status','UNKNOWN'),
                    estimate_status=accounting.get('accounting_status','UNESTIMATED'))
        return result

    def summary(self, batch_id: str) -> dict:
        # Host-only administrative scope, never sent to the character model.
        rows = [dict(r) for r in self.store.db.execute("SELECT call_id,slot_id,model,status,reserve_micro_cny,estimate_peak_micro_cny,usage_json,error_category FROM provider_calls WHERE batch_id=? ORDER BY submitted_at_utc", (batch_id,))]
        batch = self.store.db.execute('SELECT scope_json FROM call_batches WHERE batch_id=?', (batch_id,)).fetchone()
        scope = json.loads(batch[0]) if batch else {}
        formal = scope.get('schema_version') == adapter_contract.FORMAL_SCOPE_VERSION
        generic = formal or scope.get('schema_version') == adapter_contract.SCOPE_VERSION
        if generic:
            for row in rows:
                binding = json.loads(self.store.db.execute('SELECT contract_json FROM provider_call_contracts WHERE call_id=?', (row['call_id'],)).fetchone()[0])
                row.update(reserve_micro_cny=binding['reserve']['micro_cny'], reserve=binding['reserve'],
                           provider_id=binding['provider_id'], generation_identity=binding['generation_identity'])
                if formal:
                    row['native_accounting_status']=(binding.get('accounting') or {}).get('accounting_status','UNKNOWN')
        complete = all(r['estimate_peak_micro_cny'] is not None for r in rows)
        if formal:
            complete = all(r['native_accounting_status']=='ESTIMATED_FROM_COMPLETE_USAGE' for r in rows)
        subtotal = sum(r['estimate_peak_micro_cny'] or 0 for r in rows) / 1_000_000
        return {"batch_id": batch_id, "calls": rows, "calls_submitted": len(rows),
                "calls_recorded": len(rows),
                "local_pre_network_rejections": sum(r['status'] == 'LOCAL_REJECTED_BEFORE_NETWORK' for r in rows),
                "remote_outcome_unknown_count": sum(r['status'] == 'SUBMITTED_STATUS_UNKNOWN' for r in rows),
                "terminal_known_rejected_count": sum(r['status'] == 'RESPONSE_REJECTED_TERMINAL_KNOWN' for r in rows),
                "reserved_cny": (None if any(r['reserve_micro_cny'] is None for r in rows) else sum(r["reserve_micro_cny"] for r in rows) / 1_000_000),
                "peak_usage_estimate_cny": subtotal if complete else None,
                "known_peak_usage_subtotal_cny": subtotal,
                "unestimated_call_count": sum(r['estimate_peak_micro_cny'] is None for r in rows),
                "estimate_complete": complete,
                "billing_verified": False, "automatic_paid_retries": 0,
                **({'billing_certified': False, 'provider_id': scope['provider_id'],
                    'accounting_status': 'ESTIMATED' if complete else 'UNESTIMATED',
                    'known_usage_count': sum(r['native_accounting_status']=='ESTIMATED_FROM_COMPLETE_USAGE' if formal else adapter_contract.usage_known(r['usage_json']) for r in rows),
                    'unknown_usage_count': sum(r['native_accounting_status']!='ESTIMATED_FROM_COMPLETE_USAGE' if formal else not adapter_contract.usage_known(r['usage_json']) for r in rows),
                    'semantic_acceptance': False} if generic else {})}
