# Amadeus Core v0.1 Stage 0B：来源裁决实施计划

> [KNOWN｜置信度：高] 状态：已于 2026-07-29 执行完成；结果见 [Stage 0B 执行记录](Amadeus-Core-v0.1-Stage0B-执行记录-2026-07-29.md)。Stage 0B 只冻结来源级 oracle 与原子性裁决，不生成可执行 case，不进入 Stage 0C。

## 0. 反方边界

[KNOWN｜置信度：高] Stage 0A 证明的是来源编译工具链可重复运行，不是 214 项评测已经完成。当前仍有 95 个 Core 来源未分配 oracle，214 个来源未完成 atomicity review。

[FRAME｜置信度：高] Stage 0B 禁止三种捷径：把 95 个 Core 来源统一默认为 D；从标点自动拆句并把结果冒充人工裁决；把 source-clause manifest 误报为可执行 fixture catalog。

[FRAME｜置信度：高] 本阶段的完成含义仅为：每个来源都具有显式、可审计、绑定原文哈希的 oracle 与 clause 决策。`case_coverage_complete`、`catalog_ready`、`release_ready` 必须继续为 `false`。

## 1. 冻结输入

| 输入 | SHA-256 | 字节数 |
|---|---:|---:|
| [KNOWN] `fixtures/stage0a/generated/source_index_v0_1.json` | `D29855B5F8ED870608CF52B91A9997E4D41922E4085FBAE41E385610D87DE25C` | 229060 |
| [KNOWN] `fixtures/stage0a/generated/oracle_assignment_worklist_v0_1.json` | `7BD9350A108B4274FA07D83A1315FC33226504DCD998DAA17AE3ED83C917DE51` | 62790 |
| [KNOWN] `fixtures/stage0a/generated/atomicity_worklist_v0_1.json` | `D93342C7E93F4C368DF44989BB3B341AAB364B472E9B6150FC7B97E469D0BFD2` | 85569 |
| [KNOWN] `fixtures/stage0a/generated/source_toolchain_report_v0_1.json` | `3154019197C1B6C16E951F278E9688F1DD6D18459BD5D2B3AD71A87C92BBD3F0` | 337 |

[FRAME｜置信度：高] 任一输入字节漂移都必须令 Stage 0B `check` 非零退出；修订输入时先建立新的 Stage 0A 节点与新版本标识，不覆盖本表。

## 2. 交付物与目录

```text
fixtures/stage0b/
  reviewed/
    source_decisions_v0_1.json
  generated/
    adjudication_checklist_v0_1.json
    source_clause_manifest_v0_1.json
    stage0b_report_v0_1.json
tools/stage0b_adjudication/
  __init__.py
  constants.py
  io.py
  checklist.py
  schema.py
  compiler.py
  cli.py
tests/stage0b/
  test_checklist.py
  test_schema.py
  test_compiler.py
  test_cli.py
```

[FRAME｜置信度：高] `adjudication_checklist_v0_1.json` 由 Stage 0A 两份 worklist 确定性生成，精确列出 214 个来源及其 binding、现有 oracle、action、expected 和待填字段。它是逐项人工工作的叶级清单，不是裁决结果。

[FRAME｜置信度：高] `source_decisions_v0_1.json` 是唯一人工维护输入。`source_clause_manifest_v0_1.json` 与 `stage0b_report_v0_1.json` 只能由编译器生成，禁止手改。

## 3. 数据合同

### 3.1 reviewed manifest

```json
{
  "schema_version": "0.1",
  "input_artifacts": {
    "source_index_v0_1.json": "<SHA256>",
    "oracle_assignment_worklist_v0_1.json": "<SHA256>",
    "atomicity_worklist_v0_1.json": "<SHA256>",
    "source_toolchain_report_v0_1.json": "<SHA256>"
  },
  "decisions": [
    {
      "source_id": "AC-001",
      "source_group": "core",
      "source_binding_sha256": "<SHA256>",
      "assigned_oracle_kinds": ["D"],
      "oracle_rationale": "<非空、来源特定的理由>",
      "atomicity_decision": "atomic",
      "atomicity_rationale": "<非空、来源特定的理由>",
      "clauses": [
        {
          "clause_id": "AC-001#1",
          "stimulus_scope": "<本 clause 的动作范围>",
          "expected_scope": "<本 clause 的断言范围>",
          "required_oracle_kinds": ["D"]
        }
      ]
    }
  ]
}
```

### 3.2 oracle 规则

| 代码 | [FRAME] 含义 | [FRAME] 使用条件 |
|---|---|---|
| `D` | 确定性检查 | 可由返回值、状态、事件、哈希或不变量直接断言 |
| `S` | 有状态/隔离环境检查 | 需要跨步骤、重启、并发、时间或受控外部边界 |
| `H` | 双人复核的人类判断 | 需要语义、风格、关系或表达层面的人工裁决 |
| `J` | 诊断性模型裁判 | 只作诊断/对照；不得替代 D/S 的可计算断言或 H 的最终人工裁决 |

[FRAME｜置信度：高] canonical 顺序固定为 `D,S,H,J`。数组非空、无重复。119 个行为来源必须至少保留 Stage 0A 已声明的 oracle，不得静默降级；95 个 Core 来源必须逐项显式分配并填写来源特定 rationale。

### 3.3 atomicity 规则

1. [FRAME｜置信度：高] `atomic` 精确含一个 clause；`composite` 至少含两个 clause。
2. [FRAME｜置信度：高] clause ID 必须从 `SOURCE_ID#1` 连续编号，不允许跳号、重复或跨来源。
3. [FRAME｜置信度：高] 每个 clause 的 stimulus 与 expected 范围都必须非空；不得只复制标题充当范围。
4. [FRAME｜置信度：高] clause oracle 非空、canonical、有序，并且其并集不得弱于来源级 `assigned_oracle_kinds`。
5. [FRAME｜置信度：高] 只有存在不同动作、生命周期阶段、互斥前提或需要独立执行的断言时才标记 `composite`；分号数量不是裁决依据。

### 3.4 generated manifest

[FRAME｜置信度：高] generated manifest 按 Stage 0A source index 顺序输出一个 source record 和一个或多个 clause record。每个 record 绑定 `source_id`、`source_binding_sha256`、reviewed decision 摘要哈希及 clause 内容哈希；Stage 0C 必须读取这些绑定，而不是重新解析 Markdown。

## 4. CLI 合同

```powershell
py -3.12 -B -m tools.stage0b_adjudication.cli checklist --root .
py -3.12 -B -m tools.stage0b_adjudication.cli write --root .
py -3.12 -B -m tools.stage0b_adjudication.cli check --root .
```

[FRAME｜置信度：高] `checklist` 只写 deterministic checklist；`write` 校验 reviewed manifest 后写两个 generated artifact；`check` 不写文件，逐字节比较 canonical JSON 并拒绝 missing、changed、unexpected 输出。

[FRAME｜置信度：高] 成功摘要固定包含：

```text
source_adjudication_ready=true
reviewed_sources=214
pending_oracle_assignments=0
pending_atomicity_reviews=0
case_coverage_complete=false
catalog_ready=false
release_ready=false
```

## 5. 叶级执行任务

### Task B1：冻结常量与输入身份

**Files:** `constants.py`、`io.py`、`tests/stage0b/test_schema.py`

1. [COMMON] 先写输入缺失、输入 hash 漂移、非 UTF-8、非 JSON 的失败测试。
2. [COMMON] 运行 `py -3.12 -B -m pytest tests/stage0b/test_schema.py -q`，确认红灯来自缺少 Stage 0B 模块。
3. [FRAME] 实现最小读取器：固定四个路径、SHA-256、字节数；拒绝 symlink/junction、绝对路径逃逸和未知 schema version。
4. [COMMON] 重跑专项测试至绿灯。

**Commit:** `test: freeze stage0b input identities`

### Task B2：生成 214 项 deterministic checklist

**Files:** `checklist.py`、`test_checklist.py`、`adjudication_checklist_v0_1.json`

1. [COMMON] 写 exact ID set、source order、binding 对齐、字段投影和 canonical JSON 测试。
2. [FRAME] checklist 必须 join source index、oracle worklist 与 atomicity worklist；任何 missing、duplicate、unexpected 或 binding mismatch 都失败。
3. [FRAME] 输出必须精确 214 项；统计必须为 Core 95、baseline 53、increment 66，source-declared 119、pending oracle 95、pending atomicity 214。
4. [COMMON] 运行 `checklist --root .` 两次，第二次产物 hash 必须不变。

**Commit:** `feat: generate stage0b adjudication checklist`

### Task B3：实现 strict reviewed schema

**Files:** `schema.py`、`test_schema.py`

1. [COMMON] 为所有拒绝条件参数化红灯：缺项、多项、重复项、未知字段、错误类型、空 rationale、非法/乱序/重复 oracle、binding 漂移、atomic/clause 数量不符、clause ID 不连续、空 scope。
2. [FRAME] reviewed decisions 的 ID set 必须与 checklist 精确相等，不以 `len==214` 代替集合相等。
3. [FRAME] 行为来源必须保留 source-declared oracle；Core 来源不得出现 `review_state=pending` 或空 oracle。
4. [COMMON] 实现最小验证器并重跑专项测试。

**Commit:** `feat: validate stage0b reviewed decisions`

### Task B4：逐项完成 95 个 Core oracle 裁决

**Files:** `source_decisions_v0_1.json`

1. [FRAME] 按 checklist 的 Core 顺序逐项阅读 title/action/expected 与对应规范原行。
2. [FRAME] 对每项填写非空 oracle 和来源特定 rationale；禁止按 source_group 批量套用统一理由。
3. [FRAME] 每完成 10 项运行 schema validator；最后一批为 5 项。
4. [FRAME] 复核统计：95/95 explicit，空 rationale 为 0，pending 为 0。

**Commit:** `data: adjudicate core oracle assignments`

### Task B5：逐项完成 214 个 atomicity 裁决

**Files:** `source_decisions_v0_1.json`

1. [FRAME] 对 214 项逐条比较 action 与 expected，选择 atomic/composite 并填写来源特定 rationale。
2. [FRAME] 对 composite 明确每个独立 stimulus/expected scope；对 atomic 仍需写 `#1` clause。
3. [FRAME] 每完成 20 项运行 schema validator；最后一批为 14 项。
4. [FRAME] 专门复核既有复合候选 `EXIT-02`、`EXIT-06`，但不得假定只有这两项为 composite。
5. [FRAME] 完成后核对 214/214、连续 clause ID、0 pending。

**Commit:** `data: adjudicate source atomicity`

### Task B6：编译 source-clause manifest 与报告

**Files:** `compiler.py`、`test_compiler.py`、两个 generated artifact

1. [COMMON] 先写 deterministic compilation、source order、clause binding、decision hash、content hash、计数和 readiness 语义的失败测试。
2. [FRAME] 编译器只消费已验证的 reviewed manifest；不得猜测、补齐或自动改写人工字段。
3. [FRAME] report 必须有 `source_adjudication_ready=true` 和三个 `false` readiness；任何 pending 或 drift 时不写成功报告。
4. [COMMON] 连续运行两次 `write`，确认 generated artifact 的 SHA-256 不变。

**Commit:** `feat: compile stage0b source clause manifest`

### Task B7：CLI 门禁与全套回归

**Files:** `cli.py`、`test_cli.py`、`pyproject.toml`

1. [COMMON] 红灯覆盖 `checklist/write/check` 参数、退出码、stdout/stderr、missing/changed/unexpected 输出。
2. [FRAME] 增加 console script `amadeus-stage0b`，不得改变 Stage 0A CLI。
3. [COMMON] 运行：

```powershell
py -3.12 -B -m pytest tests/stage0b -q
py -3.12 -B -m pytest tests/stage0a -q
py -3.12 -B -m pytest tests/project_kb -q
py -3.12 -B -m pytest -q
py -3.12 -B -m tools.stage0a_sources.cli check
py -3.12 -B -m tools.stage0b_adjudication.cli check --root .
py -3.12 -B -m tools.project_kb.cli --root . check
git diff --check
git status --short
```

4. [COMMON] 把测试计数、输出 artifact SHA-256 与 Git commit 写入 Stage 0B 执行记录。

**Commit:** `test: close stage0b adjudication gate`

## 6. 拒绝条件与完成门

| 门 | [FRAME] 通过条件 |
|---|---|
| Input identity | 四份输入 path/hash/bytes 全部精确匹配 |
| Source set | 214 个 ID 与 binding 精确相等；无 missing/duplicate/unexpected |
| Oracle | 119 项不降级；95 项显式分配；214 项均非空、canonical、有 rationale |
| Atomicity | 214 项显式决定；clause 数量、编号、scope 与 oracle 合法 |
| Determinism | checklist、manifest、report 重写 hash 不变；check 无写入 |
| Readiness | 只声明 source adjudication ready；case/catalog/release 均为 false |
| Regression | Stage 0A、project KB 与全套 pytest 全绿 |
| Git | 工作树只含预期文件；每个完成节点独立 commit 并推送 |

## 7. 回滚与修订

[COMMON｜置信度：高] generated 文件出现 drift 时，修正 reviewed manifest 或编译器后重写，禁止直接修 generated JSON。裁决内容被证据推翻时，建立新 commit 更新对应 decision、重编译并记录原因；不改写既有 Git 历史。

[FRAME｜置信度：高] Stage 0B 通过后，下一份计划是 Stage 0C case-conversion binding。它必须绑定 `clause_id/source_binding_sha256/clause_stimulus_sha256/clause_expected_sha256/case_sha256/stimulus_mapping/assertion_or_rubric_mapping/reviewer/rationale`。

## 8. 计划自检

- [COMPUTED｜置信度：高] 214 项工作由 deterministic checklist 逐条枚举，满足 Stage 0A 的下一计划合同。
- [COMPUTED｜置信度：高] 95 个 Core oracle 没有默认值或自动规则。
- [COMPUTED｜置信度：高] atomicity 是人工裁决，自动化只校验结构与编译输出。
- [COMPUTED｜置信度：高] Stage 0C 的 case 绑定与执行语义未被提前实现。
- [COMPUTED｜置信度：高] 每个任务都有红灯、最小实现、绿灯与 Git 节点。

[我打破的规则 / RULES I BROKE]：无。
