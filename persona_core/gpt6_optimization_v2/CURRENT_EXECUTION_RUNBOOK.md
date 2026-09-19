# 当前恢复入口：陈述/证据表示已完成离线验证

唯一工作区：`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`。

CURRENT_STATE: WAITING_PROVIDER_READINESS_WITH_OFFLINE_CLAIM_EVIDENCE_VALIDATED

LAST_COMPLETED: G6-06。G6-07 的本轮通用表示实现及完整离线检查完成，G6-07 语义验收仍未通过。

RECOVERY_POINT: `persona_core/gpt6_optimization_v2/G6_07_CLAIM_EVIDENCE_ADJUDICATION.json`。

20 项新机制测试、12 个新作者样例，当前 19 个组件模块合计 279/279；旧完整 43 模块/450 项为 449 兼容通过及 1 个保留的历史源码身份错误。最终证据绑定在 adjudication 内；不要把旧的 component_final 目录名误当最终通过，当前通过的是 component_complete/TESTS.json。所有失败尝试和原始日志均保留。

本次实现按实体/模式/说话人/原文位置绑定陈述；语义候选保留阶段、条件、否定、引语及拟议关系，但不具备准入权限。自由文本不自动解析为已完成或已排除。完整检索原话替代前缀截短；放不下则在调用前拒绝。经核验的更正和文字回执在宿主摘要之外仍携带自身依据。正常对话只使用紧凑索引，实际模型自然度及字段不泄漏仍待真实生成验证。

两条历史未知请求保持原 journal、隔离和预留：rev07 N06_T4 / call_8e8d8eba92354b6bb12c8fb4e6eed8b8；rev08 N07_T3 / call_b4bb72bc78f74acaaadba41011a03cf4。没有新增生成请求，自动重试 0，没有运行中的收费执行器。不能恢复旧批次，也不能把无凭据 HTTP401 当作长生成连接已恢复。

下一步：Read CURRENT_EXECUTION_RUNBOOK.md and G6_07_CLAIM_EVIDENCE_ADJUDICATION.json. The complete current-source offline mechanism checks are finished; do not redo without source change or new evidence. Keep both historical UNKNOWNs quarantined and inspect only genuine existing receipts. No reliable long-generation transport readiness evidence is available; do not infer it from HTTP401 or create a renamed replay. Once independent readiness and a substantive new experiment basis are available, freeze a new complete source/model/configuration/price/finite-spend scope with automatic_paid_retries=0, then complete fresh external44 44/176 quote-bound review, heldout113/452 and original82/328 in order before candidate/review/new real dates. The two MAJOR findings remain OPEN and all build/product/production flags false.

本轮未知 reserve 仍为 1.285526 CNY，累计已知用量估算 3.793624 CNY；总实际费用及账单认证未知。所有构建/产品/production 标志 false；新候选日期 0/3。G6-08 至 G6-14 依赖未满足，不制造候选、独立回传或真实日期。

## 以下为保留的先前恢复记录

# 当前离线修复检查点

G6_07_CLAIM_EVIDENCE_IMPLEMENTED_OFFLINE_REGRESSION_IN_PROGRESS。通用设计及首轮日志：`resume_20260918_claim_evidence/`。已新增18项机制测试通过，正在执行全量组件检查；不能据此关闭语义问题。完整证据无法放入预算时调用前拒绝；不截断选中引文。

下一步：Finish the running claim/evidence offline component suites; repair real failures and rerun affected checks, then run complete current-source regression. Both historical batches remain non-replayable. No paid revision is ready; semantic findings remain OPEN.

以下保留前一恢复点及不可重放约束。

# 当前执行与恢复入口（2026-09-18，Asia/Shanghai）

唯一工作区：`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`。

当前目标为 `APCORE-GPT6-OPTIMIZATION-V2`。机器恢复入口是本目录 `RECOVERY_CURSOR.json`、`GOAL_STATE.json`、`TASK_GRAPH.json`、`VALIDATION_MATRIX.json` 与 `SPEND_LEDGER.json`；根目录 `PERSONA_CORE_PROGRESS.md` 首段是镜像。`operational_build_v1/TASK_STATE.json` 中的旧完成声明和旧候选日期属于历史，不能用于当前源码的验收。

## 已核实的停止点

| revision | 已提交 | 已显示 | 结果未知 | 未提交 | 当前处置 |
|---|---:|---:|---:|---:|---|
| external44_20260917_07 | 16 | 15 | 1 | 28 | 已隔离，不能恢复提交 |
| external44_20260917_08_pro | 21 | 20 | 1 | 23 | 已隔离，不能恢复提交 |

rev07 未知请求为 `N06_T4 / call_8e8d8eba92354b6bb12c8fb4e6eed8b8`；rev08 未知请求为 `N07_T3 / call_b4bb72bc78f74acaaadba41011a03cf4`。旧 `ACTIVE_RUN.json` 是保留的失败执行证据，文件存在不表示进程仍在运行。恢复时只读核对进程身份和 journal，不能删除租约后重新启动旧批次。已消费或结果未知的槽位均不得重发，历史上对另一次空回复的单次恢复授权不适用于这两条请求。

rev08 的计划标识沿用 20260917；实际开始与结束发生在 Asia/Shanghai 的 2026-09-18。20 条有效回复已完成内部非盲逐项评审：80 项中 70 PASS、10 FAIL，完整分母 176 中另有 96 项未评。未知请求不是已读到的语义失败，也不能被补成 PASS。

`R8-N02-01` 仍未关闭：新增条件被误说成排除了原来的两个候选，且过早收窄未知范围。`R8-N06-01` 仍未关闭：计划分工被扩写成已经完成的编写、修改、调试等行动，文字讨论贡献也被扩大。后续同场回答中的修正不能抹掉前面的失败。证据见 `EXTERNAL44_20260917_08_PRO_PARTIAL_ADJUDICATION.json` 和 `G6_07_REVISION08_REPAIR_BOUNDARY.json`。

## 当前源码及验证

持久检索能力已投影到实际发送的消息：内置、经过身份核验的检索服务可以说明同一对象与模式下的持久记录能力；空召回不表示记忆不存在，自定义服务的未知能力不被猜测为已实现。

rev08 后另完成了传输错误诊断改动。进程回执只增加允许列表中的异常类型和有界整数错误码，不输出异常正文、凭据、地址或请求数据；旧回执仍可读取。未知状态、费用预留、整批停批和禁止重发的逻辑未变。历史记录没有被回填错误码。一次无凭据 `GET /models` 得到 HTTP 401，只证明该时刻能够收到 HTTP 响应，不能证明历史生成请求未执行或长回复连接已恢复。

最终专项为 116/116；旧回归完整分母 450，449 项通过，唯一错误是保留的旧源码身份校验，明确归类为旧验证证据失效，没有改成 PASS。43 个模块、日志哈希及源码绑定已由候选门重新核对。当前工具准备检查为 79/79。全部是离线工程证据，不是人物语义通过证据。

传输诊断变更后的源码不能继承 rev08 的源码身份或语义结论。当前完整证据见 `G6_07_TRANSPORT_DIAGNOSTICS_ADJUDICATION.json`、`resume_20260918_transport_diagnostics/IMPLEMENTATION_AND_TESTS.json` 及其中绑定的测试日志和源码存档。

## 下一次恢复顺序

1. 读取当前五份机器状态及 Progress；对照两个 revision 的 `CURSOR.json`、`QUARANTINE.json` 和只读 provider journal。检查是否有真实存活的执行器或子进程。不要运行旧批次的 `execute`、不要改写未知结果。
2. 读取 `G6_07_REVISION08_REPAIR_BOUNDARY.json`。两类失败的关键原文已经实际进入模型请求，重复补一句同义要求没有修复依据。下一次实现前必须先冻结可检验的通用根因设计；不能用关键词、题目答案或放宽评分来解决。
3. 任何独立的新验证实验都必须有实质修复依据、冻结的完整批次、当日官方模型与费率记录、相同原题与阈值、源码归档和有限保护上限；自动付费重试为 0。不能只改 revision 名称来绕过未知请求隔离。当前没有准备好下一批收费执行。
4. 同一最终源码、模型角色和生成配置必须依次通过 external44 的 44/176、冻结 heldout 的 113/452、原始完整集的 82/328，以及原人物质量门。任何未关闭的重大问题都阻止创建当前候选。
5. 只有真实门全部满足后，才使用下述已测试工具创建新候选、生成评审材料及开始新的真实日期记录。不能继承旧候选、旧盲包、旧 Day 1 或旧开发 PASS。

只读核对现有批次可以在工作区运行：

```powershell
& 'C:\Users\skr\anaconda3\python.exe' -X utf8 -B persona_core/gpt6_optimization_v2/tools/evaluation_runner.py status --revision external44_20260917_08_pro
& 'C:\Users\skr\anaconda3\python.exe' -X utf8 -B persona_core/gpt6_optimization_v2/tools/evaluation_runner.py status --revision external44_20260917_07
```

## 外评与真实日期工具准备

| 工具 | 已实现的职责 | 尚缺的实际输入或证据 |
|---|---|---|
| `tools/candidate_day_v2.py` | 核对三个完整语义集、实际 journal、同一源码和生成配置、完整旧回归；创建隔离的零评估历史候选并做备份恢复；核对真实日期 | 三个当前源码验证集全部通过；新的候选输入清单和自然对话收费范围 |
| `tools/candidate_host_v2.py` | 在真实本地交互入口执行已冻结范围；每次核对源码和当日价格；保存输入来源、进程和原始回包绑定 | 合格的新候选及真实用户输入。工具自己的输入不能冒充用户 |
| `tools/blind_review_v2.py` | 创建中性事实材料、原始对话、空白评分表及私有映射；绑定实际外部回传 | 合格候选、完整当前证据、真实外部交付和回传。工具不发送材料，也不认证评审者身份或独立性 |
| `tools/candidate_longitudinal_v2.py` | 完整备份 checkpoint、事件与状态连续性、实际请求中收到的同一约定后续检索、重启和换模；绑定逐条人工语义评审 | 三个不同 Asia/Tokyo 日期上的真实用户互动，以及针对这些真实回复的评审 |

CLI 参数的准确接口可由各工具的 `--help` 查看。`validate-gates` 和 `create-candidate` 需要 `g6-candidate-inputs-1 / ACTUAL_CURRENT_SOURCE_EVIDENCE` 清单；其中必须绑定 source manifest、三套完整 captures/原题/评分/原生 seal/原始 journal、回归报告及裁决。当前不生成一个看似可发布的占位清单。

盲包将模型实际收到的上下文与宿主已准入事实分开，不能把只存在于 trace 的内容说成模型看过。公开包没有开发者分数、失败清单或模型元数据；原始用户或助手文本本身可能提及模型，因此不宣称完全无法识别。私有映射不交给评审者。即使回传格式及评分全部合格，也还要核验实际交付、返回和利益关系，不能把格式校验当作独立外评完成。

真实日期从新候选的 0/3 开始。进程重启、时间流逝、同日多次运行或离线模拟均不增加合格日期。输入签名证明本地记录未变，不独立证明真人身份。必须保留实际输入来源，且同一约定的后来检索须在实际发送的请求中出现。新候选创建前不能开始记 Day 1。

新的最终产品汇总还需要把实际独立回传、新三日证据和纵向语义结论绑定到同一候选；旧 R047 汇总器不能直接用于 G6。该实际汇总尚未执行，不能把工具准备计为任务完成。

## 当前完成边界与费用

`BUILD_SCOPE_COMPLETE_VALIDATION_PENDING=false`；`GPT6_CORE_BUILD_COMPLETE_VALIDATION_PENDING=false`；`PRODUCT_ACCEPTANCE_COMPLETE=false`；`production_activated=false`。外部轨保持 `WAITING_EXTERNAL`，并注明当前新包仍受内部门阻塞；真实日期轨保持 `WAITING_REAL_TIME`，新候选计数 0/3。

当前 G6 ledger 共 271 次已提交；已知用量的保守费用估算 3.793624 元，两个 UNKNOWN 的保护预留合计 1.285526 元。未知费用不当作零，也不把预留加成已发生消费；实际总费用和服务商账单认证仍未知。本次传输诊断及离线核验没有新增生成请求。

R033/R034/R035/R043、原始失败回答、冻结来源、旧回归身份校验和正式 Runtime 均保留。新验证记录继续隔离。不得声称在本轮结束后仍有收费批次在后台执行。
