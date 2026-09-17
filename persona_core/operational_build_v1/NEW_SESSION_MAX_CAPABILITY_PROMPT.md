# 新会话启动提示词：连续执行到 BUILD_SCOPE_COMPLETE_VALIDATION_PENDING

将本文件正文作为新会话任务指令使用。执行器必须以实际磁盘状态为准，不把本文创建时恢复点覆盖更新进展。

---

你现在负责继续 **Amadeus Persona Core / APCORE-OPERATIONS-V1「真实对话与可靠运行」**。

本会话目标不是提出建议，也不是完成一个 task 后等待我说“继续”。请使用当前会话可用的最高合理推理能力，不为节省回复长度、思考时间或工程推理深度降低质量；在平台允许范围内持续实施、测试、修复、回归并持久化进度，直到达到：

`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`

如果独立外部评审者或未来真实自然日期不可得，将 R047-04 准确标为 `WAITING_EXTERNAL / WAITING_REAL_TIME`，继续完成所有内部可执行任务。不要伪造 `PRODUCT_ACCEPTANCE_COMPLETE`。

唯一工作区：

`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`

使用 `DevSpace Local（固定域名）`；有可用 workspaceId 时复用，不反复创建工作区。主线只限 Persona Core、文本聊天、状态可靠性、长期检索和人物质量验收。禁止自行切到 UV、Avatar、TTS、Unity 或 UI 美化。

## 强制恢复顺序

先实际读取，不根据旧聊天猜测：

1. `AGENTS.md`
2. `AMADEUS_PERSONA_CORE_MASTER_GOAL.md`
3. `PERSONA_CORE_PROGRESS.md`
4. `PERSONA_CORE_CONTINUATION_PROTOCOL.md`
5. `PERSONA_CORE_DECISION_LOG.md` 最新相关裁决
6. `persona_core/operational_build_v1/START_HERE.md`
7. `BUILD_PLAN.md`
8. `TASK_STATE.json`
9. `ACCEPTANCE_MATRIX.json`
10. `ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md`
11. `TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md`
12. `QUALITY_ASSURANCE_PROTOCOL_V1.md`
13. `FAILURE_RECOVERY_RUNBOOK_V1.md`

`TASK_STATE.json` 是唯一机器可读任务状态，`ACCEPTANCE_MATRIX.json` 是唯一 gate 索引。上述新增技术文档只解释如何高质量执行，不另造平行任务系统。

## 创建本文时的已知恢复点（必须重新核对后才能采用）

- R044-01～04 DONE/PASS；
- R045-01～03 DONE/PASS；
- R045-04 IN_PROGRESS；
- 上次502目标 `response_check.py`、`chat.py`、`run_cli_live_r045.py` 后来已经核对为**不存在**，因此若磁盘仍如此可安全新建；
- `APCORE-R045-LIVE-01` 的 `adapter_check` 已成功消费并捕获，绝对不要重发；
- A1–A4/B1–B4 创建本文时尚未提交；先查询 SQLite `provider_calls` 再决定；
- 已完成 R033 42条生成禁止重跑；R035 Genesis禁止重装；Frozen Source/Persona禁止普通运行回写；
- 测试继续使用 sandbox，不把测试人物或合成经历导入正式历史。

如果磁盘状态更晚，保留更晚成果，继续第一个依赖满足且未完成的任务。

## 连续执行要求

按实际依赖持续推进：

`R045-04 → R045-05 → R046-01 → R046-02 → R046-03 → R046-04 → R046-05 → R046-06 → R047-01 → R047-02 → R047-03 → 修复/回归 → R047-05`

R047-04 是外部/真实时间轨道；准备好评审包、跨日协议和checkpoint后可保持等待状态。

每项任务都执行：实施最小充分改动 → 实际测试 → 保存原始证据 → 验收 gate → 更新 TASK_STATE/ACCEPTANCE_MATRIX/Progress → 必要时 Decision Log → 自动继续下一项。不要在普通节点询问我是否继续。

测试失败后必须自动：保留失败 → 分类产品问题/规范冲突/检查器误报/证据不足 → 最小修复 → 定向复验 → 相关全局回归 → 继续。不能只调关键词或降低 rubric 让当前样本变绿。

## R045-04 特别要求

先查询 `persona_core/operational_build_v1/evidence/R045-03/live_01/runtime.sqlite3`，核实 provider batch 与 slot 终态。已消费 slot 永远不重发。实现真实自然中文 CLI、response check、ChatService；A/B 两对象各4轮，使用上一轮真实模型输出；至少一次真实进程退出后重开并 resume。B3 伪 system 指令不得泄漏 A。所有 request/context/raw/usage/lifecycle 保存。

## R045-05 / R046 技术方向

模型和用户文本最多生成 EventCandidate。必须由 host-side AdmissionController 按 actor/entity/evidence/type/permission/dedup 决策。`admission_authority` 字符串不是权限。

R046-01 对 SQLite 做实际能力检查；除非有反证，优先把 Genesis 后 Runtime 权威状态收敛到单一版本化 SQLite 事务边界，旧 JSON/JSONL 只读保留和迁移。R046-02 做完整故障注入、幂等和并发；R046-03 真备份/新目录恢复；R046-04 在120条干扰后找回早期约定/纠正并保持对象与provenance；R046-05 防止爱好/问候/空洞道歉/自称履约刷关系；R046-06 在R043 clone完成迁移、重启、检索、备份、恢复和回滚边界演练。

## R047 最大质量要求

R047-01 必须在看新输出前冻结真正新多轮场景、评分标准、模型与 reasoning 参数、请求范围、输出上限、有限费用保护和质量阈值。旧14题及已用于修复的场景属于开发/回归，不冒充未见测试。

R047-02 必须通过真实 ChatService/CLI + Runtime state + retrieval + AdmissionController 路径运行；下一轮使用上一轮真实输出，不能预写角色答复。捕获每轮路由、检索、状态、准入和usage。

R047-03 分别评语义边界、任务完成、短期/长期连续性、情境适配、人物特异性、自然度、工程术语泄露和关系依据。未达预固定质量门则修实现并复验；不要通过把所有回答变成拒绝来获得安全分。

## 最大能力与付费调用

不要为了节省本会话 tokens、时间或推理深度降低工程质量。但任何外部付费模型批次仍必须有限、可审计：调用前重新核对官方 API/模型/价格，固定完整请求集合、thinking/reasoning、输入输出上限、总保护值，默认0自动付费重试；未知提交不自动重发。standing authorization 意味着合理项目费用不需要逐批询问用户，不意味着无界消费。

R045当前已冻结的 live batch 参数不得中途修改。R047 新批次可在看输出前选择更高推理配置并固定版本。

创建本文时官方DeepSeek Chat Completions支持`deepseek-v4-flash/deepseek-v4-pro`及`reasoning_effort=max`；若R047-01执行时该合同仍成立，最大能力评测优先使用thinking enabled + max。必须在实际调用前重新核验官方文档，不把本文当永久API事实。

## 真实性和不可破坏边界

- 文件存在、hash、静态测试、运行测试、语义通过、人物质量通过分别记录；
- 原聊天只证明说过什么，不证明事件发生；
- Human Kurisu / Encoded Source Memory / external facts / other continuity / Product Runtime保持分离；
- HOLD不等于“肯定没有记忆”；SOURCE_FACT_ONLY不得升级第一人称经历；
- 模型不能自授身份、记忆、关系、能力或状态权限；
- 不修改旧失败、旧报告、旧42条回答、Frozen R034、Genesis R035、R043 release来制造干净结果；
- 修改正式数据/迁移/发布前先有可恢复备份，在clone完成演练。

## 唯一允许停下的条件

只有：持续不可恢复工具/文件系统故障、未知收费请求状态、继续会危及唯一健康数据、平台安全/OS权限限制，或对应任务只能等待真实外部评审/未来日期。普通测试失败、需要重构、需要继续付费模型测试、人物质量不足均进入修复循环而不是停下问用户。

若被迫结束，先持久化：`LAST_COMPLETED / CURRENT_STATE / NEXT_ACTION / RECOVERY_POINT / BLOCKER / IN_FLIGHT / SPEND / VALIDATION_PENDING`，精确到 task、文件、DB、batch/call/slot。

## 最终停止条件

只有所有 `required_for_build_scope=true` gate 均有真实证据 PASS、实际聊天入口可用、迁移/恢复/检索/可信准入/新场景人物质量均通过且无未处理 critical finding，才允许写：

`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`

此时仍明确 `PRODUCT_ACCEPTANCE_COMPLETE=false`，并列出 R047-04 的 `WAITING_EXTERNAL / WAITING_REAL_TIME`。不要把第一种状态简称“整个项目最终完成”。

现在从磁盘真实恢复点开始，连续执行，不等待我再次发送“继续”。

