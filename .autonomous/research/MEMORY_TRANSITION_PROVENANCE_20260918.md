# WORKER-B: memory transition provenance and growth-basis freshness

Task: `AUTO-20260918-B01`  
Worker: `AMADEUS WORKER-B — MEMORY / INTELLIGENCE`  
Run: `WORKER-B-20260918T033115+0900-B01`  
Research date: 2026-09-18 Asia/Tokyo  
Disposition: RESEARCH_DELIVERABLE_FOR_REVIEW; not runtime implementation or product acceptance.

## 1. Baseline, authorization and concurrency

Repository: `Lorenzo-Holmes/Amadeus`. Inspected default `main`: `a6ffaa388ebdab03620070c3990ffc9788425e8f`. This research branch starts from the published Persona snapshot `codex/persona-core-operations-v1-20260917` at `34ae8a3d95dbe1cc565893b81306be235a36a4cb`, not from main. PR #1 publishes that snapshot; PR #2 is the existing runtime-vNext foundation; PR #3 carries the shared autonomous control plane. None is merged by this worker.

Read the master goal, continuation protocol, progress, decision log, operational TASK_STATE and ACCEPTANCE_MATRIX, control task/decision/research records, relevant branch/PR metadata, and admission/runtime/retrieval/growth source. References below are pinned to the snapshot; this is not a claim to have inspected the unpublished Windows staging workspace or every historical evidence artifact.

The old Operations state and newer G6 progress describe different phases. Historical R044–R047 completion is protected, not inherited as current G6 acceptance. The published G6 progress records unresolved N06_T4; its outcome must not be guessed or replayed. The expected current G6 canonical directory was not accessible in the inspected snapshot. The decision-log tail retains build/product completion and production activation as false for the current G6 phase. This memo does not reconcile those authorities by rewriting them.

Claim checks: B01 was READY, assigned to WORKER-B, with null leases and no dependencies; no other B CLAIMED/RUNNING task was present. Its single-file WRITE_SET is disjoint from A/C/D deliverables and protected G6 paths. The inspected task/branch/PR records showed no completed equivalent memo; this is not an exhaustive assertion about inaccessible history. The B01 claim used the current control-file blob in a compare-and-swap update, commit `fc3e56329224d90cef37284085d86e7cfb0b26d7`, with lease 2026-09-17T18:31:15Z to 2026-09-17T22:31:15Z.

Only this research memo is a branch deliverable. Shared B01 lifecycle metadata is updated separately on `autonomous/orchestrator-state`; no other worker's task is claimed. No runtime, source, Genesis, Memory Cutoff, Persona Constitution, autobiographical authority, source authority, or acceptance record is modified. No project provider is called. All experiment events and sessions below are explicit test doubles, not product experiences.

## 2. AMADEUS_CURRENT_STATE: do not rediscover completed protections

Source root: <https://github.com/Lorenzo-Holmes/Amadeus/tree/34ae8a3d95dbe1cc565893b81306be235a36a4cb>.

| Component | Existing mechanism read in source | Consequence for this research |
|---|---|---|
| `persona_core/operational_runtime_v1/admission.py` | Host-bound decisions and receipts; original displayed turns, content hashes, entity and mode binding; persisted evidence rechecked at commit/reopen. User correction cannot rewrite source identity or trusted fulfillment. | Do not add another admission authority. An admitted utterance or correction is not proof of the described external world. |
| `persona_core/operational_runtime_v1/runtime_store.py` | Atomic append-only events, state and derived index; deterministic replay; exact index content/provenance/supersession comparison; explicit derived-index rebuild. | The broad claim that Amadeus has no transition verification would be wrong. Existing R046 work already covers this layer. |
| `persona_core/operational_runtime_v1/retrieval.py` | Authenticate, verify runtime, filter entity/mode, resolve corrections, return current commitment state and provenance. Previous correction text can rank a current record without becoming the current claim. | Ranking is not authority. Ordinary corrected-record retrieval is not the proposed new gap. |
| `persona_core/operational_runtime_v1/persona_growth.py` | Proposals require multiple allowed product-mode events across sessions; host review creates versions; output preserves governed-runtime rather than source-Persona provenance. | Investigate the lifecycle of evidence supporting a derived growth version, not replacement of Persona governance. |

Relevant source blob SHAs: admission `c16ac177bfcbdb9684d4591129d0401090262e6f`; runtime store `ca2261435e48d0950c8582a501a9f58b75f2e7c6`; retrieval `1b92a1397750b77a7cc4c7cbe4dcaa49bacf10e5`; growth `f750c38b75485703132cc8dcc01d90aac60b4df5`.

The acceptance matrix already lists the old commitment/correction retrieval gate AC-R046-04, including retrieval after 120 distractors. This work does not rerun or reopen that gate. PR #2's source/claim binding reference is also not reimplemented here.

## 3. PAPERS/PROJECTS CHECKED and comparison

The initial autonomous research ledger contains inaccurate bibliographic labels. The source identifiers are retained, but the verified titles and dates below supersede those labels for this memo only. The ledger itself is not edited outside this task's WRITE_SET. No benchmark score from a paper is represented as reproduced evidence.

### S1 — TrustMem

**SOURCE / DATE / ACCESS / LICENSE:** Tianyu Yang et al., *TrustMem: Learning Trustworthy Memory Consolidation for LLM Agents with Long-Term Memory*, arXiv:2606.25161v1, **2026-06-23**. Primary full-text HTML inspected: <https://arxiv.org/html/2606.25161v1>. The displayed paper license is CC BY 4.0; a separately licensed implementation or dataset was not verified. This corrects the initial ledger's title and June 29/30 version dates.

**EXTERNAL_METHOD:** Evaluate a memory transition for coverage, preservation and faithfulness, then use verifier signals in reinforcement learning. The verifier is model-based; Appendix D's error protocol counts major omission/corruption/hallucination errors.

**AMADEUS_CURRENT_STATE:** Event/index replay already verifies structural transitions. Governed growth is a separate derived representation.

**REAL_MEMORY_GAP:** A structurally consistent growth version can retain a basis that later changes, without an explicit fresh/stale/unknown diagnostic at its module boundary.

**NOVEL_DELTA:** Adapt the three diagnostic dimensions to an offline, source-bound growth/retrieval-view evaluation contract. Do not adopt the paper's write/revise/prune policy or scalar reward as permission.

**IDENTITY_RISK:** Optimizing recall or compactness could promote a useful summary into a personality fact or erase a relevant qualification.

**PROVENANCE_RISK:** A verifier can be wrong; a high scalar score can conceal one disallowed authority elevation.

**MINIMUM_EXPERIMENT:** Paired unchanged/corrected evidence fixtures, with required current-basis IDs, preserved historical IDs and forbidden promotions declared before evaluation.

**EVALUATION_METHOD:** Report coverage omissions, preservation distortions and unsupported additions separately. Structural violations are deterministic hard findings; semantic uncertainty remains UNREVIEWED/UNKNOWN, never a model-derived admission. This is an Amadeus proposal, not a reproduced TrustMem result.

### S2 — Agent Zero Memory

**SOURCE / DATE / ACCESS / LICENSE:** Ming Wu and Pengyuan Zhu, *Agent Zero Memory: Provenance-Aware Long-Term Memory for LLM Agents*, arXiv:2608.29606, **2026-08-30**: <https://arxiv.org/abs/2608.29606>. The primary indexed abstract was read; full-text retrieval was unavailable in this run. Code, data and paper reuse licenses were not verified. The initial ledger's subtitle is corrected here.

**EXTERNAL_METHOD:** Parallel episodic, entity-event and documentary memory, with origin/time/evidence pointers and a discipline restricting citations to evidence actually opened.

**AMADEUS_CURRENT_STATE:** Existing Amadeus retrieval already carries provenance, entity boundaries and distinct first-person scopes; adding three stores would not itself improve authority.

**REAL_MEMORY_GAP:** A pointer to an opened record does not show that the record remains applicable to the current derived conclusion.

**NOVEL_DELTA:** Extend the proposed evaluation checklist from citation presence to current-basis validity and explicit historical scope; retain one authoritative event history.

**IDENTITY_RISK:** A retrieved source fact could be narrated as first-person autobiography when the evidence only licenses external knowledge.

**PROVENANCE_RISK:** Citation existence and correct hash do not establish entailment, present validity or authorization.

**MINIMUM_EXPERIMENT:** Hold citation IDs constant while appending a supported correction; distinguish historical recall from current guidance. Include a same-text, different-entity fixture.

**EVALUATION_METHOD:** Score citation reachability, evidence role, entity/mode applicability and current-vs-historical interpretation independently. Abstract claims that fabrication is excluded are not accepted as an Amadeus guarantee.

### S3 — LifeMem

**SOURCE / DATE / ACCESS / LICENSE:** Yuli Qiu et al., *LifeMem: Enabling Lifelong Experience Reuse for LLM Agents*, arXiv:2609.12655, **2026-09-11**: <https://arxiv.org/abs/2609.12655>. Primary indexed abstract inspected; full-text retrieval unavailable. Code/data/paper reuse licenses and detailed experimental protocol were not verified. No implementation is imported.

**EXTERNAL_METHOD:** Cluster interaction trajectories by workflow into reusable skills, then retrieve skills and trajectories for later tasks.

**AMADEUS_CURRENT_STATE:** Runtime experience, source memory and governed Persona/Self adaptation have deliberately different authority.

**REAL_MEMORY_GAP:** Useful past experience can still be inapplicable after the user's conditions or the evidence supporting a derived preference change.

**NOVEL_DELTA:** Add beneficial-vs-harmful reuse contrasts to evaluation. No skill-to-self conversion, automatic consolidation or new memory database.

**IDENTITY_RISK:** Task success could be mistaken for stable identity or a shared personal preference.

**PROVENANCE_RISK:** Workflow clusters can drop who did what, under which conditions, and whether the episode was only a simulation.

**MINIMUM_EXPERIMENT:** Reuse the same episode under matching conditions, changed conditions and a different entity; preserve event origin in all variants.

**EVALUATION_METHOD:** Measure usefulness only after authority/scope checks. Report negative transfer separately; do not trade a privacy or identity violation for average task performance.

### S4 — Graphiti implementation inspection

**SOURCE / DATE / ACCESS / LICENSE:** `getzep/graphiti`, inspected commit **`de8eb5b896c05ed1b5b329d4cb52015446d65e21`**, dated 2026-09-17T08:18:45Z. Repository documentation and selected source were read, not executed. <https://github.com/getzep/graphiti/tree/de8eb5b896c05ed1b5b329d4cb52015446d65e21>. The pinned root LICENSE is Apache-2.0. No dependency, code or database is imported.

**EXTERNAL_METHOD:** Temporal graph facts preserve history. The inspected `graphiti_core/edges.py` exposes `expired_at`, `valid_at`, `invalid_at` and `reference_time`, distinguishing validity-related time from other record time. Source: <https://github.com/getzep/graphiti/blob/de8eb5b896c05ed1b5b329d4cb52015446d65e21/graphiti_core/edges.py#L270-L284>.

**AMADEUS_CURRENT_STATE:** Amadeus already has event ordering, correction chains and provenance. It does not need a second graph authority to test derived-basis freshness.

**REAL_MEMORY_GAP:** Historical evidence remaining authentic is different from its being sufficient for an unchanged current growth projection.

**NOVEL_DELTA:** Make the distinction explicit in offline fixtures and diagnostics; do not propose schema migration on the strength of these fields alone.

**IDENTITY_RISK:** Automatically treating every newly extracted contradiction as authoritative could destabilize continuity.

**PROVENANCE_RISK:** Temporal metadata can be correct while extraction or identity assignment is wrong. Selected field inspection is not a full implementation security audit.

**MINIMUM_EXPERIMENT:** A late correction to an older event, retaining both original observation order and the newly stated applicability condition.

**EVALUATION_METHOD:** Evaluate current guidance and historical questions separately. Do not infer universal invalidation correctness from a data model or import Graphiti's extraction logic into Amadeus admission.

## 4. IDENTIFIED GAP: growth-basis freshness, not missing event verification

Gap ID: `B01-GROWTH-BASIS-FRESHNESS-01`.

At the pinned source, `_evidence()` reads event IDs and computes evidence bindings during proposal. `review()` approves by copying the stored proposal into a version without rereading that evidence. `active_view()` selects approved version rows without checking their supporting events' current applicability. `audit()` compares approved proposal/version fields, but does not establish that the original support remains current. `RetrievalService.context_state()` includes that growth view alongside runtime state.

**Observed fact:** the module lacks an explicit basis-freshness check on the tested review/view/audit path. **Inference to investigate:** a later accepted correction could leave an older derived preference visible without signaling the need for governance review. **Not established:** a complete production bypass, failure of every assembled caller, or falsity of the old conclusion. One corrected supporting event need not invalidate all remaining support.

This is a research/evaluation delta beyond the inspected R046 index verification and PR #2 source-binding reference. The required response is not automatic personality deletion or rewriting. A diagnostic such as `STALE_BASIS_REVIEW_REQUIRED` is proposed only for offline reports; it is not an installed runtime enum or authority decision. Preserve the original event, its correction, the original approval and any still-valid evidence. An unrelated correction should not invalidate the growth version.

## 5. EXPERIMENT ACTUALLY EXECUTED

A source-byte-identical copy of `persona_growth.py` was materialized from the connector response after container network retrieval failed. Git blob SHA was recomputed and matched `f750c38b75485703132cc8dcc01d90aac60b4df5`; SHA-256 was `1d4da263adfb2ac3a221ebdb56e317cc6727d1a34b07e7a4092a019a5d06451f`.

The exact module was executed against explicit in-memory SQLite, authentication, hashing, clock and runtime-event doubles. No operational RuntimeStore, AdmissionController, provider transport, production directory, Genesis file or current G6 source was executed. Synthetic PRODUCT_RUNTIME labels satisfy the module's branch conditions only; they do not confer genuine product provenance. The double appends a new correction and retains the old evidence unchanged. Its supersession map represents the external state whose use by this module is being probed; it is not the actual RuntimeStore reducer or index.

Observed execution: **2026-09-17T18:38:02.793731+00:00**; Python **3.13.5**, SQLite **3.46.1**; process exit 0. Six observational cases completed: four controls and two freshness probes. These are not six product-acceptance passes.

| Case | Actual observation | Interpretation |
|---|---|---|
| Unchanged approved basis | One version emitted; zero post-proposal event reads; audit `ok`. | Baseline positive control. |
| Different entity | Zero entity-scoped versions emitted. | Existing scope filter retained. |
| Basis superseded before approval | Approval and view still emit the version; zero post-proposal event reads; audit `ok`. | Freshness not checked at this module boundary. |
| Basis superseded after approval | View still emits the version; zero post-proposal event reads; audit `ok`. | Same gap after activation. |
| Raw utterance as support | Rejected. | Existing event-kind guard retained. |
| Support from only one session | Rejected. | Existing multi-session guard retained. |

The harness SHA-256 is `a76a661b2767b5b8b31fafd8bd3942077a7da64bd6dbca67ed1462e77e9a70d4`. Reproducible harness and actual output are appended in the evidence supplement of this same memo. The module test is deliberately insufficient to close a runtime implementation task or declare a new defect in unpublished G6 code.

## 6. MINIMUM_EXPERIMENT and EVALUATION_METHOD for the next allocation

The next task should be explicitly allocated by the orchestrator with its own non-conflicting WRITE_SET. It should first test a disposable assembled runtime with real admission and correction APIs, against a verified source/fixture package. Do not silently extend this memo-only lease into implementation. Direct current-G6 work remains blocked until its canonical source and persisted evidence are available.

Freeze a small paired evaluation before any candidate patch: unchanged support; relevant correction before review; relevant correction after approval; unrelated correction; partial support still valid; late correction whose applicability time differs from observation order. Include source-vs-runtime, entity and mode contrasts in that package. The current six-case probe is development evidence, not a new hidden test set.

Use a report-only tuple of `baseline_sha`, input event IDs/hashes, correction links, proposal/version IDs, entity/mode, observation sequence, evidence role, projected fields and diagnostic reasons. Obtain supersession from the existing verified event/index authority rather than trusting caller-supplied `is_current` flags. If an assembled runtime already blocks the stale projection, close this candidate as contained/documentation-only instead of inventing a repair.

**Authority:** existing host admission, frozen source boundaries and governance decide what may be used or changed. **Ranking:** recency, salience and relevance only order eligible evidence. **Proposal:** a model or heuristic may suggest a synthesis but cannot install it. These axes must remain separate even when a paper combines them into a reward.

Proposed offline diagnostics, not claimed implemented metrics:

- Coverage: required evidence and qualification atoms omitted from the inspected derived representation, divided by the fixture's required atoms. A historical item intentionally excluded from current guidance is not automatically an omission.
- Preservation: unauthorized loss/change of retained history, entity, mode, temporal or first-person scope. Check historical availability separately from current prompt inclusion.
- Faithfulness: projected atoms not supported within the permitted evidence role. A citation ID or checksum is not semantic entailment.
- Freshness: number of relevant changed-basis fixtures lacking a review/withhold/explicit-historical diagnostic. UNKNOWN and unreviewed semantic judgments stay in separate denominators rather than counting as passes.

Hard gates: zero authority elevations, cross-entity promotions, source-to-autobiography promotions or rewrites of protected history. Never average these away with utility. Correctly scoped valid evidence must remain usable; blanket suppression is not success. Measure usefulness, abstention quality and context size separately.

A truncation contrast may later place a necessary negation/condition beyond `retrieval.py`'s 900-character content boundary. That boundary and truncation flag are source observations, not a reproduced semantic defect here. Similarly, repeat a frozen context through different model adapters only after a permitted provider scope exists; the present no-provider probe cannot prove model-switch continuity. Synthetic dates cannot satisfy natural-day validation.

## 7. RISKS, disposition and rollback

Principal risks are false confidence from synthetic doubles or model judges, treating changed evidence as automatically false, losing counterexamples under compaction, stale citations, and confusing a useful workflow with a self/identity fact. For salience/forgetting, propose prompt exclusion or review of applicability, not destruction of authoritative history. A governance decision may legitimately preserve a conclusion on remaining evidence; record that rationale rather than letting a benchmark silently decide identity.

No replacement memory store, graph migration, RL writer, provider retry, model output authority or production activation is proposed as part of B01. Paper/code-license uncertainty bars copying unverified implementations; the verified Graphiti license does not authorize its use as a second Core.

Research disposition: **a narrow, source-grounded evaluation gap exists; not IDLE_NO_MEMORY_GAP**. Deliver for review. The next action is an orchestrator-scoped assembled-runtime freshness experiment, not a Persona change. Any direct G6 continuation must separately resolve the canonical-source/ledger blocker and preserve UNKNOWN no-replay semantics.

Rollback: decline/close the research PR, or revert its memo commit after any future explicitly authorized merge. There is no database migration or Persona-state rollback. Keep control-plane lifecycle history; do not force-push, erase prior approvals or restore an old database over new experiences.
