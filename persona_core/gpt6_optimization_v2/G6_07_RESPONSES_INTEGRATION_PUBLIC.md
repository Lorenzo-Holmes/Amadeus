# Responses transport integration — frozen for validation

The official DeepSeek Responses protocol is integrated through a separately versioned `apcore-provider-scope-4`. The primary model remains `deepseek-v4-pro` with max reasoning. Existing Persona, Claim/Evidence, Reasoning Scope, source/Genesis, evaluation inputs, rubric and thresholds remain unchanged. Older provider scopes retain their original protocol semantics.

The runtime commits submission intent before network I/O, never retries a submitted logical turn, and keeps partial streams non-displayable. Successful normalization requires matching completed event/status, stable identities, increasing event sequence, no later event, identical streamed/final text, and valid usage accounting. Raw SSE and normalized receipts remain separately hash-bound. Evaluation, candidate, blind review and longitudinal consumers validate the new request shape and wire bindings.

Freeze: `RESPONSES_TRANSPORT_20260919_01`. Final current components: 23 modules / 356 tests passed. Complete legacy denominator: 43 modules / 450 tests; 449 compatible passes, one preserved historical source-identity error, zero unexpected functional failures. The raw legacy report remains failed; old repair hashes and evidence were not edited. A real subprocess IPC fixture also verifies Responses dispatch without network traffic.

The four historical unknown submissions remain quarantined. Offline integration is not semantic acceptance and does not establish recovery of the old Chat Completions path. Exactly one freeze-bound synthetic formal readiness is required before fresh evaluation. Product acceptance and production activation remain false.

Official interface: https://api-docs.deepseek.com/api/create-response/
Official price evidence: https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
