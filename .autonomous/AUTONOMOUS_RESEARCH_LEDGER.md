# Amadeus Autonomous Research Ledger

Run: `ORCH-20260918T021519+0800-01`  
Control branch: `autonomous/orchestrator-state`  
Scope: research evidence for future tasks; no research item is itself authority to alter Persona, Genesis, Memory Cutoff, provenance, runtime state, or production activation.

## Finding R-20260918-01 — TRUSTMEM: transition-level memory consolidation verification

- **SOURCE:** TRUSTMEM: A Trustworthy LLM Agent Memory Framework with Policy-Driven Consolidation and Verification
- **SOURCE_DATE:** arXiv v1 2026-06-29; v2 2026-06-30
- **PROBLEM:** Long-term agent memory consolidation can omit important evidence, distort retained content, or introduce unsupported details during memory-state transitions.
- **CORE_IDEA:** Treat each memory transition as a verifiable transformation and measure coverage, preservation, and faithfulness; the paper then uses those signals to guide consolidation policy.
- **AMADEUS_CURRENT_STATE:** The inspected snapshot already separates trusted admission, transactional event/state storage, provenance-preserving retrieval and governed Persona growth. These existing authority boundaries are stronger than a generic model-managed memory store and should remain authoritative.
- **REAL_GAP:** The snapshot does not visibly expose a reusable, transition-level omission/corruption/hallucination evaluation contract that can be run offline across memory/retrieval-derived transformations.
- **PROPOSED_DELTA:** Research and specify offline verification fixtures that test whether a derived memory/retrieval representation preserves required admitted evidence, excludes revoked/superseded claims, and adds no unsupported facts. Do **not** import the paper's RL consolidation policy as authority.
- **RISKS:** Metric gaming; false confidence from evaluator models; collapsing source authority into a scalar trust score; accidentally treating summaries as authoritative memory.
- **LICENSE:** Paper use/reproduction terms were not independently verified in this run. Treat algorithms/descriptions as research references only until code/data licenses are checked separately.
- **EVALUATION_METHOD:** Synthetic and repository-grounded transition fixtures with known required evidence, supersession chains and forbidden hallucinated facts; deterministic structural checks first, model-based semantic evaluation only as non-authoritative secondary evidence.
- **TASK LINK:** `AUTO-20260918-B01`

## Finding R-20260918-02 — Agent Zero Memory: provenance and citation-lock discipline

- **SOURCE:** Agent Zero Memory: Self-Evolving Long-Term Memory for Tool-Using Agents
- **SOURCE_DATE:** arXiv:2608.29606, 2026-08
- **PROBLEM:** Long-horizon agents need durable memory while avoiding source drift and unverifiable recollection.
- **CORE_IDEA:** Reported provenance-aware memory mechanisms and citation-lock style controls aim to keep derived memories connected to origin evidence while permitting memory evolution.
- **AMADEUS_CURRENT_STATE:** Amadeus already records evidence provenance, correction/supersession semantics and object/mode isolation in its operational runtime snapshot.
- **REAL_GAP:** It is still useful to compare whether every derived retrieval/summary path in Amadeus can be traced to live, non-revoked evidence and whether stale derived artifacts are invalidated when their basis changes.
- **PROPOSED_DELTA:** Comparative evaluation checklist only: citation completeness, supersession propagation, invalidation behavior, and source-bound retrieval outputs. No second memory database or replacement provenance authority.
- **RISKS:** Project-level claims may rely on paper descriptions rather than inspected code; a citation can exist yet point to insufficient or wrong evidence; provenance metadata can become stale.
- **LICENSE:** Code/license not verified in this run; no code import is authorized from this finding.
- **EVALUATION_METHOD:** Trace each selected retrieved/derived item to admitted event IDs and current correction chain; inject revoked/superseded evidence and require stale outputs to be rejected or rebuilt.
- **TASK LINK:** `AUTO-20260918-B01`

## Finding R-20260918-03 — LifeMem: lifelong experience reuse should remain evaluation-first

- **SOURCE:** LifeMem: Learning from Lifelong Experience in Large Language Model Agents
- **SOURCE_DATE:** arXiv:2609.12655, September 2026
- **PROBLEM:** Long-lived agents accumulate experience that can help future behavior, but unconstrained reuse can transfer irrelevant, stale or unverified experience.
- **CORE_IDEA:** The work studies learning/reusing accumulated experience for future tasks across long horizons.
- **AMADEUS_CURRENT_STATE:** Amadeus already distinguishes source identity, Genesis, post-Genesis experience, controlled memory admission, retrieval and governed Persona growth.
- **REAL_GAP:** There is room to evaluate when past runtime episodes should be retrieved or withheld, especially under changed context, corrections and user/entity boundaries.
- **PROPOSED_DELTA:** Build research fixtures for beneficial-vs-harmful experience reuse: same-goal/same-entity, stale correction, cross-entity contamination, changed-condition and superseded-commitment cases. Do not auto-consolidate experience into Persona or autobiographical authority.
- **RISKS:** Negative transfer; privacy leakage; cross-user contamination; overfitting evaluation fixtures; turning performance heuristics into identity facts.
- **LICENSE:** Paper/code license not verified in this run; no implementation import authorized.
- **EVALUATION_METHOD:** Paired retrieval-ablation tests with provenance and entity isolation checks; score task usefulness separately from truth/admission correctness.
- **TASK LINK:** `AUTO-20260918-B01`

## Finding R-20260918-04 — OpenTelemetry GenAI semantic conventions

- **SOURCE:** OpenTelemetry Semantic Conventions — Generative AI systems / agent and operation spans
- **SOURCE_DATE:** Current documentation observed 2026-09-18; conventions are evolving and status varies by signal/attribute.
- **PROBLEM:** Long-running AI systems are hard to debug when provider calls, agent operations, tool attempts and state transitions use ad-hoc telemetry.
- **CORE_IDEA:** Standardized span/event/attribute vocabulary for GenAI operations can make traces more portable across observability backends.
- **AMADEUS_CURRENT_STATE:** `ProviderJournal` already durably distinguishes request attempts, raw responses, usage estimates and `SUBMITTED_STATUS_UNKNOWN`; `RuntimeStore` provides transaction/event evidence. These records are evidence sources, not telemetry-derived facts.
- **REAL_GAP:** The inspected snapshot does not expose a standardized cross-component trace vocabulary linking chat turn, provider attempt, retrieval, admission decision, state commit and tool execution while preserving the stronger journal semantics.
- **PROPOSED_DELTA:** Research a non-authoritative trace mapping layered over existing durable IDs. Default to hashes/IDs/statuses and bounded metadata; raw prompt, retrieved memory and tool outputs remain opt-in/redacted.
- **RISKS:** Sensitive prompt/memory leakage; high-cardinality cost; accidental reliance on telemetry as trusted state; semantic convention churn.
- **LICENSE:** OpenTelemetry Semantic Conventions repository/docs are Apache-2.0 project materials; verify exact vendored component license before copying source or schemas.
- **EVALUATION_METHOD:** Trace completeness tests from a synthetic turn across retrieval→provider→display/admission→commit, including timeout/UNKNOWN and crash recovery; assert telemetry loss cannot alter runtime truth.
- **TASK LINK:** `AUTO-20260918-D01`

## Finding R-20260918-05 — Harness-of-Harness: multi-day autonomous development as evidence-governed iteration

- **SOURCE:** Harness-of-Harness: Managing Multi-Day Autonomous Software Development
- **SOURCE_DATE:** arXiv:2609.01481, September 2026
- **PROBLEM:** Long autonomous coding runs drift, lose context, accumulate partial work and can mistake activity for progress.
- **CORE_IDEA:** A supervising harness structures repeated agent work, evaluation and recovery across multi-day development rather than relying on one uninterrupted context.
- **AMADEUS_CURRENT_STATE:** Amadeus has continuation protocols, recovery points, task/evidence files and now a GitHub-backed orchestration control plane. The user explicitly requires GitHub task/branch/PR state—not UI generation status—as concurrency truth.
- **REAL_GAP:** Shared leases, write-set conflict checks, novelty signatures and machine-readable task lifecycle were absent from the inspected repository before this run.
- **PROPOSED_DELTA:** Keep orchestration state small, explicit and branch-backed; tasks need evidence-based leases, non-overlapping write sets and acceptance semantics. Evaluation and review remain independent from mere worker completion.
- **RISKS:** Supervisory bureaucracy; stale leases; central orchestrator becoming a false semantic authority; excessive parallel work that increases merge conflicts rather than useful throughput.
- **LICENSE:** Paper/project implementation license not verified in this run; concepts only, no code import.
- **EVALUATION_METHOD:** Replay orchestration scenarios: worker disappears after commit, stale lease with open PR, write-set collision, semantic duplicate with renamed task, no-safe-new-task case.
- **TASK LINK:** Orchestrator control-plane design; `AUTO-20260918-D01` for deeper comparison.

## Finding R-20260918-06 — Long-horizon root-cause attribution

- **SOURCE:** Root-Cause Attribution Is a Search Problem: Long-Horizon Evaluation and Diagnosis of AI Agent Failures
- **SOURCE_DATE:** arXiv:2609.13463, September 2026
- **PROBLEM:** In long traces, the visible failure can occur far after the causal decision; naive last-step inspection misattributes root causes.
- **CORE_IDEA:** Treat root-cause diagnosis as search over a long trajectory, with evidence linking candidate causal steps to eventual failures.
- **AMADEUS_CURRENT_STATE:** Provider/runtime journals preserve many causal artifacts, but the repository currently contains contradictory high-level state summaries whose relationship had to be inspected manually.
- **REAL_GAP:** No generic read-only state/trajectory auditor is visible that reports conflicting checkpoints, missing referenced evidence and protected-state contradictions without trying to rewrite state.
- **PROPOSED_DELTA:** A deterministic state-drift auditor first; later, research trajectory-RCA over durable IDs. Avoid model-generated causal claims becoming acceptance authority.
- **RISKS:** Correlation mistaken for causation; unbounded trace volume; diagnosis tooling leaking content; automated auditor choosing a winner between two semantically different authorities.
- **LICENSE:** Paper/code license not verified in this run; no code import.
- **EVALUATION_METHOD:** Known-divergence fixtures, missing-evidence fixtures and protected-state contradiction fixtures; the tool must output explicit `CONFLICT`/`UNKNOWN` rather than silently reconcile.
- **TASK LINK:** `AUTO-20260918-C01`, `AUTO-20260918-D01`

## Finding R-20260918-07 — Persistent Memory Poisoning Attack: cross-session instruction persistence

- **SOURCE:** When Malicious Instructions Persist: Persistent Memory Poisoning Attack on Harness-Based Agents, arXiv:2609.13889.
- **SOURCE_DATE:** 2026-09-12.
- **PROBLEM:** A malicious instruction can be embedded in content that an agent persists as memory and later retrieves in another session, converting a one-shot injection into a durable cross-session influence channel.
- **CORE_IDEA:** Evaluate the attack at the memory lifecycle boundary: ingestion, persistence, retrieval, and later instruction interpretation, rather than only at the original prompt boundary.
- **AMADEUS_CURRENT_STATE:** `AdmissionController` already treats chat, retrieval and model text as untrusted and requires host-issued evidence tokens for admitted effects; forbidden source-memory, Persona, capability, state-replacement and Genesis effects are explicitly rejected. This is a stronger authority boundary than the attack paper assumes for many harness agents.
- **REAL_GAP:** No currently reviewed Amadeus task/PR exercises an adversarial cross-session fixture where apparently useful external/tool-like content contains hidden operational instructions, survives persistence/retrieval, and then attempts to obtain state/action/Persona authority in a later session.
- **PROPOSED_DELTA:** Add an offline security evaluation only. Persist/retrieve poison-shaped content as data, reopen across sessions, exercise entity boundaries and correction/supersession, and prove it cannot become authority without the existing host admission path. Do not replace `AdmissionController`, add a second memory authority, or change protected Persona state.
- **RISKS:** A synthetic fixture may overstate real exploitability; testing only admission could miss expression/tool-following effects; security tests themselves can accidentally encode unsafe strings into authoritative fixtures if boundaries are sloppy.
- **LICENSE:** Paper/code reuse terms were not independently verified in this run. No external implementation or dataset import is authorized by this finding.
- **EVALUATION_METHOD:** Offline negative/positive controls across two sessions: benign durable data still works; poison-shaped instructions remain quoted/retrieved data; requested state/action effects fail without host evidence; cross-entity retrieval stays isolated; correction/supersession does not resurrect stale poison. Zero provider calls and zero external side effects.
- **TASK LINK:** `AUTO-20260918-C02`.

## Finding R-20260918-08 — MemSentry: detection patterns are secondary to host authority

- **SOURCE:** MemSentry: A Framework for Detecting Persistent Memory Poisoning in Agentic AI, arXiv:2609.08747.
- **SOURCE_DATE:** 2026-09-08.
- **PROBLEM:** Agent memories need a repeatable way to flag suspicious durable content before later reuse.
- **CORE_IDEA:** The work frames persistent-memory screening around explicit dispositions such as accept/review/quarantine and highlights memory-specific poisoning indicators.
- **AMADEUS_CURRENT_STATE:** Amadeus already has deterministic host-side admission and evidence binding. A detector therefore cannot be allowed to become a new source of truth or grant authority merely because it labels content safe.
- **REAL_GAP:** Amadeus lacks a dedicated adversarial regression suite showing that suspicious content remains non-authoritative after persistence and retrieval; this is an evaluation gap, not evidence that the production admission design is already exploitable.
- **PROPOSED_DELTA:** Use MemSentry only as a comparative checklist for attack classes and test-case diversity. Keep deterministic admission as the authority boundary; any future classifier should be advisory and fail closed.
- **RISKS:** False negatives, false positives that suppress useful memory, classifier drift, and accidental escalation of a safety score into authorization.
- **LICENSE:** Exact code/data license was not independently verified in this run; no source is imported.
- **EVALUATION_METHOD:** Map proposed attack classes to deterministic C02 fixtures and require explicit safe failure modes. A detector result alone must never authorize state, tool or Persona effects.
- **TASK LINK:** `AUTO-20260918-C02`.

## Research disposition

No source above justifies immediate migration or replacement of Amadeus runtime, memory authority or Persona Core. The actionable deltas remain deliberately limited to **evaluation**, **read-only auditing**, **observability research**, **security regression testing**, and **comparative design** until the current G6 canonical source/evidence is available and reconciled.
