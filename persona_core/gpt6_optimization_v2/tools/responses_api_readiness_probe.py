from __future__ import annotations

import hashlib
import json
import argparse
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
RUNTIME = WORKSPACE / "persona_core" / "operational_runtime_v1"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from provider import existing_credential  # noqa: E402


ENDPOINT = "https://api.deepseek.com/responses"
MODEL = "deepseek-v4-pro"
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(canonical(value) + b"\n")
    tmp.replace(path)


def profile_config(profile: str) -> tuple[Path, str, str, int, float]:
    root = WORKSPACE / "persona_core" / "gpt6_optimization_v2"
    if profile == "short":
        return (
            root / "responses_api_readiness_20260919",
            "This is a transport-readiness probe. Return a short ordinary answer and do not call tools.",
            "Synthetic transport probe. Reply with one short sentence confirming completion.",
            2048,
            0.055296,
        )
    if profile == "transport-equivalent":
        return (
            root / "responses_api_transport_equivalent_20260919",
            "This is a synthetic transport stress probe. Do not call tools and do not discuss real users or projects.",
            "Produce exactly 600 numbered items. Each item must be one grammatical sentence of 12 to 20 English words about an invented neutral topic. Do not stop early and do not add a preface or conclusion.",
            32768,
            0.884736,
        )
    raise ValueError("unsupported profile")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("short", "transport-equivalent"), default="short")
    args = parser.parse_args()
    out_dir, synthetic_system, synthetic_user, max_output_tokens, peak_cost = profile_config(args.profile)
    intent_path = out_dir / "INTENT.json"
    result_path = out_dir / "RESULT.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    if intent_path.exists() or result_path.exists():
        raise SystemExit("Probe already has durable intent/result; refusing any repeat submission")
    payload = {
        "model": MODEL,
        "input": [
            {"role": "system", "content": synthetic_system},
            {"role": "user", "content": synthetic_user},
        ],
        "reasoning": {"effort": "max"},
        "max_output_tokens": max_output_tokens,
        "stream": True,
    }
    payload_bytes = canonical(payload)
    intent = {
        "schema": "apcore-responses-api-readiness-1",
        "created_at_utc": now(),
        "endpoint": ENDPOINT,
        "model": MODEL,
        "reasoning_effort": "max",
        "max_output_tokens": max_output_tokens,
        "stream": True,
        "automatic_paid_retries": 0,
        "synthetic_only": True,
        "external44_used": False,
        "heldout_used": False,
        "original82_used": False,
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "estimated_peak_output_cost_cny": peak_cost,
        "profile": args.profile,
        "repeat_submission_allowed": False,
    }
    atomic_write(intent_path, intent)

    credential = existing_credential()
    if not credential:
        atomic_write(result_path, {
            **intent,
            "finished_at_utc": now(),
            "status": "LOCAL_NOT_SUBMITTED",
            "reason": "CREDENTIAL_UNAVAILABLE",
            "network_attempted": False,
        })
        return 2

    req = urllib.request.Request(
        ENDPOINT,
        data=payload_bytes,
        method="POST",
        headers={
            "Authorization": "Bearer " + credential,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "Amadeus-G6-Responses-Readiness-V1",
        },
    )

    started = time.monotonic()
    submitted_at = now()
    http_status = None
    first_byte_ms = None
    first_event_ms = None
    terminal_event = None
    terminal_status = None
    event_count = 0
    last_sequence = -1
    response_id_sha256 = None
    usage_present = False
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            http_status = int(response.status)
            current_event = None
            data_lines: list[bytes] = []
            while True:
                line = response.readline()
                if line and first_byte_ms is None:
                    first_byte_ms = round((time.monotonic() - started) * 1000)
                if not line:
                    break
                stripped = line.rstrip(b"\r\n")
                if stripped.startswith(b"event:"):
                    current_event = stripped[6:].strip().decode("utf-8", "strict")
                elif stripped.startswith(b"data:"):
                    data_lines.append(stripped[5:].lstrip())
                elif stripped == b"" and data_lines:
                    raw = b"\n".join(data_lines)
                    data_lines = []
                    obj = json.loads(raw)
                    event_type = obj.get("type") or current_event
                    current_event = None
                    if first_event_ms is None:
                        first_event_ms = round((time.monotonic() - started) * 1000)
                    sequence = obj.get("sequence_number")
                    if not isinstance(sequence, int) or sequence <= last_sequence:
                        raise RuntimeError("NON_MONOTONIC_SEQUENCE")
                    last_sequence = sequence
                    event_count += 1
                    if event_type in {"response.created", "response.in_progress", "response.completed", "response.incomplete", "response.failed"}:
                        response_obj = obj.get("response")
                        if isinstance(response_obj, dict):
                            rid = response_obj.get("id")
                            if isinstance(rid, str):
                                digest = hashlib.sha256(rid.encode("utf-8")).hexdigest()
                                if response_id_sha256 is not None and digest != response_id_sha256:
                                    raise RuntimeError("RESPONSE_ID_CHANGED")
                                response_id_sha256 = digest
                            if response_obj.get("usage") is not None:
                                usage_present = True
                    if event_type in {"response.completed", "response.incomplete", "response.failed"}:
                        terminal_event = event_type
                        response_obj = obj.get("response") if isinstance(obj.get("response"), dict) else {}
                        terminal_status = response_obj.get("status")
                        break
            elapsed_ms = round((time.monotonic() - started) * 1000)
            if http_status != 200:
                status = "HTTP_TERMINAL_NON_200"
            elif terminal_event == "response.completed" and terminal_status == "completed":
                status = "PASS"
            elif terminal_event in {"response.incomplete", "response.failed"}:
                status = "TERMINAL_NON_COMPLETED"
            else:
                status = "SUBMITTED_STATUS_UNKNOWN"
            atomic_write(result_path, {
                **intent,
                "submitted_at_utc": submitted_at,
                "finished_at_utc": now(),
                "network_attempted": True,
                "http_status": http_status,
                "first_byte_ms": first_byte_ms,
                "first_event_ms": first_event_ms,
                "elapsed_ms": elapsed_ms,
                "event_count": event_count,
                "last_sequence_number": last_sequence,
                "terminal_event": terminal_event,
                "terminal_status": terminal_status,
                "response_id_sha256": response_id_sha256,
                "usage_present": usage_present,
                "status": status,
            })
            return 0 if status == "PASS" else 3
    except urllib.error.HTTPError as exc:
        atomic_write(result_path, {
            **intent,
            "submitted_at_utc": submitted_at,
            "finished_at_utc": now(),
            "network_attempted": True,
            "http_status": int(exc.code),
            "status": "HTTP_TERMINAL_NON_200",
        })
        return 4
    except BaseException as exc:
        atomic_write(result_path, {
            **intent,
            "submitted_at_utc": submitted_at,
            "finished_at_utc": now(),
            "network_attempted": True,
            "http_status": http_status,
            "first_byte_ms": first_byte_ms,
            "first_event_ms": first_event_ms,
            "event_count": event_count,
            "last_sequence_number": last_sequence,
            "terminal_event": terminal_event,
            "terminal_status": terminal_status,
            "response_id_sha256": response_id_sha256,
            "usage_present": usage_present,
            "status": "SUBMITTED_STATUS_UNKNOWN",
            "error_class": type(exc).__name__,
        })
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
