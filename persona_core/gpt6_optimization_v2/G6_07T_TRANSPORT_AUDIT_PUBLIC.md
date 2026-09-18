# G6-07T — Transport observability and readiness

2026-09-18. The transport readiness gate passed on real `deepseek-v4-pro` responses. Persona, Claim/Evidence, Relationship, Affect, Memory and Genesis semantics remain frozen. Readiness is transport evidence; it does not close any semantic finding or accept the product.

The previous 600-second `TimeoutExpired` identifies the parent subprocess deadline. Legacy nonstream code supplied the same timeout to the child HTTP client, returned only after a complete body and discarded intermediate network observations when the parent killed the worker. Its precise remote outcome remains unknown. Three historical UNKNOWN requests remain quarantined, with no retry, replay or replacement.

```text
journal intent -> owned parent/child -> next-hop DNS -> TCP
-> proxy tunnel when configured -> TLS -> request write
-> response headers -> stream bytes -> content / reasoning
-> finish_reason + [DONE] -> child exit -> parent receipt -> journal terminal
```

The opt-in lifecycle transport uses fixed telemetry fields and emits no request text, credentials, header values, URLs or exception messages. Streaming preserves messages, model, thinking, reasoning effort and token cap. Raw SSE and reconstructed JSON remain in private journals. Partial streams never become replies; UNKNOWN stops the batch and keeps its reserve. All automatic paid retries remain zero.

Connect, header/read, stream inactivity, worker deadline, parent deadline and missing-process-receipt outcomes are distinguished. The final configuration uses 15-second connect waits, 120-second read inactivity, a 595-second worker budget and a 600-second parent budget. These identify local observations, not remote nonexecution. On the observed proxy route, DNS timing covers the next hop; upstream proxy DNS cannot be separately observed.

Five independent synthetic requests were recorded: four ladder levels and one written, justified final L4 check after correcting SSE framing capacity. L1 reached a known `length` terminal at its tiny cap and remains a rejected usable reply; its transport-only terminal evidence is separately adjudicated. L2, L3, L4 and final L4 completed with `stop`. No new UNKNOWN occurred. The final L4 preserved more than 1.6 MB of SSE data, proving why stream framing must have a separate bound from normalized response text. The limits are 16 MB wire, 1 MB reconstructed body and 24 MB private worker IPC.

Final checks: 34 transport/diagnostic tests, 19 evaluation binding tests, 32 candidate configuration tests and 26 blind-package binding tests passed. The unchanged legacy suite retains its full 450-test denominator: 449 compatible passes and one historical source-identity error. That error remains an error; old semantic evidence is not inherited. All 310 protected members were unchanged. A coherent SQLite backup was verified; a main-database hash alone is not sufficient when WAL updates exist.

Fresh G6-07 validation was started under a new source-bound revision. It still requires all 44 turns and 176 explicit judgments, followed by the frozen heldout and original82 gates before a new candidate or independent review package. Product acceptance and production activation remain false. New candidate natural days remain 0/3.

Official interface references: [streaming and terminal usage](https://api-docs.deepseek.com/api/create-chat-completion/), [current models and pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/), [connection keepalives](https://api-docs.deepseek.com/quick_start/rate_limit/).
