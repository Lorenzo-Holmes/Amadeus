# Amadeus Core v0.1 Stage 0B 实施计划审查记录（2026-07-29）

## 0. 反方结论

[INFERRED｜置信度：高] 直接沿用总实现计划的旧 Stage 0 会造成范围与证据混淆：它早于 Stage 0A 的冻结产物，曾把 Core 空 oracle 映射为 D，并且只显式拆出少数复合来源。该路径不作为 Stage 0B 执行依据。

[KNOWN｜置信度：高] 本次审查对象是 [Stage 0B 来源裁决实施计划](Amadeus-Core-v0.1-Stage0B-来源裁决实施计划.md)。审查依据是 Stage 0A 已生成的四份 JSON、Stage 0A 计划第 9 节和现有 Core/评测规范。

## 1. 审查方法

[COMMON｜置信度：高] 使用反例驱动静态审查：逐项检查输入身份、来源集合、oracle 降级、人工裁决边界、原子性、生成确定性、readiness、Stage 0C 越界、测试与 Git 节点。

## 2. 审查结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| [FRAME] 四份输入身份 | 通过 | [COMPUTED] 计划逐项固定 path、SHA-256、bytes；与当前文件重算值一致 |
| [FRAME] 214 项叶级覆盖 | 通过 | [COMPUTED] Task B2 要求从三份 Stage 0A 数据 exact join 并生成 214 项 checklist |
| [FRAME] 95 个 Core oracle | 通过 | [COMPUTED] 禁止默认 D；要求逐项 explicit assignment 与来源特定 rationale |
| [FRAME] 119 个行为 oracle | 通过 | [COMPUTED] strict schema 要求保留 source-declared oracle，禁止降级 |
| [FRAME] 214 个 atomicity 决策 | 通过 | [COMPUTED] 每项均须 atomic/composite、rationale 和连续 clause；无自动标点拆分 |
| [FRAME] source binding | 通过 | [COMPUTED] exact ID/binding set、decision hash 与 clause content hash 都进入门禁 |
| [FRAME] readiness 语义 | 通过 | [COMPUTED] 只允许 source adjudication ready；case/catalog/release 固定 false |
| [FRAME] Stage 0C 边界 | 通过 | [COMPUTED] 明确不生成 executable fixture，并把 case binding 延后到下一计划 |
| [FRAME] 可复现性 | 通过 | [COMPUTED] checklist/write/check、canonical JSON、双写 hash 与 no-write check 均有测试任务 |
| [FRAME] Git 可接替性 | 通过 | [COMPUTED] 七个任务均给出 commit 边界，最终要求执行记录、推送与 clean tree |

## 3. 已阻断的错误路线

1. [INFERRED｜置信度：高] “Core 规范是确定性的，所以 95 项全设 D”会漏掉跨重启、并发、时间、表达或诊断边界；计划已禁止 source-group 默认映射。
2. [INFERRED｜置信度：高] “按中文分号拆 clause”会把同一断言的并列表述误拆，也会漏掉无分号的多阶段行为；计划将拆分保留为人工决策。
3. [INFERRED｜置信度：高] “source manifest 已覆盖 case”会把来源级证明误报为可执行覆盖；计划保持三个下游 readiness 为 false。
4. [INFERRED｜置信度：高] “只复核 EXIT-02/EXIT-06”会把旧计划候选当成完整集合；计划要求 214/214 并只把两项列为专项复核。

## 4. 非阻断 backlog

- [FRAME｜置信度：高] Stage 0C 决定 fixture DSL、case 合并与 source-clause-to-case binding。
- [FRAME｜置信度：高] Stage 0D 执行 H/J 校准与 reviewer 过程，不在 Stage 0B 提前设计。
- [FRAME｜置信度：高] GitHub 默认分支整合与仓库可见性核验放在整个当前执行批次的最终交接门。

## 5. 裁决

[INFERRED｜置信度：高] 计划可执行。开始条件是当前功能分支 clean、四份输入 hash 仍匹配；完成条件以计划第 6 节全部门为准。

[我打破的规则 / RULES I BROKE]：无。
