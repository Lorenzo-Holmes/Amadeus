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

## AUTO-DEC-008 — Persistent-memory-poisoning research creates an evaluation task, not an authority rewrite

Date: 2026-09-18. Status: ACTIVE.

Fresh research on persistent memory poisoning is relevant because cross-session reuse can turn injected text into a durable influence channel. The inspected Amadeus admission layer already treats chat, retrieval and model text as untrusted and requires host-issued evidence for admitted effects, so the research does not justify replacing `AdmissionController`, adding a second memory authority, or changing Persona/Genesis state.

A new READY task, `AUTO-20260918-C02`, is therefore limited to an offline adversarial regression suite and report. It must exercise persistence/retrieval across sessions, entity isolation, correction/supersession and attempted state/action escalation, with benign negative controls. Provider calls and external side effects remain zero. Any discovered defect is evidence for later review, not permission to silently patch protected runtime or declare product acceptance.

This task is novel relative to C01 state-drift auditing, B01 growth-basis freshness, D01 observability research, the existing admission contract, and PR #2 claim/evidence reference work. Its WRITE_SET is disjoint from all current REVIEW work and there are no valid CLAIMED/RUNNING tasks at this checkpoint.

## AUTO-DEC-009 — Security prose is not proof of enforcement

Date: 2026-09-18. Status: ACTIVE.

A security requirement written in documentation, a prompt, a worker instruction, or a model-facing policy is an obligation or advisory constraint, not evidence that the runtime deterministically blocks the prohibited effect. The control plane may mark a requirement `ENFORCED` only when it can cite a concrete host/runtime/OS enforcement point and the scope of that control.

The currently inspected `AdmissionController` is real enforcement evidence for its explicitly supported state-admission effects: untrusted text cannot manufacture host-issued evidence, request forbidden state authority, or cross entity boundaries. That evidence must not be generalized into a claim that future tool execution is already protected. Runtime-vNext's `ActionIntent -> host authorization -> execution ledger -> tool` path is an architecture proposal in PR #2, not an integrated production tool gate.

Fresh research on prose-vs-built-in deny controls, deterministic pre-action authorization, Agent Control Specification, and MCP tool sandboxing therefore creates one bounded GREEN task: `AUTO-20260918-A02`. It is a read-only/offline permission-enforcement coverage audit. It must distinguish state admission, action/tool authorization, OS sandboxing, user approval, and provider UNKNOWN/replay handling; documentation alone cannot satisfy an enforcement classification.

OAP, Microsoft Agent Governance Toolkit/ACS, and MCPGuard-Dynamic are comparative references only. This decision does not authorize a parallel permission authority, a new production tool executor, a sandbox migration, or replacement of existing AdmissionController/ProviderJournal semantics. No Persona, Genesis, Memory Cutoff, provenance, locked decision, G6 acceptance, historical evidence, or production activation state is changed.

## AUTO-DEC-010 — Verified-forgetting research must preserve audit history and authority boundaries

Date: 2026-09-18. Status: ACTIVE.

Fresh memory research distinguishes correction/supersession from deletion fidelity: information can disappear from active recall yet survive in derived summaries, indexes, growth projections, backups, or other downstream representations. The inspected Amadeus runtime intentionally keeps `runtime_events` append-only, recomputes retrieval documents from verified events, and resolves correction chains before retrieval. That design is evidence-preserving and must not be treated as a bug merely because it does not expose a user-facing deletion primitive.

A bounded research-only task, `AUTO-20260918-B02`, may therefore study **verified forgetting / deletion fidelity** as a future governance problem. It must explicitly separate: immutable historical/audit evidence; active-recall suppression; correction/supersession; derived-artifact invalidation; provenance-scoped tombstones; backup/export residue; and any future privacy-driven physical purge. It may propose deterministic offline evaluation fixtures and receipts, but it may not delete or rewrite R044-R047 evidence, Genesis, Persona Constitution, Memory Cutoff, autobiographical-memory authority, source provenance, locked decisions, current G6 evidence, or production state.

This task is not permission to import utility-decay or learned forgetting as Persona authority. Retrieval absence is not proof of physical deletion, and physical deletion is not proof that derived representations no longer contain the information. Any eventual implementation that touches durable history, identity, privacy deletion, or production persistence is YELLOW/RED and requires a separately reviewed task with backup, provenance, rollback and legal/product semantics resolved first.