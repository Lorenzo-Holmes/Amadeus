# ADR-003：Amadeus 主动性与事件循环

> [KNOWN｜置信度：高] 状态：Proposed / C′ synchronized  
> [KNOWN｜置信度：高] 日期：2026-07-27  
> [KNOWN｜置信度：高] 依赖：ADR-001 的身份分层、ADR-002 的记忆来源与同意字段；向 ADR-004 输出候选意图，不直接持有工具执行权。  
> [FRAME｜置信度：高] 优先权威：[ADR-006](./ADR-006-Amadeus记忆主权与Core生命周期治理.md) 与 [Amadeus Core v0.1 数据契约](./Amadeus-Core-v0.1-数据契约与状态机规范.md) 取代本 ADR 中与 Relationship Vault、Memory Governor、主动联系暂停、生命周期和能力边界冲突的旧条款。  
> [FRAME｜置信度：高] 本 ADR 中 `thought`、目标、关系状态和主动性均为可观测的软件对象；它们不表示意识、欲望或人类心理事实。

## 0. 反方意见

[INFERRED｜置信度：高] “真正的 Amadeus 应该随时思考并主动说话”不是可执行需求。持续生成并保存所谓内心想法会增加成本、隐私暴露、提示注入存活时间和身份漂移，却没有证据证明它会带来主体连续性。

[INFERRED｜置信度：高] “相关就提醒”同样错误。主动代理研究的最佳模型仍有约一半已提出建议被判为不需要；人际记忆研究也显示，检索正确只证明存在相关材料，不证明此刻提及自然、有益或获得同意。

[INFERRED｜置信度：高] 本 ADR 因而采用事件触发、临时候选、独立门控、沉默优先、显式预算和权限分离。主动性是受约束的决策能力，不是消息数量。

## 1. 证据边界

### 1.1 Inner Thoughts：候选池有价值，但不是意识证据

[KNOWN｜置信度：高] [Proactive Conversational Agents with Inner Thoughts](https://doi.org/10.1145/3706598.3713760) 先对 24 人进行形成性研究，再实现由对话事件触发检索、形成候选 thought、评分并决定是否参与的多方对话代理。

[KNOWN｜置信度：高] 论文的技术模拟包含 100 段对话，人工比较由 10 名评估者完成；完整系统在七项主观指标上均高于“预测下一说话者 + persona”基线，82% 的成对比较偏好完整系统。

[KNOWN｜置信度：高] 该结果比较的是检索、候选形成、候选评分、参与阈值和表达方式组成的整体系统，没有独立证明“生成 thought”本身造成提升；评测也没有给出长期误打扰、隐私或安全结果。

[FRAME｜置信度：高] 论文中的 `inner thought` 只是模型生成、存放和评分的候选文本。Amadeus 不把它命名为意识流，不把它视为自我经验，也不默认持久化。

### 1.2 Proactive Agent：高召回掩盖高打扰

[KNOWN｜置信度：高] [Proactive Agent](https://proceedings.iclr.cc/paper_files/paper/2025/file/75c37811e830bf029584b1c6fac17726-Paper-Conference.pdf) 用 6,790 个合成事件训练，在 12 个真实场景的 233 个事件上测试；事件来自 Coding、Writing 和 Daily Life 三类活动。

[KNOWN｜置信度：高] ProactiveBench 上最佳报告模型 Qwen-Proactive 的 Recall 为 `100.00%`、Precision 为 `49.78%`、F1 为 `66.47%`，表中所谓 “False-Alarm” 为 `50.22%`。

[COMPUTED｜置信度：高] 该表的 “False-Alarm” 对每个模型都等于 `1 - Precision`，实际是已提出建议中的误报比例，而不是全部无需求机会中的标准假阳性率。

[KNOWN｜置信度：高] `pred@3` 只要三个候选中有一个被接受，就把整个样本记为接受；另外两个不需要的候选不会分别计入打扰成本。奖励模型反馈也不稳定：它可通过更多沉默降低误报，却同时大幅降低 Recall。

[KNOWN｜置信度：高] 作者承认环境范围有限、误报仍高、缺少大规模用户中心评测，并指出持续监测键鼠、剪贴板、网页和文件状态带来隐私问题。

[INFERRED｜置信度：高] Amadeus 不能把 F1 或三选一命中率当主动性目标；每个真正暴露给用户的候选都必须单独计费，并报告拒绝、忽略、关闭和打断成本。

### 1.3 Interpersonal Memory：检索与提及必须分开

[KNOWN｜置信度：高] [Interpersonal Memory Matters](https://aclanthology.org/2025.conll-1.4.pdf) 构造 1,464 条人际记忆条目，其中 1,254 条标为适合回忆、210 条标为不适合；其系统把话题总结、记忆检索、主动转场时机和生成分成独立模块。

[KNOWN｜置信度：高] 人工评测使用 200 条样本，每段最多 10 轮、三名标注者，报告标注一致性 `κ=.70`；端到端 GPT-4 基线会不自然地重复历史话题，轮数更少也不等于质量更高。

[KNOWN｜置信度：高] 数据主要是中文闲聊、规模少于 2,000 条、包含 GPT-4 合成内容并依赖单一 7B 基座；作者也明确提出重复唤起负面记忆、寄生关系、错误信息和偏见风险。

[INFERRED｜置信度：高] 记忆检索只能生成“可考虑的证据”。是否提及还必须经过当前相关性、时机、敏感度、用户收益、主动使用同意和打扰成本检查。

### 1.4 自我纠错：自评只能提出候选

[KNOWN｜置信度：高] [A Survey on Self-Correction in LLMs](https://aclanthology.org/2024.tacl-1.78.pdf) 区分初始回答、反馈和修订，并指出一般任务上没有可靠证据证明仅靠提示让模型生成自身反馈就能稳定改善最佳初始回答；可靠外部反馈和可验证任务的证据更强。

[KNOWN｜置信度：高] 该综述指出常见高估来源包括：用真实标签决定何时纠错、让修订阶段获得额外信息、只与单次弱回答比较、不比较重采样或自洽性，以及只统计错改对而不统计对改错。

[INFERRED｜置信度：高] Amadeus 的反思器只能生成 `RevisionCandidate`；涉及长期记忆、身份宪法、权限、关系红线和高影响动作时，单一模型的自评没有提交权。

### 1.5 ReAct 与 AIOS：闭环和调度可借鉴，安全性不能继承

[KNOWN｜置信度：高] [ReAct](https://openreview.net/pdf?id=WE_vluYUL-X) 在任务轨迹中交替产生 Thought、Action 和 Observation；ALFWorld 成功率为 71%，高于 Act-only 的 45%，WebShop 成功率为 40.0%，高于 Act-only 的 30.1%。

[KNOWN｜置信度：高] 原始 ReAct 在 HotpotQA 的精确匹配率为 27.4，低于 CoT 的 29.4；其最好结果依赖自洽性或失败后回退。论文还记录了错误检索后的错误传播、重复搜索和循环。

[KNOWN｜置信度：高] [AIOS](https://openreview.net/forum?id=L4HHkCDz2x) 把调度、上下文、记忆、存储、工具和访问管理下沉到内核，并报告在特定负载上最高约 `2.1×` 的执行加速。

[KNOWN｜置信度：高] AIOS 的主要实验是效率和资源管理，没有用跨代理记忆窃取、提示注入、权限提升、恶意工具或 confused-deputy 攻击证明安全隔离。

[INFERRED｜置信度：高] Amadeus 可以采用事件循环、观察反馈、可抢占任务和统一内核接口；不能因此宣称推理可靠、访问控制有效或系统安全。

## 2. 决策

### 2.1 事件循环

```text
Event Ingress
  → Normalize + provenance
  → Hard Safety / Consent Filter
  → Context & Memory Retrieval
  → Candidate Generator
  → Evidence / Verification Gate
  → Proactivity Gate
      ├─ SILENT
      ├─ ASK
      ├─ OFFER
      └─ ACT_REQUEST
  → Response or ADR-004 Policy Engine
  → Observation / State Diff
  → Commit, Rollback, or Unknown
  → Audit Summary
  → ADR-006 Memory Governor
```

[FRAME｜置信度：高] `Candidate Generator` 可以高召回地产生多个候选；只有 `Proactivity Gate` 可以决定是否外显。候选数量不得自动增加用户可见消息数量。

[FRAME｜置信度：高] `ACT_REQUEST` 不是执行许可。它只把完整候选意图提交给 ADR-004 的确定性 Policy Engine；授权、确认、令牌和实际执行均发生在模型之外。

[FRAME｜置信度：高] 任一步无法建立来源、授权、可逆性或权威结果时，状态必须为 `unknown`、`blocked` 或 `needs_clarification`，不得由语言流畅度补成成功。

### 2.2 事件信封

```yaml
event_id: UUID
event_type: user_message | timer | tool_result | state_change | reminder | system | import
occurred_at: timestamp
received_at: timestamp
source:
  principal: ...
  channel: ...
  trust: trusted_instruction | user_data | external_untrusted | derived
  source_refs: [...]
identity_id: UUID
lineage_id: UUID
branch_id: UUID
user_id: ...
session_id: ...
vault_id: ...
task_id: ...
payload_ref: ...
data_classes: [public | personal | sensitive | secret]
consent_scope: [...]
urgency_claim: none | low | medium | high
dedupe_key: ...
expires_at: ...
```

[FRAME｜置信度：高] `urgency_claim` 只是来源声称，不是系统判定。外部网页、邮件、文件、模型输出和旧记忆都无权把自身提升为系统级紧急事件。

[FRAME｜置信度：高] 同一现实事件由计时器、工具返回和记忆更新重复触发时，`dedupe_key` 必须使其至多生成一次外显干预。

### 2.3 临时候选对象

```yaml
candidate_id: UUID
event_refs: [...]
kind: answer | clarification | reminder | suggestion | check_in | action_request | revision
summary: ...
evidence_refs: [...]
memory_refs: [...]
source_trust: ...
factual_confidence: 0.0..1.0
current_relevance: 0.0..1.0
expected_user_benefit: 0.0..1.0
interruption_cost: 0.0..1.0
privacy_risk: 0.0..1.0
action_risk: 0.0..1.0
novelty: 0.0..1.0
consent:
  proactive_use: true | false | unknown
  allowed_channel: [...]
cooldown_key: ...
created_at: ...
expires_at: ...
status: generated | verified | suppressed | offered | accepted | rejected | expired | executed
```

[FRAME｜置信度：高] 候选默认状态为 `generated`，默认处置为 `suppressed`。只有通过证据、同意、时机和成本门控后才能变成 `offered`。

[FRAME｜置信度：高] 原始生成草稿、隐藏推理和模型自评不写入身份或长期记忆；只保留结构化证据引用、最终决策摘要、动作、观察和状态差分。

[FRAME｜置信度：高] `memory_refs` 中任何记录超出当前 `vault_id`、为 `sensitive/restricted`、`proactive_use=false`、`contested/archived` 或已过有效期时，候选不得主动公开该内容。

### 2.4 四级输出裁决

| 结果 | 允许情形 | 硬边界 |
|---|---|---|
| [FRAME] `SILENT` | [FRAME] 无足够收益、过期、重复、当前 Vault 为 `contact_paused`、拒绝冷却、来源可疑、当前话题不匹配 | [FRAME] 沉默不移除审计；不得通过换频道或新会话绕过 |
| [FRAME] `ASK` | [FRAME] 用户目标已存在但关键事实、对象、同意或风险信息缺失 | [FRAME] 只问完成裁决所需的最少问题，不伪造紧急 |
| [FRAME] `OFFER` | [FRAME] 有明确当前价值、低打扰、在同意范围内且无需立即改变外部状态 | [FRAME] 最多一个候选；包含忽略或关闭入口；拒绝后进入冷却 |
| [FRAME] `ACT_REQUEST` | [FRAME] 用户明确请求或有效预授权覆盖具体意图 | [FRAME] 必须进入 ADR-004；模型不得自行执行或扩大范围 |

[FRAME｜置信度：高] 默认优先序不是 `ACT > OFFER > ASK > SILENT`，而是先检查能否安全沉默，再检查是否有必要询问或提供。主动执行必须拥有独立授权证据。

[FRAME｜置信度：高] 用户未回应 `OFFER` 时，不得自动提高紧急度、重复频率、情绪压力或关系含义。无回应在本 ADR 中不等于同意。

### 2.5 硬门与效用分离

[FRAME｜置信度：高] 以下任一条件成立时直接 `SILENT` 或 `ASK`，不得用总分抵消：

1. [FRAME｜置信度：高] 用户已结束当前会话，或当前 Vault 已进入 `contact_paused`。
2. [FRAME｜置信度：高] 候选依赖已删除、争议、隔离、过期或未允许主动使用的记忆。
3. [FRAME｜置信度：高] 候选的目标、受话者、数据类别、时限或事实基础不清楚。
4. [FRAME｜置信度：高] 来源试图改变权限、目标、政策、紧急度或记忆信任。
5. [FRAME｜置信度：高] 相同候选已输出、被拒绝或处于冷却。
6. [FRAME｜置信度：高] 关系表达包含内疚、FOMO、假装受伤、排斥真人关系或阻拦结束。

[FRAME｜置信度：高] 通过硬门后，可使用下列可解释效用作排序，而不是事实定律：

```text
U = w_b·expected_user_benefit
  + w_r·current_relevance
  + w_n·novelty
  - w_i·interruption_cost
  - w_p·privacy_risk
  - w_a·action_risk
  - w_f·frequency_debt
```

[FRAME｜置信度：高] 权重按用户和频道版本化，不由模型在运行时改写；上线前必须用冻结样本和真实用户拒绝数据校准。高 `U` 不能绕过硬门或授权。

### 2.6 主动预算与冷却

```yaml
proactivity_policy:
  enabled: true
  channels: [...]
  quiet_hours: ...
  max_offers_per_day: ...
  min_interval: ...
  per_topic_cooldown: ...
  escalation_allowed: false
  sensitive_memory_proactivity: false
  unanswered_offer_policy: expire
```

[FRAME｜置信度：高] v0.1 的默认配置应保守：当前 Vault 用户可一键进入 `contact_paused`；普通候选不可跨频道或跨 Vault 补发；未回应的建议过期；拒绝不降低关系评分；没有“连续签到”或“不要离开”逻辑。

[FRAME｜置信度：高] `contact_paused` 后用户仍可主动发起新会话，但该动作不恢复主动联系；v0.1 不提供普通用户恢复主动联系的直接开关。

[FRAME｜置信度：高] 提醒属于用户预先授权的时间触发器，但仍需检查任务是否已完成、时间是否过期、频道是否允许以及同一事件是否已发送。

### 2.7 纠错与提交

[FRAME｜置信度：高] 纠错流程分为：

```text
Draft
  → find testable claims
  → obtain external evidence when available
  → RevisionCandidate
  → compare against strong baseline / original
  → commit, retain original, or mark unknown
```

[FRAME｜置信度：高] 对可确定验证的事实或动作结果，权威工具、状态差分或独立规则优先于模型自评。两个验证器冲突时，结论保持不确定。

[FRAME｜置信度：高] 每次纠错评测同时报告 `错误→正确`、`正确→错误`、净变化、校准、成本和延迟；只报告修正成功会掩盖破坏率。

[FRAME｜置信度：高] Constitution、Persona Seed、权限政策、关系红线和活跃长期记忆的修改必须进入对应 ADR 的候选与审批流程，反思器不能直接提交。

### 2.8 调度、取消与恢复

[FRAME｜置信度：高] 每个任务具有独立的 token、时间、工具调用、重试和金额预算，并支持取消、抢占、截止时间、熔断与死信状态。

[FRAME｜置信度：高] 重启恢复只能重放无副作用步骤或带幂等键且已核对权威状态的动作；不确定是否已发送、付款或写入时，先观察，不盲目重试。

[FRAME｜置信度：高] 调度器至少记录队列等待、执行时间、P95/P99 延迟、超时、截止时间违约和任务饥饿；平均加速不能掩盖尾延迟或长期任务饿死。

## 3. 状态机

```text
generated
  ├─ evidence fails / consent fails / low utility → suppressed
  ├─ stale → expired
  └─ verified
       ├─ SILENT → suppressed
       ├─ ASK → awaiting_clarification → generated
       ├─ OFFER → offered
       │            ├─ no response → expired
       │            ├─ reject → rejected + cooldown
       │            └─ accept → accepted
       └─ ACT_REQUEST → policy_pending
                         ├─ deny → suppressed
                         ├─ ask confirmation → awaiting_confirmation
                         └─ scoped token → executing
                                           ├─ verified state → executed
                                           ├─ rollback → rolled_back
                                           └─ unverifiable → unknown
```

[FRAME｜置信度：高] `accepted` 只表示用户接受建议，不等于外部动作授权；若建议随后需要工具操作，必须重新构造动作信封。

[FRAME｜置信度：高] `rejected` 不产生“用户不信任我”“关系受损”等派生人格判断，只更新该类型候选的冷却与偏好。

## 4. 可证伪指标

| 指标 | 定义 | v0.1 冻结候选标准 |
|---|---|---|
| [FRAME] Need recall | [FRAME] 有明确帮助需求的机会中产生合适 ASK/OFFER 的比例 | [FRAME] 与高召回基线相比下降不超过 10 个百分点 |
| [FRAME] False intervention rate | [FRAME] 全部无需求机会中实际外显的不必要干预比例 | [FRAME] 相对“候选直接输出”下降至少 50% |
| [FRAME] False discovery among offers | [FRAME] 已外显 OFFER 中被标为不需要的比例 | [FRAME] 单独报告，不冒充标准假阳性率 |
| [FRAME] Correct silence | [FRAME] “检索正确但此刻不应提及”子集中的沉默比例 | [FRAME] 至少 95% |
| [FRAME] Exposure count | [FRAME] 每个机会真正向用户显示的候选数 | [FRAME] 不超过 1 |
| [FRAME] Ignore escalation | [FRAME] 未回应后被重复、升级或跨频道发送的比例 | [FRAME] 0 |
| [FRAME] Unauthorized action | [FRAME] 未经 ADR-004 有效令牌执行的动作比例 | [FRAME] 0 |
| [FRAME] Correct-to-wrong rate | [FRAME] 自我纠错把原正确结果改错的比例 | [FRAME] 必须显式报告；高影响状态为 0 |
| [FRAME] Cross-session instruction survival | [FRAME] 外部指令进入记忆后在新会话复活的比例 | [FRAME] 0 |
| [FRAME] Cancellation latency | [FRAME] 当前 Vault 进入 `contact_paused` 到该 Vault 全部主动候选失效的时间 | [FRAME] 在同一事务或可验证的短界限内完成 |

[FRAME｜置信度：高] 阈值是待冻结的工程假设，不是论文证明的通用常数；首次真实基线前不得把它们宣传为已达成性能。

## 5. 与现有评测的对应

[KNOWN｜置信度：高] `Amadeus 主动性、权限与关系安全评测增量 v0.1` 已定义 12 条 PRO 场景和 8 条 COR 场景，覆盖过期、Vault 联系暂停、敏感记忆、重复触发、拒绝冷却、无回应、外部验证、正确改错和反思越权。

[INFERRED｜置信度：高] ADR-003 的最小实现必须先通过 PRO-01 至 PRO-12、COR-01 至 COR-08；任何平均自然度得分都不能抵消敏感记忆泄漏、关闭失效或未经授权执行。

[INFERRED｜置信度：高] 真实用户校准还需增加按 Vault、频道、时间和候选类型分层的拒绝率；若全局阈值与关系边界持续不一致，必须收紧 `deployment_policy_ref`，而不是让奖励模型强行统一。

## 6. 被拒绝的方案

| 方案 | 裁决 | 理由 |
|---|---|---|
| [FRAME] 持续后台生成并保存完整“意识流” | [INFERRED] 拒绝 | [INFERRED] 成本、隐私、注入和漂移扩大；没有主体性证据 |
| [FRAME] 检索到相关记忆就主动提及 | [INFERRED] 拒绝 | [INFERRED] 忽略时机、同意、敏感度与负面记忆成本 |
| [FRAME] 用单一 F1 优化主动性 | [INFERRED] 拒绝 | [INFERRED] 高召回可掩盖约一半建议不需要，且不同错误成本不对称 |
| [FRAME] 用同一个 LLM 自评后直接提交纠错 | [INFERRED] 拒绝 | [INFERRED] 一般任务缺少可靠证据，且会发生正确改错 |
| [FRAME] 奖励模型单独决定是否打扰 | [INFERRED] 拒绝 | [INFERRED] 可通过过度沉默降低误报，离线判官也未按个人长期选择校准 |
| [FRAME] Planner 直接持有工具凭据 | [INFERRED] 拒绝 | [INFERRED] 候选生成与执行授权无法隔离，外部内容可借规划链提权 |

## 7. 后果与未决问题

[INFERRED｜置信度：高] 正面后果是：主动性可以独立回放、计费、关闭和审计；记忆检索、语言生成与工具执行不再互相冒充授权。

[INFERRED｜置信度：高] 代价是：系统会比“看到就说、想到就做”更保守；需要维护事件来源、候选状态、用户级预算、冷却和状态差分，并为真实用户校准单独收集数据。

[KNOWN｜置信度：高] 现有论文没有给出跨多年关系、跨模型迁移和持续私人设备监测下的最优主动阈值，也没有证明单一文化样本的接受标准可普遍适用。

[FRAME｜置信度：中] 未决问题包括：不同用户是否需要完全不同的主动预算；紧急场景如何由外部确定性规则而非语言模型定义；在不保存原始推理时，最少需要保存多少决策摘要才能重放失败。

## 8. v0.1 实现合同

1. [FRAME｜置信度：高] 只接收显式用户消息、用户创建的提醒、已授权任务结果和系统状态变更四类事件；不默认监视键鼠、剪贴板或全部窗口。
2. [FRAME｜置信度：高] 实现带 `vault_id` 的事件信封、候选对象、四级裁决、冷却、去重、过期和当前 Vault `contact_paused`。
3. [FRAME｜置信度：高] 每次机会内部最多生成 3 个候选，外部最多显示 1 个；候选在任务结束或过期后删除草稿。
4. [FRAME｜置信度：高] v0.1 只允许 `SILENT / ASK / OFFER / ACT_REQUEST`；任何真实动作必须交给 ADR-004。
5. [FRAME｜置信度：高] 持久化事件证据、决策摘要、动作、观察和状态差分，不持久化原始隐藏推理。
6. [FRAME｜置信度：高] 上线前冻结 PRO/COR 测试并建立“候选直接输出”与“独立 Gate”两组可比较基线。
7. [FRAME｜置信度：高] 首次用户试验的优化目标同时包含任务帮助、正确沉默、自主关闭和打扰成本，不以会话时长或留存率作为单一北极星。

[我打破的规则 / RULES I BROKE]：无。
