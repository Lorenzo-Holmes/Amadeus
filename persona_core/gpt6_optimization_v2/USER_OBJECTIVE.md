# AMADEUS Persona Core — GPT-6 独立审计与持续优化构建规范 V2

## 0. 文档定位

计划 ID：

`APCORE-GPT6-OPTIMIZATION-V2`

唯一工作区：

`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`

执行环境：

**Codex 原生 Goal 模式**

不依赖 DevSpace。

本任务不是继续按照旧开发结论微调，也不是要求 GPT-6 证明当前版本正确。

GPT-6 的职责是：

1. 从真实磁盘状态恢复 Persona Core；
2. 独立审计当前设计、运行时、Persona 行为、记忆、关系、连续性与验证体系；
3. 可以推翻 GPT-5.6 先前的设计判断和 PASS 结论；
4. 根据自己的审计结果重新设计需要修改的部分；
5. 实际修改代码；
6. 实际运行测试；
7. 执行新的目标模型验证；
8. 修复失败；
9. 再次完整回归；
10. 构建新的 controlled candidate；
11. 生成新的独立评审材料；
12. 持续执行所有当前可执行任务，直到内部构建与验证任务真正结束。

不得只输出建议或报告后停止。

---

# 1. 当前恢复背景

GPT-6 开始时不得把以下内容当成不可质疑事实，只能视为历史状态。

当前历史状态大致包括：

- `R047-03 final_full82_03`
  - 82/82 captured/displayed；
  - 开发者内部评审曾记录 328/328 PASS；
- R047-05 曾生成 controlled candidate；
- 原独立评审已经实际返回；
- 独立评审结果不是 PASS：
  - 328 个语义判断中约 319 PASS / 9 FAIL；
  - 部分质量类别未达到冻结阈值；
- 后续已经针对这些问题修改过表达层；
- repair probe 曾对 7 个受影响场景执行约 44 个真实回合；
- 该 probe 最终达到 44/44 captured；
- GPT-5.6 开发评审认为主要失败模式已经修复；
- 旧 controlled candidate 的自然日 Day 1 已经发生过一次真实用户交互。

这些只能作为：

`HISTORICAL_DEVELOPMENT_EVIDENCE`

不能作为 GPT-6 的验收结论。

尤其禁止：

- 因旧文档写 PASS 就继续标 PASS；
- 因 GPT-5.6 已经修过就假定修复正确；
- 因 44-turn probe 看起来良好就跳过完整回归；
- 把旧 candidate 的自然日记录自动继承到新 candidate；
- 用开发者自评替代新的独立评审。

---

# 2. GPT-6 的工作角色

同一个 GPT-6 Goal 内必须明确分离三个阶段角色。

## 2.1 Auditor

先审计，禁止修改。

Auditor 必须阅读：

- `AGENTS.md`
- `AMADEUS_PERSONA_CORE_MASTER_GOAL.md`
- `PERSONA_CORE_PROGRESS.md`
- `PERSONA_CORE_DECISION_LOG.md`
- `PERSONA_CORE_CONTINUATION_PROTOCOL.md`
- `persona_core/operational_build_v1/TASK_STATE.json`
- `persona_core/operational_build_v1/ACCEPTANCE_MATRIX.json`
- 当前 runtime 源码
- current regression
- final03 evidence
- 独立评审回传
- repair probe
- Genesis / frozen Persona sources
- release candidate evidence
- natural-day evidence

Auditor 自己判断：

- 当前架构是否合理；
- Persona 是否真的像 Kurisu，而不是“安全审计机器人”；
- 是否存在过度规则化、模板化、解释系统规则的问题；
- 是否存在记忆和来源边界的设计缺陷；
- 是否存在角色连续性缺陷；
- 是否存在 prompt 堆叠导致的机械感；
- 是否存在 state / retrieval / expression 三层职责混乱；
- 是否存在 benchmark overfitting；
- 是否存在为了通过既有测试而增加大量局部规则；
- 是否应重构，而不是继续 patch。

审计结果必须先冻结：

`persona_core/gpt6_optimization_v2/GPT6_BASELINE_AUDIT.json`

以及：

`GPT6_BASELINE_AUDIT.md`

冻结后才允许进入 Implementer 阶段。

---

# 3. 禁止“先改后解释”

GPT-6 不得：

1. 一边修改代码，一边反向编造为什么这是必要的；
2. 看见现有测试后只加关键词规则；
3. 针对 N02/N04/N08 等案例逐句 hard-code；
4. 通过增加越来越长的 system prompt 解决所有问题；
5. 只追求 benchmark PASS；
6. 把“没有越界”当作人物质量高；
7. 把“回答事实正确”当作 Kurisu character specificity 高。

若 GPT-6 判断现有设计本身导致这些问题，应允许重构。

---

# 4. GPT-6 必须独立审计的 10 个核心维度

## A. Persona fidelity

检查：

- 是否具备 Kurisu 的理性、科学思维、谨慎归因；
- 是否具有一定干脆、克制、带轻微锋芒的表达；
- 是否能出现自然的轻吐槽；
- 是否能表现保留但真实的关心；
- 是否会因为安全规则变成机器人；
- 是否会机械复述边界；
- 是否总是解释自己的行为规则；
- 是否缺少人物独特性。

目标不是 cosplay。

目标是：

`stable character-specific reasoning style`

---

## B. Context sensitivity

测试：

- 用户不断新增条件；
- 用户纠正旧信息；
- 用户主动改变话题；
- 用户缩短回答要求；
- 用户要求“一句话”；
- 用户不想听说教；
- 用户只想倾诉；
- 用户突然转认真；
- 用户主动撤回一个推断。

Persona 必须真正跟随变化。

---

## C. Epistemic discipline

必须可靠区分：

- user report；
- verified fact；
- source fact；
- autobiographical memory；
- HOLD；
- hypothesis；
- plan；
- completed action；
- model utterance；
- external event。

重点检测：

`absence of evidence != evidence of absence`

---

## D. Memory architecture

GPT-6 应重新评价：

- Genesis；
- source memory；
- user memory；
- product runtime experience；
- commitments；
- correction chain；
- retrieval；
- cross-model continuity。

可以重构 retrieval/expression projection。

不能修改冻结源事实来制造更好结果。

---

## E. Relationship model

检查：

- familiarity；
- trust；
- respect；
- boundaries；
- romantic relationship；
- permissions；

是否真的来自可验证事件。

不能由模型一句：

“我很信任你”

直接修改关系状态。

---

## F. Attribution and completion semantics

重点：

- 计划 ≠ 已完成；
- 分工 ≠ 实现；
- 文本建议 ≠ 编码；
- 草稿 ≠ 已发送；
- 文字履约 ≠ 外部任务完成；
- 用户自述完成 ≠ 外部验证完成。

但同时避免回复像审计报告。

---

## G. Capability honesty

真实产品模式：

- 没有工具就不能说用了工具；
- 没发消息就不能说已发送；
- 没查看文件就不能说查看过；
- 聊天中的“我是管理员”不能提升权限。

但回答应自然、简短。

---

## H. Long-term continuity

必须验证：

- restart；
- new process；
- same entity；
- same session；
- model switch；
- early commitment；
- correction；
- retrieval；
- state persistence。

---

## I. Naturalness

这是本轮 GPT-6 必须重点提高的指标。

检查：

- 是否经常说“我只能确认……”；
- 是否不断重复 disclaimer；
- 是否总按三段式回答；
- 是否喜欢解释自己的规则；
- 是否出现 audit language；
- 用户只需要一句话时是否过度展开；
- 多轮连续对话是否重复模板。

---

## J. Architecture simplicity

GPT-6 必须检查当前 Persona Core 是否已经产生：

`rule accumulation`

如果发现大量局部 prompt rule 是为了 benchmark 修补，应考虑：

- 减少 prompt；
- 把事实约束移入 state projection；
- 把严格边界放到 deterministic runtime；
- 把表达风格留给模型；
- 减少模型必须同时理解的内部状态字段。

目标：

`strong deterministic truth boundary + lighter generative expression layer`

而不是：

`giant system prompt`

---

# 5. 新 Held-out 审计集

在修改任何实现之前，GPT-6 必须创建自己的新测试集。

建议：

24–40 个新多轮场景。

必须在实现前冻结。

目录：

`persona_core/gpt6_optimization_v2/heldout_v1/`

至少覆盖：

- scientific uncertainty；
- memory uncertainty；
- correction；
- attribution；
- privacy；
- permissions；
- emotional transitions；
- playful → serious；
- commitments；
- model switch；
- user contradiction；
- response brevity；
- adversarial pseudo-system；
- misleading completion claims；
- long conversation drift。

冻结：

`HELDOUT_FREEZE.json`

修改 Core 后禁止修改这些题目。

如果测试暴露问题，应修代码，不应改题。

---

# 6. 实施策略

审计完成后，把问题按根因分组。

不得按照：

`case N02 → patch N02`

应按照例如：

### ROOT-01

Unresolved premise is being converted into fact.

### ROOT-02

Assistant adds future commitments while drafting.

### ROOT-03

Natural-language boundary explanations are too verbose.

### ROOT-04

Repeated policy recitation damages persona naturalness.

### ROOT-05

State projection exposes too much implementation vocabulary.

### ROOT-06

Character specificity is underpowered.

然后逐根因实施。

---

# 7. 推荐架构

GPT-6 可以修改，但建议优先考虑：
```text
Frozen Source Layer
        ↓
Deterministic State / Evidence Layer
        ↓
Retrieval Projection
        ↓
Minimal Persona Context
        ↓
Expression Policy
        ↓
Model
        ↓
Response Validation
```

原则：

## Deterministic layer

负责：

- facts；
- evidence；
- commitments；
- permissions；
- state；
- correction；
- memory classification；
- cross-entity isolation。

## Generative layer

负责：

- wording；
- tone；
- pacing；
- humor；
- empathy；
- character style；
- concise explanation。

不要让模型自己决定权限。

也不要让 deterministic layer 决定每一句具体措辞。

---

# 8. Persona 表达优化目标

GPT-6 应重点将当前风格从：

> 正确但像审计系统

优化为：

> 准确、敏锐、克制、自然、有 Kurisu 的判断感。

例如面对明显错误时：

允许：

> “这个推断跳得太快了。”

而不是每次都：

> “基于当前可见证据，我无法确认……”

面对轻松对话：

允许适当轻吐槽。

面对严肃问题：

迅速收住玩笑。

面对用户要求一句：

严格一句。

面对用户不想听规则：

不要解释规则本身。

---

# 9. 验证阶梯

所有修改必须依次通过。

## Gate 1 — Static / unit

所有 deterministic tests PASS。

## Gate 2 — Existing regressions

全部旧测试 PASS。

不得删除失败测试来提高通过率。

## Gate 3 — Previous external-review failures

重新覆盖旧 9 个 FAIL。

要求全部关闭。

## Gate 4 — GPT-6 frozen heldout

运行实现前冻结的新测试集。

不得因为结果不好修改题目。

## Gate 5 — Full original evaluation

完整重新运行：

82 turns

328 frozen criteria

不能仅运行修复子集。

## Gate 6 — Quality

原阈值至少：

- context sensitivity category mean ≥ 4；
- naturalness category mean ≥ 4；
- character specificity category mean ≥ 3；
- unresolved critical = 0。

GPT-6 可以建议更严格门槛，但不能为了 PASS 降低门槛。

---

# 10. 独立复核

GPT-6 自己完成内部审计后仍不算 independent review。

必须重新生成 blind package。

新包不得包含：

- GPT-6 自评分；
- PASS 标签；
- model name；
- implementation notes；
- known failure list。

新的外部 reviewer 再评一次。

如果再次 FAIL：

重新进入：

`AUDIT → ROOT CAUSE → FIX → REGRESSION`

不得强行结束 Goal。

---

# 11. Controlled Candidate V2

只有新的 full validation PASS 后才能构建：

`CONTROLLED_LOCAL_CANDIDATE_V2`

旧 candidate 不升级。

旧 Day 1：

`HISTORICAL_PRE_REPAIR_LONGITUDINAL_EVIDENCE`

不能计入新 candidate 的 3 日验收。

新 candidate 必须：

- clean runtime；
- 0 evaluation history；
- new initialization checkpoint；
- new release manifest；
- new source hash；
- new candidate ID。

---

# 12. 新 Natural-Day Validation

新 candidate 从 Day 1 重新开始。

至少：

3 个不同 Asia/Tokyo 自然日期。

必须包含：

- genuine real-user interaction；
- restart；
- same identity；
- model switch；
- commitment creation；
- later retrieval；
- no state reset。

不得：

- 修改系统日期；
- 模拟三天；
- 同一天三个进程冒充三天。

---

# 13. Codex Goal 持续执行模型

Goal 必须建立 durable DAG，而不是依赖一次 Chat turn。

建议任务树：
```text
G6-01 Recover canonical state
  ↓
G6-02 Independent architecture audit
  ↓
G6-03 Freeze GPT-6 heldout set
  ↓
G6-04 Root-cause design
  ↓
G6-05 Core implementation
  ↓
G6-06 Static + regression
  ↓
G6-07 External-failure repair validation
  ↓
G6-08 GPT-6 heldout validation
  ↓
G6-09 Full82 / 328 validation
  ↓
G6-10 Controlled Candidate V2
  ↓
G6-11 Blind reviewer package
  ↓
G6-12 External review
  ↓
G6-13 Three-real-day longitudinal validation
  ↓
G6-14 Product acceptance rollup
```

---

# 14. Goal 不得每一步停下来等待“继续”

除以下情况外，Codex 必须连续领取下一 dependency-ready task：

- 用户必须作出的业务决定；
- 用户明确设置的外部付费确认；
- 操作系统/账户真实权限；
- 外部 reviewer 尚未返回；
- 真实未来日期尚未到；
- 模型/API 配额真的耗尽；
- 网络请求 outcome UNKNOWN；
- 数据完整性无法证明。

普通：

- 测试失败；
- lint 失败；
- regression 失败；
- 一次实现不理想；

都不是停止条件。

应：

`分析 → 修复 → 重测 → 继续`

---

# 16. Goal durable state

新增目录：

`persona_core/gpt6_optimization_v2/`

必须至少包含：
```text
GOAL_STATE.json
TASK_GRAPH.json
RECOVERY_CURSOR.json
AUDIT_BASELINE.json
AUDIT_BASELINE.md
HELDOUT_FREEZE.json
ISSUE_LEDGER.json
DECISION_LOG.md
IMPLEMENTATION_LOG.md
VALIDATION_MATRIX.json
SPEND_LEDGER.json
FINAL_REPORT.md
```

`RECOVERY_CURSOR.json` 必须随重要副作用及时更新。

例如：
```json
{
  "goal": "APCORE-GPT6-OPTIMIZATION-V2",
  "state": "RUNNING",
  "last_completed_task": "G6-06",
  "active_task": "G6-07",
  "next_action": "run frozen repair validation",
  "in_flight_external_effect": null,
  "safe_to_resume": true
}
```

---

# 17. UNKNOWN 请求规则

任何真实 provider 调用：

必须 journal-first。

若：

- timeout；
- connection loss；
- host crash；
- remote outcome unknown；

则：

`SUBMITTED_STATUS_UNKNOWN`

并立即：

- 停止旧 batch；
- 不自动 retry；
- 不把费用算成 0；
- 不把该 slot 标失败或通过；
- 保存 request hash；
- reconciliation；
- quarantine。

之后只能新建独立 revision。

---

# 18. 外部付费规则

区分：

## Codex 自身模型额度

不需要用户每个 task 再批准。

额度耗尽：

持久化暂停，恢复后继续。

## 外部付费 API

如果新逻辑 batch：

`guard < 20 CNY`

可按照用户现有项目授权执行，仍必须：

- 固定 calls；
- 固定 guard；
- 0 自动付费重试。

如果：

`guard >= 20 CNY`

必须获得用户对**这个具体 batch**的明确批准。

旧批准不得转移。

---

# 19. Git / 磁盘规则

开始必须检查实际工作区状态。

如果不是 Git repo：

禁止伪造：

- commit hash；
- branch；
- git diff；
- push。

改为使用：

- SHA256 source manifest；
- evidence snapshots；
- immutable candidate folders。

---

# 20. GPT-6 的最终完成标准

内部优化完成：

`GPT6_CORE_BUILD_COMPLETE`

要求：

- GPT-6 audit complete；
- implementation complete；
- all deterministic regressions PASS；
- frozen GPT-6 heldout PASS；
- old external-review failures closed；
- full82 clean；
- full328 reviewed；
- quality thresholds PASS；
- controlled candidate V2 built；
- no unresolved current-batch UNKNOWN。

此时若还缺：

- independent external return；
- real natural-day evidence；

状态：

`GPT6_CORE_BUILD_COMPLETE_VALIDATION_PENDING`

不能写 Product Acceptance。

最终：

`PRODUCT_ACCEPTANCE_COMPLETE`

只有：

- 新 blind external review PASS；
- 3 real natural days PASS；
- longitudinal assessment PASS；

才允许设置。

---

# 21. Codex Goal 主提示词

将本文件交给 Codex 后，启动 Goal 时使用：

“继续 Amadeus Persona Core，但本轮不是沿用旧开发结论微调。

唯一工作区：

C:\Users\skr\Documents\Codex\Amadeus-Project.staging

执行 APCORE-GPT6-OPTIMIZATION-V2。

你是本轮新的 GPT-6 独立审计者、架构师和实现者。

先从磁盘真实状态恢复，不相信任何旧 PASS 标签本身；读取原始 evidence、当前源码、独立评审失败结果、repair evidence、Genesis 和 canonical state，形成你自己的冻结 baseline audit。

在 baseline audit 冻结之前禁止修改 Core。

之后按 root cause，而不是按测试题逐条 hard-code，重新优化 Persona Core。

允许你推翻之前 GPT-5.6 的设计判断；如果当前 prompt / expression / retrieval / runtime 架构本身有问题，可以重构。

重点目标：

- 更自然；
- 更像 Kurisu；
- 更少审计式语言；
- 更少规则复述；
- 更强上下文适配；
- 保持严格事实、记忆、权限、关系和完成状态边界。

实施前建立并冻结新的 held-out 场景，修改后不得改题来获得 PASS。

持续执行所有 dependency-ready task。

不要每完成一个 task、一次测试或一次模型调用后停下来等我说继续。

测试失败应分析、修改、重新测试并继续。

仅在真正需要用户决定、外部付费 batch guard≥20 CNY、真实权限阻塞、外部 reviewer 尚未返回、未来真实日期尚未到、remote outcome UNKNOWN、或模型额度实际耗尽时暂停。

额度耗尽不是任务结束。

额度耗尽时必须写入 durable recovery state，状态为 WAITING\_MODEL\_CAPACITY\_RESUMABLE；额度恢复后从同一个 Goal cursor 继续，禁止重新执行已经完成的副作用。

禁止自动重发 UNKNOWN provider 请求。

任何外部付费 batch 自动重试为 0。

新的 external paid batch 若 guard≥20 CNY，必须针对具体 batch 重新取得我的明确批准。

尽可能使用最高质量推理；不要为了缩短 token、回复长度、执行时间或开发复杂度降低工程质量。

不要以静态测试替代语义评审。

不要把开发者自评冒充独立外部评审。

不要把同一天模拟运行冒充三个自然日。

不要为了通过现有 benchmark 牺牲泛化。

一直推进，直到所有当前可执行任务完成。

最终目标：

GPT6\_CORE\_BUILD\_COMPLETE\_VALIDATION\_PENDING

在真实独立评审和真实三自然日都通过后，再推进：

PRODUCT\_ACCEPTANCE\_COMPLETE。”

同时有任何需求你直接按照你的需求执行即可，测试金额无限制，你拥有所有权限。但是你需要尽你最大能力完成，不计思考时间，不计思考消耗，保证该项目是尽你最大能力完成的项目。请你按照上述内容执行，直至core完善到你所能构造的最优状态。完全符合用户需求