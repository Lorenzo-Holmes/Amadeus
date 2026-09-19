# APCORE-OPERATIONS-V1 一次连续执行协议

文档状态：`ACTIVE EXECUTION POLICY`  
目标停止状态：`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`  
机器任务状态唯一入口：`TASK_STATE.json`  
验收唯一索引：`ACCEPTANCE_MATRIX.json`

本文件不是第二套任务表，也不覆盖 `TASK_STATE.json`。它规定：新会话如何从**实际磁盘恢复点**开始，持续完成所有内部可执行任务，直到内部工程门全部通过；外部独立评审和真实跨日验证保持真实等待状态。

## 1. 当前创建时恢复点

2026-09-07 本文创建时，磁盘已核实：

- `R044-01` ～ `R044-04`：`DONE`，对应 gate `PASS`；
- `R045-01` ～ `R045-03`：`DONE`，对应 gate `PASS`；
- `R045-04`：`IN_PROGRESS`，`AC-R045-04=IN_REVIEW`；
- `R045-05` 及 R046/R047 后续任务未完成；
- `workspace_sync_status=VERIFIED`；
- 上次 502 涉及的 `response_check.py`、`chat.py`、`run_cli_live_r045.py` **实际均不存在**，因此不是“可能部分落盘”的状态；
- `APCORE-R045-LIVE-01` 中 `adapter_check` 已消费并成功捕获，剩余 A1–A4/B1–B4 八个 slot 尚未提交；
- 已消费 slot 禁止重发；旧 R033 42 条生成禁止重跑；R035 Genesis 禁止重装。

新会话必须先重新读取 `TASK_STATE.json` 和实际 provider journal。若磁盘已经比上述状态更晚，以磁盘较新证据为准，不把本文的创建时快照回写到任务状态。

## 2. 连续执行目标

执行器收到“一次执行到底”的授权后，应循环：

```text
读取 canonical TASK_STATE / ACCEPTANCE_MATRIX
→ 找到依赖已满足且未完成的任务
→ 检查是否有上次未知写入/未知收费请求
→ 实施最小充分改动
→ 执行行为测试/语义评审/故障注入
→ 保存原始失败和实际证据
→ 按验收门裁决
→ 更新 TASK_STATE + ACCEPTANCE_MATRIX + Progress
→ 有长期裁决时追加 Decision Log
→ 立即进入下一可执行任务
```

不要因为完成一个文件、revision、测试、模型调用、候选或阶段报告而停下来等待“继续”。

## 3. 推荐执行顺序

依赖关系仍以 `TASK_STATE.json` 为准。当前主路径建议：

```text
R045-04 真实CLI闭环
→ R045-05 可信事件准入
→ R046-01 事务存储决策
→ R046-02 原子提交/幂等/并发/故障恢复
→ R046-03 真实备份与恢复
→ R046-04 长期相关检索
→ R046-05 关系与情绪防滥用
→ R046-06 迁移及发布前恢复演练
→ R047-01 在看新输出前冻结新评测协议
→ R047-02 端到端真实多轮模型测试
→ R047-03 人物/边界/连续性评审
→ 修复所有阻塞问题并定向+全局回归
→ R047-05 受控发布候选
→ 将 R047-04 准确保留为 WAITING_EXTERNAL / WAITING_REAL_TIME
→ BUILD_SCOPE_COMPLETE_VALIDATION_PENDING
```

`R047-04` 不要求为了内部 build scope 伪造完成。独立评审者和未来自然日不可得时，必须保存可交付评审包、跨日协议与当前 checkpoint，然后继续其它内部任务。

## 4. R045-04 当前必须先做的恢复动作

1. 查询 `live_01/runtime.sqlite3` 的 `provider_calls`、`call_batches`、`turns` 和 `turn_lifecycle`。
2. 确认 `adapter_check` 已是终态 `RESPONSE_CAPTURED`，且不存在任何 `SUBMITTED_STATUS_UNKNOWN`。
3. 确认 A1–A4/B1–B4 没有对应 `provider_calls`，才允许提交。
4. 新建而不是猜测恢复：
   - `persona_core/operational_runtime_v1/response_check.py`
   - `persona_core/operational_runtime_v1/chat.py`
   - `persona_core/operational_build_v1/tools/run_cli_live_r045.py`
5. CLI 必须允许用户只输入自然中文；tags、事件 JSON、authority 字符串不得成为普通用户接口要求。
6. A 和 B 使用不同 entity；至少一次真正 Python 进程退出后重新打开 DB 并 resume，再继续 A4/B4。
7. 后一轮模型上下文必须包含上一轮真实、已展示的模型输出，不能使用预写 assistant answer。
8. 保存每轮 request/context/raw response/usage/turn lifecycle；如果某 slot 进入未知提交状态，立即停止该收费 batch，不提交后续 slot。

## 5. 自动修复循环

出现失败时默认继续，而不是结束会话：

```text
保存失败原件
→ 分类：PRODUCT_BUG / SPEC_CONFLICT / CHECKER_FALSE_POSITIVE / EVIDENCE_INSUFFICIENT / EXTERNAL_FAILURE
→ 最小修复
→ 定向复验
→ 相关全局回归
→ 更新风险记录
→ 继续依赖满足任务
```

只有明确证据证明检查器错时才修检查器；不能改变 rubric 或扩关键词使当前样本变绿。原输出、原失败、原评分标准和旧发布文件保持可追溯。

## 6. 最大能力与资源政策

本项目不以减少 ChatGPT 回复长度、思考时间或工程推理深度为优化目标。复杂架构、故障恢复、语义评审和人物质量判断使用当前会话可用的最高合理推理强度。

这不等于允许外部付费 API 无界消费：

- 每个逻辑批次必须在调用前固定模型、thinking/reasoning 配置、请求集合、输入/输出上限、有限总保护值；
- 默认 `automatic_paid_retries=0`；
- 已提交结果未知时禁止自动重发；
- 不通过拆成许多小批次规避总费用记录；
- 不为了省钱删除原计划要求的关键场景；若实际完整测试需要更高保护值，可建立具名预算 revision 并在 standing authorization 下直接执行；
- 每次付费批次调用前重新核对官方模型名、API合同和最新价格；服务端 usage 估算不是账单认证。

R045-04 必须保持已经冻结的 `APCORE-R045-LIVE-01` 参数，不因本文改变历史批次。R047-01 可以在**查看新输出之前**创建新的高推理评测批次并固定参数。

## 7. 唯一允许暂停的硬条件

允许暂停仅限：

- `UNRECOVERABLE_TOOL_OR_ENVIRONMENT_BLOCK`：DevSpace/文件系统持续不可恢复，且无法安全持久化恢复点；
- `UNKNOWN_PAID_REQUEST_STATE`：收费请求已可能到达服务端但结果无法确认；
- `DATA_INTEGRITY_BLOCK`：继续写可能破坏唯一健康副本或权威状态；
- `REQUIRED_EXTERNAL_DEPENDENCY`：只有外部评审者/未来真实日期才能满足；但这只阻塞对应 R047-04，不阻塞其它内部任务；
- 平台安全或实际 OS 权限阻止继续。

普通测试失败、需要重构、需要多轮调试、API正常费用、UNKNOWN来源事实、人物质量未达阈值均不是自动停止理由，应进入修复循环。

## 8. 每个 gate 的完成规则

任务只有同时满足以下条件才能 `DONE`：

1. 原依赖全部 `DONE`；
2. `ACCEPTANCE_MATRIX` 对应 gate 的全部 required evidence 实际存在；
3. 证据与当前代码/数据 hash 或版本绑定；
4. 实际测试/评审通过；
5. 原始失败没有被删除；
6. gate 有 checked_at 和 reviewer/执行身份；
7. `TASK_STATE` 与 `PERSONA_CORE_PROGRESS.md` 同步；
8. 不能由静态检查自动制造语义 PASS。

## 9. 达到目标状态的严格条件

只有以下 required-for-build-scope gates 均为 PASS，且没有未处置 critical finding，才允许：

```text
completion.build_scope_complete = true
phase_status = BUILD_SCOPE_COMPLETE_VALIDATION_PENDING
```

同时必须明确：

```text
completion.product_acceptance_complete = false
independent_blind_acceptance = PENDING_EXTERNAL 或真实结果
true_natural_day_validation = PENDING_REAL_TIME 或真实结果
```

不得把 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING` 写成“整个产品最终验收完成”。只有 R047-04 未来取得真实独立评审和真实跨自然日证据并通过，才允许 `PRODUCT_ACCEPTANCE_COMPLETE`。

## 10. 会话结束时恢复记录

若因硬阻塞或平台边界结束，必须在磁盘持久化：

```text
LAST_COMPLETED
CURRENT_STATE
NEXT_ACTION
RECOVERY_POINT
BLOCKER
IN_FLIGHT
SPEND
VALIDATION_PENDING
```

恢复点必须精确到 task ID、文件、DB/batch/call/slot 状态和下一条安全操作。写入超时后先读回文件/DB/日志，不能盲目重复 patch、迁移或收费调用。

