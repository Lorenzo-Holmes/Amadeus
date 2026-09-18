# G6-07T — Transport observability and readiness

2026-09-18. The synthetic transport ladder passed on real `deepseek-v4-pro` responses. The subsequent external validation stopped on a new UNKNOWN, so current readiness is blocked pending new evidence. The earlier ladder PASS remains an accurate historical result. Persona, Claim/Evidence, Relationship, Affect, Memory and Genesis semantics remain frozen. Readiness is transport evidence; it does not close any semantic finding or accept the product.

The previous 600-second `TimeoutExpired` identifies the parent subprocess deadline. Legacy nonstream code supplied the same timeout to the child HTTP client, returned only after a complete body and discarded intermediate network observations when the parent killed the worker. Its precise remote outcome remains unknown. Three historical UNKNOWN requests remain quarantined, with no retry, replay or replacement.

```text
journal intent -> owned parent/child -> next-hop DNS -> TCP
-> proxy tunnel when configured -> TLS -> request write
-> response headers -> stream bytes -> content / reasoning
-> finish_reason + [DONE] -> child exit -> parent receipt -> journal terminal
```

The opt-in lifecycle transport uses fixed telemetry fields and emits no request text, credentials, header values, URLs or exception messages. Streaming preserves messages, model, thinking, reasoning effort and token cap. Raw SSE and reconstructed JSON remain in private journals. Partial streams never become replies; UNKNOWN stops the batch and keeps its reserve. All automatic paid retries remain zero.

Connect, header/read, stream inactivity, worker deadline, parent deadline and missing-process-receipt outcomes are distinguished. The final configuration uses 15-second connect waits, 120-second read inactivity, a 595-second worker budget and a 600-second parent budget. These identify local observations, not remote nonexecution. On the observed proxy route, DNS timing covers the next hop; upstream proxy DNS cannot be separately observed.

Five independent synthetic requests were recorded: four ladder levels and one written, justified final L4 check after correcting SSE framing capacity. L1 reached a known `length` terminal at its tiny cap and remains rejected as a usable reply; its transport-only terminal evidence is separately adjudicated. L2, L3, L4 and final L4 completed with `stop`. No new UNKNOWN occurred within that ladder. The final L4 preserved more than 1.6 MB of SSE data, proving why stream framing must have a separate bound from normalized response text. The limits are 16 MB wire, 1 MB reconstructed body and 24 MB private worker IPC.

Final checks: 34 transport/diagnostic tests, 19 evaluation binding tests, 32 candidate configuration tests and 26 blind-package binding tests passed. The unchanged legacy suite retains its full 450-test denominator: 449 compatible passes and one historical source-identity error. That error remains an error; old semantic evidence is not inherited. All 310 protected members were unchanged. A coherent SQLite backup was verified; a main-database hash alone is not sufficient when WAL updates exist.

Fresh G6-07 validation submitted 30 of its 44 turns. It captured 29 complete replies and stopped immediately on one UNKNOWN; the remaining 14 turns were not submitted. All available replies received explicit internal review, covering 116 of the original 176 criteria. The incomplete revision has no whole-suite acceptance, and no later gate was started. Private scores, findings, dialogue, wire captures and call identifiers remain excluded from this public report.

The interrupted call reached HTTP 200, first bytes and a first token before a response-stream error at about 47 seconds. It preserved 301,689 bytes of partial SSE without a finish reason, terminal usage or DONE marker. Captured SSE records parse offline; no capture-cap or recorded timeout fired. The worker exited and the parent received its UNKNOWN envelope. The precise network, proxy or service-side cause remains unknown because the running version retained only a safe aggregate protocol/connection category. The partial stream was never displayed as a reply or reused to continue generation.

All 29 completed streams reconstruct exactly to their saved responses. The original three quarantined journals remain unchanged, and the new request raises the unresolved total to four. Automatic paid retries remain zero. The new revision is permanently quarantined; renewed execution requires new evidence resolving the transport blocker and a justified, separately bound revision. User authorization for subsequent evidence-driven Core repair is preserved, with no Core change made during this stopped run. Product acceptance and production activation remain false. New candidate natural days remain 0/3.

Official interface references: [streaming and terminal usage](https://api-docs.deepseek.com/api/create-chat-completion/), [current models and pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/), [connection keepalives](https://api-docs.deepseek.com/quick_start/rate_limit/).
