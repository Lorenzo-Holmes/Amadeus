# APCORE-OPERATIONS-V1 故障与跨会话恢复手册

## 1. 原则

失败先保存事实，再判断是否重试。写操作、迁移和收费调用的“超时”永远不是“没有发生”的证明。

## 2. DevSpace 502 / 工具连接故障

发生 502/超时：

1. 不立即重复 patch/exec；
2. 先有限重试只读：目标文件是否存在、大小/hash/mtime；
3. 对 SQLite 查询目标 table/row；
4. 查询可能仍在运行的本地进程元数据；
5. 分类：`NOT_APPLIED / FULLY_APPLIED / PARTIAL_OR_UNKNOWN`；
6. 只有确认 `NOT_APPLIED` 才重做同一写入；
7. `PARTIAL_OR_UNKNOWN` 先建立恢复记录，再做非破坏 reconciliation。

本项目已有实例：上次502后 `response_check.py/chat.py/run_cli_live_r045.py` 经后续读回确认全部不存在，因此可以从零新建；不能继续把它们描述成未知半写状态。

## 3. 收费请求未知状态

Provider 必须在网络 I/O 前写 `SUBMITTED_STATUS_UNKNOWN`。如果网络异常：

- 不自动重发；
- batch stopped；
- 保存 call_id/request hash/slot/model/reserve；
- 尝试通过本地已捕获 raw/provider id 或服务方可用查询证据 reconciliation；
- 无法确认时保持 unknown，不能为了完成测试重新发送同一 slot；
- 后续固定分母中将其作为失败/未知实际记录处理。

`adapter_check` 当前已确定成功，禁止再次消费。

## 4. 文件写入故障

文本/代码用 `apply_patch`。失败后读回目标；不要依据工具错误字符串猜测文件状态。重要一次性证据目录采用新目录/新文件，不覆盖旧失败。

## 5. SQLite 故障

写入只在事务内。数据库打不开时：

1. 保留原 DB/WAL/SHM 字节；
2. 不先运行破坏性“修复”；
3. 复制到隔离目录；
4. `PRAGMA integrity_check`；
5. 检查 schema/user_version/migration_history；
6. 从最近健康 backup 在新目录恢复；
7. 与事件尾/状态/Genesis核对；
8. 原损坏副本作为失败证据保留。

## 6. 测试失败

测试失败不是停点：保留日志 → 最小修复 → 定向复验 → 完整相关回归。只有继续可能破坏权威数据时才硬停。

## 7. 语义/人物质量失败

不允许：改旧答案、删除失败场景、降低阈值、扩大关键词、把失败改为静态误报而无证据。

允许：修上下文、路由、检索、状态逻辑或真正的 checker bug；建立具名 revision；用同一冻结测试重新执行受影响范围并保留前后结果。

## 8. 进度状态更新顺序

有意义阶段完成后：

1. 写证据；
2. 运行 gate verifier；
3. gate PASS 后更新 `ACCEPTANCE_MATRIX`；
4. 更新 `TASK_STATE`；
5. 更新 `PERSONA_CORE_PROGRESS.md` 镜像；
6. 长期裁决追加 Decision Log；
7. 运行 `validate_plan.py`；
8. 再进入下一任务。

不要先把任务改 DONE 再补证据。

## 9. 会话被迫结束时必须保存

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

`IN_FLIGHT` 特别记录 provider batch/call/slot、提交状态和是否允许重发。

## 10. BUILD_SCOPE 完成后的真实停止方式

若所有 required-for-build-scope gate PASS：保存 release candidate、启动/恢复说明、完整清单，然后设 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`。R047-04 保持真实等待，不因为“想一口气完成”伪造外部评审或未来日期。

