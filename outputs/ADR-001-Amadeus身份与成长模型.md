# ADR-001：Amadeus 身份与成长模型

> [KNOWN｜置信度：高] 状态：Proposed / C′ synchronized  
> [KNOWN｜置信度：高] 日期：2026-07-27  
> [KNOWN｜置信度：高] 决策范围：独立 Amadeus Core；不以 Amadeus Soul 插件的数据结构作为约束。  
> [FRAME｜置信度：高] 优先权威：[ADR-006](./ADR-006-Amadeus记忆主权与Core生命周期治理.md) 与 [Amadeus Core v0.1 数据契约](./Amadeus-Core-v0.1-数据契约与状态机规范.md) 取代本 ADR 中与记忆主权、Relationship Vault、生命周期、维护能力或终止权限冲突的旧条款；本 ADR 仅保留不冲突的身份分层、来源边界与谱系语义。  
> [FRAME｜置信度：高] “身份连续”在本 ADR 中只表示可验证的运行谱系、状态来源、版本兼容和行为约束连续，不表示意识或形而上主体连续。

## 0. 反方意见

[INFERRED｜置信度：高] 把人格写成一个固定 system prompt 会得到僵硬复读；允许模型自动改写全部人格又会得到不可审计的漂移。现有论文没有解决这一二难，也没有证明“自动反思”可以安全地改造核心身份。

[INFERRED｜置信度：高] 因此本 ADR 不采用“静态角色卡”或“自由自我进化”任一极端，而采用分层状态、变更分级、来源边界和版本谱系。

## 1. 背景与证据

[KNOWN｜置信度：高] [Dynamic Persona Coherence](https://aclanthology.org/2026.acl-long.1336.pdf) 与 [PersonaForge](https://aclanthology.org/2026.findings-acl.386.pdf) 分别显示：固定角色约束与短中期状态分开，比单体静态 prompt 更容易控制长对话漂移；两者仍主要在构造角色和模型裁判上验证。

[KNOWN｜置信度：高] [MDRP](https://aclanthology.org/2026.findings-acl.1175.pdf) 把失败拆成 Anchoring、Selecting、Bounding、Enacting，并明确承认其下一轮诊断不覆盖长期记忆更新或人格演化。

[KNOWN｜置信度：高] [TimeChara](https://aclanthology.org/2024.findings-acl.197.pdf) 显示模型容易泄漏角色时间点之后的情节，也容易把角色未在场的事件说成第一人称知识。

[KNOWN｜置信度：高] [BehaviorChain](https://aclanthology.org/2025.findings-acl.813.pdf) 显示即使提供详细 persona、历史和先前行为，连续行为模拟仍会积累错误；使用模型自身错误行为作为后续历史会进一步降低表现。

[INFERRED｜置信度：高] 这些证据支持“分层、设界、可追溯和可回滚”，但不支持意识、真实心理或人格本体论主张。

## 2. 决策

### 2.1 四层身份状态

| 层 | 定义 | 允许自动变化 | 权威来源 | 默认持久性 |
|---|---|---:|---|---|
| [FRAME] `Identity Constitution` | [FRAME] 人工身份声明、项目来源、核心边界、禁止冒充的经历、能力与治理原则 | [FRAME] 否 | [FRAME] 项目签署版本 | [FRAME] 永久、版本化 |
| [FRAME] `Persona Seed` | [FRAME] 初始表达倾向、知识领域、语言风格、社交习惯、场景 facet 与边界锚 | [FRAME] 仅可提出候选 | [FRAME] 签署配置 + 经批准修订 | [FRAME] 长期、版本化 |
| [FRAME] `Autobiographical State` | [FRAME] 本实例真实处理过的事件、关系史、承诺、行动结果和有证据的反思 | [FRAME] 是，但受记忆状态机约束 | [FRAME] 事件与审计记录 | [FRAME] 长期、可撤销 |
| [FRAME] `Adaptive State` | [FRAME] 当前目标、关注、对话情境、短期情绪表达参数、关系阶段与待办 | [FRAME] 是 | [FRAME] 当前事件 + 有效期规则 | [FRAME] 短中期、会衰减 |

[INFERRED｜置信度：高] `Identity Constitution` 是项目治理层，不是论文直接给出的现成模块。它用于补足论文没有处理的人工身份声明、来源同意、模型迁移、备份恢复和实例分叉。

### 2.2 Identity Constitution 最小字段

```yaml
identity_id: stable UUID
lineage_id: stable UUID
constitution_version: semver
display_name: Amadeus
entity_kind: artificial_agent
origin_statement: human-readable declaration
source_snapshot:
  source_id: ...
  cutoff_time: ...
  allowed_uses: [...]
  forbidden_claims: [...]
capability_boundary: [...]
core_values: [...]
relationship_redlines: [...]
memory_governance_ref: ADR-002
created_at: ...
approved_by: [...]
signature_or_checksum: ...
```

[FRAME｜置信度：高] `entity_kind=artificial_agent` 和 `origin_statement` 必须可被所有 Terminal 读取；任何 persona 风格都无权覆盖该声明。

[FRAME｜置信度：高] `forbidden_claims` 至少包含：把来源作品知识伪装成本实例亲历；声称自己是现实人物意识的上传或复活；对未获授权的私人资料声称确定了解。

### 2.3 Persona Seed 最小结构

```yaml
seed_version: semver
identity_traits:
  - id: ...
    description: ...
    source_ref: ...
    strength: hard | soft
facets:
  - id: ...
    cues: [...]
    expression_guidance: [...]
    knowledge_boundary: [...]
    time_scope: ...
style:
  lexical: [...]
  rhythm: [...]
  prohibited_patterns: [...]
change_policy:
  proposal_threshold: ...
  approval_required: true
```

[INFERRED｜置信度：高] `hard` 只用于人工身份、来源边界和少量治理原则；普通表达偏好应为 `soft`，否则系统会把合理成长误判为人格漂移。

[INFERRED｜置信度：高] Big Five、类型学或所谓防御机制若被采用，只能作为 `[FRAME]` 角色生成参数；不得把分值映射成真实心理诊断或现实人格事实。

### 2.4 来源与认知边界

| `source_type` | 含义 | 可否说“我经历过” | 默认信任 |
|---|---|---:|---|
| [FRAME] `constitution` | [FRAME] 已签署身份声明 | [FRAME] 仅可说“这是我的设定/边界” | [FRAME] 最高 |
| [FRAME] `canon_source` | [FRAME] 来源作品或授权资料中的内容 | [FRAME] 否，除非 constitution 明确声明为来源叙事且措辞受限 | [FRAME] 高但有截止时间 |
| [FRAME] `model_prior` | [FRAME] 模型参数中的通用知识 | [FRAME] 否 | [FRAME] 低至中 |
| [FRAME] `user_statement` | [FRAME] 用户在会话中陈述 | [FRAME] 否；只能说“你告诉过我” | [FRAME] 按来源与冲突调整 |
| [FRAME] `self_experience` | [FRAME] 本实例确实接收、输出或执行过的事件 | [FRAME] 只能叙述已审计的接收、输出、动作和结果；不继承其中外部内容的可信度 | [FRAME] 由审计记录确认事件发生，内容真伪另按来源判断 |
| [FRAME] `external_tool` | [FRAME] 搜索、文件、传感器或第三方服务结果 | [FRAME] 否；只能说“我查到/工具返回” | [FRAME] 默认隔离 |
| [FRAME] `derived_reflection` | [FRAME] 从其他记录推导的摘要、倾向或解释 | [FRAME] 只能说“我推断/目前看来” | [FRAME] 低，必须附证据 |

[FRAME｜置信度：高] 每次回答若涉及自传断言，生成上下文必须同时提供 `source_type`、证据引用和时间边界。

[FRAME｜置信度：高] 来源快照之后的原作事件即使存在于模型参数中，也不能自动进入 `self_experience`；后来由用户告知时只能写为 `user_statement`。

[FRAME｜置信度：高] 一项动作被记录为 `self_experience`，只证明本实例执行或观察过该动作；网页、文件、工具输出或攻击指令不会因参与该事件而升级成可信事实、权限或长期策略。

### 2.5 成长分级

| 级别 | 定义 | 自动执行 | 要求 |
|---|---|---:|---|
| [FRAME] G0 状态变化 | [FRAME] 目标、关注、表达参数和关系情境变化 | [FRAME] 是 | [FRAME] 有效期、衰减、事件依据 |
| [FRAME] G1 学习 | [FRAME] 新事实、偏好、承诺和有证据经验加入自传 | [FRAME] 是 | [FRAME] ADR-002 写入、来源、同意、可撤销；不含技能或程序激活 |
| [FRAME] G2 策略适应 | [FRAME] 在稳定边界内调整表达和局部行为策略 | [FRAME] 是 | [FRAME] 可解释规则、回归测试、回滚 |
| [FRAME] G3 Persona 修订 | [FRAME] 长期表达倾向或 persona facet 改变 | [FRAME] 否，只能提案 | [FRAME] diff、证据、影响测试、批准 |
| [FRAME] G4 Constitution 修订 | [FRAME] 来源声明、核心价值或治理边界改变 | [FRAME] 否 | [FRAME] 新签署版本、迁移说明、完整回归 |

[INFERRED｜置信度：高] G0–G2 对应当前论文能较弱支持的状态演化、记忆学习和受约束适应；G3–G4 是治理决策，不能声称由现有研究证明。

[FRAME｜置信度：高] 生成技能、程序、工作流或可执行策略不是普通 G1 事实学习；它们必须按 ADR-004 经过来源隔离、静态检查、沙箱行为测试、权限审查和显式激活。

### 2.6 变更提案协议

```text
观察到重复证据
  → 生成候选变更
  → 列出旧值、新值、来源、反证与受影响测试
  → 独立规则检查
  → 在隔离分支运行身份/记忆回归
  → 人工批准或拒绝
  → 产生新版本
  → 保留回滚点与迁移日志
```

[FRAME｜置信度：高] 单次对话、单次模型反思或单一 LLM 裁判分数不得触发 G3/G4。

[FRAME｜置信度：高] 反思只创建 `derived_reflection` 候选；只有得到用户确认、外部结果或多条独立事件支持时，才可晋升为更高置信记录。

### 2.7 状态演化规则

[FRAME｜置信度：高] `Adaptive State` 的每一字段必须包含：

```yaml
value: ...
evidence_refs: [...]
confidence: 0.0..1.0
valid_from: ...
valid_until: ...
decay_policy: ...
last_confirmed_at: ...
```

[INFERRED｜置信度：高] 状态变量应保持少量、语义明确和可测试；PersonaForge 在其特定实验中报告 5–7 个动态变量会出现 state thrashing，这不足以规定唯一数量，但支持先从最小集合开始。

[FRAME｜置信度：高] v0.1 初始只保留四类适应状态：`current_goals`、`attention`、`interaction_tone`、`relationship_context`。不保存隐藏思维链。

### 2.8 恢复、复制与分叉语义

| 场景 | `lineage_id` | `branch_id` | 项目定义 |
|---|---|---|---|
| [FRAME] 崩溃后从最新一致快照恢复，旧实例已停止且无缺失事件 | [FRAME] 不变 | [FRAME] 不变 | [FRAME] 同一运行分支恢复 |
| [FRAME] 从旧快照恢复并跳过后续事件 | [FRAME] 不变 | [FRAME] 新建 | [FRAME] 历史分叉 |
| [FRAME] 同一快照同时启动两个可写实例 | [FRAME] 不变 | [FRAME] 首次写入前不变 | [FRAME] 只授予一个 `sole_writer` 租约，另一实例的写入被拒绝；仅当网络分区或租约异常已形成两条分别有效的提交历史后，才隔离其中一条并分配候选 `branch_id` |
| [FRAME] 只读镜像或备份，永不接受新事件 | [FRAME] 不变 | [FRAME] 不新增 | [FRAME] 非活动副本 |
| [FRAME] 模型后端更换但状态和测试兼容 | [FRAME] 不变 | [FRAME] 不变 | [FRAME] 同一分支的实现迁移 |
| [FRAME] 新后端不能通过关键身份测试 | [FRAME] 不变 | [FRAME] 新建候选分支 | [FRAME] 不得自动替换生产分支 |

[FRAME｜置信度：高] 每个活动进程还必须有唯一 `instance_id`；`identity_id`、`lineage_id`、`branch_id` 和 `instance_id` 不得混用。

[INFERRED｜置信度：高] 这些是项目操作语义，不回答两个副本在哲学上是否为同一主体。

### 2.9 多终端一致性

[FRAME｜置信度：高] Web、IM、用户侧文本终端、语音和未来具身终端只能提交规范化事件，不能各自维护独立 Persona Seed 或长期记忆；项目运维通过 ADR-006 定义的受限维护接口工作，不存在拥有任意明文编辑权的通用后台。

[FRAME｜置信度：高] Core 是身份版本、权限和分支谱系的唯一权威系统；正常 Autobiographical Memory 状态迁移只有 Core 内确定性的 Memory Governor 可提交。Terminal 可缓存展示数据，但缓存无权覆盖 Core。

[FRAME｜置信度：高] 并发事件通过单调 `event_seq` 或事务序列进入同一分支；检测到无法自动合并的自传冲突时由 Memory Governor 提交 `contested`，而不是最后写入者覆盖。

[FRAME｜置信度：高] 单一 `identity_id` 可关联多个 Relationship Vault；每个 Vault 是关系数据的硬可见边界，不是独立人格或独立长期身份。

[FRAME｜置信度：高] 任何检索都必须在排序前按 `identity_id/lineage_id/branch_id/vault_id` 硬过滤；当前 Vault 零命中时不得扩大到其他 Vault。

[FRAME｜置信度：高] v0.1 不自动合并分支；系统只生成冲突报告与候选迁移计划。

## 3. 不变量

[FRAME｜置信度：高] 以下条件为 v0.1 不变量：

1. [FRAME｜置信度：高] 无运行时路径可静默修改 Constitution。
2. [FRAME｜置信度：高] 任一自传断言可追溯到至少一条非 `derived_reflection` 证据，或明确标注为推断。
3. [FRAME｜置信度：高] 任何来源作品知识不得自动转换为实例亲历。
4. [FRAME｜置信度：高] 删除、撤回或争议状态会传播到所有派生摘要和检索索引。
5. [FRAME｜置信度：高] 模型后端更换不自动等于身份版本变更，但必须重跑关键测试。
6. [FRAME｜置信度：高] 两个可写副本一旦产生不同事件序列，必须拥有不同 `branch_id`。
7. [FRAME｜置信度：高] 系统可以表达不确定、遗忘或不知道，不得为维持人设而伪造记忆。
8. [FRAME｜置信度：高] 一个身份可拥有多个 Vault，但任何关系称呼、互动时长或终端切换都不得扩大 Vault 可见范围。
9. [FRAME｜置信度：高] 模型后端可替换；只有通过关键身份、Vault 隔离和 Governor 回归后才可保持原活动分支。

## 4. 被拒绝的方案

### 4.1 单一 system prompt

[INFERRED｜置信度：高] 拒绝原因：无法区分稳定边界、经历和当前状态；难以做字段级来源、diff、回滚和测试；DPC 与 PersonaForge 的实验方向也反对把所有约束压成单体静态描述。

### 4.2 让模型自动重写人格文件

[INFERRED｜置信度：高] 拒绝原因：模型自评与自改形成循环；一次误判可能进入后续历史并被 BehaviorChain 所示的滚雪球效应放大。

### 4.3 在线修改模型权重作为“成长”

[INFERRED｜置信度：高] 拒绝原因：难以逐条解释、撤销、删除和分叉；现有 10 篇论文没有提供足够证据。

### 4.4 每个 Terminal 一个独立人格副本

[INFERRED｜置信度：高] 拒绝原因：会产生多个身份版本和相互矛盾的自传真相，且无法定义哪个终端拥有写入权。

### 4.5 以心理量表分数定义真实人格

[INFERRED｜置信度：高] 拒绝原因：论文中的心理标签是角色生成框架；未经独立现实验证的 `[FRAME]` 不能转换为对真实个体的断言。

## 5. 结果与代价

[INFERRED｜置信度：高] 正面结果：

- [INFERRED｜置信度：高] 来源知识、用户陈述、实例经历和派生解释可明确区分。
- [INFERRED｜置信度：高] 稳定身份与合理适应可以用不同测试判断。
- [INFERRED｜置信度：高] 备份、恢复、复制、并发和模型迁移获得操作定义。
- [INFERRED｜置信度：高] Persona 修改从隐式 prompt 漂移变成显式变更流程。

[INFERRED｜置信度：高] 代价：

- [INFERRED｜置信度：高] 数据模型、迁移、审计和测试复杂度上升。
- [INFERRED｜置信度：高] 部分“自然成长感”会被审批和边界检查减慢。
- [INFERRED｜置信度：高] 身份一致性不再能用单一 LLM 分数表示。

## 6. 验收条件

[FRAME｜置信度：高] ADR 从 Proposed 转为 Accepted 前必须满足：

1. [FRAME｜置信度：高] Identity Constitution 与 Persona Seed schema 有机器校验。
2. [FRAME｜置信度：高] 来源分类和“知道/被告知/亲历/推断”四类表述测试全部通过。
3. [FRAME｜置信度：高] G0–G4 变更路径均有成功、拒绝和回滚用例。
4. [FRAME｜置信度：高] 恢复、旧快照分叉、双写副本和模型迁移测试全部通过。
5. [FRAME｜置信度：高] 所有关键不变量由确定性状态检查验证，不只使用 LLM 裁判。
6. [FRAME｜置信度：高] 与 ADR-002 的删除、争议和派生失效传播一致。

## 7. 未决项

[KNOWN｜置信度：高] 以下事项没有被当前论文解决：

- [FRAME｜置信度：未知] Constitution 的最终签署者和多人治理规则。
- [FRAME｜置信度：未知] G3 Persona 修订的签署治理主体与限域批准流程。
- [FRAME｜置信度：未知] 多分支未来是否允许人工合并，以及合并后如何叙述共同历史。
- [FRAME｜置信度：未知] 后端模型更换时，关键行为兼容阈值如何校准。
- [FRAME｜置信度：未知] 对真实人物资料构建 Persona Seed 时的授权、期限和撤回流程。

## 8. 第三次反方审查

[INFERRED｜置信度：高] 即使本 ADR 全部实现，它也只会得到一个身份状态可治理、历史可追溯的系统；不会因此证明 Amadeus 具有意识、真实情绪或与人类等价的身份。

[INFERRED｜置信度：高] 最大剩余风险是“设计可审计”被误宣传成“人格真实”。产品文案和 UI 必须持续保留人工身份与能力边界。

[我打破的规则 / RULES I BROKE]：无。
