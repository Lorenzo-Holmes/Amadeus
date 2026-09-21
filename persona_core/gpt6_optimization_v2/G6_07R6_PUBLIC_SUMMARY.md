# G6-07R6: trusted semantic acceptance

Status: IMPLEMENTED / OFFLINE_VALIDATED / FROZEN_FOR_FRESH_VALIDATION.

The host now admits independently trusted typed inputs, validates proposed plans,
issues claim/exclusion/closure certificates, renders controlled Chinese answers,
and stores independent accepted-output records. Display, conversation history,
next-turn context, observed memory, evaluation, candidate creation, blind-package
inputs and review all select the accepted record in explicitly enabled sessions.
Provider bytes and visible raw answers remain separately identifiable audit data.

Authority comes from host program facts, explicit structured state, reviewed
source mappings and finite deterministic rules. Model-authored semantic labels
and source hashes alone grant no proof authority. Typed checks bind relation
domain, directed bridges, scope, modality, phase, responsibility and strength.
Strong closure needs an authenticated complete finite universe and checked member
partition. A provider draft that differs from the host realization is rebuilt.

The feature gate defaults to OFF. TRUSTED mode is explicitly enabled for new
sessions and cannot be silently changed. The additive persistence tables are
installed only for enabled sessions, preserving legacy database and backup
behavior. Restart reuses persisted accepted records without regeneration.

This milestone covers a bounded typed vertical slice. Ordinary free text remains
UNPARSED unless a host-owned adapter independently admits its meaning. The tiny
user-report grammar does not verify real-world completion. Naturalness was checked
on controlled fixture responses; general persona-conversation fluency and general
natural-language entailment have not been established.

## Offline validation

| Check | Result |
| --- | --- |
| New focused tests | 135/135 PASS |
| Full component suite | 732/732 PASS across 31 modules |
| Unmodified prior component baseline | 597/597 PASS across 30 modules |
| Fixed legacy suite | 43 modules, 450 checks; 449 compatible PASS, 1 expected historical source-identity sentinel, 0 unexpected failures |
| New authored scenarios | 36: 16 positive, 8 negative, 12 additional adversarial variants |
| Prior diagnostic pairs | 26 reused unchanged; 26 valid typed mappings allowed, 26 invalid strengthenings prevented |
| Over-conservatism | All 16 positive scenarios allowed, including inference, bridge, finite closure, responsibility, completion and conditions |
| Controlled naturalness | 16 automated fixtures and author text review of 42 examples; no internal enums or JSON in user output |

Diagnostic reuse relies on explicitly authored typed mappings. It is not evidence
of automatic parsing of the original free-language prompts. Legacy's expected
source-identity sentinel remains a raw failing check, retained with adjudication;
the legacy run is not reported as 450/450 PASS.

All test execution was offline under a non-loopback network guard. Provider
transport, routing, streaming and journal core were unchanged. Runtime semantic
acceptance and consumer sources changed; frozen Persona/Genesis sources did not.
Protected files (536), historical evidence members (1,987), journals (25), historic
UNKNOWN rows (7), historical findings and the spend ledger remain preserved.

## Freeze and next state

Freeze: TRUSTED_SEMANTIC_ACCEPTANCE_R14_20260920_01.

G6-07 remains VALIDATION_PENDING with FRESH_SEMANTIC_VALIDATION_REQUIRED.
The next fresh revision is READY_FOR_NEW_REVISION but has not been created:
0/44 captures and 0/176 judgments, with no inherited semantic PASS.
G6-08, G6-09, Candidate V2 and Blind remain LOCKED. Production is not activated.
Model generation, provider requests, readiness calls, validation campaign calls
and automatic paid retries are all zero in this milestone.

The public freeze file binds this publication's exact source, tests, architecture
and aggregate reports. The complete local source manifest binds 157 files.
Private captures, evaluation evidence, databases, credentials, hidden reasoning
and the spend ledger are excluded from this publication.
