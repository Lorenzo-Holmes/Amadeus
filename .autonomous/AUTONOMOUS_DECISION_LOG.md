# Amadeus Autonomous Decision Log

## AUTO-DEC-001 — GitHub shared state is the concurrency authority

Date: 2026-09-18. Status: ACTIVE.

The orchestrator must not infer worker activity from ChatGPT UI generation state. Valid concurrency is derived from `.autonomous/AUTONOMOUS_TASK_STATE.json` plus branch/commit/PR evidence. A lease alone is insufficient after expiry; branch, commit, PR and task output must be inspected before release.

## AUTO-DEC-002 — Bootstrap from the Persona snapshot, not `main`

Date: 2026-09-18. Status: ACTIVE.

`main` is at `a6ffaa388ebdab03620070c3990ffc9788425e8f`, while the only published Persona operational snapshot is `codex/persona-core-operations-v1-20260917` at `34ae8a3d95dbe1cc565893b81306be235a36a4cb`. The autonomous control branch is created from the Persona snapshot so its orchestration records can reason about current published Persona files without rewriting `main` or presenting the snapshot as newly authored work.

## AUTO-DEC-003 — Preserve Operations completion; do not inherit it into G6

Date: 2026-09-18. Status: ACTIVE.

`persona_core/operational_build_v1/TASK_STATE.json` records `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`, while the root progress/decision log contains a newer G6 optimization line whose latest visible decision says current G6 build-scope completion is false. Therefore R044-R047 are protected historical/completed work and must not be rebuilt, while their completion flags are not inherited as G6 completion.

The orchestrator does not silently choose one file as the universal truth when authorities differ by phase. It records the divergence and blocks direct G6 state mutation until the actual canonical G6 source/evidence is available.

## AUTO-DEC-004 — `feat/amadeus-runtime-vnext-foundation` occupies one conservative lease

Date: 2026-09-18. Status: ACTIVE UNTIL LEASE RECONCILIATION.

The branch has commits at 2026-09-17T18:11:53Z, is two commits ahead of the Persona snapshot, and writes only `docs/runtime_vnext/**`. With no pre-existing shared lease state, the bootstrap conservatively records it as `RUNNING` for four hours rather than risking duplicate architecture work. This bootstrap lease must be reconciled against later branch/PR/task evidence when it expires.

## AUTO-DEC-005 — No fifth implementation task; research-first slots are legitimate

Date: 2026-09-18. Status: ACTIVE.

TARGET_CONCURRENCY=4 counts only CLAIMED+RUNNING. With one conservative active worker, three READY tasks are permitted. Two are research-only and one is isolated read-only audit tooling. Worker idleness does not justify code generation. If these tasks are later claimed, their non-overlapping write sets permit parallel execution.

## AUTO-DEC-006 — Current direct G6 implementation is BLOCKED, not READY

Date: 2026-09-18. Status: ACTIVE.

The inspected GitHub snapshot does not expose the expected `persona_core/gpt6_optimization_v2/` canonical directory or complete current provider/persisted evidence, while the published progress references an unresolved `N06_T4` that must not be replayed. Consequently, continuing G6 implementation from summaries would require inventing state. `HOLD-G6-07-CANONICAL` remains BLOCKED until the canonical source and ledger can be verified.

## AUTO-DEC-007 — External research can create evaluation deltas, not authority deltas

Date: 2026-09-18. Status: ACTIVE.

TrustMem, Agent Zero Memory, LifeMem, OpenTelemetry GenAI conventions, Harness-of-Harness and long-horizon RCA research are useful only after mapping them against Amadeus's current architecture. No external project is considered a reason to replace the existing Persona, memory-admission, provenance, RuntimeStore or ProviderJournal authorities. Proposed near-term deltas are restricted to offline evaluation, read-only state auditing, observability research and comparative architecture.
