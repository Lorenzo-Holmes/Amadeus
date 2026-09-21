# Governance V2.1 milestone

This directory publishes the public-safe policy/refactor report, R18 disposition,
tested source identity, construction-only acceptance config and public summary.

The full private test logs, raw captures, original source archive, historical
manifest, run receipt, canonical pointer and immutable recovery checkpoints stay
in the authorized local workspace. They are deliberately not published here.

The canonical resume command requires those local pinned files. A public-only
clone cannot infer execution readiness or recover private evidence from this
summary; it must fail closed rather than fabricate the missing checkpoint.

The tested source freeze is a byte-identity record, not paid execution authority.
R18 is permanently preserved. R18-N02-U01 remains unresolved, and no replacement
validation was authorized or executed in this task.

The governance utility is deliberately offline-only. Its replacement checker is
a diagnostic, not an automatic paid-allocation executor. Formal paid-runner
integration remains an explicit follow-on migration, not a shipped capability.

Read EXECUTIVE_AUDIT.md for the twelve deliverables and the A–E conclusions.
Read MIGRATION_PLAN.md for exact changes and the explicitly deferred compatibility
migration of the four legacy machine-state writers/consumers.
