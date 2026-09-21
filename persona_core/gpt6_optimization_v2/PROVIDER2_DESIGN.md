# G6-07T-PROVIDER2 — sealed design before source changes

## Scope and identity

Introduce apcore-provider-scope-6 for independent synthetic validation. Fields include provider_id, api_protocol, endpoint, generation_config, network_route_policy, transport_contract_version, source_binding, spend_policy and bounded slots with explicit model identities. The generation identity hashes these fields and the actual semantic messages; identical text from different providers/models/protocols/routes/configurations/source cannot share an identity. Full batch scope remains immutable and separately hashed. Legacy scopes 1–5 keep their serialized requests and existing formal behavior. Foreign provider/identity metadata added to a legacy scope is rejected rather than silently ignored.

## Adapter contract

A registry selects an adapter by exact provider_id. An adapter supplies immutable capabilities, model/endpoint/route validation, request serialization, native stream decoder, normalized terminal interpretation, credential resolution and one-shot transport. Capabilities describe permitted requests; they never certify a returned response. Both worker and parent check native wire. DeepSeek delegates to existing parsers, transport, route checker and reviewed rates. A local fixture adapter uses its own strict, sequenced event protocol with explicit completed/failed/incomplete terminals and independent usage field names. No provider-name branches are added to consumers.

## Lifecycle, certainty and usability

All adapters use ProviderJournal's committed submission, unique slot/turn, hard worker deadline, sanitized telemetry, stopped-batch and no-retry mechanisms. The fixture crosses a real child-process IPC boundary but performs no socket operation. Its deterministic short/long/error cases are synthetic inputs, never Persona benchmark material.

For scope6, validate native identity/sequence/framing and rederive the exact normalized body in the parent. Missing or untrustworthy terminal means SUBMITTED_STATUS_UNKNOWN. A validated failed/incomplete terminal, invalid usage, no visible text, tool output or truncation means RESPONSE_REJECTED_TERMINAL_KNOWN. A completed, correctly bound and usable answer means RESPONSE_CAPTURED; semantic_verdict is always unset. Common usage/output validators serve both new adapters and the legacy journal without changing historical DeepSeek decisions. Reasoning is never promoted into content.

## Accounting

Record known or unknown usage independently of answer usability. Reviewed rates may yield a conservative estimate; missing rates yield null/unestimated, never invented zero spending. New-scope accounting records a nullable money reserve plus bounded input/output token reserve. Because the existing provider_calls reserve column is non-null, its scope6 compatibility placeholder is explicitly superseded by an additive provider_call_contracts row and public journal accessors; legacy rows are not migrated. billing_certified remains false. Unpriced scopes are allowed only for the non-network fixture; paid adapters require reviewed finite spend policy before submission.

## Formal gates

The independent scope6 path is synthetic-only. It cannot enter external44, heldout, original82, formal readiness, Candidate or Blind gates. Add a shared legacy/formal identity guard at gate entry points, including rejection of provider metadata smuggled into a legacy scope. Existing source/model/settings comparisons remain required. Future paid-provider expansion needs an explicit approved adapter and priced bounded scope; this task introduces no arbitrary-URL HTTP escape hatch.

## Validation and publication

Add registry, selection, capabilities, identity, native terminal, rejection, disconnect, malformed usage, reasoning separation, no-retry, journal isolation, worker IPC, DeepSeek request-byte compatibility and gate mismatch tests. Run every current component module (baseline 27/443), then the unchanged 43-module/450-test legacy runner, preserving its single historical source-identity sentinel. Hash-check source and historical evidence, then create PROVIDER_AGNOSTIC_RUNTIME_20260919_01 with a linked predecessor and private source archive. Remote synthetic validation is skipped when no second credential exists. Re-read state files and reconcile concurrent edits before final updates. Publish only reviewed source/tests and public-safe design/freeze summary on the existing branch; no private evidence, raw wire, SQLite, billing, heldout or credentials.

DeepSeek blocker remains open. Provider2 validation does not satisfy G6-07.

## Verified implementation

The completed freeze is PROVIDER_AGNOSTIC_RUNTIME_20260919_01. All 28 component modules and 499 tests pass; 56 tests are new and the prior 443 remain. The fixed 43-module legacy suite retains 449 compatible passes plus one expected historical source-identity sentinel, with zero unexpected functional failures. A 12-case authored differential comparison matches the previous DeepSeek implementation; ten native parser/HTTP/diagnostics sections remain unchanged. Freeze-bound short and long local fixtures both pass. No remote generation or readiness was run.
