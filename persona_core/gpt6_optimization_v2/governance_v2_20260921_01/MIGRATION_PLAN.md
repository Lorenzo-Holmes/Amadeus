# Governance V2.1 — Exact Change and Migration Plan

## 已实施的边界

Existing files:

- AGENTS.md：收敛为单一当前入口；旧完整 bytes 已归档，不重复保留互相竞争的 CURRENT 块。
- persona_core/APCORE_CANONICAL_EXECUTION_GUIDE.md：仅增加执行治理采用说明；原架构和科学原则不替换。
- persona_core/gpt6_optimization_v2/tools/evaluation_runner.py：call_rows 只增加 p.http_status；不修改原验证条件。
- persona_core/gpt6_optimization_v2/tools/test_deepseek_successor_binding.py：真实 completed-row → review → next-slot 合成链路与负向测试；不写新的真实评估答案。

New / corrected V2 files:

- persona_core/APCORE_CODEX_EXECUTION_POLICY_V2.md：完整正式规则与 R18 未决项边界。
- persona_core/CODEX_EXECUTION_RULES.md：短启动入口。
- persona_core/gpt6_optimization_v2/CODEX_EXECUTION_POLICY.json：固定 machine policy。
- persona_core/gpt6_optimization_v2/TEST_INVALIDATION_MATRIX.json：可执行的文件→测试映射。
- persona_core/gpt6_optimization_v2/tools/governance_v2.py：分类、test plan、pinned manifest verifier、single-writer CAS、原子 checkpoint 与 resume。
- persona_core/gpt6_optimization_v2/tools/test_governance_v2.py：26 项离线治理测试。
- persona_core/gpt6_optimization_v2/CANONICAL_MACHINE_STATE.json：从未封存的 V2 草案迁移为小型版本指针；旧草案 bytes 已归档。
- persona_core/gpt6_optimization_v2/governance_checkpoints/<digest>/：immutable checkpoint 与 deterministic public projection。
- 本目录 EXECUTIVE_AUDIT.md、R18_RECOVERY_DISPOSITION.json、合并回执、source freeze 及 formal acceptance config：新对象，不覆盖 R18 对象。

work/governance_v2_restart 下仅保留本轮的原字节、候选/日志、驱动脚本和私有历史清单；不把私有捕获或临时测试数据库提交到 Git。

## 历史迁移顺序

1. 保存中断前文件 bytes 和 hash，确认现存 R18 seal；已完成。
2. 定位原始 R18 204-member source；精确匹配的旧源码保存为父版本，不覆盖旧 SOURCE_MANIFEST；已执行。
3. 只修复 evaluator SQL 和新增中性测试，不改变 model/prompt/rubric/Persona。
4. 记录一个 source candidate，运行原 34 模块基线及新必要测试；同一 source identity 不重复 full suite。
5. 完成新 source freeze 与真正 zero-provider formal preflight。preflight READY 不等于 paid authorization。
6. single-writer 发布不可变 checkpoint，最后原子替换 pointer；崩溃时保留旧 pointer，不制造半同步九份状态。
7. 按明确 public-safe allowlist 在原分支提交一次；当前分离 Git 工作树中的无关 missing files 不提交。

本轮 collector 首次出现共享目录竞争和单模块本地超时，原失败/超时均保留。恢复只针对相应模块串行执行，并复用其它已完成日志；这不等于忽略测试失败或改写首次收集结果。

## 明确未实施：旧 writer/consumer 的全面兼容替换

旧 GOAL_STATE.json、TASK_GRAPH.json、RECOVERY_CURSOR.json、VALIDATION_MATRIX.json 保留原 bytes 与科学/DAG语义。Master/Progress/Continuation/Decision Log/Runbook 不因普通局部修复而人工全量同步。

后续需要全面兼容时，在一个明确的 source migration 中新增 tools/governance_v2_compat.py，不修改已封存历史脚本的旧版本：

1. 枚举当前真正仍被执行的读/写入口；与仅用于历史复现的 record_* / work/<historical stage> 脚本区分。
2. 以已归档四份 JSON 作为历史模板；将其独有 DAG、gate、evidence 等事实完整建模，不丢弃节点或把旧 FAIL 覆盖为治理 GREEN。
3. 为“活动编排状态”和“历史科学状态”建立显式字段映射与 schema version；不只合并顶层键名。
4. compat 工具仅生成 derived/read-only views，记录 canonical digest；禁止两个独立 writer。
5. 对所有活跃 consumers 做 contract tests 和断电/并发回归；在同一原子 generation 内提交整组 views。
6. consumer 迁移验收后才把旧四文件正式标成 V2 derived mirrors。当前不得提前标记已完成。

这是一项明确保留的兼容阶段，不是本轮已实施功能的隐含宣称。

## R18 后续执行顺序

R18 保持永久历史，不补槽、不重放。技术修复和工程测试完成后，仍需仅使用已有证据裁决 R18-N02-U01；本轮没有把它自动改成 PASS。

只有科学边界保持、所有已观察问题已裁决、harness exclusion 有审计依据、lineage 剩余额度有效，以及新的具体 paid authorization 同时成立，才可以在新 revision 从零开始一次完整固定验收。

本轮绝不完成最后的 paid allocation/validation；不能拿历史项目预算授权覆盖用户这次明确的零调用要求。

## 正式付费编排的实现边界

当前 governance_v2.py 是 offline-only 工具：分类和 replacement_blockers 只作门禁诊断，commit_state 不发布 paid_requests_allowed=true，也不分配或调用模型。这不是已实现的自主付费执行器。

后续需要接入正式 paid runner 时，新增独立的、显式授权的执行适配层，而不是把当前 JSON 中的 false 手工改成 true：将 immutable lineage、一次性 allocation reservation、受 pin 的授权/预算、全部工程回执及已有质量观察裁决绑定到原 formal runner；在请求前原子预留、结束后保留实际请求结果，UNKNOWN 和任何科学阻塞不恢复额度。需新增 allocation 并发/CAS/崩溃恢复与拒绝路径测试，在新 source freeze 中验收。当前本轮只有这份精确的后续接入计划，没有宣称该适配层已实现。

该后续适配的精确文件建议为：新增 tools/governance_paid_dispatch.py 与 tools/test_governance_paid_dispatch.py；在 tools/governance_v2.py 中增加明确授权的状态迁移入口，保留当前 offline-only 默认；每次付费任务在自己的新 revision 范围内保存被 pin 的 TASK_AUTHORIZATION.json，并将 allocation counter 仍写回同一 canonical writer，而不是另建一份可独立重置的预算状态。dispatch 只在所有前置证据通过后调用现有 evaluation_runner.prepare/run；不修改 rubric、原槽位或 Provider retry 行为。上述文件本轮未新增或修改。

paid dispatch 必须检查完整的既有 criterion 裁决，不仅检查 Major 计数；任何已成立的必需项 FAIL 或 UNCLEAR 都阻塞 harness exclusion。当前 offline diagnostic 不被当作完整 paid eligibility evaluator。
