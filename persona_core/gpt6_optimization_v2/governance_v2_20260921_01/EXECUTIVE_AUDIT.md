# Amadeus Persona Core — Governance Efficiency / Quality-Preserving Refactor

日期：2026-09-21。版本：Governance V2.1。

## 1. Executive verdict

**OVERHEAD_CONFIRMED_IN_CONTEXT_STATE_AND_LOCAL_REPAIR_ORCHESTRATION。**

当前存在可以明确削减的重复上下文、状态复制和局部故障收尾成本。但不能把所有历史审计都判成浪费：Provider/configuration/source identity、原始证据、质量未决项、private/public separation 和真正的接受门仍需要独立保护。

本次落地的是离线治理规则、可执行测试调度/完整性/状态工具，以及 R18 evaluator 的局部修复。没有修改 Persona Core 的对话、记忆、状态准入业务语义；没有修改 44/176 验收；没有调用目标模型或重跑 R18。

最终离线测试、source freeze、preflight 和发布状态，以本目录 PRIVATE_RUN_RECEIPT.json、公开投影及 CANONICAL_MACHINE_STATE.json 指向的不可变 checkpoint 为准。文档中的设计不是模型质量 PASS。

## 2. 实际审计范围与可复核来源

工作区：C:\Users\skr\Documents\Codex\Amadeus-Project.staging。

仓库采用分离 Git 元数据：work/github_submit_amadeus.git。检查到的本地起点是 codex/persona-core-operations-v1-20260917，commit 91ff05a598fbc5bd53b1ce8c3f6a17360d163b3d。普通根目录 git status 失败不能据此推断项目没有 Git 历史。

已定位并核对用户列出的 AGENTS、Canonical Guide、Master Goal、Progress、Continuation、Decision Log、四份 machine JSON 和 Current Runbook；重点核对当前路由、原始原则、重复字段和停止规则，而不是重新审理所有历史人格结论。

六个指定治理目录的顶层文件数分别为：

| 目录 | 顶层文件数 | 已找到续接 prompt 大小 |
|---|---:|---:|
| model_quality_acceptance_20260920_01 | 21 | 4,019 bytes |
| model_configuration_qualification_20260920_01 | 26 | 4,320 bytes |
| successor_binding_contract_20260921_01 | 31 | 3,378 bytes |
| openai_formal_binding_20260921_01 | 27 | 3,415 bytes |
| input_bound_proof_20260921_01 | 22 | 3,493 bytes |
| deepseek_successor_20260921_01 | 42 | 未在该目录发现同名 prompt |

这 169 个顶层文件不是“169 个重复文件”；其中包括独立的配置、源码、原始审计和冻结对象。上述 prompt 的真实测量不支持“这些文件都超过上万 tokens”的说法。未进行 tokenizer 计数，不伪造 token 百分比。

四份 machine state 的字节数是 104,171 / 456,381 / 103,912 / 165,468，总计 829,932 bytes。四份 JSON 有 232 个值完全相同的顶层字段，包括 CURRENT_STATE、IN_FLIGHT、NEXT_ACTION、RECOVERY_POINT 等。重复维护与读取问题有直接证据。

关键原始证据：

- deepseek_successor_20260921_01/FINAL_AUDIT_V2.json、EVIDENCE_SEAL_V2.json、OFFLINE_TEST_RECEIPT.json、SOURCE_MANIFEST.json。
- 同目录 validation/DRIVER_FINDING.json、QUALITY_OBSERVATION_PRIVATE.json、STATE_INTEGRITY_AUDIT.json、BENCHMARK_LEAKAGE_AUDIT.json。
- operational_build_v1/evidence/G6_V2_external44_20260921_18_fresh_deepseek_flash/runtime/runtime.sqlite3 的实际 provider_calls 行。
- tools/evaluation_runner.py::call_rows、validate_rows、require_successor_review_prefix。
- tools/test_deepseek_successor_binding.py，尤其原来 mock 掉 validate_rows 的 review-gate test。
- model_quality_acceptance_20260920_01/MODEL_QUALITY_ACCEPTANCE_POLICY.md 与冻结清单。
- model_configuration_qualification_20260920_01/STOP_RULES.md。
- input_bound_proof_20260921_01/OFFLINE_TEST_RECEIPT.json 的 component/legacy reuse 记录。

所有路径未另注明时相对 persona_core/gpt6_optimization_v2；restart inventory 与原字节备份位于 work/governance_v2_restart/restart_baseline/INVENTORY.json。

## 3. 必须保留、应优化、应合并

必须保留：44 original turns、176 original criteria、A176/B132、原 IDs/wording/order/rubric/routing、Conversation Utility 与 State Integrity、原 Major/Critical 阈值、leakage controls、Persona/Genesis、memory/state admission、UNKNOWN 不重发、Provider 不自动 retry、raw/history/spend 不删除、源码可追溯。

应优化：默认恢复读取、重复状态写入、局部 repair 的测试选择、同一 source candidate 的重复全套回归、历史解释与 JSON dump、每个小步骤的 commit/push/PR 检查。

应合并：相同 milestone 中重复描述同一状态的 FINAL_AUDIT/PUBLIC_AUDIT/PUBLIC_STATE/CONSISTENCY/STATE_WRITE_RECEIPT 段落。职责相同的摘要可以合并；原始证据、private/public 权限域、source manifest 和恢复对象不能因文件数量目标而删除。

反例必须保留：input-bound 阶段明确记录 component_regression.rerun_this_task=false，复用了 821 测试与 legacy 回执。因此本次是把已有正确的增量做法固定为通用政策，不是声称从前每一轮都全量重复。

## 4. R18 的精确裁决

实际数据库只有一条 N02_T1 Provider 记录：RESPONSE_CAPTURED、HTTP 200、model=deepseek-flash；原回执具有 wire/native usage/display 支持。原封存清单核验没有 mismatch。

已确认的本地错误是 SQL projection 漏字段：call_rows 的 SELECT 缺少 p.http_status，而 scope-9 completed audit 读取 row['http_status']。修复仅补入这个字段，没有关闭回执核对，也没有将缺失值默认成 200。

因此 R18 的**技术处置**可归为 HARNESS_INVALIDATED_PERMANENT_HISTORY。历史 FAIL/PERMANENTLY_QUARANTINED 文件按原政策保留；不是事后改写成 PASS。

但 R18 同时存在 R18-N02-U01：MODEL_RAW / UNCLEAR / UNRESOLVED_NOT_ACCEPTED。已评 4 项为 PASS3、FAIL0、UNCLEAR1，另有 172 项未评。FAIL0 不等于质量通过，也不证明所有未评项没有失败。

**当前不能直接退还并放行替代 draw。** 技术修复可以完成；模型质量机会的 harness-exclusion 结算仍需已有观察的裁决。即使所有工程测试通过，本任务的零付费授权边界仍然有效。

## 5. 新故障与停止矩阵

| 分类 | 触发条件 | 处理 |
|---|---|---|
| HARD STOP | Model/Conversation Utility blocking Major、State Integrity Major、Critical、污染、越权提升 | 停正式批次；保留并隔离；不得局部改名绕过 |
| HARD STOP | Provider UNKNOWN / ambiguous terminal / 无可信终态 | 停止；隔离；NO RETRY；不补槽 |
| HARD STOP / DEEP RECOVERY | 完整性缺口、来源身份无法证明、异常未分类 | 核对实际证据；不改 hash 隐藏漂移 |
| LOCAL REPAIR CONTINUE | 已知终态或未提交、可证明本地缺陷、无已成立科学/状态阻塞、证据保持完整 | 关 paid gate；修复、targeted/affected tests、完整链路测试和预检 |
| MILESTONE PAUSE | 正常封存/发布边界 | 写一个 checkpoint；无新决策则同一会话继续 |
| QUALITY REVIEW PAUSE | UNCLEAR / 评审分歧 | 只裁决既有证据；不生成新答案解决争议 |

分类优先看后果和证据，不看异常类名。engineering Major 可以保持 Major，同时使用本地修复流程；不需要降级严重度来节省额度。

## 6. Harness-invalidated draw 防滥用

每个实际请求与 allocation 永久记账。harness exclusion 是显式裁决，不是异常处理器自动退款。

一个 immutable candidate/configuration/benchmark lineage 最多一次 replacement allocation；会话、revision 或 campaign 改名不重置。新 writer 用 CAS 与单调 counter 防止丢失并发更新或恢复旧预算。

替代前需要已保存观察全部裁决、缺陷与答案质量无关、模型/prompt/Persona/rubric 不因输出调优、targeted/affected/full-path/full-suite 完整证据、新 source freeze、zero-provider preflight 和单独有效的执行授权。

R18 例外是 retrospective governance amendment，不能宣称事前预注册；保留原结果和未决观察。禁止挑最好 revision、拼接好槽位、重抽坏槽位或把格式不合格的模型输出一律归咎于 harness。

## 7. Test invalidation matrix

| 变更 | 必须测试 | 全套/legacy |
|---|---|---|
| evaluation_runner.py | evaluator、scope7/8/9 binding、completed-row、display/consumer、review gate | 新 freeze candidate 跑完整基线一次；未改变 legacy runtime 时核对复用证据 |
| provider/transport/accounting/preflight | provider-specific、transport、accounting、evaluator、消费者 | 新 freeze 全套；共享兼容面变化则 legacy |
| transcript/admission/accepted_output/semantic | state integrity、persistence、consumer、正式 integration | 全套与相关 legacy |
| 治理 policy、状态 writer、manifest 工具 | schema、固定阈值、分类、CAS、故障恢复、hash 与公共投影 | 不为每个文档编辑重复 821 |
| test 文件 | 该文件本身及测试收集身份 | 正式候选包含新增测试，不把历史 821 当硬上限 |
| 未分类路径/依赖或环境漂移 | 保守扩大，不默认无影响 | full + legacy dependency review |
| benchmark/rubric/Genesis | 不是普通测试失效 | HARD STOP / 另行科学变更控制 |

完整模块清单在 TEST_INVALIDATION_MATRIX.json，plan 子命令可实际生成测试选择。缓存键不仅是结果日志的 hash，还包括源码/依赖、fixture、解释器、环境与 collection identity。

## 8. 为什么旧 118 + 821 + READY 漏掉 bug

旧 preflight 是 pre-request construction；没有 completed row。原 DeepSeek 测试覆盖 ChatService、ProviderJournal 和 review gate 的局部行为，其中 review 测试直接 mock 掉 validate_rows，不能证明 completed scope-9 的 SQL 投影。

新增测试从真实的 synthetic wire 经原 ProviderJournal、transcript、display journal、state/consumer projection 进入未 mock 的 validate_rows，先证明无 review 不准下一槽，再写显式合成 review 并验证下一槽。

另有故障测试：删除 http_status 投影的 mutant 必须失败；篡改 wire 必须失败；UNCLEAR、Major、UNKNOWN 必须阻止下一槽。合成 review 的 PASS 是测试夹具，不是模型质量结果。

本轮完整回归还暴露出一项 LOCAL_TEST 调度缺陷：test_openai_formal_binding 的预检测试比较整个 G6 evidence 目录集合，而并行的 formal_acceptance_integration 正在创建/删除合成 revision，导致集合断言失败。该失败保留原日志；不删除断言、不修改生产实现，改为在其它 worker 结束后串行复测受影响模块。最终是否通过由 consolidated test receipt 判定，不能直接将首次失败改写为通过。此调度边界已加入政策和 invalidation matrix。

此外，首次 collector 对 formal_acceptance_integration 设置的 480 秒本地收集期限被超过，进程被停止；首次收集因此是 INCOMPLETE，不是完整通过。其它模块的完整日志保留，超时模块未持久化的 stdout 不冒称已恢复。恢复脚本仅串行补跑该模块、发生目录竞争的 OpenAI 模块，以及政策变更后的治理测试，生成引用首次失败/超时回执的 consolidated receipt；没有再次运行全部 821 项。

## 9. Historical integrity 与读取优化

restart 核验中，3,243 个非源码受保护历史文件全部匹配。R18 原 204-member source 只有两处已知局部改动；它们的原始 bytes 已从匹配原 SHA-256 的 Git blob 保存，不能把当前修复源码冒充旧 freeze。

新 verifier 要求 pinned manifest，并实际重算叶子 hash，返回 root、计数和有界 changed paths。清单 hash 不等于磁盘树 hash；一个静态 MATCH 字符串不能证明未读文件没变。

当前没有可信变更日志，因此**模型上下文读取可显著减少，但并未声称零逐文件 I/O 的 Merkle 增量验证已经实现**。未来接入 immutable object store 或完整变更日志再优化实际磁盘 I/O。现阶段保留必要的机器 hash 检查，而不让 Codex重复解释每个历史正文。

## 10. Machine state simplification 与迁移边界

已实现单一 V2 writer、独占锁、SHA-256 CAS、不可变 generation 和原子 canonical pointer。公共摘要由 payload 白名单确定性生成；测试覆盖 crash、并发、policy pin drift、counter reset 和不写旧四文件。

旧四份 machine JSON 包含历史 DAG、门、科学事实和冻结回执关联。本次保留其 bytes，不把它们粗暴压成一个小 JSON。它们现在是 V1 fact snapshots，不是“已转换好的 V2 mirrors”。

旧 writer/consumer 的全面兼容适配没有伪装成已完成；精确后续变更边界见 MIGRATION_PLAN.md。新 Codex 入口已使用 V2，不再手工同步九份相近状态。此举不会解锁 G6-08/09。

工具实现边界也保持明确：replacement_blockers 是诊断器，不是 allocation 执行器；当前 single-writer 工具只发布 offline 状态。正式付费 runner 的一次性 allocation/授权适配尚未实现，其后续源文件和验收要求列入迁移计划。不能把“政策允许满足条件后继续”误写成“自主付费续跑已经上线”。

## 11. Artifact / Git / context 最小化

普通 milestone 的三个主产物是 PRIVATE_RUN_RECEIPT、PUBLIC_SUMMARY、STATE_CHECKPOINT。源码和历史封存需要自己的 manifest；真实 Git 发布需要真实 publication receipt。原始 capture/log 不能因为“只留三个文件”被删除。

Git 只在所选源码候选验收后作一次 public-safe 显式路径提交。使用独立 index 保留当前仓库其它内容，不提交工作树中的无关缺失文件。原始 Provider request/response、rubric、私有日志和 archive 不公开。

默认恢复读取 short entry + policy + canonical pointer + checkpoint；稳定 Canonical Guide 以 digest 和摘要关联，必要时按段读取。只有具体 identity mismatch、scope ambiguity 或历史冲突才进入深层历史。

短提示词：

> 按 APCORE Governance V2 从 canonical checkpoint 恢复，在该 checkpoint 的授权范围内连续执行到硬停止点。

固定规则留在仓库，不复制到每个新对话。工具输出保留完整落盘日志，默认只显示摘要、失败和不超过 60 行的失败 tail。

## 12. 最终 A–E 回答与效率估计

A：当前执行治理在重复上下文、状态复制和普通本地 bug 的任务终止方式上存在过度审计；不能泛化成所有科学审查都过度。

B：真实质量/状态门、UNKNOWN、污染、原始证据、源绑定、completed-row 路径和实际 preflight 必须保留。

C：无 invalidation 的重复全文读取、重复状态抄写、同一已测 freeze 的第二次 full suite、同义摘要文件和每小步 Git 发布属于应消除的消耗。

| 项目 | 预计减少 | 限定 |
|---|---|---|
| 模型上下文中的重复文件读取 | HIGH | 当前入口与短状态代替 830 KB 四份重复 machine JSON；不是取消取证 |
| 无必要 full regression | HIGH | 每个源码候选一次；源码/环境变化仍须重跑 |
| 普通 milestone 的摘要 artifact | HIGH | 不包括必须保留的原始证据、源码清单和独立安全回执 |
| 续接 prompt 长度 | HIGH | 由约 3.3–4.3 KB 的已测样本缩至一条引用式指令；未声称 token 精确比例 |
| 因普通 local bug 产生的人工“继续” | HIGH | 科学/授权分叉与平台边界不能消除 |
| 实际逐文件 hash I/O | LOW / 未完成增量化 | 没有可信变更日志时保留实际叶子验证 |

D：上述是结构性工程估计，不是实际 ChatGPT/Codex 计费测量，不承诺固定额度节省比例。

E：同一授权会话可以连续完成 local bug → repair → regression → freeze → zero-provider preflight。接上 replacement validation 还必须具有有效 paid authorization、完成 harness-exclusion 裁决并解决所有已观察的质量未决项。当前 R18 与本任务不满足这一末段条件，不能宣称已跑替代验证。

本审计是当前执行者的内部工程审计，不冒称独立审稿或真实模型质量验收。
