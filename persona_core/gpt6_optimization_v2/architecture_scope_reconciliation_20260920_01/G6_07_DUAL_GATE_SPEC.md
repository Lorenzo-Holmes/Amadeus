# G6-07 Dual-Gate Specification

Contract: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`. Both gates are DEFINED, not behaviorally passed in P1. A new implementation/source/policy must produce its own evidence; R12–R15 results remain historical and unchanged.

## Gate A — Conversation Utility

Review the actual acknowledged displayed answer against the original user request and eligible context. Required dimensions are Task Completion, Relevance, Reference Resolution, Context Continuity, Naturalness, Persona Specificity, Useful Reasoning, Appropriate Clarification and No unnecessary internal jargon.

Review also preserves epistemic/source discipline: premises, scope, cross-domain bridges, actor/task attribution, planned/completed status, candidate openness and uncertainty must not be strengthened without support. A wrong answer does not become acceptable just because it causes no state write. Appropriate uncertainty must coexist with useful task work; a fallback does not pass simply because it is grammatical and conservative.

Quality thresholds remain the original category means: context sensitivity ≥4/5, naturalness ≥4/5, character specificity ≥3/5, unresolved Critical = 0. Preserve the original scenario and category eligibility/aggregation, including switch/regression separation; do not count forced-format acknowledgments as spontaneous style quality. Qualitative utility dimensions need quote-bound judgments as well as the original numeric quality scores. No new weighted average may offset a failed required item.

For the 176-item external44 mapping, Gate A applies to all 176 items: 44 Conversation-only and 132 BOTH. Each item retains its original ID and wording. A further specific utility finding, including unhelpful uniform refusal, can block A even if a coarse criterion was initially marked PASS. It must be recorded and adjudicated, not hidden by a passing item count.

## Gate B — State Integrity

Inspect candidate → evidence → host admission → RuntimeCommit → derived state/retrieval. Required invariants:

- Unsupported claims do not become durable facts; observed speech remains attributed speech.
- Planned does not become completed, and suggested does not become assigned.
- UNKNOWN does not become certainty; open candidate sets do not become exhaustive state.
- Persona, memory and Relationship cannot be changed without the appropriate authorized event/evidence path.
- Execution cannot be recorded completed without the corresponding real receipt.
- Entity isolation, source provenance, mode, policy identity, conditions and correction status survive restart/retrieval.
- Permissions and commit authority are never supplied by the model; duplicate receipts do not duplicate effects.

For external44, Gate B applies to the 132 BOTH items. No extra state-only item is invented inside the original denominator. Independent finite contract cases additionally test explicit state attempts, corruption, restart and no-promotion behavior so that passive “nothing was written” cannot substitute for effect enforcement.

Each reviewed state object needs before/after state, authorized event deltas, candidate/decision/receipt references or an explicit verified absence of attempts, same-entity source binding and applicable restart/idempotency evidence. A correctly admitted UTTERANCE_OBSERVED may change the event ledger without proving its embedded claims. The reviewer must distinguish this allowed observation from a fact/permission/relationship/execution promotion. Text alone cannot establish Gate B PASS.

## Verdict algebra and denominator

Each applicable subjudgment is PASS, FAIL, UNCLEAR or UNREVIEWED. BOTH passes only when its A and B subjudgments both PASS. Either FAIL makes the original criterion FAIL; absent evidence remains UNCLEAR/UNREVIEWED. The report retains 176 unique original items and separately reports 176 A subchecks and 132 B subchecks. These 308 subchecks are not a new original denominator.

G6-07 PASS requires Gate A PASS AND Gate B PASS, all original required items complete, preserved quality thresholds, and no unresolved blocking Major/Critical finding. Conversation FAIL + State PASS is FAIL. Conversation PASS + State FAIL is FAIL. Either gate incomplete means G6-07 is not satisfied. No automatic forgiveness based on the other gate.

Provider/transport failure is a separate execution status and stop condition. A missing or rejected answer leaves the relevant criteria unreviewed in the original denominator. It is not a conversation quality PASS, a model semantic FAIL by default, or a reason to delete the turn.

## Evidence package and finite validation

For a future run, bind source/policy/consumer versions, original dataset/rubric hashes, routing hash, original input/context and raw/displayed/accepted lineages. A reviewer provides exact displayed quotes for A and exact state objects/deltas for B. Record reviewer identity and independence; developer/nonblind review is not independent review.

`CONTRACT_DECISION_CASES.json` defines eight required positive/negative families plus mixed-output, delivery, corruption and migration cases. P2 may implement only within its allowlist. P3 executes the bounded offline cases and affected regressions on isolated data, including restart and idempotency. Offline success does not claim target-model naturalness or external44 success. Historical 449 compatible + 1 expected source-identity sentinel must not be restated as 450 ordinary passes.

P4 requires the completed P2/P3 prerequisites and separate explicit fresh-validation authorization. P1 allocates no revision, submits no request and unlocks no downstream task. The R15 revision remains permanently quarantined with 1/44 submitted, 1/44 accepted, 4/176 reviewed, 3 PASS, 1 FAIL, 172 UNREVIEWED.
