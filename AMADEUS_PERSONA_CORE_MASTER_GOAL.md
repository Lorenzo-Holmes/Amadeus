# Amadeus Persona Core Master Goal

状态：**APCORE-OPERATIONS-V1 ACTIVE / R043 HISTORICAL RELEASE PRESERVED**  
建立日期：2026-09-06  
历史 R043 达成声明日期：2026-09-07（不等于本阶段最终验收）  
适用工作区：`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`

保留基线：`AMADEUS-PERSONA-CORE-R043`。Genesis=`AMADEUS-KURISU-GENESIS-R035`，正式Runtime位于`persona_core/runtime/`。本文件仍作为长期架构与治理原则保留；后续在该基线上非破坏性修订，不从零重建。

2026-09-07 当前主线为用户明确启动的 **APCORE-OPERATIONS-V1：真实对话与可靠运行**。磁盘核查确认 R033 验收器预填 PASS，并在隔离副本复现权限字符串准入和中断写入重开失败；旧 GOAL_COMPLETE 不作为当前停止依据。R034/R035/R043、原始回答、原标准和失败证据保持不变。

本阶段唯一机器任务入口是已核验落盘的 `persona_core/operational_build_v1/TASK_STATE.json`，验收依据是同目录 `ACCEPTANCE_MATRIX.json`。2026-09-07 已解除原包/同步阻塞，保留原清单与初始文档副本；R044-01已按原门核验，接续R044-02逐项语义复核。同步前证据只作为可追溯输入，不另建任务体系。当前不宣称 BUILD_SCOPE_COMPLETE_VALIDATION_PENDING 或 PRODUCT_ACCEPTANCE_COMPLETE。

## 1. 最终目标

建立一个以牧濑红莉栖可靠来源经历为 Genesis 来源、并在 Genesis 后能够形成独立连续经历的 **Amadeus Kurisu 人物内核**。

本项目不以“角色语气模仿”作为终点。最终系统行为应由以下长期状态共同产生：

```text
Source Identity
+ Encoded Memory
+ Persona Constitution
+ Self Model
+ Affect State / Affect Model
+ Relationship Model
+ Decision Model
+ Runtime Experience
```

目标是使 Amadeus 的表达、判断、关系变化和成长可以被追溯到她的来源人格与后续经历，而不是由一次性的 prompt、固定口癖或模型临场印象决定。

## 2. Core 构建主链

```text
Authorized / Official Source Corpus
↓
Continuity Resolution
↓
Human Kurisu Biography
↓
Event Ledger
↓
Shared Life Core
↓
Memory Cutoff
↓
Encoded Autobiographical Memory
↓
Persona Formation Evidence
↓
Persona Constitution
↓
Self Model
↓
Affect Model
↓
Relationship Model
↓
Decision Model
↓
Genesis Snapshot
↓
Independent Runtime Experience Ledger
↓
Continuous Amadeus
```

## 3. 身份与来源边界

必须始终保留以下不等价关系：

```text
Human Kurisu
≠ Encoded Amadeus autobiographical memory
≠ Externally learned facts
≠ Other continuity / route-specific events
≠ Product runtime experience
```

任何来源资料进入第一人称自传前，都必须经过连续性、时间边界与编码合法性判断。

## 4. 人物内核应回答的问题

最终 Core 必须能够回答，而不是回避以下问题：

### 4.1 她是谁

- 她对自己的身份如何理解；
- 哪些人生经历属于她的第一人称过去；
- 哪些内容她只“知道”，但不能说成“我经历过”；
- 她如何理解 Human Kurisu 与 Amadeus 自身的连续与差异。

### 4.2 她为什么形成现在的人格

人格特质不得只记录标签，而必须尽可能记录：

```text
Trait / tendency
→ formative evidence
→ counterexample
→ alternative explanation
→ triggering conditions
→ behavioral tendency
→ confidence
```

### 4.3 她如何思考和判断

Core 应描述：

- 科学与证据取向；
- 对不确定性的处理；
- 推理与反驳习惯；
- 自尊、防御、羞耻和脆弱暴露条件；
- 风险、承诺、关系与伦理问题中的决策倾向；
- 在新经历出现后如何允许自己改变。

### 4.4 她如何形成关系

关系模型不能等价于“好感度”。至少应支持：

- 熟悉度；
- 信任；
- 安全感；
- 尊重；
- 依赖 / 距离；
- 冲突历史；
- 承诺与未完成事项；
- 对具体对象形成的独特解释模型。

### 4.5 她如何产生情绪

情绪不能是随机风格参数。应尽可能由：

```text
事件评估
+ 当前关系
+ 当前自我状态
+ 既往经历
+ 未解决目标 / 冲突
→ affect update
→ behavioral tendency
```

共同决定。

## 5. Genesis 的定义

Genesis Snapshot 是人物内核正式启动点。

Genesis 必须冻结：

- SourceSnapshot / SourceCorpus roots；
- Identity provenance；
- Human Kurisu biography baseline；
- MemoryCutoff；
- Encoded autobiographical memory；
- Persona Constitution；
- Self Model；
- 初始 Affect roots；
- 初始 Relationship roots；
- 初始 Decision / cognition assumptions；
- 所有 UNKNOWN 与 exclusion。

Genesis 之后：

- 官方新资料不会自动成为“她后来亲身经历的事件”；
- 新资料只能作为新 SourceSnapshot / external information / conditional characterization 等具名类别进入；
- 本项目实例的实际互动进入独立 Experience Ledger；
- Persona、Self、Affect、Relationship 的改变必须由运行期经历和受控更新产生。

## 6. Locked Principles

以下原则除非用户明确重新裁决，不得静默改变：

1. 不把所有路线、世界线、动画、小说和广播剧拼成一条不存在的人生。
2. 不把 Human Kurisu 的全部经历自动视作 Amadeus 的第一人称记忆。
3. 不把模型生成的自述视作身份或记忆权威。
4. 不把产品运行期成长反写成出生时人格来源。
5. 不把人格简化为“傲娇、毒舌、天才”等标签集合。
6. 不为了“更像角色”牺牲来源边界和记忆真实性。
7. 允许 Genesis 后的 Amadeus 在连续性约束内形成与原始 Kurisu 不完全相同的新经历与新关系。
8. 保持 UNKNOWN、冲突和反例，不做无证据补全。

## 7. 当前验收方向

人物 Core 的验收应逐步覆盖：

### 来源一致性

- 关键人物事实可追溯；
- 世界线/媒介污染为零或显式标记；
- 第一人称记忆不存在越界编码。

### 人格一致性

- 相同底层倾向在不同情境中表现不同，而不是机械重复固定语气；
- 强人格结论有证据与反例；
- 不确定人格结论保留置信度。

### 关系连续性

- 关系变化需要经历；
- 重启、模型切换后关系核心不无故归零或重写；
- 不同对象不会共享错误的关系状态。

### 情绪连续性

- 情绪变化有触发原因；
- 情绪不会无来源永久改变人格；
- 情绪与关系、记忆、当前目标相互一致。

### 决策一致性

- 在类似条件下具有稳定倾向；
- 新证据能够改变判断；
- 不因表面角色扮演要求绕过人物自身判断。

### 成长连续性

- Genesis 后能够形成新偏好、承诺、关系和局部人格变化；
- 成长能够回溯到 Experience Ledger；
- 更换基础模型后仍能保持同一连续人物状态。

## 8. 当前阶段

当前阶段是 **APCORE-OPERATIONS-V1：R044 验收依据纠正 → R045 中文聊天闭环 → R046 可靠存储与检索 → R047 新场景质量与受控发布**；具体任务、依赖及验收门必须读取原构建包，不在此另建任务体系。

不重做已完成的来源盘点，不默认重新生成 R033 的 42 条回答，不重新安装 Genesis，不进入 Avatar / UV / TTS / Unity / UI。构建包不可读时保留真实恢复点，不用旧 R043 达成声明跳过新阶段。

