# Amadeus 下一会话执行入口

请继续 **Amadeus Persona Core：真实对话与可靠运行** 主线，工作区：

`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`

本次目标按 `APCORE-OPERATIONS-V1` 执行，不再按旧R043的`GOAL_COMPLETE`提前停止。用户已授权项目内持续构建、测试、合理费用保护下的模型调用、备份及受控迁移，不需要每项任务完成后再问是否继续；权限不超出实际工具/操作系统和项目范围，授权不替代验收证据。

先读取AGENTS、原Master Goal、Progress、Continuation Protocol和最新Decision Log，再读取：

```text
persona_core/operational_build_v1/START_HERE.md
persona_core/operational_build_v1/BUILD_PLAN.md
persona_core/operational_build_v1/TASK_STATE.json
persona_core/operational_build_v1/ACCEPTANCE_MATRIX.json
```

若这些文件尚未落盘，使用本会话实际附件中的构建包，按其中`WORKSPACE_SYNC_INSTRUCTIONS.md`导入并核对哈希，不要假设路径存在。同步补丁只用于匹配的旧状态；若已有后续进展，保留进展并更新入口，不能退回初始任务。

初始恢复点为`R044-01`，但以实际TASK_STATE与磁盘证据为准。主线为：

**R044 纠正验收依据并复核既有42条输出 → R045 隔离环境连续中文聊天闭环 → R046 可信事件准入、事务、恢复与长期检索 → R047 新场景、多轮人物质量及受控发布。**

执行一项、验证一项、记录一项，然后连续推进下一依赖满足任务。不要只给计划或反复建立目标文档，不在一个revision完成时停下。不重做已完成的来源盘点，不覆盖R001–R043、冻结内容或原始回答，不用模拟经历污染正式用户关系。

关键约束：

- 程序预填PASS、关键词命中、文件哈希和测试数量都不是语义验收。逐项判定要有实际输入/答复、标准、引用、理由和评审者。
- 区分来源审计、虚构场景和产品运行，不把所有虚构动作误当现实越权，也不把真实操作声明当普通表演。
- 自然语言/模型只能提议事件。可信控制层验证来源、对象和权限后才事务化更新，不能凭`admission_authority`字符串自授权限。
- 先在克隆sandbox接通对话；可靠存储、恢复和新场景门通过后才受控激活。保持Genesis及历史身份谱系。
- 后续模型调用前确认当前官方接口与计价，固定总保护额和请求范围；已提交但状态未知的收费请求不自动重试。
- 完成状态必须附实际证据。最后8条事件不是长期检索，哈希摘要不是恢复备份，模型交叉评审不是独立盲评。

若发现失败，先分清产品问题、标准冲突和静态误报，再做最小修复；不能修改检查器只为让当前样本变绿。独立评审和真实跨日条件不可得时标PENDING并继续其它可执行任务，不伪造日期或评审者。

在工具可用的当前会话持续推进。若到达平台执行边界或不可恢复工具故障，保存LAST_COMPLETED、CURRENT_STATE、NEXT_ACTION、RECOVERY_POINT、BLOCKER、IN_FLIGHT与SPEND；说明具体未完成事项，不能承诺回复后仍在后台执行。

现在从实际恢复点开始实施，不先输出另一份长计划。
