# P1 Acceptance Checklist

Task: `G6-07-ARCHITECTURE-RECONCILIATION-P1`. Result: **P1 COMPLETE / ARCHITECTURE CONTRACT ADOPTED**.

This checklist distinguishes static contract completeness, actual byte-preservation checks and adoption bookkeeping from future behavioral validation. Review method: primary-agent local contract review plus deterministic structural/hash checks; not an independent reviewer or target-model experiment.

| Requirement | Result | Evidence / scope |
|---|---|---|
| Canonical Guide alignment | PASS | Guide §§0–20, 25–28, 32, 35–36; ARCHITECTURE_DECISION.md; no Master Goal mission conflict |
| Conversation / Trusted State responsibilities | FROZEN | ARCHITECTURE_DECISION.md |
| DISPLAY_ELIGIBILITY | FROZEN | DISPLAY_STATE_ADMISSION_CONTRACT.md; explicit mode/policy/schema and boundaries |
| STATE_ADMISSION | FROZEN | DISPLAY_STATE_ADMISSION_CONTRACT.md; host evidence/decision/commit kept separate |
| UNPARSED behavior | FROZEN | UNPARSED_BEHAVIOR_CONTRACT.md; no universal block or raw bypass |
| Authority Ladder | 6 / 6 COMPLETE | AUTHORITY_LADDER.md/.json; all eleven usage/evidence questions plus existing mappings |
| Mechanism placement | 14 / 14 COMPLETE | MECHANISM_PLACEMENT_MATRIX.md/.json |
| Consumer mapping | 14 / 14 COMPLETE | CONSUMER_AUTHORITY_MATRIX.md/.json; seven inputs each |
| External44 criterion routing | 176 / 176 COMPLETE | 44 original turns × four unchanged criterion strings; 44 Conversation-only, 132 BOTH, 0 N/A |
| Benchmark leakage audit | PASS | BENCHMARK_LEAKAGE_AUDIT.json; field projection, private fragment/secret scan and manual contract review |
| G6-07 Conversation Utility Gate | DEFINED | G6_07_DUAL_GATE_SPEC.md; NOT_RUN on new contract |
| G6-07 State Integrity Gate | DEFINED | G6_07_DUAL_GATE_SPEC.md; NOT_RUN on new contract |
| P2 exact allowlist | 14 exact paths COMPLETE | 8 runtime, 4 direct validation adapters, 2 new tests; no wildcards |
| Migration | COMPLETE | MIGRATION_ROLLBACK_PLAN.md; explicit new policy, no implicit legacy conversion |
| Rollback | COMPLETE | MIGRATION_ROLLBACK_PLAN.md; scoped source restore and quarantine, no history deletion |
| Finite paired validation contract | 24 cases DEFINED | Eight paired families plus eight edge cases; execution NOT_RUN |
| Historical R12–R15 and journals | UNCHANGED | Actual start/end hash comparison; PROTECTED_INTEGRITY_AUDIT.json |
| Runtime source | UNCHANGED | 39 runtime files unchanged; existing source manifest 163 / 163 MATCH |
| Provider / readiness / paid / generation requests | 0 / 0 / 0 / 0 | P1 work imports no runtime or provider and invokes none; Git publication is separately authorized |
| Decision Log | APPENDED | ADR-P1-20260920; original prefix preserved byte-for-byte |
| Canonical adoption | APPENDED / ADOPTED | Guide §38; original prefix and audit wording preserved |
| Machine state reconciliation | PASS | Four current G6 JSON files plus root/runbook mirrors; full prior snapshots retained privately |
| Downstream and session boundary | SAFE STOP | G6-07 REPAIR; G6-08 LOCKED; P2 next session only; no new validation revision |

Protected unique files: 2764. Counts overlap: 163 frozen source members, 39 runtime files, 233 files in the named R12–R15 artifact directories, 2,215 earlier historical members, 536 protected members, 7 Persona members, 26 journal files, 4 dataset files and the spend ledger. They are not summed as separate unique files. All compared hashes match the P1 start baseline.

Original R15 verdict remains FAIL with 3 PASS / 1 FAIL / 172 UNREVIEWED. P1 does not close historical semantic findings, pass G6-07, change product acceptance or activate production. The only next phase is P2 — Minimal Boundary Repair in the next session.
