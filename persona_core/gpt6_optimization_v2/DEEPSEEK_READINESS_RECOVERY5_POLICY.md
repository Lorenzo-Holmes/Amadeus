# DeepSeek official bounded readiness recovery policy

Classification: `USER_AUTHORIZED_BOUNDED_READINESS_POLICY_CHANGE`.

User authorization recorded at 2026-09-19T15:01:58.513976+00:00. The exact message-send timestamp is unavailable. This decision takes effect upon recording.

The prior gate required new independent official recovery evidence or a proven local interruption fix before another readiness request. That gate remains an immutable historical fact. The user now explicitly authorizes one bounded campaign of at most five fresh official readiness requests, without claiming recovery in advance.

Every attempt has a new call ID, local request identity, journal, intent and submission timestamp. The canonical payload hash deliberately remains identical across attempts because the input and generation configuration are fixed. Later attempts do not resume, replay, resend, retry or replace any earlier journal request. An UNKNOWN remains permanently quarantined even if a later fresh attempt passes. No SDK or worker may automatically retry a paid request.

FRESH_READINESS_ATTEMPT_BUDGET=5; PRE_SUBMISSION_RECONNECT_BUDGET=5 across the whole campaign; POST_SUBMISSION_RESEND_BUDGET=0; AUTOMATIC_PAID_RETRY=0. DNS/TCP/TLS reconnection is optional and requires positive proof that no request body was written; absence of telemetry alone is insufficient. This campaign uses the frozen one-shot worker; it does not enable any new reconnect loop. A pre-write failure is reviewed locally before any action. Ambiguity is quarantined and never used as permission to resend.

Only DeepSeek Official https://api.deepseek.com/responses, deepseek-v4-pro, Responses, reasoning=max, DIRECT_NO_PROXY and stream=true are permitted. There is no cross-host redirect or provider fallback. Historical secondary-provider evidence has no acceptance role.

All attempts retain the exact historical synthetic readiness system/user messages: 600 numbered neutral sentences, 12–20 English words each, without tools or real user/project content. The developer-message list remains empty as in the frozen harness. Max output remains 32768 including reasoning; parent deadline 600s, worker 595s, read inactivity 120s, connect 15s. Persona, heldout, external44, original82, Candidate and Blind content are excluded. No hidden reasoning is requested or published. Only event metadata/accounting is inspected.

PASS requires HTTP success, valid SSE, trusted response.completed, usable visible output, valid usage, worker terminal, parent receipt, complete journal, intact identities and no protocol corruption or reasoning promotion. The long-stress floor is at least 100 reasoning delta events, 1000 total SSE events and 30 seconds. These thresholds are frozen before any remote request; completed responses below the stress floor are terminal-known rejected. Incomplete/failed or completed-but-unusable responses are also terminal-known rejected. Submitted requests without trusted terminal are UNKNOWN.

Stop immediately at the first full PASS or after five submitted attempts without PASS. Success means bounded campaign success, not first-attempt success unless attempt 1 actually passed. Preserve all earlier outcomes. Perform adjudication, reconciliation, regression checks and validation/policy freeze before marking G6-07 AUTHORIZED_TO_START. This session stops safely; a new complete 44/176 revision must be created separately. G6-08, G6-09, Candidate V2 and Blind stay locked. No Persona-quality acceptance is implied.

The original runtime source freeze is retained, not replaced by a fictitious runtime freeze. The independent campaign freezes policy, harness and evidence. Current pricing refresh was unavailable; legacy rate constants may enforce the existing finite local guards but are not certified current tariffs. Campaign money is UNESTIMATED, billing_certified=false, estimate_complete=false; token usage is retained when available. Per-attempt legacy guard 1.15 CNY, aggregate policy guard 5.75 CNY, neither represented as a certified billing cap.
