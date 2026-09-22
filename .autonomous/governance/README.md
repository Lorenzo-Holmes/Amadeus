# GOVERNANCE_BOOTSTRAP_REPORT — 2026-09-18

GOVERNANCE_VERSION: `AMADEUS_AUTONOMOUS_RD_GOVERNANCE_V1`  
GOVERNANCE_RUN_ID: `GOV-20260918T035326+0900-BOOTSTRAP-01`  
CONTROL_PLANE_HEALTH: `DEGRADED_SCHEMA_REVIEW_AND_EVIDENCE_GAPS`

## 入口与事实顺序

控制入口：[Issue #6 — [AUTO-R&D] Amadeus Autonomous Control Plane](https://github.com/Lorenzo-Holmes/Amadeus/issues/6)。沿用现有 `autonomous/orchestrator-state` 分支和 [Draft PR #3](https://github.com/Lorenzo-Holmes/Amadeus/pull/3)，没有建立第二套任务分配权威。

实时 GitHub refs / PR / commit 与当前 `.autonomous/AUTONOMOUS_TASK_STATE.json` 决定并发事实。本目录是带观察时间的治理报告，不是任务领取接口，不授予 memory、Persona、provider 或生产状态权限。不要从旧快照复制 OWNER、LEASE 或计数覆盖当前控制文件。

## 本轮实际产物

| 产物 | 用途 |
|---|---|
| [初始治理快照与完整地图](https://github.com/Lorenzo-Holmes/Amadeus/blob/abcb6dd7be5f8312b10889b2f5545ffd143c65d0/.autonomous/governance/GOVERNANCE_BOOTSTRAP_20260918.json) | 观察截至 2026-09-18 03:53:26 Asia/Tokyo；30 项能力、16 个架构边界、12 条 claim/failure/test/oracle/evidence 链，早期六项研究注释和 GOV-DEC-001..003 |
| [最终并发对账增补](https://github.com/Lorenzo-Holmes/Amadeus/blob/8a2b02336fa10b432619547b6abe3214c8a14189/.autonomous/governance/GOVERNANCE_FINAL_RECONCILIATION_20260918.json) | 观察截至 2026-09-18 08:02:49 Asia/Tokyo；覆盖初始快照已过时的活动数、READY 清单及账本数量，记录 GOV-DEC-004 |
| 本 README | 人类可读报告、地图/日志组合视图入口、独立审查交接 |

地图使用 `columns`、`rows` 和 `record_defaults` 表达完整记录。原始研究、决策、任务文件继续保留在 `.autonomous/`，本目录的注释不是替代账本。检索研究或重开决策前，必须同时读当前原始账本及本目录适用增补。

## Repository reconciliation

默认 `main` 在最终 refs 回读仍为 `a6ffaa388ebdab03620070c3990ffc9788425e8f`。

CURRENT_BASE_SHA 为 `34ae8a3d95dbe1cc565893b81306be235a36a4cb`，对应 `codex/persona-core-operations-v1-20260917` 的可复现公开 Persona 源码快照；它不是经核实的当前 G6 canonical workspace。

最终对账绑定的控制源码 ref 为 `abcb6dd7be5f8312b10889b2f5545ffd143c65d0`，任务 blob 为 `06791760284f0ab3167d5550f283c570deb49412`。本轮添加治理文件时，其他 Orchestrator 已更新任务/研究/决策记录；因此追加最终对账，没有用初始快照覆盖它们。

PR #1–#5 仍是本轮看到的公开待审工作。PR #1 的 209 文件快照、PR #2 的离线架构/引用契约、PR #4 的 B01 研究和 PR #5 的 C01 审计器，不是当前 G6 已通过产品验收的证明。PR #3 是共享治理分支的审查入口；本次提交不自动合并它。

## Persona Core 状态恢复

Historical Operations 的机器状态仍是 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING / R047-04`。其历史完成与证据应保护，不重做、不删除失败，也不能继承成当前 G6 验收。

当前公开 progress 活动块描述 `external44_20260917_07`：15 条显示回复，60 项已评中 46 PASS / 14 FAIL，另 116 项未评，N06_T4 保持 UNKNOWN。DEC-G6-009 描述的是较早的 revision06：159 PASS / 17 FAIL，不是同一轮。两者都是仓库公开 checkpoint 的陈述，本轮没有获得原始当前 provider ledger 来独立重算。

当前 G6 product acceptance 与 production activation 仍为 false，新候选真实自然日公开状态为 0/3。R005 原始 provenance closure 仍报告 NOT_ENOUGH_EVIDENCE。不得重发 UNKNOWN、用新 slot/model/ID 绕过未知提交、伪造自然日或从摘要重建原始凭证。

公开 README 明确不包含完整 raw captures、数据库、review returns 和自然日产物。G6 canonical 路径与原始证据的可访问性缺口，不代表原 Windows workspace 已丢失数据。需要经授权的私密证据访问和 source/revision/ledger 绑定，而不是向公共仓库上传原始对话。哈希一致也不是语义验收。

## 最终任务、租约与重复检查

| 字段 | 08:02:49 Asia/Tokyo 的对账结果 |
|---|---|
| ACTIVE_IMPLEMENTATION_TASKS | C02，1 项：代码写入型离线 memory-poisoning evaluation |
| ACTIVE_RESEARCH_TASKS | 0 |
| READY_TASKS | A02、B02、D01；本轮未替其追认新 V1 价值门 |
| REVIEW_TASKS | A01、B01、C01、REVIEW-PR-1、REVIEW-PR-3 |
| BLOCKED_TASKS | HOLD-G6-07-CANONICAL |
| WRITE_SET_CONFLICTS | 当前活动写集未发现重叠；新领取必须再查 |
| DUPLICATE_TASKS_FOUND | 本轮未新增确认的重复任务；历史拒绝策略不冒充新发现 |
| SUPERSEDED_TASKS | 本轮未判定任务被替代；初始活动数和账本数量已被最终对账替代 |
| STALE_LEASES | 观察时没有过期活动租约；本轮未释放任何租约 |

C02 租约截至 2026-09-18 08:27:00 Asia/Tokyo。其分支仍在 baseline，无 PR；不能由此断定进程停工、伪造心跳或抢占租约。到期后也必须再看 owner、提交、PR 和交接证据。

有三个可用 implementation 槽位并不要求创建三个任务。当前 Control Plane 的 NEXT_ACTION / AUTO-DEC-011 把纯研究也算入总四人上限，而用户 Governance V1 指定的是最多四个代码写入 implementation Worker、纯研究/只读 Audit 不计入。此处明确记录口径冲突，不静默重写 allocation。

## 地图、研究与决策状态

CAPABILITY_MAP_CHANGES：建立 30 项源代码定位和成熟度记录；源码存在不标成产品 VALIDATED。最终仅追加任务交叉引用：C02 → memory/security，A02 → permission enforcement，B02 → forgetting/persistence，D01 → observability。RUNNING/READY 不升级为已交付能力。

ARCHITECTURE_DRIFT：记录 runtime/admission/growth 从 provider.py 导入 generic canonical/digest 的结构耦合。没有据此断言 provider-specific Persona 语义污染，也不提出纯美观的 utility 抽取。未在本次检查中确立第二个活动 Memory authority；未集成的 vNext 设计不冒充生产系统。

EVALUATION_GAPS：当前 G6 source/private evidence；语义失败与未评项目；B01 growth-support freshness 的真实装配 runtime oracle；独立验收与新真实日期。C02/A02 尚未产生可用于关闭这些缺口的交付。PR #2 报告的 40 个离线测试、PR #5 报告的 38 个合成测试、B01 的六个 module-boundary 观察均不是本轮复跑，更不是产品验收。

RESEARCH_LEDGER_CHANGES：当前原账本已有 R-20260918-01..16，共 16 项。初始治理 JSON 仅对最初六项做注释；其余十项是并发 Orchestrator 后续加入，最终对账保留其 C02/A02/B02/D01 或 deferred 关联。本轮没有独立复核这些论文/项目的实时内容、日期或许可证，没有引入任何外部代码。前三项与 B01 的书目差异继续列为未核实冲突，不把另一个 Worker 的修正自动当真。

DECISION_LOG_CHANGES：当前原日志为 AUTO-DEC-001..011；本轮的 GOV-DEC-001..003 在初始 JSON，GOV-DEC-004 在最终 JSON。AUTO-DEC-004 的早期 A 占用叙述和初始治理零活动观察都有各自时间范围，不是当前租约。本轮没有删除或重写原决策日志。

## 未关闭的治理缺口

Task Registry 尚未整体完成 V1 schema 升级：部分 type/risk/value/forbidden paths/heartbeat/review/novelty 字段缺失或不统一。当前压缩后的 A01/B01/C01 记录也少了早期记录中的详细 EVIDENCE 与 lease-history 直接引用；Git 和 PR 历史仍存在，不应夸大为证据已删除。应在独立审查的 registry 更新中补齐可追溯指针，不能编造历史心跳或批准。

SECURITY_ALERTS：最终 branches 读取返回 11 个分支，均 protected=false；此前 rulesets 读取为空。书面 integration gate 不等于 GitHub 已强制执行。本轮没有改保护设置，也没有认证整个仓库无安全问题。

IDENTITY_ALERTS：R005 provenance 与当前 G6 语义验收未关闭。任何未来 Genesis、Constitution、cutoff、自传/identity/provenance authority、破坏性迁移或生产激活变更，均需适用的明确用户裁决；没有新 RED 实施被本轮创建或放行。

Integration 仍须实现、targeted tests、regression、acceptance evidence、自审、duplicate/write-conflict recheck、独立审查、文档和 Control Plane 更新；YELLOW 须 APPROVE_FOR_INTEGRATION，RED 否则 BLOCKED_NEEDS_USER_DECISION。本报告不构成批准。

## TOP_NEXT_ACTIONS

1. 通过授权访问补齐当前 canonical source 与私密原始证据绑定，保持 N06_T4 UNKNOWN 与 R005 uncertainty。
2. 审查现有 PR #1–#5，补齐 registry schema、历史指针与并发口径；保留 C02 有效租约，复用 C01/A02/C02，不新造等价审计器。
3. 先审 B01，再决定真实 runtime 最小实验；沿用 B02/D01 的现有研究边界，经过 source/novelty/value/oracle 门后再考虑实施。

STOP_CONDITIONS：WAITING_FOR_DEPENDENCY、WAITING_FOR_REVIEW、WAITING_FOR_REAL_WORLD_EVIDENCE、WAITING_FOR_NATURAL_TIME；没有充分依据的新实施项为 NO_SAFE_NEW_TASK。

## 周期安排

已创建每周架构复盘与月度治理整理任务，不是每小时扩张 Builder。每周复盘自 2026-09-25 起于周五上午运行；月度整理自 2026-10-18 起于每月 18 日上午运行。均使用 Asia/Tokyo，以 08:00 为弹性调度基点、允许前后一小时。每次重读 GitHub，最多三个优先方向；月度整理仅做非破坏性元数据整理与候选交接，保留全部历史证据/失败/决策，不直接删分支或生产数据。调度已创建，未来实际执行结果需由各轮证据证明。

## 执行边界与回滚

本轮业务代码、Persona 状态、历史 evidence 修改为 0；项目 provider 调用、UNKNOWN replay、自动合并、新 implementation task 均为 0。本轮未执行 runtime/product tests，未完成独立产品审查；完整 git checkout 因 DNS 失败不可用。GitHub connector 的 pinned source/file readback 可用；没有声称执行全量 JSON 程序校验、完整 protected-tree hash 认证或 Windows/生产恢复测试。

本轮仓库改动仅为本目录三个新增治理文件，外加 Issue #6 入口与 PR #3 交接评论。原 TASK_STATE/研究/决策文件未被本轮改写。暂不采用这些治理增补即可停止其使用；如需撤销已合并内容，使用新的、受审查的 revert commit，并保留原历史。不得 force-push、删除失败证据或通过回滚触发 UNKNOWN 请求。
