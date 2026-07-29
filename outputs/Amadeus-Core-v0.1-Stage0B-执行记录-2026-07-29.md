# Amadeus Core v0.1 Stage 0B 执行记录（2026-07-29）

## 0. 反方结论

[KNOWN｜置信度：高] Stage 0B 完成不等于 fixture catalog、case coverage、Core release 或 Amadeus v0.1 完成。本节点只证明 214 个冻结来源的 oracle 与 atomicity 已显式裁决，并可确定性编译为 source-clause manifest。

## 1. 执行范围

[KNOWN｜置信度：高] 权威工作区：`D:\amadues bot\Amadeus`。

[KNOWN｜置信度：高] 执行依据：

- [Stage 0B 来源裁决实施计划](Amadeus-Core-v0.1-Stage0B-来源裁决实施计划.md)
- [Stage 0B 实施计划审查记录](Amadeus-Core-v0.1-Stage0B-实施计划审查记录-2026-07-29.md)
- Stage 0A 四份 frozen generated JSON

[FRAME｜置信度：高] 本次未生成 executable case、fixture DSL、S 动作沙箱、H/J reviewer 流程或 catalog；这些内容保留到 Stage 0C/0D。

## 2. Git 节点

| 节点 | Commit | [KNOWN] 内容 |
|---|---|---|
| [FRAME] 计划与审查 | `f700b6a` | Stage 0B 叶级计划、反例审查、README/知识库入口 |
| [FRAME] 冻结 checklist | `3bede47` | 四输入身份门禁、214 项 deterministic checklist |
| [FRAME] strict schema | `254fcee` | exact source set、oracle、binding、atomicity 与 clause 拒绝条件 |
| [FRAME] 人工裁决数据 | `c586d1b` | 95 个 Core oracle、214 个 atomicity decision、259 个 clause |
| [FRAME] 编译与 CLI | `3bd2baf` | source-clause manifest、readiness report、`write/check` 与 console script |

[KNOWN｜置信度：高] 上述每个节点均已推送到 `origin/codex/project-kb-stage0b-bootstrap`。

## 3. 输入身份

| 输入 | [COMPUTED] SHA-256 | [COMPUTED] 字节数 |
|---|---:|---:|
| `source_index_v0_1.json` | `D29855B5F8ED870608CF52B91A9997E4D41922E4085FBAE41E385610D87DE25C` | 229060 |
| `oracle_assignment_worklist_v0_1.json` | `7BD9350A108B4274FA07D83A1315FC33226504DCD998DAA17AE3ED83C917DE51` | 62790 |
| `atomicity_worklist_v0_1.json` | `D93342C7E93F4C368DF44989BB3B341AAB364B472E9B6150FC7B97E469D0BFD2` | 85569 |
| `source_toolchain_report_v0_1.json` | `3154019197C1B6C16E951F278E9688F1DD6D18459BD5D2B3AD71A87C92BBD3F0` | 337 |

[COMPUTED｜置信度：高] Stage 0B 读取器在 path、size 或 SHA-256 任一漂移时拒绝继续。

## 4. 裁决结果

### 4.1 Oracle

| 来源组 | [COMPUTED] 结果 |
|---|---:|
| Core | 95 项显式分配；`D=42`、`D+S=52`、`D+H=1` |
| baseline + increment | 119 项保留 source-declared oracle，无降级 |
| 总计 | 214 项非空、canonical、有来源特定 rationale |

[KNOWN｜置信度：高] oracle canonical 顺序为 `D,S,H,J`。Core 没有 source-group 默认值；每项决定都绑定 `source_id` 与 `source_binding_sha256`。

### 4.2 Atomicity

| 指标 | [COMPUTED] 结果 |
|---|---:|
| atomic 来源 | 185 |
| composite 来源 | 29 |
| 来源总数 | 214 |
| clause 总数 | 259 |
| pending review | 0 |

[KNOWN｜置信度：高] composite 决策显式列出独立 setup/action；atomic 来源精确含一个 clause。所有 clause ID 从 `SOURCE_ID#1` 连续编号，stimulus/expected scope 与 oracle 均非空。

## 5. 产物身份

| 产物 | [COMPUTED] SHA-256 | [COMPUTED] 字节数 |
|---|---:|---:|
| `fixtures/stage0b/generated/adjudication_checklist_v0_1.json` | `BB8570775049B60A933F8EBB4C2490E039B2C02AF082C4E9C64AEF3BD7B4568D` | 121508 |
| `fixtures/stage0b/reviewed/source_decisions_v0_1.json` | `CC1259BB4A3987AA67054D254A6F61B0734C9E0B0193E68DAF749A3F67ECD0C8` | 191835 |
| `fixtures/stage0b/generated/source_clause_manifest_v0_1.json` | `DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C` | 252478 |
| `fixtures/stage0b/generated/stage0b_report_v0_1.json` | `F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8` | 585 |

[COMPUTED｜置信度：高] 连续两次 `write` 后 manifest 与 report 的 SHA-256 均保持不变；`check` 只读并比较完整的 missing/changed/unexpected 集合。

## 6. 验证证据

执行命令：

```powershell
py -3.12 -B -m pytest tests/stage0b -q
py -3.12 -B -m pytest -q
py -3.12 -B -m tools.stage0a_sources.cli check
py -3.12 -B -m tools.stage0b_adjudication.cli check --root .
py -3.12 -B -m tools.project_kb.cli --root . check
git diff --check
```

结果：

```text
Stage 0B: 33 passed
Full suite: 127 passed
source_toolchain_ready=true
pending_oracle_assignments=95
pending_atomicity_reviews=214
source_adjudication_ready=true
reviewed_sources=214
pending_oracle_assignments=0
pending_atomicity_reviews=0
case_coverage_complete=false
catalog_ready=false
release_ready=false
project_kb_ready=true
indexed_documents=30
raw_paths_indexed=0
```

[KNOWN｜置信度：高] Stage 0A 报告中的 95/214 是其冻结 worklist 的历史边界；Stage 0B 报告中的 0/0 是 reviewed manifest 的完成状态。两者服务不同阶段，不构成矛盾。

## 7. Readiness 裁决

| 标志 | [KNOWN] 值 |
|---|---|
| `source_toolchain_ready` | `true` |
| `source_adjudication_ready` | `true` |
| `atomicity_complete` | `true` |
| `case_coverage_complete` | `false` |
| `catalog_ready` | `false` |
| `release_ready` | `false` |

[INFERRED｜置信度：高] 下一个有效节点是 Stage 0C 计划：消费 frozen source-clause manifest，设计 clause→case binding、fixture DSL 与 S sandbox；不重新解析源 Markdown 或重做 Stage 0B 裁决。

[我打破的规则 / RULES I BROKE]：无。
