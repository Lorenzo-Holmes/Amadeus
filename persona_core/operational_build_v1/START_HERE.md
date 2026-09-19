# 后续会话从这里开始

计划：`APCORE-OPERATIONS-V1`｜2026-09-07  
目标：可信验收 → 连续文本对话 → 可靠存储/恢复/检索 → 新场景人物验证。

## 本包现在代表什么

本包是用户要求编制的构建文档与执行契约，不是R044–R047已经实施的代码包。历史R043仍保留，但其“全部完成”结论不能替代新的验收。

本次只成功读取了部分Windows项目文档；随后DevSpace的read、exec及重新打开工作区均返回502。因此**没有确认本包及进度入口已写入Windows工作区**。本目录里的`TASK_STATE.json`如实保留`workspace_sync_status=NOT_VERIFIED`。

更新（2026-09-07）：上段为原包制备时的历史情况。现已完成Windows原成员核验与入口合并；以当前TASK_STATE为准。R044-01已按原门验证完成，接续R044-02。不要重新导入初始任务表或覆盖较新状态；同步前证据保留为历史。

建议安装位置：

```text
C:\Users\skr\Documents\Codex\Amadeus-Project.staging
└─ persona_core\operational_build_v1\
```

## 恢复流程

1. 先连接DevSpace并复用有效workspaceId；确认实际工作区路径。先读项目AGENTS与原四份恢复文档，再读本包。
2. 若本包只在附件/下载目录，按`WORKSPACE_SYNC_INSTRUCTIONS.md`导入。只有文件真正落盘并核对后，才能把同步状态改成VERIFIED。不要从文件名编造本地路径。
3. 检查是否已有更新的任务状态、R044以后成果或在途请求。已有进展则合并，不用本包初始状态覆盖它。
4. 依次读`BUILD_PLAN.md`、`TASK_STATE.json`、`ACCEPTANCE_MATRIX.json`、`BASELINE_AND_EVIDENCE.md`。
5. **不要再使用原包的“初始实施任务=R044-01”作为当前恢复点。** 先读取 `TASK_STATE.json`；2026-09-07 本文v1.1创建时实际状态已推进到 `R045-04 IN_PROGRESS`，R044-01～04与R045-01～03均已通过原gate。若磁盘更晚，以更晚状态为准。
6. 若目标是一次连续执行至内部工程门完成，继续读取：`ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md`、`TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md`、`QUALITY_ASSURANCE_PROTOCOL_V1.md`、`FAILURE_RECOVERY_RUNBOOK_V1.md`。
7. 每项验证后同步TASK_STATE和根目录Progress，关键裁决写Decision Log；普通阶段完成后继续下一项，不等待用户重复发送“继续”。

## 文件职责

| 文件 | 用途 |
|---|---|
| `BUILD_PLAN.md` | 完整目标、架构、20个实施任务、验收及运行边界 |
| `TASK_STATE.json` | 唯一机器可读任务状态，初始20项均未实施 |
| `ACCEPTANCE_MATRIX.json` | 每任务一个验收门、证据要求及最终汇总规则 |
| `CONTINUE_PROMPT.md` | 新会话直接可用的续作指令 |
| `BASELINE_AND_EVIDENCE.md` | 历史依据、当前核对范围和不确定性 |
| `WORKSPACE_SYNC_INSTRUCTIONS.md` | 导入、备份、冲突处理与回滚规则 |
| `WORKSPACE_ENTRYPOINT_PATCH.patch` | 对旧根目录状态的最小同步补丁；需先核对现状 |
| `CHANGELOG.md` | 文档版本与同步状态记录 |
| `tools/validate_plan.py` | 只读校验任务依赖、证据门和初始状态；不是Runtime测试 |
| `MANIFEST.json` | 此交付快照文件大小和哈希 |
| `DOCUMENT_VALIDATION.json` | 本包结构校验的真实结果，不代表项目验收 |
| `ONE_SHOT_EXECUTION_TO_BUILD_SCOPE_COMPLETE.md` | 从真实TASK_STATE连续执行到内部工程门完成的总执行协议；不维护平行任务状态 |
| `TECHNICAL_ARCHITECTURE_OPERATIONS_V1.md` | R045–R047目标技术架构、可信边界、SQLite事务/检索/恢复设计 |
| `QUALITY_ASSURANCE_PROTOCOL_V1.md` | 各阶段必须执行的行为、故障、恢复、长期检索和人物质量测试 |
| `FAILURE_RECOVERY_RUNBOOK_V1.md` | DevSpace/收费调用/数据库/语义失败的非破坏恢复规则 |
| `NEW_SESSION_MAX_CAPABILITY_PROMPT.md` | 新会话一次执行到 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING` 的完整启动指令 |
| `tools/validate_one_shot_docs.py` | 校验一次执行文档与当前计划/任务契约的一致性；不是项目功能验收 |

本阶段内部工程完成可标为`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`。独立评审与真实跨日证据也通过，才能使用`PRODUCT_ACCEPTANCE_COMPLETE`。不要把这两个状态合并成无范围的“项目全完成”。
