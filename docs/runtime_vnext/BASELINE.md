# Amadeus runtime vNext — GitHub baseline and discrepancy record

Recorded: 2026-09-18. Scope: the connected GitHub repository, not the Windows staging filesystem.

## Verified repository facts

Repository: `Lorenzo-Holmes/Amadeus` (public). Default branch: `main`.

| Ref observed before this work | Commit |
|---|---|
| `main` | `a6ffaa388ebdab03620070c3990ffc9788425e8f` |
| `codex/project-kb-stage0b-bootstrap` | `a6ffaa388ebdab03620070c3990ffc9788425e8f` |
| `codex/persona-core-operations-v1-20260917` | `34ae8a3d95dbe1cc565893b81306be235a36a4cb` |
| `codex/stage0c-fixture-conversion` | `ccdda518c6aa87174a66b058940f178a0f881d8f` |
| `aster01-gptimage2-bridge` | `b47e6698b1d66b8d71014a14c9567eca003a7714` |

The selected **public-source inspection baseline** is `34ae8a3d95dbe1cc565893b81306be235a36a4cb`, tree `f2bcd2fd85db2a6e4bb82a4ca04e2b5adef1ecd7`. It is the observed head of the Persona Core snapshot branch, with parent `a6ffaa388ebdab03620070c3990ffc9788425e8f`. Its commit message is `Add Persona Core operations v1 runtime and validation snapshot`, dated 2026-09-17T13:54:25Z. The main head is dated 2026-08-31T07:23:06Z, message `assets: add qualified texture and image archive`; its preceding commit is `83455dc4fda8b91cfe6c4f5b7f46f5cae0acf961` (`assets: publish previous generated textures`).

New branch: `feat/amadeus-runtime-vnext-foundation`, created from the selected immutable commit. The intended PR base is the existing Persona Core snapshot branch, **not main**, so this PR does not present the entire historical snapshot as newly authored work. No merge is authorized.

## Critical discrepancy: this is NOT the verified G6 canonical baseline

The user identifies `APCORE-GPT6-OPTIMIZATION-V2`, canonical directory `persona_core/gpt6_optimization_v2/`, and the following expected local state:

```text
phase=WAITING_PROVIDER_OUTCOME_WITH_SEMANTIC_REPAIR_PENDING
LAST_COMPLETED=G6-06
ACTIVE_TASK=G6-07
BUILD_SCOPE_COMPLETE_VALIDATION_PENDING=false
GPT6_CORE_BUILD_COMPLETE_VALIDATION_PENDING=false
PRODUCT_ACCEPTANCE_COMPLETE=false
production_activated=false
```

These are user-provided expectations, **not verified local facts**. The Windows workspace `C:\Users\skr\Documents\Codex\Amadeus-Project.staging` has not been accessed in this work.

The selected GitHub commit's complete, non-recursive `persona_core` tree does **not** contain `gpt6_optimization_v2`. The contents lookup for that directory returned 404. Do not fabricate this directory or a replacement canonical state file.

The root `PERSONA_CORE_PROGRESS.md` does contain a newer G6 header: `LAST_COMPLETED: G6-06`, `CURRENT_STATE: GPT6_PARTIAL_REVIEW_BOUND_CAPABILITY_REPAIR_IN_PROGRESS`. It records revision07 partial review and an unresolved `N06_T4`, with instructions not to replay it. This is a **documented checkpoint**, not an independently revalidated runtime ledger or provider outcome. The local canonical phase expected by the user and the published progress header differ.

In contrast, `persona_core/README.md` still describes `APCORE-OPERATIONS-V1` and `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`. Its historical completion statement is not inherited. It explicitly says raw provider captures, SQLite runtime databases, reviewer returns, recovery archives and natural-day checkpoints were excluded from the public snapshot.

## Scope decision recorded before implementation

Proceed with source-grounded architecture, an isolated offline semantic contract reference, and its synthetic tests. Do not change the operational runtime, source/Genesis bytes, existing state records, provider submission behavior, release status, or production activation. Do not claim R8-N02-01 or R8-N06-01 reproduced or repaired: their current canonical implementation and raw evidence are unavailable here.

The reference is not a new Persona Core, not a production parser, not a state writer, and not a replacement for the existing AdmissionController. Production integration remains gated on reconciliation with the actual G6 canonical source and evidence.

For every `SUBMITTED_STATUS_UNKNOWN` request: preserve the original record; no resubmission, automatic retry, fallback replay, new-ID bypass, or inference that a missing response means unsent. This task performs no project provider calls.

## Reproducible source evidence

Use immutable commit links, not branch names, to reproduce these observations:

- [Selected commit](https://github.com/Lorenzo-Holmes/Amadeus/commit/34ae8a3d95dbe1cc565893b81306be235a36a4cb)
- [Parent/main checkpoint](https://github.com/Lorenzo-Holmes/Amadeus/commit/a6ffaa388ebdab03620070c3990ffc9788425e8f)
- [Complete persona_core child tree](https://api.github.com/repos/Lorenzo-Holmes/Amadeus/git/trees/314cabd3c1ee138c849e718064480a9a1964d620)
- [G6 progress header](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/PERSONA_CORE_PROGRESS.md)
- [Public snapshot exclusions and stale status](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/README.md)

A container `git clone` attempt failed because github.com DNS resolution was unavailable. It did not produce a checkout. Source inspection and GitHub writes use the connected GitHub API. Any local test result must state precisely which authored files were materialized and tested; it is not a full repository regression.
