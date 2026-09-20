# Migration / Rollback Contract

Version: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`. Migration is forward-only for new explicit session policies. P1 performs no runtime/database migration. P2 works in isolated new stores and retains the old source and all old evidence.

## R6/R7 mechanism disposition

| Classification | Exact mechanism / application rule | Frozen disposition |
|---|---|---|
| KEEP_UNCHANGED | R6 finite proof types, scoped validator, claim/exclusion/closure certificates and strict renderer | Retain their bounded guarantees and existing tests; no ontology expansion |
| KEEP_UNCHANGED | Raw capture, immutable raw/accepted records and tamper checks | Retain exact old bytes and interpretations; new records are additive and versioned |
| KEEP_UNCHANGED | Host EvidenceToken, AdmissionDecision, atomic RuntimeStore.commit, idempotency and legal reducers | Same allowed effects and evidence requirements; no new permissions/writers |
| KEEP_UNCHANGED | R7 source-policy-provider identity binding, formal dataset/rubric provenance and no retry/UNKNOWN recovery | Preserve checks and historical identity; add an explicit new policy branch rather than weakening the old one |
| KEEP_BUT_NARROW_SCOPE | Consumer binding and meaning of accepted text | Bind the correct purpose: displayed dialogue versus policy-certified claim versus admitted event; preserve cross-consumer consistency |
| KEEP_BUT_NARROW_SCOPE | Fail-closed presentation rule | Continue integrity/privacy/truthful action boundaries; pure lack of semantic coverage alone is not a conversation block |
| ROUTE_TO_STATE_ONLY | Event admission and effect authorization as a prerequisite for changing memory/facts/relationship/execution | Required for effects; not a prerequisite for every ordinary sentence to be spoken |
| ROUTE_TO_HIGH_AUTHORITY_ONLY | Universal proposed typed-plan request, strict certificate rendering before display | Required only for the selected supported bounded claim path; ordinary conversation is separately checked |
| ROUTE_TO_HIGH_AUTHORITY_ONLY | Exclusion/closure proof | Trigger on a certified finite exclusion/exhaustiveness assertion or an effect that depends on it; open hypothesis discussion remains possible |
| AUDIT_ONLY | Raw/accepted differences and semantic-coverage counters | Diagnostic lineage; a transformation or UNPARSED flag alone cannot establish raw semantic violation or task success |
| DEPRECATE_APPLICATION_RULE | All formal conversational responses must be fully typed and rendered before any display | Replaced prospectively by DISPLAY_ELIGIBILITY plus independent STATE_ADMISSION |
| DEPRECATE_APPLICATION_RULE | All consumer purposes inherit one undifferentiated TRUSTED accepted authority | Replaced prospectively by the 14-consumer matrix, preserving legacy policy readers |
| DEPRECATE_APPLICATION_RULE | Every UNPARSED is a semantic error; generic fallback implies safe/useful/natural PASS | Coverage, semantic review and utility remain separate; historical records are retained, not rewritten |
| REMOVE_CODE | None authorized | No code deletion is justified by this contract; removing an application requirement does not mean removing its module |

## Policy and record migration

1. Before P2 edits, capture an exact pre-P2 source/manifest snapshot and verify the original 163-member R7 freeze remains readable. Register all proposed changed files and P2 contract/routing hashes. Keep the original source freeze ID; create a new one for new code only after relevant validation.
2. Define a new explicit bounded session policy and record schema distinct from OFF and TRUSTED v1. The display policy purpose, optional bounded-claim acceptance and event state admission must be distinct and immutable for a session. Policy selection comes from host configuration, never text or benchmark membership.
3. Use a new isolated database/session for the new policy. Add immutable displayed lineage and policy-scoped acceptance without changing `turns.assistant_text` raw meaning, old accepted rows or old policy bindings. Bind raw, selected candidate, display acknowledgment, source/context/policy and state refs before consumers use them.
4. Preserve existing OFF/TRUSTED sessions under their recorded source/policy. Never re-sign old accepted records with the new runtime hash. If current loaders reject their old source identity, inspect with the verified original frozen reader in a read-only isolated context. Do not add a permissive “ignore hash” compatibility switch.
5. Migration of historical sessions into the new policy is NOT approved. If later needed, a separate reviewed export/import must retain source bytes and create explicit new identities; it cannot rewrite the R12–R15 evidence or promote old text. New clean conversation state does not inherit evaluation history.
6. Keep proposed/HOLD/REJECT decisions append-only. New evidence requiring reconsideration creates a separately identified candidate/decision with a supersedes link; do not mutate a previously sealed HOLD into ADMIT. P2 does not introduce an automatic retry or a new admission feature for this purpose.
7. Freeze consumer projection and evaluator schema together. Legacy exports retain legacy semantics. Missing or incompatible new records fail explicitly; no fallback to raw. Dual-gate evaluation starts as NOT_RUN and never inherits a historical PASS.

## Rollback triggers

Rollback the affected P2 candidate for a display/history mismatch, unexpected authority promotion, missing observation/commit lineage, unexpected regression, entity/privacy leak, source corruption, inability to read the pinned policy, changed historical bytes, or an allowlist escape. Ordinary newly discovered requirements go back to reconciliation rather than being patched outside scope.

## Rollback procedure

1. Stop the new isolated candidate's local execution. P2/P3 have zero provider authorization; do not invoke readiness or remote recovery to diagnose it. If an unexpected external side effect exists, preserve its actual state and stop that branch rather than claiming it undone.
2. Preserve the new-policy records, logs, source diff and failure as a quarantined evidence package. Do not delete or relabel them as legacy data. Preserve the current reconciliation contract; source rollback does not silently repeal an adopted architecture decision.
3. Restore only the explicitly changed allowlisted source files from the checked pre-P2 snapshot, or select the original frozen source in a separate read-only inspection context. Verify their exact hashes. Avoid a broad workspace reset that could overwrite unrelated user work.
4. Restore an isolated pre-P2 database snapshot into a different recovery location if needed. Never delete new committed evidence or write it into an old store. Do not run an older binary on a new schema and let it guess; unsupported policy/schema must reject. Historic stores remain untouched throughout.
5. Validate source hashes, raw/accepted immutability, original dataset and R12–R15 hashes, and old policy identity. Verify that no provider call, duplicate receipt or redisplay occurred. Run only the relevant rollback/compatibility checks on copies.
6. Append rollback evidence and mark the new implementation unavailable, with G6-07 still REPAIR/VALIDATION_PENDING and G6-08 LOCKED. P1's adopted contract remains a target; if the contract itself must change, use a new append-only architecture decision. Resume P2 only under the recorded safe scope.

No step edits historical verdicts, request outcomes, journals, spend ledgers, Persona/Genesis or original raw/accepted captures. A valid new commit receipt proves only its exact event/effect; rollback cannot assert an external action was undone merely because code was reverted.
