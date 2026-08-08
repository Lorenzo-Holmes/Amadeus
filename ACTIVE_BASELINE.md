# Active baseline

## Current authority and project identity

[FRAME] The strongest contrary condition is snapshot scope: `FINAL_VERIFIED` applies to the exact M4.3-R4 product snapshot, not to every Amadeus milestone and not to this synchronized status document.
CONFIDENCE: HIGH

[KNOWN] Gate C is complete. The formal current project is `Amadeus-Project.staging`, and its active Git repository is `active/` on branch `codex/stage0c-fixture-conversion`.
CONFIDENCE: HIGH

[FRAME] Route/source B is the active engineering line. Route/source A remains historical design and Stage0A evidence; it does not override the active Route B line.
CONFIDENCE: HIGH

## M4.3-R4 verified product snapshot

[COMPUTED] Packet `M4.3-R4-REVIEW-20260808` is `FINAL_VERIFIED` at `review_epoch=0`: the Final Gate collected 1647 nodes and recorded 1645 passed, 2 skipped, and 0 failed. The evidence entry is `../tasks/M4.3-R4-REVIEW-20260808.md`.
CONFIDENCE: HIGH

[COMPUTED] `verified_product_snapshot` is branch `codex/stage0c-fixture-conversion`, parent HEAD `85f9d3ed2c8e37eb68a4cdfb6e9d11b56cd69e2e`, dirty manifest `71/79EA2F6C2E9E869AE2463D2110008EEF5556CFCAFD2917146A1FB69A9791D15C`, dirty path manifest `71/D18CFE2CB3AA459C4459EA3920BACDBE7E509B6DB4B072E38B860CACE6894A94`, and workspace manifest `253/DE35171067ADD7315E416509F2ACF631FC915D495CF75798A0FEB5D3F19B8EB6`.
CONFIDENCE: HIGH

[COMPUTED] The preserved ownership hashes are `tests/integration/stage0c_case_loader.py=9FB98DC5D80AB58A0DE33A9CADD2F06A22F4C9B72937D77011021E133F8945A7`, `tests/integration/test_b01_m4_governance_slice.py=1FED3DC8A1383C39A14BB109A0BF5A92312DF12E7E60D73E1459B99E065CE73A`, and `tests/storage/test_unit_of_work.py=ADCB4CE7F40C421EADBA79576583BCA268519487DC9EBFA147873A55B8E2A2A4`.
CONFIDENCE: HIGH

## Local checkpoint snapshot

[FRAME] `checkpoint_snapshot` is the tree of the single local commit that contains this file, whose parent is `85f9d3ed2c8e37eb68a4cdfb6e9d11b56cd69e2e`. Its product files are byte-identical to `verified_product_snapshot`; the only post-gate active-repository content delta is this permitted `ACTIVE_BASELINE.md` metadata synchronization. The externally computed exact commit SHA is recorded in `../CURRENT_STATE.md`, `../README.md`, and `../SOURCE_INDEX.md` after the commit exists.
CONFIDENCE: HIGH

[KNOWN] The Final Gate did not review this synchronized documentation. This metadata-only checkpoint does not claim a new product review, an intelligence-capability advance, or completion of all Amadeus work; the product review remains bound to `review_epoch=0` and the exact verified product snapshot above.
CONFIDENCE: HIGH

[KNOWN] The local repository has zero remotes. GitHub synchronization status is `PENDING_REMOTE_CONFIGURATION`; the checkpoint is not pushed or released.
CONFIDENCE: HIGH

## Engineering frontier

[FRAME] The engineering frontier remains Route B M5, specifically M5.2a3 P3. P1 and P2 artifacts and prior gate evidence exist; P3 runtime and its tests remain pending implementation, and P4 with the full B02 conversion follows only after P3 closure.
CONFIDENCE: HIGH

[KNOWN] `outputs/M5.2a3-ViewBuilder-契约闭合提案-2026-08-06.md` defines the P1→P2→P3→P4 dependency order. `outputs/M5.2a3-P3-runtime-contract-amendment-2026-08-06.md` remains a proposed amendment with `P3_RUNTIME_STATUS=NOT_AUTHORIZED`; it records P3 runtime/tests and reviewed AC-031/032 B02 fixtures as remaining work.
CONFIDENCE: HIGH

[FRAME] The recommended next single phase after this checkpoint is `AMAD-GOV-OPT-01`; starting it requires a fresh snapshot and TaskPacket.
CONFIDENCE: HIGH

## Retained historical evidence

[KNOWN] Gate C/M4.2, M4.3 B01, M4.4 attack review, and M5.2a2 retain their historical evidence in the corresponding validation outputs. Their earlier dirty-worktree wording is historical and is superseded for current Git state by this local checkpoint record.
CONFIDENCE: HIGH

[UNKNOWN] Execution evidence for the two FIFO-specific nodes on a platform with `os.mkfifo` remains absent.
CONFIDENCE: HIGH

[FRAME] [我打破的规则 / RULES I BROKE]：无。
CONFIDENCE: HIGH
