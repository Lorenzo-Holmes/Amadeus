# Model Quality Acceptance Policy

Policy version: `APCORE_MODEL_QUALITY_ACCEPTANCE_1`。Task: `G6-07-MODEL-QUALITY-ACCEPTANCE-DECISION-V1`。状态：ADOPTED / FROZEN。适用：当前 G6-07 及以后明确绑定此政策的配置资格审查；不改写历史 verdict。

## 正式裁决

选择 **STRATEGY C — Model-Configuration Qualification，采用 A 的 Single-Revision Strict Acceptance 作为配置门**。当前配置：`CURRENT_CONFIGURATION_FAILED_MODEL_QUALITY_GATE`。这里的 FAILED 是未满足原产品验收合同，不是证明模型的总体错误率超过某个统计阈值，也不是认定服务商整体不可用。

一个具名配置只能获得一次预注册的完整 external44 验收机会。所有必需项必须通过；出现真实 blocking Major，该 revision 和配置的本次资格审查失败。已失败的相同 source + 有效模型配置不得靠新 revision 再抽样获得准入。没有通用产品缺陷证据时，进入模型配置资格审查，不修改 Persona、prompt 或状态架构。

## 原始目标与依据

Master Goal 要求可追溯来源人格和连续运行；G6 USER_OBJECTIVE §§3、7、9、20 要求减少局部规则、维持状态边界、关闭必需失败项并完成后续验证。Canonical Guide §§9、18–21、27、35 和已采用 P1 `G6_07_DUAL_GATE_SPEC.md` 明定两门同时满足、必需项全部完成、无未解决 blocking Major/Critical，且新加权平均不能抵消失败项。产品使命不绑定某个 Provider。

本政策保留这些门，明确其配置资格语义；不建立原规范没有授权的“允许一个 Major”预算。`stochastic` 是可能的生成特性，不能充当错误免责条款。R16 只证明实际产生过一个阻塞质量错误；其随机成因、复发概率、总体能力不足均未被证实。

## 两类验收

Product Integrity Acceptance：身份、来源、Persona/Genesis、Memory、关系、权限、执行、candidate→admission→commit、重启与幂等。应用 P1 Gate B 与 P3 已有离线证据；现实 P4 覆盖仍不完整。

Model Conversation Quality Acceptance：推理、任务完成、指代、上下文、自然度、帮助性、人物特异性及认识论纪律。应用 P1 Gate A 的实际展示评审与原评分规则。Gate B 通过不抵消 Gate A 失败；Gate A 失败不自动授权扩大 State Guard。

## 验收单位

| 单位 | 作用 | 能否单独放行产品 |
|---|---|---|
| single response | 不可变 raw、accepted、displayed 谱系；错误层定位 | 否 |
| single turn | 四个原 criterion、A/B 子判断及该轮 finding | 否 |
| single revision | 固定 44 turns / 176 unique criteria 的工程验收单位 | 仅可满足 G6-07 的一个配置门 |
| model configuration | source、provider、模型角色映射、接口及全部有效生成控制绑定的资格单位 | 仍须 G6-08/09 等后续门 |
| whole product candidate | 同版本 source、配置、干净实例与全部内部/外部/真实日期证据 | 仅完整原 DAG 满足后可验收 |

“某轮回答正确”“某个 revision PASS”“配置通过 G6-07”“产品最终验收”不得互换。

## 策略比较

| 策略 | 优点 | 缺点与本次裁决 |
|---|---|---|
| A 单 revision 严格门 | 原必需项不降门；停止条件简单；不挑选最好结果 | 对随机失误敏感；只能证明具名测试合格/不合格，不能声称总体可靠率。采用为 C 的门。 |
| B 预注册 K revisions | 可在独立且同分布等条件成立时估计重跑可靠性；固定 K 防止重置计数 | 原目标未给总体容忍率和统计风险；44 轮有上下文相关，176 项不是176次独立试验。允许失败后 aggregate PASS 会改变既有门；K=3 也不能证明高可靠性。本版不采用。 |
| C 配置资格审查 | 将生成质量归于精确配置；不为一个错误无限改架构；允许后端变化 | 需要事前候选选择理由与有限机会，防止配置搜索变相 retry。作为主策略采用。 |
| D 功能门加有限多轮可靠性 | 可分别检验功能与随机稳定性，保留全部失败 | 必须另定总体可靠性目标、抽样和预算；若容忍 Major 则冲突，若全轮零错则更严且不是原门所必需。本版不采用。 |

对 B/D 的拒绝不是声称统计验收不可能；是拒绝在看过失败后替本项目发明有利容忍率。未来明确的可靠性研究可另立版本/任务，但不能将本轮未采用的设计当作运行许可。

## 版本、失败与变更

政策内容及阈值由 `POLICY_FREEZE_MANIFEST.json` 绑定。以后调整阈值、停止规则、K、错误预算或验收单位，必须新 policy version、明确变更依据和原目标兼容性，先于新结果冻结。旧结果按原策略保留，不能直接混入新策略的成功统计；旧失败在资格历史表中始终可见。版本变更本身不为同一失败配置重开一次机会。

本轮 source、Persona、Genesis、benchmark、历史 finding、UNKNOWN、SPEND 均不修改；没有 fresh revision、readiness 或 Provider call。当前 G6-07 保持 FAIL；G6-08/09 LOCKED。
