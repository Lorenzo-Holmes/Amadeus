# Next Validation Plan

Policy APCORE_MODEL_QUALITY_ACCEPTANCE_1。当前 state=MODEL_CONFIGURATION_REQUALIFICATION_REQUIRED，G6-07=FAIL；下一动作是零调用模型配置选型，**不是**直接创建R17或重新运行R16。

## 已冻结的前瞻规则

| 字段 | 固定值或提交前必须满足的条件 |
|---|---|
| next-stage kind | MODEL_CONFIGURATION_QUALIFICATION / ZERO_PROVIDER_SELECTION |
| current exact configuration additional revisions | 0 |
| successor candidates this qualification campaign | 1；没有失败后自动候补 |
| successor revision budget | 1，44 turns，176 unique criteria，原顺序/场景/换模位置 |
| source | 现有P3 freeze，182 members，hash MATCH；无生产修改 |
| policy and denominator | APCORE_MODEL_QUALITY_ACCEPTANCE_1；A176/B132；不重加权 |
| thresholds | 原必需项全部PASS；blocking Major=0；Critical=0；context/naturalness≥4、specificity≥3；原场景/类别规则 |
| independence | 新隔离状态和journal，不继承评测历史；场景内保留真实上下文；不假设IID |
| hard stops | HARD_STOP_POLICY.md；quality Major也停；UNKNOWN/terminal rejection不补槽 |
| automatic paid retries | 0 |
| cost ceiling, present task and next selection | 0 CNY；Provider/readiness/paid calls均0 |
| future paid qualification design ceiling | 19.00 CNY总最坏保护上限，最多44次生成，readiness=0，含已花费和未知预留；不是消费预测或本轮授权 |
| future price feasibility | 提交前用当日官方定价和完整44槽位输入/输出上限计算保守上界；若无法在19.00内覆盖完整计划则BUDGET_NOT_READY，不降低上下文/输出能力来硬塞预算、不拆batch规避额度；另立具名预算决策后才能运行 |
| unresolved successor fields | provider/model/role map/API/reasoning/temperature/top_p/seed及其支持状态/限制/配置hash/定价hash 尚未选定；必须在任何新call之前冻结，缺一则NOT_READY |
| confidence | 工程门，不声明总体可靠率；无多revision聚合 |

19.00 CNY是本次制定的有限未来预算设计边界，保守小于USER_OBJECTIVE §18的20 CNY具体批次审批线；原文最后的宽泛授权不影响本轮显式0调用限制。历史48.64 CNY不转移为新授权；遇预算不合适时更改预算需要提交前具名批准/记录，不是结果出来以后补记。当前不声称任一候选满足该预算。

## 执行前阻塞顺序

先只读选择一个有实质质量差异的候选并固定选型依据；核对它可由当前冻结driver完整接线，不得把独立synthetic provider路径当正式验收。将全部有效参数和原角色映射写入CONFIGURATION_PREREGISTRATION，锁定44/176与费用上界并hash seal。缺字段/接口不兼容/预算不够则明确停止。

将候选绑定到正式零Provider预检；先核验实际构造请求、journal-first、关闭重试、原题/rubric隔离与source/policy/consumer匹配。预检可构造对象但不能readiness或请求模型。旧READY不复用为新配置READY。

只有后续执行会话明确获得完整且有效的执行范围、配置manifest和READY证据后才分配一次fresh revision；本轮不分配编号。成功仍只推进到原DAG的G6-08，未通过不得解锁；本轮和下一选型会话均不进入G6-08。
