# Persona Core Continuation Protocol

状态：**ACTIVE / REQUIRED FOR CONTINUATION**  
建立日期：2026-09-06

## 1. 用途

本协议用于防止新会话、新模型或长时间中断后出现：

- 忘记人物 Core 主目标；
- 重复已经完成的研究；
- 无证据重写人格；
- 将 UV / Avatar / TTS / UI 工作误当作人物内核进度；
- 将不同世界线或媒介重新混合；
- 重新提出已被否决的旧架构；
- 因上下文丢失而从零规划。

## 2. 每次恢复的强制顺序

### STEP 1 — Load Goal

读取：

`AMADEUS_PERSONA_CORE_MASTER_GOAL.md`

确认当前任务仍属于 Persona Core。

### STEP 2 — Load Progress

读取：

`PERSONA_CORE_PROGRESS.md`

确认：

- CURRENT_PHASE
- COMPLETED
- IN_PROGRESS
- KNOWN_GAPS
- DO_NOT_REDO
- NEXT_ACTION

### STEP 3 — Load Decisions

读取：

`PERSONA_CORE_DECISION_LOG.md`

不得静默推翻已锁定裁决。

### STEP 4 — Check New Evidence

检查自上次进度后是否出现：

- 新授权资料；
- 新 SourceSnapshot；
- 用户明确修正；
- 原裁决中的事实错误；
- 新的冲突证据。

如果没有，不重新审判已完成基础原则。

### STEP 5 — Continue NEXT_ACTION

APCORE-OPERATIONS-V1 生效期间，以 `persona_core/operational_build_v1/TASK_STATE.json` 为唯一机器可读任务状态入口，以同目录 `ACCEPTANCE_MATRIX.json` 为验收依据；Progress 同步镜像。恢复前先检查这些文件是否实际存在并读取，不从旧聊天或文件名推断状态。

原包现已落盘且12个原清单成员逐项核验；后续状态更新不改原MANIFEST来伪装未变化。`persona_core/operational_recovery_20260907_r001/RECOVERY_RECORD.json` 只保留为历史同步前证据，不能覆盖已更新的canonical TASK_STATE。每次超时写入先读回目标及哈希；本轮已确认上次中断入口补丁未改变目标，使用当前具名小补丁接续。

非本阶段任务则继续遵循 `PERSONA_CORE_PROGRESS.md` 中的第一个未完成 `NEXT_ACTION`。

不得用“重新规划整个项目”替代实际继续工作。

## 3. 不得重复的工作

标记为 `COMPLETED` 或 `DO_NOT_REDO` 的内容，只有以下情况允许重开：

1. 出现新的高权重来源；
2. 发现明确事实错误；
3. 发现连续性污染；
4. 用户明确要求重审；
5. 旧结论与新的 Locked Principle 冲突。

重开时必须记录原因。

## 4. 新证据与旧结论冲突时

不得静默覆盖。

必须记录：

```text
Previous decision
Previous evidence
New evidence
Conflict type
Can coexist? yes/no/conditional
Recommended resolution
Confidence
Affected artifacts
```

涉及长期项目方向的，追加到 `PERSONA_CORE_DECISION_LOG.md`。

## 5. 来源到人格的顺序约束

默认禁止以下捷径：

```text
台词印象 → Persona trait
```

推荐顺序：

```text
Source
→ Event / statement
→ continuity context
→ interpretation
→ counterexample search
→ PersonaAnchor candidate
→ confidence
→ Persona Constitution
```

强人格主张必须优先寻找反例。

## 6. 记忆写入约束

任何第一人称过去时自传内容进入 Core 前，必须回答：

1. 这件事属于哪一个 continuity？
2. 是否发生在对应 MemoryCutoff 之前？
3. 是否有证据表明它被 Amadeus 编码？
4. 是否只是 Human Kurisu 发生过？
5. 是否只是后来外部获知？
6. 是否来自其他路线/媒介？

无法回答时，不得默认写入第一人称记忆。

## 7. Genesis 后更新约束

Genesis 后：

- 新互动 → Experience Ledger；
- 新关系事实 → Relationship updates；
- 新情绪 → Affect updates；
- 长期稳定变化 → Persona/Self proposal；
- 外部资料 → external information 或新 SourceSnapshot；
- 不允许直接改写出生时来源经历。

## 8. 会话结束前

如果本次完成了有意义的阶段工作：

1. 更新 `PERSONA_CORE_PROGRESS.md`；
2. 更新 `CURRENT_PHASE` / `COMPLETED` / `NEXT_ACTION`；
3. 如产生新重要裁决，更新 `PERSONA_CORE_DECISION_LOG.md`；
4. 不把仅讨论但未执行的计划标记为完成。

## 9. Continuous Execution Mode

本协议默认启用连续执行模式。

### 9.1 连续推进规则

收到“继续”“按照计划继续”“持续执行”“开始下一步”或等价指令后：

1. 执行当前 `NEXT_ACTION`；
2. 当前 action 完成后，若后续 action 的依赖已经满足，则直接继续；
3. 不以“需要用户确认下一步”为默认停点；
4. 不以“已经形成建议”为完成；可执行的建议应转化为实际产出；
5. 自动进行来源核验、连续性检查、反例检查、记忆合法性检查与产物一致性检查；
6. 每跨越一个有意义阶段立即持久化进度。

### 9.2 允许暂停的硬阻塞

仅以下情况允许暂停：

```text
GOAL_COMPLETE
REQUIRED_USER_SOURCE_MISSING
EXPLICIT_AUTHORIZATION_REQUIRED
IRREVERSIBLE_OR_HIGH_RISK_ACTION
UNRECOVERABLE_TOOL_OR_ENVIRONMENT_BLOCK
PLATFORM_EXECUTION_BOUNDARY
```

普通 UNKNOWN、资料尚未完全整理、存在多个可逆方案、需要继续核验等情况，不属于硬阻塞。

### 9.3 被迫结束时的恢复记录

若因 `PLATFORM_EXECUTION_BOUNDARY` 或其他硬阻塞结束本轮，必须在 `PERSONA_CORE_PROGRESS.md` 中保存：

```text
LAST_COMPLETED
CURRENT_STATE
NEXT_ACTION
RECOVERY_POINT
BLOCKER (if any)
```

其中 `RECOVERY_POINT` 必须精确到下一轮可以直接继续的文件、阶段、记录范围或任务编号。

### 9.4 项目级持续授权（2026-09-07 用户明确授权）

用户已明确授予 Amadeus 项目为完成项目目标所需的持续执行权限，并要求后续不要再逐步索取项目授权。该授权作为本项目的长期 standing authorization 使用。

因此，在 Amadeus 项目范围内，只要某操作是为了完成已确认的项目目标，且不违反平台安全限制或工具本身的权限边界，则默认视为已获用户授权，包括但不限于：

- 继续当前 NEXT_ACTION 与后续依赖已满足的任务；
- 创建、修改、测试、构建、重构和验证项目文件；
- 调用已配置的模型/API并自行设置合理的本地费用保护；
- 进行 Persona / Memory / Self / Affect / Relationship / Decision 的候选冻结与版本推进；
- 在前置验证通过后执行 Genesis freeze / install 及 Runtime 初始化；
- 执行恢复、迁移、回归、模型切换、重启与持久化测试；
- 为完成项目自行选择可逆实现方案和必要权限范围。

该 standing authorization 取代本项目此前“每次进入下一阶段、每个小额付费批次、Genesis 冻结/安装都必须再次询问用户”的重复确认要求。此前要求单独确认的项目内部授权门，今后视为已由本条满足。

仍不得绕过：平台安全政策、工具/操作系统实际未授予的权限、不属于 Amadeus 项目目标的外部操作，以及无法验证目标或会造成明显非项目性损害的行为。

即使发生不可逆项目状态变化，也应先创建可恢复快照/备份并记录回滚点；但不再因此暂停等待用户再次授权。

## 10. 工作线切换

只有用户明确要求时才切换到：

- UV / Modeling；
- Avatar；
- TTS；
- Unity；
- UI；
- Runtime tools；
- 其他 Amadeus 子项目。

切换任务不等于关闭 Persona Core 目标。返回 Core 时继续读取本协议与 Progress。

## 11. APCORE-OPERATIONS-V1 的验收与暂停语义

R043 旧 GOAL_COMPLETE 不关闭本阶段。已确认旧 R033 验收器预填 PASS；旧报告作为历史保留，但必须依据原始答复与原标准具名复核，不重新生成答复制造替代结果。

只有对应原任务门满足且证据落盘，才能更新 canonical TASK_STATE 为 DONE。关键词命中、引用存在、字节一致、代码运行、语义判断与人物质量分别记录；未知保持未知。源研究、明确虚构场景与真实运行必须区分。

`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING` 只表示工程门满足但独立评审/跨日证据待完成；不能简称整个项目最终验收完成。`PRODUCT_ACCEPTANCE_COMPLETE` 还要求预定独立评审、真实跨日证据以及无未处理关键错误。当前两者均未达到。

外部包、独立评审者或真实时间跨度不可得时准确记录 WAITING_EXTERNAL / WAITING_REAL_TIME，并继续其它依赖明确满足的任务；不能伪造依赖。中断前保存 LAST_COMPLETED、CURRENT_STATE、NEXT_ACTION、RECOVERY_POINT、BLOCKER、IN_FLIGHT、SPEND、VALIDATION_PENDING。新会话不得盲目重发未知结果的收费请求，或重跑一次性备份脚本覆盖证据。

