# G6-07T-PROVIDER2-REMOTE — design before implementation

This task validates a configured second remote provider using the frozen generic journal and transport contract. It does not satisfy DeepSeek G6-07, establish DeepSeek recovery, or accept Persona semantics. The prior source freeze and its historical evidence remain immutable.

## Selected contract

Use provider `openrouter`, model `openai/gpt-4.1-mini`, and the official HTTPS Chat Completions endpoint `https://openrouter.ai/api/v1/chat/completions`. Pin the upstream to `openai` using both `order` and `only`, with `allow_fallbacks=false` and `require_parameters=true`. Send one model, no model fallback array, no tools, no plugins, and no automatic retries. The configured credential is resolved only from `OPENROUTER_API_KEY` in the process or Windows user environment; values never enter command arguments, evidence, or logs. Existing Anthropic-compatible settings that point to DeepSeek do not qualify as a second provider.

The native request contains model, messages, stream=true, max_tokens, stream_options.include_usage=true, temperature=0, and the fixed provider routing object. Reasoning is unsupported by this minimal model contract and is explicitly disabled in the generation scope. Long output, rather than private reasoning, exercises the sustained stream.

## Native stream and terminal semantics

Parse SSE incrementally across arbitrary byte boundaries, ignoring comments and accepting the documented repeated finish reason in the final usage chunk. Require stable response identity and model within a stream, a single choice at index zero, no visible text after a finish, and a complete record boundary. Ordinary completion requires finish_reason plus `[DONE]`. A documented structured streaming error with finish_reason=error is a known failed terminal even if no `[DONE]` follows. A complete non-2xx JSON error with a valid error object is a known HTTP failure; HTML, malformed framing, contradictory identities, or disconnect without a trustworthy terminal remain UNKNOWN.

Normalize stop to completed, length/content_filter/tool output to incomplete, and explicit errors to failed. Retain usage independently from reply usability. Missing or malformed usage, empty output, reasoning-only output, tool output, truncation, or wrong returned model rejects a known terminal as RESPONSE_REJECTED_TERMINAL_KNOWN. Reasoning fields never become visible assistant text. Error messages are never copied into public diagnostics; only fixed categories and numeric HTTP codes are used.

## Usage and spending

Normalize prompt_tokens, completion_tokens, total_tokens, cached prompt tokens, and optional reasoning-token details into the existing shared accounting contract. Do not coerce negative, fractional, Boolean, inconsistent, or absent token counts into valid usage. Preserve native fields in private wire evidence. The project has no previously reviewed OpenRouter price configuration, so rates, money reserve, and estimated money remain null; billing_certified=false and estimate_complete=false. A separate user-authorized UNESTIMATED_SYNTHETIC policy permits at most two slots, 4096 input bytes per request, and 8192 output tokens per request. This bounded exception applies only to the new adapter; DeepSeek's reviewed-price requirement is unchanged.

## Transport and identity

Reuse the owned worker, private stdin credential channel, bounded and concurrently drained IPC, lifecycle diagnostics, verified TLS, and parent receipt binding. Extend worker dispatch through registered adapter methods rather than adding provider cases to journal consumers. The OpenRouter adapter owns its fixed HTTPS endpoint and local opener; redirects are refused. The scope explicitly chooses SYSTEM_PROXY or DIRECT_NO_PROXY, without modifying system settings or DeepSeek routing. Both parent and worker validate the fixed route and native request.

The scope binds provider_id, model_id, api_protocol, endpoint, streaming mode, terminal capabilities, usage capability, disabled reasoning, native generation options including upstream routing, transport policy, network route, and runtime source hash. Existing generation_identity includes these bound values. Identical input from DeepSeek and OpenRouter cannot share an identity. Parent decoding of raw wire must exactly reproduce the worker's normalized receipt before the journal admits terminal certainty.

## Execution and quarantine

A dedicated fixed destination is exclusively created before any submission; it cannot be renamed or reopened to create another validation. One isolated runtime and one immutable batch contain exactly SHORT_SYNTHETIC and LONG_SYNTHETIC. The short prompt requests one neutral sentence; the long prompt requests numbered neutral records unrelated to this project. The long slot runs only after the short slot passes. The driver never imports Persona prompts or benchmark materials.

An UNKNOWN immediately stops the entire validation, leaves the long slot unsubmitted if applicable, and permanently consumes the validation intent. No retry, resume, resend, replacement, metadata probe, or third generation is permitted. A terminal-known rejection also stops this bounded validation without reclassifying it as UNKNOWN. A long PASS additionally requires substantial visible output and many content-bearing stream events. This assesses transport, not answer quality.

## Verification and publication

Before remote execution, test serialization, identity/source/route binding, event parsing, terminal and usage normalization, terminal-known rejections, disconnect UNKNOWN, malformed usage, reasoning separation, credential redaction, journal isolation, and one-shot behavior. Preserve all 499 existing component tests and add adapter tests; run the full component suite and unchanged 43-module/450-test legacy regression before freezing and using new source. Preserve the single expected historical identity sentinel and zero unexpected functional failures.

Create PROVIDER2_REMOTE_RUNTIME_20260919_01 only after source-bound offline checks. Reconcile current machine files by rereading and merging concurrent updates. Publish only allowlisted adapter/dispatch/test/driver/design and public freeze files; no keys, private evidence, raw wire, SQLite, billing ledger, heldout, dialogue, or UNKNOWN evidence. A successful remote result is only REMOTE_PROVIDER2_VALIDATION_PASS.

## Protocol references

- [Official streaming and terminal error schema](https://openrouter.ai/docs/api_reference/streaming)
- [Official provider routing and fallback controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Official selected model and endpoint](https://openrouter.ai/openai/gpt-4.1-mini)

References were checked on 2026-09-19. Advertised pricing is not a project-certified estimate or billing evidence.
