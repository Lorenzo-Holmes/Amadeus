# G6-07T-PROVIDER2 — architecture audit before implementation

The runtime already separates terminal certainty from output usability for Responses, but provider identity remains implicit in endpoints, model tables and schema versions. A second successful provider cannot establish DeepSeek recovery or satisfy G6-07. This audit uses the current source freeze LONG_STREAM_DIAGNOSTICS_20260919_01 and the saved terminal/Candidate Closure decisions; no historical request is replayed.

| Audited component | A: generic mechanisms | B: DeepSeek coupling | C/D: protocol coupling | E: model/config coupling |
| --- | --- | --- | --- | --- |
| operational_runtime_v1/provider.py | immutable batches; transaction before submission; consumed turn/slot; quarantine; usage bounds; answer usability | endpoints, credential lookup, RATES, response model aliases | request serialization and Responses terminal rejection embedded in journal | scope versions 1–5, max reasoning, finite caps, reviewed CNY rates |
| provider_transport.py | owned worker, drained IPC pipes, frame hashes, deadlines, sanitized lifecycle/errors, wire capture | fixed HTTPS endpoints | StreamAssembly handles Chat finish/DONE; ResponsesAssembly validates native event/identity/terminal/usage | transport policy version and bounds |
| provider_http_worker.py | bounded private input/output, no database, no retries | legacy official_transport entry point | operation allowlist selects catalogue or Responses | strict private frame contract |
| provider_network_route.py | opener-local route selection; no global proxy mutation | fixed api.deepseek.com host | independent of answer protocol | versioned DIRECT_NO_PROXY/SYSTEM_PROXY |
| tools/evaluation_runner.py | source/config seals, journal/capture binding, stop on unknown, frozen denominators | RATES and approved model roles | exact Chat/Responses request reconstruction | semantic suites and scope3/4/5 generation contract |
| tools/responses_formal_readiness.py | isolated journal, single-use preparation, source binding | deepseek-v4-pro, formal pricing | Responses only | formal max/direct policy; must stay a DeepSeek gate |
| tools/candidate_day_v2.py | same-source/settings gates, complete review and legacy regression | endpoint and formal model roles implicit | wire rebinding for Responses | generation_settings does not reject foreign provider metadata on legacy scopes |
| tools/candidate_host_v2.py | actual user ingress, exact candidate binding, finite calls | DeepSeek rates and credential reader | delegates to runtime and candidate gates | pricing and scope checks before submission |
| tools/candidate_longitudinal_v2.py | real dates, continuity, captured source/request evidence | formal scope inherited from candidate | protocol verification delegated to candidate_day | same candidate and generation settings |
| tools/blind_review_v2.py | raw/capture/receipt binding, blank scores, independent return requirements | identity implicit in scope | exact request reconstruction | only conditionally invokes generation_settings at private context entry |

## Existing behavior to preserve

DeepSeek legacy scopes remain byte-compatible. Responses completed/incomplete/failed retain current certainty, output and usage semantics. Reasoning remains distinct from assistant text. Direct routing, deadlines, diagnostic limits, historical UNKNOWN rows, journals, adjudications, quarantines and Candidate Closure are preserved. Historical evidence is protected by physical/logical hashes, not rewritten to pass a new source identity.

## Required boundary changes

Add an explicit registry and versioned scope for new adapters. Separate provider, model, protocol, generation configuration, route and transport contract in identity. Reuse ProviderJournal and the owned-worker lifecycle. Bind normalized receipts to native wire before admitting any new-scope terminal. Apply one common usability/usage check after decoding. Keep the formal evaluation/candidate/blind chain restricted to its existing approved provider contract; generic transport success is not semantic evidence.

The independent adapter in this implementation is a deterministic local fixture. No remote second-provider capability or recovery is asserted.
