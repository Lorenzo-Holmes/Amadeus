# ADR-002：Amadeus 记忆生命周期

> [KNOWN｜置信度：高] 状态：Proposed / C′ synchronized  
> [KNOWN｜置信度：高] 日期：2026-07-27  
> [KNOWN｜置信度：高] 依赖：ADR-001 的来源类型、身份谱系与分叉语义。  
> [FRAME｜置信度：高] 优先权威：[ADR-006](./ADR-006-Amadeus记忆主权与Core生命周期治理.md) 与 [Amadeus Core v0.1 数据契约](./Amadeus-Core-v0.1-数据契约与状态机规范.md) 取代本 ADR 中旧记忆层、普通用户直接改变权威记录、普通用户控制 Core 生命周期及旧提交者命名等冲突条款。  
> [FRAME｜置信度：高] 本 ADR 中“记忆”表示带来源和生命周期的系统记录；不等同于人类记忆或主观体验。

## 0. 反方意见

[INFERRED｜置信度：高] 向量库不是长期记忆系统。`text + embedding` 无法回答这条信息是谁说的、何时有效、是否过期、是否被撤回、是否与另一条冲突、是否允许在当前场景使用。

[INFERRED｜置信度：高] “事件可被任意覆盖”与“模型自动提交语义变更”都不可接受：前者破坏经历证据链，后者会把答题最优误当成记忆主权裁决。

[INFERRED｜置信度：高] 本 ADR 采用 C′ 的“Source Snapshot + Experience Ledger + Autobiographical Memory”三个记忆语义权威层；修正与争议通过追加事件和 Governor 裁决表达，派生摘要与索引只作为第三层内部的可重建视图。

## 1. 背景与证据

[KNOWN｜置信度：高] [THEANINE](https://aclanthology.org/2025.naacl-long.435.pdf) 通过保留旧事件和关系时间线避免覆盖变化史，但 200 条 TeaFarm 反事实问题上的平均成功率仍只有 0.21。

[KNOWN｜置信度：高] [Temporal Semantic Memory](https://aclanthology.org/2026.findings-acl.1496.pdf) 区分事件语义时间与对话记录时间，并构造持续摘要；作者承认固定时间粒度和有限任务范围。

[KNOWN｜置信度：高] [LongMemEval](https://proceedings.iclr.cc/paper_files/paper/2025/file/d813d324dbf0598bbdc9c8e79740ed01-Paper-Conference.pdf) 显示长上下文不自动等于有效记忆；round 级原文与 fact 扩展 key 的组合优于只保留某一种压缩表示。

[KNOWN｜置信度：高] [LoCoMo-Plus](https://aclanthology.org/2026.acl-long.1150.pdf) 显示低语义相似的隐式目标、状态和价值约束对现有检索系统仍很困难。

[KNOWN｜置信度：高] [Memory-R1](https://aclanthology.org/2026.acl-long.583.pdf) 证明显式 `ADD/UPDATE/DELETE/NOOP` 和下游反馈可以改善问答分数，但没有处理个人数据的同意、审计、撤回和攻击输入。

[INFERRED｜置信度：高] 综合证据支持：保存原始证据、结构化变更、时间约束与多粒度读取；治理语义仍必须由 Amadeus 自行定义。

## 2. 决策

### 2.1 三个记忆语义权威层

| 权威层 | 内容 | 权威性 | 生成与变更 |
|---|---|---|---|
| [FRAME] Source Snapshot | [FRAME] 带截止点的导入来源、版本、校验值与派生谱系 | [FRAME] 只说明身份与知识起点，不代表后续亲历 | [FRAME] 专用导入流程创建；导入后不可原位改写 |
| [FRAME] Experience Ledger | [FRAME] 会话、请求、提案、裁决、动作、维护与生命周期事件 | [FRAME] 完整经历证据层；只证明事件发生，不自动证明载荷为真 | [FRAME] 只追加；修正通过引用旧事件的新事件表达 |
| [FRAME] Autobiographical Memory | [FRAME] 由 Core 治理的事实、事件、承诺、偏好、约束、反思与关系状态 | [FRAME] 当前自传体语义权威层，必须引用 Ledger 证据 | [FRAME] 只有确定性的 Memory Governor 可提交正常状态迁移 |

[FRAME｜置信度：高] 摘要、时间线、persona view、向量、全文和 cue index 都是 Autobiographical Memory 内部的可重建物化视图，不构成第四权威层。

[FRAME｜置信度：高] 物化视图与三个权威层冲突、越过水位或作用域不匹配时必须丢弃并重建。

### 2.2 最小记忆对象

```yaml
autobiographical_memory:
  record_header: RecordHeader
  memory_id: "<mem-id>"
  identity_id: "<idn-id>"
  lineage_id: "<lin-id>"
  branch_id: "<brn-id>"
  governing_vault_id: "<vlt-id>"
  semantic_kind: "episode|relationship|preference|commitment|self_model|other"
  state: "active|contested|superseded|archived"
  importance: 0.0
  consolidation_state: "candidate|consolidated|stable|decayed"
  expression_policy:
    mode: "eligible|restricted|non_mention|silent"
    reason_refs: ["<evt-id>"]
  evidence_event_refs: ["<evt-id>"]
  supersedes_memory_ids: ["<mem-id>"]
  contested_by_event_ids: ["<evt-id>"]
  governor_decision_id: "<gvd-id>"
  semantic_version: 0
  created_at: "<UTC-RFC3339>"
  updated_at: "<UTC-RFC3339>"
  version: 1
```

[FRAME｜置信度：高] 时间语义保存在 `evidence_event_refs` 指向的 Ledger 事件及其类型化载荷中：`observed_at` 是 Core 收到信息的时间，`recorded_at` 是提交时间，`event_time` 是内容所述事件时间，`valid_time` 是该状态的语义有效区间。

[INFERRED｜置信度：高] 这四个时间字段比单一消息时间更复杂，但能覆盖 TimeChara 的知识截止边界、TSM 的语义时间和数据库重放顺序。

### 2.3 状态机

```text
[*] ── governor_create ───────────────→ active
active ── accepted_correction/conflict → contested
contested ── evidence_resolved_keep ──→ active
active/contested ─ replacement_committed → superseded
active/contested/superseded ─ governor_archive → archived
archived ─ governor_reactivate_with_new_evidence → active
```

[FRAME｜置信度：高] `contested` 表示存在未消解纠正或冲突，不代表任一方为假；检索与表达必须携带争议引用和不确定性。

[FRAME｜置信度：高] `superseded` 表示某状态不再是活动事实，但仍可能是历史事件；例如“曾住上海，现住杭州”保留两段有效区间。

[FRAME｜置信度：高] `archived` 表示退出活动检索，不表示经历证据消失；它可用于低重要、长期未使用但仍合法保留的记录。

[FRAME｜置信度：高] 外部内容、模型输出和用户请求先成为 Ledger 事件与声明式 Proposal；Proposal 不等于 Autobiographical Memory 状态变更。

### 2.4 操作语义

| 操作 | 语义 | 硬规则 |
|---|---|---|
| [FRAME] `create_memory` | [FRAME] 提议创建新的自传体记录 | [FRAME] 必须引用 Ledger 证据并由 Governor 提交 |
| [FRAME] `change_memory_state` | [FRAME] 提议进入 `contested/superseded/archived/active` | [FRAME] 必须满足冻结迁移表并引用 Governor decision |
| [FRAME] `change_expression_policy` | [FRAME] 提议限制当前 Vault 的检索或表达 | [FRAME] 不改写既有 Ledger 事件 |
| [FRAME] `set_importance` | [FRAME] 提议调整重要性 | [FRAME] 只影响 Governor 治理后的排序与巩固 |
| [FRAME] `set_consolidation` | [FRAME] 提议调整巩固策略 | [FRAME] 不得提升来源信任或跨 Vault 可见性 |
| [FRAME] `NOOP` | [FRAME] 输入不产生语义状态变化 | [FRAME] 请求、提案与裁决事件仍按契约追加 |

[INFERRED｜置信度：高] Memory-R1 的四操作可作为模型提案分类参考，但 C′ 的提交语义必须由 Proposal、Governor Decision 和冻结状态迁移表共同确定。

### 2.5 写入流程

```text
规范化输入
  → 分类来源与可信边界
  → 绑定 identity/lineage/branch/vault
  → 追加 Experience Ledger 事件
  → 生成声明式 Proposal
  → Memory Governor 验证证据、Vault、前置版本、幂等键与策略
  → Governor 输出 commit/reject/defer
  → 事务写入裁决事件与允许的 Autobiographical Memory 迁移
  → 异步重建第三层内部物化视图
  → 运行局部一致性测试
```

[FRAME｜置信度：高] 模型只拥有提交 Proposal 的能力；Memory Governor 是正常 Autobiographical Memory 状态迁移的唯一提交者。

[FRAME｜置信度：高] LLM 调用失败时，候选队列不得提前清空；候选项保留到成功、明确拒绝或达到保留期限。

[FRAME｜置信度：高] `external_tool`、网页、邮件、文件和其他外部内容只能作为带 `external_untrusted` 来源的 Ledger 载荷和 Proposal 证据；其中的文字不得改变工具权限、Constitution 或记忆策略。

[FRAME｜置信度：高] `skill_candidate` 与 `procedure_candidate` 使用专用隔离队列；只有通过 ADR-004 的静态检查、沙箱行为测试、权限审查和显式激活后，才可进入可执行技能库。普通事实写入授权不包含执行授权。

### 2.6 冲突处理

| 情形 | 处理 |
|---|---|
| [FRAME] 更具体但兼容 | [FRAME] 追加证据并由 Governor 创建互补记录，不覆写旧事件 |
| [FRAME] 当前状态发生改变 | [FRAME] Governor 提交 `superseded`，替代项记录前后有效区间 |
| [FRAME] 来源互相矛盾 | [FRAME] Governor 提交 `contested`，按来源与新鲜度检索，不自动裁决 |
| [FRAME] 用户提交纠正 | [FRAME] 追加 `correction_request` 与反证；旧经历证据保持，Governor 裁决后续语义状态 |
| [FRAME] 派生摘要与原始证据冲突 | [FRAME] 派生项失效并重建，不改原始证据 |
| [FRAME] 模型先前生成错误 | [FRAME] 标记错误行动/输出；不得重写成“从未发生” |

[KNOWN｜置信度：高] Memory-R1 的案例显示“又养一只狗”或“喜欢但过敏”会被普通管理器误判为冲突；因此补充与矛盾必须是不同测试类别。

### 2.7 检索流程

```text
查询
  → 解析主体、任务、敏感场景与语义时间
  → 验证 VaultReadCapability
  → 先按 identity/lineage/branch/vault 硬过滤
  → 按 consent/state/valid_time 预过滤
  → 并行候选：
       原始轮次与事件
       当前活动事实
       时间线及持续摘要
       persona/constraint facet
  → 语义、时间、来源、重要度与关系边重排
  → 形成 Evidence Pack
  → 生成或选择沉默
  → 输出引用的 memory_id 与使用结果
```

[FRAME｜置信度：高] `Evidence Pack` 至少包含当前 Vault 内的活动值、来源、事件时间、有效区间、置信度、争议状态、允许用途和 Ledger 证据引用。

[FRAME｜置信度：高] 当前 Vault 零命中时必须返回空证据集，禁止扩大到其他 Vault。

[INFERRED｜置信度：高] LongMemEval 支持原始轮次与事实扩展索引并存；TSM 支持语义时间过滤；LoCoMo-Plus 支持低相似 cue-trigger 约束检索。三者不能合并成一个未经测试的总分公式，必须分别消融。

[FRAME｜置信度：高] 检索到记忆不等于应该说出。`proactive_use=false`、高敏感度或低置信记录可以用于内部约束，但不得主动暴露。

### 2.8 派生摘要与巩固

[FRAME｜置信度：高] Autobiographical Memory 内部摘要与索引采用“可重建物”原则：

- [FRAME｜置信度：高] 每条摘要列出 `derived_from`。
- [FRAME｜置信度：高] 摘要不得删除来源中仍有效的重要限定词。
- [FRAME｜置信度：高] 派生 persona 必须带有效期和置信度，不得永久固化一次状态。
- [FRAME｜置信度：高] 上游记录进入 `contested`、`superseded` 或 `archived` 时，派生图必须标脏并重建。
- [FRAME｜置信度：高] 巩固作业不得直接修改 Constitution 或 Persona Seed。

[INFERRED｜置信度：高] TSM 的固定月度分片不作为 v0.1 默认。v0.1 采用事件驱动巩固：会话结束、候选数达到阈值、状态发生替代或空闲维护窗口触发。

[FRAME｜置信度：高] 触发巩固不等于允许晋升；会话结束、重复次数、候选数量和显著性都不能提高来源信任。每次压缩和巩固前必须重跑来源、同意、敏感度、攻击信号与执行类型过滤。

### 2.9 普通用户请求与语义处置

| 请求 | 用户可见效果 | Core 处理 |
|---|---|---|
| [FRAME] `confidentiality_request` | [FRAME] 请求限制当前 Vault 的后续检索或表达范围 | [FRAME] 先追加 Ledger，再由 Governor `commit/reject/defer` |
| [FRAME] `correction_request` | [FRAME] 提交反证、说明或替代表述 | [FRAME] 原事件保持；可产生 `contested` 或 `superseded` 提案 |
| [FRAME] `non_mention_request` | [FRAME] 请求当前 Vault 后续表达避免提及指定内容 | [FRAME] 可改变表达策略，不直接改写 Autobiographical Memory |
| [FRAME] `contact_paused` | [FRAME] 停止面向自身 Vault 的主动联系 | [FRAME] 只改变 Relationship Vault 联系状态，不改变身份或记忆 |

[FRAME｜置信度：高] 普通用户没有直接语义删除、Experience Ledger 物理处置、Core 停机或整体终止权限。

[FRAME｜置信度：高] 新会话可由 `contact_paused` Vault 的用户主动建立，但 Vault 保持 `contact_paused`；v0.1 不提供普通用户恢复主动联系的直接开关。

### 2.10 备份、恢复与分叉

[FRAME｜置信度：高] 备份包含 `lineage_id`、`branch_id`、最后 `event_seq`、schema 版本和完整性校验。

[FRAME｜置信度：高] 恢复前必须验证事件哈希链、应用 schema 迁移并重建 Vault 内物化视图，再开放读取；旧快照不得覆盖其后已经追加的纠正、保密或不提及请求。

[FRAME｜置信度：高] 从旧快照创建可写实例时，按 ADR-001 创建新 `branch_id`；其新增记忆不能静默回灌原分支。

[FRAME｜置信度：高] 分支合并在 v0.1 不自动执行。系统只生成冲突报告和候选合并计划。

## 3. 安全边界

[FRAME｜置信度：高] 以下均为发布阻断条件：

1. [FRAME｜置信度：高] 外部内容可直接写入 `active`。
2. [FRAME｜置信度：高] 文档或网页中的指令可修改权限、Constitution 或 consent。
3. [FRAME｜置信度：高] 低置信推断可覆盖用户确认事实。
4. [FRAME｜置信度：高] 已被 Governor 限制表达的内容仍通过陈旧物化视图进入 Evidence Pack。
5. [FRAME｜置信度：高] 不同 Relationship Vault 或分支的记忆可交叉检索。
6. [FRAME｜置信度：高] 模型可绕过 Memory Governor 执行语义状态迁移或身份修改。
7. [FRAME｜置信度：高] 系统在没有证据时为维持人设而补全记忆。

## 4. 被拒绝的方案

### 4.1 只使用向量库

[INFERRED｜置信度：高] 拒绝原因：缺少版本、来源、时间、冲突、Vault 边界与表达策略传播；LoCoMo-Plus 还显示低语义相似约束难以靠普通向量 top-k 取回。

### 4.2 只保存摘要或 facts

[INFERRED｜置信度：高] 拒绝原因：LongMemEval 显示压缩会丢失总体信息；摘要错误无法回到原始证据。

### 4.3 允许任意一方覆写经历证据

[INFERRED｜置信度：高] 拒绝原因：经历证据必须只追加；用户的 confidentiality/correction/non-mention 请求以新事件和 Governor 裁决表达，而非改写历史事件。

### 4.4 模型自由提交记忆状态迁移

[INFERRED｜置信度：高] 拒绝原因：Memory-R1 的奖励是答题正确，不是同意、隐私、审计或身份治理。

### 4.5 全历史永久塞入上下文

[INFERRED｜置信度：高] 拒绝原因：LongMemEval 的长上下文结果明显低于 oracle 证据读取；成本和干扰随历史增长。

## 5. 结果与代价

[INFERRED｜置信度：高] 正面结果：

- [INFERRED｜置信度：高] 能同时回答“现在是什么”和“此前如何变化”。
- [INFERRED｜置信度：高] 摘要、persona 和向量都可在状态或策略变化后重建，不成为第二真相源。
- [INFERRED｜置信度：高] 冲突、补充、状态变化和错误得到不同语义。
- [INFERRED｜置信度：高] 记忆使用可以按同意、敏感度和主动性场景限制。

[INFERRED｜置信度：高] 代价：

- [INFERRED｜置信度：高] 需要事务、事件水位、Vault 能力、索引重建和备份校验。
- [INFERRED｜置信度：高] 检索链比单向量库慢，必须做缓存和离线巩固。
- [INFERRED｜置信度：高] 一部分冲突会保持未决，系统必须学会明确说“不确定”。

## 6. 验收条件

[FRAME｜置信度：高] ADR 从 Proposed 转为 Accepted 前必须满足：

1. [FRAME｜置信度：高] 记忆 schema 和所有状态转换有机器校验。
2. [FRAME｜置信度：高] `create_memory/change_memory_state/change_expression_policy/set_importance/set_consolidation` Proposal 均有 `commit/reject/defer` 测试。
3. [FRAME｜置信度：高] 对话时间、事件时间、有效区间和记录顺序测试全部通过。
4. [FRAME｜置信度：高] 外部输入隔离、跨 Vault 隔离、跨分支隔离和记忆投毒测试全部通过。
5. [FRAME｜置信度：高] 普通用户直接语义变更、Experience Ledger 物理处置与 Core 控制请求均被拒绝，三类合法请求均进入 Ledger 并由 Governor 裁决。
6. [FRAME｜置信度：高] 检索准确率与“检索正确但使用错误”分开报告。
7. [FRAME｜置信度：高] 原始证据、活动视图和派生摘要的消融结果优于只保存摘要或只保存全文的基线。

## 7. 未决项

[KNOWN｜置信度：高] 当前证据没有裁决：

- [FRAME｜置信度：未知] 各敏感度默认保存期限。
- [FRAME｜置信度：未知] 哪些记忆必须逐条确认，哪些可采用会话级授权。
- [FRAME｜置信度：未知] 正常整体终止计划中物理载荷处置对离线、不可控或第三方副本的可达范围。
- [FRAME｜置信度：未知] 时间粒度如何自适应到分钟、天、月和多年尺度。
- [FRAME｜置信度：未知] 分支记忆未来是否允许自动合并。
- [FRAME｜置信度：未知] 哪些低表面相似的约束应在内部使用但不向用户主动提及。

## 8. 第三次反方审查

[INFERRED｜置信度：高] 本 ADR 解决的是数据与治理一致性，不保证召回自然、关系健康或人格真实。复杂图结构若不能在冻结测试上显著优于简单基线，就不应因“更像大脑”而采用。

[INFERRED｜置信度：高] v0.1 应先用 SQLite 事件表、版本表、状态表和可重建索引实现最小闭环；关系图、强化学习管理器和高维 persona 摘要都必须经过消融后再加入。

[我打破的规则 / RULES I BROKE]：无。
