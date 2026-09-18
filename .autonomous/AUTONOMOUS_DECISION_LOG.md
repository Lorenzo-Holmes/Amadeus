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

## AUTO-DEC-011 — Multimodal observations and audit anchors remain non-authoritative; do not manufacture another READY task

Date: 2026-09-18. Status: ACTIVE.

Fresh MMPIBench and TRACER research identifies a real future boundary: image/audio/tool observations can carry injected instructions, and generated claims need traceable support to observation evidence. The current inspected Amadeus snapshot, however, does not expose an integrated production multimodal/tool execution surface. Runtime-vNext only describes future adapters. Therefore this run records the boundary as research evidence rather than pretending a current exploit surface exists or opening implementation work that cannot yet be grounded in real integration code.

Perceptual text, OCR, audio transcripts, tool observations and model-produced provenance must be treated as **untrusted observations/data**. They do not obtain state, action, Persona, autobiographical-memory, source-provenance or acceptance authority merely because they were perceived, cited, or accompanied by a provenance record. Any future multimodal evaluation should distinguish perception, interpretation, attempted propagation, authorization and committed effect so that a blocked attack attempt is still visible evidence.

The inspected `mpi-dsg/agent-flight-recorder` research prototype is folded into existing `AUTO-20260918-D01`, not opened as a parallel implementation task. Its hash-chain/Merkle/external-anchor design can inform tamper/incomplete-trace evaluation, but `RuntimeStore` and `ProviderJournal` remain the durable Amadeus truth. Cryptographic integrity proves byte/history consistency under stated checkpoints, not semantic correctness, authorization, complete history, Persona truth or product acceptance. A valid prefix can also remain incomplete without a trusted terminal checkpoint, a limitation the project itself documents.

At this checkpoint C02 has a still-valid lease and D01, A02 and B02 already form three non-overlapping READY tasks for the three remaining potential concurrency slots. The new multimodal findings are novel as future research, but they are not sufficiently actionable to justify a fourth queued READY task while no actual multimodal execution surface exists. Result for new task creation in this run: `NO_SAFE_NEW_TASK`.

## AUTO-DEC-012 — Canonical G6 publication resolves source availability, not provider or semantic readiness

Date: 2026-09-18. Status: ACTIVE / SUPERSEDES ONLY THE SOURCE-AVAILABILITY PREMISE OF AUTO-DEC-006.

The Persona branch advanced to `9ad6063ce7001d222e5823f55d65b0e265015546` and now publishes `persona_core/gpt6_optimization_v2/`, including the current execution runbook and claim/evidence adjudication. Therefore the earlier statement that canonical G6 source/evidence is unavailable is no longer current. The historical observation in AUTO-DEC-006 remains preserved; it is not rewritten.

This new publication does **not** make G6-07 READY for paid semantic validation. The current runbook and adjudication say the claim/evidence mechanism is offline-complete but not model-semantic acceptance; `R8-N02-01` and `R8-N06-01` remain OPEN; `N06_T4` and `N07_T3` remain `SUBMITTED_STATUS_UNKNOWN` and non-replayable; long-generation provider readiness is not established; all build/product/production flags remain false and new candidate days remain 0/3.

DeepSeek's current official Responses API is stateless. Streaming provides ordered SSE `sequence_number` events and a terminal `response.completed` / `response.incomplete` / `response.failed` event when that terminal event is actually received, but `previous_response_id`, stored conversations and server-side response storage are not supported. Consequently, streaming progress can improve observability during a connection but cannot be treated as an authoritative reconciliation mechanism after a dropped connection. Generic provider advice to retry 500/503 errors does not override Amadeus's journal-first `SUBMITTED_STATUS_UNKNOWN` no-replay rule.

`HOLD-G6-07-CANONICAL` therefore remains BLOCKED for updated reasons: establish provider readiness without replaying either UNKNOWN, establish a substantive experiment basis for the two OPEN MAJOR findings, then freeze a new complete source/model/configuration/price/finite-spend scope with `automatic_paid_retries=0`. Only a genuinely fresh scope may proceed through external44 44/176, heldout113/452 and original82/328 before a new candidate, independent review or natural-day evidence.

The expired C02 lease was also reconciled under AUTO-DEC-001: after expiry its reserved branch remained exactly at the old baseline, no task commit or PR existed, and no separate task output was found. The lease is released to READY, but C02 must re-ground on `9ad6063...` before a new claim. With C02/D01/A02/B02 now forming four non-overlapping READY scopes and zero active leases, this run creates no fifth task: `NO_SAFE_NEW_TASK`.
