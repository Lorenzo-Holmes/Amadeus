# Amadeus Persona Core — Canonical Execution Guide

版本：1.0 · 2026-09-20。交付状态：`INSTALLED_AS_CANONICAL_GOVERNANCE_ENTRY`。

安装记录：2026-09-20 经用户明确授权写入当前 Persona Core 主工作区，并由根 `AGENTS.md` 设为 Persona Core 会话首读治理入口。本文中的 `PROPOSED_CHANGE`、P1–P8 路线和新增架构裁决仍须按 Change-Control Protocol 逐阶段采用；安装本文件不等于这些 proposed architecture 已实现、G6 machine truth 已改变或历史 validation verdict 已改写。

本文件完成原始目标恢复、架构范围裁决及后续执行治理设计。它不是实现完成、验证通过或生产激活证书。本轮未向 Windows 项目写盘，未修改源码、机器状态、历史证据或 Codex 会话，未调用目标模型，未启动 R16 或新的 external44。

审计裁决：`SCOPE_DRIFT_CONFIRMED_IN_FORMAL_VALIDATION_PATH`。需要架构校准，但不应推倒 Persona Core，也不应将问题扩大为所有普通会话均被锁死。

## 0. Document Authority

### 0.1 权威与生效范围

当前审计对象是 `C:\Users\skr\Documents\Codex\Amadeus-Project.staging\persona_core` 的 Operations V1 / G6 主线。该路径由 Master Goal、Operations 构建文档和 G6 `USER_OBJECTIVE.md` 共同明确指定，不是仅凭目录名或修改时间选出的。[S02、S05、S07]

本文件区分：`RECOVERED_PRINCIPLE` 为已从原始文档恢复的原则；`OBSERVED_STATE` 为本轮读取或计算的事实；`AUDIT_JUDGMENT` 为基于来源的架构判断；`PROPOSED_CHANGE` 为待落实的新设计。不得将建议当作现有实现。

用户当前要求优先于旧的持续执行提示词。本轮授权只覆盖读取、搜索、分析与交付文档；“继续执行”不扩大为改源码、调用模型或解锁任务。安装本文件、修改启动入口、修改实现和开展付费验证是不同动作，不因其中一项获准而自动全部获准。[S01]

经用户明确要求写盘后，本文件可作为 Persona Core 的首读治理入口；必须保留已批准的原始原则，并明确新增架构裁决的采用记录。未安装之前，不能声称其他会话已被强制约束。它不取代机器状态，不接管 D 盘旧 Route B 的全部工程或未来自主系统。

### 0.2 Source Authority Hierarchy

规范问题依次依据：当前明确用户要求与有效修订、Master Goal / 原始目标、当前适用的正式架构与续接协议。事实问题依次核对：原始回执和实际代码/数据库、具名机器状态、验证报告、历史会话总结。二者不能混成一个总排名。

机器状态可以证明“失败、停止、尚未完成”，不能授权扩大产品目标；旧目标不能把真实失败改成成功。原始用户消息可作为需求证据，guardian 子会话中的转述、assistant 总结和临时推测不能冒充用户要求。历史 finding 是证据，不是无限增加架构门禁的授权。

### 0.3 来源索引

以下未标绝对路径的来源均相对当前 C 盘工作区；`G6/` 简写指 `persona_core/gpt6_optimization_v2/`，`OPS/` 指 `persona_core/operational_build_v1/`，`RT/` 指 `persona_core/operational_runtime_v1/`。

| 编号 | 可复核来源与本轮用途 |
|---|---|
| S01 | 用户 2026-09-20 上传的 942 行审计指令；目标、只读约束、完整交付要求。 |
| S02 | `AMADEUS_PERSONA_CORE_MASTER_GOAL.md`；已读全文，原始使命、Genesis、人物构建链、历史镜像。 |
| S03 | `PERSONA_CORE_CONTINUATION_PROTOCOL.md`；已读全文，状态更新、来源和续接规则。 |
| S04 | 当前根 `AGENTS.md`；主线、角色来源和 Operations 状态入口。 |
| S05 | `OPS/BUILD_PLAN.md` 全文；`OPS/TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md` 的对话、展示、准入和事务合同。 |
| S06 | `OPS/QUALITY_ASSURANCE_PROTOCOL_V1.md`、`ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md`、`START_HERE.md`；`TASK_STATE.json`、`ACCEPTANCE_MATRIX.json` 的状态、任务和门。 |
| S07 | `G6/USER_OBJECTIVE.md` 全文；G6 原始优化授权、确定性边界与表达层、质量阈值、后续 DAG。 |
| S08 | `G6/GOAL_STATE.json`、`TASK_GRAPH.json`、`RECOVERY_CURSOR.json`、`VALIDATION_MATRIX.json`；当前字段和任务/门结构；`CURRENT_EXECUTION_RUNBOOK.md` 与根 Progress 的当前镜像。 |
| S09 | `G6/terminal_revision12_stop_20260919/FINAL_AUDIT.json`。 |
| S10 | `G6/fresh_external44_20260919_13/FINAL_AUDIT.json` 的结果与 finding 字段。 |
| S11 | `G6/fresh_external44_20260920_14/FINAL_AUDIT.json` 的结果、摘录与 finding 字段。 |
| S12 | `G6/semantic_output_guard_r14_20260920_01/FINAL_AUDIT.json`、`USER_SCOPE.json`，即 G6-07R5。 |
| S13 | `G6/trusted_semantic_acceptance_20260920_01/FINAL_AUDIT.json`、`USER_SCOPE.json`；`G6/TRUSTED_SEMANTIC_ACCEPTANCE_DESIGN.md`，即 R6。 |
| S14 | `G6/trusted_acceptance_external44_preflight_20260920_01/FINAL_AUDIT.json`；`trusted_acceptance_external44_integration_20260920_01/FINAL_AUDIT.json`、`G6/FORMAL_BINDING_ROOT_CAUSE.md`，即预检和 R7。 |
| S15 | `G6/fresh_external44_20260920_15/FINAL_AUDIT.json`；该目录 `turns/N02_T1/RAW_TEXT_PRIVATE.json`、`ACCEPTED_TEXT_PRIVATE.json`。 |
| S16 | `RT/chat.py`、`accepted_output.py`、`trusted_admission_adapter.py`、`semantic_types.py`；`admission.py` 的候选、决定和 `observe_turn` 路径。 |
| S17 | `PERSONA_CORE_DECISION_LOG.md` 的相关裁决，特别是 1172–1223 行的 R13→R15 原始追加记录。 |
| S18 | `D:\AI\CodexWorkspaces\Amadeus-Project.staging\PROJECT_CHARTER.md`、`README.md`；该目录 `AGENTS.md` 的早期愿景、比例化审查和旧 Route B 边界。 |
| S19 | `.codex\sessions` 的 7 月主会话用户消息和 8 月重复核验治理要求；精确文件及覆盖范围见配套发现报告。 |
| S20 | 本轮目录元数据扫描、直接目录列表及 163 文件 SHA-256 核验回执；完整范围和哈希见配套发现报告。 |

### 0.4 Project Discovery Report 摘要

已实际发现当前 C 盘 Persona Core 工作区、D 盘较早的控制工作区、Route B 仓库与 worktree，以及来源语料、备份和日期任务副本。部分目录名指向研究、桌宠或 VRoid 资产，但未逐一读取内容，其用途只作暂定分类。当前 G6 的权威工作区不等于所有历史 Amadeus 工程只有一个目录。[S18、S20]

本轮目录级有界扫描访问 44,898 个目录，停止时队列仍有 40,744 个目录；排除了依赖、版本库内部、系统目录和链接，存在权限错误。因此是有覆盖边界的发现，不是全盘无遗漏扫描。没有递归读取 D 盘全部文件正文。[S20]

原始目标由早期 Charter、当前 Master Goal、Operations 与 G6 原始规范交叉恢复。7–8 月日志已检索并核验部分用户原文，但未穷尽所有会话，也不宣称找到项目诞生的第一条消息。该限制不阻止根据已读正式规范、实际代码及 R15 原始输出裁决当前路径；不得据此断言未读材料不存在。

## 1. Original Product Mission

`RECOVERED_PRINCIPLE`：建立一个具有持续身份、来源人格、受治理记忆、关系与独立运行经历的 Amadeus，而非一次性角色提示词、无状态聊天机器人或单纯模仿口癖的界面。[S02、S18]

来源中的人物经历构成起源；Genesis 后的实际运行形成该实例自己的经历。人物表达、判断、关系变化和成长，应能关联到来源、上下文及真实经验，而不是让模型凭自述重写身份。

长期愿景包含受治理的自主学习、信息获取、工具使用、获准联系与任务完成。当前阶段先交付真实连续文本对话、可靠运行和可检验的质量；不能把长期愿景删成“永不成长”，也不能把全部自主能力提前塞入 G6-07。[S05、S18]

## 2. Non-Goals

本阶段不构建通用中文自然语言定理证明器，不要求任意自然语言都进入有限 ontology 后才允许回应。R6 自身也明确限定为 bounded typed vertical slice，不能把其局部保证外推为全部中文语义保证。[S13]

不混合不同连续性为同一人生，不用模型先验填补来源缺口，不把来源事实自动写成第一人称回忆，不把测试经历注入生产实例，不通过重装 Genesis 消除失败。[S02、S03、S05]

UV、Avatar、TTS、Unity、网页外观和全面自主 Executor 扩展不属于本次修复。它们可以是未来工程，但不是 G6-07 通过的前置条件。增加 revision、证书种类或审计报告数量也不是产品目标。

## 3. Product Architecture

来源构建主链保持：来源证据→连续性辨析→人物经历与事件→记忆截断→编码记忆→人物形成证据→Constitution / Self / Affect / Relationship / Decision→Genesis→独立 Runtime Experience。[S02]

运行上采用两个职责层，但不抹掉 Operations 原有三类记录：

```text
Conversation Layer
  身份与模式 → 检索及近期上下文 → 最小人物路由 → 模型候选回答
  → 模式相关 Response Check → 实际展示 → 对话记录 / 有限上下文

Trusted State Layer
  可核验事件或状态变更候选 → 独立证据与权限核查
  → AdmissionDecision → 原子 RuntimeCommit → 受控派生状态
```

对话、事件、状态仍是不同数据类别。两层是职责划分，不要求重建两套数据库或替换全部 Core。[S05、S16]

`PROPOSED_CHANGE`：取消“所有正式验证回答都必须由有限类型证明渲染”的通用前置条件；保留被明确选中的严格声明与状态更新的验证路径。具体路由与存储版本须先冻结合同再实现。

## 4. Conversation Layer

普通对话需要完成任务、理解指代、保持上下文、自然表达并遵守认识论边界。无需用户填写 tags、事件 JSON 或证书。科学讨论中的条件分析、明确假设、建议、问题澄清可以存在于当前对话，而不自动成为持久事实。[S05、S07]

Conversation 并非无约束 raw 放行。仍检查隐私、跨对象内容、来源/回忆混淆、伪造工具能力、虚假已完成声明以及当前模式。已知错误不能因“不写 memory”而被合理化。

下一轮上下文使用实际展示给用户的内容，并保留角色、来源、假设和纠正。未展示的 raw 草稿不能暗中成为共同对话历史；历史中出现过错误，也不能因反复引用而升格为事实。

## 5. Trusted / Durable State Layer

可信层管理来源边界、Runtime Memory、关系派生状态、用户事实的证据性质、承诺与执行状态。它保护的是明确的数据与状态迁移，不是垄断全部语言表达。[S02、S05]

必须区分两个现存机制：`TrustedAdmission` 服务于 R6 的有限类型语义证明；`AdmissionController` 处理事件候选、证据和可提交的状态效果。名称都有 Admission，不代表两者具有同一职责，也不代表前者必须支配每次显示。[S16]

模型可以提出 interpretation、event candidate 或 growth proposal，但不能自行签发权限、证据或提交决定。合法观察可以自动经过宿主规则准入，不要求用户人工审核每句话；规则确认不了的效果保留 HOLD，而不是强制整段对话沉默。

## 6. Trust Boundaries

同时保留 Human Kurisu、Encoded Source Memory、Externally Learned Fact、Other Continuity 与 Product Runtime Experience 的区分。[S02、S03]

还必须区分“说过 X”“报告 X”“在假设下推得 X”“已有证据支持 X”“准许写入某个状态”“动作实际完成”。这些事实各自需要相应证据，不因同处一个 JSON 或一个回答而互相授权。

`admission.py::observe_turn` 当前已把 `described_events_proven` 和 `content_is_event_proof` 置为 false；它能记录发言事件，不证明发言内容所描述的外部事件。该正确边界应保留。[S16]

摘要、检索、模型切换和重启不能消除这些限定。哈希证明版本绑定或完整性，不证明文本命题为真，更不抵御能同时改写全部可信根的宿主攻击。

## 7. State Transition Model

治理上使用下列六级视图，但不新增一套同名代码枚举。它们必须映射到现有类型，而且不是自动升级链。[S16]

| 治理视图及现存映射 | 显示 / next-turn / working context | Memory / Persona / Relationship | Task / execution | 证据及证书 |
|---|---|---|---|---|
| CONVERSATIONAL：原始发言、展示记录、`UTTERANCE_OBSERVED` | 经对话检查可用；保留说话方和模式 | 可留发言观察，不认定内容为事实；不直接改人格或关系 | 不产生完成事实 | 发言观察由实际 transcript 支持；不普遍要求语义证书 |
| INFERRED：明确推断；责任域存在 `Attribution.INFERRED` | 可作为推断、假设或建议 | 不自动成为用户事实或人格变化 | 不把计划变为执行 | 保留前提与不确定性；相关严格路径才需形式证明 |
| SUPPORTED：类型域中有 `Epistemic.SUPPORTED` | 可在证据允许的强度内表达 | 仍须目标状态的准入 | 仍不等于权限或完成 | 有具名证据；语义支持不替代控制授权 |
| CANDIDATE：`EventCandidate` / `event_candidates` | 可作为待证提案或问题 | 仅候选存储，不改权威状态 | 只能提出待核查变化 | 引用原始来源；候选不能自签证书 |
| ADMITTED：`AdmissionDecision.verdict=ADMIT` | 可陈述其精确准入范围 | 只允许决定所批准的效果；尚不等于提交完成 | 必须绑定对象、类型和真实回执 | 宿主证据 token / 决定；形式证书仅在对应有限类型策略要求时使用 |
| DURABLE：受支持的 `RuntimeCommit` / 已提交运行事件 | 可由保留来源的检索使用 | 合法派生状态可更新；Source/Genesis 不因此可写 | 仅被验证并提交的具体效果 | 原子提交、证据和幂等记录可复核；禁止把整个回答一并“持久化为真” |

现存 `Epistemic`、`Disposition`、`Coverage`、`Modality`、`TemporalState`、`Attribution` 是不同轴。`SUPPORTED` 不等于 ADMIT，`ADMIT` 不等于已 COMMIT，`COMPLETED` 文本标签不等于工具完成回执。权限另由宿主控制。[S16]

## 8. Persona / Memory / Relationship / Execution Rules

Persona / Genesis：来源身份与出生截断保持冻结。成长经明确 proposal、证据和版本化决定产生；不把临时回应、检索摘要或测试结果反写成起源。

Memory：保留 `HOLD / SOURCE_FACT_ONLY / ENCODED_SOURCE_MEMORY / PRODUCT_RUNTIME`。可记住某人作过报告，不等于承认报告真实。记忆重要性、检索和表达可以受人物与上下文治理，但不能绕过来源及状态权限。[S03、S05、S18]

Relationship / Affect：多维、按对象、由合格事件派生；熟悉不等于信任，兴趣重复和空洞道歉不能刷权限。情绪增量是工程参数，不是已验证的原作心理定律。

Execution：区分建议、计划、分配、尝试、回执、完成和验证。现有运行代码禁止一般候选直接执行 `PERSONA_WRITE / CAPABILITY_GRANT / RELATIONSHIP_WRITE / GENESIS_INSTALL` 等效果。未来 Executor 仍须独立权限、范围与回执合同，不由人格台词授权。[S16]

旧 Route B 的认知开关、终止和自主控制设计保留为其具名历史/未来合同，不在本次文档中宣告已经迁入当前 Persona Core，也不能据其文字改变现实宿主权限。[S18]

## 9. Validation Philosophy

原始目标同时要求正向对话质量与可靠状态。无越权不等于有用；拒绝全部回答也不能通过人物质量门；自然流畅同样不能掩盖虚假记忆、错误责任归属或无证执行。[S05、S07]

分别记录 BYTE_PRESENT、HASH_BOUND、STATIC_VALID、BEHAVIOR_TESTED、FAULT_TESTED、TARGET_MODEL_CAPTURED、SEMANTIC_REVIEWED、QUALITY_GATE_PASSED、INDEPENDENT_REVIEWED、REAL_TIME_LONGITUDINAL。低层证据不能自动升级。[S06]

新设计不降低已经冻结的情境适配 ≥4/5、自然度 ≥4/5、人物特异性 ≥3/5、Critical=0 等要求；改变的是不适用的证明前置条件和明确的判定维度，而不是删除失败标准。[S07]

## 10. G6 Correct Scope

G6 应优化人物忠实度、自然表达、上下文、认识论纪律以及状态可靠性。原规范明确要求强确定性边界配合较轻的生成式表达层，并反对让确定性层决定每句具体措辞。[S07]

以下为机制重新安置裁决。A=普通对话适用；B=高权威/强断言；C=持久状态准入；D=执行与权限；E=审计。F 指应废弃的适用规则，不表示删除整个模块。

| 机制 | 保留位置与边界 |
|---|---|
| Claim / Evidence | A 保留事实依据与限定；B/C/D 要求匹配的证据，不让每句闲谈生成证书。 |
| Reasoning Scope | A/B 保留前提、域与推理强度；C/D 的形式迁移在有限类型内严格检查。 |
| Candidate Closure | A 不能谎称穷尽；B/C 涉及确定排除和有限全集时严格验证；开放讨论可列非穷尽候选。 |
| Responsibility Grounding | A 保留说话者、执行者和建议/分配区分；C/D 禁止错误写入责任或完成状态。 |
| Provenance | A–E 全程保留，尤其经过摘要、检索和模型切换时。 |
| UNKNOWN | A 允许带不确定性的有用回答；C/D 阻止无证升格，E 分清语义未知和调用未知。 |
| Typed Semantic Plan | B/C/D 的有限类型路径及 E；不是全部 Conversation 的协议前提。 |
| Trusted Admission | 有限类型证明入口保留；事件准入仍由 `AdmissionController` 管理，二者不能混同。 |
| Claim Certificate | B/C 的需证强声明及 D 的特定已验证效果；不替代权限 token。 |
| Exclusion Certificate | B/C 中明确作排除结论的有限域；普通猜想不要求先穷尽全部可能。 |
| Closure Certificate | B/C 中声明全集封闭的情形；不服务于无限自然语言世界的全覆盖。 |
| Raw / Accepted Separation | A–E 保留不可变 raw 和真实展示谱系；显示合格不自动代表内容已获持久事实权威。 |
| Fail-closed | D、状态提交、身份/隐私及绑定完整性必须保留；对纯语义 UNPARSED 采用局部禁止升格，而非普遍封嘴。 |
| Consumer Binding | 保留显示、历史、next-turn、评测一致性；memory 消费须追加事件/事实准入，不一刀切地继承文本权威。 |

F：废弃“普通回答必须全部由有限证明器覆盖才能显示”这一通用规则；废弃把模板兜底计作自然度成功或把每个 UNPARSED 计作模型语义违规的推导。历史记录不改写。[S13–S16]

## 11. What G6 Must Not Become

不能从一次 benchmark failure 自动跳到新 parser、新 ontology、新 certificate，再要求覆盖更大的语言空间。新增控制必须能指向具体产品风险、状态迁移、有限责任范围和可验证退出条件。

也不能反向走向无状态聊天或直接放行所有 raw。原本有效的来源、记忆、权限、真实性约束仍然适用。复杂度应集中在真实权威边界，而不是把全部人物表达变成审计表格。[S05、S07、S18]

## 12. Historical Lessons R12–R15

| 阶段 | 原始观察 | 本次裁决 |
|---|---|---|
| R12 | 9 次提交，8 次捕获，1 次已知终态拒绝；32/176 已评，31 PASS、1 FAIL | 传输终态与语义 finding 分开；既有问题保留，不能归咎于 R15 输出门。 |
| R13 | 24 次提交，23 次捕获，1 次已知终态拒绝；92 项=79 PASS、8 FAIL、5 UNCLEAR | 候选封闭、计划/完成、归因和指代问题是真实待修项，不因后续架构改变作废。 |
| R14 | 4 次提交及捕获；16 项=12 PASS、4 FAIL；2 Minor、1 Major finding | 推理跨域桥接和候选穷尽存在问题；不能用“普通聊天不用证书”合理化错误结论。 |
| R5，2026-09-20 03:27 UTC 审计 | 把 ordinary input 缺少可信语义解释列为根因；提出 HYBRID；`REPAIR_ARCHITECTURE_NOT_READY` | 在已读记录中，这是向证明式输出修复转向的明确节点，但此时尚未实现生产 guard。 |
| R6，报告记录 04:28–04:38 UTC | 有限类型准入/证明/渲染及 accepted 持久化；135 focused、732 component；默认 OFF | 局部机制有效性与普通自然语言适用性不是一回事；其离线自然度 PASS 不能外推。 |
| 预检，报告记录 06:58–06:59 UTC | 正式路径仍 OFF，绑定失败，0 调用、0 判定 | 正确发现“组件存在但正式路径未接入”；零观察不是 PASS。 |
| R7，报告记录 07:45–07:49 UTC | 正式 external44 必须显式 TRUSTED；有限目录和 consumer 绑定接入 | 正式自然对话验证被要求经过有限证明路径，范围冲突成为实际接线问题。 |
| R15，08:09 观察、08:16 关闭 | 1 次真实请求；raw 语义违规计数 0；UNPARSED→BLOCK→模板；任务完成 FAIL | 证实形式接线正确仍可损坏对话可用性；停止当前 revision 合理。 |

来源分别为 S09–S17。测试数量是历史审计所记录，本轮未重跑测试。

R15 raw 对当前问题给出了限定条件和核查建议，accepted 却只剩“这段信息还不能支持可靠判断，请补充明确的条件或来源。”代码在 plan=null 时触发 `UNPARSED_OR_UNSUPPORTED_INPUT`，随后固定 fallback，形成可复核的因果链。[S15、S16]

R15 的评审标注为 `INTERNAL_DEVELOPER_NONBLIND`，不是外部独立盲评。运行时 raw violation 标志源于 UNPARSED，也不等于已发现 raw 语义错误。只实际观察一轮，不能报告 44 轮全部失败。

范围裁决：漂移已在正式验证路径确认；没有证据证明所有普通生产会话已被全球开启的 guard 锁死。R5/R6 也有具名 scope 授权，不能指控为擅自修改；问题是局部修复组合后的产品适用范围没有同时满足原来的对话目标。[S12–S16]

## 13. Current Machine Truth

`OBSERVED_STATE`：2026-09-20 读取的四份 G6 状态文件一致，最新状态记录时间为 `2026-09-20T08:16:11.319276+00:00`。[S08、S20]

```text
CURRENT_STATE = G6_07_FRESH_R15_STOPPED_REVIEW_COMPLETE
ACTIVE_TASK = G6-07
ACTIVE_SUBTASK = null
LAST_COMPLETED = G6-06
LAST_COMPLETED_INTERNAL_SUBTASK = G6-07-FRESH-R15-ADJUDICATION
BLOCKER = TRUSTED_ADMISSION_COVERAGE_INSUFFICIENT
revision = external44_20260920_15_fresh_trusted
revision_status = PERMANENTLY_QUARANTINED
submitted / captured / accepted = 1 / 1 / 1
reviewed = 4/176；PASS 3；FAIL 1；UNCLEAR 0；UNREVIEWED 172
natural_days = 0
product_acceptance_complete = false
production_activated = false
G6-08 / G6-09 / Candidate V2 / Blind = LOCKED
```

`current_repair_build_complete=true` 只是局部修复构建字段；当前源语义验收及 G6 build-scope pending 完成标志仍为 false。不得摘出局部 true 宣布全项目通过。

当前冻结为 `TRUSTED_ACCEPTANCE_EXTERNAL44_INTEGRATION_20260920_01`。本轮重新计算其 163 个成员哈希，163/163 匹配；manifest SHA-256：`0995cf66719e5c0a9aaec5aad2e38bec97ccf480182386333a1fa05c7065753b`。[S20]

机器记录历史 UNKNOWN 行 7 个、尚未解决 6 个；当前 R15 没有新增 UNKNOWN。历史隔离不是静默清零，也不是自动重发许可。[S08]

Operations V1 旧状态已曾达到 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`，并记录过旧候选真实日进度；G6 是明确重开的新验证周期。旧候选的 82/328 或 Day 1 均不继承到当前 G6。[S06–S08]

## 14. Frozen Decisions

继续保留既有冻结原则：来源与运行经历分离；Genesis 不被普通对话改写；模型不自授权；事件与提交具名；实体隔离；UNKNOWN 调用不自动重发；历史失败不可覆盖。[S02–S07]

本次新增的“两个职责层、双验收门、有限严格路径”属于 `PROPOSED_CHANGE`。本文件交付即形成审计建议，不自动把实现标成恢复完成。正式采用时追加架构决定，写明替代哪些旧适用规则、保留哪些旧行为、影响哪些 consumer 和哪些验证身份。

不得在普通 repair 中再改已采用的这些边界。需要扩大架构时，重新取得明确的 Architecture Reconciliation 授权，而不是引用一个旧 finding 当许可证。

## 15. Architecture Invariants

模型输出不产生控制权；实际展示不等于内容为真；发言记录不等于外部事件；证据支持不等于获准提交；获准提交不等于事务已经完成。

Source/Genesis、实体归属、权限、真实执行和历史证据保持边界。显示与 next-turn/evaluation 对齐；memory 的权威依据由自己的目标状态准入决定。可疑事实不能经摘要或重复复述洗成确定事实。

对无法证明的普通解释，允许保留条件和不确定性；对无法验证的状态变更，禁止升格。绑定损坏、跨对象泄漏、伪造能力与执行回执不是普通 UNPARSED，仍必须阻止相应操作。

## 16. Allowed Repair Scope

下一次获准实施后，优先检查和最小修改 `RT/chat.py`、`accepted_output.py`、`trusted_admission_adapter.py`、`semantic_binding.py` 及其直接 consumer 接口，明确 DISPLAY_ELIGIBILITY 与 STATE_ADMISSION 的不同合同。前两者的命名是本文件提出的职责标签，不冒充现有枚举。

保留当前 raw 不可变记录、accepted 谱系、实体和版本绑定、事务与回执检查。涉及 `admission.py`、检索或评测投影时必须说明具体受影响状态，不能为重构方便无差别重写。

禁止修改冻结来源人格、Genesis、旧审计 verdict、旧 raw/accepted、历史 journal、既有测试实例来获得通过。禁止顺带重构 provider transport、添加 Avatar/UI、扩大工具权限或构建通用语义解析器。

## 17. Scope Drift Guardrails

每个修复必须回答：恢复哪一项已批准产品行为；保护哪个明确 state transition；为什么既有边界不足；新增机制的最小范围及退出条件是什么。

若 benchmark failure 需要扩大 production architecture，先进入治理状态 `ARCHITECTURE_RECONCILIATION_REQUIRED`。该状态是本文件建议的变更控制规则，本轮没有写入现有机器状态。

同一产品快照上的重复审查应复用有效证据。工具重启、报告追加或无关临时文件变化，不自动使产品全部证据失效。新的产品/治理语义变化才触发相关范围复验。禁止审计报告再触发对报告的无限审计。[S18、S19]

## 18. Conversation Utility Gate

该门评估用户实际看到的回答，而非仅评 raw、计划或形式证明。范围包括任务完成、相关性、指代、语境连续、自然度、人物特异性、可操作帮助及不必要的工程术语。[S05、S07]

同时保留回答中的事实与推理纪律：不得伪造排除、责任、记忆或行动；开放假设必须是开放假设。一般性兜底只有在真正需要澄清且无法先提供有用回答时才合理，不能因 adapter 未解析就自动获得“安全且自然”的评分。

采用预先冻结的原始质量阈值。报告明确 UNREVIEWED 和 UNCLEAR，不把未评项目视作通过。不用 guard block 数量、证书数量或“零状态写入”代理任务完成率。

## 19. State Integrity Gate

该门直接检查 candidate→decision→commit 及 next-turn/retrieval 的状态与来源效果：unsupported 不升级事实；planned 不变 completed；suggested 不变 assigned；UNKNOWN 不升级 certainty；开放候选不被写成穷尽；Persona、记忆、关系和执行状态不受无证污染。[S05、S16]

检查需要有 before/after、事件与证据引用、entity、幂等和重启结果。不能只读取最终文本便声称所有状态安全；也不能把一次受约束的发言观察自动计作事实污染。

下一轮离线合同至少覆盖八类成对用例：条件分析、待证猜想、引用错误说法、计划/完成、建议/分配、开放/封闭候选、HOLD/跨实体、真实回执/重复回执。同类内容分别测试“用于对话”和“请求升格状态”，形成有限正反例，而不是继续扩大无限语言覆盖。

## 20. Benchmark Isolation Rules

旧 external44 的 44 轮/176 项不是问题本身。已确认的混合发生在执行策略：普通对话任务被强制送入有限证明式输出路径，UNPARSED 于是变成展示阻断。[S14–S16]

新协议必须在看新输出前，把每个原 criterion 映射到 Conversation Utility、State Integrity 或二者；保留原 ID、原题、原失败和分母，另附适用性裁决。本文未声称已逐项完成全部 176 项映射，映射是下一实施阶段的具体产物。

普通会话轨不强制 typed plan；类型化状态轨使用独立宿主事实、确切证据及严格证明。不得把 benchmark 标准答案塞入 trusted catalog，不能把 PRIVATE_RUBRIC 发给生成模型。更改执行合同形成新版本，新旧结果不能合并成同一通过率。

R12–R15 已见问题可以进入开发回归，但不再称为未见样本。后续 G6-08 heldout 和 G6-09 全量 82/328 仍保留，不以“架构已调整”省略。

## 21. Provider / Runtime Boundaries

Provider 是生成后端，不是身份、权限、记忆或回执权威。成功响应、有效文本、显示成功、语义通过、状态提交和产品验收分别记录。[S05、S07、S15]

继续采用 journal-first、具名 batch/turn、原始 request/response、明确终态及 `automatic_paid_retries=0`。UNKNOWN 可能已收费，先查已有证据，不自动补发、替换或隐藏再生成。

当前用户禁止模型请求，因此本轮 remote/readiness/generation 均为 0。未来批次只在适用授权下执行，并在看输出前固定模型、接口、请求数、输出上限和有限费用保护；执行当时再核实官方接口与计价，不能从本文继承旧价格或模型可用性。

## 22. Source Freeze Rules

保留当前 R7 source freeze 和 R15 validation identity。下一次实现形成新的 source freeze；新验证形成新的 validation revision，二者不互相冒充。

冻结内容限于产品字节和明确声明的 governing 工件。临时目录、环境噪声、审计日志和报告追加不是默认产品身份；不得通过层层 hash-of-hash 构造自指重验证链。[S18]

运行时 hash/version 改变可能使旧 accepted 记录拒绝加载；这是现存 `load_record` 行为，迁移必须显式处理。不能修改旧记录的 runtime identity 来让新代码接受它们，也不能把旧数据库普通切成新模式。旧模式不可变，迁移先隔离验证。[S16]

## 23. Evidence Preservation Rules

原始 provider 响应、raw、accepted、审阅、case IDs、历史 source/validation freezes 和调用终态保持不可变。纠正采用新记录引用旧记录，既保留当时结论，也记录后来发现。

当前源码 163/163 匹配是本轮实际计算结果；历史报告中的 777 个组件检查、2,215 个历史成员保全等属于当时报告，不冒充本轮重跑或重新全量保全验证。[S14、S15、S20]

私有案例、用户消息、凭据和回执不能因 Git/publication 需要而自动公开。公开摘要与私有审计包分开；写盘、提交、推送、公开发布分别受实际授权约束。

## 24. Historical Revision Rules

R12、R13、R14、R15 继续保留原 verdict、原分母和原未评状态。架构改善不能“洗掉”历史失败，也不能把 R15 当前永久隔离改成可续跑。[S09–S15]

旧 Operations 的 build complete、旧 Route B 的 FINAL_VERIFIED、当前 R6/R7 的局部 PASS、G6-07 的失败，是不同范围和版本上的事实，不矛盾，也不能相互替代。[S06、S08、S18]

历史裁决如果有误，追加“原结论—新证据—影响范围—新裁决”，不覆盖旧原件。新版本的回归通过只能证明新版本对应问题已解决，不把旧 FAIL 改成 PASS。

## 25. Stop Conditions

本轮在只读审计和文档交付完成处停止，不开展实现或新实验。

后续执行遇到权限/平台阻断、数据完整性风险、未知收费提交、冻结身份不匹配、真实 Major/Critical 阻塞或架构范围扩展时，停止相应危险分支并保存事实；不为了完成计数继续收费或写状态。

普通解析不足不自动阻止独立离线分析；真实外部评审与未来自然日只阻塞相应门。已获准范围内的普通工程失败应分类修复，但不能借“持续执行”跨越新架构或付费授权。

## 26. Architecture Reconciliation Trigger

以下情形需要校准：原本只保护状态的机制开始控制所有表达；一个有限域组件成为普通聊天的必需协议；为修一个 benchmark 需要新增生产能力或放宽权限；离线通过与实际用户可用性长期冲突；重复增加相同类型补丁而无新证据。

校准产物必须给出原始需求、实际调用链、失败实例、保留/撤回/迁移矩阵、目标状态边界、有限验证及退出标准。不能只有“更安全”或“再扩 coverage”两个理由。

R15 已满足触发条件。本轮完成其只读诊断与治理方案；生产代码、machine truth 和准入合同仍保持原状。[S15、S16]

## 27. Phase Roadmap

以下 P0–P8 是本文件的规划标签，不是已写入 TASK_GRAPH 的新任务，也不改原 G6-01～14 编号。各阶段未达到条件不得继承完成状态。

### P0 — Original Goal Recovery / Scope Reconciliation

**Goal / Why：**恢复产品目标并定位形式证明与展示的范围冲突，避免继续盲目扩大 parser。**Input：**原始治理、Operations、G6 状态、R12–R15、实际代码与 raw/accepted。

**Allowed / Forbidden：**仅 read/search/analyze 和回答/沙箱文档交付；禁止改项目、运行模型、启动新 revision。**Deliverables：**本 Guide、发现报告、来源和哈希核验、八项裁决。

**Validation / Pass：**使命、调用链和 R15 因果证据互相一致，未知范围明确；本轮已达到只读裁决与交付范围。**Stop：**交付后停止。**Remote Provider：**0。**Source Freeze：**保留现有。**Unlock：**后续明确授权采用/写盘，才进入 P1；不是自动开始 R16。

### P1 — Adopt Bounded Architecture Contract

**Goal / Why：**把两层边界落实为可审查合同，先定范围再改代码。**Input：**P0、当前四份状态及 163 文件冻结、原 external44 rubric。

**Allowed / Forbidden：**获准后写 Guide/ADR、consumer 矩阵和执行协议；禁止改历史 verdict、生成目标回答、放宽原质量阈值或扩大自主功能。**Deliverables：**显示与状态准入合同、14 机制矩阵、176 项适用性映射、精确文件 allowlist、迁移/回滚和有限测试定义。

**Validation / Pass：**每个 consumer 有明确来源/权限；UNPARSED 正反例结果固定；严格路径有限、无答案映射；不存在“文档通过=产品通过”。**Stop：**合同冲突或需扩大范围。**Remote Provider：**0。**Source Freeze：**旧冻结保留，新增治理版本单独登记。**Unlock：**合同采用且实现范围获准后 P2。

### P2 — Minimal Boundary Repair

**Goal / Why：**恢复普通 Conversation 的可用性，同时保持状态与执行保护。**Input：**P1 合同和 allowlist。

**Allowed / Forbidden：**最小修改显示选择、typed-path 选择、consumer 投影和必要的版本处理；禁止重写 Persona/Genesis、provider transport、旧会话策略、旧 raw/accepted 或历史评审。**Deliverables：**局部代码差异、显式模式/来源字段、迁移或拒绝迁移规则、回滚说明。

**Validation / Pass：**普通合法分析不因 plan=null 被模板覆盖；无证状态更新仍 HOLD/REJECT；实体、隐私和真实执行约束保留；实际显示与 history/next-turn 一致。**Stop：**需扩 ontology 或跨越合同边界时回 P1，不即兴扩项。**Remote Provider：**0。**Source Freeze：**新源版本，不覆盖旧冻结。**Unlock：**实现完成且可离线检验后 P3。

### P3 — Offline Dual-Gate Validation

**Goal / Why：**证明可用性与状态保护可以同时成立，再考虑付费。**Input：**P2 新源、固定的成对样例和相关既有回归。

**Allowed / Forbidden：**隔离副本中的单元、集成、重启、幂等和受影响故障测试；禁止正式状态写入、历史请求重发、把 mock 当真实模型表现。**Deliverables：**正反例结果、状态前后差异、consumer 对齐、相关回归及旧身份 sentinel 的明确解释。

**Validation / Pass：**两门同时通过全部固定离线用例，0 意外功能回归；文档哈希、代码行为和录制字段一致。既有 449 compatible + 1 expected sentinel 不得伪写成 450 全通过。**Stop：**任何新边界逃逸或只靠拒答过关。**Remote Provider：**0。**Source Freeze：**通过后冻结新源。**Unlock：**零调用预检通过且获得新批次授权后 P4。

### P4 — Fresh G6-07 Validation

**Goal / Why：**在新合同和新源上验证真实对话，不复活 R15。**Input：**P3 冻结、新 source/policy/consumer 身份、P1 预定的 criterion 映射与批次。

**Allowed / Forbidden：**只提交具名新 revision 的固定请求；禁止续跑 R15、重发旧 UNKNOWN、隐藏补答、边生成边改源码/rubric，或把 accepted 兜底算任务成功。**Deliverables：**新 44/176 或经明确授权且事前正式登记的等价分轨覆盖，原分母与映射均可见；raw、实际展示、判断、状态 trace 和费用记录。

**Validation / Pass：**G6-07 的全部适用必需项完成并通过，两门均满足，所有新 Major/Critical 已依合同处理；未评不算 PASS。**Stop：**预定硬失败或未知提交出现即停止该 revision。**Remote Provider：**只按新授权与有限批次执行，0 自动重试。**Source Freeze：**批次内不变。**Unlock：**正式 G6-07 PASS 后 G6-08；失败则新的具名修复，保留本次失败。

### P5 — G6-08 Heldout / G6-09 Full Internal Validation

**Goal / Why：**确认修复不是只适配旧 external44。**Input：**P4 合格源、既有未见题冻结与原全量 82/328 协议。

**Allowed / Forbidden：**按原 DAG 进行 heldout 和全量真实多轮评测；禁止将已见题重新标为未见、删难例、继承旧82/328 PASS或改质量门。**Deliverables：**heldout、全量输出/判断、质量分项、长上下文和模型切换证据。

**Validation / Pass：**原门全部满足，情境/自然度/人物特异性及状态约束分别合格；原失败可追溯。**Stop：**预定失败、身份漂移、未知收费或测试污染。**Remote Provider：**各批事前冻结并受适用授权约束。**Source Freeze：**同一候选源；修改则相应验证失效。**Unlock：**G6-08/09 真正通过后 P6。

### P6 — Clean Candidate / Build-Scope Rollup

**Goal / Why：**形成干净可用候选，而非把开发数据库当成成长中的产品。**Input：**P5 合格结果、有效来源/Genesis和运行恢复能力。

**Allowed / Forbidden：**G6-10 创建干净 Candidate V2，G6-11 准备盲评包、跨日协议和具名内部汇总；禁止导入评测历史、沿用旧候选自然日、提前宣称外部评审通过。**Deliverables：**候选身份与清单、启动/恢复入口、私有/公开材料边界、内部完成报告。

**Validation / Pass：**新候选无测试经历，源/状态/模型绑定完整，内部功能及质量门全过，可验证恢复。**Stop：**污染、无法恢复或尚有内部阻塞。**Remote Provider：**仅协议内获准的必要验证，不隐式新增。**Source Freeze：**冻结候选身份。**Unlock：**可报告当前 G6 对应的 build-scope complete / validation pending；不提前完成 G6-14，进入 P7。

### P7 — G6-12 External Review / G6-13 Real Days

**Goal / Why：**完成不能由开发者自评或加速时钟替代的产品证据。**Input：**P6 同一干净候选及冻结协议。

**Allowed / Forbidden：**具名独立盲评、至少3个不同 Asia/Tokyo 自然日期的真实用户使用、重启、模型切换和旧约定恢复；禁止伪造日期/独立性、将7–9月旧实例进度移入新候选。**Deliverables：**实际 reviewer 记录、完整判断、真实日期和实例谱系。

**Validation / Pass：**独立评审及真实跨日轨分别达到原标准，无未处置阻塞；3天只是该验收门，不等于长期稳定性的普遍证明。**Stop：**需要外部人或未来时间时如实 WAITING，不承诺回复结束后自主工作。**Remote Provider：**仅真实协议内调用。**Source Freeze：**候选不变；变更须评估影响并具名重验。**Unlock：**两轨合格后 P8。

### P8 — G6-14 Product Acceptance

**Goal / Why：**一次性核对全部门与候选一致性。**Input：**P6 内部门、P7 外部/真实时间证据及当前机器状态。

**Allowed / Forbidden：**具名最终 rollup 与后续受控激活决策；禁止只改 true 字段、掩盖未评项目、把发布提交等同验收。**Deliverables：**验收报告、最终矩阵、实例和版本、已知限制、实际激活状态。

**Validation / Pass：**当前版本所有必需门和外部/跨日证据满足，无未处置关键缺陷，数据可恢复且来源一致。**Stop：**任一证据冲突。**Remote Provider：**无隐含追加实验；有新验证须新登记。**Source Freeze：**最终候选保留。**Unlock：**才可标 `PRODUCT_ACCEPTANCE_COMPLETE`；生产激活仍需实际授权与成功回执。

## 28. Current Next Phase

推荐阶段为 `G6-07 Architecture Scope Reconciliation`，不是“继续提高 Trusted Admission Coverage”。本轮已完成只读裁决与文档交付部分；下一执行动作是 P1 的正式采用与精确合同落盘，之后才是获准的最小实现。

P1 必须明确保留 R6 的 typed proof / certificates / raw-accepted / immutable records，以及 R7 的 source-policy-consumer binding；迁移的只是它们被普遍用于展示前置条件的范围。

UNPARSED 处理合同：纯语义未覆盖且对话内容通过适用边界检查时，可正常表达但不得自动成为可信事实；涉及真实权限、执行、记忆、责任或完整性风险时，限制相应声明/效果；身份和绑定损坏仍 fail-closed。禁止简单将全部会话切 OFF 作为“修复”。

明确生成有限 consumer 表、176 项映射及成对正反例，再进入代码。旧 R15 保持停止；本轮不分配下一 revision 编号，也不把当前机器 blocker 静默改名。

## 29. Definition of Done

本轮 Done：有来源支持的使命恢复、范围裁决、实际代码与 R15 证据、当前源哈希核验、发现覆盖说明，以及完整38节文档交付。不是全盘穷尽、全部历史逐条审阅、源码修复或产品验收完成。

后续实现 Done：合同明确、实际代码存在、相应行为测试和原始证据通过、版本与状态一致、无隐藏失败、历史保留。文档、test count、commit 或局部 true 均不能单独构成 Done。[S05–S08]

## 30. BUILD_SCOPE_COMPLETE_VALIDATION_PENDING Criteria

这是内部工程完成、外部/真实时间证据尚待办的范围状态，不是整个产品最终成功。

当前 G6 至少需要：G6-07 的旧问题新源验证合格、G6-08 heldout、G6-09 全量82/328与原质量门合格、可靠运行/恢复/检索/准入有效、干净 Candidate V2 和可交付盲评/跨日材料、所有必需内部证据绑定当前版本。[S07]

然后才可设置该主线对应的 `GPT6_CORE_BUILD_COMPLETE_VALIDATION_PENDING` 及相关 build rollup；不得复制旧 Operations 的 `completion.build_scope_complete=true`。外部评审、真实自然日、产品验收与生产激活状态分别保留真实值。

## 31. Production Acceptance Criteria

当前版本内部 build 门通过，加上新候选真正独立评审、至少3个 Asia/Tokyo 真实自然日期的规定证据、同实例重启与连续性、长期相关检索/模型切换，以及所有预定质量和状态安全门通过，才能宣布产品验收完成。[S07]

无当前批次未解决的提交状态、无候选污染、无未处置关键缺陷。历史隔离 UNKNOWN 仍保留，不通过篡改历史使总数变成零。

`PRODUCT_ACCEPTANCE_COMPLETE`、用户允许激活、激活实际成功三者分开记录。当前三者不能从本文件推定为真。

## 32. New Session Startup Protocol

本文件安装并被采用后，作为首份产品治理入口；同时服从工具必须先加载的根/下级 `AGENTS.md`，不以“首读”绕过实际宿主规则。

随后读取当前 `GOAL_STATE.json`、`TASK_GRAPH.json`、`RECOVERY_CURSOR.json`、`VALIDATION_MATRIX.json` 和当前 recovery point。只有发现语义冲突或需要核验时才展开历史，避免每轮从头扫盘和重复所有审计。

执行 Scope Alignment Check：任务类别为 PRODUCT / INFRASTRUCTURE / VALIDATION / REPAIR / EXPERIMENT；写出保护的 state transition、Conversation 影响、Durable State 影响、validation scope 是否扩展及本轮读/写/远程权限。只执行依赖已满足且被授权的下一任务。

恢复时先查询既有副作用状态，不重复收费、重装 Genesis 或创建平行实例。工具不可用或工作区改变时报告实际错误，不冒充已执行。

## 33. Per-Session Execution Checklist

开始时确认工作区、有效用户要求、源/策略版本、当前任务、隔离 revision、在途调用以及精确允许写入范围。只读审计不得因为目录已有 modify 授权就写盘。

执行中每个改动绑定需求和状态迁移；原始失败留存；验证只做最短充分链路；没有新产品变化或新反证，不因证据报告追加重复整个 suite。

结束时区分实际读取、计算、修改、测试、模型调用、审阅与未完成项；报告精确恢复点。没有写回机器状态就明确说明，不能把回答中的计划冒充已保存任务。

## 34. Required Final Report

每次报告必须包含：实际范围与授权；已完成产物；源/策略/候选身份；真实测试和评审结果；调用提交/捕获/拒绝/UNKNOWN及费用边界；保留的失败；当前机器状态；明确未完成项；唯一下一安全动作。

审计报告额外回答原始目标是否改变、控制机制是否越过职责边界、建议是否已实现。本次结论为“正式验证路径存在范围漂移，需要两门分离”；不是“整个项目失效”，也不是“已经修好”。

本轮项目文件修改0、模型调用0、实验启动0；163成员哈希核验已完成；目录扫描和历史恢复的非穷尽范围在发现报告中明确列出。

## 35. Change-Control Protocol

`IMMUTABLE PRINCIPLE`：来源真实性、身份/实体隔离、模型不自授权、历史证据不可改写；普通会话不得改。

`FROZEN ARCHITECTURE DECISION`：经明确采用的职责边界、证据/权限合同和模式迁移规则；改变需新的 Architecture Reconciliation。

`CURRENT MACHINE STATE`：实际任务、源版本、停止原因、调用和验收结果；只有真实操作或回执支持时更新，不由愿望修改。

`ACTIVE PLAN`：依赖明确的后续路线；可在已授权范围内细化，不自动改变冻结原则和验收门。

`APPEND-ONLY HISTORY`：旧请求、输出、finding、verdict、冻结和决策谱系；追加说明，不覆盖。

文档改动若改变产品适用规则，是治理语义变化，不可伪装成纯排版。但也不应仅因报告或环境噪声变化使无关产品证据失效。单写者、影响范围审查及真实授权始终保留。[S05、S18]

## 36. Append-Only Decision Ledger

以下是本次交付的审计条目，尚未追加到本机 Decision Log；后续采用时以新 ID/时间记录，不冒充过去已执行。

| ID | 审计结论 | 来源及状态 |
|---|---|---|
| AR-20260920-01 | 早期使命是持续身份、受治理成长和可用交互；工程控制是手段 | S02、S05、S18；RECOVERED |
| AR-20260920-02 | G6-07 正式 TRUSTED 路径存在通用展示证明的范围冲突 | S07、S12–S16；AUDIT_JUDGMENT |
| AR-20260920-03 | 普通会话默认 OFF，不能把问题描述成全部生产输出已锁死 | S13、S14、S16；OBSERVED |
| AR-20260920-04 | 对话显示、发言观察、事实准入和事务提交分别治理 | S05、S16；RECOVERED + PROPOSED ROUTING |
| AR-20260920-05 | 保留 R6/R7 有效机制和全部 R12–R15 失败，禁止继承 PASS | S09–S17；RECOMMENDED |
| AR-20260920-06 | 双门、有限严格路径及 scope guard 纳入后续合同 | 本文 §§17–20、27–28；PROPOSED_CHANGE |
| AR-20260920-07 | 当前源163/163匹配、G6停止、自然日0、未激活 | S08、S20；OBSERVED_STATE |

## 37. Glossary

**Original Goal**：原始且仍有效的产品目标，不是最新一次失败自动生成的新目标。**Scope drift**：机制的适用范围或验收对象偏离产品职责；不等于所有新增机制错误。

**Conversation Layer**：处理当前交互、表达和有限上下文的职责层。**Trusted State Layer**：管理证据、准入及状态效果的职责层。**Conversation / Event / State**：原有三种不同记录，不能因两层划分而合并。

**Interpretation / Candidate**：解释或待核查提案，不自带事实权威。**Evidence**：支持某一精确范围的来源或回执。**TrustedAdmission**：现存有限类型语义准入组件。**AdmissionController**：现存事件准入控制器。**Durable**：经合法提交保存的状态，不表示数据库里出现的所有文本都为真。

**UNPARSED**：当前语义映射未覆盖；不同于“必然错误”“不能回答”或“允许写入”。**UNKNOWN**：必须按领域区分来源未知、语义未知和调用结果未知，不能混用恢复策略。

**Raw / Displayed / Accepted**：provider原件、实际展示和策略处理结果。现存 TRUSTED accepted 是有限证明路径的产物；新方案中的“可展示”不得自动继承“全部内容已证实”的含义。

**Source freeze / Validation revision / Candidate identity**：代码与治理版本、评测批次身份、运行实例身份；三者分别绑定。**Build-scope complete**：内部范围完成；不等于外部验收、真实跨日通过或生产激活。

**External44**：当前具名44轮/176项验证协议；名称含 external 不证明 reviewer 独立。**Historical finding**：必须保留的证据，不是无限扩项授权。**Canonical Guide**：采用后的首读治理索引，不是自动运行器、权限卡、模型能力证明或完成证书。


## 38. P1 Adoption Record — ADR-P1-20260920

采用时间：`2026-09-20T11:59:39.448227+00:00`。Task：`G6-07-ARCHITECTURE-RECONCILIATION-P1`。治理状态：`FROZEN_ARCHITECTURE_DECISION`；记录：**P1 architecture contract adopted**。本记录与具名 `FINAL_AUDIT.json` 的 P1 COMPLETE 共同构成采用回执，不是实现或产品通过证明。

本节是 §35/§36 下的追加记录，保留原有审计措辞、PROPOSED_CHANGE 标签和历史状态快照。对于本次采用的精确范围，以下 proposal 自本记录生效后转为 FROZEN_ARCHITECTURE_DECISION：§3 的 Conversation / Trusted State 职责分离；§7 的治理 Authority Ladder；§10 的机制适用范围；§14、§18–20、§28、AR-20260920-04/05/06 中的显示/观察/准入/提交分离、有限严格路径、consumer binding 和双门。未涉及的 P2–P8 实现与验证仍是后续计划，不继承通过。

规范合同：`persona_core/gpt6_optimization_v2/architecture_scope_reconciliation_20260920_01/`。主契约版本 `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`；冻结清单 `CONTRACT_FREEZE_MANIFEST.json`；采用决定 `ARCHITECTURE_DECISION.md`；显示/状态与 UNPARSED 合同、六级 Authority Ladder、14机制及14 consumer 矩阵、44轮176项原 ID/原措辞路由、双门、P2精确allowlist、迁移/回滚均以该目录具名文件为准。路由为44项 CONVERSATION_UTILITY、132项 BOTH、0项 N/A；未生成或评判新模型回答。

保留 R6 的有限类型证明/证书/raw-accepted/不可变记录与 R7 的来源、策略和consumer绑定；只收窄其作为所有对话展示前提的适用范围。UNPARSED 可在适用 display boundary 通过后保持 conversational authority；无证或禁止的状态效果仍 HOLD/REJECT。显示、事实支持、状态准入和提交不等价。新策略只用于以后显式建立的新隔离会话，不重解释历史。

R15仍为 PERMANENTLY_QUARANTINED：1/44 submitted、1/44 accepted、4/176 reviewed、3 PASS、1 FAIL、172 UNREVIEWED；raw semantic violation 未被独立确认，Conversation Utility / Over-conservatism 的真实失败保留。R12–R14 真实失败及所有历史 evidence/verdict/journal 不改写。

本次实际范围：只读恢复和治理合同落盘、append-only采用与当前P1进度更新；runtime修改0、Provider requests0、readiness0、external44 generation0、paid requests0。没有新revision、没有P2实现、没有G6-07 PASS。原§13/§28/§34是之前的审计快照；当前next phase以本追加记录及machine state为准。

当前状态：`G6_07_ARCHITECTURE_SCOPE_RECONCILED_IMPLEMENTATION_PENDING`；BLOCKER=`P2_MINIMAL_BOUNDARY_REPAIR_REQUIRED`；ACTIVE_TASK=`G6-07`；LAST_COMPLETED=`G6-06`；LAST_COMPLETED_INTERNAL_SUBTASK=`G6-07-P1-ARCHITECTURE-RECONCILIATION`；G6-08=`LOCKED`。唯一下一阶段：下一会话的 **P2 — Minimal Boundary Repair**，严格按精确allowlist并保持0 Provider调用；本会话在P1安全停止。恢复点：`persona_core/gpt6_optimization_v2/architecture_scope_reconciliation_20260920_01/FINAL_AUDIT.json`。
