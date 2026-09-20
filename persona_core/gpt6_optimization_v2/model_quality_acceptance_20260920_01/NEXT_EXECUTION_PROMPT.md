继续 Amadeus Persona Core / APCORE-GPT6-OPTIMIZATION-V2。

唯一工作区：C:\Users\skr\Documents\Codex\Amadeus-Project.staging

本轮任务：G6-07-MODEL-CONFIGURATION-QUALIFICATION-PLAN-V1。

首先完整读取 persona_core/APCORE_CANONICAL_EXECUTION_GUIDE.md，再读取AGENTS.md、Master Goal、Progress、Continuation Protocol、Decision Log、G6 USER_OBJECTIVE、四份machine state和CURRENT_EXECUTION_RUNBOOK。

从 persona_core/gpt6_optimization_v2/model_quality_acceptance_20260920_01/FINAL_AUDIT.json 恢复，核验POLICY_FREEZE_MANIFEST并读取该目录全部八份政策/下一步文档。采用APCORE_MODEL_QUALITY_ACCEPTANCE_1：策略C，以A单revision严格门进行资格验收。当前配置已FAILED_MODEL_QUALITY_GATE；这是工程拒收，非总体模型能力不足的统计结论。R16 FAIL/PERMANENTLY_QUARANTINED；R16-N02-01仍MAJOR/OPEN_BLOCKING。

本轮只完成零调用的配置选型和提交前资格计划。禁止DeepSeek/OpenRouter/其他Provider调用、readiness、paid request、fresh revision创建、历史请求恢复重发替换、生产源码和Persona/Genesis修改、benchmark/阈值修改、G6-08。不要把本提示词理解成运行下一次44轮的授权。

连续执行：
1. 验证现有P3 source182全部MATCH，P1合同及历史原件hash不变，恢复当前配置的完整角色映射。历史计划42 pro+2 flash，失败实际发生于pro；不能只换未运行的flash逃避主模型失败。
2. 用公开官方能力/接口资料和现有本地兼容性证据，选择至多一个有实质质量差异的候选。可同Provider或不同Provider，不能预设保留或更换。不得使用private rubric/答案作prompt或选型依据；不得真实采样后挑最好配置。
3. 把source、Provider、精确model/版本、原槽位角色映射、API、route、stream、reasoning、temperature/top_p/seed/penalties的值或NOT_SENT/UNSUPPORTED、输入输出上限、timeout、工具、consumer/acceptance版本全部固定。有效设置未知不得伪造。只换seed/日期/session/revision无效；找不到实质候选即CONFIGURATION_NOT_READY。
4. 审查现有正式driver是否支持该候选。若只有独立synthetic路径可用，记录VALIDATION_BINDING_CHANGE_REQUIRED并交付精确有限接线计划，本轮不得修改production source。已有provider2 PASS不满足G6-07。
5. 固定唯一后继候选、一次future revision、44/176原题原顺序、A176/B132、全部必需PASS、Major0/Critical0、原场景/类别阈值、hard-stop、UNKNOWN和terminal拒绝规则、0自动付费retry。没有失败后自动候補候选。
6. 当前及本轮预算0 CNY。未来设计上限19.00 CNY、44次generation、readiness0。依据当日官方费率计算完整44槽位最坏上界，含未知预留。若不够则BUDGET_NOT_READY；不得偷偷压缩输入输出能力、拆批或继承旧48.64授权。保存精确预算和所需下一次决策。
7. 在字段完整且兼容时进行真正零Provider的binding preflight；不调用provider，也不分配revision。冻结CONFIGURATION_PREREGISTRATION、资格决定、预检或阻塞报告、public-safe audit和NEXT_EXECUTION_PROMPT。完整READY才生成未来一次fresh validation提示词，否则生成解决真实阻塞的有限提示词。
8. 更新四份machine state及当前镜像，append-only Decision Log，保留所有旧失败及UNKNOWN/SPEND。按现有公开allowlist发布到Lorenzo-Holmes/Amadeus现有branch codex/persona-core-operations-v1-20260917 / PR #1；禁止private responses、dialogue、rubric、SQLite、SPEND、credentials、UNKNOWN capture、hidden reasoning。

不要逐步询问。完成所有零调用工作后停止，不运行下一次validation。最终报告候选、实质变化依据、完整有效配置、预算可行性、source/history核验、READY或具名阻塞、G6-07仍未通过、G6-08/09锁定、零调用和下一恢复点。没有可行候选时如实停止，禁止改产品或质量阈值只为获得PASS。
