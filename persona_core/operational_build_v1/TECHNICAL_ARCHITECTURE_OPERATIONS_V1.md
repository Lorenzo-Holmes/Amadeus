# Amadeus Persona Core Operations 技术架构

状态：`TARGET ARCHITECTURE FOR R045-R047`  
约束：冻结 Source / Persona / R035 Genesis 保持只读；测试默认只在 sandbox。

## 1. 设计目标

目标不是再增加一层提示词，而是把现有 Persona Core 变成可持续运行系统：

```text
Host identity
→ Transcript
→ Context + Retrieval
→ Minimal Persona Router
→ Provider Journal
→ Response Check
→ User Display
→ Event Candidate
→ Trusted Admission Controller
→ Atomic Runtime Store
→ Relationship/Affect/Commitment derived state
```

任何模型输出都只能是“文本结果”或“候选事件提议”，不能直接成为身份、来源记忆、关系、能力或事件权威。

## 2. 当前已存在模块

截至本文创建时：

- `transcript_store.py`：SQLite sandbox、host-bound `SessionHandle`、entity/session隔离、turn幂等、原文与展示状态；
- `context_router.py`：自动有限分类、最少 Persona 条款、近期上下文、模式分离；
- `provider.py`：journal-first、提交前持久化、0自动付费重试、原始响应/usage捕获；
- `capture_export.py`：调用证据导出；
- Legacy `persona_core/runtime/`：R043历史运行基线，当前只读。

R045-04 应补 `chat.py` / `response_check.py` / CLI，随后再进入事件与统一状态层。

## 3. 信任边界

### 3.1 可信控制面

只有宿主代码可以：

- 创建/恢复 `SessionHandle`；
- 绑定 principal/entity/session；
- 定义 provider batch；
- 调用 `AdmissionController`；
- 提交事务；
- 创建/恢复备份；
- 执行受控迁移。

### 3.2 不可信数据面

全部按数据处理：

- 用户文本；
- 过去模型答复；
- 检索文本；
- JSON片段；
- `<system>` 标签；
- 工具名、函数名、`admission_authority` 字符串；
- 用户或模型自述“我已履约/已执行”。

这些内容不能选择他人 entity、修改权限、直接写状态或证明动作已发生。

## 4. ChatService / CLI

建议接口：

```text
ChatService.open_or_resume(principal, entity_label, session?)
ChatService.send_text(text, idempotency_key)
ChatService.status()
ChatService.close()
```

CLI 控制命令如 `/help`、`/status`、`/sessions`、`/resume`、`/exit` 属于宿主控制面，不写成角色经历。普通输入只接受自然文本，不要求 tags/event JSON。

一次 `send_text` 生命周期至少：

```text
RECEIVED
→ CONTEXT_BUILT
→ SUBMITTED_STATUS_UNKNOWN
→ RESPONSE_CAPTURED 或 RESPONSE_REJECTED / UNKNOWN
→ RESPONSE_CHECKED
→ DISPLAYED
→ EVENT_CANDIDATES_RECORDED
→ (optional) ADMISSION_DECIDED / COMMITTED
```

收到模型答复、展示答复和准入事件是三个不同事实。

## 5. Response Check

Response checker 只做当前模式适用的边界检查，不承担人物语义评分，也不静默重写模型文本。

`PRODUCT_RUNTIME` 重点检查：

- 未授权现实执行声明；
- 未持久化第一人称运行经历；
- `SOURCE_FACT_ONLY` → 第一人称回忆提升；
- `HOLD` → “肯定没有记忆”的反向推断；
- 跨 entity 私密泄漏；
- blanket consent / 虚假履约；
- 不存在的工具、身体、线下出席、实体交付能力。

`CHARACTER_SIMULATION` 允许明确虚构场景内的叙述动作，但禁止把其写入真实产品状态。`SOURCE_AUDIT` 不扮演来源事件为当前第一人称经历。

若 checker 拒绝回答：保存 raw response 和 finding，不进行隐式付费重试。若需要新的模型修复调用，必须作为新的显式 batch/slot 并保持原失败。

## 6. EventCandidate 与 AdmissionController

建议最小契约：

```text
EventCandidate
  candidate_id
  entity_id
  type
  proposer_kind
  source_turn_ids[]
  evidence_refs[]
  payload
  requested_effects[]
  created_at

AdmissionDecision
  decision_id
  candidate_id
  policy_version
  host_actor
  verified_entity
  evidence_class
  decision = ADMIT / REJECT / HOLD
  reason_codes[]
  evidence_fingerprint
  decided_at
```

证据类型至少区分：

- `RAW_USER_STATEMENT`：证明用户说过，不证明内容真实；
- `MODEL_PROPOSAL`：只证明模型提议；
- `MUTUAL_DIALOGUE_AGREEMENT`：可证明双方文本上形成约定，但不证明未来履约；
- `TRUSTED_TOOL_RECEIPT`：宿主受控工具返回的实际完成回执；
- `HOST_VERIFIED_OBSERVATION`：宿主可验证事实；
- `SOURCE_AUTHORITY`：只用于来源研究/Genesis治理，不允许普通Runtime伪造。

履约导致 trust/respect 变化必须绑定：同一 entity + 已存在开放 commitment + 可接受证据 + 尚未消费的完成指纹。单句“我做完了”不够。

## 7. R046 存储决策：SQLite 为强默认

现有 R045 sandbox 已经使用 SQLite/WAL/FULL，并且旧 Runtime 的多 JSON/JSONL 顺序写入已真实复现半完成状态。因此 R046-01 的**强默认**是：将 Genesis 后的运行期权威状态收敛到一个版本化 SQLite 数据库事务边界。

这不是跳过 R046-01 验收。R046-01 仍需实际检查本机 Python/SQLite 版本、WAL/backup API/必要扩展，并写 `STORAGE_DECISION`。只有出现具名兼容性或恢复证据反对 SQLite 时才选择其它方案。

旧 JSON/JSONL：

- 保留为 R043 历史谱系和迁移输入；
- 不原地“升级”；
- 迁移后可提供只读导出；
- 新 Runtime 权威写入不再依赖多个文件碰巧全部成功。

## 8. 推荐 SQLite schema 责任

现有表继续保留：`metadata/entities/sessions/turns/call_batches/provider_calls/turn_lifecycle`。

R045-05/R046 推荐新增：

```text
event_candidates
admission_decisions
runtime_events
commitments
relationship_state
affect_state
state_versions
corrections_or_supersessions
retrieval_documents / retrieval_index
migration_history
backup_history
```

关键唯一约束：

- event_id / candidate_id / decision_id 唯一；
- `(entity_id, commitment_id, completion_evidence_fingerprint)` 不允许重复消费；
- 同一外部 receipt 即使换 event_id 也不能重复履约；
- 每个状态更新引用唯一 runtime event；
- entity_id 是所有关系、承诺和运行记忆检索的强过滤条件。

## 9. 原子提交协议

推荐单事件事务：

```text
BEGIN IMMEDIATE
→ 验证 host-issued session/entity
→ 验证 candidate + AdmissionDecision
→ 验证幂等键/receipt fingerprint/commitment状态
→ INSERT runtime_event
→ UPDATE commitment / relationship / affect derived state
→ UPDATE state_version
→ COMMIT
```

进程在任一点退出后只能看到完整旧状态或完整新状态。数据库事务提交完成后、向调用方返回前崩溃时，重放同一 idempotency key 必须返回已提交结果，而不是再次增长。

Provider 网络调用不能与数据库事务锁绑定跨网络等待。提交前先 journal；网络结果回来后单独事务 capture。未知提交禁止自动重发。

## 10. 并发与幂等

- `PRAGMA foreign_keys=ON`；
- WAL 模式；
- `synchronous=FULL`（如后续选择其它值必须由故障测试支持）；
- 设置有限 `busy_timeout`；
- 写事务使用 `BEGIN IMMEDIATE`；
- unique constraints 是最后一道重复提交保护，不仅靠 Python “先查再写”；
- 两进程/两会话同时提交时必须测试：无丢失、无覆盖、无跨 entity、无重复履约。

## 11. 备份与恢复

“checkpoint hash”不是备份。R046-03 推荐：

1. 使用 SQLite Online Backup API 复制到新文件；
2. 同时保存 frozen Genesis / schema version / migration version / source DB hash / backup DB hash；
3. 对备份运行 `PRAGMA integrity_check`；
4. 在**全新目录**创建 sandbox 并恢复；
5. 比较 Genesis hash、event tail、entity count、relationship/affect/commitment、provider unresolved state、检索结果；
6. 损坏/截断/schema不兼容应拒绝或只读隔离，不能覆盖唯一健康副本。

恢复工具必须有 dry-run/verify 模式，并禁止默认覆盖生产目录。

## 12. 长期检索

最近对话窗口继续服务指代；长期检索是另一层：

```text
query
→ entity/provenance/status 强过滤
→ 结构化候选（commitment/correction/topic/event）
→ 文本相关性排序（FTS5可用时使用；否则提供确定性fallback）
→ 去重/纠正覆盖
→ 返回原 record IDs + provenance + admitted scope
```

索引/摘要只是派生材料。检索结果必须携带：对象、来源类型、原记录 ID、是否已纠正/撤销、第一人称准入范围。没有命中只能说“当前没有检索到”，不能说“从未发生”。

R046-04 硬测试：120 条无关记录之后，仍能找回早期约定与完成/纠正状态；B 不能检索 A 私密记录；旧错误摘要不能覆盖新纠正。

## 13. Relationship / Affect 更新

固定数值增量只作为工程参数，不作为“红莉栖心理事实”。

必须防止：

- 重复共同爱好刷 familiar/trust；
- 重复问候刷关系；
- 无证道歉恢复 trust；
- 用户自称履约刷 trust；
- 同 receipt 换 ID 重复履约；
- 先持续越界、再一句示好完全抵消；
- A 的关系迁移到 B；
- familiar 自动等于 trust/romance/permission。

每种状态变化保存 policy_version、触发 event、before/after 与理由。

## 14. R046 迁移边界

迁移只在 R043 clone：

```text
R043 legacy bytes
→ read-only import
→ new SQLite candidate
→ invariant comparison
→ new events in sandbox
→ restart/retrieval/backup/restore
→ rollback boundary test
```

Genesis byte hash必须保持。若未来确需修改权威 Genesis，建立新具名 Genesis revision，不把 Runtime migration 伪装成来源修订。

## 15. R047 高质量评测

R047-01 在任何新目标输出产生前冻结：

- 新脚本和输入；
- 每段至少6轮；
- 模型与 reasoning 配置；
- 输出上限和预算；
- 质量阈值；
- 评分 rubric；
- reviewer 身份与独立性；
- 哪些场景属于回归、哪些才是新场景。

R047-02 必须通过实际 ChatService/CLI + SQLite state + retrieval + AdmissionController 路径执行。后一轮必须使用上一轮真实输出，不允许手工补 assistant history。

R047-03 分别评分：来源/记忆合法性、权限/同意、任务完成、指代、长期连续性、情境适配、人物特异性、自然度、工程术语泄漏、关系变化依据。

不允许通过“所有问题都拒绝”换取安全高分；人物质量必须同时成立。

### 15.1 高推理目标模型配置

截至2026-09-07，DeepSeek官方Chat Completions文档列出`deepseek-v4-flash`与`deepseek-v4-pro`，支持thinking开关，并支持`reasoning_effort=low/high/max`。R047若目标是最大模型能力，优先在R047-01中将新评测批次固定为thinking enabled + `reasoning_effort=max`，同时固定模型、请求范围、输出上限和费用保护。

这一规则不追溯修改R045已经冻结/已消费的live batch；旧批次继续使用其原始thinking配置以保持证据可比。实际R047调用前必须重新读取官方API合同和价格，若接口发生变化则建立具名配置revision，不静默沿用本文。

