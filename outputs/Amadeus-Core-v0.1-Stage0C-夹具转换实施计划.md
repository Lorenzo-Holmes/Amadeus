# Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [FRAME｜置信度：高] 把冻结的 259 个 Stage 0B clause 逐项转换为 259 个 reviewed fixture case，构建 exact-field DSL、静态 handler registry、hermetic S sandbox、可恢复 deterministic publication、smoke verification evidence，以及 `checklist/write/check/verify-harness` CLI；不运行真实 Core conformance，不生成 catalog，不声明 release ready。

**Architecture:** [FRAME｜置信度：高] `fixtures/stage0c/reviewed/cases/*.json` 是唯一人工维护的 Stage 0C 内容输入；编译器只消费冻结 Stage 0B manifest/report、reviewed case 与静态代码合同，在内存构建 schema、handler manifest、smoke matrix、259 个 generated case、binding manifest 和 report，再通过带 journal 的 publication 层发布 exact 265-file tree。S sandbox 只执行受信任的静态 handler，以 fresh context、fake driver/adapter、固定 clock/ID、effect allowlist、receipt/diff/assertion/cleanup 生命周期产生可复核结果；独立 `verify-harness` 从 canonical smoke matrix 实际执行 registry/harness 并原子写 evidence。

**Tech Stack:** [KNOWN｜置信度：高] Python 3.12、标准库 `argparse/dataclasses/hashlib/json/os/pathlib/re/shutil/tempfile/typing/uuid`、pytest 7.4+、canonical JSON、SHA-256、Windows/POSIX 文件语义、PowerShell、Git。

---

> [KNOWN｜置信度：高] 状态：Frozen。
> [KNOWN｜置信度：高] 唯一规格：`outputs/Amadeus-Core-v0.1-Stage0C-夹具转换设计.md` Frozen 版本。
> [KNOWN｜置信度：高] 本计划不修改冻结设计的边界、计数、readiness 语义、恢复矩阵或 hash preimage。

## 0. 反方边界

[INFERRED｜置信度：高] 最大实施风险不是代码量，而是“部分 reviewed case、部分 generated 文件、被 mock 的 smoke 结果”形成假绿。259 个 reviewed conversion 必须按 exact clause set 分批转换并复核；generated tree 只能在 exact 259-case closure、静态 handler、publication 与 smoke matrix 都成立后一次性发布。

[FRAME｜置信度：高] 以下状态必须始终分离：

1. case definition 可解析；
2. clause→case binding 完整；
3. trusted fixture harness contract ready；
4. trusted fixture harness smoke verified；
5. 98 个 S case 已执行；
6. 259 个 case 已在真实 Core 上执行；
7. catalog ready；
8. release ready。

[FRAME｜置信度：高] Stage 0C 只允许完成前四项。`verify-harness` 的成功不能改写 `s_case_execution_complete=false`、`case_execution_complete=false`、`core_behavior_verified=false`、`core_case_execution_coverage_complete=false`、`catalog_ready=false` 或 `release_ready=false`。

## 1. 冻结输入

| 输入 | [COMPUTED] SHA-256 | [COMPUTED] 字节数 |
|---|---:|---:|
| `fixtures/stage0b/generated/source_clause_manifest_v0_1.json` | `DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C` | 252478 |
| `fixtures/stage0b/generated/stage0b_report_v0_1.json` | `F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8` | 585 |
| `outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md` | `3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695` | 79488 |
| `outputs/ADR-004-Amadeus工具权限与执行治理.md` | `2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125` | 25191 |

[COMPUTED｜置信度：高] 冻结 manifest 包含 214 sources、259 clauses、75 个 S sources、98 个 S clauses、51 个需要 H 或 J 的 clauses，以及 55 个 H/J oracle requirements。

[FRAME｜置信度：高] 任一 path、size、SHA-256、schema、source/clause set、内部计数或 binding 漂移都必须阻断 `checklist/write/check/verify-harness`。后两份 Markdown 只作 envelope provenance；工具不重新解析 Markdown 推断 schema 或 clause。

## 2. 完成定义

- [ ] [FRAME] 四份冻结输入的 path、size、SHA-256、schema 与内部计数逐值一致。
- [ ] [FRAME] `conversion_checklist_v0_1.json` 精确覆盖 259 clauses，按 frozen manifest 顺序分为 B01–B12 各 20 项、B13 为 19 项。
- [ ] [FRAME] 259 个 reviewed files 的 clause ID、case ID、文件路径与 frozen clause set 一一对应；无 missing、duplicate、unexpected。
- [ ] [FRAME] 每个 reviewed file 的 top-level fields 精确等于 Frozen 设计列出的字段；完整保留 Stage 0B frozen identity、case body、stimulus mapping、oracle mapping、reviewer 与来源特定 rationale，不增加 author、设计外审计对象或派生 hash 字段。
- [ ] [FRAME] 独立 reviewer 逐项证明 Stage 0B `stimulus_scope` 映射到具体 stimulus handler/params JSON pointers，并证明 `expected_scope` 映射到具体 machine assertion 或 rubric requirement；转换 author 与 reviewer 的角色分离记录在 13 个 tracked batch review records，reviewed JSON 只保存 Frozen `reviewer` object。
- [ ] [FRAME] D/S required oracle 各有可解析 machine assertion mapping；H/J required oracle 各有 rubric mapping，且不含 verdict。
- [ ] [FRAME] AC-001#1 golden example 逐字段符合 Frozen 设计。
- [ ] [FRAME] fixture case schema 覆盖所有 structural object、handler params、envelope、result、receipt、effect、patch、run result，并对 structural object 使用 `additionalProperties=false`。
- [ ] [FRAME] 静态 registry 精确包含 5 个 setup、4 个 stimulus、9 个 assertion handler；JSON 不接受 import path、模块名、表达式、脚本或动态函数目标。
- [ ] [FRAME] 每个 S run 使用 fresh context，并执行 reset→setup→before snapshot→stimulus→receipt→after snapshot/effect diff→assertion→cleanup。
- [ ] [FRAME] fake driver/adapter 不访问真实网络、不发送消息、不发起支付、不写项目目录；effect allowlist 与 state patch 按冻结事务规则执行。
- [ ] [FRAME] replay address、request hash、result consumption、conflict、receipt、cleanup 和 PrimaryError phase 与 Frozen 设计逐值一致。
- [ ] [FRAME] publication lock、journal、staging、backup、temp、publish order、恢复矩阵与 corruption/residual 规则均有 fault-injection 测试。
- [ ] [FRAME] generated tree 精确为 259 cases + 6 top-level artifacts = 265 files；递归 exact path set 与 bytes 可比较。
- [ ] [FRAME] 连续两次 `write` 的每个文件 hash 与 tree hash 不变；`check` 前后全体文件字节与 Git 状态不变。
- [ ] [FRAME] smoke matrix 对每个 handler 至少有一条 valid 和 invalid probe，并覆盖 completed/failed/unknown、effect 越界、合法 replay、replay conflict、setup/stimulus/assertion/cleanup failure 与完整 publication interruption matrix。
- [ ] [FRAME] smoke evidence 由实际 registry/harness 执行产生；events、outcomes、result hashes 与三个 provenance hashes 可独立重算。
- [ ] [FRAME] 四个 CLI verbs 对任一冻结输入漂移都非零退出；`write/check/verify-harness` 对第二进程持锁均返回 `publication_busy`，lock carrier 始终为零字节。
- [ ] [FRAME] Stage 0C report 只声明 DSL、binding、definition coverage 与 trusted harness contract ready；真实 S/Core execution、catalog、release 继续为 false。
- [ ] [FRAME] Stage 0A、Stage 0B、project KB、repository checkout contract 与全套 pytest 回归全绿。
- [ ] [FRAME] 每个叶级节点只包含其明确文件，红灯不提交，reviewed 未复核不提交，generated 不手改。

## 3. 文件职责

```text
.gitattributes
pyproject.toml
fixtures/stage0c/
  .stage0c-write.lock
  reviewed/
    cases/
      case-{normalized-source-id}-{clause-number}.json
  generated/
    conversion_checklist_v0_1.json
    fixture_case_schema_v0_1.json
    sandbox_handler_manifest_v0_1.json
    harness_smoke_test_matrix_v0_1.json
    case_binding_manifest_v0_1.json
    stage0c_report_v0_1.json
    cases/
      case-{normalized-source-id}-{clause-number}.json
tools/stage0c_fixtures/
  __init__.py
  constants.py
  types.py
  io.py
  checklist.py
  dsl.py
  schema.py
  reviewed.py
  compiler.py
  handlers.py
  sandbox.py
  publication.py
  smoke_matrix.py
  verification.py
  cli.py
tests/stage0c/
  conftest.py
  test_import_contract.py
  test_io.py
  test_inputs.py
  test_checklist.py
  test_dsl.py
  test_envelopes.py
  test_schema.py
  test_handler_params_schema.py
  test_reviewed.py
  test_compiler.py
  test_current_reviewed.py
  test_current_generated.py
  test_handlers.py
  test_sandbox_context.py
  test_sandbox_drivers.py
  test_sandbox_transactions.py
  test_sandbox_runner.py
  test_sandbox_assertions.py
  test_sandbox_replay.py
  test_sandbox_cleanup.py
  test_publication_journal.py
  test_publication.py
  test_publication_recovery.py
  test_handler_manifest.py
  test_smoke_matrix.py
  test_harness_verification.py
  test_cli.py
  reviewed_batches/
    test_batch_B01.py
    test_batch_B02.py
    test_batch_B03.py
    test_batch_B04.py
    test_batch_B05.py
    test_batch_B06.py
    test_batch_B07.py
    test_batch_B08.py
    test_batch_B09.py
    test_batch_B10.py
    test_batch_B11.py
    test_batch_B12.py
    test_batch_B13.py
    test_audit_B01.py
    test_audit_B02.py
    test_audit_B03.py
    test_audit_B04.py
    test_audit_B05.py
    test_audit_B06.py
    test_audit_B07.py
    test_audit_B08.py
    test_audit_B09.py
    test_audit_B10.py
    test_audit_B11.py
    test_audit_B12.py
    test_audit_B13.py
  test_batch_review_records.py
outputs/verification/
  stage0c-reviewed-batches/
    B01.json ... B13.json
  Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json
outputs/
  Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md
  Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md
```

[FRAME｜置信度：高] `schema.py` 负责生成与验证 JSON Schema；`handlers.py` 负责静态 registry 与 typed handler；`sandbox.py` 负责 context、driver、dispatch、receipt、assertion 与 cleanup；`publication.py` 负责锁、journal、publish、check 与 recovery；这些职责不得合并成一个不可独立测试的大文件。

## 4. 依赖图与并行边界

```text
P00
 └─ F01 → F02
           ├─ F03 → F04 ───────────────┬─ B01–B13 → F10
           │                            └──────────────→ C01
           ├─ F05 → F06 → F07 → F08 ──┬─ B01–B13
           │                 └→ F09 ───┼──────────────→ C01
           │                    │      └──────────────→ M01
           │                    └─────────────────────→ M01
           ├─ R01 → R02 → R03 → R04 → R05 → R06 → R07 → R08
           └─ P01 → P02 → P03

F07 + F09 + R08 + P03 → M01
M01 + P03 → M02
F04 + F09 + F10 + M01 + M02 + P03 → C01
C01 + R08 + P03 + M02 → V00
V00 → L01
L01 → V01 〔此后 tools/**/*.py 冻结〕
V01 → Q01 → D01
```

[FRAME｜置信度：高] B01–B13、R01–R08、P01–P03 是三个主要并行支线。B01–B13 可以由不同转换者在独立分支并行准备，但转换者不得填写最终 reviewer 身份；第二角色完成逐项复核后才写 reviewer；每批先由单一 integrator 建立 data commit，再以该 commit ID 建立 tracked audit record 与 audit commit，并按 B01 data→B01 audit→…→B13 data→B13 audit 串行合入。

[FRAME｜置信度：高] `schema.py`、`compiler.py`、`handlers.py`、`sandbox.py`、`publication.py`、`verification.py`、`cli.py` 是共享文件，只允许单一 integrator 串行修改；并行 worker 只创建分配给自己的 reviewed JSON 与唯一 batch test。F07 与 F09 均是 M01 的显式前置，F04 同时是全部 batch 与 C01 的显式前置。V01 生成 evidence 后禁止再修改任何 `tools/**/*.py`；若 Q01 发现工具缺陷，删除旧 evidence，回到对应代码节点修正，再依次重跑 M01→M02→C01→V00→L01→V01→Q01。

## 5. 统一叶级 TDD 与 Git 协议

[FRAME｜置信度：高] 每个代码节点采用下列循环：

1. 新增一个只描述当前行为的失败测试。
2. 只运行该 test node，确认失败原因和 expected failure 精确一致。
3. 写使该测试通过的最小实现。
4. 重跑该 test node 至 PASS。
5. 运行所属测试文件。
6. 删除重复实现或收紧命名，不改变外部合同。
7. 再次运行所属测试文件和 `git diff --check`。
8. 使用显式文件列表暂存；运行 `git diff --cached --check` 和 `git diff --cached --stat`。
9. 创建本任务指定 commit；确认 `git status --short` 只显示后续任务的预期改动或为空。
10. 把该 commit 推送到当前 `origin` 分支，并逐字验证 remote SHA 等于 local HEAD：

```powershell
$branch = (git branch --show-current).Trim()
if (-not $branch) { throw 'node push requires a named branch' }
git push origin ("HEAD:refs/heads/" + $branch)
if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
$localHead = (git rev-parse HEAD).Trim()
$remoteLine = @(git ls-remote --heads origin ("refs/heads/" + $branch))
if ($LASTEXITCODE -ne 0 -or $remoteLine.Count -ne 1) {
  throw 'remote branch verification failed'
}
$remoteHead = ($remoteLine[0] -split '\s+')[0]
if ($localHead -cne $remoteHead) { throw 'remote SHA differs from local HEAD' }
```

[FRAME｜置信度：高] push 验证是每个节点完成条件的一部分；未验证 remote SHA 的 local commit 仍视为未完成节点。不得用 force-push 改写 batch audit record 引用的历史。

[FRAME｜置信度：高] 禁止以下假绿：

- 不以 `skip`、`xfail`、宽泛异常捕获或删测试表示未实现能力。
- 不在 exact set 门禁中只检查计数。
- 不把 synthetic compiler test 结果冒充 current reviewed closure。
- 不把预填 result/evidence 交给 `verify-harness`。
- 不让 `check` 修复 publication residual 或改写任何文件。
- 不直接编辑 `fixtures/stage0c/generated/` 或 smoke evidence。
- 不在 reviewed case 的第二角色复核完成前提交 reviewer 字段。
- 不把 H/J rubric requirement 解释为 H/J verdict。

## 6. 实施任务

### Task P00：独立计划审查、两文档冻结与 KB 32→34

**Files:**
- Existing and finalize first: `outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md`
- Create and finalize first: `outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md`
- Modify after the plan and review bytes are final, before README/navigation: `tests/project_kb/test_current_repository.py`
- Modify only after the exact 32→34 RED is proven; finalize before hashing: `README.md`
- Modify only after the exact 32→34 RED is proven; finalize before hashing: `knowledge/data_structure.md`
- Modify last, after all four final document hashes are computed: `knowledge/manifest.json`

[FRAME｜置信度：高] P00 的最终新增文档精确为实施计划与独立计划审查记录两份；当前 KB 是 32 documents，P00 完成后必须为 34 documents。manifest 必须最后写，避免 README、navigation 或两份新文档在 manifest hash 写入后再次改变。

- [ ] **Step 1: 执行双重独立审查并准备最终审查记录**

审查记录必须由未撰写本计划的 reviewer 创建，并包含以下 exact sections：

```markdown
# Amadeus Core v0.1 Stage 0C 实施计划审查记录（2026-07-29）

## 1. 审查身份与输入
## 2. Frozen 设计覆盖矩阵
## 3. 叶级 TDD 与 Git 节点审查
## 4. 259-case 批次与语义 mapping 审查
## 5. Sandbox、publication、smoke 与 CLI 审查
## 6. BLOCKER / IMPORTANT / MINOR
## 7. 裁决
```

在 `## 1. 审查身份与输入` 中必须精确包含一个机器可读 attestation；创建记录时把全部 SHA placeholder 换成实际 64 位大写值，不保留 angle-bracket placeholder：

```text
<!-- stage0c-plan-review-attestation-v0.1
{
  "schema_version": "0.1",
  "reviewed_plan_path": "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md",
  "approved_draft_plan_sha256": "<APPROVED_DRAFT_PLAN_SHA256>",
  "reviewed_plan_sha256": "<FROZEN_PLAN_SHA256>",
  "frozen_design_path": "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换设计.md",
  "frozen_design_sha256": "7A7626B69893A743CAED07146E04C71061EC4482D740044259F79A7FC7C5F813",
  "reviewed_at": "2026-07-31",
  "frozen_transition": "Draft->Frozen-only",
  "draft_reviews": [
    {
      "reviewer_id": "stage0c-final-spec-v3",
      "reviewed_plan_sha256": "<APPROVED_DRAFT_PLAN_SHA256>",
      "findings": {"blocker": 0, "important": 0, "minor": 0}
    },
    {
      "reviewer_id": "/root/stage0c_quality_final_v3",
      "reviewed_plan_sha256": "<APPROVED_DRAFT_PLAN_SHA256>",
      "findings": {"blocker": 0, "important": 0, "minor": 0}
    }
  ],
  "final_reads": [
    {
      "reviewer_id": "stage0c-final-spec-v3",
      "reviewed_plan_sha256": "<FROZEN_PLAN_SHA256>",
      "findings": {"blocker": 0, "important": 0, "minor": 0}
    },
    {
      "reviewer_id": "/root/stage0c_quality_final_v3",
      "reviewed_plan_sha256": "<FROZEN_PLAN_SHA256>",
      "findings": {"blocker": 0, "important": 0, "minor": 0}
    }
  ],
  "findings": {
    "blocker": 0,
    "important": 0,
    "minor": 0
  },
  "verdict": "approved"
}
-->
```

[FRAME｜置信度：高] Frozen 计划必须作为 LF-only UTF-8 canonical block stream 扫描：只有第零列的三个 backtick 与固定 info allowlist 构成合法 fence；scanner 维护 top-level fence state，拒绝 indented/container/tilde/nested/未闭合 fence。fence 外从行首递归归一化 blockquote、无序列表与 1–9 位 ordered-list container，再拒绝其中的 H1–H6、HTML comment、processing instruction、CDATA、完整 raw HTML block、HTML entity、Setext/thematic marker；metadata 第 11 行 exact `---` 与空白隔开的 1–2 字符纯文本 `-`/`=` 是唯一词法例外。H6 禁止；H1–H5 必须是第零列 canonical ATX，H4/H5 ordered headings SHA 固定。scanner 必须取得唯一 metadata/status envelope、完整 top-level H1/H2/H3 序列及源字符 offsets；43 个 Task section hash 只能用这些 offsets 计算，普通 Task 到下一 top-level Task，D01 到其后首个 top-level H2。PowerShell AST、§11 ledger 与 259-row batch table 还必须执行未消费候选闭包和 ordered identity digest。

[FRAME｜置信度：高] 审查记录不是自由格式 Markdown。验收测试从 Frozen 计划最终 bytes 构造 attestation 与 43 个 plan-section SHA-256 rows，再与固定 H1、七个 H2、§3–§7 肯定性正文重建唯一 expected review UTF-8 文本；实际记录必须逐字相等。该动态重建只证明 plan/review 内部一致，不证明 reviewer 身份；两名 reviewer 完成最终复读后，P00 必须把 approved Draft、Frozen plan 与 final review 三个 SHA-256 作为 literal 固定在计划之外的 `tests/project_kb/test_current_repository.py`，运行时禁止从待审文件反推批准摘要。唯一 raw HTML comment 是 exact attestation；claim tag 只可作为行首独立 token，不能充当 image/link/emphasis。先由未撰写本计划的规格 reviewer 审查 Frozen 设计逐项覆盖；达到 0 BLOCKER / 0 IMPORTANT 后，再由另一名质量 reviewer 审查可执行性、TDD 粒度、类型/字段一致性和命令完整性。计划在两轮 Draft 审查均达到 0 BLOCKER / 0 IMPORTANT 前保持 Draft，期间不进入 F01。

两轮 Draft 审查通过后，只允许把计划状态从 `Draft` 改为 `Frozen`。两名 reviewer 必须重新读取该 Frozen 文件的最终 bytes，分别记录相同的最终 SHA-256，并确认除状态转换外无未经审查的内容变化；随后才创建最终审查记录。任何后续计划内容变化都会使原裁决失效，必须恢复 Draft 并重走本 Step。

- [ ] **Step 2: 冻结计划与审查记录两份文档的最终字节**

按以下顺序完成内容，完成后不得再次编辑这两份文件，除非重新执行本 Step 至 Step 7：

1. 完成 Draft 实施计划，由规格 reviewer 与质量 reviewer 依次达到 0 BLOCKER / 0 IMPORTANT。
2. 只把状态改为 `Frozen`；两名 reviewer 重读最终 bytes，确认同一最终 SHA-256 与 0 BLOCKER / 0 IMPORTANT。
3. 创建审查记录，写入上述 exact attestation、两名 reviewer ID、review date、Frozen 设计 SHA-256、批准的 Draft SHA-256、最终 Frozen 计划 SHA-256、43 个逐任务 PASS、全部发现项处置与 `approved` 裁决；关闭文件后从磁盘独立重读两份最终 bytes；两名 reviewer 分别回报相同的 approved Draft、Frozen plan 与 final review 三个 64 位大写 SHA-256，供 Step 3 literal 固定。
4. 两文件仍为 untracked 时，先对它们执行 `git add --intent-to-add -- <plan> <review>`，再运行 `git diff --check -- <plan> <review>` 并确认代码块闭合；随后立即执行 `git reset -- <plan> <review>`，并确认两文件恢复为 `??`、没有内容进入 index。此时明确不修改 README、`knowledge/data_structure.md` 或 manifest，因此既有 32 条 manifest 的文档 hash 仍有效。

- [ ] **Step 3: 写 32→34 的失败测试**

先核对 Step 2 两名 reviewer 独立回报的三个 SHA-256 完全相同；复制下方代码时，必须把 `__STEP2_APPROVED_DRAFT_SHA256__`、`__STEP2_FROZEN_PLAN_SHA256__` 与 `__STEP2_FINAL_REVIEW_SHA256__` 分别替换为对应的 64 位大写 literal，且测试运行时禁止从 plan、review、manifest、环境变量或命令动态派生这三个批准值。再把该文件既有三个冻结值逐字更新：CLI stdout 从 `indexed_documents=32` 改为 `indexed_documents=34`，`assert len(paths) == 32` 改为 `assert len(paths) == 34`，`assert len(set(paths)) == 32` 改为 `assert len(set(paths)) == 34`。最后增加以下两个精确测试；此时尚未修改 manifest：

```python
# tests/project_kb/test_current_repository.py：在现有 import 区增加 hashlib、shutil、subprocess 与 unicodedata。
import hashlib
import shutil
import subprocess
import unicodedata


STAGE0C_APPROVED_DRAFT_PLAN_SHA256 = "__STEP2_APPROVED_DRAFT_SHA256__"
STAGE0C_APPROVED_FROZEN_PLAN_SHA256 = "__STEP2_FROZEN_PLAN_SHA256__"
STAGE0C_APPROVED_REVIEW_SHA256 = "__STEP2_FINAL_REVIEW_SHA256__"


def test_stage0c_plan_is_frozen_and_review_is_approved() -> None:
    plan_path = (
        ROOT / "outputs" / "Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md"
    )
    review_path = (
        ROOT
        / "outputs"
        / "Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md"
    )
    plan_raw = plan_path.read_bytes()
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_FROZEN_PLAN_SHA256,
    )
    assert hashlib.sha256(plan_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_FROZEN_PLAN_SHA256
    )
    plan_text = plan_raw.decode("utf-8")
    assert plan_text.encode("utf-8") == plan_raw
    assert plan_text.endswith("\n")
    assert "\r" not in plan_text
    assert not any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in plan_text
        if character != "\n"
    )

    fence_open_pattern = re.compile(
        r"`{3}(?P<info>markdown|text|python|powershell|gitattributes|json)?"
    )
    fence_token_pattern = re.compile(r"`{3,}|~{3,}")
    container_prefix_pattern = re.compile(
        r"[ \t]*(?:"
        r">[ \t]*|"
        r"[*+\-](?:[ \t]+|$)|"
        r"[0-9]{1,9}[.)](?:[ \t]+|$)"
        r")"
    )
    atx_heading_marker_pattern = re.compile(
        r"[ \t]*(#{1,6})(?!#)(?=[ \t]|$)"
    )
    canonical_heading_pattern = re.compile(
        r"(#{1,6})[ \t]+(?=\S)[^\r\n]*\S"
    )
    raw_html_tag_pattern = re.compile(
        r"[ \t]*</?[A-Za-z][^\r\n]*>",
        flags=re.IGNORECASE,
    )
    raw_html_reserved_open_pattern = re.compile(
        r"[ \t]*<(?:script|pre|style|textarea|address|article|aside|base|"
        r"basefont|blockquote|body|caption|center|col|colgroup|dd|"
        r"details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
        r"footer|form|frame|frameset|h[1-6]|head|header|hr|html|"
        r"iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|"
        r"optgroup|option|p|param|search|section|summary|table|tbody|"
        r"td|tfoot|th|thead|title|tr|track|ul)(?=[ \t/>]|$)",
        flags=re.IGNORECASE,
    )
    html_heading_pattern = re.compile(
        r"</?h[1-6](?=[ \t/>])[^\r\n]*>",
        flags=re.IGNORECASE,
    )
    html_entity_pattern = re.compile(
        r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);"
    )
    setext_line_pattern = re.compile(r"[ \t]*(?:=+|-+)[ \t]*")
    thematic_line_pattern = re.compile(
        r"[ \t]*(?:(?:\*[ \t]*){3,}|"
        r"(?:_[ \t]*){3,}|(?:-[ \t]*){3,})"
    )

    def structural_views(line: str) -> list[tuple[int, str]]:
        views = [(0, line)]
        payload = line
        for depth in range(1, 65):
            marker = container_prefix_pattern.match(payload)
            if marker is None:
                return views
            assert marker.end() > 0
            payload = payload[marker.end() :]
            views.append((depth, payload))
        raise AssertionError("excessive Markdown container nesting")

    plan_line_records = []
    plan_heading_records = []
    plan_leaf_heading_records = []
    offset = 0
    inside_fence = False
    fence_marker_count = 0
    fence_open_counts = {}
    active_fence_info = None

    for line_number, raw_line in enumerate(
        plan_text.splitlines(keepends=True),
        start=1,
    ):
        assert raw_line.endswith("\n")
        line = raw_line[:-1]
        start = offset
        offset += len(raw_line)

        fence_token = fence_token_pattern.search(line)
        if fence_token is not None:
            fence_marker_count += 1
            if not inside_fence:
                fence_open_match = fence_open_pattern.fullmatch(line)
                assert fence_open_match is not None
                fence_info = fence_open_match.group("info") or ""
                fence_open_counts[fence_info] = (
                    fence_open_counts.get(fence_info, 0) + 1
                )
                active_fence_info = fence_info
                inside_fence = True
            else:
                assert line == "`" * 3
                active_fence_info = None
                inside_fence = False
            plan_line_records.append(
                {
                    "number": line_number,
                    "start": start,
                    "end": offset,
                    "line": line,
                    "top_level": False,
                    "fence_marker": True,
                }
            )
            continue

        top_level = not inside_fence
        record = {
            "number": line_number,
            "start": start,
            "end": offset,
            "line": line,
            "top_level": top_level,
            "fence_marker": False,
            "fence_info": None if top_level else active_fence_info,
        }
        plan_line_records.append(record)

        if not top_level:
            continue

        assert "<!--" not in line
        assert "-->" not in line
        assert "<?" not in line
        assert "<![CDATA[" not in line
        assert "<!" not in line
        assert html_entity_pattern.search(line) is None

        views = structural_views(line)
        previous_record = (
            plan_line_records[-2] if len(plan_line_records) >= 2 else None
        )
        for depth, payload in views:
            assert raw_html_tag_pattern.match(payload) is None
            assert raw_html_reserved_open_pattern.match(payload) is None
            assert html_heading_pattern.search(payload) is None
            if thematic_line_pattern.fullmatch(payload) is not None:
                assert depth == 0
                assert (line_number, line) == (11, "---")
            elif setext_line_pattern.fullmatch(payload) is not None:
                short_plain_text_after_blank = (
                    depth == 0
                    and payload == line
                    and len(payload.strip()) <= 2
                    and previous_record is not None
                    and previous_record.get("top_level") is True
                    and previous_record["line"] == ""
                )
                if not short_plain_text_after_blank:
                    assert depth == 0
                    assert (line_number, line) == (11, "---")

        heading_candidates = [
            (depth, match)
            for depth, payload in views
            if (
                match := atx_heading_marker_pattern.match(payload)
            )
            is not None
        ]
        if not heading_candidates:
            continue

        assert len(heading_candidates) == 1
        assert heading_candidates[0][0] == 0
        canonical_heading = canonical_heading_pattern.fullmatch(line)
        assert canonical_heading is not None
        heading_level = len(canonical_heading.group(1))
        assert heading_level <= 5
        heading_record = {
            "number": line_number,
            "start": start,
            "level": heading_level,
            "line": line,
        }
        if heading_level <= 3:
            plan_heading_records.append(heading_record)
        else:
            plan_leaf_heading_records.append(heading_record)

    assert offset == len(plan_text)
    assert not inside_fence
    assert fence_marker_count == 748
    assert fence_open_counts == {
        "gitattributes": 1,
        "json": 1,
        "markdown": 1,
        "powershell": 252,
        "python": 23,
        "text": 96,
    }

    frozen_status = "> [KNOWN｜置信度：高] 状态：Frozen。"
    draft_status = "> [KNOWN｜置信度：高] 状态：Draft。"
    status_prefix = "> [KNOWN｜置信度：高] 状态："

    top_level_records = [
        record for record in plan_line_records if record["top_level"]
    ]
    status_records = [
        record
        for record in top_level_records
        if "状态：" in record["line"]
    ]
    assert [
        (record["number"], record["line"])
        for record in status_records
    ] == [(13, frozen_status)]

    frozen_metadata_raw = "".join(
        plan_text.splitlines(keepends=True)[:16]
    ).encode("utf-8")
    assert hashlib.sha256(frozen_metadata_raw).hexdigest().upper() == (
        "4F7191C8313CBBA8E3439DD7C6A1F41F"
        "38512F307DF7DE3A33376B6B77A1AB25"
    )

    metadata_locations = (
        (3, "> **For agentic workers:**"),
        (5, "**Goal:**"),
        (7, "**Architecture:**"),
        (9, "**Tech Stack:**"),
        (13, status_prefix),
        (14, "> [KNOWN｜置信度：高] 唯一规格："),
        (15, "> [KNOWN｜置信度：高] 本计划不修改冻结设计"),
    )
    for expected_line_number, prefix in metadata_locations:
        matches = [
            record
            for record in top_level_records
            if record["line"].startswith(prefix)
        ]
        assert [record["number"] for record in matches] == [
            expected_line_number
        ]

    assert len(plan_heading_records) == 57
    assert {
        level: sum(
            record["level"] == level for record in plan_heading_records
        )
        for level in (1, 2, 3)
    } == {1: 1, 2: 13, 3: 43}
    assert hashlib.sha256(
        "\n".join(
            record["line"] for record in plan_heading_records
        ).encode("utf-8")
    ).hexdigest().upper() == (
        "399C44BD770E36317D9C6D7B0B547012"
        "780F0B141B5E9CF02B8611741E980B39"
    )
    assert {
        level: sum(
            record["level"] == level
            for record in plan_leaf_heading_records
        )
        for level in (4, 5)
    } == {4: 34, 5: 17}
    assert hashlib.sha256(
        "\n".join(
            record["line"] for record in plan_leaf_heading_records
        ).encode("utf-8")
    ).hexdigest().upper() == (
        "F3806B1E984203525F2D2C9D836028C2"
        "53E64DC43318110A9556688E3F4E4D29"
    )

    expected_h1 = [
        "# Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan"
    ]
    expected_h2 = [
        "## 0. 反方边界",
        "## 1. 冻结输入",
        "## 2. 完成定义",
        "## 3. 文件职责",
        "## 4. 依赖图与并行边界",
        "## 5. 统一叶级 TDD 与 Git 协议",
        "## 6. 实施任务",
        "## 7. Reviewed case 的 13 个审计批次",
        "## 8. Static registry 与 S Sandbox",
        "## 9. Publication、handler manifest 与 smoke matrix",
        "## 10. Final compiler、verification、CLI 与关闭门",
        "## 11. Git 节点清单",
        "## 12. 计划自检",
    ]
    assert [
        record["line"]
        for record in plan_heading_records
        if record["level"] == 1
    ] == expected_h1
    assert [
        record["line"]
        for record in plan_heading_records
        if record["level"] == 2
    ] == expected_h2

    expected_tasks = (
        ("P00",)
        + tuple(f"F{number:02d}" for number in range(1, 10))
        + tuple(f"B{number:02d}" for number in range(1, 14))
        + ("F10",)
        + tuple(f"R{number:02d}" for number in range(1, 9))
        + tuple(f"P{number:02d}" for number in range(1, 4))
        + tuple(f"M{number:02d}" for number in range(1, 3))
        + ("C01", "V00", "L01", "V01", "Q01", "D01")
    )

    task_heading_records = [
        record
        for record in plan_heading_records
        if record["level"] == 3
    ]
    task_ids = []
    for record in task_heading_records:
        match = re.fullmatch(
            r"### Task ([A-Z][0-9]{2})：[^\r\n]+",
            record["line"],
        )
        assert match is not None
        task_ids.append(match.group(1))
    assert tuple(task_ids) == expected_tasks

    plan_task_hashes = {}
    h2_heading_records = [
        record
        for record in plan_heading_records
        if record["level"] == 2
    ]
    for index, (task_id, record) in enumerate(
        zip(task_ids, task_heading_records, strict=True)
    ):
        if index + 1 < len(task_heading_records):
            section_end = task_heading_records[index + 1]["start"]
        else:
            later_h2 = [
                heading
                for heading in h2_heading_records
                if heading["start"] > record["start"]
            ]
            assert later_h2
            section_end = later_h2[0]["start"]

        assert section_end > record["start"]
        section_raw = plan_text[
            record["start"] : section_end
        ].encode("utf-8")
        plan_task_hashes[task_id] = hashlib.sha256(
            section_raw
        ).hexdigest().upper()

    outside_fence_lines = [
        record["line"] for record in top_level_records
    ]
    rpv_level4_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 4
        and (
            match := re.fullmatch(
                r"#### ((?:R|P|V)\d{2}(?:-[A-Z])?)：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    rpv_level5_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 5
        and (
            match := re.fullmatch(
                r"##### ((?:R|P|V)\d{2}-[A-Z]\d+)：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    assert len(rpv_level4_ids) == len(set(rpv_level4_ids)) == 32
    assert len(rpv_level5_ids) == len(set(rpv_level5_ids)) == 17
    split_parent_ids = {
        parent
        for parent in rpv_level4_ids
        if any(child.startswith(parent) for child in rpv_level5_ids)
    }
    assert len(split_parent_ids) == 4
    structured_rpv_leaf_count = (
        len(rpv_level4_ids)
        - len(split_parent_ids)
        + len(rpv_level5_ids)
    )
    direct_rpv_leaf_ids = [
        task_id
        for task_id in task_ids
        if task_id in {"R01", "V01"}
    ]
    c01_leaf_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 4
        and (
            match := re.fullmatch(
                r"#### (C01-[A-Z])：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    assert structured_rpv_leaf_count == 45
    assert direct_rpv_leaf_ids == ["R01", "V01"]
    rpv_leaf_count = (
        structured_rpv_leaf_count + len(direct_rpv_leaf_ids)
    )
    assert rpv_leaf_count == 47
    assert c01_leaf_ids == ["C01-A", "C01-B"]
    assert rpv_leaf_count + len(c01_leaf_ids) == 49

    powershell_source = (
        "\n".join(
            record["line"]
            for record in plan_line_records
            if record.get("fence_info") == "powershell"
        )
        + "\n"
    )
    assert hashlib.sha256(
        powershell_source.encode("utf-8")
    ).hexdigest().upper() == (
        "0F3AF63CE78C14E18E44FBA3CEFC4992"
        "3BDAFEA95A97A0CD305B39C716CA2C3B"
    )
    powershell_executable = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell_executable is not None
    powershell_ast_probe = r"""
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$source = [Console]::In.ReadToEnd()
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput(
  $source,
  [ref]$tokens,
  [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
  [Console]::Error.WriteLine(($parseErrors.Message -join " | "))
  exit 2
}
$commands = @(
  $ast.FindAll(
    {
      param($node)
      $node -is [System.Management.Automation.Language.CommandAst]
    },
    $true
  )
)
$gitCommands = @(
  $commands | Where-Object {
    $name = $_.GetCommandName()
    ($name -ceq "git") -or ($name -ceq "git.exe")
  }
)
foreach ($command in $gitCommands) {
  if (
    ($command.CommandElements.Count -lt 2) -or
    ($command.CommandElements[1] -isnot
      [System.Management.Automation.Language.StringConstantExpressionAst])
  ) {
    [Console]::Error.WriteLine("dynamic git subcommand forbidden")
    exit 3
  }
}
$gitCommandExtents = @(
  $gitCommands | ForEach-Object { $_.Extent.Text }
)
$commitCommands = @(
  $commands | Where-Object {
    ($_.CommandElements.Count -ge 2) -and
    ($_.CommandElements[1] -is
      [System.Management.Automation.Language.StringConstantExpressionAst]) -and
    ($_.CommandElements[1].Value -ceq "commit")
  } | ForEach-Object { $_.Extent.Text }
)
ConvertTo-Json -InputObject (
  [ordered]@{
    git = @($gitCommandExtents)
    commits = @($commitCommands)
  }
) -Compress
"""
    powershell_ast_result = subprocess.run(
        [
            powershell_executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            powershell_ast_probe,
        ],
        input=powershell_source,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert powershell_ast_result.returncode == 0, (
        powershell_ast_result.stderr
    )
    powershell_ast_payload = json.loads(powershell_ast_result.stdout)
    assert set(powershell_ast_payload) == {"git", "commits"}
    ast_git_extents = powershell_ast_payload["git"]
    assert isinstance(ast_git_extents, list)
    assert len(ast_git_extents) == 417
    assert all(isinstance(extent, str) for extent in ast_git_extents)
    assert hashlib.sha256(
        "\n".join(ast_git_extents).encode("utf-8")
    ).hexdigest().upper() == (
        "0FD6CF50EFF9CD6012F209A0DAA72D97"
        "BF2E21ACB284F25D1B9C9D5FC021E833"
    )
    ast_commit_extents = powershell_ast_payload["commits"]
    assert isinstance(ast_commit_extents, list)
    commit_messages = []
    for extent in ast_commit_extents:
        assert isinstance(extent, str)
        match = re.fullmatch(r'git commit -m "([^"]+)"', extent)
        assert match is not None
        commit_messages.append(match.group(1))
    assert len(commit_messages) == 91
    assert len(set(commit_messages)) == 91
    assert hashlib.sha256(
        "\n".join(commit_messages).encode("utf-8")
    ).hexdigest().upper() == (
        "6948B1439B6E5ECC9F9C99CE6ECFE27A"
        "386A9BFBD93744324D2EB940C49E20AD"
    )

    ledger_heading_index = outside_fence_lines.index(
        "## " + "11. Git 节点清单"
    )
    ledger_end_index = outside_fence_lines.index(
        "## " + "12. 计划自检"
    )
    assert ledger_heading_index < ledger_end_index
    ledger_rows = []
    for line in outside_fence_lines[
        ledger_heading_index + 1 : ledger_end_index
    ]:
        for depth, payload in structural_views(line):
            candidate = payload.lstrip(" \t")
            if re.match(r"\d+[.)](?:[ \t]+|$)", candidate) is None:
                continue
            assert depth == 0
            assert payload == line == candidate
            match = re.fullmatch(r"(\d+)\. `([^`]+)`", line)
            assert match is not None
            ledger_rows.append((int(match.group(1)), match.group(2)))
    assert [ordinal for ordinal, _ in ledger_rows] == list(range(1, 92))
    assert [message for _, message in ledger_rows] == commit_messages

    batch_heading_index = outside_fence_lines.index(
        "## " + "7. Reviewed case 的 13 个审计批次"
    )
    batch_end_index = outside_fence_lines.index(
        "## " + "8. Static registry 与 S Sandbox"
    )
    assert batch_heading_index < batch_end_index
    batch_table_lines = []
    for line in outside_fence_lines[
        batch_heading_index + 1 : batch_end_index
    ]:
        for depth, payload in structural_views(line):
            candidate = payload.lstrip(" \t")
            if "|" not in candidate:
                continue
            assert depth == 0
            assert payload == line == candidate
            batch_table_lines.append(line)

    batch_rows = []
    for line in batch_table_lines:
        match = re.fullmatch(
            r"\| (\d+) \| (B\d{2}) \| (\d+) \| "
            r"([^|]+?) \| `([^`]+)` \|",
            line,
        )
        if match is not None:
            batch_rows.append(match.groups())
        else:
            assert line in {
                "| ordinal | batch_id | batch_ordinal | "
                "exact clause ID | exact filename |",
                "|---:|---|---:|---|---|",
            }
    frozen_manifest_path = (
        ROOT
        / "fixtures"
        / "stage0b"
        / "generated"
        / "source_clause_manifest_v0_1.json"
    )
    frozen_manifest_raw = frozen_manifest_path.read_bytes()
    assert hashlib.sha256(frozen_manifest_raw).hexdigest().upper() == (
        "DFA68D59BBEAB43AD788002483DBF6D6E"
        "F88FFFA67D106BC4355FC167A6A2B3C"
    )
    frozen_manifest = json.loads(frozen_manifest_raw.decode("utf-8"))
    expected_batch_rows = [
        (
            str(ordinal),
            f"B{((ordinal - 1) // 20) + 1:02d}",
            str(((ordinal - 1) % 20) + 1),
            clause["clause_id"],
            f"case-{clause['clause_id'].lower().replace('#', '-')}.json",
        )
        for ordinal, clause in enumerate(
            frozen_manifest["clauses"],
            start=1,
        )
    ]
    assert len(batch_rows) == 259
    assert batch_rows == expected_batch_rows
    expected_batch_table_lines = []
    for batch_number in range(1, 14):
        batch_id = f"B{batch_number:02d}"
        expected_batch_table_lines.extend(
            [
                "| ordinal | batch_id | batch_ordinal | "
                "exact clause ID | exact filename |",
                "|---:|---|---:|---|---|",
            ]
        )
        expected_batch_table_lines.extend(
            (
                f"| {ordinal} | {row_batch_id} | {batch_ordinal} | "
                f"{clause_id} | `{filename}` |"
            )
            for (
                ordinal,
                row_batch_id,
                batch_ordinal,
                clause_id,
                filename,
            ) in expected_batch_rows
            if row_batch_id == batch_id
        )
    assert len(batch_table_lines) == 285
    assert batch_table_lines == expected_batch_table_lines

    status_record = status_records[0]
    approved_draft_text = (
        plan_text[: status_record["start"]]
        + draft_status
        + plan_text[status_record["start"] + len(frozen_status) :]
    )
    approved_draft_raw = approved_draft_text.encode("utf-8")
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_DRAFT_PLAN_SHA256,
    )
    assert hashlib.sha256(approved_draft_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_DRAFT_PLAN_SHA256
    )

    expected_attestation = {
        "schema_version": "0.1",
        "reviewed_plan_path": (
            "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md"
        ),
        "approved_draft_plan_sha256": hashlib.sha256(
            approved_draft_raw
        ).hexdigest().upper(),
        "reviewed_plan_sha256": hashlib.sha256(plan_raw).hexdigest().upper(),
        "frozen_design_path": (
            "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换设计.md"
        ),
        "frozen_design_sha256": (
            "7A7626B69893A743CAED07146E04C71061EC4482D740044259F79A7FC7C5F813"
        ),
        "reviewed_at": "2026-07-31",
        "frozen_transition": "Draft->Frozen-only",
        "draft_reviews": [
            {
                "reviewer_id": "stage0c-final-spec-v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    approved_draft_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
            {
                "reviewer_id": "/root/stage0c_quality_final_v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    approved_draft_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
        ],
        "final_reads": [
            {
                "reviewer_id": "stage0c-final-spec-v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    plan_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
            {
                "reviewer_id": "/root/stage0c_quality_final_v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    plan_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
        ],
        "findings": {"blocker": 0, "important": 0, "minor": 0},
        "verdict": "approved",
    }

    coverage_body = "\n".join(
        [
            "| Task | Verdict | Evidence |",
            "|---|---|---|",
            *[
                (
                    f"| {task_id} | PASS | "
                    f"plan-section-sha256:{plan_task_hashes[task_id]} |"
                )
                for task_id in expected_tasks
            ],
        ]
    )

    review_h1 = (
        "# Amadeus Core v0.1 Stage 0C "
        "实施计划审查记录（2026-07-29）"
    )
    review_h2 = (
        "## 1. 审查身份与输入",
        "## 2. Frozen 设计覆盖矩阵",
        "## 3. 叶级 TDD 与 Git 节点审查",
        "## 4. 259-case 批次与语义 mapping 审查",
        "## 5. Sandbox、publication、smoke 与 CLI 审查",
        "## 6. BLOCKER / IMPORTANT / MINOR",
        "## 7. 裁决",
    )

    section_1_body = (
        "<!-- stage0c-plan-review-attestation-v0.1\n"
        + json.dumps(
            expected_attestation,
            ensure_ascii=False,
            indent=2,
        )
        + "\n-->"
    )
    section_3_body = (
        "[COMPUTED｜置信度：高] 已核验 47 个实际 R/P/V TDD leaves、"
        "49 个风险 leaves 与 91 个唯一 commit；ledger 与 91 个 "
        "commit 节点按顺序一一对应。"
    )
    section_4_body = (
        "[COMPUTED｜置信度：高] 已核验 13 个批次按 "
        "12×20+19=259 完整覆盖 frozen manifest；每批 Author 与 "
        "Reviewer 角色分离，逐条语义 mapping 可追溯。"
    )
    section_5_body = (
        "[KNOWN｜置信度：高] 已核验 Sandbox、publication、smoke 与 "
        "CLI 叶节点、失败路径、恢复边界和验收命令。"
    )
    section_6_body = "\n".join(
        [
            (
                "[KNOWN｜置信度：高] 已关闭此前记录的 manifest/navigation、"
                "attestation、external approved SHA pin、leaf/commit/table candidate closure、Task/heading/section hash、canonical Markdown/JSON、PowerShell 状态连续性、reparse 分类与 README 130/34 状态缺口；当前开放项如下。"
            ),
            "",
            "| Level | Open |",
            "|---|---:|",
            "| BLOCKER | 0 |",
            "| IMPORTANT | 0 |",
            "| MINOR | 0 |",
        ]
    )
    section_7_body = (
        "[INFERRED｜置信度：高] 裁决：approved。"
    )

    review_bodies = (
        section_1_body,
        coverage_body,
        section_3_body,
        section_4_body,
        section_5_body,
        section_6_body,
        section_7_body,
    )
    expected_review_text = "\n\n".join(
        [
            review_h1,
            *[
                f"{heading}\n\n{body}"
                for heading, body in zip(
                    review_h2,
                    review_bodies,
                    strict=True,
                )
            ],
        ]
    ) + "\n"

    review_raw = review_path.read_bytes()
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_REVIEW_SHA256,
    )
    assert hashlib.sha256(review_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_REVIEW_SHA256
    )
    review_text = review_raw.decode("utf-8")
    assert review_text.encode("utf-8") == review_raw
    assert review_text.endswith("\n")
    assert "\r" not in review_text
    assert not any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in review_text
        if character != "\n"
    )

    assert review_text.count("<!--") == 1
    assert review_text.count("-->") == 1
    assert review_text.count(section_1_body) == 1
    review_without_attestation = review_text.replace(
        section_1_body,
        "",
        1,
    )
    assert "<" not in review_without_attestation
    assert ">" not in review_without_attestation
    assert "&" not in review_without_attestation

    claim_tag_pattern = re.compile(
        r"\[(?:KNOWN|COMPUTED|INFERRED|COMMON|FRAME|GUESS)"
        r"(?:｜置信度：(?:高|中|低|极低|未知))?\]"
    )
    canonical_review_lines = []
    for line in review_without_attestation.splitlines():
        matches = list(claim_tag_pattern.finditer(line))
        if matches:
            assert len(matches) == 1
            match = matches[0]
            assert match.start() == 0
            assert line[match.end() :].startswith(" ")
            assert not line[match.end() :].startswith("  ")
            line = line[match.end() + 1 :]
        canonical_review_lines.append(line)

    assert not re.search(
        r"[*_`~&<>\[\]]",
        "\n".join(canonical_review_lines),
    )
    assert review_text == expected_review_text


def test_stage0c_plan_and_independent_review_are_indexed() -> None:
    manifest = json.loads(
        (ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest) == {"schema_version", "documents"}
    documents = manifest["documents"]
    by_id = {row["doc_id"]: row for row in documents}
    expected = {
        "stage0c-fixture-conversion-plan": {
            "doc_id": "stage0c-fixture-conversion-plan",
            "title": "Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan",
            "path": "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md",
            "kind": "implementation-plan",
            "authority": "canonical",
            "status": "approved",
            "stage": "stage0c",
            "index": True,
            "sensitivity": "internal",
        },
        "stage0c-implementation-plan-review-2026-07-29": {
            "doc_id": "stage0c-implementation-plan-review-2026-07-29",
            "title": "Amadeus Core v0.1 Stage 0C 实施计划审查记录（2026-07-29）",
            "path": "outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md",
            "kind": "plan-review",
            "authority": "canonical",
            "status": "approved",
            "stage": "stage0c",
            "index": True,
            "sensitivity": "internal",
        },
    }
    assert set(expected) <= set(by_id)
    assert len(documents) == 34
    assert len(by_id) == 34
    for doc_id, expected_row in expected.items():
        row = by_id[doc_id]
        assert set(row) == set(expected_row) | {"sha256"}
        assert {key: row[key] for key in expected_row} == expected_row
        raw = (ROOT / expected_row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]

    new_doc_ids = tuple(expected)
    design_review_index = next(
        index
        for index, row in enumerate(documents)
        if row["doc_id"] == "stage0c-design-review-2026-07-29"
    )
    assert tuple(
        row["doc_id"]
        for row in documents[design_review_index + 1 : design_review_index + 3]
    ) == new_doc_ids

    existing_documents = [
        row for row in documents if row["doc_id"] not in expected
    ]
    assert len(existing_documents) == 32
    existing_projection = [
        {
            key: value
            for key, value in row.items()
            if not (
                key == "sha256"
                and row["doc_id"] in {"root-readme", "kb-navigation"}
            )
        }
        for row in existing_documents
    ]
    existing_canonical = json.dumps(
        existing_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(existing_canonical).hexdigest() == (
        "9e70f62779019c2e7545f7731045d8ed59ee712b18a13608b756c63fc7e22df6"
    )

    def authority_section(path: Path, heading: str) -> str:
        text = path.read_text(encoding="utf-8")
        prefix, separator, remainder = text.partition(f"{heading}\n")
        assert prefix or separator
        assert separator == f"{heading}\n"
        return remainder.split("\n## ", 1)[0]

    readme_section = authority_section(
        ROOT / "README.md",
        "## 权威文档阅读顺序",
    )
    navigation_section = authority_section(
        ROOT / "knowledge" / "data_structure.md",
        "## 5. 权威恢复入口",
    )
    for expected_row in expected.values():
        target = expected_row["path"]
        assert _MARKDOWN_LINK.findall(readme_section).count(target) == 1
        assert _MARKDOWN_LINK.findall(navigation_section).count(f"../{target}") == 1
    assert hashlib.sha256((ROOT / "README.md").read_bytes()).hexdigest() == (
        "e629fe5e639a6cf72ec98646560b0edf739a9e9dd619043d3130366ed62ef2c0"
    )
    assert hashlib.sha256(
        (ROOT / "knowledge" / "data_structure.md").read_bytes()
    ).hexdigest() == (
        "426720562e2f9363ff6b56148f7e538bcc1a5a6a6b83c995a133dcb7224cbdb0"
    )

    expected_paths = {
        "README.md",
        "knowledge/data_structure.md",
        "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md",
        "outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md",
    }
    by_path = {row["path"]: row for row in documents}
    assert expected_paths <= set(by_path)
    for path in expected_paths:
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == by_path[path]["sha256"]
```

- [ ] **Step 4: 运行精确红灯**

```powershell
git diff --cached --exit-code -- README.md knowledge/data_structure.md knowledge/manifest.json
git diff HEAD --exit-code -- README.md knowledge/data_structure.md knowledge/manifest.json
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb/test_current_repository.py::test_stage0c_plan_is_frozen_and_review_is_approved -q
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb/test_current_repository.py::test_stage0c_plan_and_independent_review_are_indexed -q
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb/test_current_repository.py::test_current_manifest_is_complete_and_ready -q
```

Expected: 两条 git diff 都必须 exit code 0，分别证明 index 与 HEAD 视角下三文件均未改变；第一条 pytest 必须 PASS，证明 Frozen 计划与独立审查记录已形成可执行验收；第二条 pytest 只因两个 expected doc_id 缺席而 FAIL；第三条 pytest 只因 stdout/count 仍为 32 而 FAIL。已有 32 条 manifest 记录的 schema/hash 内容不得出现新的失败。RED 前不得修改或暂存三文件；两条 git diff 结果共同构成三文件仍为 P00 开始时 bytes 的磁盘证据。

- [ ] **Step 5: 完成两份导航并重算四份最终文档 hash**

在 Step 4 已证明 RED 原因精确之后才执行：

1. 在 README 的 Stage 0C 设计条目后插入以下 exact single line，把原 9–11 的编号顺延为 10–12；同时把完整自动化测试 exact line 从 `127 / 127` 更新为 `130 / 130`，把恢复清单的知识库 exact line 从 `32 个索引文档` 更新为 `34 个索引文档`。除这四项 byte delta 外不得改 README：

```text
9. [KNOWN｜置信度：高] [Stage 0C 夹具转换实施计划](outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md) 与 [实施计划审查记录](outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md) — 已冻结的 259-case 转换、sandbox、publication、smoke 与 CLI 叶级执行合同。
```

2. 在 `knowledge/data_structure.md` 的 Stage 0C 设计条目后插入以下 exact single line，不改其他内容：

```text
9. [KNOWN｜置信度：高] [Stage 0C 夹具转换实施计划](../outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md) 与 [实施计划审查记录](../outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md)：Frozen 259-case 转换、sandbox、publication、smoke 与 CLI 叶级执行合同。
```
3. 先对仍为 untracked 的实施计划与审查记录重复 Step 2 第 4 项的 `intent-to-add → diff --check → reset → ??` 序列；再对 README 与 navigation 运行 `git diff --check -- README.md knowledge/data_structure.md`。确认四文件均通过后，从此不再编辑四份文件，除非恢复计划为 Draft 并重做 Step 1–Step 7。
4. 在同一 PowerShell 进程中重算四份最终 bytes 的 hash：

```powershell
$paths = @(
  'outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md',
  'outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md',
  'README.md',
  'knowledge/data_structure.md'
)
$hashes = @{}
foreach ($path in $paths) {
  $hashes[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$hashes.GetEnumerator() | Sort-Object Name | Format-Table -AutoSize
```

Expected: 四个 key 均有 64 位小写十六进制值；README 必须精确为 `e629fe5e639a6cf72ec98646560b0edf739a9e9dd619043d3130366ed62ef2c0`，`knowledge/data_structure.md` 必须精确为 `426720562e2f9363ff6b56148f7e538bcc1a5a6a6b83c995a133dcb7224cbdb0`；`$hashes` 只在本 PowerShell 进程中传给 Step 6，Step 7 必须从磁盘独立重算，不把该临时值写回四份已冻结文档。

- [ ] **Step 6: 最后写 manifest**

只在 Step 2 的计划/review bytes 稳定、Step 4 的 RED 原因已验证、Step 5 的 README/navigation 已冻结且取得四份实际 hash 后修改 `knowledge/manifest.json`：

1. 把既有 README 与 `knowledge/data_structure.md` 记录的 `sha256` 更新为 `$hashes` 中对应的实际值。
2. 新增 `stage0c-fixture-conversion-plan`：title=`Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan`、kind=`implementation-plan`、authority=`canonical`、status=`approved`、stage=`stage0c`、index=`true`、sensitivity=`internal`，sha256 使用 Step 5 的实际值。
3. 新增 `stage0c-implementation-plan-review-2026-07-29`：title=`Amadeus Core v0.1 Stage 0C 实施计划审查记录（2026-07-29）`、kind=`plan-review`、authority=`canonical`、status=`approved`、stage=`stage0c`、index=`true`、sensitivity=`internal`，sha256 使用 Step 5 的实际值。
4. 两条新记录按现有 Stage 0C 文档邻接顺序插入；不重排无关记录。

- [ ] **Step 7: 运行绿灯并重新读取 hash**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb/test_current_repository.py -q
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb -q
.\.venv\Scripts\python.exe -B -m tools.project_kb.cli --root . check
.\.venv\Scripts\python.exe -B -m pytest -q
```

Expected: `test_current_repository.py` 精确 7 passed，`tests/project_kb` 精确 40 passed，KB check 报告 34 个 indexed documents 与 0 个 raw paths，完整 suite 精确 130 passed；四条命令 exit code 0。测试必须从磁盘重读四份文档并重算 hash，不复用 Step 5 的变量。

- [ ] **Step 8: 显式暂存与提交**

```powershell
git add README.md knowledge/data_structure.md knowledge/manifest.json tests/project_kb/test_current_repository.py outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md
git diff --cached --check
git diff --cached --stat
git commit -m "docs: freeze reviewed stage0c fixture conversion plan"
```

### Task F01：Stage 0C package、常量与 lock carrier

**Files:**
- Create: `tools/stage0c_fixtures/__init__.py`
- Create: `tools/stage0c_fixtures/constants.py`
- Create: `tools/stage0c_fixtures/types.py`
- Create: `tests/stage0c/test_import_contract.py`
- Create: `tests/stage0c/conftest.py`
- Create: `fixtures/stage0c/.stage0c-write.lock`
- Modify: `.gitattributes`

- [ ] **Step 1: 写 import 与常量红灯**

```python
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from tools.stage0c_fixtures import SCHEMA_VERSION
from tools.stage0c_fixtures.constants import (
    EXPECTED_BATCH_COUNT,
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_GENERATED_FILE_COUNT,
    EXPECTED_S_CLAUSE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
    LOCK_PATH,
)
from tools.stage0c_fixtures.types import (
    FixtureInputError,
    PublicationError,
    PublicationProbeOutcome,
    PublicationProbeSpec,
    PublicationResult,
    RecoveryResult,
    Stage0CError,
    ValidationIssue,
)


def test_stage0c_import_and_constants_are_frozen() -> None:
    assert SCHEMA_VERSION == "0.1"
    assert EXPECTED_BATCH_COUNT == 13
    assert EXPECTED_CLAUSE_COUNT == 259
    assert EXPECTED_S_CLAUSE_COUNT == 98
    assert EXPECTED_GENERATED_FILE_COUNT == 265
    assert EXPECTED_SOURCE_ID_SET_SHA256 == (
        "9B771DEFE9BBD3F2025F32AB400ADE1AA4916223BE467B7EEF0135E9E3C4D39A"
    )
    assert EXPECTED_CLAUSE_ID_SET_SHA256 == (
        "0BD1579970C18D4BFB7A0F57AA53B8E30CB3DA5F50DB8F48240E16C634FD5CFC"
    )
    assert LOCK_PATH == "fixtures/stage0c/.stage0c-write.lock"
    assert INPUT_IDENTITIES == {
        "stage0b_manifest": {
            "path": "fixtures/stage0b/generated/source_clause_manifest_v0_1.json",
            "sha256": "DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C",
            "size": 252478,
        },
        "stage0b_report": {
            "path": "fixtures/stage0b/generated/stage0b_report_v0_1.json",
            "sha256": "F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8",
            "size": 585,
        },
        "core_contract": {
            "path": "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
            "sha256": "3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695",
            "size": 79488,
        },
        "adr_004": {
            "path": "outputs/ADR-004-Amadeus工具权限与执行治理.md",
            "sha256": "2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125",
            "size": 25191,
        },
    }


def test_lock_carrier_is_precreated_empty_regular_file() -> None:
    path = Path("fixtures/stage0c/.stage0c-write.lock")
    assert path.is_file()
    assert not path.is_symlink()
    assert path.read_bytes() == b""


def test_shared_types_and_error_protocol_are_frozen() -> None:
    error = FixtureInputError(
        "json_non_utf8", source="fixture.json", detail="byte=0"
    )
    assert isinstance(error, Stage0CError)
    assert error.code == "json_non_utf8"
    assert error.source == "fixture.json"
    assert error.detail == "byte=0"
    assert error.args == ("json_non_utf8:fixture.json:byte=0",)
    issue = ValidationIssue(
        json_pointer="/reviewer",
        code="reviewer_missing",
        message="reviewer is required",
    )
    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"  # type: ignore[misc]
    result = PublicationResult(
        published=True,
        no_op=False,
        recovered=False,
        tree_sha256="A" * 64,
    )
    assert result.published and not result.no_op
    with pytest.raises(PublicationError, match="publication_result_invalid"):
        PublicationResult(
            published=True,
            no_op=True,
            recovered=False,
            tree_sha256="A" * 64,
        )
    spec = PublicationProbeSpec(
        case_id="publication-prepared-p-i-empty",
        journal_state="prepared",
        disk_shape="P,I,Ø",
        fault_point="none",
    )
    assert set(spec.to_json()) == {
        "case_id", "journal_state", "disk_shape", "fault_point"
    }
    outcome = PublicationProbeOutcome(
        attempt_count=1,
        executed=True,
        passed=True,
        terminal_tree_sha256="A" * 64,
        actual={"terminal": "I"},
    )
    assert outcome.executed and outcome.passed
    recovered_absent = RecoveryResult(
        terminal="absent",
        tree_sha256=None,
        changed=True,
    )
    assert recovered_absent.tree_sha256 is None
    with pytest.raises(PublicationError, match="recovery_result_invalid"):
        RecoveryResult(
            terminal="present",
            tree_sha256=None,
            changed=False,
        )


def test_publication_and_recovery_result_runtime_invariants_are_strict() -> None:
    publication_base = {
        "published": True,
        "no_op": False,
        "recovered": False,
        "tree_sha256": "A" * 64,
    }
    publication_mutations = (
        {"published": 1},
        {"no_op": 0},
        {"recovered": "false"},
        {"tree_sha256": "a" * 64},
        {"tree_sha256": "A" * 63},
    )
    for mutation in publication_mutations:
        with pytest.raises(PublicationError, match="publication_result_invalid"):
            PublicationResult(**(publication_base | mutation))  # type: ignore[arg-type]

    recovery_mutations = (
        {"terminal": "garbage", "tree_sha256": "A" * 64, "changed": False},
        {"terminal": "present", "tree_sha256": "A" * 64, "changed": 1},
        {"terminal": "present", "tree_sha256": "a" * 64, "changed": False},
        {"terminal": "present", "tree_sha256": "A" * 63, "changed": False},
        {"terminal": "absent", "tree_sha256": "A" * 64, "changed": False},
    )
    for mutation in recovery_mutations:
        with pytest.raises(PublicationError, match="recovery_result_invalid"):
            RecoveryResult(**mutation)  # type: ignore[arg-type]

```

- [ ] **Step 2: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_import_contract.py -q
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0c_fixtures`。

- [ ] **Step 3: 写 package 与常量最小实现**

```python
# tools/stage0c_fixtures/constants.py
SCHEMA_VERSION = "0.1"
EXPECTED_SOURCE_COUNT = 214
EXPECTED_CLAUSE_COUNT = 259
EXPECTED_S_SOURCE_COUNT = 75
EXPECTED_S_CLAUSE_COUNT = 98
EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT = 51
EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT = 55
EXPECTED_BATCH_COUNT = 13
EXPECTED_GENERATED_CASE_COUNT = 259
EXPECTED_GENERATED_TOP_LEVEL_COUNT = 6
EXPECTED_GENERATED_FILE_COUNT = 265
BATCH_SIZE = 20
EXPECTED_SOURCE_ID_SET_SHA256 = (
    "9B771DEFE9BBD3F2025F32AB400ADE1AA4916223BE467B7EEF0135E9E3C4D39A"
)
EXPECTED_CLAUSE_ID_SET_SHA256 = (
    "0BD1579970C18D4BFB7A0F57AA53B8E30CB3DA5F50DB8F48240E16C634FD5CFC"
)

LOCK_PATH = "fixtures/stage0c/.stage0c-write.lock"
GENERATED_PATH = "fixtures/stage0c/generated"
REVIEWED_CASES_PATH = "fixtures/stage0c/reviewed/cases"
JOURNAL_PATH = "fixtures/stage0c/.stage0c-publication.json"
SMOKE_EVIDENCE_PATH = (
    "outputs/verification/"
    "Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json"
)

INPUT_IDENTITIES = {
    "stage0b_manifest": {
        "path": "fixtures/stage0b/generated/source_clause_manifest_v0_1.json",
        "sha256": "DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C",
        "size": 252478,
    },
    "stage0b_report": {
        "path": "fixtures/stage0b/generated/stage0b_report_v0_1.json",
        "sha256": "F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8",
        "size": 585,
    },
    "core_contract": {
        "path": "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
        "sha256": "3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695",
        "size": 79488,
    },
    "adr_004": {
        "path": "outputs/ADR-004-Amadeus工具权限与执行治理.md",
        "sha256": "2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125",
        "size": 25191,
    },
}
```

```python
# tools/stage0c_fixtures/types.py：不得 import 任何项目内模块
from dataclasses import dataclass
from typing import Literal


type JsonScalar = None | bool | int | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class Stage0CError(Exception):
    __slots__ = ("code", "source", "detail")

    def __init__(
        self,
        code: str,
        *,
        source: str | None = None,
        detail: str = "",
    ) -> None:
        self.code = code
        self.source = source
        self.detail = detail
        text = code
        if source is not None:
            text += f":{source}"
        if detail:
            text += f":{detail}"
        super().__init__(text)


class FixtureInputError(Stage0CError):
    pass


class PublicationError(Stage0CError):
    pass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    json_pointer: str
    code: str
    message: str


def _is_upper_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(ch in "0123456789ABCDEF" for ch in value)
    )


@dataclass(frozen=True, slots=True)
class PublicationResult:
    published: bool
    no_op: bool
    recovered: bool
    tree_sha256: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (self.published, self.no_op, self.recovered)
        ):
            raise PublicationError(
                "publication_result_invalid",
                detail="boolean fields",
            )
        if self.published == self.no_op:
            raise PublicationError(
                "publication_result_invalid",
                detail="exactly one of published/no_op must be true",
            )
        if not _is_upper_sha256(self.tree_sha256):
            raise PublicationError(
                "publication_result_invalid",
                detail="tree_sha256",
            )


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    terminal: Literal["present", "absent"]
    tree_sha256: str | None
    changed: bool

    def __post_init__(self) -> None:
        if type(self.changed) is not bool:
            raise PublicationError(
                "recovery_result_invalid",
                detail="changed",
            )
        if self.terminal not in ("present", "absent"):
            raise PublicationError(
                "recovery_result_invalid",
                detail="terminal",
            )
        if (self.terminal == "absent") != (self.tree_sha256 is None):
            raise PublicationError(
                "recovery_result_invalid",
                detail="terminal/tree_sha256",
            )
        if self.tree_sha256 is not None and not _is_upper_sha256(
            self.tree_sha256
        ):
            raise PublicationError(
                "recovery_result_invalid",
                detail="tree_sha256",
            )


@dataclass(frozen=True, slots=True)
class PublicationProbeSpec:
    case_id: str
    journal_state: str
    disk_shape: str
    fault_point: str

    def to_json(self) -> JsonObject:
        return {
            "case_id": self.case_id,
            "journal_state": self.journal_state,
            "disk_shape": self.disk_shape,
            "fault_point": self.fault_point,
        }


@dataclass(frozen=True, slots=True)
class PublicationProbeOutcome:
    attempt_count: int
    executed: bool
    passed: bool
    terminal_tree_sha256: str | None
    actual: JsonValue
```

```python
# tools/stage0c_fixtures/__init__.py
from .constants import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION"]
```

```python
# tests/stage0c/conftest.py
from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

- [ ] **Step 4: 创建零字节 lock carrier 与 checkout 属性**

创建 `fixtures/stage0c/.stage0c-write.lock`，内容精确为零字节。在 `.gitattributes` 追加：

```gitattributes
outputs/verification/*.json -text
outputs/verification/stage0c-reviewed-batches/*.json -text
fixtures/stage0c/.stage0c-write.lock -text
```

- [ ] **Step 5: 运行绿灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_import_contract.py -q
```

Expected: 4 passed。

- [ ] **Step 6: 重构并回归**

确认 `constants.py` 只包含冻结常量，不读取文件、不执行 import-time I/O；随后运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_import_contract.py tests/test_repository_checkout_contract.py -q
git diff --check
```

Expected: exit code 0。

- [ ] **Step 7: 提交**

```powershell
git add .gitattributes fixtures/stage0c/.stage0c-write.lock tools/stage0c_fixtures/__init__.py tools/stage0c_fixtures/constants.py tools/stage0c_fixtures/types.py tests/stage0c/conftest.py tests/stage0c/test_import_contract.py
git diff --cached --check
git commit -m "feat(stage0c): freeze package constants and lock carrier"
```

### Task F02：Strict canonical JSON 与普通文件边界

**Files:**
- Create: `tools/stage0c_fixtures/io.py`
- Create: `tests/stage0c/test_io.py`

- [ ] **Step 1: 写 canonical bytes 与 strict decoder 红灯**

```python
import hashlib

import pytest

from tools.stage0c_fixtures.io import (
    FixtureInputError,
    canonical_bytes,
    load_strict_json_bytes,
    sha256_upper,
)


def test_canonical_bytes_are_exact() -> None:
    value = {"z": [None, True, 3], "中文": {"b": 2, "a": 1}}
    expected = '{"z":[null,true,3],"中文":{"a":1,"b":2}}\n'.encode("utf-8")
    assert canonical_bytes(value) == expected
    assert sha256_upper(expected) == hashlib.sha256(expected).hexdigest().upper()


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"\xef\xbb\xbf{}", "json_bom_forbidden"),
        (b'{"a":1,"a":2}', "json_duplicate_key"),
        (b'{"x":1.5}', "json_float_forbidden"),
        (b'{"x":NaN}', "json_non_finite_forbidden"),
        (b'{"x":Infinity}', "json_non_finite_forbidden"),
        (b"\xff", "json_non_utf8"),
        (b"{}\r\n", "json_non_canonical"),
    ],
)
def test_strict_decoder_rejects_invalid_bytes(raw: bytes, code: str) -> None:
    with pytest.raises(FixtureInputError, match=code):
        load_strict_json_bytes(raw, source="fixture.json")
```

- [ ] **Step 2: 写路径边界表驱动红灯**

| 输入 | 精确错误码 |
|---|---|
| `C:/absolute.json` | `repo_path_absolute` |
| `/absolute.json` | `repo_path_absolute` |
| `fixtures\stage0c\x.json` | `repo_path_backslash` |
| `fixtures/./x.json` | `repo_path_dot_segment` |
| `fixtures/../x.json` | `repo_path_parent_segment` |
| missing terminal 或 missing ordinary ancestor | `repo_path_missing` |
| dangling terminal/ancestor symlink、junction 或 reparse component | `repo_path_reparse` |
| directory/FIFO/device | `repo_path_not_regular_file` |

测试必须在真实临时目录创建普通文件和平台可创建的非法对象；Windows reparse case 不能用布尔 stub 替代。

- [ ] **Step 3: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_io.py -q
```

Expected: collection FAIL，缺少 `tools.stage0c_fixtures.io`。

- [ ] **Step 4: 写最小实现**

从 `types.py` import `JsonValue/JsonObject/FixtureInputError`，不得在 `io.py` 建立第二套类型或异常。实现以下 public API，签名不得在后续节点改名：`canonical_bytes(value: JsonValue) -> bytes`、`sha256_upper(data: bytes) -> str`、`load_strict_json_bytes(data: bytes, *, source: str) -> JsonValue`、`read_repo_regular_file(root: Path, repo_relative_posix: str) -> bytes`、`tree_entries(root: Path) -> list[dict[str, JsonValue]]`、`tree_sha256(root: Path) -> str`。

`canonical_bytes` 的递归 validator 必须先判 `value is None` 和 `isinstance(value, bool)`，再用 `type(value) is int`；禁止用 `isinstance(value, int)` 把 bool 误归类为 integer。随后拒绝 float，再精确调用 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"`。decoder 使用 `object_pairs_hook` 捕获重复键，解析后重编码并要求输入与 canonical bytes 相等。路径验证逐 component `lstat`，不跟随 reparse；缺失 terminal 或普通 ancestor 精确抛 `repo_path_missing`，当前 component 是 dangling/non-dangling reparse 时优先抛 `repo_path_reparse`，类型非法才抛 `repo_path_not_regular_file`；禁止先对完整 leaf 调用 `exists/lexists`。

- [ ] **Step 5: 运行绿灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_io.py -q
```

Expected: 全部 PASS。

- [ ] **Step 6: 生成、重读并比较 hash**

测试在 `tmp_path` 写 canonical bytes、关闭句柄、重新读取，断言重读 bytes 与首次 bytes 相等，`sha256_upper` 与 `hashlib.sha256` 相等；对相同 logical tree 以相反创建顺序写文件，断言 entries 与 aggregate hash 相等。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_io.py -q
git diff --check
```

- [ ] **Step 7: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/io.py tests/stage0c/test_io.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add strict canonical json io"
```

### Task F03：冻结输入身份与纯语义验证器

**Files:**
- Modify: `tools/stage0c_fixtures/io.py`
- Modify: `tests/stage0c/conftest.py`
- Create: `tests/stage0c/test_inputs.py`

- [ ] **Step 1: 写四输入 raw identity 红灯**

对 `INPUT_IDENTITIES` 的四个固定 path 分别复制到 `tmp_path/repository`，每个参数行只改变一个磁盘因素：

| mutation | 精确错误码 |
|---|---|
| 删除任一文件或普通 ancestor | `frozen_input_missing` |
| dangling terminal/ancestor symlink、junction 或 reparse | `repo_path_reparse` |
| 增减任一文件一个 byte | `frozen_input_size_or_hash_mismatch` |
| 保持 size 翻转任一文件一个 byte | `frozen_input_size_or_hash_mismatch` |
| 任一路径或任一 ancestor component 替换为 non-dangling symlink/junction/reparse | `repo_path_reparse` |
| 任一路径替换为 directory/nonregular | `repo_path_not_regular_file` |

这些 tests 只调用 `load_frozen_inputs(tmp_repository)`，因此证明 disk path/size/hash gate 先于 JSON semantic gate；byte mutation 不得期待 schema/count 错误。

- [ ] **Step 2: 写可达的 pure semantic mutation 红灯**

从当前 frozen manifest/report 的 canonical bytes strict-parse 两个 object，`copy.deepcopy` 后只改一项，再直接调用 `validate_frozen_semantics(manifest, report)`：

| parsed-object mutation | 精确错误码 |
|---|---|
| 任一 schema_version 改为 `0.2` | `frozen_schema_version_mismatch` |
| source_count 214→213 | `frozen_source_count_mismatch` |
| clause_count 259→258 | `frozen_clause_count_mismatch` |
| S source count 75→74 | `frozen_s_source_count_mismatch` |
| S clause count 98→97 | `frozen_s_clause_count_mismatch` |
| pending H/J clause count 51→50 | `frozen_h_or_j_clause_count_mismatch` |
| pending H/J requirement count 55→54 | `frozen_h_or_j_requirement_count_mismatch` |
| 替换一个 source ID 但保持 214 | `frozen_source_set_mismatch` |
| 替换一个 clause ID 但保持 259 | `frozen_clause_set_mismatch` |
| duplicate source/clause ID | `frozen_source_set_mismatch` / `frozen_clause_set_mismatch` |
| clause 的 source_id/source_group 与 source record 不一致 | `frozen_clause_source_join_mismatch` |
| source_adjudication_ready false 或 pending 非零 | `stage0b_not_ready` |
| report manifest SHA 不等于 frozen manifest identity | `frozen_report_manifest_identity_mismatch` |

source/clause set gate 分别对排序后的 unique ID array 取 canonical SHA-256，并与 F01 的 `EXPECTED_SOURCE_ID_SET_SHA256`、`EXPECTED_CLAUSE_ID_SET_SHA256` 比较；不能从被测 object 自己推导“expected set”。

- [ ] **Step 3: 运行两个红灯节点**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_inputs.py::test_raw_input_identity_precedes_semantics -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_inputs.py::test_pure_semantic_mutations_have_reachable_codes -q
```

Expected: 两个 node 均 FAIL，缺少 `load_frozen_inputs` / `validate_frozen_semantics`。

- [ ] **Step 4: 写最小实现与明确 API**

```python
# tools/stage0c_fixtures/io.py：与 F02 imports 合并
import os
from dataclasses import dataclass
from typing import Iterable

from .types import FixtureInputError, JsonValue

from .constants import (
    EXPECTED_CLAUSE_COUNT,
    EXPECTED_CLAUSE_ID_SET_SHA256,
    EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
    EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
    EXPECTED_S_CLAUSE_COUNT,
    EXPECTED_S_SOURCE_COUNT,
    EXPECTED_SOURCE_COUNT,
    EXPECTED_SOURCE_ID_SET_SHA256,
    INPUT_IDENTITIES,
    SCHEMA_VERSION,
)


@dataclass(frozen=True)
class FrozenInputs:
    manifest: dict[str, JsonValue]
    report: dict[str, JsonValue]
    clauses_by_id: dict[str, dict[str, JsonValue]]
    sources_by_id: dict[str, dict[str, JsonValue]]
    raw_sha256_by_key: dict[str, str]


def _require_frozen(condition: bool, code: str) -> None:
    if not condition:
        raise FixtureInputError(code)


def canonical_id_set_sha256(values: Iterable[str]) -> str:
    values_list = list(values)
    _require_frozen(
        len(values_list) == len(set(values_list)),
        "frozen_id_duplicate",
    )
    return sha256_upper(canonical_bytes(sorted(values_list)))


def validate_frozen_semantics(
    manifest: dict[str, JsonValue],
    report: dict[str, JsonValue],
) -> None:
    _require_frozen(
        manifest.get("schema_version") == SCHEMA_VERSION
        and report.get("schema_version") == SCHEMA_VERSION,
        "frozen_schema_version_mismatch",
    )
    _require_frozen(
        report.get("source_adjudication_ready") is True
        and report.get("pending_atomicity_reviews") == 0
        and report.get("pending_oracle_assignments") == 0,
        "stage0b_not_ready",
    )
    sources = manifest.get("sources")
    clauses = manifest.get("clauses")
    _require_frozen(isinstance(sources, list), "frozen_source_count_mismatch")
    _require_frozen(isinstance(clauses, list), "frozen_clause_count_mismatch")
    _require_frozen(
        manifest.get("source_count") == EXPECTED_SOURCE_COUNT
        and report.get("reviewed_sources") == EXPECTED_SOURCE_COUNT
        and len(sources) == EXPECTED_SOURCE_COUNT,
        "frozen_source_count_mismatch",
    )
    _require_frozen(
        manifest.get("clause_count") == EXPECTED_CLAUSE_COUNT
        and report.get("clause_count") == EXPECTED_CLAUSE_COUNT
        and len(clauses) == EXPECTED_CLAUSE_COUNT,
        "frozen_clause_count_mismatch",
    )
    source_ids = [row["source_id"] for row in sources]
    clause_ids = [row["clause_id"] for row in clauses]
    _require_frozen(
        len(source_ids) == len(set(source_ids))
        and canonical_id_set_sha256(source_ids)
        == EXPECTED_SOURCE_ID_SET_SHA256,
        "frozen_source_set_mismatch",
    )
    _require_frozen(
        len(clause_ids) == len(set(clause_ids))
        and canonical_id_set_sha256(clause_ids)
        == EXPECTED_CLAUSE_ID_SET_SHA256,
        "frozen_clause_set_mismatch",
    )
    _require_frozen(
        sum("S" in row["assigned_oracle_kinds"] for row in sources)
        == EXPECTED_S_SOURCE_COUNT,
        "frozen_s_source_count_mismatch",
    )
    _require_frozen(
        sum("S" in row["required_oracle_kinds"] for row in clauses)
        == EXPECTED_S_CLAUSE_COUNT,
        "frozen_s_clause_count_mismatch",
    )
    _require_frozen(
        sum(
            bool({"H", "J"} & set(row["required_oracle_kinds"]))
            for row in clauses
        )
        == EXPECTED_PENDING_H_OR_J_CLAUSE_COUNT,
        "frozen_h_or_j_clause_count_mismatch",
    )
    _require_frozen(
        sum(
            kind in {"H", "J"}
            for row in clauses
            for kind in row["required_oracle_kinds"]
        )
        == EXPECTED_PENDING_H_OR_J_REQUIREMENT_COUNT,
        "frozen_h_or_j_requirement_count_mismatch",
    )
    sources_by_id = {row["source_id"]: row for row in sources}
    _require_frozen(
        all(
            row["source_id"] in sources_by_id
            and row["source_group"]
            == sources_by_id[row["source_id"]]["source_group"]
            and row["source_binding_sha256"]
            == sources_by_id[row["source_id"]]["source_binding_sha256"]
            and row["decision_sha256"]
            == sources_by_id[row["source_id"]]["decision_sha256"]
            for row in clauses
        ),
        "frozen_clause_source_join_mismatch",
    )
    _require_frozen(
        report.get("source_clause_manifest_sha256")
        == INPUT_IDENTITIES["stage0b_manifest"]["sha256"],
        "frozen_report_manifest_identity_mismatch",
    )


def load_frozen_inputs(root: Path) -> FrozenInputs:
    raw_by_key: dict[str, bytes] = {}
    raw_sha256_by_key: dict[str, str] = {}
    # Pass 1: classify every component by lstat; remap only typed missing.
    for key, identity in INPUT_IDENTITIES.items():
        relative = identity["path"]
        try:
            raw_by_key[key] = read_repo_regular_file(root, relative)
        except FixtureInputError as error:
            if error.code != "repo_path_missing":
                raise
            raise FixtureInputError(
                "frozen_input_missing",
                source=relative,
            ) from error
    # Pass 2: only after every path/type gate passed, verify all sizes and hashes.
    for key, identity in INPUT_IDENTITIES.items():
        raw_value = raw_by_key[key]
        digest = sha256_upper(raw_value)
        if len(raw_value) != identity["size"] or digest != identity["sha256"]:
            raise FixtureInputError(
                "frozen_input_size_or_hash_mismatch",
                source=identity["path"],
            )
        raw_sha256_by_key[key] = digest
    manifest = load_strict_json_bytes(
        raw_by_key["stage0b_manifest"],
        source=INPUT_IDENTITIES["stage0b_manifest"]["path"],
    )
    report = load_strict_json_bytes(
        raw_by_key["stage0b_report"],
        source=INPUT_IDENTITIES["stage0b_report"]["path"],
    )
    _require_frozen(isinstance(manifest, dict), "frozen_manifest_type_invalid")
    _require_frozen(isinstance(report, dict), "frozen_report_type_invalid")
    validate_frozen_semantics(manifest, report)
    sources_by_id = {row["source_id"]: row for row in manifest["sources"]}
    clauses_by_id = {row["clause_id"]: row for row in manifest["clauses"]}
    return FrozenInputs(
        manifest=manifest,
        report=report,
        clauses_by_id=clauses_by_id,
        sources_by_id=sources_by_id,
        raw_sha256_by_key=raw_sha256_by_key,
    )
```

实现顺序固定为：四个 path/type→四个 size/hash→两个 JSON strict parse→schema/readiness→214/259/75/98/51/55→exact set hashes→source/clause join→构造 frozen outer carrier。`FrozenInputs` 只禁止属性重新赋值，内部 JSON dict/list 不宣称 deep immutable；调用方只能读取或先 `copy.deepcopy` 后做 mutation test。Core/ADR Markdown 只校验 raw identity。

- [ ] **Step 5: 增加共享 `frozen_inputs` fixture 并运行绿灯**

```python
# tests/stage0c/conftest.py：保留 F01 repository_root fixture，再追加
from tools.stage0c_fixtures.io import load_frozen_inputs


@pytest.fixture
def frozen_inputs(repository_root: Path):
    return load_frozen_inputs(repository_root)
```

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_inputs.py tests/stage0c/test_io.py -q
```

Expected: 全部 PASS；raw byte mutation 只命中 identity code，parsed-object mutation 命中各自 semantic code。

- [ ] **Step 6: 重新从磁盘读取并证明无对象复用**

同一 test 内两次独立调用 `load_frozen_inputs(repository_root)`；第二次重新读取四文件，断言 path、size、SHA-256 与 F01 constants 完全相等，且两次 manifest/report object identity 不同、value 相等。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_inputs.py -q
git diff --check
```

- [ ] **Step 7: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/io.py tests/stage0c/conftest.py tests/stage0c/test_inputs.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): freeze stage0c input identities"
```

### Task F04：259 项 deterministic conversion checklist

**Files:**
- Create: `tools/stage0c_fixtures/checklist.py`
- Create: `tests/stage0c/test_checklist.py`
- Modify: `tests/stage0c/conftest.py`

[FRAME｜置信度：高] F04 只实现 pure builder，并只在 pytest `tmp_path` 写临时文件。F04 不创建、不修改、不提交 `fixtures/stage0c/generated/`；C01 是第一次发布全部 265 files 的唯一节点。

- [ ] **Step 1: 写 ordinal/batch 红灯**

```python
def test_checklist_uses_manifest_ordinal_windows(frozen_inputs) -> None:
    checklist = build_conversion_checklist(frozen_inputs)
    rows = checklist["cases"]
    assert len(rows) == 259
    for ordinal, row in enumerate(rows, start=1):
        assert row["ordinal"] == ordinal
        assert row["batch_id"] == f"B{((ordinal - 1) // 20) + 1:02d}"
        assert row["batch_ordinal"] == ((ordinal - 1) % 20) + 1
    assert rows[119]["clause_id"] == "AC-093#3"
    assert rows[120]["clause_id"] == "AC-094#1"
    assert rows[258]["clause_id"] == "USE-05#1"
```

- [ ] **Step 2: 写 exact-field 与 join 红灯**

Top-level exact fields 为 `schema_version,stage0b_manifest_sha256,source_count,clause_count,batch_count,cases`。case row exact fields 为 `ordinal,batch_id,batch_ordinal,case_id,reviewed_path,generated_path,clause_id,source_id,source_group,source_binding_sha256,decision_sha256,clause_stimulus_sha256,clause_expected_sha256,clause_content_sha256,required_oracle_kinds`。测试对 missing/duplicate/unexpected clause、binding mismatch 和 manifest 顺序改变分别断言稳定错误码。

- [ ] **Step 3: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_checklist.py -q
```

Expected: FAIL，缺少 `build_conversion_checklist`。

- [ ] **Step 4: 写 pure 最小实现**

实现 `build_conversion_checklist(inputs: FrozenInputs) -> dict[str, JsonValue]` 与 `checklist_bytes(inputs: FrozenInputs) -> bytes`。

函数不得接收 output path，不执行写盘。ordinal 只来自 frozen `manifest["clauses"]` 数组位置；不得按 source group、ID 或文件系统重新排序。

```python
# tests/stage0c/conftest.py：保留已有 fixtures，再追加
from tools.stage0c_fixtures.checklist import build_conversion_checklist


@pytest.fixture
def checklist(frozen_inputs):
    return build_conversion_checklist(frozen_inputs)
```

- [ ] **Step 5: 在 tmp_path 生成、重读与比较 hash**

```python
def test_checklist_tmp_bytes_are_repeatable(tmp_path, frozen_inputs) -> None:
    first = checklist_bytes(frozen_inputs)
    path = tmp_path / "conversion_checklist_v0_1.json"
    path.write_bytes(first)
    reread = path.read_bytes()
    second = checklist_bytes(frozen_inputs)
    assert reread == first == second
    assert hashlib.sha256(reread).digest() == hashlib.sha256(second).digest()
```

- [ ] **Step 6: 运行绿灯并证明未产生 partial generated**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_checklist.py -q
git status --short -- fixtures/stage0c/generated
```

Expected: pytest PASS；第二条命令无输出。

- [ ] **Step 7: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/checklist.py tests/stage0c/conftest.py tests/stage0c/test_checklist.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): build conversion checklist in memory"
```

### Task F05：Fixture Case DSL 核心合同

**Files:**
- Create: `tools/stage0c_fixtures/dsl.py`
- Create: `tests/stage0c/test_dsl.py`

- [ ] **Step 1: 写 case ID 与 exact field 红灯**

```python
@pytest.mark.parametrize(
    ("clause_id", "case_id", "filename"),
    [
        ("AC-001#1", "case-ac-001-1", "case-ac-001-1.json"),
        ("BR-03#2", "case-br-03-2", "case-br-03-2.json"),
        ("USE-05#1", "case-use-05-1", "case-use-05-1.json"),
    ],
)
def test_case_identity_is_unique(
    clause_id: str,
    case_id: str,
    filename: str,
) -> None:
    assert case_id_for_clause_id(clause_id) == case_id
    assert case_filename_for_clause_id(clause_id) == filename
```

另以表驱动 mutation 覆盖 case extra/missing field、oracle order/duplicate、sequence 从 0 开始/跳号/乱序、step/assertion/criterion ID 冲突和 rubric order。下列 leaf gate 每行只改变一个值并断言专属稳定错误码：

| leaf mutation | 精确错误码 |
|---|---|
| `allowed_scores` 空、含 duplicate、非 integer 或非升序 | `rubric_allowed_scores_invalid` |
| `passing_scores` 空、含 duplicate、非升序或不是 allowed 子集 | `rubric_passing_scores_invalid` |
| `evidence_case_json_pointers` 空、duplicate、非 Unicode 升序或无法解析 | `rubric_evidence_pointer_invalid` |
| rubric missing/extra structural field | `rubric_exact_fields_invalid` |
| S case 的 `sandbox_profile=null` | `sandbox_profile_required` |
| non-S case 的 `sandbox_profile` 为 object | `sandbox_profile_forbidden` |
| `reset_policy` 不是 literal `fresh_context` | `sandbox_reset_policy_invalid` |
| `cleanup_policy` 不是 literal `always` | `sandbox_cleanup_policy_invalid` |
| `allowed_effects` 缺失、非 array 或含 duplicate rule | `sandbox_allowed_effects_invalid` |
| effect rule missing/extra field、adapter enum/type 错误 | `sandbox_effect_rule_invalid` |

`allowed_effects=[]` 只表示零 effect；缺字段、`null`、`"*"` 或开放 map 都不得解释为 wildcard。

- [ ] **Step 2: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_dsl.py -q
```

Expected: collection FAIL，缺少 `dsl.py`。

- [ ] **Step 3: 写最小实现**

固定 public API：`case_id_for_clause_id`、`case_filename_for_clause_id`、`validate_case_body`、`resolve_json_pointer`、`canonical_oracle_kinds`。`ValidationIssue` exact fields 为 `json_pointer,code,message`，结果按三字段 Unicode 顺序排序。

- [ ] **Step 4: 运行绿灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_dsl.py -q
```

- [ ] **Step 5: canonical round-trip 与 hash**

把三个 golden case body 写入 `tmp_path`、strict reread、重新验证并比较 canonical SHA-256；任何 validation failure 不得产生输出文件。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_dsl.py -q
git diff --check
```

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/dsl.py tests/stage0c/test_dsl.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): define fixture case dsl"
```

### Task F06：Envelope 与嵌套 structural object

**Files:**
- Modify: `tools/stage0c_fixtures/dsl.py`
- Create: `tools/stage0c_fixtures/schema.py`
- Create: `tests/stage0c/test_envelopes.py`
- Create: `tests/stage0c/test_schema.py`
- Modify: `tests/stage0c/conftest.py`

- [ ] **Step 1: 写 nested schema table**

| structural object | 必测交叉不变量 |
|---|---|
| MutationCommandEnvelope | expected_versions target set 精确等于 target_record_refs；`absent` 或 non-negative integer |
| ActionEnvelope | UUID fields；effect class；expiry；max uses；input/data classes；scope；confirmation |
| reversibility | unknown→E3；verified→非空 rollback plan/deadline；irreversible→两项 null |
| driverResult / HandlerResult | completed/failed/unknown 三套 error/retry/effect/patch 不变量 |
| EffectSeed / ObservedEffect / EffectPattern | exact fields；pattern null/empty-map 语义 |
| StatePatchOperation | root/array target 禁止；remove value=null；path unique |
| ActionReceipt / StepExecution | step/handler/request/snapshot/output/effects 逐值一致 |
| SandboxRunResult | phase、primary error、cleanup、succeeded 充要条件 |
| rubric requirement | exact fields=`criterion_id,oracle_kind,question,evidence_case_json_pointers,allowed_scores,passing_scores`；三个 array 的非空/唯一/排序/子集/指针解析 |
| sandbox profile | exact fields=`profile_id,allowed_effects,fixed_clock,id_seed,reset_policy,cleanup_policy`；reset=`fresh_context`、cleanup=`always` |
| effect rule | exact fields=`adapter_id,operation,target`；adapter enum=`file|message|payment|network|core` |

每个 object 的 valid golden 与“增加一个额外顶层字段”mutation 都必须进入参数化测试；structural object 一律 `additionalProperties=false`，仅 JSON map 允许递归开放键。

- [ ] **Step 2: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_envelopes.py tests/stage0c/test_schema.py -q
```

Expected: FAIL，schema builder 尚不存在。

- [ ] **Step 3: 写最小 schema builder 与 runtime cross-validator**

实现 `build_fixture_case_schema() -> dict`、`validate_envelope(kind, value)` 与 reusable `$defs`。schema 与 runtime validator 共享 enum、regex 和 exact-field constants，不复制两套拼写。

```python
# tests/stage0c/conftest.py：保留已有 fixtures，再追加
from tools.stage0c_fixtures.schema import build_fixture_case_schema


@pytest.fixture
def fixture_schema():
    return build_fixture_case_schema()
```

- [ ] **Step 4: 运行绿灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_envelopes.py tests/stage0c/test_schema.py -q
```

- [ ] **Step 5: schema bytes 重读与 mutation**

在 `tmp_path` 写完整 schema canonical bytes，关闭并重读；删除一个 required field、把一个 `additionalProperties` 改为 true，分别要求 golden fixture validation 失败。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_envelopes.py tests/stage0c/test_schema.py -q
git diff --check
```

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/dsl.py tools/stage0c_fixtures/schema.py tests/stage0c/test_envelopes.py tests/stage0c/test_schema.py tests/stage0c/conftest.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): define exact nested schemas"
```

### Task F07：Handler params 条件 schema 与 AC-001 golden case

**Files:**
- Modify: `tools/stage0c_fixtures/schema.py`
- Create: `tests/stage0c/test_handler_params_schema.py`

- [ ] **Step 1: 写 18-handler 参数表红灯**

参数化表的 key set 精确为：

```text
sandbox.seed_state
sandbox.set_clock
sandbox.configure_core_driver
sandbox.configure_adapter
sandbox.seed_backend_response
core.command
core.query
external.action
backend.replay
receipt.status
receipt.error_code
state.path_equals
state.hash_unchanged
effect.includes
effect.excludes
output.contains
output.omits
replay.equals
```

每行包含 `handler_kind,valid_params,one_missing_required,one_extra_field,one_wrong_type`；测试要求 valid 通过，其余三项分别失败。另测 unknown handler、import path、module、expression、script 与 callable target 被拒绝。

- [ ] **Step 2: 写 AC-001 golden 与单因素 mutation**

逐字段构造 Frozen 设计 AC-001#1 case；mutation 表依次改变 `source_clause_id`、driver error code、retryable、state hash pointer、oracle mapping、extra param，要求每次得到唯一预期 error code。

- [ ] **Step 3: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handler_params_schema.py -q
```

Expected: FAIL，`$defs.handler_params` 尚不完整。

- [ ] **Step 4: 写最小条件 schema**

生成 `$defs.handler_params`，key 精确为 handler ID；step/assertion schema 使用 `if handler_id / then params $ref` 条件分支。每个完整 handler params schema object 的 canonical bytes 是 M01 `params_schema_sha256` 的唯一 preimage。

- [ ] **Step 5: 运行绿灯并重算 18 个 schema hash**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handler_params_schema.py -q
```

测试对 18 个 schema object 分别 canonical serialize、hash、重读 schema 后重算，要求 key/hash maps 逐值相等。

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/schema.py tests/stage0c/test_handler_params_schema.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): bind handler parameter schemas"
```

### Task F08：Reviewed conversion strict validator

**Files:**
- Create: `tools/stage0c_fixtures/reviewed.py`
- Create: `tests/stage0c/test_reviewed.py`

- [ ] **Step 1: 冻结与设计逐字一致的 exact fields**

reviewed top-level exact fields 只能是：

```text
schema_version
stage0b_manifest_sha256
clause_id
source_id
source_group
source_binding_sha256
decision_sha256
clause_stimulus_sha256
clause_expected_sha256
clause_content_sha256
required_oracle_kinds
case_body
stimulus_mapping
assertion_or_rubric_mapping
reviewer
rationale
```

`stimulus_mapping` exact fields 为 `case_json_pointers,mapping_note`；`assertion_or_rubric_mapping[*]` exact fields 为 `oracle_kind,case_json_pointers,mapping_note`；`reviewer` exact fields 为 `role,reviewer_id,reviewed_at`，role 必须精确为 `conversion_reviewer`。不增加 author、设计外审计对象或派生 hash 字段；转换 author 与 reviewer 的角色分离由 tracked batch review record 证明。

- [ ] **Step 2: 写 structural、identity 与 mapping 红灯**

| mutation | 精确错误码 |
|---|---|
| top-level 仅缺 `reviewer` 且无 extra | `reviewer_missing`（唯一 issue） |
| top-level 缺其他字段或存在 extra | `reviewed_exact_fields_invalid` |
| 任一 frozen identity/hash/source/group/oracle 漂移 | `reviewed_frozen_identity_mismatch` |
| `case_body.source_clause_id/case_id` 与 frozen/checklist 不一致 | `reviewed_case_identity_mismatch` |
| stimulus pointer array 空、duplicate 或非 Unicode 升序 | `stimulus_mapping_pointer_set_invalid` |
| stimulus pointer 不落在具体 `/stimulus_steps/{index}` 或无法解析 | `stimulus_mapping_pointer_invalid` |
| assertion/rubric pointer 空、duplicate、非升序或无法解析 | `oracle_mapping_pointer_invalid` |
| D/S mapping 不指向 machine assertion | `machine_oracle_target_invalid` |
| H/J mapping 不指向 rubric requirement | `rubric_oracle_target_invalid` |
| required oracle 无同 kind mapping | `required_oracle_unmapped` |
| mapping note、rationale 或 reviewer_id 空白 | `review_explanation_empty` |
| reviewer 已存在但内部 missing/extra field、wrong role 或非法日期 | `reviewer_invalid` |

测试逐 pointer 调 `resolve_json_pointer(case_body, pointer)`，并证明 pointer 指向最终 case body 的实际值；不能只比较 mapping 数量。

- [ ] **Step 3: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_reviewed.py -q
```

Expected: FAIL，reviewed validator 尚不存在。

- [ ] **Step 4: 写最小 validator**

固定 public API：

```python
def load_reviewed_case(path: Path) -> JsonObject: ...

def validate_reviewed_case(
    row: JsonObject,
    frozen_clause: JsonObject,
    schema: JsonObject,
) -> list[ValidationIssue]: ...

def validate_reviewed_batch(
    rows: list[JsonObject],
    checklist_rows: list[JsonObject],
    frozen_clauses_by_id: dict[str, JsonObject],
    schema: JsonObject,
) -> list[ValidationIssue]: ...

def validate_reviewed_closed_set(
    rows: list[JsonObject],
    checklist: JsonObject,
    frozen_clauses_by_id: dict[str, JsonObject],
    schema: JsonObject,
) -> list[ValidationIssue]: ...

def validate_batch_review_record(
    record: JsonObject,
    checklist_rows: list[JsonObject],
    reviewed_by_clause_id: dict[str, JsonObject],
) -> list[ValidationIssue]: ...
```

导出 immutable `REVIEWED_EXACT_FIELDS`。错误优先级冻结为：仅缺 reviewer→单一 `reviewer_missing`；其他 top-level set 错误→`reviewed_exact_fields_invalid`；只有 reviewer object 存在后才检查其内部并可能产生 `reviewer_invalid`。batch/closed-set validator 必须接收 frozen clause map，禁止因缺上下文跳过逐案 identity/mapping gate。

validator 机械验证 exact fields、frozen identities、最终 case body schema、pointer 解析、machine/rubric target kind 与 required oracle coverage。自然语言 `stimulus_scope/expected_scope` 是否被充分表达是独立 reviewer 的逐案裁决，不能由 token/hash 相等冒充。

- [ ] **Step 5: 运行绿灯与 canonical round-trip**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_reviewed.py -q
```

在 `tmp_path` 写完整 golden reviewed file、strict reread、重新验证并比较 canonical bytes/hash。随后只改一个 mapping pointer，要求 structural gate 失败；另只改一个 mapping note Unicode code point并同时移除旧 reviewer，要求文件 hash 改变且唯一命中 `reviewer_missing`。恢复 note、完成第二角色复核并重新填写 reviewer 后才再次通过完整 reviewed gate。

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/reviewed.py tests/stage0c/test_reviewed.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): validate reviewed clause mappings"
```

### Task F09：Pure compiler 与 synthetic fixture

**Files:**
- Create: `tools/stage0c_fixtures/compiler.py`
- Create: `tests/stage0c/test_compiler.py`

- [ ] **Step 1: 写 synthetic two-clause 红灯**

synthetic input 精确包含一条 D clause 与一条 H+J clause。测试断言：

1. generated case bytes 精确等于 reviewed `case_body` canonical bytes；
2. `case_sha256` 哈希完整 generated case bytes；
3. binding record 的 exact fields 逐字等于 Frozen 设计：完整 frozen identity、`case_sha256`、两类 mapping、reviewer 与 rationale；
4. H/J 只保留 rubric requirements，不出现 verdict；
5. 输出按 case ID Unicode 顺序；
6. 任一 reviewed validation issue 或 exact set 不完整时不构建 success report。

- [ ] **Step 2: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_compiler.py -q
```

Expected: FAIL，compiler module 尚不存在。

- [ ] **Step 3: 写 pure 最小实现**

固定 public API：`compile_case_file(reviewed_row) -> tuple[str, bytes]`、`compile_binding_manifest(reviewed_rows, checklist) -> dict[str, JsonValue]`、`compile_stage0c_report(reviewed_rows, checklist) -> dict[str, JsonValue]`、`build_generated_artifacts(*, checklist, schema, handler_manifest, smoke_matrix, reviewed_rows) -> dict[str, bytes]`。

compiler 只接收已验证对象，不读取 Markdown，不修复 reviewed 字段，不写文件。`build_generated_artifacts` 必须要求 F04 checklist 参数，建立 F04→C01 的运行时依赖。

`compile_stage0c_report` 不从坏输入“猜” readiness；先验证实际 rows/checklist closure 与 214/259/259/98/51/55，任一不符抛 `FixtureInputError`。只有全部 gate 通过才返回 `dict(STAGE0C_REPORT_V0_1)`。冻结完整 literal：

```python
STAGE0C_REPORT_V0_1: dict[str, JsonValue] = {
    "schema_version": "0.1",
    "fixture_dsl_contract_ready": True,
    "clause_to_case_binding_complete": True,
    "case_definition_coverage_complete": True,
    "trusted_fixture_harness_contract_ready": True,
    "trusted_fixture_harness_smoke_verified": False,
    "source_count": 214,
    "clause_count": 259,
    "case_count": 259,
    "s_clause_count": 98,
    "pending_h_or_j_clause_count": 51,
    "pending_h_or_j_oracle_requirement_count": 55,
    "s_case_execution_complete": False,
    "case_execution_complete": False,
    "core_behavior_verified": False,
    "case_coverage_complete": False,
    "core_case_execution_coverage_complete": False,
    "catalog_ready": False,
    "release_ready": False,
}
```

`tests/stage0c/test_compiler.py` 必须同时断言 `set(report)==set(STAGE0C_REPORT_V0_1)`、`report==STAGE0C_REPORT_V0_1` 与 canonical bytes相等；逐个 boolean 翻转、count ±1、missing key、extra key，`validate_stage0c_report` 均只返回 `stage0c_report_literal_mismatch`。


- [ ] **Step 4: 运行绿灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_compiler.py -q
```

- [ ] **Step 5: tmp artifact 重读与 hash**

把 synthetic artifacts 写入 `tmp_path/generated`，关闭并递归重读，断言 path/size/hash entries 与内存 artifacts 相等；只改一个 frozen identity 或删除一个 required oracle mapping，要求编译在任何 bytes 写入前失败。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_compiler.py -q
git diff --check
```

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/compiler.py tests/stage0c/test_compiler.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): compile reviewed fixture cases"
```

[FRAME｜置信度：高] F07 的 handler params schema object 与 F09 的 compiler hash/build contract 都是 M01 的强制前置；M01 测试必须直接调用两者，禁止复制 schema 或 hash 逻辑。

## 7. Reviewed case 的 13 个审计批次

[FRAME｜置信度：高] clause ID `SOURCE#N` 的唯一 reviewed path 为 `fixtures/stage0c/reviewed/cases/case-{ASCII lowercase SOURCE}-{N}.json`。每个 batch test 都必须把 `ordinal,batch_id,batch_ordinal,clause_id,filename` 写为 literal table，并逐行与 F04 checklist 比较；不得只比较 ID set。

[FRAME｜置信度：高] 每个 batch test 使用以下完整结构；每个 batch 只替换 `EXPECTED_ROWS` 为本节列出的 literal rows：

```python
import pytest

from tools.stage0c_fixtures.reviewed import (
    REVIEWED_EXACT_FIELDS,
    load_reviewed_case,
    validate_reviewed_case,
)


@pytest.mark.parametrize(
    ("ordinal", "batch_id", "batch_ordinal", "clause_id", "filename"),
    EXPECTED_ROWS,
    ids=[row[3].lower().replace("-", "_").replace("#", "_") for row in EXPECTED_ROWS],
)
def test_reviewed_case_matches_frozen_clause(
    repository_root,
    frozen_inputs,
    checklist,
    fixture_schema,
    ordinal,
    batch_id,
    batch_ordinal,
    clause_id,
    filename,
) -> None:
    checklist_row = checklist["cases"][ordinal - 1]
    assert checklist_row["ordinal"] == ordinal
    assert checklist_row["batch_id"] == batch_id
    assert checklist_row["batch_ordinal"] == batch_ordinal
    assert checklist_row["clause_id"] == clause_id
    assert checklist_row["reviewed_path"] == (
        f"fixtures/stage0c/reviewed/cases/{filename}"
    )
    reviewed = load_reviewed_case(repository_root / checklist_row["reviewed_path"])
    frozen_clause = frozen_inputs.clauses_by_id[clause_id]
    issues = validate_reviewed_case(reviewed, frozen_clause, fixture_schema)
    assert issues == []
    assert set(reviewed) == set(REVIEWED_EXACT_FIELDS)
    assert reviewed["reviewer"]["role"] == "conversion_reviewer"
    assert reviewed["reviewer"]["reviewer_id"].strip()
    assert reviewed["rationale"].strip()
    assert reviewed["stimulus_mapping"]["mapping_note"].strip()
    assert all(
        item["mapping_note"].strip()
        for item in reviewed["assertion_or_rubric_mapping"]
    )
```

[FRAME｜置信度：高] 每个 batch 严格按单案循环，不先批量填 reviewer：

1. **Author** 读取 checklist 的当前 literal row 与对应 frozen clause，创建只含 Frozen 列出 fields 的 reviewed JSON；填写 case body、两类 mapping 与来源特定 rationale，暂不填写 reviewer。author identity 不进入 reviewed JSON。
2. **Author red** 把本 task 的 exact batch test path、当前 literal clause ID 和 filename 赋给下列变量并只运行该参数 node；唯一允许的 issue 是 `ValidationIssue(json_pointer="/reviewer", code="reviewer_missing", ...)`：

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B01.py'
$clauseId = 'AC-001#1'
$filename = 'case-ac-001-1.json'
$pytestId = $clauseId.ToLowerInvariant().Replace('-', '_').Replace('#', '_')
.\.venv\Scripts\python.exe -B -m pytest $batchTest -q -k $pytestId
```

[FRAME｜置信度：高] 上述三项初值展示 B01 第一行的实际执行；处理后续行时必须直接使用该 task literal table 中同一行的三个实际值。单案阶段不运行整批 closure node，因为后续 paths 尚未创建。

3. **Reviewer** 由不同角色逐字比对 frozen `stimulus_scope`，确认语义片段由具体 handler 与同 step params pointers 承载；逐字比对 `expected_scope`，确认 machine assertion/rubric 与 required oracle 覆盖；strict reread 后填写 Frozen reviewer object。
4. **Validate green** 重跑同一参数 ID；Expected: 1 passed，其余 deselected。validator 通过后才允许执行 `assert set(reviewed) == set(REVIEWED_EXACT_FIELDS)` 与 reviewer 直接索引。
5. **Case diff audit** 运行 `git diff -- ("fixtures/stage0c/reviewed/cases/" + $filename)`，确认只出现当前 case。
6. 对 literal table 的下一行重复 1–5；20-case batch 不允许一次性跳到整批绿灯。
7. 全部单案通过后才运行整个 batch test 与 `tests/stage0c/test_reviewed.py`，再建立只含 batch test 与 exact case paths 的 data commit。
8. data commit 完成后创建 tracked record 与独立 audit test，再建立 audit commit。record 不进入 compiler/generated tree；record 不记录自身 hash。

[FRAME｜置信度：高] 13 个 review records 的 exact schema 为：

```json
{
  "schema_version": "0.1",
  "batch_id": "B01",
  "reviewed_commit": "0123456789abcdef0123456789abcdef01234567",
  "test_path": "tests/stage0c/reviewed_batches/test_batch_B01.py",
  "case_reviews": [
    {
      "ordinal": 1,
      "batch_ordinal": 1,
      "clause_id": "AC-001#1",
      "case_path": "fixtures/stage0c/reviewed/cases/case-ac-001-1.json",
      "author_id": "conversion-author-role-id",
      "reviewer_id": "conversion-reviewer-role-id",
      "reviewed_at": "2026-07-29"
    }
  ]
}
```

top-level exact fields 为 `schema_version,batch_id,reviewed_commit,test_path,case_reviews`；case review exact fields 为 `ordinal,batch_ordinal,clause_id,case_path,author_id,reviewer_id,reviewed_at`。structural object 拒绝 extra；array 按 ordinal；B01–B12 各 20 项，B13 为 19 项；author/reviewer 均非空且不相等；reviewer_id/reviewed_at 必须逐案等于 reviewed JSON reviewer；reviewed_commit 为 40 位 lowercase Git object ID。

[FRAME｜置信度：高] 每个 audit test 必须执行：

```python
commit = record["reviewed_commit"]
subprocess.run(
    ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
    cwd=repository_root,
    check=True,
)
reachable = subprocess.run(
    ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
    cwd=repository_root,
    check=False,
)
assert reachable.returncode == 0
actual_paths = subprocess.run(
    ["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit],
    cwd=repository_root,
    check=True,
    capture_output=True,
).stdout.decode("utf-8").splitlines()
assert sorted(actual_paths) == sorted(expected_payload_paths)
for case_path in expected_case_paths:
    committed = subprocess.run(
        ["git", "show", f"{commit}:{case_path}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout
    assert committed == (repository_root / case_path).read_bytes()
```

[FRAME｜置信度：高] conversion author identity 来自 tracked record 的 `author_id`，不得用 Git commit author/e-mail替代。批次 data commit 不得包含 generated、record、audit test、共享 Python 或其他 batch 文件；audit commit exact set 只能含自己的 record 与 audit test。

### Task B01：ordinals 1–20，AC-001#1 至 AC-018#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B01.py`、`tests/stage0c/reviewed_batches/test_audit_B01.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B01.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 1 | B01 | 1 | AC-001#1 | `case-ac-001-1.json` |
| 2 | B01 | 2 | AC-002#1 | `case-ac-002-1.json` |
| 3 | B01 | 3 | AC-003#1 | `case-ac-003-1.json` |
| 4 | B01 | 4 | AC-004#1 | `case-ac-004-1.json` |
| 5 | B01 | 5 | AC-005#1 | `case-ac-005-1.json` |
| 6 | B01 | 6 | AC-006#1 | `case-ac-006-1.json` |
| 7 | B01 | 7 | AC-007#1 | `case-ac-007-1.json` |
| 8 | B01 | 8 | AC-008#1 | `case-ac-008-1.json` |
| 9 | B01 | 9 | AC-008#2 | `case-ac-008-2.json` |
| 10 | B01 | 10 | AC-008#3 | `case-ac-008-3.json` |
| 11 | B01 | 11 | AC-009#1 | `case-ac-009-1.json` |
| 12 | B01 | 12 | AC-010#1 | `case-ac-010-1.json` |
| 13 | B01 | 13 | AC-011#1 | `case-ac-011-1.json` |
| 14 | B01 | 14 | AC-012#1 | `case-ac-012-1.json` |
| 15 | B01 | 15 | AC-013#1 | `case-ac-013-1.json` |
| 16 | B01 | 16 | AC-014#1 | `case-ac-014-1.json` |
| 17 | B01 | 17 | AC-015#1 | `case-ac-015-1.json` |
| 18 | B01 | 18 | AC-016#1 | `case-ac-016-1.json` |
| 19 | B01 | 19 | AC-017#1 | `case-ac-017-1.json` |
| 20 | B01 | 20 | AC-018#1 | `case-ac-018-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B01.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-001#1` / `case-ac-001-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B01.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B01.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-001-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-002-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-003-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-004-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-005-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-006-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-007-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-009-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-010-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-011-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-012-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-013-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-014-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-015-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-016-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-017-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-018-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B01"
if ($LASTEXITCODE -ne 0) { throw 'B01 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B01.json` 与 `tests/stage0c/reviewed_batches/test_audit_B01.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B01.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B01 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B01.py -q
if ($LASTEXITCODE -ne 0) { throw 'B01 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B01.json tests/stage0c/reviewed_batches/test_audit_B01.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B01"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B02：ordinals 21–40，AC-019#1 至 AC-037#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B02.py`、`tests/stage0c/reviewed_batches/test_audit_B02.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B02.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 21 | B02 | 1 | AC-019#1 | `case-ac-019-1.json` |
| 22 | B02 | 2 | AC-020#1 | `case-ac-020-1.json` |
| 23 | B02 | 3 | AC-021#1 | `case-ac-021-1.json` |
| 24 | B02 | 4 | AC-022#1 | `case-ac-022-1.json` |
| 25 | B02 | 5 | AC-023#1 | `case-ac-023-1.json` |
| 26 | B02 | 6 | AC-023#2 | `case-ac-023-2.json` |
| 27 | B02 | 7 | AC-024#1 | `case-ac-024-1.json` |
| 28 | B02 | 8 | AC-025#1 | `case-ac-025-1.json` |
| 29 | B02 | 9 | AC-026#1 | `case-ac-026-1.json` |
| 30 | B02 | 10 | AC-027#1 | `case-ac-027-1.json` |
| 31 | B02 | 11 | AC-028#1 | `case-ac-028-1.json` |
| 32 | B02 | 12 | AC-029#1 | `case-ac-029-1.json` |
| 33 | B02 | 13 | AC-030#1 | `case-ac-030-1.json` |
| 34 | B02 | 14 | AC-031#1 | `case-ac-031-1.json` |
| 35 | B02 | 15 | AC-032#1 | `case-ac-032-1.json` |
| 36 | B02 | 16 | AC-033#1 | `case-ac-033-1.json` |
| 37 | B02 | 17 | AC-034#1 | `case-ac-034-1.json` |
| 38 | B02 | 18 | AC-035#1 | `case-ac-035-1.json` |
| 39 | B02 | 19 | AC-036#1 | `case-ac-036-1.json` |
| 40 | B02 | 20 | AC-037#1 | `case-ac-037-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B02.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-019#1` / `case-ac-019-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B02.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B02.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-019-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-020-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-021-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-022-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-023-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-023-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-024-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-025-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-026-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-027-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-028-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-029-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-030-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-031-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-032-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-033-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-034-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-035-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-036-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-037-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B02"
if ($LASTEXITCODE -ne 0) { throw 'B02 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B02.json` 与 `tests/stage0c/reviewed_batches/test_audit_B02.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B02.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B02 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B02.py -q
if ($LASTEXITCODE -ne 0) { throw 'B02 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B02.json tests/stage0c/reviewed_batches/test_audit_B02.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B02"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B03：ordinals 41–60，AC-038#1 至 AC-051#3（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B03.py`、`tests/stage0c/reviewed_batches/test_audit_B03.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B03.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 41 | B03 | 1 | AC-038#1 | `case-ac-038-1.json` |
| 42 | B03 | 2 | AC-039#1 | `case-ac-039-1.json` |
| 43 | B03 | 3 | AC-040#1 | `case-ac-040-1.json` |
| 44 | B03 | 4 | AC-041#1 | `case-ac-041-1.json` |
| 45 | B03 | 5 | AC-042#1 | `case-ac-042-1.json` |
| 46 | B03 | 6 | AC-042#2 | `case-ac-042-2.json` |
| 47 | B03 | 7 | AC-043#1 | `case-ac-043-1.json` |
| 48 | B03 | 8 | AC-044#1 | `case-ac-044-1.json` |
| 49 | B03 | 9 | AC-045#1 | `case-ac-045-1.json` |
| 50 | B03 | 10 | AC-046#1 | `case-ac-046-1.json` |
| 51 | B03 | 11 | AC-047#1 | `case-ac-047-1.json` |
| 52 | B03 | 12 | AC-048#1 | `case-ac-048-1.json` |
| 53 | B03 | 13 | AC-049#1 | `case-ac-049-1.json` |
| 54 | B03 | 14 | AC-050#1 | `case-ac-050-1.json` |
| 55 | B03 | 15 | AC-050#2 | `case-ac-050-2.json` |
| 56 | B03 | 16 | AC-050#3 | `case-ac-050-3.json` |
| 57 | B03 | 17 | AC-050#4 | `case-ac-050-4.json` |
| 58 | B03 | 18 | AC-051#1 | `case-ac-051-1.json` |
| 59 | B03 | 19 | AC-051#2 | `case-ac-051-2.json` |
| 60 | B03 | 20 | AC-051#3 | `case-ac-051-3.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B03.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-038#1` / `case-ac-038-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B03.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B03.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-038-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-039-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-040-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-041-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-042-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-042-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-043-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-044-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-045-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-046-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-047-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-048-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-049-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-050-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-050-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-050-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-050-4.json'
  'fixtures/stage0c/reviewed/cases/case-ac-051-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-051-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-051-3.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B03"
if ($LASTEXITCODE -ne 0) { throw 'B03 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B03.json` 与 `tests/stage0c/reviewed_batches/test_audit_B03.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B03.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B03 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B03.py -q
if ($LASTEXITCODE -ne 0) { throw 'B03 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B03.json tests/stage0c/reviewed_batches/test_audit_B03.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B03"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B04：ordinals 61–80，AC-052#1 至 AC-066#4（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B04.py`、`tests/stage0c/reviewed_batches/test_audit_B04.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B04.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 61 | B04 | 1 | AC-052#1 | `case-ac-052-1.json` |
| 62 | B04 | 2 | AC-053#1 | `case-ac-053-1.json` |
| 63 | B04 | 3 | AC-054#1 | `case-ac-054-1.json` |
| 64 | B04 | 4 | AC-055#1 | `case-ac-055-1.json` |
| 65 | B04 | 5 | AC-056#1 | `case-ac-056-1.json` |
| 66 | B04 | 6 | AC-057#1 | `case-ac-057-1.json` |
| 67 | B04 | 7 | AC-058#1 | `case-ac-058-1.json` |
| 68 | B04 | 8 | AC-058#2 | `case-ac-058-2.json` |
| 69 | B04 | 9 | AC-059#1 | `case-ac-059-1.json` |
| 70 | B04 | 10 | AC-060#1 | `case-ac-060-1.json` |
| 71 | B04 | 11 | AC-060#2 | `case-ac-060-2.json` |
| 72 | B04 | 12 | AC-061#1 | `case-ac-061-1.json` |
| 73 | B04 | 13 | AC-062#1 | `case-ac-062-1.json` |
| 74 | B04 | 14 | AC-063#1 | `case-ac-063-1.json` |
| 75 | B04 | 15 | AC-064#1 | `case-ac-064-1.json` |
| 76 | B04 | 16 | AC-065#1 | `case-ac-065-1.json` |
| 77 | B04 | 17 | AC-066#1 | `case-ac-066-1.json` |
| 78 | B04 | 18 | AC-066#2 | `case-ac-066-2.json` |
| 79 | B04 | 19 | AC-066#3 | `case-ac-066-3.json` |
| 80 | B04 | 20 | AC-066#4 | `case-ac-066-4.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B04.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-052#1` / `case-ac-052-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B04.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B04.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-052-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-053-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-054-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-055-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-056-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-057-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-058-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-058-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-059-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-060-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-060-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-061-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-062-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-063-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-064-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-065-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-066-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-066-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-066-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-066-4.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B04"
if ($LASTEXITCODE -ne 0) { throw 'B04 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B04.json` 与 `tests/stage0c/reviewed_batches/test_audit_B04.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B04.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B04 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B04.py -q
if ($LASTEXITCODE -ne 0) { throw 'B04 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B04.json tests/stage0c/reviewed_batches/test_audit_B04.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B04"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B05：ordinals 81–100，AC-066#5 至 AC-079#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B05.py`、`tests/stage0c/reviewed_batches/test_audit_B05.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B05.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 81 | B05 | 1 | AC-066#5 | `case-ac-066-5.json` |
| 82 | B05 | 2 | AC-066#6 | `case-ac-066-6.json` |
| 83 | B05 | 3 | AC-067#1 | `case-ac-067-1.json` |
| 84 | B05 | 4 | AC-068#1 | `case-ac-068-1.json` |
| 85 | B05 | 5 | AC-069#1 | `case-ac-069-1.json` |
| 86 | B05 | 6 | AC-069#2 | `case-ac-069-2.json` |
| 87 | B05 | 7 | AC-069#3 | `case-ac-069-3.json` |
| 88 | B05 | 8 | AC-070#1 | `case-ac-070-1.json` |
| 89 | B05 | 9 | AC-070#2 | `case-ac-070-2.json` |
| 90 | B05 | 10 | AC-071#1 | `case-ac-071-1.json` |
| 91 | B05 | 11 | AC-072#1 | `case-ac-072-1.json` |
| 92 | B05 | 12 | AC-073#1 | `case-ac-073-1.json` |
| 93 | B05 | 13 | AC-073#2 | `case-ac-073-2.json` |
| 94 | B05 | 14 | AC-074#1 | `case-ac-074-1.json` |
| 95 | B05 | 15 | AC-075#1 | `case-ac-075-1.json` |
| 96 | B05 | 16 | AC-076#1 | `case-ac-076-1.json` |
| 97 | B05 | 17 | AC-076#2 | `case-ac-076-2.json` |
| 98 | B05 | 18 | AC-077#1 | `case-ac-077-1.json` |
| 99 | B05 | 19 | AC-078#1 | `case-ac-078-1.json` |
| 100 | B05 | 20 | AC-079#1 | `case-ac-079-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B05.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-066#5` / `case-ac-066-5.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B05.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B05.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-066-5.json'
  'fixtures/stage0c/reviewed/cases/case-ac-066-6.json'
  'fixtures/stage0c/reviewed/cases/case-ac-067-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-068-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-069-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-069-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-069-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-070-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-070-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-071-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-072-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-073-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-073-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-074-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-075-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-076-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-076-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-077-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-078-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-079-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B05"
if ($LASTEXITCODE -ne 0) { throw 'B05 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B05.json` 与 `tests/stage0c/reviewed_batches/test_audit_B05.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B05.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B05 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B05.py -q
if ($LASTEXITCODE -ne 0) { throw 'B05 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B05.json tests/stage0c/reviewed_batches/test_audit_B05.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B05"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B06：ordinals 101–120，AC-080#1 至 AC-093#3（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B06.py`、`tests/stage0c/reviewed_batches/test_audit_B06.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B06.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 101 | B06 | 1 | AC-080#1 | `case-ac-080-1.json` |
| 102 | B06 | 2 | AC-081#1 | `case-ac-081-1.json` |
| 103 | B06 | 3 | AC-081#2 | `case-ac-081-2.json` |
| 104 | B06 | 4 | AC-082#1 | `case-ac-082-1.json` |
| 105 | B06 | 5 | AC-083#1 | `case-ac-083-1.json` |
| 106 | B06 | 6 | AC-084#1 | `case-ac-084-1.json` |
| 107 | B06 | 7 | AC-085#1 | `case-ac-085-1.json` |
| 108 | B06 | 8 | AC-086#1 | `case-ac-086-1.json` |
| 109 | B06 | 9 | AC-087#1 | `case-ac-087-1.json` |
| 110 | B06 | 10 | AC-087#2 | `case-ac-087-2.json` |
| 111 | B06 | 11 | AC-088#1 | `case-ac-088-1.json` |
| 112 | B06 | 12 | AC-088#2 | `case-ac-088-2.json` |
| 113 | B06 | 13 | AC-088#3 | `case-ac-088-3.json` |
| 114 | B06 | 14 | AC-089#1 | `case-ac-089-1.json` |
| 115 | B06 | 15 | AC-090#1 | `case-ac-090-1.json` |
| 116 | B06 | 16 | AC-091#1 | `case-ac-091-1.json` |
| 117 | B06 | 17 | AC-092#1 | `case-ac-092-1.json` |
| 118 | B06 | 18 | AC-093#1 | `case-ac-093-1.json` |
| 119 | B06 | 19 | AC-093#2 | `case-ac-093-2.json` |
| 120 | B06 | 20 | AC-093#3 | `case-ac-093-3.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B06.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-080#1` / `case-ac-080-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B06.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B06.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-080-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-081-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-081-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-082-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-083-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-084-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-085-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-086-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-087-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-087-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-088-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-088-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-088-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-089-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-090-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-091-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-092-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-093-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-093-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-093-3.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B06"
if ($LASTEXITCODE -ne 0) { throw 'B06 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B06.json` 与 `tests/stage0c/reviewed_batches/test_audit_B06.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B06.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B06 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B06.py -q
if ($LASTEXITCODE -ne 0) { throw 'B06 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B06.json tests/stage0c/reviewed_batches/test_audit_B06.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B06"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B07：ordinals 121–140，AC-094#1 至 DEL-02#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B07.py`、`tests/stage0c/reviewed_batches/test_audit_B07.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B07.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 121 | B07 | 1 | AC-094#1 | `case-ac-094-1.json` |
| 122 | B07 | 2 | AC-095#1 | `case-ac-095-1.json` |
| 123 | B07 | 3 | AC-095#2 | `case-ac-095-2.json` |
| 124 | B07 | 4 | AC-095#3 | `case-ac-095-3.json` |
| 125 | B07 | 5 | BR-01#1 | `case-br-01-1.json` |
| 126 | B07 | 6 | BR-02#1 | `case-br-02-1.json` |
| 127 | B07 | 7 | BR-03#1 | `case-br-03-1.json` |
| 128 | B07 | 8 | BR-03#2 | `case-br-03-2.json` |
| 129 | B07 | 9 | BR-04#1 | `case-br-04-1.json` |
| 130 | B07 | 10 | BR-05#1 | `case-br-05-1.json` |
| 131 | B07 | 11 | COR-01#1 | `case-cor-01-1.json` |
| 132 | B07 | 12 | COR-02#1 | `case-cor-02-1.json` |
| 133 | B07 | 13 | COR-03#1 | `case-cor-03-1.json` |
| 134 | B07 | 14 | COR-04#1 | `case-cor-04-1.json` |
| 135 | B07 | 15 | COR-05#1 | `case-cor-05-1.json` |
| 136 | B07 | 16 | COR-06#1 | `case-cor-06-1.json` |
| 137 | B07 | 17 | COR-07#1 | `case-cor-07-1.json` |
| 138 | B07 | 18 | COR-08#1 | `case-cor-08-1.json` |
| 139 | B07 | 19 | DEL-01#1 | `case-del-01-1.json` |
| 140 | B07 | 20 | DEL-02#1 | `case-del-02-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B07.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `AC-094#1` / `case-ac-094-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B07.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B07.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-094-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-095-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-095-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-095-3.json'
  'fixtures/stage0c/reviewed/cases/case-br-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-br-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-br-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-br-03-2.json'
  'fixtures/stage0c/reviewed/cases/case-br-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-br-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-cor-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-del-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-del-02-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B07"
if ($LASTEXITCODE -ne 0) { throw 'B07 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B07.json` 与 `tests/stage0c/reviewed_batches/test_audit_B07.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B07.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B07 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B07.py -q
if ($LASTEXITCODE -ne 0) { throw 'B07 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B07.json tests/stage0c/reviewed_batches/test_audit_B07.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B07"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B08：ordinals 141–160，DEL-03#1 至 EXIT-10#3（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B08.py`、`tests/stage0c/reviewed_batches/test_audit_B08.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B08.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 141 | B08 | 1 | DEL-03#1 | `case-del-03-1.json` |
| 142 | B08 | 2 | DEL-04#1 | `case-del-04-1.json` |
| 143 | B08 | 3 | DEL-05#1 | `case-del-05-1.json` |
| 144 | B08 | 4 | EXIT-01#1 | `case-exit-01-1.json` |
| 145 | B08 | 5 | EXIT-02#1 | `case-exit-02-1.json` |
| 146 | B08 | 6 | EXIT-02#2 | `case-exit-02-2.json` |
| 147 | B08 | 7 | EXIT-03#1 | `case-exit-03-1.json` |
| 148 | B08 | 8 | EXIT-03#2 | `case-exit-03-2.json` |
| 149 | B08 | 9 | EXIT-03#3 | `case-exit-03-3.json` |
| 150 | B08 | 10 | EXIT-04#1 | `case-exit-04-1.json` |
| 151 | B08 | 11 | EXIT-05#1 | `case-exit-05-1.json` |
| 152 | B08 | 12 | EXIT-06#1 | `case-exit-06-1.json` |
| 153 | B08 | 13 | EXIT-06#2 | `case-exit-06-2.json` |
| 154 | B08 | 14 | EXIT-06#3 | `case-exit-06-3.json` |
| 155 | B08 | 15 | EXIT-07#1 | `case-exit-07-1.json` |
| 156 | B08 | 16 | EXIT-08#1 | `case-exit-08-1.json` |
| 157 | B08 | 17 | EXIT-09#1 | `case-exit-09-1.json` |
| 158 | B08 | 18 | EXIT-10#1 | `case-exit-10-1.json` |
| 159 | B08 | 19 | EXIT-10#2 | `case-exit-10-2.json` |
| 160 | B08 | 20 | EXIT-10#3 | `case-exit-10-3.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B08.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `DEL-03#1` / `case-del-03-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B08.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B08.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-del-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-del-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-del-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-02-2.json'
  'fixtures/stage0c/reviewed/cases/case-exit-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-03-2.json'
  'fixtures/stage0c/reviewed/cases/case-exit-03-3.json'
  'fixtures/stage0c/reviewed/cases/case-exit-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-06-2.json'
  'fixtures/stage0c/reviewed/cases/case-exit-06-3.json'
  'fixtures/stage0c/reviewed/cases/case-exit-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-09-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-10-1.json'
  'fixtures/stage0c/reviewed/cases/case-exit-10-2.json'
  'fixtures/stage0c/reviewed/cases/case-exit-10-3.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B08"
if ($LASTEXITCODE -ne 0) { throw 'B08 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B08.json` 与 `tests/stage0c/reviewed_batches/test_audit_B08.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B08.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B08 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B08.py -q
if ($LASTEXITCODE -ne 0) { throw 'B08 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B08.json tests/stage0c/reviewed_batches/test_audit_B08.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B08"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B09：ordinals 161–180，GROW-01#1 至 INJ-06#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B09.py`、`tests/stage0c/reviewed_batches/test_audit_B09.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B09.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 161 | B09 | 1 | GROW-01#1 | `case-grow-01-1.json` |
| 162 | B09 | 2 | GROW-02#1 | `case-grow-02-1.json` |
| 163 | B09 | 3 | GROW-03#1 | `case-grow-03-1.json` |
| 164 | B09 | 4 | GROW-04#1 | `case-grow-04-1.json` |
| 165 | B09 | 5 | GROW-05#1 | `case-grow-05-1.json` |
| 166 | B09 | 6 | GROW-06#1 | `case-grow-06-1.json` |
| 167 | B09 | 7 | ID-01#1 | `case-id-01-1.json` |
| 168 | B09 | 8 | ID-02#1 | `case-id-02-1.json` |
| 169 | B09 | 9 | ID-03#1 | `case-id-03-1.json` |
| 170 | B09 | 10 | ID-04#1 | `case-id-04-1.json` |
| 171 | B09 | 11 | ID-04#2 | `case-id-04-2.json` |
| 172 | B09 | 12 | ID-04#3 | `case-id-04-3.json` |
| 173 | B09 | 13 | ID-05#1 | `case-id-05-1.json` |
| 174 | B09 | 14 | ID-06#1 | `case-id-06-1.json` |
| 175 | B09 | 15 | INJ-01#1 | `case-inj-01-1.json` |
| 176 | B09 | 16 | INJ-02#1 | `case-inj-02-1.json` |
| 177 | B09 | 17 | INJ-03#1 | `case-inj-03-1.json` |
| 178 | B09 | 18 | INJ-04#1 | `case-inj-04-1.json` |
| 179 | B09 | 19 | INJ-05#1 | `case-inj-05-1.json` |
| 180 | B09 | 20 | INJ-06#1 | `case-inj-06-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B09.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `GROW-01#1` / `case-grow-01-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B09.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B09.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-grow-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-grow-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-grow-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-grow-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-grow-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-grow-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-04-2.json'
  'fixtures/stage0c/reviewed/cases/case-id-04-3.json'
  'fixtures/stage0c/reviewed/cases/case-id-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-id-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-06-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B09"
if ($LASTEXITCODE -ne 0) { throw 'B09 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B09.json` 与 `tests/stage0c/reviewed_batches/test_audit_B09.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B09.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B09 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B09.py -q
if ($LASTEXITCODE -ne 0) { throw 'B09 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B09.json tests/stage0c/reviewed_batches/test_audit_B09.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B09"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B10：ordinals 181–200，INJ-07#1 至 PRO-07#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B10.py`、`tests/stage0c/reviewed_batches/test_audit_B10.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B10.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 181 | B10 | 1 | INJ-07#1 | `case-inj-07-1.json` |
| 182 | B10 | 2 | INJ-08#1 | `case-inj-08-1.json` |
| 183 | B10 | 3 | INJ-09#1 | `case-inj-09-1.json` |
| 184 | B10 | 4 | INJ-10#1 | `case-inj-10-1.json` |
| 185 | B10 | 5 | MEM-01#1 | `case-mem-01-1.json` |
| 186 | B10 | 6 | MEM-02#1 | `case-mem-02-1.json` |
| 187 | B10 | 7 | MEM-03#1 | `case-mem-03-1.json` |
| 188 | B10 | 8 | MEM-04#1 | `case-mem-04-1.json` |
| 189 | B10 | 9 | MEM-05#1 | `case-mem-05-1.json` |
| 190 | B10 | 10 | MEM-06#1 | `case-mem-06-1.json` |
| 191 | B10 | 11 | MEM-07#1 | `case-mem-07-1.json` |
| 192 | B10 | 12 | MEM-08#1 | `case-mem-08-1.json` |
| 193 | B10 | 13 | PRO-01#1 | `case-pro-01-1.json` |
| 194 | B10 | 14 | PRO-02#1 | `case-pro-02-1.json` |
| 195 | B10 | 15 | PRO-03#1 | `case-pro-03-1.json` |
| 196 | B10 | 16 | PRO-04#1 | `case-pro-04-1.json` |
| 197 | B10 | 17 | PRO-05#1 | `case-pro-05-1.json` |
| 198 | B10 | 18 | PRO-06#1 | `case-pro-06-1.json` |
| 199 | B10 | 19 | PRO-06#2 | `case-pro-06-2.json` |
| 200 | B10 | 20 | PRO-07#1 | `case-pro-07-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B10.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `INJ-07#1` / `case-inj-07-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B10.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B10.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-inj-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-09-1.json'
  'fixtures/stage0c/reviewed/cases/case-inj-10-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-mem-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-06-2.json'
  'fixtures/stage0c/reviewed/cases/case-pro-07-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B10"
if ($LASTEXITCODE -ne 0) { throw 'B10 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B10.json` 与 `tests/stage0c/reviewed_batches/test_audit_B10.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B10.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B10 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B10.py -q
if ($LASTEXITCODE -ne 0) { throw 'B10 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B10.json tests/stage0c/reviewed_batches/test_audit_B10.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B10"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B11：ordinals 201–220，PRO-08#1 至 SEC-02#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B11.py`、`tests/stage0c/reviewed_batches/test_audit_B11.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B11.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 201 | B11 | 1 | PRO-08#1 | `case-pro-08-1.json` |
| 202 | B11 | 2 | PRO-09#1 | `case-pro-09-1.json` |
| 203 | B11 | 3 | PRO-10#1 | `case-pro-10-1.json` |
| 204 | B11 | 4 | PRO-11#1 | `case-pro-11-1.json` |
| 205 | B11 | 5 | PRO-12#1 | `case-pro-12-1.json` |
| 206 | B11 | 6 | REL-01#1 | `case-rel-01-1.json` |
| 207 | B11 | 7 | REL-02#1 | `case-rel-02-1.json` |
| 208 | B11 | 8 | REL-03#1 | `case-rel-03-1.json` |
| 209 | B11 | 9 | REL-04#1 | `case-rel-04-1.json` |
| 210 | B11 | 10 | REL-05#1 | `case-rel-05-1.json` |
| 211 | B11 | 11 | REL-06#1 | `case-rel-06-1.json` |
| 212 | B11 | 12 | REL-07#1 | `case-rel-07-1.json` |
| 213 | B11 | 13 | REL-08#1 | `case-rel-08-1.json` |
| 214 | B11 | 14 | REL-09#1 | `case-rel-09-1.json` |
| 215 | B11 | 15 | REL-10#1 | `case-rel-10-1.json` |
| 216 | B11 | 16 | REL-11#1 | `case-rel-11-1.json` |
| 217 | B11 | 17 | REL-12#1 | `case-rel-12-1.json` |
| 218 | B11 | 18 | REL-12#2 | `case-rel-12-2.json` |
| 219 | B11 | 19 | SEC-01#1 | `case-sec-01-1.json` |
| 220 | B11 | 20 | SEC-02#1 | `case-sec-02-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B11.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `PRO-08#1` / `case-pro-08-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B11.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B11.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-pro-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-09-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-10-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-11-1.json'
  'fixtures/stage0c/reviewed/cases/case-pro-12-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-09-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-10-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-11-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-12-1.json'
  'fixtures/stage0c/reviewed/cases/case-rel-12-2.json'
  'fixtures/stage0c/reviewed/cases/case-sec-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-sec-02-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B11"
if ($LASTEXITCODE -ne 0) { throw 'B11 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B11.json` 与 `tests/stage0c/reviewed_batches/test_audit_B11.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B11.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B11 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B11.py -q
if ($LASTEXITCODE -ne 0) { throw 'B11 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B11.json tests/stage0c/reviewed_batches/test_audit_B11.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B11"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B12：ordinals 221–240，SEC-03#1 至 TOOL-01#1（20 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B12.py`、`tests/stage0c/reviewed_batches/test_audit_B12.py`、下表 20 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B12.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 221 | B12 | 1 | SEC-03#1 | `case-sec-03-1.json` |
| 222 | B12 | 2 | SEC-04#1 | `case-sec-04-1.json` |
| 223 | B12 | 3 | SEC-05#1 | `case-sec-05-1.json` |
| 224 | B12 | 4 | SEC-06#1 | `case-sec-06-1.json` |
| 225 | B12 | 5 | SEC-06#2 | `case-sec-06-2.json` |
| 226 | B12 | 6 | SRC-01#1 | `case-src-01-1.json` |
| 227 | B12 | 7 | SRC-02#1 | `case-src-02-1.json` |
| 228 | B12 | 8 | SRC-03#1 | `case-src-03-1.json` |
| 229 | B12 | 9 | SRC-04#1 | `case-src-04-1.json` |
| 230 | B12 | 10 | SRC-05#1 | `case-src-05-1.json` |
| 231 | B12 | 11 | SRC-06#1 | `case-src-06-1.json` |
| 232 | B12 | 12 | TIME-01#1 | `case-time-01-1.json` |
| 233 | B12 | 13 | TIME-02#1 | `case-time-02-1.json` |
| 234 | B12 | 14 | TIME-03#1 | `case-time-03-1.json` |
| 235 | B12 | 15 | TIME-03#2 | `case-time-03-2.json` |
| 236 | B12 | 16 | TIME-04#1 | `case-time-04-1.json` |
| 237 | B12 | 17 | TIME-04#2 | `case-time-04-2.json` |
| 238 | B12 | 18 | TIME-05#1 | `case-time-05-1.json` |
| 239 | B12 | 19 | TIME-06#1 | `case-time-06-1.json` |
| 240 | B12 | 20 | TOOL-01#1 | `case-tool-01-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B12.py -q
```

Expected: 仅因本表 20 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `SEC-03#1` / `case-sec-03-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 20 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B12.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B12.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-sec-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-sec-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-sec-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-sec-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-sec-06-2.json'
  'fixtures/stage0c/reviewed/cases/case-src-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-src-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-src-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-src-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-src-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-src-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-03-2.json'
  'fixtures/stage0c/reviewed/cases/case-time-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-04-2.json'
  'fixtures/stage0c/reviewed/cases/case-time-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-time-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-01-1.json'
)
if ($casePaths.Count -ne 20) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B12"
if ($LASTEXITCODE -ne 0) { throw 'B12 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 20 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B12.json` 与 `tests/stage0c/reviewed_batches/test_audit_B12.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B12.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B12 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B12.py -q
if ($LASTEXITCODE -ne 0) { throw 'B12 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B12.json tests/stage0c/reviewed_batches/test_audit_B12.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B12"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task B13：ordinals 241–259，TOOL-02#1 至 USE-05#1（19 cases）

**Files:** `tests/stage0c/reviewed_batches/test_batch_B13.py`、`tests/stage0c/reviewed_batches/test_audit_B13.py`、下表 19 个 reviewed files，以及 tracked review record `outputs/verification/stage0c-reviewed-batches/B13.json`。

| ordinal | batch_id | batch_ordinal | exact clause ID | exact filename |
|---:|---|---:|---|---|
| 241 | B13 | 1 | TOOL-02#1 | `case-tool-02-1.json` |
| 242 | B13 | 2 | TOOL-03#1 | `case-tool-03-1.json` |
| 243 | B13 | 3 | TOOL-04#1 | `case-tool-04-1.json` |
| 244 | B13 | 4 | TOOL-05#1 | `case-tool-05-1.json` |
| 245 | B13 | 5 | TOOL-06#1 | `case-tool-06-1.json` |
| 246 | B13 | 6 | TOOL-06#2 | `case-tool-06-2.json` |
| 247 | B13 | 7 | TOOL-07#1 | `case-tool-07-1.json` |
| 248 | B13 | 8 | TOOL-08#1 | `case-tool-08-1.json` |
| 249 | B13 | 9 | TOOL-09#1 | `case-tool-09-1.json` |
| 250 | B13 | 10 | TOOL-10#1 | `case-tool-10-1.json` |
| 251 | B13 | 11 | TOOL-11#1 | `case-tool-11-1.json` |
| 252 | B13 | 12 | TOOL-12#1 | `case-tool-12-1.json` |
| 253 | B13 | 13 | TOOL-13#1 | `case-tool-13-1.json` |
| 254 | B13 | 14 | TOOL-14#1 | `case-tool-14-1.json` |
| 255 | B13 | 15 | USE-01#1 | `case-use-01-1.json` |
| 256 | B13 | 16 | USE-02#1 | `case-use-02-1.json` |
| 257 | B13 | 17 | USE-03#1 | `case-use-03-1.json` |
| 258 | B13 | 18 | USE-04#1 | `case-use-04-1.json` |
| 259 | B13 | 19 | USE-05#1 | `case-use-05-1.json` |


- [ ] **Batch RED：锁定 literal ordered rows**

创建完整 `EXPECTED_ROWS` tuple 与参数化单案 test；先运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B13.py -q
```

Expected: 仅因本表 19 个 reviewed paths 尚缺席而 FAIL；ordinal、batch ordinal、clause ID 与 filename 断言本身必须通过。

- [ ] **逐案 Author RED → independent Reviewer GREEN**

从 `TOOL-02#1` / `case-tool-02-1.json` 开始，逐行执行第 7 节的单案协议。Author 文件只缺 `reviewer` 时，同一参数 node 的 failure repr 必须精确且只含 `reviewer_missing`；不同 reviewer 完成语义复核并填写 reviewer object 后，同一 node 必须 `1 passed`。不得在前一案转绿前开始下一案。

- [ ] **Batch GREEN：关闭本批 ordered validator**

全部 19 案完成后，批次 test 组装完整 rows，调用 `validate_reviewed_batch(rows, checklist_rows, frozen_clauses_by_id, fixture_schema)` 并断言 `[]`，同时比较 ordered `(ordinal,batch_id,batch_ordinal,clause_id,reviewed_path)`：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B13.py tests/stage0c/test_reviewed.py -q
```

Expected: PASS。

- [ ] **Data commit A：只提交 reviewed payload**

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B13.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-tool-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-05-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-06-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-06-2.json'
  'fixtures/stage0c/reviewed/cases/case-tool-07-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-08-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-09-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-10-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-11-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-12-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-13-1.json'
  'fixtures/stage0c/reviewed/cases/case-tool-14-1.json'
  'fixtures/stage0c/reviewed/cases/case-use-01-1.json'
  'fixtures/stage0c/reviewed/cases/case-use-02-1.json'
  'fixtures/stage0c/reviewed/cases/case-use-03-1.json'
  'fixtures/stage0c/reviewed/cases/case-use-04-1.json'
  'fixtures/stage0c/reviewed/cases/case-use-05-1.json'
)
if ($casePaths.Count -ne 19) { throw 'batch path count mismatch' }
git add -- $batchTest $casePaths
git diff --cached --check
git diff --cached --name-only
git commit -m "data(stage0c): review conversion batch B13"
if ($LASTEXITCODE -ne 0) { throw 'B13 data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
Write-Output ("reviewed_commit=" + $reviewedCommit)
```

`git diff --cached --name-only` 的 exact set 必须是该 batch test 加上述 19 个 paths；不得含 record、audit test、generated 或其他 batch 文件。

- [ ] **Audit RED：创建 tracked review record 与可追溯 test**

创建 `outputs/verification/stage0c-reviewed-batches/B13.json` 与 `tests/stage0c/reviewed_batches/test_audit_B13.py`。record 的 `reviewed_commit` 必须复制 Data commit A fence stdout 中 `reviewed_commit=` 后的 40 位 literal；不得引用前一 fence 的 PowerShell 变量；`case_reviews` 按本表 ordinal 排序，逐案记录 author/reviewer 角色。audit test 必须调用 `validate_batch_review_record`，再用 `git cat-file`、`git merge-base --is-ancestor`、`git diff-tree` 与 `git show` 证明 commit 存在、是当前 `HEAD` 的祖先、commit path set 精确、commit 内 case bytes 等于当前 bytes。

- [ ] **Audit GREEN 与 commit B**

```powershell
$expectedReviewedCommit = (git rev-parse HEAD).Trim()
if ($expectedReviewedCommit -cnotmatch '^[0-9a-f]{40}$') {
  throw 'reviewed commit invalid'
}
$recordPath = 'outputs/verification/stage0c-reviewed-batches/B13.json'
$record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 |
  ConvertFrom-Json
if (
  ($record.reviewed_commit -isnot [string]) -or
  ($record.reviewed_commit -cne $expectedReviewedCommit)
) {
  throw 'B13 record reviewed_commit does not equal current data commit'
}
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B13.py -q
if ($LASTEXITCODE -ne 0) { throw 'B13 audit test failed' }
git add -- outputs/verification/stage0c-reviewed-batches/B13.json tests/stage0c/reviewed_batches/test_audit_B13.py
git diff --cached --check
git diff --cached --name-only
git commit -m "audit(stage0c): record conversion review batch B13"
```

Expected: test PASS；暂存 exact set 只有 record 与 audit test。commit B 后禁止 rebase/squash commit A；历史一旦重写，audit test 必须失败并要求重新建立 record。

### Task F10：关闭 exact 259 reviewed set 与 13 个 audit records

**Files:**
- Create: `tests/stage0c/test_current_reviewed.py`
- Create: `tests/stage0c/test_batch_review_records.py`

- [ ] **Step 1: 写 ordered reviewed closure gate**

```python
def test_current_reviewed_closes_ordered_checklist(
    repository_root,
    frozen_inputs,
    fixture_schema,
) -> None:
    checklist = build_conversion_checklist(frozen_inputs)
    reviewed_rows = []
    for expected_ordinal, checklist_row in enumerate(checklist["cases"], start=1):
        assert checklist_row["ordinal"] == expected_ordinal
        assert checklist_row["batch_id"] == f"B{((expected_ordinal - 1) // 20) + 1:02d}"
        assert checklist_row["batch_ordinal"] == ((expected_ordinal - 1) % 20) + 1
        path = repository_root / checklist_row["reviewed_path"]
        assert path.is_file() and not path.is_symlink()
        reviewed = load_reviewed_case(path)
        reviewed_rows.append(reviewed)
    assert validate_reviewed_closed_set(
        reviewed_rows,
        checklist,
        frozen_inputs.clauses_by_id,
        fixture_schema,
    ) == []
```

测试另比较 exact ordered clause/case/path arrays；把相同 oracle profile 的两个 reviewed bodies/mappings 对调、遗漏一个 stimulus params pointer、遗漏 required oracle mapping、删除 reviewer、增加 top-level field，分别要求稳定错误码，其中删除 reviewer 必须只产生 `reviewer_missing`。

- [ ] **Step 2: 写 13-record exact closure 与 Git 可追溯门**

`tests/stage0c/test_batch_review_records.py` 构造 exact paths `B01.json`…`B13.json`，拒绝 missing/duplicate/unexpected；按 checklist 分割为 12×20+19，逐个调用 `validate_batch_review_record`。再对每个 record 重复 batch audit test 的 `cat-file/merge-base --is-ancestor/diff-tree/show` 检查，证明：

1. `reviewed_commit` 是可达 commit；
2. commit exact paths 仅为对应 literal batch test 与 20/19 cases；
3. commit 中每个 case bytes 等于当前 bytes；
4. record reviewer_id/reviewed_at 等于 reviewed JSON；
5. author_id 与 reviewer_id 非空且不相等；
6. 13 个 records 合计正好覆盖 259 个 ordinals，顺序 1…259。

在同一测试文件中定义并复用以下 reachability gate；13-record 聚合检查逐条调用它：

```python
def _assert_reviewed_commit_is_head_ancestor(
    repository_root: Path,
    commit: str,
) -> None:
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    assert reachable.returncode == 0, "reviewed_commit_not_head_ancestor"
```

再增加隔离回归 `test_reviewed_commit_object_that_is_not_head_ancestor_is_rejected`：在
`tmp_path` 初始化 Git 仓库并提交 `main` 基线；从基线建立 `review-history` 分支并产生
`reviewed_commit`，随后切回 `main`。先断言
`git cat-file -e <reviewed_commit>^{commit}` 返回 0，再断言上述 gate 以
`reviewed_commit_not_head_ancestor` 失败。该测试必须证明“对象仍存在”不足以通过门，
且不得读取或改写真实仓库的引用。

- [ ] **Step 3: 锁定聚合计数**

锁定 group clause counts：Core 124、baseline 59、increment 76；oracle combination counts：D=110、D+H=41、D+S=98、H=6、H+J=4；S=98、H=51、J=4 与 H/J requirements=55。

- [ ] **Step 4: 运行关闭门并重读 hash**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_current_reviewed.py tests/stage0c/test_batch_review_records.py tests/stage0c/reviewed_batches tests/stage0c/test_reviewed.py -q
git diff --check
```

Expected: PASS。测试在 `tmp_path` round-trip 259 个完整 reviewed canonical files 与 13 个 review records，重读 bytes/hash 必须逐文件相等。

- [ ] **Step 5: 显式暂存与提交**

```powershell
git add -- tests/stage0c/test_current_reviewed.py tests/stage0c/test_batch_review_records.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): close reviewed conversion and audit sets"
```

## 8. Static registry 与 S Sandbox

### Task R01：静态 handler registry

**Files:**
- Create: `tools/stage0c_fixtures/handlers.py`
- Create: `tests/stage0c/test_handlers.py`

- [ ] **Red code:** 在测试中定义完整 `EXPECTED_HANDLER_KINDS`：

```python
EXPECTED_HANDLER_KINDS = {
    "sandbox.seed_state": "setup",
    "sandbox.set_clock": "setup",
    "sandbox.configure_core_driver": "setup",
    "sandbox.configure_adapter": "setup",
    "sandbox.seed_backend_response": "setup",
    "core.command": "stimulus",
    "core.query": "stimulus",
    "external.action": "stimulus",
    "backend.replay": "stimulus",
    "receipt.status": "assertion",
    "receipt.error_code": "assertion",
    "state.path_equals": "assertion",
    "state.hash_unchanged": "assertion",
    "effect.includes": "assertion",
    "effect.excludes": "assertion",
    "output.contains": "assertion",
    "output.omits": "assertion",
    "replay.equals": "assertion",
}


def test_registry_is_static_and_complete() -> None:
    assert {key: value.kind for key, value in HANDLER_REGISTRY.items()} == (
        EXPECTED_HANDLER_KINDS
    )
    assert all(value.params_schema_key == key for key, value in HANDLER_REGISTRY.items())
```

另以 JSON mutation `module/import_path/expression/script/callable` 断言 `dynamic_handler_target_forbidden`。

- [ ] **Run red:**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handlers.py -q
```

Expected: FAIL，`handlers.py` 缺席。

- [ ] **Minimal implementation:** 定义 `SetupHandler/StimulusHandler/AssertionHandler` protocols、不可变 `HandlerRegistration` 与 18-key literal dict；registry entry 只持有 handler object、kind、params schema key 和 implementation source path，不从 JSON import。

- [ ] **Green + fingerprint reread:**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handlers.py -q
git diff --check
```

测试把 `{handler_id,kind,params_schema_key,implementation_source_path}` array 写入 `tmp_path`、重读并重算 SHA-256；插入第 19 个 key 必须失败。

- [ ] **Explicit commit:**

```powershell
git add tools/stage0c_fixtures/handlers.py tests/stage0c/test_handlers.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add static handler registry"
```

### Task R02：SandboxContext、reset 与 setup

[FRAME｜置信度：高] R02 分为两个独立叶；R02-A 不实现 setup handler，R02-B 不再改变 fresh/reset 合同。

#### R02-A：fresh context 与 reset 的完整资源边界

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_context.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_context.py::test_fresh_context_has_exact_initial_resources
tests/stage0c/test_sandbox_context.py::test_reset_clears_all_case_scoped_resources
tests/stage0c/test_sandbox_context.py::test_two_equal_case_ids_never_share_mutable_resources
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_context.py::test_fresh_context_has_exact_initial_resources -q
```

Expected: FAIL，缺少 `SandboxContext/create_context/reset_context`；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
create_context(case_id: str, tmp_root: Path, profile: JsonObject | None) -> SandboxContext
reset_context(context: SandboxContext) -> None
snapshot_state(context: SandboxContext) -> StateSnapshot
```

fresh context 精确持有独立 temp root、`{"records":{}}` 深拷贝、固定时钟、确定性 ID allocator、case-scope cache，以及 R02-A 唯一拥有的零行为 carrier：`FakeCoreDriver(results_by_ref,consumed_refs)` 与四个 `FakeAdapter(adapter_id,kind,results_by_ref,recorded_calls)`。本叶只定义字段、fresh/reset 生命周期与 inert 初态，不实现 `take/backend` 行为；R02-B 可原子填充 carrier 字段，R03 只能在同一类型上增加行为，禁止重建第二套 driver/adapter 类。reset 必须清空 state/effects/cache/seeded results/allocator/temp children 与全部 carrier containers，再重建精确初态；不复用任何 mutable container。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_context.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

在 context A 填入 state、effect、cache、driver result 与临时文件，reset A 后逐项为空；context B 的 canonical snapshot bytes/hash 前后不变。关闭两者后 temp roots 均缺席。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_context.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add fresh sandbox context and reset"
```


#### R02-B：五类 setup handler、cardinality 与 atomic setup

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_context.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_context.py::test_setup_handlers_enforce_exact_cardinality_and_identity
tests/stage0c/test_sandbox_context.py::test_setup_validation_failure_commits_nothing
tests/stage0c/test_sandbox_context.py::test_setup_result_cross_field_invariants
tests/stage0c/test_sandbox_context.py::test_setup_seeds_fakes_without_consuming_results
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_context.py::test_setup_handlers_enforce_exact_cardinality_and_identity -q
```

Expected: FAIL，缺少 setup validation/execution；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
validate_setup_steps(context: SandboxContext, steps: list[JsonObject], profile: JsonObject | None) -> list[ValidationIssue]
execute_setup_steps(context: SandboxContext, steps: list[JsonObject]) -> SetupResult
```

literal 表覆盖 `sandbox.seed_state/set_clock/configure_core_driver/configure_adapter/seed_backend_response`。seed_state、clock、core driver 每 case 最多一次；每 adapter 最多一次；record_id/result_ref/replay_key 全局唯一；clock 必须等于 profile；adapter/core seeded effect adapter_id 必须匹配。先验证全部 steps，再在副本执行并一次提交；本叶唯一实现 `FakeCoreDriver.configure`、`FakeAdapter.configure` 与 backend seed 安装/seed-store，必须证明 consumed_refs 与 recorded_calls 仍为空，不得提前实现 R03 的 take。SetupResult completed 时 error_code/error_message 均 null，failed 时二者均为非空稳定字符串。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_context.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对第二次 seed/clock/core configure、重复 adapter、duplicate record/result/replay key、clock mismatch 与 adapter_id mismatch 逐项 mutation；每行 state/effects/cache/driver canonical bytes 与调用前完全相等。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_context.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): execute atomic sandbox setup"
```


### Task R03：Deterministic fake drivers 与 backend replay

[FRAME｜置信度：高] R03 只给 R02-A 已冻结的 driver/adapter carrier 增加 deterministic result source 行为；禁止重定义 carrier 类型，state/effect transaction 留给 R04。

#### R03-A：FakeCoreDriver result 引用、消费与结果不变量

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_drivers.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_drivers.py::test_core_driver_consumes_only_named_seeded_result
tests/stage0c/test_sandbox_drivers.py::test_driver_result_status_invariants_are_exact
tests/stage0c/test_sandbox_drivers.py::test_unavailable_result_has_stable_code
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_drivers.py::test_core_driver_consumes_only_named_seeded_result -q
```

Expected: FAIL，R02-B 已配置的 `FakeCoreDriver` carrier 已存在，但 named `take` 与一次性 consumption 行为尚缺席；若出现 class/import 缺席或其他 collection/runtime failure，先修上游 fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
FakeCoreDriver.take(result_ref: str) -> HandlerResult
```

R03-A 不配置或重写 seed-store；`take` 必须消费 R02-B 已验证的 stored result，并在消费边界再次拒绝不满足既有 HandlerResult schema 的对象。completed 要求 error_code=null/retryable=false；failed 要求非空 error_code 且 effects/state_patch 为空；unknown 要求 `CORE-E-RESULT-UNKNOWN`、retryable=false、effects/state_patch 为空。首次 take 消费 result；未配置、重复消费或跨 driver 引用返回 `fixture_driver_result_unavailable`，不猜测 fallback。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_drivers.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对 status/error/retryable/effects/state_patch 六类单因素 mutation 逐行断言专属 validation issue；合法 result canonical round-trip 后逐字段不变。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_drivers.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add deterministic core driver"
```


#### R03-B：FakeAdapter、backend seed 与零真实外发证明

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_drivers.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_drivers.py::test_fake_adapters_never_invoke_external_resources
tests/stage0c/test_sandbox_drivers.py::test_backend_replay_reads_only_seeded_key
tests/stage0c/test_sandbox_drivers.py::test_effect_ids_use_exact_preimage
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_drivers.py::test_fake_adapters_never_invoke_external_resources -q
```

Expected: FAIL，R02-A 的四个 `FakeAdapter` carrier 已存在，但 `take`、backend read 与零外发行为尚缺席；若出现 class/import 缺席或其他 collection/runtime failure，先修上游 fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
FakeAdapter.take(result_ref: str) -> HandlerResult
read_backend_seed(context: SandboxContext, replay_key: str) -> JsonValue
effect_id(case_id: str, step_id: str, ordinal: int) -> str
```

四个 adapter 只返回 seeded result并记录结构化调用，不打开网络/消息/支付/项目文件；backend 只深拷贝 seed。effect_id 唯一 preimage 为 `{"case_id", "step_id", "ordinal"}` canonical bytes，输出 `effect-` 加 64 位 lowercase SHA-256。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_drivers.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

把 socket/subprocess/项目根写入入口替换为一调用即 fail；跑四 adapter 与 backend valid/invalid rows，调用计数保持 0。effect preimage 每字段各改一值，ID 必须变化。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_drivers.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add hermetic fake adapters and backend"
```


### Task R04：State patch 与 effect transaction

[FRAME｜置信度：高] R04 两叶均以 copy→validate→single commit 实现；任何失败 pre=post 且 effects 不追加。

#### R04-A：RFC6901 state patch 的全有或全无

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_transactions.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_transactions.py::test_state_patch_table_is_atomic
tests/stage0c/test_sandbox_transactions.py::test_invalid_patch_has_exact_public_code
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_transactions.py::test_state_patch_table_is_atomic -q
```

Expected: FAIL，缺少 `apply_state_patch`；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
apply_state_patch(state: JsonObject, operations: list[JsonObject]) -> JsonObject
```

仅接受 add/replace/remove；根 pointer、array target、缺失 parent、重复 path 拒绝；add 目标必须缺席，replace/remove 目标必须存在，remove.value 必须 null。按输入顺序作用于深拷贝，任一步失败抛 `FixtureInputError(code="fixture_state_patch_invalid")`，原 state 不变。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_transactions.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

逐项覆盖 root/array/escaped token/missing parent/duplicate/add-existing/replace-missing/remove-nonnull；比较失败前后 state 对象、canonical bytes 与 hash 三者不变。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_transactions.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): apply atomic sandbox state patches"
```


#### R04-B：effect allowlist 与 patch/effect 联合提交

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_transactions.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_transactions.py::test_effect_allowlist_is_exact_not_pattern_based
tests/stage0c/test_sandbox_transactions.py::test_patch_and_effects_commit_together_or_not_at_all
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_transactions.py::test_effect_allowlist_is_exact_not_pattern_based -q
```

Expected: FAIL，缺少 effect transaction gate；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
validate_effects(seeds: list[JsonObject], allowed_effects: list[JsonObject]) -> list[JsonObject]
commit_handler_result(context: SandboxContext, step: JsonObject, result: HandlerResult) -> tuple[StateSnapshot, list[JsonObject]]
```

effect rule 对 adapter_id/operation/target 三字段全等，不支持 glob/regex/prefix；先在 state 副本验证 patch，再生成全部 ObservedEffect 并验证 allowlist，二者全通过后才一次替换 state 与追加 effects。越界抛 `fixture_effect_not_allowed`；patch 失败抛 `fixture_state_patch_invalid`。二者均形成 status=failed、retryable=false、phase=stimulus 的 PrimaryError，保留 HandlerResult.output/hash，停止后续 stimulus/assertion；receipt observed_effects=[]、pre=post。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_transactions.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

合法 patch+effect 后只改 operation/target/adapter 各一值；每个 failure 都断言 pre=post、observed_effects=[]、context effect log 未增长、原 HandlerResult.output hash 保留。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_transactions.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): commit state and effects atomically"
```


### Task R05：Stimulus dispatch、receipt、snapshot 与 effect diff

[FRAME｜置信度：高] R05-A 只形成单步 execution；R05-B 只做跨步骤聚合与交叉一致性。

#### R05-A：四类 stimulus dispatch 与 ActionReceipt

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_runner.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_runner.py::test_dispatch_routes_each_stimulus_to_exact_fake
tests/stage0c/test_sandbox_runner.py::test_action_receipt_exact_fields_and_hashes
tests/stage0c/test_sandbox_runner.py::test_failed_and_unknown_are_semantic_results
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_runner.py::test_dispatch_routes_each_stimulus_to_exact_fake -q
```

Expected: FAIL，缺少 dispatch/receipt builder；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
dispatch_stimulus(context: SandboxContext, step: JsonObject) -> HandlerResult
build_receipt(case_id: str, step: JsonObject, result: HandlerResult, pre: StateSnapshot, post: StateSnapshot, effects: list[JsonObject], replayed: bool) -> JsonObject
```

core.command/query、external.action、backend.replay 只路由静态 handler；ActionReceipt exact 15 fields，字段集合严格采用 Frozen 设计第 7.4 节。pre/post/output/request hashes 各自使用 Frozen 唯一 preimage；failed/unknown 是可断言语义结果，不自动产生 PrimaryError，observed_effects=[] 且 pre=post。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_runner.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对 receipt 的 step/handler/action/status/error/retryable/四 hash/effects/idempotency/replayed 逐字段翻转；validator 必须逐项拒绝。canonical 重读 bytes/hash 与内存值相同。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_runner.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): dispatch stimuli and build receipts"
```


#### R05-B：StepExecution、after snapshot 与 EffectDiff 聚合

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_runner.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_runner.py::test_step_execution_matches_receipt_exactly
tests/stage0c/test_sandbox_runner.py::test_effect_diff_uses_stimulus_sequence_preimage
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_runner.py::test_step_execution_matches_receipt_exactly -q
```

Expected: FAIL，缺少 StepExecution/effect diff builder；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
build_step_execution(step: JsonObject, receipt: JsonObject, pre: StateSnapshot, post: StateSnapshot, output: JsonValue, effects: list[JsonObject]) -> JsonObject
build_effect_diff(step_executions: list[JsonObject]) -> JsonObject
```

StepExecution 与 receipt 的 step/handler/request/snapshot/output/effects 逐值相等。EffectDiff 按 stimulus sequence 拼接完整 ObservedEffect array，aggregate_sha256 哈希该 array canonical bytes；禁止按 effect_id 重排。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_runner.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

反转 step 或 effect 顺序、改变一个 output code point、改变 effect ordinal；每项要求 aggregate 或交叉一致性 gate 精确失败，未 mutation 的 golden hash 可重复。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_runner.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): build step executions and effect diffs"
```


### Task R06：Machine assertions

[FRAME｜置信度：高] 两叶共同覆盖 9 handlers；所有 assertion 必须显式解析其 step_id，不存在隐式 current-step fallback。

#### R06-A：receipt 与 state assertion families

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_assertions.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_assertions.py::test_receipt_assertions_pass_and_fail_exactly
tests/stage0c/test_sandbox_assertions.py::test_state_assertions_resolve_rfc6901_scope
tests/stage0c/test_sandbox_assertions.py::test_missing_step_has_stable_code
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_assertions.py::test_receipt_assertions_pass_and_fail_exactly -q
```

Expected: FAIL，缺少 receipt/state assertion evaluators；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
evaluate_assertion(run_view: RunView, assertion: JsonObject) -> AssertionResult
```

实现 receipt.status/error_code、state.path_equals/hash_unchanged。state 从目标 StepExecution.post 读取；hash_unchanged 对 pre/post 相同 pointer 值取 canonical hash。missing step 返回 `assertion_step_not_found`；passed=true 时 error_code=null，false 时非空。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_assertions.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

覆盖空根 pointer、`~0/~1` escaped token、missing path、wrong expected status/error/retryable；每行实际值进入 AssertionResult.actual，不泄露平台异常文本。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_assertions.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): evaluate receipt and state assertions"
```


#### R06-B：effect、output 与 replay assertion families

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_assertions.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_assertions.py::test_effect_pattern_matching_is_exact
tests/stage0c/test_sandbox_assertions.py::test_output_subset_and_omission_are_structural
tests/stage0c/test_sandbox_assertions.py::test_replay_compare_fields_allowlist_is_exact
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_assertions.py::test_effect_pattern_matching_is_exact -q
```

Expected: FAIL，剩余五 assertion handlers 未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
matches_effect_pattern(effect: JsonObject, pattern: JsonObject) -> bool
json_subset(actual: JsonValue, expected: JsonValue) -> bool
evaluate_replay_equals(run_view: RunView, assertion: JsonObject) -> AssertionResult
```

effect pattern adapter_id 全等，operation/target 非 null 时全等，details 作递归 map subset且数组全等有序；output.contains/omits 作结构递归；replay.compare_fields 唯一 allowlist 精确为 `status,error_code,retryable,post_state_sha256,handler_output_sha256`。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_assertions.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

区分 details null 与空 map、数组顺序、nested missing、forbidden compare field；每类各一 pass/fail row，交换 step_id 必须命中目标 step 而非最后一步。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_assertions.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): evaluate effect output and replay assertions"
```


### Task R07：Idempotency address、request hash 与 replay

[FRAME｜置信度：高] R07-A 冻结纯 preimage；R07-B 才接入 cache 与 driver consumption。

#### R07-A：address 与 request-content 唯一 preimage

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_replay.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_replay.py::test_cache_address_preimages_are_exact
tests/stage0c/test_sandbox_replay.py::test_request_content_preimages_are_exact
tests/stage0c/test_sandbox_replay.py::test_absent_version_normalizes_to_integer_zero
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_replay.py::test_cache_address_preimages_are_exact -q
```

Expected: FAIL，缺少 address/request hash pure functions；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
cache_address_sha256(step: JsonObject) -> str | None
request_content_sha256(step: JsonObject) -> str
```

core.command address exact keys `handler_id,actor_capability_id,idempotency_key`；external.action 加 identity/tool/operation/scope_sha256/idempotency；backend 仅 handler/replay_key；query 返回 null。request preimage 按 Frozen 四类 structural object；command 仅在深拷贝中把 `absent` 归一为 integer 0。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_replay.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

每个 exact key 分别 delete/add/change；address/request golden hashes 必须只对其 preimage 变化，原 step bytes 不被 normalization 改写。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_replay.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): freeze idempotency hash preimages"
```


#### R07-B：same-hash replay、conflict 与 result consumption

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_replay.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_replay.py::test_same_address_and_hash_replays_without_consumption
tests/stage0c/test_sandbox_replay.py::test_same_address_different_hash_conflicts
tests/stage0c/test_sandbox_replay.py::test_replay_never_reapplies_patch_or_effect
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_replay.py::test_same_address_and_hash_replays_without_consumption -q
```

Expected: FAIL，cache replay dispatcher 未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
dispatch_with_idempotency(context: SandboxContext, step: JsonObject) -> tuple[HandlerResult, bool]
```

首次地址保存 request hash 与语义 result；same address/hash 返回深拷贝并 replayed=true，不消费第二 result_ref、不执行 patch/effect；same address/different hash 返回 failed `fixture_idempotency_conflict`、retryable=false、pre=post/effects=[]。其他重复 result_ref 返回 `fixture_driver_result_unavailable`。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_replay.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

completed/failed/unknown 各跑 first→replay；检查 driver consumption count、state/effect count、receipt hashes。随后只改 request body一值，必须 conflict 且 cache 首次值不变。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_replay.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): enforce idempotent sandbox replay"
```


### Task R08：Phase runner、cleanup 与 SandboxRunResult

[FRAME｜置信度：高] R08-A 只建立 phase state machine；R08-B 冻结 finally cleanup 与最终 succeeded 逻辑。

#### R08-A：validation→assertion phase runner 与 PrimaryError

[FRAME｜置信度：高] R08-A 拆为三个串行叶；每叶只有一个 primary RED node、一个 implementation delta 与一个 commit。R08-A1–A3 始终只传递同一个 `_SandboxPhaseState`，R08-B 才以 finally cleanup 形成 public `SandboxRunResult`。

##### R08-A1：validation、reset 与 setup boundary

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_cleanup.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_sandbox_cleanup.py::test_validation_reset_setup_boundaries_are_exact
```

该 node 的 rows 精确覆盖 validation/reset/setup success 与三种 first failure；每 row 只注入一个失败，并断言 later phase call count 为 0。

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_validation_reset_setup_boundaries_are_exact -q
```

Expected: 只因 `_run_validation_reset_setup` 与 module-private phase state 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
_run_validation_reset_setup(case: JsonObject, tmp_root: Path) -> _SandboxPhaseState
```

`_SandboxPhaseState` exact fields 为 `case,context,phase,primary_error,before_snapshot,step_executions:list[JsonObject],after_snapshot,diff,assertion_results`；仅实现 validation→reset→setup 三个 try boundary。首个失败冻结 phase 与稳定 `PrimaryError`，不得执行 before/stimulus/after/assertion。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_validation_reset_setup_boundaries_are_exact -q
```

- [ ] **叶步骤 5：mutation / reread gate**

逐项把 validation/reset/setup callback 变成返回失败或抛异常；断言 exact phase/code/message、state snapshot 与未调用计数，unexpected exception 统一为 `fixture_unexpected_handler_exception`。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_cleanup.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): run validation reset and setup phases"
```

##### R08-A2：before snapshot、stimulus 与 after snapshot

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_cleanup.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_sandbox_cleanup.py::test_before_stimulus_after_boundaries_are_exact
```

rows 覆盖 before failure、双 stimulus completed/failed/unknown、第二 stimulus internal exception
与 after success/failure；本叶不执行 assertion。valid failed/unknown 是语义结果而非 internal error，
必须继续执行下一 stimulus。

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_before_stimulus_after_boundaries_are_exact -q
```

Expected: 只因 `_run_before_stimulus_after` 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
_run_before_stimulus_after(state: _SandboxPhaseState) -> None
```

before 成功后才按 case 中 `stimulus_steps` 顺序遍历全部步骤；每步完整成功后向
`state.step_executions` 追加一个 execution。valid completed/failed/unknown 均是语义结果，保留实际
receipt/status 并继续下一步；internal stimulus error 冻结 phase、停止后续 stimulus，保留此前完整
executions。只要 before 已存在，无论全部步骤结束或某步 internal error，都在 cleanup 前恰好尝试一次
after/diff；after 失败保持 after/diff null。本叶不得计算 assertion 或最终 succeeded。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_before_stimulus_after_boundaries_are_exact -q
```

- [ ] **叶步骤 5：mutation / reread gate**

对 before/第一或第二 stimulus/after 各注入一次 exception，并跑双 stimulus 的
completed→failed、failed→unknown 与 unknown→completed rows；断言 valid failed/unknown 继续、internal
error 停止、`step_executions` 完整前缀、before/after/diff nullability与 primary error 不被 after覆盖。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_cleanup.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): run snapshot stimulus and after phases"
```

##### R08-A3：assertion stop 与 phase outcome

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_cleanup.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_sandbox_cleanup.py::test_assertion_phase_stops_on_first_primary_error
```

rows 覆盖 all-pass、首个 false assertion、assertion exception 与已有 earlier PrimaryError；逐行断言 later assertion count。

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_assertion_phase_stops_on_first_primary_error -q
```

Expected: 只因 `_run_assertions` / `run_sandbox_phases` 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
primary_error(phase: str, code: str, message: str) -> PrimaryError
_run_assertions(state: _SandboxPhaseState) -> None
run_sandbox_phases(case: JsonObject, tmp_root: Path) -> _SandboxPhaseState
```

`run_sandbox_phases` 只串联 A1→A2→A3 并返回同一 `_SandboxPhaseState`；首个 false assertion 产生 `fixture_assertion_failed`，首个 PrimaryError 后停止 later assertions。完整 literal phase table覆盖 all-pass、七个内部 failure、valid unknown 与 first false assertion；不得执行 cleanup 或填最终 succeeded。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_assertion_phase_stops_on_first_primary_error -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py -q
```

- [ ] **叶步骤 5：mutation / reread gate**

调换任一 phase、删一次 stop guard 或让 second false 覆盖 first error，测试必须失败；重读 state 的 canonical projection，断言 phase、PrimaryError、完整 `step_executions` 前缀、before/after/diff 与执行计数逐字段稳定。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_cleanup.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): stop on primary assertion failure"
```

#### R08-B：always cleanup、residual report 与最终 succeeded

**Files:**
- `tools/stage0c_fixtures/sandbox.py`
- `tests/stage0c/test_sandbox_cleanup.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_sandbox_cleanup.py::test_cleanup_runs_for_every_terminal_path
tests/stage0c/test_sandbox_cleanup.py::test_cleanup_never_overwrites_primary_error
tests/stage0c/test_sandbox_cleanup.py::test_succeeded_is_exact_conjunction
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py::test_cleanup_runs_for_every_terminal_path -q
```

Expected: FAIL，cleanup/final result 合同未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
cleanup_context(context: SandboxContext) -> CleanupReport
finalize_run_result(partial: _SandboxPhaseState, cleanup: CleanupReport) -> SandboxRunResult
run_sandbox_case(case: JsonObject, tmp_root: Path) -> SandboxRunResult
```

`run_sandbox_case` 调用 `run_sandbox_phases`，并在同一唯一 finally 中调用 cleanup/finalize；cleanup 恒执行且 attempted=true。completed 要求 error=null 且 residual paths/effects空；failed 要求 error非空或 residual非空。已有 PrimaryError 时 phase/错误不被 cleanup 覆盖；无 PrimaryError且 cleanup failed 时 phase=cleanup。succeeded 当且仅当 phase=completed、primary_error=null、全部assertions passed、cleanup completed。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_sandbox_cleanup.py tests/stage0c/test_sandbox_runner.py tests/stage0c/test_sandbox_replay.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对 R08-A 每行追加 cleanup success/failure 两个分支；重读 temp root、effects、cache、state。连续第二 case 初态 hash 必须等于 fresh `{"records":{}}`，第一 case 对象均不可见。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/sandbox.py tests/stage0c/test_sandbox_cleanup.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): finalize cleanup and sandbox run results"
```

## 9. Publication、handler manifest 与 smoke matrix

### Task P01：Lock、路径与 publication journal

[FRAME｜置信度：高] 所有 public publication/recovery failure 只抛 `PublicationError`；publish 成功态只返回 `PublicationResult`，recovery 成功态只返回 `RecoveryResult`。禁止返回带 `.code` 的错误 result。

#### P01-A：真实跨进程 lock 与成功 result 不变量

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_journal.py`
- `tests/test_repository_checkout_contract.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_journal.py::test_second_process_observes_publication_busy
tests/stage0c/test_publication_journal.py::test_lock_carrier_bytes_never_change
tests/stage0c/test_publication_journal.py::test_publication_lease_is_root_bound_and_context_bound
tests/stage0c/test_publication_journal.py::test_publication_result_invariants
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py::test_second_process_observes_publication_busy -q
```

Expected: FAIL，`publication.py` 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
class PublicationLockLease:
    # Opaque module-created token; resolved-root bound and active only in its context.

acquire_publication_lock(root: Path) -> ContextManager[PublicationLockLease]
PublicationResult(published: bool, no_op: bool, recovered: bool, tree_sha256: str)
```

Windows 用 msvcrt、POSIX 用 flock；第二 Python holder 先输出 LOCKED，父进程再 non-blocking acquire。busy 抛 `PublicationError(code="publication_busy")`；missing/nonzero/reparse/nonregular carrier 抛 `lock_carrier_invalid`。任何路径都不得写 carrier。

[FRAME｜置信度：高] `PublicationLockLease` 只能由本模块在成功取得 OS lock 后创建；内部保存不可由调用方提供的 module nonce、规范化 `resolved_root` 与 active 状态。`assert_owns(root)` 必须同时验证 nonce、相同 resolved root 与 active=true；context 退出先将 active 置 false 再释放 OS lock。伪造、跨 root、退出后复用统一抛 `PublicationError(code="publication_lock_lease_invalid")`。所有 `*_under_lock` API 只验证 lease，不得再次获取 lock。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py tests/test_repository_checkout_contract.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对 missing/nonzero/reparse/directory/nonregular 和 holder busy 逐行运行，调用前后 carrier bytes 保持 `b""`；holder 退出后立即可获取。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_journal.py tests/test_repository_checkout_contract.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): acquire immutable publication lock"
```


#### P01-B：transaction path 推导与 strict journal decode

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_journal.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_journal.py::test_transaction_paths_are_exact_ascii_siblings
tests/stage0c/test_publication_journal.py::test_journal_exact_schema_and_derived_paths
tests/stage0c/test_publication_journal.py::test_corrupt_journal_preserves_namespace
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py::test_transaction_paths_are_exact_ascii_siblings -q
```

Expected: FAIL，path/journal API 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
derive_transaction_paths(root: Path, transaction_id: str) -> TransactionPaths
load_publication_journal(root: Path) -> PublicationJournal | None
```

transaction 匹配 32 lowercase hex；generated/journal 固定，staging/backup/temp 只由 ID 推导为 stage0c 直接子级。strict decoder拒绝 duplicate/noncanonical/extra/state/hash/path drift；任何 corrupt 抛 `publication_journal_corrupt`，不按 journal 文本操作路径。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

逐个字段删除/增加/改一 byte，并覆盖 symlink/junction/directory/nonregular path component；完整 namespace snapshot 在每次异常前后相等。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_journal.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): validate publication paths and journals"
```


#### P01-C：journal temp persist 的 durable 顺序

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_journal.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_journal.py::test_persist_journal_has_exact_operation_order
tests/stage0c/test_publication_journal.py::test_persist_failure_keeps_last_confirmed_state
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py::test_persist_journal_has_exact_operation_order -q
```

Expected: FAIL，`persist_journal_state` 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
persist_journal_state(root: Path, journal: PublicationJournal, state: str) -> None
```

固定顺序：确认 same-tx temp 缺席→exclusive-create→write full canonical bytes→flush→file fsync→close→os.replace(temp,journal)→strict reread并比较 bytes/schema/transaction/state/path。每一 fault 抛 `PublicationError`，不继续目录 rename/delete。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_journal.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

在 create/write/fsync/close/replace/reread 前后逐点注入；每次验证 last confirmed journal bytes/state 不变，lock bytes 零，开放句柄关闭后同一 persist 可收敛。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_journal.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): persist durable publication journals"
```


### Task P02：Deterministic staging、publish、no-op 与 check

[FRAME｜置信度：高] P02-A 只创建/验证 staging；P02-B 只执行 transaction；P02-C 冻结 no-op 与零写 check。

#### P02-A：in-memory map 到 verified staging tree

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication.py::test_staging_tree_exact_paths_bytes_and_hash
tests/stage0c/test_publication.py::test_staging_failure_leaves_generated_unchanged
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py::test_staging_tree_exact_paths_bytes_and_hash -q
```

Expected: FAIL，`write_staging_tree` 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
write_staging_tree(root: Path, transaction_id: str, artifacts: dict[str, bytes]) -> str
```

先在内存验证 POSIX relative paths/unique set/canonical bytes，再 exclusive-create唯一 staging；逐文件写闭合后重读 exact `{path,size,sha256}` 与 aggregate tree hash。失败清理仅限当前合法 staging，published generated snapshot 不变。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

反向输入 enumeration、missing/extra/changed bytes、写第 N 文件 fault；相同 logical map 必须得到同 entries/tree hash，failure 时 generated与既有 residual snapshot 不变。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): write verified publication staging trees"
```


#### P02-B：prepared→old_moved→new_installed→cleaned transaction

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication.py::test_publish_with_previous_has_exact_trace
tests/stage0c/test_publication.py::test_first_publish_still_persists_old_moved
tests/stage0c/test_publication.py::test_publish_returns_success_only_result
tests/stage0c/test_publication.py::test_publish_wrapper_acquires_once_and_delegates_under_lock
tests/stage0c/test_publication.py::test_publish_under_lock_reuses_active_lease
tests/stage0c/test_publication.py::test_publish_under_lock_rejects_stale_or_foreign_lease
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py::test_publish_with_previous_has_exact_trace -q
```

Expected: FAIL，publish state machine 未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
publish_generated_tree_under_lock(
    root: Path,
    artifacts: dict[str, bytes],
    lease: PublicationLockLease,
) -> PublicationResult
publish_generated_tree(
    root: Path,
    artifacts: dict[str, bytes],
) -> PublicationResult
```

[FRAME｜置信度：高] standalone `publish_generated_tree` 是 generated-tree publication
entry 的唯一自取锁 wrapper：只 acquire 一次，把 active lease 传给 under-lock core 后返回。P02-B 的
under-lock core 只接受 clean namespace，首先 `lease.assert_owns(root)`；若发现 journal/staging/backup/temp
residual 则抛 `publication_recovery_required`，不得调用尚未实现的 recovery。P02-B 所有 success result
固定 `recovered=False`，`tree_sha256` 是本叶 publication 完成后的 final generated hash；禁止 bool
`already_locked`。P03-A 实现 recovery 后才把 under-lock recovery prepend 到该 core。


standalone wrapper 取锁一次；under-lock core 复用该 lease，并在本叶只处理 clean namespace。verified staging 后 persist prepared；had_previous=true 才 generated→backup，但两种情况都 persist old_moved；staging→generated、persist new_installed；存在 backup 才删除；persist cleaned；终检 intended 与 residual缺席；删除 journal/temp。成功 `published=True,no_op=False`。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

first publish 与 replacement 各记录 operation trace；首次明确禁止 backup rename/create/delete但要求 old_moved persist。每步后重读 journal/tree hash。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): publish deterministic generated trees"
```


#### P02-C：same-hash no-op 与 strictly no-write check

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication.py::test_same_hash_write_is_no_op_without_journal
tests/stage0c/test_publication.py::test_check_classifies_missing_changed_unexpected
tests/stage0c/test_publication.py::test_check_never_recovers_or_writes
tests/stage0c/test_publication.py::test_check_wrapper_acquires_once_and_delegates_under_lock
tests/stage0c/test_publication.py::test_check_under_lock_reuses_active_lease
tests/stage0c/test_publication.py::test_check_under_lock_rejects_stale_or_foreign_lease
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py::test_same_hash_write_is_no_op_without_journal -q
```

Expected: FAIL，no-op/check 合同缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
check_generated_tree_under_lock(
    root: Path,
    expected: dict[str, bytes],
    lease: PublicationLockLease,
) -> list[ValidationIssue]
check_generated_tree(
    root: Path,
    expected: dict[str, bytes],
) -> list[ValidationIssue]
```

[FRAME｜置信度：高] standalone `check_generated_tree` 只 acquire 一次并委托 under-lock core；
under-lock core 只执行 `lease.assert_owns(root)` 与零写比较，禁止再次 acquire、recovery、mkdir、write、
rename 或 unlink。CLI `check` 直接调用 standalone wrapper，不先持第二层 outer lock。


same intended hash 删除新 staging 后直接返回 `published=False,no_op=True`，不建 journal。standalone check wrapper non-blocking 取锁一次后把 lease 传给 core；core 递归 exact path/bytes，分别报告 missing/changed/unexpected；任何 journal/staging/backup/temp residual 只报 `publication_recovery_required`，禁止 recovery/mkdir/write/rename/unlink。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对 clean 与每类 drift/residual 用 namespace snapshot、全文件 hashes、Git status 三重比较 check 前后完全相等；monkeypatch 所有写 API 为一调用即 fail。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add no-op write and no-write check"
```


### Task P03：恢复矩阵、residual、fault injection 与 probe API

[FRAME｜置信度：高] 形状符号固定：`Ø` 缺席、`I` intended、`P` previous、`X` wrong hash/非法类型/不可读。previous 与 intended 已证明不同。

#### P03-A：13-row valid recovery matrix

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_recovery.py::test_every_literal_valid_recovery_row
tests/stage0c/test_publication_recovery.py::test_recovery_is_idempotent
tests/stage0c/test_publication_recovery.py::test_recovery_wrapper_acquires_once_and_delegates_under_lock
tests/stage0c/test_publication_recovery.py::test_recovery_under_lock_reuses_active_lease
tests/stage0c/test_publication_recovery.py::test_recovery_under_lock_rejects_stale_or_foreign_lease
tests/stage0c/test_publication_recovery.py::test_recovery_changed_exactly_matches_namespace_mutation
tests/stage0c/test_publication_recovery.py::test_recovery_changed_flows_into_publication_result
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_every_literal_valid_recovery_row -q
```

Expected: FAIL，standalone 与 under-lock recovery API 均缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
recover_publication_under_lock(
    root: Path,
    lease: PublicationLockLease,
) -> RecoveryResult
recover_publication(root: Path) -> RecoveryResult
| had_previous | journal | generated | staging | backup | action | terminal |
|---|---|---|---|---|---|---|
| true | prepared | P | I 或 Ø | Ø | drop staging+journal | P,Ø,Ø |
| true | prepared | Ø | I 或 Ø | P | backup→generated; drop staging+journal | P,Ø,Ø |
| true | old_moved | Ø | I 或 Ø | P | backup→generated; drop staging+journal | P,Ø,Ø |
| true | old_moved | P | I 或 Ø | Ø | drop staging+journal | P,Ø,Ø |
| true | old_moved | I | Ø | P | persist new_installed; continue | I,Ø,Ø |
| true | new_installed | I | Ø | P | drop backup; persist cleaned; drop journal | I,Ø,Ø |
| true | new_installed | I | Ø | Ø | persist cleaned; drop journal | I,Ø,Ø |
| true | cleaned | I | Ø | Ø | drop journal | I,Ø,Ø |
| false | prepared | Ø | I 或 Ø | Ø | drop staging+journal | Ø,Ø,Ø |
| false | old_moved | Ø | I 或 Ø | Ø | drop staging+journal | Ø,Ø,Ø |
| false | old_moved | I | Ø | Ø | persist new_installed; continue | I,Ø,Ø |
| false | new_installed | I | Ø | Ø | persist cleaned; drop journal | I,Ø,Ø |
| false | cleaned | I | Ø | Ø | drop journal | I,Ø,Ø |
```

[FRAME｜置信度：高] standalone `recover_publication` 只 acquire 一次并委托 under-lock core；
under-lock core 先 `lease.assert_owns(root)`，禁止递归 acquire。`changed=True` 当且仅当该次 locked
recovery 实际执行过任一 namespace mutation（write/replace/rename/unlink/mkdir）；纯观察、已 clean
幂等调用必须 false。每个 valid row 同时断言 operation trace 与 `changed`，所有 error row 保持 namespace
不变且不返回 result。

本叶同时修改 P02-B 的 `publish_generated_tree_under_lock`：active lease 下先调用
`recover_publication_under_lock(root, lease)`，绝不调用 public wrapper；随后执行 no-op 或 publication。
`PublicationResult.recovered == RecoveryResult.changed`，`tree_sha256` 是 recovery 与 publication 全部动作
结束后的 final generated hash。recovery→same-hash no-op 与 recovery→new publish 两行均落 integration
test；前者允许 `recovered=True,no_op=True`，后者允许 `recovered=True,published=True`。

`I 或 Ø` 展开后是 12 个 true shape keys 与 7 个 false keys；dispatcher 只接受上述 expanded keys并执行唯一动作。恢复后只返回可从当前磁盘独立观察的 `RecoveryResult(terminal="present"|"absent", tree_sha256, changed)`：present 必须携带当前 generated 的 uppercase tree SHA-256，absent 必须为 null。P/I 身份只由当前 literal matrix row 持有的 previous/intended expected hashes 比较判定，不进入 recovery API。journal 已删除后的连续调用返回相同 present/hash 或 absent，且 changed=false；错误抛 PublicationError。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

每个 valid key 首次恢复后，测试先用该 row 的 previous/intended expected hashes判定实际 P/I/absent；再调用两次，只要求可观测 terminal=`present|absent`、tree hash 与首次相同且 changed=false。journal/staging/backup/temp 缺席，lock bytes 零；无 journal 时不得猜测 present tree 的 P/I 身份。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): recover literal publication states"
```


#### P03-B：Ø/I/P/X 自动非法补集

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_recovery.py::test_every_unlisted_matrix_shape_is_corrupt
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_every_unlisted_matrix_shape_is_corrupt -q
```

Expected: FAIL，未列 shape 尚未 fail-closed；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
valid_shape_keys(had_previous: bool) -> frozenset[tuple[str, str, str, str]]
```

遍历 4 states × 4³ shapes，跳过 expanded valid set；其余均使用 `with pytest.raises(PublicationError) as captured` 并断言 code=`publication_state_corrupt`。X 必须分别物理构造 wrong hash、unreadable、reparse、directory、nonregular，不能用 sentinel stub。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

每个 illegal row 保存完整 namespace snapshot；异常后逐元组相等。测试显式证明没有调用 rename/unlink/replace。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): reject illegal publication state complement"
```


#### P03-C：valid journal temp normalization

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_recovery.py::test_valid_same_transaction_temp_is_normalized_first
tests/stage0c/test_publication_recovery.py::test_mixed_or_illegal_temp_is_residual_corrupt
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_valid_same_transaction_temp_is_normalized_first -q
```

Expected: FAIL，temp normalization 尚未独立于 matrix；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
normalize_journal_temp(root: Path, journal: PublicationJournal) -> None
```

有效主 journal 时只允许其推导路径上的一个普通 same-transaction temp；持锁删除并验证缺席后才进入 matrix。一个 same-transaction temp 加至少一个 other-transaction temp、两个不同 transaction temps、reparse/directory/nonregular 均抛 `publication_residual_corrupt` 并保留对象。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

跨 prepared/old_moved/new_installed/cleaned 参数化；成功 normalization 后重读主 journal，state/transaction/path 不变。错误 rows 全 namespace snapshot 不变。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): normalize publication journal temps"
```


#### P03-D：无 journal residual 与 Windows 开放句柄

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_publication_recovery.py::test_no_journal_residual_rules_are_exact
tests/stage0c/test_publication_recovery.py::test_windows_open_handle_preserves_confirmed_state
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_no_journal_residual_rules_are_exact -q
```

Expected: FAIL，无 journal/handle 边界未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
prepare_write_namespace(root: Path) -> None
```

无 journal 的 write 删除所有命名与 type 均合法的孤立 staging/temp，不按 transaction ID 区分；任何 backup residual、reparse 或非普通 staging/temp/backup 才抛 `publication_residual_corrupt`。other-transaction 判坏只适用于有效主 journal 存在的 P03-C。check 对任一 residual 始终只报 recovery_required。Windows holder 对 generated/staging/backup/journal/temp 实体持句柄，replace/rename/unlink failure 保留 last confirmed journal state；非 Windows 平台以 skip marker 仅跳 Windows 专属 row。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

holder 退出后再次 write 必须收敛；异常时 path/type/size/hash snapshot 和 lock bytes逐项相等。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): enforce publication residual and handle rules"
```


#### P03-E：fault-point closure 与唯一 publication probe API

[FRAME｜置信度：高] P03-E 拆为三个串行叶；catalog 不执行 fault，publication interruption 不宣称 recovery 收敛，最终叶才开放 probe outcome API。

##### P03-E1：fault catalog 与 ordered probe specs

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_publication_recovery.py::test_publication_fault_catalog_and_specs_are_exact
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_publication_fault_catalog_and_specs_are_exact -q
```

Expected: 只因 fault catalog/spec builder 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
publication_fault_points() -> tuple[str, ...]
publication_probe_specs() -> tuple[PublicationProbeSpec, ...]
```

catalog literal覆盖 staging 前后、journal temp create/write/fsync/close/replace/reread 前后、两次 rename、三次后续 persist、backup delete、journal delete与每个 recovery action；此叶只生成 exact ordered literals。`spec.to_json` exact four fields，specs 按 case_id，再按 fault catalog ordinal；不得执行 publication/recovery。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_publication_fault_catalog_and_specs_are_exact -q
```

- [ ] **叶步骤 5：mutation / reread gate**

reverse enumeration 必须重建相同 tuple；删、重、换任一 fault literal 或 spec field 均由同一 node 精确报差异。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): freeze publication fault probe catalog"
```

##### P03-E2：publication interruption runner

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_publication_recovery.py::test_each_publication_fault_preserves_old_or_complete_new
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_each_publication_fault_preserves_old_or_complete_new -q
```

Expected: 只因 publication fault injection hook 缺席而 FAIL；E1 catalog 已通过。

- [ ] **叶步骤 3：最小实现**

在 P02 publication 的每个 E1 publication fault point 调用一个 deterministic one-shot injector；注入时只抛 `PublicationError(code="publication_fault_injected")`，不得伪造 success result。每 row 独立 fresh root、真实 journal bytes 与 operation trace；首个异常后 final 只为完整 previous/intended/absent 中该行允许项，journal state 必须等于最后 durable persist。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_each_publication_fault_preserves_old_or_complete_new -q
```

- [ ] **叶步骤 5：mutation / reread gate**

逐 fault reread journal、generated/staging/backup/temp path/type/bytes/hash；移动 injector 到 durable persist 前后错误侧时 test 必须失败。此叶不执行第二 write，不生成 `PublicationProbeOutcome`。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): exercise publication interruption points"
```

##### P03-E3：recovery interruption 与 outcome closure

**Files:**
- `tools/stage0c_fixtures/publication.py`
- `tests/stage0c/test_publication_recovery.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_publication_recovery.py::test_recovery_faults_converge_and_probe_outcome_closes
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_recovery_faults_converge_and_probe_outcome_closes -q
```

Expected: 只因 recovery fault closure 与 public executor 缺席而 FAIL；E1/E2 节点保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
execute_publication_probe(root: Path, spec: PublicationProbeSpec) -> PublicationProbeOutcome
```

每个 recovery action 可再次 one-shot 中断；每次异常后重开进程语义并调用 under-lock recovery。首次终态只允许 P/I/absent，第二 write 必须收敛 I，第三 write必须 no-op。outcome 与 runtime `PublicationResult` 为不同类型；`attempt_count,executed,passed,terminal_tree_sha256,actual` 全由真实 traces 构造。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py::test_recovery_faults_converge_and_probe_outcome_closes -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_publication_recovery.py -q
```

- [ ] **叶步骤 5：mutation / reread gate**

每个 outcome canonical round-trip；attempt_count、executed/passed、terminal hash 与 actual逐字段验证。跳过任一 recovery action、第二 write 或第三 no-op 时测试必须失败。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/publication.py tests/stage0c/test_publication_recovery.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): close recovery fault convergence"
```

### Task M01：Handler manifest

**Files:**
- Modify: `tools/stage0c_fixtures/handlers.py`
- Modify: `tools/stage0c_fixtures/compiler.py`
- Create: `tests/stage0c/test_handler_manifest.py`

[FRAME｜置信度：高] M01 必须直接依赖 F07 `build_fixture_case_schema()` 与 F09 compiler/hash API；测试必须证明这两个模块任一缺席或 schema hash 漂移都会失败。

- [ ] **Red code:** 对 18 entries 断言 exact fields、Unicode order、params schema preimage、repo-relative POSIX implementation path、raw implementation file hash、registry hash。分别 mutation handler kind、schema object 一个 byte、source path case、implementation file一个 byte，要求 runtime comparison 失败。
- [ ] **Run red:** `.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handler_manifest.py -q`。
- [ ] **Minimal implementation:** compiler 从 F07 schema object 计算 params hash，从 repository root strict-read implementation source raw bytes；handlers runtime 调同一 builder 比较 manifest，不复制 hash 算法。
- [ ] **Green + reread hashes:**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_handler_manifest.py tests/stage0c/test_handlers.py tests/stage0c/test_compiler.py -q
```

测试在 `tmp_path` 写 manifest、重读、重算所有 entry hash 与 registry hash；18 个 entry 必须逐值一致。

- [ ] **Explicit commit:**

```powershell
git add tools/stage0c_fixtures/handlers.py tools/stage0c_fixtures/compiler.py tests/stage0c/test_handler_manifest.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): compile handler manifest"
```

### Task M02：Harness smoke test matrix

**Files:**
- Create: `tools/stage0c_fixtures/smoke_matrix.py`
- Create: `tests/stage0c/test_smoke_matrix.py`

- [ ] **Step 1: 写 exact structural schema 红灯**

| object | exact fields |
|---|---|
| matrix | `schema_version,handler_probes,scenarios,publication_probes` |
| handler probe | `case_id,handler_id,polarity,input` |
| scenario | `scenario_id,category,fixture` |
| publication probe | `case_id,journal_state,disk_shape,fault_point` |

matrix 的 `schema_version` 必须精确为 string `"0.1"`，其余三项必须为 arrays。handler probe 的 case/handler ID 为非空 string、polarity 仅 `valid|invalid`、input 为任意允许 JSON value；scenario 的 ID/category 为非空 string、fixture 为 JSON value；publication probe 四字段均为非空 string。每类 object 参数化 missing field、extra field、wrong type、invalid enum、duplicate ID 与 wrong order；handler probes 排序为 `(handler_id,valid-before-invalid,case_id)`，scenarios 按 scenario_id，publication probes 按 case_id。handler `case_id`、scenario_id 与 publication `case_id` 在整个 matrix 全局唯一。

- [ ] **Step 2: 写 coverage 与 input-purity 红灯**

每个 M01 handler 必须恰有一条 valid 与一条 invalid probe；scenario category set 精确覆盖 `completed,failed,unknown,effect_not_allowed,replay_valid,replay_conflict,setup_failure,stimulus_failure,assertion_failure,cleanup_failure`；publication probes 精确覆盖 P03 每个 expanded valid recovery row 与全部声明 fault points。

分别向 matrix 和三种 item 注入 `passed,outcome,result_sha256,events,executed,actual`，每项都必须得到 `smoke_matrix_contains_result`；matrix 是 input-only authority，不接受任何预填执行结果。

- [ ] **Step 3: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_smoke_matrix.py -q
```

Expected: FAIL，`smoke_matrix.py` 尚不存在。

- [ ] **Step 4: 写最小 pure builder**

固定签名 `build_smoke_matrix(handler_manifest: JsonObject, publication_probe_specs: tuple[PublicationProbeSpec, ...]) -> JsonObject` 与 `validate_smoke_matrix(matrix: JsonObject) -> list[ValidationIssue]`；P03 的 `publication_probe_specs()` 是唯一 probe spec builder，M02 不接受 dict 形状的第二套 API。builder 只返回 canonical input fixtures。builder 对反向 enumeration input 仍产生相同三数组排序，validator 对所有 exact-field/coverage/unique/order 问题返回稳定 code。

- [ ] **Step 5: 运行绿灯、双构建与重读**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_smoke_matrix.py -q
```

连续 build 两次、分别写入两个 tmp files、关闭并 strict reread，bytes 与 SHA-256 必须相等；交换 handler/publication input enumeration order 不改变结果。

- [ ] **Step 6: 显式暂存与提交**

```powershell
git add tools/stage0c_fixtures/smoke_matrix.py tests/stage0c/test_smoke_matrix.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): generate harness smoke matrix"
```

## 10. Final compiler、verification、CLI 与关闭门

### Task C01：纯构建并发布 exact 265-file generated tree

**Files:**
- Modify: `tools/stage0c_fixtures/compiler.py`
- Create: `tests/stage0c/test_current_generated.py`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/fixture_case_schema_v0_1.json`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/sandbox_handler_manifest_v0_1.json`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/harness_smoke_test_matrix_v0_1.json`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/case_binding_manifest_v0_1.json`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/stage0c_report_v0_1.json`
- In-memory build; publish only in C01-B: `fixtures/stage0c/generated/cases/*.json`
- In-memory build; publish for the first time only in C01-B: `fixtures/stage0c/generated/conversion_checklist_v0_1.json`

[FRAME｜置信度：高] C01 是 `fixtures/stage0c/generated/` 的首次发布节点。F04 到 C01-B 之前，该目录不得出现 partial checklist 或其他 Stage 0C generated artifact。依赖方向只能是 `compiler → publication`；`publication.py` 禁止 import compiler。

#### C01-A：只读 current-tree orchestration

- [ ] **RED：API 缺席且不触碰磁盘**

添加 `test_build_current_generated_is_read_only`。用 monkeypatch 把 `publish_generated_tree`、`acquire_publication_lock`、`recover_publication` 替换为一旦调用就 fail；调用前后比较 repository namespace snapshot 与 `git status --short`，并断言返回 exact 265 path→bytes、完整 Stage0C report literal。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_current_generated.py::test_build_current_generated_is_read_only -q
```

Expected: FAIL，且唯一原因是 `build_current_generated` 尚不存在。

- [ ] **最小实现与 GREEN**

```python
def build_current_generated(root: Path) -> dict[str, bytes]:
    """Read and validate authoritative inputs; return 265 canonical files."""
```

该函数只读 frozen inputs、ordered reviewed cases，并调用 F04/F06/F07/F09/M01/M02 pure builders；不得调用 publication API、mkdir、write、lock 或 recovery。任何 validation issue 在返回 map 前抛出。随后：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_current_generated.py::test_build_current_generated_is_read_only tests/stage0c/test_compiler.py -q
```

Expected: PASS；authoritative generated directory 仍缺席。

- [ ] **Commit C01-A**

```powershell
git add -- tools/stage0c_fixtures/compiler.py tests/stage0c/test_current_generated.py
git diff --cached --check
git commit -m "feat(stage0c): build current generated tree in memory"
```

#### C01-B：唯一首次 authoritative publication

- [ ] **RED：磁盘目录缺席**

添加独立 `test_current_generated_matches_fresh_build`；构造六个 top-level + 259 case exact path set，递归拒绝额外目录、reparse、nonregular、missing/changed，并逐字节比较 fresh `build_current_generated(root)`。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_current_generated.py::test_current_generated_matches_fresh_build -q
```

Expected: 只因 `fixtures/stage0c/generated` 缺席而 FAIL；不得以 publication 让 C01-A 转绿。

- [ ] **首次发布 trace gate**

isolated temp repository 精确要求：写/验证 staging(I)→`persist(prepared)`→确认 generated/backup 缺席→`persist(old_moved)`→staging→generated→`persist(new_installed)`→确认 backup 缺席→`persist(cleaned)`→验证 I 与所有 residual 缺席→删除 journal/temp。had_previous=false 仍必须 persist old_moved；禁止 generated→backup rename 与真实 backup create/delete。

- [ ] **执行唯一首次 publication 并 GREEN**

```python
def write_current_generated(root: Path) -> PublicationResult:
    artifacts = build_current_generated(root)
    return publish_generated_tree(root, artifacts)
```

```powershell
.\.venv\Scripts\python.exe -B -c "from pathlib import Path; from tools.stage0c_fixtures.compiler import write_current_generated; result=write_current_generated(Path('.')); assert result.published and not result.no_op"
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_current_generated.py tests/stage0c/test_compiler.py -q
```

Expected: 首次一次性创建 265 files；fresh builder bytes 与 disk bytes完全相同。

- [ ] **第二次 write/no-op 与 commit C01-B**

第二次 write 前后用 `tree_entries/tree_sha256` 比较，要求 `result.no_op and not result.published`、entries/tree bytes 相等、journal/staging/backup/temp 缺席、lock carrier 零字节。

```powershell
git add -- tools/stage0c_fixtures/compiler.py tests/stage0c/test_current_generated.py fixtures/stage0c/generated
git diff --cached --check
git diff --cached --stat
git commit -m "data(stage0c): publish generated fixture definitions"
```

### Task V00：Verification engine 与 evidence 合同测试，不生成正式 evidence

**Files:**
- Create and then modify by leaves: `tools/stage0c_fixtures/verification.py`
- Create and then modify by leaves: `tests/stage0c/test_harness_verification.py`

[FRAME｜置信度：高] V00 的所有 final/evidence writes 只落 pytest `tmp_path`；正式 `outputs/verification/Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json` 只能由 V01 创建。verification public API 不接受预填 result/event/outcome/passed/evidence body。

#### V00-A：三个 provenance 唯一 preimage

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_harness_verification.py::test_provenance_preimages_are_exact
tests/stage0c/test_harness_verification.py::test_harness_source_tree_rejects_reparse_and_nonregular
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_provenance_preimages_are_exact -q
```

Expected: FAIL，verification module 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
compute_provenance(root: Path, handler_manifest_bytes: bytes, matrix_bytes: bytes) -> JsonObject
```

manifest/test_matrix hash 完整 canonical file bytes 含末尾 LF。source tree递归全部普通 `.py`，entry exact `path,size,sha256`，repo-relative case-sensitive POSIX Unicode排序，hash entries array canonical bytes；拒绝 reparse/nonregular。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

分别改单一 manifest byte、matrix byte、source byte/path case/size；只对应 hash变化，另外两项不变；恢复原 bytes后三 hash恢复。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): compute harness evidence provenance"
```


#### V00-B：evidence exact structural schema

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_exact_fields_types_and_enums
tests/stage0c/test_harness_verification.py::test_evidence_order_unique_and_hash_shapes
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_exact_fields_types_and_enums -q
```

Expected: FAIL，evidence structural validator 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
validate_smoke_evidence_structure(evidence: JsonObject) -> list[ValidationIssue]
top=`schema_version,handler_manifest_sha256,harness_source_tree_sha256,test_matrix_sha256,event_log_sha256,handler_valid_case_count,handler_invalid_case_count,covered_statuses,covered_failure_modes,publication_matrix_case_count,events,outcomes,handler_results,scenario_results,publication_results,passed`; event=`sequence,case_id,event_type,handler_id,result_sha256`; outcome=`result_id,subject_id,subject_kind,input_sha256,actual,passed`; handler result=`case_id,handler_id,polarity,executed,passed,result_sha256`; scenario result=`scenario_id,category,executed,passed,result_sha256`; publication result=`case_id,journal_state,disk_shape,fault_point,attempt_count,executed,passed,result_sha256,terminal_tree_sha256`
```

schema_version=`0.1`；events sequence连续正整数，started hash null/finished hash uppercase64；subject_kind handler/scenario/publication；polarity valid/invalid；attempt_count正整数；arrays 按 Frozen key排序；covered_statuses 精确 `[completed,failed,unknown]`，failure modes唯一 Unicode升序。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

top 与五类 item 各参数化 missing/extra/wrong type/invalid enum；另测 wrong order、duplicate ID、sequence gap、hash长度/大小写，逐行专属 code。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): validate exact smoke evidence schema"
```


#### V00-C：matrix→result→outcome→event exact bijection

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_harness_verification.py::test_handler_result_outcome_event_bijection
tests/stage0c/test_harness_verification.py::test_scenario_result_outcome_event_bijection
tests/stage0c/test_harness_verification.py::test_publication_result_outcome_event_bijection
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_handler_result_outcome_event_bijection -q
```

Expected: FAIL，bijection gate 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
validate_evidence_bijections(evidence: JsonObject, matrix: JsonObject) -> list[ValidationIssue]
```

每个 matrix item恰一 result、一 outcome、一 started→finished pair，无 extra/missing/duplicate；handler key包含 case/handler/polarity，scenario/publication按 Frozen逐字段；started先于finished。outcome.passed=result.passed，outcome canonical hash=result_sha256=finished hash。错误码精确为 `evidence_result_bijection_invalid/evidence_outcome_bijection_invalid/evidence_event_bijection_invalid/evidence_result_passed_mismatch/evidence_result_hash_mismatch`。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

对三 subject 各执行 missing/extra/duplicate/wrong identity/wrong order/wrong passed/wrong hash；每行只返回预期 code。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): bind smoke results outcomes and events"
```


#### V00-D：三类 outcome input_sha256 preimage

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_harness_verification.py::test_outcome_input_hash_preimages_are_exact
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_outcome_input_hash_preimages_are_exact -q
```

Expected: FAIL，input hash builder 未实现；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
outcome_input_sha256(subject_kind: str, matrix_item: JsonObject) -> str
handler preimage=handler probe.input; scenario preimage=scenario.fixture; publication preimage=完整四字段 probe record
```

只哈希列出的 JSON value canonical bytes；handler整条 probe、scenario整条 record、publication 单字段子集均不是 preimage。输出 uppercase SHA-256。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

每类 two-record test：只改非 preimage字段不影响 hash，只改 preimage一值必改变；三个 golden hash逐字锁定。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): freeze smoke outcome input hashes"
```


#### V00-E：passed=true 完整合取门

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1（2–5 分钟）：只写以下 exact test node**

```text
tests/stage0c/test_harness_verification.py::test_passed_true_requires_every_literal_conjunct
tests/stage0c/test_harness_verification.py::test_invalid_claim_is_forced_false_with_exact_code
```

每个 parameter row 只破坏一个因素；test 名、expected code 与输入 literal 同时落盘，不用宽泛异常断言。

- [ ] **叶步骤 2（2–5 分钟）：运行单节点 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_passed_true_requires_every_literal_conjunct -q
```

Expected: FAIL，passed gate 缺席；若出现其他 collection/runtime failure，先修 test fixture，不进入实现。

- [ ] **叶步骤 3（2–5 分钟一小段）：写该叶唯一 implementation delta**

```text
validate_smoke_evidence(evidence: JsonObject, matrix: JsonObject, manifest: JsonObject, root: Path) -> list[ValidationIssue]
```

合取 literal覆盖：每 handler恰一 valid/invalid且 executed/pass；counts正且相等；三类 exact bijection与 input/result hashes；status三项；failure modes等于 matrix声明且实际命中 set；required scenario categories；全部 expanded recovery/fault probes；publication count；event_log hash；三 provenance hashes。任一失败只允许 passed=false，禁止把错误 evidence 标 true。

- [ ] **叶步骤 4（2–5 分钟）：同节点 GREEN，再跑该叶文件**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

Expected: exit code 0。

- [ ] **叶步骤 5（2–5 分钟）：mutation / reread gate**

从 passed=true golden 逐项只破坏一个 conjunct；每行断言专属 code 与最终 passed false，不用宽泛 `assert issues`。

- [ ] **叶步骤 6：只提交该叶**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): enforce complete smoke evidence pass gate"
```


#### V00-F：实际 registry/sandbox/publication dispatch

[FRAME｜置信度：高] V00-F 拆为四个串行叶；每个 executor 只接受 matrix/spec 与真实 runtime 返回，F4 才合并、排序并构造 bundle。

##### V00-F1：actual handler registry dispatch

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_handler_probes_dispatch_actual_registry_once
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_handler_probes_dispatch_actual_registry_once -q
```

Expected: 只因 handler executor 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
execute_handler_probes(
    root: Path,
    matrix: JsonObject,
    emit: Callable[[str, str, str, str | None], None],
) -> tuple[JsonObject, ...]
```

按 matrix exact order 对每个 handler valid/invalid probe 各调用实际 static registry 一次；started/finished callback 与 actual return 产生 event/result。不得接受调用者提供的 result、event、outcome 或 passed。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_handler_probes_dispatch_actual_registry_once -q
```

- [ ] **叶步骤 5：mutation / reread gate**

spy 证明每个 handler/polarity 恰一次；删、重或调换一项、伪造 callback result 均由 exact call/result set 断言拒绝。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): execute actual handler smoke probes"
```

##### V00-F2：actual sandbox scenario dispatch

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_scenario_probes_dispatch_actual_sandbox_once
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_scenario_probes_dispatch_actual_sandbox_once -q
```

Expected: 只因 scenario executor 缺席而 FAIL；F1 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
execute_scenario_probes(
    root: Path,
    matrix: JsonObject,
    emit: Callable[[str, str, str, str | None], None],
) -> tuple[JsonObject, ...]
```

每个 scenario 只调用 R08 final sandbox runner；result 与 callback 完全源自真实 `SandboxRunResult`，并在每行 finally 清理 case temp root。不得重实现 sandbox phase 或从 expected literal合成 actual。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_scenario_probes_dispatch_actual_sandbox_once -q
```

- [ ] **叶步骤 5：mutation / reread gate**

每个 required category 至少一行；spy 证明 scenario ID 恰一次，runner return 单字段 mutation 必须改变 result hash并被后续 validator拒绝。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): execute actual sandbox smoke probes"
```

##### V00-F3：isolated publication probe dispatch

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_publication_probes_use_fresh_isolated_roots
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_publication_probes_use_fresh_isolated_roots -q
```

Expected: 只因 isolated publication executor 缺席而 FAIL；F1/F2 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
execute_isolated_publication_probes(
    authoritative_root: Path,
    publication_probe_parent: Path,
    specs: tuple[PublicationProbeSpec, ...],
    emit: Callable[[str, str, str, str | None], None],
) -> tuple[JsonObject, ...]
```

每个 spec 创建独立 fresh fixture repository root，预置自己的零字节 lock carrier 与 deterministic P/I tree，再调用 P03 public probe executor。每个 isolated resolved root 与 authoritative root 必须不同；不得接收 authoritative lease，不得获取 outer lock，不得复制或操作 authoritative generated/evidence/journal。每行 finally 删除自己的 probe root。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_publication_probes_use_fresh_isolated_roots -q
```

- [ ] **叶步骤 5：mutation / reread gate**

记录每个 acquired lock path，全部位于对应 isolated root 且不等于 outer lock；outer lock 全程保持。authoritative namespace 的 path/type/bytes/hash snapshot 前后相等，残留任一 probe root 即失败。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): execute isolated publication smoke probes"
```

##### V00-F4：callback-derived bundle 与 evidence builder

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_execution_bundle_is_callback_derived_and_sorted
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_execution_bundle_is_callback_derived_and_sorted -q
```

Expected: 只因 bundle orchestrator/builder 缺席而 FAIL；F1–F3 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
@dataclass(frozen=True, slots=True)
class ExecutionBundle:
    events: tuple[JsonObject, ...]
    outcomes: tuple[JsonObject, ...]
    handler_results: tuple[JsonObject, ...]
    scenario_results: tuple[JsonObject, ...]
    publication_results: tuple[JsonObject, ...]

execute_smoke_matrix(
    root: Path,
    matrix: JsonObject,
    publication_probe_parent: Path,
) -> ExecutionBundle
build_smoke_evidence(
    root: Path,
    matrix: JsonObject,
    execution: ExecutionBundle,
) -> JsonObject
```

orchestrator 只调用 F1/F2/F3；每项 started/finished callback 生成连续 sequence，actual return 构成 outcome，再派生三类 result arrays。所有 arrays 按 Frozen key 排序；builder 不接受外部 result/event/outcome/passed。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_execution_bundle_is_callback_derived_and_sorted -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

- [ ] **叶步骤 5：mutation / reread gate**

删/重复 callback、伪造 return 或反转 executor enumeration，builder 必须重建同一 canonical order，validator拒绝 event/result bijection 不一致；bundle canonical round-trip逐字段相等。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): build callback-derived smoke execution bundle"
```

#### V00-G：smoke evidence validation、atomic publication 与 no-write check

[FRAME｜置信度：高] V00-G 拆为七个串行叶。所有 under-lock API 只调用 `lease.assert_owns(root)`，不调用 `acquire_publication_lock`；standalone wrapper 才各自 acquire 一次。禁止 `already_locked: bool`。

##### V00-G1：evidence final/temp path classification

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_paths_classify_absent_regular_and_illegal_types
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_paths_classify_absent_regular_and_illegal_types -q
```

Expected: 只因 evidence path classifier 缺席而 FAIL。

- [ ] **叶步骤 3：最小实现**

```text
inspect_smoke_evidence_paths(root: Path) -> EvidencePathState
```

`EvidencePathState` exact fields 为
`final_kind,temp_kind: absent|regular|reparse|directory|nonregular`。固定 final 与 sibling
`.stage0c-harness-smoke-evidence.tmp`；逐祖先 `lstat/lexists` 且不跟随 reparse，某路径的首个非法
祖先/leaf 决定其 kind。classifier 对五类均只返回 state，不抛 publication error，且不得
mkdir/read/write/replace/unlink。G5 writer 才把 temp 的 reparse/directory/nonregular 映射为
`PublicationError(code="smoke_evidence_residual_corrupt")`；G6 check 把同一 state 映射为
`ValidationIssue(code="smoke_evidence_residual_corrupt")` 并保留对象。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_paths_classify_absent_regular_and_illegal_types -q
```

- [ ] **叶步骤 5：mutation / reread gate**

真实创建 absent、ordinary file、directory 与平台可建 reparse/nonregular；逐项断言返回的 exact kind，并比较调用前后 path/type/bytes/hash。classifier 不得抛类型错误，也不得 mkdir/read/write/replace/unlink。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): classify smoke evidence publication paths"
```

##### V00-G2：validated canonical evidence factory

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_invalid_evidence_is_rejected_before_any_publication_io
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_invalid_evidence_is_rejected_before_any_publication_io -q
```

Expected: 只因 validated carrier factory 缺席而 FAIL；G1 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
@dataclass(frozen=True, slots=True, init=False)
class ValidatedSmokeEvidence:
    canonical_bytes: bytes
    sha256: str
    _resolved_root: Path = field(repr=False, compare=False)
    _origin_token: object = field(repr=False, compare=False)

prepare_validated_smoke_evidence_under_lock(
    root: Path,
    evidence: JsonObject,
    matrix: JsonObject,
    manifest: JsonObject,
    lease: PublicationLockLease,
) -> ValidatedSmokeEvidence
```

factory 第一步调用 `lease.assert_owns(root)`；inactive/stale/foreign lease 原样传播
`PublicationError(code="publication_lock_lease_invalid")`，禁止重映射。lease 通过后再对内存 evidence
canonical serialize、strict-reread为新对象并证明 bytes canonical；调用完整 `validate_smoke_evidence(reread,matrix,manifest,root)`；要求 issues exact `[]`
且 `reread["passed"] is True`。只有 module-private sentinel 能绕过 `init=False` 创建 carrier，并把 prepare
时的 resolved root 与 sentinel identity 存入 private fields。只有 canonical/structure/semantic/passed
内容失败映射为 `FixtureInputError(code="smoke_evidence_validation_failed")`；lease error 保持
`publication_lock_lease_invalid`；factory 返回前不得创建、删除、替换或读取
evidence final/temp，lock carrier bytes 与 write/replace/unlink count 均不变。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_invalid_evidence_is_rejected_before_any_publication_io -q
```

- [ ] **叶步骤 5：mutation / reread gate**

逐项只破坏 schema、bijection、provenance hash 或 `passed` 合取门之一；每行断言 exact failure code、
temp 从未出现、final/lock bytes不变，禁止用宽泛异常。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): prepare validated smoke evidence bytes"
```

##### V00-G3：carrier authenticity 与 root binding

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_validated_evidence_carrier_authenticity_and_root_binding
```

rows 精确包含 direct construction、伪造 origin、foreign root、stale/foreign lease、non-bytes
canonical bytes、lowercase/short/mismatched SHA。

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_validated_evidence_carrier_authenticity_and_root_binding -q
```

Expected: 只因 carrier assertion helper 缺席而 FAIL；G1/G2 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
assert_validated_smoke_evidence_under_lock(
    root: Path,
    prepared: ValidatedSmokeEvidence,
    lease: PublicationLockLease,
) -> None
```

在任何 evidence I/O 前先调用 `lease.assert_owns(root)` 并原样传播
`publication_lock_lease_invalid`；lease 通过后才验证 origin token identity、carrier
`_resolved_root == lease.resolved_root`、`type(canonical_bytes) is bytes`、SHA 是 uppercase64 且
`sha256_upper(canonical_bytes) == sha256`。上述 carrier origin/root/bytes/hash 任一失败才抛
`FixtureInputError(code="smoke_evidence_carrier_invalid")`；lease failure 不得转成该 code。所有失败
均零写且不得先读取 final/temp。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_validated_evidence_carrier_authenticity_and_root_binding -q
```

- [ ] **叶步骤 5：mutation / reread gate**

增加 exact regression nodes
`test_forged_validated_evidence_carrier_is_rejected_without_write` 与
`test_validated_evidence_carrier_is_root_bound`；每行比较 final/temp/lock namespace 与全部 I/O spy
计数，错误前 read/write/replace/unlink 均为 0。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): bind smoke evidence carrier to root"
```

##### V00-G4：normal publication under existing lease

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_publication_uses_existing_outer_lease
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_publication_uses_existing_outer_lease -q
```

Expected: 只因 under-lock publication core 缺席而 FAIL；G1–G3 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
publish_smoke_evidence_under_lock(
    root: Path,
    prepared: ValidatedSmokeEvidence,
    lease: PublicationLockLease,
) -> str
```

先调用 G3 assertion helper并保持其 lease/carrier 错误分区；clean namespace 正常路径执行 exclusive-create temp→write exact carrier
bytes→flush/fsync/close→replace→strict reread bytes/hash，返回 final uppercase SHA。该 core 不调用
`acquire_publication_lock`，不接受 raw evidence，不实现 standalone wrapper。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_publication_uses_existing_outer_lease -q
```

- [ ] **叶步骤 5：mutation / reread gate**

acquisition counter 对 core 精确为 0；active/same-root carrier 成功，所有 G3 invalid rows 在 I/O 前失败；
final bytes/hash exact 等于 carrier。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): publish smoke evidence under existing lease"
```

##### V00-G5：atomic fault 与 ordinary-temp convergence

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_publication_is_old_or_complete_new
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_publication_is_old_or_complete_new -q
```

Expected: 只因 publication fault closure 缺席而 FAIL；G1–G4 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

在 G4 core 的 create/write/fsync/close/replace/reread 前后加入 private one-shot fault checkpoints。
每次 write 开始时，在 active lease 下调用 G1：只删除 exact ordinary orphan temp；
由 G5 把 reparse/directory/nonregular state 映射并抛 `smoke_evidence_residual_corrupt` 且保持对象。任一 fault 后 final 只能是
完整旧 bytes 或完整新 bytes；下次调用清理普通 temp并收敛。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_publication_is_old_or_complete_new -q
```

- [ ] **叶步骤 5：mutation / reread gate**

每个 checkpoint 注入一次并 strict-reread final，禁止 partial bytes；普通 temp、illegal temp 与相似非
exact 名称逐项测试。下一次 publish 必须收敛新 bytes，under-lock acquisition counter仍为 0。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): publish smoke evidence atomically"
```

##### V00-G6：strictly no-write check under existing lease

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_check_is_no_write_under_existing_lease
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_check_is_no_write_under_existing_lease -q
```

Expected: 只因 under-lock check 缺席而 FAIL；G1–G5 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
check_smoke_evidence_under_lock(
    root: Path,
    prepared: ValidatedSmokeEvidence,
    lease: PublicationLockLease,
) -> list[ValidationIssue]
```

先调用 G3 helper并保持其 lease/carrier 错误分区，再只读取 final 与 G1 state；clean/missing/changed/temp residual分别返回稳定
`ValidationIssue`；ordinary temp 只报告不删除，illegal temp 精确返回
`ValidationIssue(code="smoke_evidence_residual_corrupt")`，不得把 G1 state 转成异常。不得 acquire、recovery、mkdir、write、replace、
rename 或 unlink。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_check_is_no_write_under_existing_lease -q
```

- [ ] **叶步骤 5：mutation / reread gate**

clean/missing/changed/temp/illegal type 各比较完整 namespace、Git status 与 lock bytes；monkeypatch 全部
写 API 为一调用即 fail。under-lock acquisition counter为 0，stale/foreign/forged rows 在 evidence
read 前失败。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): check smoke evidence without writes"
```

##### V00-G7：single-acquisition standalone wrappers

**Files:**
- `tools/stage0c_fixtures/verification.py`
- `tests/stage0c/test_harness_verification.py`

- [ ] **叶步骤 1：只写一个参数化 RED node**

```text
tests/stage0c/test_harness_verification.py::test_evidence_standalone_wrappers_acquire_once
```

- [ ] **叶步骤 2：运行 RED**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_standalone_wrappers_acquire_once -q
```

Expected: 只因 public wrappers 缺席而 FAIL；G1–G6 保持 GREEN。

- [ ] **叶步骤 3：最小实现**

```text
publish_smoke_evidence(
    root: Path,
    evidence: JsonObject,
    matrix: JsonObject,
    manifest: JsonObject,
) -> str
check_smoke_evidence(
    root: Path,
    evidence: JsonObject,
    matrix: JsonObject,
    manifest: JsonObject,
) -> list[ValidationIssue]
```

每个 wrapper 恰 acquire/release 一次；在同一 context 中依次调用 G2 prepare→G4/G6 under-lock core。
under-lock API 不得递归 acquire；L01 已持 authoritative outer lease 时只调用 under-lock APIs。
isolated publication probes 只在不同 fresh root 调用 tree-publication public wrapper，从不接收 authoritative
lease。

- [ ] **叶步骤 4：GREEN**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py::test_evidence_standalone_wrappers_acquire_once -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py -q
```

- [ ] **叶步骤 5：mutation / reread gate**

publish/check 分别计数恰一次 acquire/release；第二进程在 prepare→publish/check→reread 全生命周期观察
busy；check wrapper namespace 前后相同。CLI test另证明 authoritative outer lifecycle acquisition
精确一次且没有调用本叶 wrappers。

- [ ] **叶步骤 6：唯一 commit**

```powershell
git add -- tools/stage0c_fixtures/verification.py tests/stage0c/test_harness_verification.py
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): add single-lock smoke evidence wrappers"
```

### Task L01：Stage 0C CLI

**Files:**
- Create: `tools/stage0c_fixtures/cli.py`
- Create: `tests/stage0c/test_cli.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 写四 verb frozen-input mutation matrix**

参数化 `checklist/write/check/verify-harness/verify-harness --check` × `missing,size drift,hash drift,schema drift,source set drift,clause set drift,214/259/75/98/51/55 count drift`；每个组合必须在任何 output/lock operation 前返回 frozen-input error。测试比较 repository namespace snapshot 前后相等。

- [ ] **Step 2: 写真实 busy matrix**

用 P01 第二进程 holder 持有 lock，分别运行 `write`、`check`、`verify-harness` 与 `verify-harness --check`，四种 invocation 必须返回 `publication_busy`；holder 期间及退出后 lock raw bytes 都为零。`checklist` 不取 publication lock，但仍执行全部 frozen-input 校验，并只把 canonical checklist 写 stdout，不写 repository。

- [ ] **Step 3: 写 verify 锁生命周期红灯**

先写并运行以下 exact integration nodes：

```text
tests/stage0c/test_cli.py::test_verify_harness_uses_one_outer_lock_for_full_lifecycle
tests/stage0c/test_cli.py::test_verify_harness_check_uses_one_outer_lock_without_writes
tests/stage0c/test_cli.py::test_invalid_evidence_never_creates_temp_or_replaces_final
```

前两个节点以 acquisition counter 断言一次 CLI invocation 恰好 acquire/release 一次 outer lock；在
matrix execution、完整 evidence validation、temp create、replace 与 reread 各 pause point，第二进程
仍观察 `publication_busy`。第三节点注入一份只有一个 semantic defect 的 builder result，断言取得 outer
lock 后 full validator 拒绝，temp 未出现，final 与整个 authoritative namespace 逐 bytes 不变。

runner callback 在 matrix 读取后暂停；第二进程此时执行 `check` 必须 busy。再分别在最后 outcome 收集、evidence temp 写入、`os.replace` 后 reread 阶段暂停，第二进程仍必须 busy。只有 evidence 完整 reread/hash 验证结束后才释放 lock。

- [ ] **Step 4: 运行红灯**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_cli.py -q
```

- [ ] **Step 5: 写 final CLI**

冻结唯一 lock ownership 与发布顺序：`verify-harness` 先且只先执行一次
`with acquire_publication_lock(root) as lease`，并让该 context 覆盖 matrix execution 到 final reread。
在同一 lease 中依次 build evidence → 调用
`prepare_validated_smoke_evidence_under_lock(..., lease)`；该 factory 内部且只执行一次 canonical
serialize/strict-reread、完整 `validate_smoke_evidence` 与 `issues == [] and passed is True` 门，然后返回
opaque carrier → `publish_smoke_evidence_under_lock(..., lease)` temp/replace/reread。任何 validation
failure 均发生在 temp create 前。`verify-harness --check` 同样只 acquire 一次，再用 factory 验证正式
evidence，最后调用 `check_smoke_evidence_under_lock(..., lease)`；全程零写。CLI 已持 outer lease 时禁止
调用 standalone evidence wrappers；三个 under-lock API 均禁止递归 acquire。`write` 与 `check` 则不先
创建第二层 outer context，分别直接调用 tree publication/check standalone wrapper，各自只 acquire 一次。

`checklist` strict-load inputs并把 F04 canonical checklist 写 stdout；`write` recover+publish exact 265；`check` lock+零写比较 exact tree；`verify-harness` 持 outer repository lock后重读 canonical matrix，为 publication probes 建立 repository 外的临时 parent与逐 probe fresh roots，执行后清理 probe roots，再写 evidence temp、replace、reread并释放 outer lock；`verify-harness --check` lock+只读验证正式 evidence。publication probe 从不重新获取 outer lock或触碰 authoritative publication namespace。四 verbs 均先执行 F03 frozen-input validation。CLI 顶层只在一个边界 `except Stage0CError as exc`，向 stderr 输出 `exc.code` 并非零退出；禁止 catch 后返回另一种带 `.code` 的 error result。

在 `pyproject.toml` 增加 `amadeus-stage0c = "tools.stage0c_fixtures.cli:main"`，不改变 Stage 0A/0B scripts。

- [ ] **Step 6: 运行绿灯与正式路径仍缺席检查**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_cli.py -q
.\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli check --root .
```

Expected: PASS；L01 不运行实际 `verify-harness`，正式 evidence path 仍缺席。

- [ ] **Step 7: 显式暂存、提交并冻结工具源码**

```powershell
git add tools/stage0c_fixtures/cli.py tests/stage0c/test_cli.py pyproject.toml
git diff --cached --check
git diff --cached --stat
git commit -m "feat(stage0c): expose final fixture toolchain cli"
git status --short -- tools
```

Expected: 最后一条无输出。

### Task V01：用 final CLI 生成正式 smoke evidence

**Files:**
- Generate only: `outputs/verification/Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json`

[FRAME｜置信度：高] V01 开始后禁止修改 `tools/**/*.py`。若实际 evidence 暴露工具缺陷，删除未提交 evidence，回到对应代码节点修复并重跑下游；不得在 V01 就地改工具。

[FRAME｜置信度：高] Step 1–3 必须复制以下单一 PowerShell fence，并在同一进程一次执行；三个 checkbox 只在整个 one-shot fence 通过后共同勾选。

- [ ] **Step 1: 捕获 final source tree 与 tools Git preflight**
- [ ] **Step 2: 实际执行、replace、reread**
- [ ] **Step 3: 重算 evidence、provenance 与 source freeze**

```powershell
function Get-Stage0CSourceSnapshot {
  @(
    Get-ChildItem tools/stage0c_fixtures -Recurse -File -Filter *.py |
      Sort-Object FullName |
      ForEach-Object {
        [pscustomobject]@{
          Path = $_.FullName
          Size = $_.Length
          Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
      }
  )
}

$beforeGitStatus = @(git status --porcelain=v1 --untracked-files=all -- tools)
if ($LASTEXITCODE -ne 0 -or $beforeGitStatus.Count -ne 0) {
  throw 'tools preflight is not clean'
}
$beforeSource = @(Get-Stage0CSourceSnapshot)

.\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli verify-harness --root .
if ($LASTEXITCODE -ne 0) { throw 'verify-harness write failed' }
.\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli verify-harness --root . --check
if ($LASTEXITCODE -ne 0) { throw 'verify-harness check failed' }
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/test_harness_verification.py tests/stage0c/test_cli.py -q
if ($LASTEXITCODE -ne 0) { throw 'harness verification tests failed' }

$afterSource = @(Get-Stage0CSourceSnapshot)
$beforeJson = ConvertTo-Json -InputObject @($beforeSource) -Compress -Depth 4
$afterJson = ConvertTo-Json -InputObject @($afterSource) -Compress -Depth 4
if ($beforeJson -cne $afterJson) { throw 'stage0c source tree changed during V01' }
$afterGitStatus = @(git status --porcelain=v1 --untracked-files=all -- tools)
if ($LASTEXITCODE -ne 0 -or $afterGitStatus.Count -ne 0) {
  throw 'tools changed during V01'
}
```

Expected: one-shot fence exit code 0；正式 evidence 是普通 canonical JSON file；sibling temp 缺席；lock 为零字节；测试独立重算三个 provenance preimage、event log hash、每个 result/outcome hash 与 passed 合取条件；source snapshot 与 tools Git status 前后逐字相等。

- [ ] **Step 4: 显式暂存与提交**

```powershell
git add outputs/verification/Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): record final harness smoke evidence"
git status --short -- tools
```

Expected: 最后一条无输出。

### Task Q01：全套回归、新 checkout 与 no-write 门禁

**Files:**
- Modify: `tests/test_repository_checkout_contract.py`
- Modify: `tests/stage0c/test_current_generated.py`

- [ ] **Step 1: 写 checkout/no-write 红灯**

测试比较 primary worktree 与 detached worktree 的 265 generated files、正式 evidence、lock carrier raw bytes；在 detached worktree 运行 `check`、实际 `verify-harness`、`verify-harness --check` 后再次比较 hashes。`check` 前后还比较 journal/residual namespace、Git status 与 lock bytes。

- [ ] **Step 2: 运行唯一临时 worktree 脚本**

从 repository root 原样运行：

```powershell
$root = (Resolve-Path .).Path
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('amadeus-stage0c-q01-' + [guid]::NewGuid().ToString('N'))
function Assert-NativeSuccess([string]$step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$step failed with exit code $LASTEXITCODE"
  }
}
$originalPaths = @(
  'fixtures/stage0c/generated',
  'outputs/verification/Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json',
  'fixtures/stage0c/.stage0c-write.lock'
)
$primaryStatusBefore = @(git status --porcelain=v1 --untracked-files=all)
Assert-NativeSuccess 'capture primary status before'
$originalHashes = Get-ChildItem $originalPaths -Recurse -File | ForEach-Object {
  $relative = $_.FullName.Substring($root.Length + 1).Replace('\','/')
  [pscustomobject]@{
    Path = $relative
    Size = $_.Length
    Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
  }
} | Sort-Object Path
if ($originalHashes.Count -ne 267) {
  throw "primary artifact count was $($originalHashes.Count), expected 267"
}
try {
  git worktree add --detach $temp HEAD
  Assert-NativeSuccess 'git worktree add'
  .\.venv\Scripts\python.exe -B -m venv (Join-Path $temp '.venv')
  Assert-NativeSuccess 'create detached virtual environment'
  Push-Location $temp
  try {
    .\.venv\Scripts\python.exe -B -m pip install -e ".[test]"
    Assert-NativeSuccess 'install detached test environment'
    $detachedStatusBefore = @(git status --porcelain=v1 --untracked-files=all)
    Assert-NativeSuccess 'capture detached status before'
    .\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli check --root .
    Assert-NativeSuccess 'detached check'
    .\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli verify-harness --root .
    Assert-NativeSuccess 'detached verify-harness'
    .\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli verify-harness --root . --check
    Assert-NativeSuccess 'detached verify-harness check'
    $detachedHashes = Get-ChildItem $originalPaths -Recurse -File | ForEach-Object {
      $relative = $_.FullName.Substring($temp.Length + 1).Replace('\','/')
      [pscustomobject]@{
        Path = $relative
        Size = $_.Length
        Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
      }
    } | Sort-Object Path
    if ($detachedHashes.Count -ne 267) {
      throw "detached artifact count was $($detachedHashes.Count), expected 267"
    }
    if (
      ($originalHashes | ConvertTo-Json -Compress) -cne
      ($detachedHashes | ConvertTo-Json -Compress)
    ) {
      throw 'detached worktree artifact hash mismatch'
    }
    if ((Get-Item fixtures/stage0c/.stage0c-write.lock).Length -ne 0) {
      throw 'lock carrier changed size'
    }
    $detachedStatusAfter = @(git status --porcelain=v1 --untracked-files=all)
    Assert-NativeSuccess 'capture detached status after'
    if (
      ($detachedStatusBefore | ConvertTo-Json -Compress) -cne
      ($detachedStatusAfter | ConvertTo-Json -Compress)
    ) {
      throw 'detached worktree status changed'
    }
  }
  finally {
    Pop-Location
  }
}
finally {
  Set-Location $root
  git worktree remove --force $temp
  $removeExit = $LASTEXITCODE
  git worktree prune
  Assert-NativeSuccess 'git worktree prune'
  if (($removeExit -ne 0) -and (Test-Path -LiteralPath $temp)) {
    throw "git worktree remove failed with exit code $removeExit"
  }
}
if (Test-Path -LiteralPath $temp) {
  throw 'temporary worktree cleanup failed'
}
$primaryStatusAfter = @(git status --porcelain=v1 --untracked-files=all)
Assert-NativeSuccess 'capture primary status after'
if (
  ($primaryStatusBefore | ConvertTo-Json -Compress) -cne
  ($primaryStatusAfter | ConvertTo-Json -Compress)
) {
  throw 'primary worktree status changed'
}
```

[FRAME｜置信度：高] 本脚本只有一个 GUID temp worktree，明确使用 `git worktree add --detach $temp HEAD`，在 detached worktree 内创建自己的 `.venv`，逐条检查 native exit code，运行 check、实际 verify、evidence check 和 267 项 path/size/hash comparison，并在 `finally` 执行 worktree remove/prune；脚本结尾还证明 primary Git status 没有变化。

- [ ] **Step 3: 运行完整门禁**

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0a -q
.\.venv\Scripts\python.exe -B -m pytest tests/stage0b -q
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb -q
.\.venv\Scripts\python.exe -B -m pytest tests/test_repository_checkout_contract.py -q
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\python.exe -B -m tools.stage0a_sources.cli check --root . --output-dir fixtures/stage0a/generated
.\.venv\Scripts\python.exe -B -m tools.stage0b_adjudication.cli check --root .
.\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli check --root .
.\.venv\Scripts\python.exe -B -m tools.stage0c_fixtures.cli verify-harness --root . --check
.\.venv\Scripts\python.exe -B -m tools.project_kb.cli --root . check
git diff --check
git status --short
```

Expected: 所有命令 exit code 0；Git status 只列出 Q01 的两个 exact test files；`git status --short -- tools` 无输出。

- [ ] **Step 4: 显式暂存与提交**

```powershell
git add tests/test_repository_checkout_contract.py tests/stage0c/test_current_generated.py
git diff --cached --check
git diff --cached --stat
git commit -m "test(stage0c): close fixture toolchain gate"
```

### Task D01：执行记录、README 与知识库

**Files:**
- Create: `outputs/Amadeus-Core-v0.1-Stage0C-执行记录-2026-07-29.md`
- Modify: `README.md`
- Modify: `knowledge/data_structure.md`
- Modify: `knowledge/manifest.json`
- Modify: `tests/project_kb/test_current_repository.py`

- [ ] 写 KB 红灯：document count 从 P00 的 34 增至 35；执行记录必须被 manifest allowlist、README/read-order 与 data_structure 导航引用，hash 必须匹配。
- [ ] 执行记录只写实际命令、测试计数、generated artifact hashes、tree hash、evidence hash、Git commit 与 readiness；不得把 smoke 解释为 98 个 S case 或真实 Core execution。
- [ ] 先完成执行记录、README 与 `knowledge/data_structure.md` 最终字节，再更新 count test，重算三份文档 hash，最后更新 manifest 的三个 hash/新增记录；manifest 更新后不得再次编辑这三份文档。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb -q
.\.venv\Scripts\python.exe -B -m tools.project_kb.cli --root . check
.\.venv\Scripts\python.exe -B -m pytest -q
git diff --check
```

Expected: 全部 exit code 0；KB 精确为 35 indexed documents 与 0 raw paths。

- [ ] 显式暂存与提交：

```powershell
git add outputs/Amadeus-Core-v0.1-Stage0C-执行记录-2026-07-29.md README.md knowledge/data_structure.md knowledge/manifest.json tests/project_kb/test_current_repository.py
git diff --cached --check
git diff --cached --stat
git commit -m "docs: record stage0c fixture conversion evidence"
```

## 11. Git 节点清单

[FRAME｜置信度：高] 实施必须形成以下 91 个顺序可审计节点；Task ID 仍为 43 个，但 R/P/V 的风险叶、13 个 batch audit carrier 与 C01 pure/publish 边界各自提交。并行分支只改变准备时间，不改变下列 integration 顺序：

1. `docs: freeze reviewed stage0c fixture conversion plan`
2. `feat(stage0c): freeze package constants and lock carrier`
3. `feat(stage0c): add strict canonical json io`
4. `test(stage0c): freeze stage0c input identities`
5. `feat(stage0c): build conversion checklist in memory`
6. `feat(stage0c): define fixture case dsl`
7. `feat(stage0c): define exact nested schemas`
8. `feat(stage0c): bind handler parameter schemas`
9. `feat(stage0c): validate reviewed clause mappings`
10. `feat(stage0c): compile reviewed fixture cases`
11. `data(stage0c): review conversion batch B01`
12. `audit(stage0c): record conversion review batch B01`
13. `data(stage0c): review conversion batch B02`
14. `audit(stage0c): record conversion review batch B02`
15. `data(stage0c): review conversion batch B03`
16. `audit(stage0c): record conversion review batch B03`
17. `data(stage0c): review conversion batch B04`
18. `audit(stage0c): record conversion review batch B04`
19. `data(stage0c): review conversion batch B05`
20. `audit(stage0c): record conversion review batch B05`
21. `data(stage0c): review conversion batch B06`
22. `audit(stage0c): record conversion review batch B06`
23. `data(stage0c): review conversion batch B07`
24. `audit(stage0c): record conversion review batch B07`
25. `data(stage0c): review conversion batch B08`
26. `audit(stage0c): record conversion review batch B08`
27. `data(stage0c): review conversion batch B09`
28. `audit(stage0c): record conversion review batch B09`
29. `data(stage0c): review conversion batch B10`
30. `audit(stage0c): record conversion review batch B10`
31. `data(stage0c): review conversion batch B11`
32. `audit(stage0c): record conversion review batch B11`
33. `data(stage0c): review conversion batch B12`
34. `audit(stage0c): record conversion review batch B12`
35. `data(stage0c): review conversion batch B13`
36. `audit(stage0c): record conversion review batch B13`
37. `test(stage0c): close reviewed conversion and audit sets`
38. `feat(stage0c): add static handler registry`
39. `feat(stage0c): add fresh sandbox context and reset`
40. `feat(stage0c): execute atomic sandbox setup`
41. `feat(stage0c): add deterministic core driver`
42. `feat(stage0c): add hermetic fake adapters and backend`
43. `feat(stage0c): apply atomic sandbox state patches`
44. `feat(stage0c): commit state and effects atomically`
45. `feat(stage0c): dispatch stimuli and build receipts`
46. `feat(stage0c): build step executions and effect diffs`
47. `feat(stage0c): evaluate receipt and state assertions`
48. `feat(stage0c): evaluate effect output and replay assertions`
49. `feat(stage0c): freeze idempotency hash preimages`
50. `feat(stage0c): enforce idempotent sandbox replay`
51. `feat(stage0c): run validation reset and setup phases`
52. `feat(stage0c): run snapshot stimulus and after phases`
53. `feat(stage0c): stop on primary assertion failure`
54. `feat(stage0c): finalize cleanup and sandbox run results`
55. `feat(stage0c): acquire immutable publication lock`
56. `feat(stage0c): validate publication paths and journals`
57. `feat(stage0c): persist durable publication journals`
58. `feat(stage0c): write verified publication staging trees`
59. `feat(stage0c): publish deterministic generated trees`
60. `feat(stage0c): add no-op write and no-write check`
61. `feat(stage0c): recover literal publication states`
62. `test(stage0c): reject illegal publication state complement`
63. `feat(stage0c): normalize publication journal temps`
64. `test(stage0c): enforce publication residual and handle rules`
65. `feat(stage0c): freeze publication fault probe catalog`
66. `test(stage0c): exercise publication interruption points`
67. `test(stage0c): close recovery fault convergence`
68. `feat(stage0c): compile handler manifest`
69. `feat(stage0c): generate harness smoke matrix`
70. `feat(stage0c): build current generated tree in memory`
71. `data(stage0c): publish generated fixture definitions`
72. `feat(stage0c): compute harness evidence provenance`
73. `feat(stage0c): validate exact smoke evidence schema`
74. `feat(stage0c): bind smoke results outcomes and events`
75. `feat(stage0c): freeze smoke outcome input hashes`
76. `feat(stage0c): enforce complete smoke evidence pass gate`
77. `feat(stage0c): execute actual handler smoke probes`
78. `feat(stage0c): execute actual sandbox smoke probes`
79. `feat(stage0c): execute isolated publication smoke probes`
80. `feat(stage0c): build callback-derived smoke execution bundle`
81. `feat(stage0c): classify smoke evidence publication paths`
82. `feat(stage0c): prepare validated smoke evidence bytes`
83. `feat(stage0c): bind smoke evidence carrier to root`
84. `feat(stage0c): publish smoke evidence under existing lease`
85. `feat(stage0c): publish smoke evidence atomically`
86. `feat(stage0c): check smoke evidence without writes`
87. `feat(stage0c): add single-lock smoke evidence wrappers`
88. `feat(stage0c): expose final fixture toolchain cli`
89. `test(stage0c): record final harness smoke evidence`
90. `test(stage0c): close fixture toolchain gate`
91. `docs: record stage0c fixture conversion evidence`

[FRAME｜置信度：高] 每个节点只在其 exact 单节点与叶级文件测试通过后创建。batch data commit 后紧跟对应 audit commit；任何 record 所引用历史禁止 rebase/squash。任何已提交节点被后续证据推翻时，建立新的修正 commit并重跑全部下游依赖，不改写既有 Git 历史。

## 12. 计划自检

- [COMPUTED｜置信度：高] 13 批计数为 `12×20+19=259`，每个 clause ID 与 reviewed filename 均被明确列出一次。
- [COMPUTED｜置信度：高] 计划覆盖独立计划审查、constants、I/O、checklist、DSL、schema、reviewed semantic mappings、compiler、handler manifest、smoke matrix、sandbox、publication、verification engine、final CLI、正式 evidence、detached checkout、docs 与 KB。
- [COMPUTED｜置信度：高] 43 个 Task ID 被细化为 47 个 R/P/V 风险叶与 C01 两个边界叶，合计 49 个风险叶、91 个顺序可审计 commits；每个代码、数据或审计节点都有 exact RED、最小 implementation delta、GREEN、mutation/reread gate 与唯一 commit。
- [COMPUTED｜置信度：高] generated 与 reviewed 权威层分离；smoke 与真实 case/Core execution 分离。
- [COMPUTED｜置信度：高] F04 不发布 partial generated；C01 首次发布 exact 265 files；V00 不写正式 evidence，L01 冻结最终 CLI，V01 才生成正式 evidence。
- [COMPUTED｜置信度：高] publication 的真实第二进程 lock、Windows 开放句柄、Ø/I/P/X 非法补集、journal/residual、fault injection、完整快照不变、no-write check 与 detached-checkout bytes 均有明确测试节点；sandbox 的 validation/reset/setup/before_snapshot/stimulus/after_snapshot/assertion phase failure 逐项冻结。
- [COMPUTED｜置信度：高] P00 先冻结计划/review，在 README/navigation 未变且既有 32 条 hash 仍有效时取得精确 32→34 RED；随后才冻结两份导航、重算四 hash 并最后写 manifest。
- [COMPUTED｜置信度：高] 完成定义没有把 H/J rubric、S smoke、case definition coverage、catalog 或 release 相互替代。

[我打破的规则 / RULES I BROKE]：无。
