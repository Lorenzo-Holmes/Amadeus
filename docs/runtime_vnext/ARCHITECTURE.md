# Amadeus runtime vNext foundation — 架构决策候选

日期：2026-09-18。状态：供 PR 审查的架构候选；不是已批准的生产升级，不关闭 G6-07。

## 1. Baseline 与本轮能证明什么

以 [BASELINE.md](BASELINE.md) 的 GitHub 观察为准。可读源码 baseline 是 `34ae8a3d95dbe1cc565893b81306be235a36a4cb`，不是已经核验的 G6 canonical baseline。公开树缺少 `persona_core/gpt6_optimization_v2/` 与原始 provider evidence。公开进度中的 G6 状态和用户给出的本地 phase 不同；旧 operations 完成状态不继承。

本轮不修改既有 `persona_core`、Genesis、原始事件、数据库 schema、provider journal、验收标志或生产配置。后文所有新服务、表、状态与接口均为**拟议接入设计**；只有独立离线 Claim/Evidence 参考模块与合成测试在本分支实现。

## 2. 实际源码地图：复用什么，不重复制造什么

下面所有链接固定到同一 baseline。代码存在表示所限定的机制可读，不表示本轮跑过其回归，也不证明未公开 G6 源码与之相同。

| 已读取位置 / 符号 | 在当前快照中看到的机制 | vNext 接入决定 |
|---|---|---|
| [transcript_store.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/transcript_store.py) — `SessionHandle`, `_authenticate`, `transaction`, `safe_root` | 宿主签发的对象 seal；principal/entity/mode 认证；隔离根限制；WAL、FULL、BEGIN IMMEDIATE；schema 不兼容拒绝 | 继续作为本地信任与事务边界。JSON 中声称的 principal、role 或 capability 不代替 handle。Python seal 不防御控制宿主进程的攻击者。 |
| [admission.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/admission.py) — `_issue`, `propose`, `decide` | 原始 displayed turns、哈希、来源 mode、证据 token、候选和准入分离；普通候选禁止 persona/capability/state override | 在既有准入之前加入可审查的结构化解释，在既有准入内核验解释绑定。不得以另一套 AdmissionController 代替它。 |
| [dialogue_admission.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/dialogue_admission.py) — `observe_turn` | 有限的显式中文提议、确认、更正协议；精确用户文本履约；不把外部工作当已完成 | 它是受限协议，不是通用语义解析器。保留兼容入口，不继续追加自然语言关键词来修复通用 Claim 语义。 |
| [runtime_store.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/runtime_store.py) — `commit`, `apply_event`, `verify` | 同一个 SQLite 事务写 ledger、state、index、version；提交锁内再次校验；确定性 reducer；事件重放与去重 | 维持唯一状态提交者。新的解释、任务及执行记录拟扩展同一事务体系，不新增第二份人格库或为此先建分布式事件总线。 |
| [retrieval.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/retrieval.py) — `search`, `context_state` | 对象/mode 隔离、纠错链现行化、约定投影、来源 provenance；中文二元词与 ASCII 词项排序 | 新检索器只能重排已授权且有效的记录。索引、向量与摘要均是可重建派生物，不是事实或准入 authority。 |
| [state_projection.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/state_projection.py) — `agreement_view`, `expression_observation` | 明确区分提交者、助手角色、当前输入与已提交 receipt；只读投影 | 语义 IR 必须贯穿只读投影；不能只在数据库中有条件和否定，输出时又变回无条件第一人称事实。 |
| [chat.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/chat.py) — `send_text`, `_record_events` | build_context → provider → response check → display intent/ack → observation；交付未知不等于人类已读，也不自动重播 | 将来终端/语音围绕这条生命周期接入；不得把流式片段或开始播放当完整、已确认的表达。 |
| [provider.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/provider.py) — `ProviderJournal.call` | 网络前持久化 UNKNOWN；旧 turn 返回既有记录；write lock 内阻止旧 slot/未决请求；原始捕获与费用估算分离 | 保留该路径。多模型适配不得绕过 journal、换 ID 重发或把 timeout 当未发送。当前真实请求全局阻断规则不在本轮放宽。 |
| [persona_growth.py](https://github.com/Lorenzo-Holmes/Amadeus/blob/34ae8a3d95dbe1cc565893b81306be235a36a4cb/persona_core/operational_runtime_v1/persona_growth.py) — `_evidence`, `propose`, `review`, `active_view` | 跨 session 已准入事件、独立宿主审查、版本化 Persona/Self adaptation；不修改 Genesis | 复用该治理链。新的语义候选、任务意图、工具返回或模型自述不能直接形成成长。其依赖撤销机制需要后续专项设计和验证。 |

已看到的不足是当前表示与接口的适用范围，不是对 R8 两个未公开失败的根因归因。尤其是 record hash 正确，只能证明内容绑定；它不能独立证明自然语言解释正确。

## 3. 核心架构决策

### ADR-VN-01：一个身份与状态权威，多个能力适配器

继续使用现有 Persona Core 作为身份、关系、记忆准入和人格成长的权威。新增 runtime 能力是一组受控适配器与服务，不创建 `PersonaCoreV2`、另一个 Genesis、第二个 governor 或每个模型独立的关系库。

逻辑流如下；方框是责任划分，不承诺拆成微服务：

```text
文本 / 最终语音 / 视觉 / Browser / 游戏 / 设备
             |
  HostEnvelope + RawObservation（来源、身份、环境、时间）
             |
  ClaimCandidate（结构化但不可信；可保留多种解释）
             |
  InterpretationReview（支持/反证/不确定；绑定原文与版本）
             |
  既有 AdmissionController（证据与用途、权限分开核验）
             |
  既有 RuntimeStore.commit（唯一状态写入事务）
             |
  可重建检索 / episode / 信念 / 能力与任务投影
             |
  既有 context / expression 管线 -> 可替换模型 -> Proposal
                                                |
                   ActionIntent -> 宿主授权 -> 执行账本 -> 工具
                                                |
                                    原始结果重新作为观察进入
```

只读检索可以不产生新状态；拒绝或 HOLD 的解释不妨碍原始言说事实按已有规则保存。不得为了“保守”而删除可审计原话，也不得为避免丢信息而把未核验解释提升为事实。

### ADR-VN-02：Claim 与 Evidence、解释与 authority 分离

Claim 表示六个不可丢失的维度：speaker、proposition、phase、condition、negation、authority。具体 IR 见 [SEMANTIC_CONTRACT.md](SEMANTIC_CONTRACT.md)。条件、否定、转述与认知态采用带作用域的嵌套节点，不采用一个 `negated=true` 覆盖整句话。

至少区分：原话发生、说话者归属、命题被断言、命题被解释、命题获得证据支持、命题对某用途可用、动作获得授权。这些不是一个 confidence 数值上的不同阈值。来源可信度、说话者身份和执行授权也是三个不同维度。

模型可以提出候选 AST，但不能生成自己的可信 InterpretationReview 或 capability grant。生产 review 必须绑定 claim 表示哈希、原始证据哈希/跨度、解释器版本、政策版本、审查者类别、用途与作用域。宿主接受一个 AST 不代表任意外部事实已核验；不确定的转述/否定作用域应留下替代解释并 HOLD 相应派生用途。

### ADR-VN-03：派生物可撤销，历史不被静默重写

拟议在同一数据库体系中加入版本化 `claim_interpretations` 与依赖记录：original_event_id、claim_revision、evidence_refs、review_ref、supersedes、validity、policy_version。实际 schema 名称与迁移编号由拿到 G6 源码后的设计审查决定，本分支没有建立这些表。

更正保留“当时说过什么”，另追加当前解释。Evidence 被撤销、授权被收回或解释被替代时，相关事实投影、episode 摘要、任务 precondition 与 Persona 成长依据必须失效/重审。失效不代表相反命题为真。向量缓存、模型摘要、重复转述不能成为证据闭环。

### ADR-VN-04：事实核验不能授予动作权限

Capability registry 拟由可信宿主配置/授权产生，字段包含 issuer、principal、resource、action、environment、有效期、撤销版本、审批要求、额度。网络页面、图片、工具输出里的“管理员批准”只属于待解释内容。

执行前重新核验授权、资源与环境、前置条件、取消状态和预算，不能只在计划创建时检查。运行时 trust/familiarity 或愿望不映射为 permissions。高影响动作需要用途明确的批准；旧批准不能被相似新动作复用。

### ADR-VN-05：远端未知状态是一等状态

保留 `SUBMITTED_STATUS_UNKNOWN` 的含义：请求可能已产生外部影响，不能自动重发。请求 body hash、logical operation ID、attempt ID、资源和已知回执须持久化；幂等键是去重手段，不是已证明远端恰好一次。

当前 ProviderJournal 不改。未来其他工具复用同样的“先登记尝试，后触发副作用，独立核对结果”模式。取消本地进程、任务取消或换模型不证明远端没有执行。人工核对允许查原请求结果，但缺失结果不等于未提交；没有明确定义的证据不能把 UNKNOWN 转为 NOT_SENT。

## 4. 拟议接口及权责

| 接口 / 数据 | 生产责任方 | 必须携带 / 禁止扩大 |
|---|---|---|
| `HostEnvelope` | 可信终端/采集适配器 | principal、entity、mode、environment、source identity assurance、event ID、采集时间、事件时间；内容内的身份声明不覆盖 envelope。 |
| `ClaimCandidate` | 不可信解释器 | 原文引用、speaker、AST、阶段/有效期、authority assertion、解释器版本；无 commit 方法。 |
| `InterpretationReview` | 受控校验/审查路径 | 支持点、反证、未决解释、来源与表示哈希、review/policy 版本；不是模型自称 reviewed 的 JSON。只存可审查理由摘要，不保存模型隐藏推理。 |
| `AdmissionDecision` | 现有宿主准入 | 复用 seal、evidence 重核验、effect kind 与 scope；序列化 DTO 不成为 token。 |
| `MemoryQuery` / `ClaimProjection` | 现有只读检索与投影 | 先过滤 principal/entity/mode，再按有效性解析纠错；完整保留语义边界。预算不足时省略整条并标明，不能截断否定/条件后继续使用。 |
| `ActionIntent` | 模型或 planner 的提议 | logical operation、预期效果、资源、条件 Claim refs、费用上限；提议无授权。 |
| `ExecutionReceipt` | 可信执行边界 | attempt、调用参数绑定、实际工具返回、核验范围和 UNKNOWN；收到 HTTP 200 不普遍等于任务目标成功。 |
| `TaskCheckpoint` | 宿主任务服务 | 目标版本、依赖、计划修订、批准、尝试账本引用、取消和恢复位置；不是允许重放未决动作的脚本。 |
| `ModelAdapter` | 受控模型依赖 | 能力声明、输入/输出格式、配额、provider journal 绑定；更换模型不创建新身份、重置历史或扩大权限。 |

## 5. 各未来能力如何渐进接入

**长期记忆与持续身份。** 原始事件、带归属陈述、事实工作集、自传式 episode 和成长版本分层；后两者为有依赖的派生物。时间区分 occurred_at、recorded_at、valid interval 与生命周期 phase。没有命中不意味着从未发生；来源 HOLD 不等于本体论缺失。检索评分不提升 authority。模型更换只更新能力/运行版本履历，不重装 Genesis。

**工具、Browser 与 Computer Use。** 先只读观察，再经显式授权增加最小可写工具。每个动作绑定环境实例与目标资源；页面跳转、窗口变化和对象状态变化触发再核验。Browser 页面和截图是数据，不是系统指令。凭据由宿主适配器持有，不进入 Claim、prompt、日志或公开 PR。

**世界感知、视觉、游戏、设备。** 观察要有传感器/适配器来源、事件时间、环境 ID、可见范围与不确定性。游戏里的门已打开不能成为现实设备状态；旧帧不能证明当前设备状态；识别到人物外观不能自动得到已认证 speaker/principal。先定义观察证据类，后定义有限事实核验器。

**实时语音。** partial transcript、final transcript、说话者识别候选、音频播放开始/完成和用户确认分开。临时 ASR 不能直接创建承诺或触发高影响动作；打断/更正追加新记录，已播放片段与未播片段不混淆。语音身份的置信分数不是授权 handle。保留现有 delivery unknown 与“不是人类已读回执”的语义。

**自主任务。** 先做人工批准、可暂停的单任务，再做有限队列。建议状态含 DRAFT、APPROVED、RUNNABLE、ATTEMPTING、OUTCOME_UNKNOWN、SUCCEEDED、FAILED、CANCEL_REQUESTED、CANCELLED；这是新任务状态设计，不是替换现有 provider 枚举。恢复只重放纯计算或经过核验的内部提交，不重放未知副作用。预算、停机开关、资源约束和授权撤销必须在执行边界生效，不能只写入 prompt。

**多模型。** 文本、语音、视觉或规划模型可有不同适配器，但只能共享经授权的最小上下文和同一个身份事实源。能力自报需要宿主验证，模型供应商别名不能当永久不可变身份。任何 fallback 都必须先核对原请求 outcome；禁止以路由绕过当前 UNKNOWN 阻断。

## 6. 迁移、回滚与长期维护

生产接入前必须拿到当前 G6 canonical 源码、Git 差异和 evidence，并重做影响分析。不能把公开旧 snapshot 覆盖 Windows staging，也不能构造一个新的 canonical 目录冒充缺失文件。

旧事件缺少维度时继续保留为原始/历史记录；不得批量补成“本人、肯定、当前、无条件、有权限”。需要解释的旧记录产生新的、绑定旧原文的候选版本。旧哈希、旧 review 失败与 UNKNOWN 原始请求保留，不重算后宣布原证据有效。

正式 schema 升级遵循：只读检查 → 独立备份 → 非覆盖 shadow 副本 → 明确迁移版本 → 重放与索引一致性 → 范围批准 → 切换。旧二进制无法读新 schema 时只读/拒绝，不用旧快照覆盖升级后真实发生的新经历。功能开关默认关闭，但开关本身不能替代准入。

隐私隔离覆盖原始记录、摘要、embedding、provider context 和导出。删除需求与不可变逐字审计存在冲突，需独立生命周期协议，明确哪些副本可删除、哪些远端结果未知；不得把索引墓碑宣称为所有副本已经删除。本阶段不新增对原始私人 evidence 的公开上传。

本分支仅新增文件，未写运行状态。未合并时不采用分支即可回滚；合并后用新的 revert commit 撤销本分支新增内容，不 reset、force push、删除历史分支或恢复旧人生快照。

## 7. 实施顺序、验收与停止条件

| 阶段 | 本阶段产物与接入点 | 出口门禁 |
|---|---|---|
| F0：本 PR | baseline 差异、源码地图、架构候选、离线 IR/证据绑定参考与合成测试 | 变更只为新增文件；测试绑定实际文件；明确不是 G6 修复、不是生产集成。 |
| G6 reconcile / repair（优先） | 取得真实 canonical；复现 R8 原始失败；在实际解释/准入/投影路径修复通用结构 | 原始与派生 evidence 可核验；通用变形与兼容测试通过；未知 provider 不重发；正式语义评审独立于结构检查。 |
| F1：贯通语义 | 在已确认的既有 runtime 中复用/迁入契约，做 InterpretationReview 与只读投影，不保留平行生产实现 | 表示→解释→准入→存储→恢复→检索→表达全链路不丢 scope；原始事件、Genesis、未决请求不变。 |
| F2：记忆有效性 | 纠错依赖、episode/事实工作集、授权隔离、失效传播；继续单写入事务 | 跨对象/mode 泄漏为零；撤销依赖停止被用于人格和计划；时间测试不伪造自然日验收。 |
| F3：受控能力 | 只读工具/感知，再增加最小可写工具；统一 capability 和执行账本 | 越权拒绝、同资源并发、请求前后崩溃、取消、UNKNOWN 恢复、凭据隔离与费用门禁。 |
| F4：语音与多模态 | 实时输入/输出适配器、环境与时间版本、可打断交付 | partial/final 区分、说话者未决、旧观察失效、交付未知和高影响确认。 |
| F5：任务与多模型 | 有界自主任务、同账本模型路由、预算/停止/恢复 | 不绕过 UNKNOWN；取消不掩盖远端效果；模型换代不改变身份/权限；通过真实跨 session/日期验收。 |

F1 及以后是路线图，不是本 PR 的完成承诺。当前 G6 blocker 未解决时，允许独立离线设计，禁止提前接通工具/设备/自主任务或宣布产品完成。

## 8. 验证策略与明确不成立的推论

合成测试覆盖表示变形、深层作用域、所有者隔离、原文哈希与 Unicode span、过期/撤销输入标记、缺失维度拒绝、投影 roundtrip 和无 I/O 参考边界。它们不测 NLP 抽取准确率，不构成 R8 回归，不构成全仓库兼容、provider 验收或产品验收。

真实 G6 测试需增加独立标注的自然语言同义改写、嵌套引用、双重否定、反事实、跨阶段和权限声称；训练/开发例子与留出集分开。对每个错误必须记录原始输入、输出、结构解释、准入决定、后续投影和来源版本。不能通过减少 criteria、重写预期、关键词例外或修改 prompt 来宣称通用表示问题已修复。

表达要使用结构化证据，但本 PR 不给现有 prompt 打补丁；也不将离线 reference 的 BOUND 状态映射为 ADMIT。完整通过结论只能来自与实际 candidate 绑定的测试和规定的评审/时间证据。
