# ADR-P1-20260920 — Adopt Bounded Architecture Contract

Task: `G6-07-ARCHITECTURE-RECONCILIATION-P1`  
Contract: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`  
Classification: `ARCHITECTURE / REPAIR GOVERNANCE`  
Adoption is effective only with this directory's completed `FINAL_AUDIT.json` and the append-only Canonical Guide adoption record. This is a contract freeze, not an implementation or product acceptance certificate.

## Scope Alignment Check — PASS

The Canonical Guide was read first. Its original mission and the Master Goal both require a continuing, source-grounded identity, governed experience, useful conversation, and reliable state. There is no core-mission conflict. The original Operations architecture already separates conversation, event candidates and committed state. The two responsibility layers preserve those three record categories.

This decision governs transitions from generated text to displayed conversation, from displayed conversation to attributed context, and from a proposed effect to host admission and durable commit. Conversation behavior and state admission are specified here, but their implementation is unchanged in P1. The external44 denominator stays 44 turns / 176 criteria; an applicability route and explicit state evidence requirements are added, not replacement answers or easier thresholds.

P1 may write contracts, governance matrices, append-only adoption decisions and current machine progress. P1 may read runtime code and frozen evidence. P1 may publish the expressly allowlisted public governance files. Provider requests, readiness, generation, runtime edits, new revisions, Persona/Genesis changes and historical evidence mutations are prohibited. No P2 implementation is authorized in this session.

## Decision

The Conversation Layer owns current-turn reasoning, references, contextual continuity, conditional analysis, suggestions, clarification, persona expression and the actual user-visible answer. It must respect sources, privacy, entities, truthful capability and execution statements. Ordinary lawful language does not require durable-state-level formal proof before display.

The Trusted State Layer owns event candidates, evidence, host admission, RuntimeCommit, governed memory, user-fact projections, Persona/Relationship effects, responsibility, execution, permissions and external-action effects. It remains fail-closed. Models can propose; they cannot issue evidence, permissions, admission decisions or commits.

`DISPLAY_ELIGIBLE != FACT_TRUE != STATE_ADMITTED != STATE_COMMITTED`.

The existing finite typed semantic proof path remains available for a selected bounded high-authority claim. It is not the universal output protocol for conversation. `TrustedAdmission` verifies a bounded typed inventory; `AdmissionController` admits event effects. They remain separate services with separate evidence responsibilities.

## Why reconciliation, not a broader parser

The R15 final audit records one submitted and captured turn, one accepted output, four reviewed criteria (3 PASS, 1 FAIL), and 172 UNREVIEWED. The revision remains permanently quarantined. Its observed chain was UNPARSED → null plan → BLOCK → generic fallback, with task completion failure and over-conservatism observed. A raw semantic violation was not independently established. This does not prove every ordinary session is blocked or every unsubmitted turn would fail.

The old finite catalog was being required to authorize all displayed task content. Expanding that catalog to cover benchmark language would move the product toward a general language prover and invite answer leakage. This decision changes the application boundary instead. It preserves Candidate Closure, Responsibility Grounding, domain/scope/attribution discipline, planned/completed separation and UNKNOWN discipline. R12–R14 failures are not rescinded. R15's original finding and verdict are not reclassified in their historical files.

## Frozen invariants

1. Actual display and dialogue history agree. A hidden raw draft is not shared conversational history.
2. Repetition, summaries, retrieval, model switches and restarts cannot promote a report or inference into a world fact.
3. An admitted utterance observation proves that the utterance occurred, not that its described event occurred.
4. Semantic support is neither host permission nor a durable commit. A hash binds bytes, not truth.
5. Source/Genesis identity, entity isolation, permissions, real execution receipts and immutable evidence retain their existing protection.
6. Plain UNPARSED is a coverage result. Known boundary violations and binding corruption remain distinct failures.
7. Gate A and Gate B must both pass on the same new source/policy identity. P1 completion satisfies neither behavioral gate.
8. No benchmark ID, answer, ownership mapping or expected chronology may select a production semantic rule.

## Existing implementation recovered

`accepted_output.py` currently supports OFF/TRUSTED, keeps raw and accepted immutable, and routes nine named consumer purposes. Its formal null-plan path produces the fallback. `chat.py` requires formal TRUSTED identity and installs a semantic-plan request. `semantic_binding.py` binds source, policy, provider configuration, dataset/rubric and consumers. `operations.py` constructs that path.

`admission.py` binds real displayed utterances to host evidence and sets `described_events_proven=false` and `content_is_event_proof=false`. `RuntimeStore.commit` validates the decision and atomically writes event, state and index with idempotency. These correct boundaries are retained. Response Check is explicitly a finite guard, not a complete semantic evaluator.

The governance Authority Ladder uses existing types/records; it does not require a new enum. In particular, Attribution is presently a validated string axis, EventCandidate is represented by `event_candidates`, and RuntimeCommit by `RuntimeStore.commit` plus persisted event/state records, not classes that this document pretends already exist.

## Decision set and next boundary

The other documents in this directory normatively define display/state contracts, authority, 14 mechanisms, 14 consumers, UNPARSED decisions, dual gates, all 176 criterion routes, the exact P2 file allowlist and migration/rollback. `CONTRACT_DECISION_CASES.json` freezes finite offline acceptance cases; none has been executed against new runtime code in P1.

P2 must use a new explicit bounded policy identity on new isolated sessions, preserve old OFF/TRUSTED interpretations, and implement only the listed paths. If any listed boundary needs a generic ontology, transport change, Persona/Genesis write, answer-specific routing or a broader file scope, stop and reopen reconciliation. This session stops after P1 governance adoption and publication.

## Local sources

Canonical Guide §§0–7, 9–20, 25–28, 32, 35–36; `AMADEUS_PERSONA_CORE_MASTER_GOAL.md`; `PERSONA_CORE_CONTINUATION_PROTOCOL.md`; `PERSONA_CORE_DECISION_LOG.md`; original `USER_OBJECTIVE.md`; Operations `TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md` §§4–7; the four G6 machine files; R15 `FINAL_AUDIT.json`; R6/R7 design and frozen source manifest; the actual runtime modules named above. All paths are relative to the authorized workspace. Private answers are not normative inputs to this decision.
