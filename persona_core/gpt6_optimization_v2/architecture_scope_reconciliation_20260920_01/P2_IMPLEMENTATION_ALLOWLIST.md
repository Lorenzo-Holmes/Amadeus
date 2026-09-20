# P2 Exact Implementation Allowlist

Contract: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`. This file freezes the maximum P2 repair scope; it does not authorize implementation during P1. Next session must recover the adopted contract and actual machine state before beginning P2. No wildcard file permissions are implied.

The smallest sufficient change separates display selection from semantic/state acceptance, versions the new policy explicitly, and keeps every consumer on its appropriate projection. Modify a listed conditional file only when the named coupling actually requires it; otherwise leave it untouched and record why. If an unlisted file is necessary, stop implementation, document the exact boundary and seek a new architecture/scope decision instead of expanding this list silently.

## Runtime files

All paths below are relative to the unique workspace.

| Exact file | Permitted change and reason | Limit |
|---|---|---|
| persona_core/operational_runtime_v1/chat.py | Select new policy's ordinary display candidate independently from finite typed proof; preserve Response Check, host-state claim checks, acknowledged display, event observation and restart order | No provider submission/transport/retry change; no fabricated display or execution receipt |
| persona_core/operational_runtime_v1/accepted_output.py | Add versioned raw/displayed/policy-accepted lineage and explicit consumer projections for new sessions; retain strict typed path and append-only records | No overwrite of raw/legacy accepted; no universal raw fallback; no reinterpretation of old sessions |
| persona_core/operational_runtime_v1/trusted_admission_adapter.py | Make the plan request specific to the selected bounded claim path; ordinary conversation need not produce typed envelopes | Do not broaden catalog, grammar, predicates or ontology; no case IDs or answers; do not trust model certificates |
| persona_core/operational_runtime_v1/semantic_binding.py | Bind new explicit policy, schema and consumer purposes separately while keeping legacy version checks | No weakened identity/source check; do not erase dataset/rubric provenance in formal evaluation |
| persona_core/operational_runtime_v1/operations.py | Necessary constructor adapter: currently unconditionally constructs TRUSTED for formal sessions; dispatch the explicitly declared new policy | Only constructor/policy wiring, not provider configuration or creation of a fresh paid revision |
| persona_core/operational_runtime_v1/transcript_store.py | Conditional direct projection boundary: expose acknowledged displayed lineage to conversation_recent/conversation_turn without changing raw storage | Keep schema/storage behavior outside additive display-record integration unchanged |
| persona_core/operational_runtime_v1/admission.py | Necessary memory-observation adapter: _turn/_issue/observe_turn must bind displayed lineage and its policy hash, not inherit whole-turn semantic truth | Do not change allowed/forbidden effect kinds, EvidenceToken seals, receipt checks, payload approval or host admission rules; keep content_is_event_proof=false |
| persona_core/operational_runtime_v1/capture_export.py | Conditional direct audit consumer: export versioned display record separately from raw and policy acceptance | No historical export overwrite, public-data expansion or hidden-reasoning export |

## Direct validation consumers

| Exact file | Permitted change and reason | Limit |
|---|---|---|
| persona_core/gpt6_optimization_v2/tools/evaluation_runner.py | Version-aware displayed-answer projection and new-policy identity plumbing through existing offline preparation/capture interfaces | No batch allocation or remote execution in P2, no transport/accounting change, no new answers or rubric edits |
| persona_core/gpt6_optimization_v2/tools/semantic_review.py | Validate raw/displayed/accepted lineages and consume frozen routing with A/B subjudgments while preserving 176 original pairs | No automatic semantic PASS, threshold reductions, historical-review rewrites or private-answer generation prompts |
| persona_core/gpt6_optimization_v2/tools/blind_review_v2.py | Conditional downstream adapter for approved displayed-text projection with a separate restricted provenance map | Do not build a real new blind candidate/package in P2; no expansion of reviewer payload beyond the frozen blind contract |
| persona_core/gpt6_optimization_v2/tools/formal_binding_preflight.py | Make offline binding assertions policy-specific and verify new consumer purposes; current assertions hardcode TRUSTED/accepted-only | Zero provider calls; no reinterpretation of old preflight reports or readiness |

## Exact new tests

| New file | Required purpose |
|---|---|
| persona_core/gpt6_optimization_v2/tools/test_bounded_display_state_contract.py | New isolated offline paired cases: useful UNPARSED conversation, rejected unauthorized effects, strict proof support, no certificate/permission conflation |
| persona_core/gpt6_optimization_v2/tools/test_bounded_consumer_binding.py | New isolated offline tests of actual display/history/next-turn/observation consistency, wrong entity, corruption, delivery UNKNOWN, restart/idempotency and explicit legacy rejection/migration |

There are 14 exact source/test paths: 8 runtime, 4 direct validation consumers, 2 new tests. Existing fixtures and regression tests are read/run unchanged. P2 must explain each actual changed path against this table and freeze the resulting source separately.

## Explicitly excluded source changes

Provider/transport/network/adapters/credential handling; Persona/Genesis/source evidence; generic parser/ontology; `semantic_types.py`, `semantic_admission.py`, `semantic_validator.py`, `semantic_renderer.py`, `trusted_semantic_catalog.json`; runtime event reducer, memory schema, retrieval algorithms, persona growth; Avatar/UI/TTS. `response_check.py` remains a finite existing guard and is not expanded into a general parser in P2. `context_projection.py` must continue to receive correctly attributed projected history through the listed interfaces; if changing it becomes necessary, return to change control rather than editing it under this allowlist.

No mutation of existing database/evidence/session policy or historical R12–R15 journal is allowed. New isolated P2/P3 fixture databases and new source manifests are disposable development evidence, not production memory or a formal validation revision. Exact governance/manifest paths for the P2 evidence package must be registered when P2 starts; that registration does not expand this source allowlist.

## P2 acceptance boundary

Ordinary useful analysis survives plan=null after applicable display checks. Unsupported state effects still HOLD/REJECT. A true supported event still admits/commits under existing host rules. Actual display, history and next-turn agree. Displayed facts never self-promote. Legacy/source mismatches remain explicit. No benchmark content or provider behavior changes. Failure to meet these requirements within this list returns to P1 change control; it does not justify a larger parser or a silent OFF switch.
