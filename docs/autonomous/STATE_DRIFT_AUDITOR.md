# WORKER-C: deterministic read-only state-drift auditor

Task: AUTO-20260918-C01. Implementation baseline: `34ae8a3d95dbe1cc565893b81306be235a36a4cb` on `codex/persona-core-operations-v1-20260917`. Default main was inspected at `a6ffaa388ebdab03620070c3990ffc9788425e8f`. Feature branch: `feat/worker-c-state-drift-auditor-20260918`. Control-plane claim commit: `fff3633c2f3ecf93dd1c039726b9bf4e1fb9d7a8`.

This design is recorded before implementation. Test results belong in `tools/autonomous_state_audit/VALIDATION.json` and `TEST_OUTPUT.txt`; this document does not predeclare PASS.

## Observed baseline and non-duplication

The published Operations task state has plan `APCORE-OPERATIONS-V1` and phase `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`; the marked active progress block has plan `APCORE-GPT6-OPTIMIZATION-V2`, last completed G6-06, and state `GPT6_PARTIAL_REVIEW_BOUND_CAPABILITY_REPAIR_IN_PROGRESS`. These scopes can coexist. The defect to prevent is silently treating historical Operations completion as current G6 completion, not the mere existence of history.

The complete inspected Persona tree (`314cabd3c1ee138c849e718064480a9a1964d620`) has no `gpt6_optimization_v2` child. The complete operational-build tree (`761f79bcbbb7a1288ad61e787a5875858351cd24`) has no `evidence` child. This is a publication/access gap, not proof that the original Windows workspace lost evidence. Do not reconstruct canonical files or raw records from summaries.

The active published progress records N06_T4 as unresolved. A missing journal is not zero unresolved calls, and not proof of non-submission. No request is replayed, resent, replaced, or resolved by this tool.

Existing acceptance gates AC-R045-03, AC-R046-02/03/06 and AC-R047-04 already address provider failures, concurrency/idempotency, recovery/corruption, migration and genuine external/day evidence. R044-R047 are not rerun or replaced here. Their recorded PASS values remain historical declarations unless the original evidence is independently available and validated for its exact scope.

`audit_operations_resume.py` reads a specific historical runtime database and creates backups/audit artifacts. It does not reconcile current control metadata across phases. `test_fault_recovery_matrix_r047.py` tests classified historical UNKNOWN counts and no-resend values; it does not establish completeness of a newly published G6 journal. PR #2's synthetic Claim/Evidence tests intentionally establish structural bindings, not proposition truth or product acceptance. C01 adds a separate, read-only metadata checker, not a second runtime, memory authority or durable-execution system.

## New evaluation contract

Common WRITE_SET: `tools/autonomous_state_audit/**` and this document only. Shared task claiming/reporting uses current-blob compare-and-swap on the control branch, separately from implementation. No Persona files, historical tests/evidence, source/Genesis, Constitution, Memory Cutoff, runtime database, provider journal, production flag or acceptance flag may be modified.

### C01-F1: cross-phase completion inheritance

- NEW_FAILURE_MODE: an old plan's completed build or natural dates are presented as current-plan acceptance.
- WHY_EXISTING_TESTS_MISS_IT: historical runtime/storage tests operate within their own plan and candidate; structural binding tests do not reconcile root progress with Operations state.
- ORACLE: preserve each plan/state independently; emit SCOPE_RECONCILIATION_REQUIRED when scopes differ. Never choose a universal authority or emit semantic PASS.
- TEST_DESIGN: pair completed Operations JSON with a marked G6 active block; append old PASS text below the active block; remove/duplicate/corrupt the active markers.
- FALSE_POSITIVE_RISK: legitimate history is not corrupt. The finding is UNKNOWN pending scoped reconciliation, not a claim that either historical file is false. Markdown parsing is deliberately narrow, not natural-language interpretation.
- WRITE_SET: common write set above.
- ACCEPTANCE: divergent plans remain distinct; trailing historical text cannot override the active block; ambiguous parsing yields UNKNOWN.

### C01-F2: missing evidence interpreted as successful recovery

- NEW_FAILURE_MODE: missing, malformed or inaccessible evidence yields an empty collection that is mistaken for zero failures/UNKNOWNs.
- WHY_EXISTING_TESTS_MISS_IT: historical classifiers and their tests do not establish that the current G6 source, cursor and provider journal are present in a published snapshot.
- ORACLE: missing required source/evidence is UNKNOWN or BLOCKED, never PASS, NOT_SUBMITTED, or resolved. An existing file establishes availability only, not validity.
- TEST_DESIGN: missing PASS-gate evidence, malformed JSON/duplicate keys/wrong shapes, absent G6 directory/cursor/journal, and one published unresolved request with no journal. File presence must not grant acceptance.
- FALSE_POSITIVE_RISK: an intentionally partial export must be labeled partial; missing locally does not mean missing globally. No database is opened or repaired.
- WRITE_SET: common write set above.
- ACCEPTANCE: stable machine-readable findings preserve all reported unresolved identifiers and explicitly withhold replay permission and acceptance.

### C01-F3: stale or inconsistent shared ownership evidence

- NEW_FAILURE_MODE: stale counters, expired leases, duplicate task IDs, overlapping active write sets or branch/PR head mismatch are treated as safe ownership.
- WHY_EXISTING_TESTS_MISS_IT: runtime transaction tests do not test GitHub control-plane leases and branch/PR observations. A real initial claim in this run was rejected with HTTP 409 after WORKER-B updated the shared blob; reread-and-CAS preserved B's claim.
- ORACLE: explicit as-of time, source observations, unique IDs and disjoint supported write sets. Expiry never auto-releases ownership; branch existence never proves a worker process is alive.
- TEST_DESIGN: deterministic lease fixtures, conflicting and adjacent directories, unresolved dependencies, counter disagreement, missing/partial/stale branch observations and mismatched declared PR heads.
- FALSE_POSITIVE_RISK: external snapshots can be incomplete or stale. Such cases remain UNKNOWN. Only literal paths and suffix `/**` patterns are interpreted; other glob syntax remains UNKNOWN rather than silently disjoint.
- WRITE_SET: common write set above.
- ACCEPTANCE: no task acquisition/release, metadata write, network request or PR merge occurs inside the auditor. All ambiguity is visible.

### C01-F4: protected-invariant attestation without byte evidence

- NEW_FAILURE_MODE: a boolean declaration or existence check is mistaken for proof that protected bytes are unchanged.
- WHY_EXISTING_TESTS_MISS_IT: schema/metadata assertions alone do not compare the actual protected file bytes across snapshots.
- ORACLE: compare only explicitly supplied baseline SHA-256 entries against safely readable files; report missing baseline/entry/unreadable path as UNKNOWN and mismatches as CONFLICT.
- TEST_DESIGN: matching/mismatched/missing protected files, bad digests, traversal/symlink attempts and no baseline. Read-only integration compares input bytes and modification times before/after.
- FALSE_POSITIVE_RISK: a supplied manifest is not automatically trustworthy and does not establish full protected-tree coverage. The report states checked paths; matching hashes are byte-comparison observations only.
- WRITE_SET: common write set above.
- ACCEPTANCE: the tool never creates a baseline from current bytes and calls it historical proof. No runtime/provider import or write occurs.

## Interface and safety

Python standard library only. Intended command:

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/autonomous_state_audit/audit.py \
  --root /path/to/immutable/checkout \
  --control-state /path/to/control-state.json \
  --as-of 2026-09-17T18:34:33Z \
  --github-snapshot /path/to/github-observation.json \
  --protected-baseline /path/to/protected-hashes.json
```

Optional inputs omitted => corresponding UNKNOWN coverage, not an optimistic default. The auditor writes JSON to stdout only; caller-controlled redirection should be outside the inspected checkout. It does not use the system clock, execute Git, use network/provider calls, open SQLite, migrate files or select a canonical authority. Run against a quiescent immutable checkout: path checks are not a hostile-filesystem TOCTOU sandbox and cannot prove a multi-file live snapshot was atomic. Python startup/cache behavior outside this script is not a filesystem sandbox; use the shown environment setting.

GitHub snapshot schema: `amadeus-github-observation-1`, with `repository`, `observed_at`, `source_sha`, `branches` (ref-to-SHA object), and `pull_requests` (objects containing `url`, `head_ref`, `head_sha`, `state`). These are externally collected observations, not authenticated by this offline program. `source_sha` is declared, not independently bound to checkout bytes. More than one hour old or future-dated relative to `--as-of` => UNKNOWN. Missing rows never prove absence.

Protected manifest schema: `amadeus-protected-baseline-1`, with nonempty `files` list of `{path, sha256}`. Paths are repository-relative; baseline provenance/coverage must be reviewed separately.

Output is deterministic for identical input bytes and explicit time; it excludes wall-clock runtime, absolute workspace paths and random IDs. Findings are sorted. Exit 2 = CONFLICT, 3 = BLOCKED, 4 = UNKNOWN, 0 = OBSERVATIONS_ONLY. None is a product, semantic, billing or natural-day acceptance verdict. `semantic_acceptance`, `product_acceptance` and `replay_authorized` are always false. Findings may coexist; the highest-priority status does not discard other findings.

## Source anchors (inspected, not independently rerun)

All paths below are at baseline `34ae8a3d95dbe1cc565893b81306be235a36a4cb`, except PR #2 tests at `bbb99d73c80b77445ae9d1a5fa82ad4607ccbc69`:

- `AMADEUS_PERSONA_CORE_MASTER_GOAL.md` (blob `995d88b89ecd6fa10d201364ed32cc6e60a3ce0d`).
- `PERSONA_CORE_CONTINUATION_PROTOCOL.md` (blob `23a91d690e579ff8a80f954fc16c0077391c3c1e`).
- `PERSONA_CORE_PROGRESS.md` (blob `cbc0bd3c40c54a67f91c87a3b0d6595702b1bfdc`), marked G6 block and historical entries.
- `PERSONA_CORE_DECISION_LOG.md` (blob `5e5e6229793f0715e81e690fbbbc7d42d46c80f4`), locked decisions and DEC-G6-001..009. DEC-G6-002 retains the historical source-identity invalidation rather than rewriting it to PASS.
- `persona_core/operational_build_v1/TASK_STATE.json` (blob `22e4330bcf5325d3a9a4c40b4362cec612dace0b`).
- `persona_core/operational_build_v1/ACCEPTANCE_MATRIX.json` (blob `4b1c6855231069f0da27cc2ee3512937b9bb83f3`).
- `persona_core/operational_build_v1/tools/audit_operations_resume.py` (blob `b621ec4f2db36ec5125b3af654e7f8d3fe30f4b2`).
- `persona_core/operational_build_v1/tools/fault_recovery_matrix_r047.py` (blob `a70563f07cf602c5d82fde06b468ab5eb21b4469`) and its test (blob `cba2695b28ad38755c0d760bbe8f06696dca50e8`).
- PR #2 `tests/runtime_vnext/test_semantic_contract.py` (blob `f209eb06e80425bfcfaa9572c4e6671f1bccdd2f`).

## Verification limits and rollback

The container's direct git clone failed DNS resolution. This run may execute only newly materialized isolated auditor code and synthetic fixtures unless full source acquisition is explicitly recorded later. Do not describe that as a full checkout, original-evidence run, Windows validation, GitHub Actions run, provider evaluation or full repository regression.

C01 does not close HOLD-G6-07-CANONICAL, R005 provenance, semantic acceptance, external review, real days or production activation. Review PR #1/#2/#3 remains independent. No external paper's unverified metadata is used as implementation evidence.

Before merge, leave this additive branch unused or close its PR. After merge, use a new revert commit appropriate to the actual merge strategy; no force-push, historical deletion, database restore or UNKNOWN replay. Coordinate control-task disposition separately with current-blob CAS. Do not auto-merge.
