"""Minimal DeepSeek ChatCompletions adapter for the R006 evaluation harness.

Security / cost properties:
- Reads DEEPSEEK_API_KEY from the process environment, or on Windows from the
  current user's Environment registry value when the current process has not
  inherited it yet. Only this named variable is read; its value is never logged.
- Never prints the key.
- No automatic retries.
- Defaults to thinking disabled for a small evaluation smoke test.
- Refuses remote calls unless DEEPSEEK_MAX_BUDGET_CNY is explicitly set > 0.
- Uses a conservative upper-bound budget check based on UTF-8 bytes and peak
  DeepSeek-V4-Flash prices current at 2026-09-06. Update the price constants
  before future paid runs if official pricing changes.

Adapter contract: one JSON object on stdin, one JSON object on stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


BASE_URL = "https://api.deepseek.com/chat/completions"
ALLOWED_MODELS = {"deepseek-v4-flash", "deepseek-v4-pro"}

# Official peak CNY pricing per 1M tokens at 2026-09-06.
PEAK_INPUT_CNY_PER_M = {
    "deepseek-v4-flash": 3.0,
    "deepseek-v4-pro": 9.0,
}
PEAK_OUTPUT_CNY_PER_M = {
    "deepseek-v4-flash": 9.0,
    "deepseek-v4-pro": 27.0,
}


class AdapterError(RuntimeError):
    pass


def fail(message: str, code: int = 2) -> int:
    print(json.dumps({"status": "FAIL", "error": message}, ensure_ascii=True), file=sys.stderr)
    return code


def load_stdin() -> dict[str, Any]:
    try:
        raw = sys.stdin.buffer.read()
        value = json.loads(raw.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise AdapterError(f"invalid stdin JSON: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise AdapterError("stdin JSON must be an object")
    return value


def windows_user_env_value(name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except (ImportError, FileNotFoundError, OSError):
        return None
    return value if isinstance(value, str) and value else None


def credential_value() -> tuple[str | None, str]:
    value = os.environ.get("DEEPSEEK_API_KEY")
    if value:
        return value, "process_environment"
    value = windows_user_env_value("DEEPSEEK_API_KEY")
    if value:
        return value, "windows_user_environment"
    return None, "missing"


def positive_budget(override: float | None = None) -> float:
    if override is not None:
        value = override
    else:
        raw = os.environ.get("DEEPSEEK_MAX_BUDGET_CNY", "")
        if not raw:
            raw = windows_user_env_value("DEEPSEEK_MAX_BUDGET_CNY") or ""
        if not raw:
            raise AdapterError("DEEPSEEK_MAX_BUDGET_CNY is not set; paid calls are disabled")
        try:
            value = float(raw)
        except ValueError as exc:
            raise AdapterError("DEEPSEEK_MAX_BUDGET_CNY must be numeric") from exc
    if not (0.0 < value <= 10.0):
        raise AdapterError("DEEPSEEK_MAX_BUDGET_CNY must be > 0 and <= 10 CNY for this adapter")
    return value


def validate_request(value: dict[str, Any]) -> tuple[str, str, list[dict[str, str]], int]:
    request_id = value.get("request_id")
    model_id = value.get("model_id")
    messages = value.get("messages")
    max_output_tokens = value.get("max_output_tokens")
    if not isinstance(request_id, str) or not request_id:
        raise AdapterError("request_id is required")
    if model_id not in ALLOWED_MODELS:
        raise AdapterError("unsupported DeepSeek model")
    if not isinstance(messages, list) or not messages:
        raise AdapterError("messages must be a nonempty list")
    cleaned: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict) or set(item) != {"role", "content"}:
            raise AdapterError("each message must contain only role and content")
        role, content = item.get("role"), item.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise AdapterError("invalid message role/content")
        cleaned.append({"role": role, "content": content})
    if type(max_output_tokens) is not int or not (1 <= max_output_tokens <= 600):
        raise AdapterError("max_output_tokens must be an integer from 1 to 600")
    return request_id, model_id, cleaned, max_output_tokens


def conservative_cost_bound_cny(model: str, messages: list[dict[str, str]], max_output_tokens: int) -> float:
    # A UTF-8 byte count is deliberately used as a conservative upper bound on
    # input token count for this small harness. Output is bounded by max_tokens.
    input_bytes = len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return (input_bytes / 1_000_000.0) * PEAK_INPUT_CNY_PER_M[model] + \
        (max_output_tokens / 1_000_000.0) * PEAK_OUTPUT_CNY_PER_M[model]


def invoke(request: dict[str, Any], budget_override: float | None = None) -> dict[str, Any]:
    request_id, model, messages, max_output_tokens = validate_request(request)
    api_key, _ = credential_value()
    if not api_key:
        raise AdapterError("DEEPSEEK_API_KEY is not set")
    budget = positive_budget(budget_override)
    bound = conservative_cost_bound_cny(model, messages, max_output_tokens)
    if bound > budget:
        raise AdapterError(f"conservative call-cost bound {bound:.6f} CNY exceeds configured budget")

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_output_tokens,
        "stream": False,
        "thinking": {"type": "disabled"},
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    http_request = urllib.request.Request(
        BASE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Amadeus-Persona-Core-R006/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=55) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise AdapterError("DeepSeek response exceeds 1MB")
    except urllib.error.HTTPError as exc:
        # Do not echo the response body; it may contain provider diagnostics.
        raise AdapterError(f"DeepSeek HTTP error {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise AdapterError("DeepSeek network error") from exc

    try:
        parsed = json.loads(raw)
        text = parsed["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise AdapterError("unexpected DeepSeek response schema") from exc
    if not isinstance(text, str) or not text.strip():
        raise AdapterError("DeepSeek returned an empty completion")

    usage = parsed.get("usage") if isinstance(parsed, dict) else None
    safe_usage = None
    if isinstance(usage, dict):
        safe_usage = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
    return {
        "request_id": request_id,
        "model_id": model,
        "response_text": text,
        "provider_usage": safe_usage,
    }


def check_environment() -> int:
    _, key_source = credential_value()
    budget_process = bool(os.environ.get("DEEPSEEK_MAX_BUDGET_CNY"))
    budget_user = bool(windows_user_env_value("DEEPSEEK_MAX_BUDGET_CNY")) if not budget_process else False
    result = {
        "adapter": "deepseek_chat_completions",
        "base_url": "https://api.deepseek.com",
        "models": sorted(ALLOWED_MODELS),
        "api_key_present": key_source != "missing",
        "api_key_source": key_source,
        "budget_present": budget_process or budget_user,
        "budget_source": "process_environment" if budget_process else "windows_user_environment" if budget_user else "missing",
        "network_called": False,
        "thinking": "disabled",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--budget-cny", type=float, default=None,
                        help="Explicit per-call local budget cap in CNY; does not persist to the environment")
    args = parser.parse_args()
    if args.check:
        return check_environment()
    try:
        print(json.dumps(invoke(load_stdin(), args.budget_cny), ensure_ascii=True))
        return 0
    except AdapterError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
