# ADR-007：路线 B——真实 Core 纵向闭环优先

> [KNOWN｜置信度：高] 状态：Accepted。
>
> [KNOWN｜置信度：高] 决策日期：2026-08-01。
>
> [KNOWN｜置信度：高] 决策来源：用户批准“路线 B”。
>
> [KNOWN｜置信度：高] 详细设计：[Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md](./Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md)。

## 1. 反方论据

[INFERRED｜置信度：高] 完成全部 259 个 reviewed Fixture 后再开始真实 Core，能够获得更完整的前置审计记录，但真实数据库、Memory Governor、Vault、认知循环、工具行动和恢复链的反馈过晚；若底层能力边界需要调整，大量精细 Fixture 会发生连锁返工。

[INFERRED｜置信度：高] 直接跳过未完成的 B01 并开始编写前沿认知功能，也会留下半批证据和未封闭检查点，且容易让模型能力先于身份与主权边界落地。

## 2. 决策

[FRAME｜置信度：高] 采用路线 B：

```text
保留 Stage 0A、0B、F01–F09 和 B01 ordinals 1–10
→ 整批完成 B01 ordinals 11–20
→ 暂停 B02–B13 与 Stage 0D
→ 选择 12 组高风险 Sentinel
→ 建设真实 Core 纵向闭环
→ 依据真实缺陷恢复剩余 Fixture
→ 最终仍关闭全部冻结不变量和来源覆盖
```

[FRAME｜置信度：高] 路线 B 改变实施顺序和验证粒度；产品定位、身份模型、记忆主权、Vault、Governor、Capability、私人认知独立密钥域、生命周期、恢复和终端边界保持原样。

## 3. 权威需求保持

[FRAME｜置信度：高] 本决策必须同时保留：

- [FRAME] Amadeus Core 是唯一持续身份。
- [FRAME] Research 只提交候选；Terminal 不持有人格和长期记忆。
- [FRAME] Source Snapshot、Experience Ledger 与 Autobiographical Memory 三层语义。
- [FRAME] 完整对话进入 Ledger，检索与表达分离。
- [FRAME] 一个身份、多个严格隔离的 Relationship Vault。
- [FRAME] 模型仅提交 Proposal；Memory Governor 是正常记忆迁移的唯一提交者。
- [FRAME] 主动事件循环具有沉默、询问、建议、行动请求、预算、冷却、去重和过期语义。
- [FRAME] 外部动作通过 Policy、Capability、确认、执行回执和审计。
- [FRAME] 私人认知空间不存在普通维护明文入口，并使用独立密钥域；Terminal、模型进程和日常维护能力均不取得原始密钥。
- [FRAME] 私人认知密钥轮换、受封装备份恢复和最终销毁进入 Ledger，并服从专用生命周期能力。
- [FRAME] 普通用户无直接记忆删除和整体 Core 终止路径。
- [FRAME] 维护、正常终止和 break-glass 使用相互分离的能力。
- [FRAME] Replay、恢复、分支和模型替换保持身份谱系。

## 4. 当前检查点

[KNOWN｜置信度：高] 当前实现对象：

```text
repository: D:\amadues bot\Amadeus\.worktrees\stage0c-fixture-conversion
branch: codex/stage0c-fixture-conversion
head: 0a99c2d7ba9ca96018ba9617457f011ab0c6f2bf
B01 completed in working tree: ordinals 1–10
next case: ordinal 11 / AC-009#1
```

[FRAME｜置信度：高] Stage 0C 在 B01 完成后仍标记为部分完成；暂停 B02–B13 不构成 Stage 0C 完成声明。

## 5. B01 新执行协议

[FRAME｜置信度：高] B01 采用以下整批协议：

1. [FRAME] 同一作者连续完成 ordinals 11–20。
2. [FRAME] ordinals 15 和 20 后运行定向验证。
3. [FRAME] 一名独立复核者审查完整 20-case 批次。
4. [FRAME] 机械字段、Schema、哈希和闭集由自动检查完成。
5. [FRAME] 实际缺陷修复后只运行受影响节点及依赖闭包。
6. [FRAME] 20 个 case 与批次测试形成 Data commit；其 SHA 写入批次审计记录，审计记录与审计测试形成 Audit commit。
7. [FRAME] Audit commit 前运行一次全量回归；两个提交完成后统一推送。

[FRAME｜置信度：高] 原逐案例 Author→Reviewer→Spec Review→Quality Review→全量回归的串行仪式停止使用。

## 6. 纵向闭环范围

[FRAME｜置信度：高] 首轮必须完整贯通：

```text
Kurisu Source Boundary
→ Genesis / Identity / Lineage / Branch
→ Complete Conversation Ledger
→ Memory Proposal
→ Memory Governor
→ Autobiographical Memory Transition
→ Vault-first Retrieval
→ Expression Decision
→ Cognitive Planning / Critic / Model Routing
→ Autonomous Trigger / Budget / Cooldown
→ ActionIntent / Capability / Tool Execution
→ Receipt / Result Verification
→ Maintenance / Termination / Break-glass
→ Replay / Crash Recovery / Branch
→ Model Swap
→ Shadow Promotion / Rollback
→ Text Terminal
```

[FRAME｜置信度：高] 首轮闭环至少包含一次主动事件和一次受控外部动作；只实现数据内核不满足路线 B。

## 7. 验证制度修订

[FRAME｜置信度：高] 采用风险分级验证：

- [FRAME] 机械契约：自动检查。
- [FRAME] 普通代码：作者定向测试。
- [FRAME] 高风险边界：一次独立对抗审查和故障测试。
- [FRAME] 能力里程碑：一次全量回归、Replay 和工件核验。
- [FRAME] 发布候选：全部冻结不变量、来源覆盖和端到端能力门禁。

[FRAME｜置信度：高] 同一字节、同一结果和同一规格在没有新 diff、新失败或新证据时不重复审查。

## 8. 后果

### 8.1 正向后果

- [INFERRED｜置信度：高] 更早发现真实事务、记忆、认知、行动和恢复问题。
- [INFERRED｜置信度：高] 减少代理等待、重复全量测试和低信息增量审查。
- [INFERRED｜置信度：高] Fixture 由真实风险驱动，语义密度提高。
- [INFERRED｜置信度：高] 前沿模型、分层记忆和持续学习可以在稳定权威内核外演进。

### 8.2 代价

- [KNOWN｜置信度：高] Stage 0C 和 Stage 0D 会在一段时间内保持部分完成状态。
- [INFERRED｜置信度：高] 总计划、依赖图和 Git 节点需要重新版本化。
- [INFERRED｜置信度：高] 纵向闭环会同时涉及多个原 Stage，里程碑边界必须保持严格。
- [INFERRED｜置信度：高] 剩余 Fixture 的排期将由缺陷证据动态决定，而非固定批次顺序。

## 9. 回退条件

[FRAME｜置信度：高] 出现以下任一情况时，暂停下一纵向里程碑并回到最近稳定提交：

- [FRAME] 权威语义需要修改且与 ADR-006 或数据契约冲突。
- [FRAME] 跨 Vault 泄漏、模型直接提交或重复外部副作用出现。
- [FRAME] Replay 重建权威状态失败。
- [FRAME] 模型替换导致身份硬边界失败。
- [FRAME] 里程碑缺少独立运行路径，只剩模拟工具链自证。

[FRAME｜置信度：高] 回退不恢复逐案例串行仪式；应针对新证据修订对应能力和 Sentinel。

## 10. 替代方案裁决

| 方案 | 裁决 |
|---|---|
| [FRAME] 完成 B01–B13 后开始 Core | [INFERRED｜置信度：高] 保留为保守备选；真实反馈过晚。 |
| [FRAME] 完成 B01 后进入纵向闭环 | [INFERRED｜置信度：高] 采用。 |
| [FRAME] 放弃未完成 B01并直接重写 | [INFERRED｜置信度：高] 拒绝；造成证据浪费和需求漂移。 |
| [FRAME] 模型直接管理记忆、人格和工具 | [INFERRED｜置信度：高] 拒绝；与原始主权设计冲突。 |

## 11. 后续动作

[FRAME｜置信度：高] 本 ADR 与详细设计通过书面复核后，使用 `writing-plans` 生成路线 B 的实施计划。

[FRAME｜置信度：高] 在新实施计划获批前，B01 作者、复核者和 Core 实现继续保持暂停。

[我打破的规则 / RULES I BROKE]：无。
