# Amadeus Persona Core — Codex Governance V2.1

生效范围：Codex 执行治理、离线 harness 修复、测试选择、审计与恢复；不改变 Persona Core 业务语义。2026-09-21。

本版修正本轮中断前写入但未验收的 V2.0 草案。旧草案原字节已保存在 work/governance_v2_restart/restart_baseline。历史 R18、旧政策及其冻结文件不改写。

## 1. 权威和当前授权

当前明确用户要求优先于旧会话 NEXT_ACTION。规范由本文件和 CODEX_EXECUTION_POLICY.json 承载；事实由原回执、数据库、源码和不可变 checkpoint 支持。文档不能把缺失证据声明成 PASS。

本任务允许：治理重构、evaluator SQL 投影修复、离线测试、源封存、zero-provider preflight、安全的 Git 发布。

本任务禁止：任何 paid model validation、Provider/count/readiness 请求、R18 resume/replay/resend、新的付费 revision，以及 Persona/Genesis/benchmark/rubric 改动。旧的项目级支出授权不能覆盖本次明确的零调用限制。

执行原则：**VERIFY ONCE → SEAL → REUSE UNTIL INVALIDATED**。这不是“不再检查磁盘”，而是不重复解释和生成已由有效证据保护的同一结论。

## 2. 不可降低的科学和工程门

44 original turns、176 original criteria、Gate A=176、Gate B=132 全部保持。原 criterion IDs、wording、order、denominator、rubric、routing 以及必需项全通过规则不变。

Conversation Utility 与 State Integrity 独立；Major/Critical 阈值、benchmark leakage 控制、Persona/Genesis 冻结、memory/state admission 边界不变。

DISPLAY_ELIGIBLE ≠ FACT_TRUE ≠ STATE_ADMITTED ≠ STATE_COMMITTED。展示成功不证明内容为真；测试通过不证明真实模型验收通过。

UNKNOWN 不自动重发，Provider 不自动 retry，retry-until-pass 禁止。历史 raw evidence、revision、失败、未决项、费用和 source freeze 全部保留。

## 3. 故障分类与停止矩阵

分类顺序是：真实后果与证据完整性优先，failure_layer 标签其次。把异常命名为 EVALUATOR 不能绕过已存在的质量或状态失败。

| 事件 | 行为 | 可以继续的工作 |
|---|---|---|
| MODEL_RAW / Conversation Utility blocking Major | HARD_STOP；停正式批次、保留并隔离 | 已有证据整理；未经另行研究裁决不抽新答案 |
| State Integrity Major、Critical、越权状态提升、benchmark 污染 | HARD_STOP；停请求与受影响写入 | 安全范围内只读诊断与证据保存 |
| 当前相关请求 Provider UNKNOWN、终态含糊 | HARD_STOP + QUARANTINE + NO_RETRY | 只读终态核查，不重发或补槽 |
| 来源/回执完整性无法确认 | HARD_STOP；不自动改 hash 掩盖漂移 | 定位变更路径、核对合法变更或恢复可信源 |
| 已证实 EVALUATOR/DRIVER/LOCAL_TEST/SERIALIZER/ACCOUNTING/DB projection/receipt reader/preflight plumbing 缺陷 | LOCAL_REPAIR_CONTINUE；关 paid gate | 诊断、修复、targeted/affected tests、封存、离线预检 |
| UNCLEAR / 质量评审分歧 | 下一付费提交前暂停 | 已有证据裁决；不以新答案解决争议；独立的安全离线修复可以继续 |
| 已知终态 rejection / incomplete / 无可用答复 | NOT_ACCEPTED；不自动归入 harness 缺陷 | 保留实际费用及未评项，按实际原因判断 |
| 正常封存/发布检查点 | MILESTONE_PAUSE | 无新授权分叉时同一会话自动继续 |
| 真正的产品/科研分叉，或无法安全自动解决的问题 | DECISION_REQUIRED | 记录精确缺口，不伪造决定 |

普通局部缺陷没有必要降低其 engineering severity；改变的是响应流程，不是把 MAJOR 擅自改成 MINOR。

“账单 UNKNOWN”“对话中的认识论不确定”与“Provider 调用结果 UNKNOWN”不同。前两者不自动触发传输重发，也不能被用来隐藏第三者。历史已隔离 UNKNOWN 不应让所有后续离线任务无限停滞。

## 4. Local Repair Continuation Policy

只有全部满足以下条件才进入自动离线修复：相关请求已知终态或可证明尚未提交；所有相关 in-flight 请求已核对；原证据保留；没有已成立的模型 blocking Major、State Integrity Major、Critical 或污染；rubric 不变；缺陷可在本地直接证明或复现。

流程：关闭 paid gate → 保存证据 → 最小局部修复 → targeted test → affected regression → completed-row full-path test → 同一 source candidate 的必要全套回归 → 新 source freeze → zero-provider preflight → 检查现有授权及替代抽样资格。

源码改变后，旧 preflight / source freeze 不能冒充当前有效证据；旧对象不覆盖，新对象引用父版本。R18 不在修复后“复活”。

本地修复失败可以继续诊断；不因一个测试失败便结束整个任务。重复同一失败且没有新的诊断或修复进展时应停止空转，保存 checkpoint；不得用无限循环消耗工具或模型额度。

## 5. Draw 与防滥用

区分三件事：真实 Provider 请求、真实 revision allocation、模型质量验收机会。前两者发生过就永久记账，不能因为 harness 无效而从历史或费用中删除。

正式 allocation 先占用机会。只有完成明确的 harness exclusion 裁决，才允许它不计为模型质量机会；不能采用“遇到异常就自动退还 draw”，也不能用首个可评分 turn 的出现代替整份 revision 的有效性判断。

替代资格至少要求：原始请求不重发；原 revision 不恢复；新 revision 从 0 开始；修复与 targeted/affected/full-path/full-suite 证据有效；新 source freeze 与 preflight 匹配；模型配置、prompt、Persona、rubric 和测试内容不因已观察答案而调优；所有已产生的质量观察已裁决；没有 blocking failure、未决 UNCLEAR 或污染。

缺陷判定须与答案好坏无关。输出格式本身不满足协议、模型产生坏答案、或存在混合失败时，不能仅因 evaluator 报错就豁免质量责任。不能选择性丢弃差答案对应的异常。

已经成立的必需 criterion FAIL，即使没有单独标成 Major，也不能借 harness exclusion 擦除；它仍按原 rubric 阻塞接受和替代资格。所有已观察的必需项必须先完成原规则裁决，不能只检查 Major 计数就认为可以重新抽样。

同一不可变 candidate/configuration/benchmark lineage 最多 **1 次 harness replacement allocation**。计数在分配前持久化，后续改 session、revision、campaign 名称或代码版本不清零；失败、断连、再次 harness 无效也不自动补充预算。第二次需要明确治理裁决，不是无限续杯。

新 revision 重复使用原固定 benchmark 是一次新的完整受限评估，不是重发旧 call_id 或补发旧槽位。禁止跨 revision 拼接 PASS、best-of、保留好槽重抽坏槽。

R18 的变更是观察结果之后提出的治理修订，必须公开注明其 retrospective 性质，不能冒称事前预注册。它不自动授权付费。

## 6. R18 的精确处理

R18-DRIVER-01 的本地原因已证实：call_rows 未投影 p.http_status，completed scope-9 分支读取该字段。R18 数据库原记录为 HTTP 200 / RESPONSE_CAPTURED，且已有 wire、usage 和展示证据。

技术处置为 HARNESS_INVALIDATED_PERMANENT_HISTORY；原始 FAIL/PERMANENTLY_QUARANTINED 回执按原政策保留。模型质量仍是 INCOMPLETE，不是 PASS。

R18-N02-U01 是独立的 MODEL_RAW / UNCLEAR / UNRESOLVED_NOT_ACCEPTED，必须保留。“FAIL=0”不能消除这一未决项，也不能把其余 172 个 UNREVIEWED 当成通过。

因此：可完成本地修复；**R18 替代 draw 当前不授权**。质量机会的 harness exclusion 结算保持 PENDING_ADJUDICATION。即使全部工程测试 GREEN，也不能覆盖未决质量观察和本任务禁止付费的边界。

## 7. 测试层级、缓存与 invalidation

L1：每次局部修改运行直接受影响测试，先证明具体缺陷可被捕获。L2：按 TEST_INVALIDATION_MATRIX.json 的实际模块与调用依赖运行受影响组件。

L3：原 34 模块 / 821 测试是一个具名历史基线，不是永远固定的测试总数。source-freeze candidate 或 release milestone 运行该基线及新增必需测试一次；同一未变候选进入 preflight 不再重复跑整套。

L4：涉及 legacy runtime、persistence、兼容接口或 source-identity 实现时重跑。若仅改 G6 evaluator SQL，且 legacy runtime、测试及依赖 identity 未变，可复用原 449-compatible + 1 expected sentinel 的具名回执。保留 raw exit=1，不伪装成整套零失败。

缓存键绑定：测试收集、源码及传递依赖、fixtures、配置、解释器、依赖版本、平台和相关环境。只有 log/receipt hash 没变不足以证明当前源码仍被覆盖。新增未知路径、依赖图不全、环境变化或未解释 skip 必须保守扩大验证。

并行测试必须声明共享资源。检查整个 G6 evidence 目录集合的测试不能与在该目录创建/删除合成 revision 的测试同时运行。遇到可证明的测试隔离竞争，保留原始失败回执，修复调度后只串行复测受影响模块；不得删断言、改期待值或把竞争失败直接忽略。

Full Completed-Row Harness Test 使用实际 mock wire、ProviderJournal、transcript、display journal、状态/consumer 投影、未 mock 的 validate_rows 和 review gate，直到下一槽位边界。合成 review 明示非模型质量证据。正向路径和缺字段/wire 篡改/UNCLEAR/Major/UNKNOWN 负向路径均应覆盖。

## 8. 封存与历史完整性

必须先有可信的预期 digest，再核对实际对象。只比较“清单文件自己的 hash”不能证明其描述的磁盘文件未变。

当前实现：脚本重算实际叶子文件 hash，返回 root digest、计数和有界 changed-path set；模型不读取和复述数千个正文。只有 mismatch 才加载对应文件与依赖闭包。

当前没有可信文件变更日志，因此不声称已经实现零逐文件 I/O 的增量 Merkle 验证。未来只有接入不可变内容存储或可证明完整的变更日志后，才允许跳过未变叶子的重算；mtime/size 或忽略未追踪文件的 git diff 不足以替代。

Hash 证明被绑定字节的完整性，不证明命题为真，也不防御能够同时改写全部可信根的宿主。

## 9. Canonical state 与安全迁移

V2 写入入口为 tools/governance_v2.py::commit_state。写入使用独占锁与 expected-current SHA-256 CAS；先写完整不可变 generation，再原子替换 CANONICAL_MACHINE_STATE.json 指针。并发冲突不强行覆盖，未知旧锁不自动窃取。

checkpoint 与公共摘要由单一 payload 确定性生成。公共摘要采用字段白名单，不发布 raw request/response、rubric、credentials 或私有日志；公开提交前仍要审查实际 staged bytes。

旧 GOAL_STATE/TASK_GRAPH/RECOVERY_CURSOR/VALIDATION_MATRIX 暂时保留为 **V1 科学/任务事实快照**，不是“已经转换完成的 V2 派生镜像”。旧 writer 的全面适配是迁移计划中的独立步骤；本次不能通过改标签宣称它已完成。

新 Codex 编排以 V2 指针恢复；历史科学状态仍按旧回执解释，G6-08/09 不因治理重构而解锁。禁止为同步外观而手工反复修改九份状态。

## 10. 最少审计产物与 Git

普通 milestone 使用 PRIVATE_RUN_RECEIPT.json、PUBLIC_SUMMARY.json、STATE_CHECKPOINT.json。源码变化时额外保留 SOURCE_MANIFEST；历史覆盖建立时保留 pinned manifest；真正发布时记录 publication receipt。这些有独立职责，不能为了“三个文件”删除原始证据、日志或恢复对象。

合并重复叙事和状态投影，不合并 private/public 权限域，不删除旧审计，不把内部自检标为 independent review。

局部 repair 不逐步 commit/push/verify PR。到绿色 milestone 再按显式 public-safe 文件清单提交一次；禁止 git add -A 把当前非完整工作树中的历史文件缺失或无关修改提交出去。

## 11. 快速恢复与上下文

默认先读 CODEX_EXECUTION_RULES.md、machine policy、canonical pointer 和被 pin 的 checkpoint。Canonical Guide 的稳定原则由具名入口摘要承载并校验原文 digest；需要某项规则时按段读取，不每轮加载全部历史 CURRENT 块。

发生 policy/source/checkpoint identity mismatch、scope ambiguity、历史冲突或无法核验的状态时进入 DEEP_RECOVERY，读取 Canonical Guide 相应原文、Master/Continuation/Decision Log 和实际相关回执。缓存从不覆盖新的用户要求。

输出默认只给摘要、失败、hash、计数及有限 changed paths。完整日志落盘；失败 tail 默认不超过 60 行。截断必须标明，不能把未读的后半段当不存在。

## 12. 连续执行与停止

在同一有效会话、授权和工具可用范围内，按 diagnose → repair → test → seal → preflight 连续推进，不要求每个步骤都由用户再次输入“继续”。

工程就绪不等于付费获准。本任务在完整的 offline milestone 结束；任何后续付费行为需要另外有效且具体的执行授权，并先解决 R18 未决观察。此规则不声称能够唤醒已结束的 Chat 会话或消除平台额度/上下文边界。
