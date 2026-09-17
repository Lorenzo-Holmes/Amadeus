# Amadeus Persona Core

This directory contains the public-safe implementation snapshot for `APCORE-OPERATIONS-V1`.

Included here are the operational runtime, frozen/installed runtime baseline needed to open an isolated candidate, build and validation contracts, and the tooling used to reproduce the engineering gates.

The local development workspace intentionally contains additional evidence that is **not** published to the public repository: provider raw captures, SQLite runtime databases, reviewer-return packages, recovery archives, natural-day checkpoints, and other generated evidence under `operational_build_v1/evidence/`. Those artifacts can contain local runtime history and are not required as source code.

Canonical local status at the time of this snapshot is recorded in:

- `operational_build_v1/TASK_STATE.json`
- `operational_build_v1/ACCEPTANCE_MATRIX.json`
- the root `PERSONA_CORE_PROGRESS.md`

The current engineering state is `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`; this is not the same as `PRODUCT_ACCEPTANCE_COMPLETE`.

