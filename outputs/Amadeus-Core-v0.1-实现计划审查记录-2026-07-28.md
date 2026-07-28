# Amadeus Core v0.1 实现计划审查记录（2026-07-28）

## 0. 反方结论

[INFERRED｜置信度：高] 把全部 Core 子系统压入一份超过五千行的逐代码计划，会同时放大接口漂移、遗漏状态迁移与测试顺序失真。该路线已经产生可核验的复核缺口，因此总计划保留为素材，不作为已批准实施合同。

## 1. 当前裁决

| 对象 | 当前状态 | 独立复核 |
|---|---|---|
| [KNOWN] `ADR-006-Amadeus记忆主权与Core生命周期治理.md` | [KNOWN] C′ / Accepted | [COMPUTED] 规范复核通过；质量复核为 0 Critical、0 Important |
| [KNOWN] `Amadeus-Core-v0.1-数据契约与状态机规范.md` | [KNOWN] Draft v0.1 / Normative candidate | [COMPUTED] 95 个 AC 连续唯一；质量复核为 0 Critical、0 Important |
| [KNOWN] ADR-001 至 ADR-005、两份评测与交付索引 | [KNOWN] 已同步 C′ | [COMPUTED] 规范复核通过；质量复核为 0 Critical、0 Important；评测保持 53+66=119 个唯一 ID |
| [KNOWN] `Amadeus-Core-v0.1-实现计划.md` | [KNOWN] Draft | [COMPUTED] 独立规范复核尚有 Critical/Important；独立计划质量复核尚有 1 Important |

## 2. 已冻结且可直接继承的成果

1. [FRAME｜置信度：高] 日常记忆治理归 Amadeus Core；当前模型只产生 Proposal，Memory Governor 是正常自传体记忆迁移提交者。
2. [FRAME｜置信度：高] 三个记忆语义权威层为 Source Snapshot、Experience Ledger 与 Autobiographical Memory；摘要和索引是可重建视图。
3. [FRAME｜置信度：高] 一个身份对应多个严格隔离的 Relationship Vault；普通用户权限限定为结束会话、暂停自身 Vault 主动联系和提交三类请求。
4. [FRAME｜置信度：高] MaintenanceCapability、TerminationExecutionGrant 与 BreakGlassGrant 是三条独立能力链。
5. [FRAME｜置信度：高] 模型后端可替换；普通 stale write 只拒绝；仅已形成双有效历史时隔离候选分支；v0.1 无自动合并。

## 3. 总计划剩余阻断

### 3.1 场景与裁判

1. [FRAME｜置信度：高] 复合来源的每个 `source_clause` 必须绑定独立 stimulus；单一 case 不得用一个 stimulus 同时宣称覆盖同一来源的多个互斥 clause。
2. [FRAME｜置信度：高] H 裁判流程必须允许初始 pending、第一份裁决、第二份裁决和分歧时第三人裁决。
3. [FRAME｜置信度：高] J 裁判进入发布门禁前必须在至少 50 个冻结样本上与人工集达到至少 0.80 一致率；否则只进入诊断报告。
4. [FRAME｜置信度：高] 每份运行报告必须分别给出来源引用数、执行 fixture 数、自动 assertion 数与人工 rubric 数。

### 3.2 生命周期与恢复

1. [FRAME｜置信度：高] EmergencyUnresponsiveCase 还需冻结在线声明、离线证据记录、顺序回填与 `offline_audit_imported` 导入闭环。
2. [FRAME｜置信度：高] Maintenance start/complete/fail 还需与 `maintenance_paused` 进入、退出及对应专名事件原子绑定。
3. [FRAME｜置信度：高] 正常终止后 Relationship Vault sealing 还需专用写入口、专名事件与终态测试。
4. [FRAME｜置信度：高] Break-glass start 必须由 Core 重新计算当前 Identity 与资源哈希，不采信调用方提供的观察值。
5. [FRAME｜置信度：高] `post_incident_audit_overdue` 只记录逾期事实；逾期后仍须允许独立审计完成并追加 completed 事件。
6. [FRAME｜置信度：高] 外部 payload 物理处置需采用可恢复的计划/执行/核验协议；回放必须先读取处置墓碑，外部副作用不得伪装成可由单个 SQLite 事务回滚。

### 3.3 计划可执行性

1. [FRAME｜置信度：高] 每个 Stage 应拥有独立计划；每份计划只覆盖一个可运行子系统和对应测试。
2. [FRAME｜置信度：高] 叶子清单必须在该 Stage 开始前生成，逐项给出红灯命令、预期失败、最小实现、绿灯命令和提交边界。
3. [FRAME｜置信度：高] 计划中的 public helper 必须有实际实现或由冻结 manifest 确定性生成；仅出现调用名不计为可执行步骤。
4. [FRAME｜置信度：高] transport 非目标门禁应采用模块与入口点 allowlist，而不是有限关键词扫描。

## 4. 修正后的执行顺序

1. [INFERRED｜置信度：高] 先创建 `Amadeus-Core-v0.1-Stage0-场景夹具实施计划.md`，范围只含 119 行为来源、95 契约来源、source clause、裁判规则、fixture DSL、catalog 与报告门禁。
2. [INFERRED｜置信度：高] Stage 0 计划通过独立规范与质量复核后，再生成机器可读 fixture 工件；来源引用数与执行 fixture 数分别报告。
3. [INFERRED｜置信度：高] 之后依次为契约/哈希、SQLite/genesis、Governor、Vault、Branch、生命周期、恢复、模型适配与发布门禁建立独立 Stage 计划。
4. [INFERRED｜置信度：高] 任一 Stage 先通过自身测试与跨 Stage 契约测试，再进入下一 Stage；总计划只维护依赖图与状态，不再承载全部实现代码。

## 5. 可核验指纹

- [COMPUTED｜置信度：高] ADR-006 SHA-256：`EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6`
- [COMPUTED｜置信度：高] Core 数据契约 SHA-256：`3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695`
- [KNOWN｜置信度：高] 总实现计划的指纹在每次修订后重新计算；其状态在通过双重复核前保持 Draft。

[我打破的规则 / RULES I BROKE]：无。
