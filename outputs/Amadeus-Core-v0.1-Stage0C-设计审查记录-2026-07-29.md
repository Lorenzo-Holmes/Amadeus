# Amadeus Core v0.1 Stage 0C：设计审查记录

> [KNOWN｜置信度：高] 日期：2026-07-29  
> [KNOWN｜置信度：高] 结论：APPROVED / Frozen  
> [KNOWN｜置信度：高] 对象：[Stage 0C 夹具转换与 S Sandbox 设计](Amadeus-Core-v0.1-Stage0C-夹具转换设计.md)

## 0. 反方结论

[KNOWN｜置信度：高] 设计最初并不具备冻结条件。首轮与第二轮审查发现 nested DSL、ActionEnvelope、handler/driver、state/effect、receipt、smoke evidence 和 Windows publication recovery 均存在可导致双重实现、假绿或恢复停滞的缺口。

[COMPUTED｜置信度：高] 最终冻结前审查结果为：

- [COMPUTED｜置信度：高] 敌对实现复审：APPROVED，既有反例全部闭合。
- [COMPUTED｜置信度：高] 规格定点复审：APPROVED，0 BLOCKER / 0 IMPORTANT。
- [COMPUTED｜置信度：高] 最后一项修订只固定 smoke outcome 的 subject_id 映射并为 publication result 补入 result_sha256；规格复审确认三类 result hash 已可机械判定。

## 1. 冻结输入复核

| 输入 | [COMPUTED] bytes | [COMPUTED] SHA-256 |
|---|---:|---|
| `fixtures/stage0b/generated/source_clause_manifest_v0_1.json` | 252478 | `DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C` |
| `fixtures/stage0b/generated/stage0b_report_v0_1.json` | 585 | `F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8` |
| `outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md` | 79488 | `3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695` |
| `outputs/ADR-004-Amadeus工具权限与执行治理.md` | 25191 | `2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125` |

[COMPUTED｜置信度：高] Stage 0B 当前集合为 214 sources、259 clauses、75 个 S sources、98 个 S clauses、51 个含 H/J 的 clauses 和 55 个 H/J requirements。

## 2. 审查闭环

| 审查面 | [KNOWN] 初始风险 | [COMPUTED] 冻结合同 |
|---|---|---|
| Case DSL | root/nested schema 与示例不闭合 | AC-001#1 golden case、structural object / JSON map 分离、sequence/ID/rubric 门禁 |
| Envelope | ADR-004 字段与 Core 版本语义漂移 | 28 字段 ActionEnvelope、逐目标唯一 expected_versions、`absent→0` 命令哈希归一 |
| Handler | params-only 与 typed-step 协议分叉 | setup/stimulus/assertion 三协议、静态 registry、可重算 manifest provenance |
| State/effect | state layout、patch、effect ID 与 matcher 不唯一 | 固定 state root、StatePatchOperation、EffectSeed→ObservedEffect、EffectPattern |
| Receipt/replay | hash scope、phase、idempotency 与错误路径分叉 | StepExecution、精确 hash preimage、canonical cache address、phase/result 交叉不变量 |
| Smoke evidence | 声明式计数可伪造执行 | canonical test matrix、callback events/outcomes、充要 passed 条件、原子 evidence 发布 |
| Windows publish | rename 与 journal state 间崩溃窗口 | logical-root tree hash、预置锁载体、temp 规范化、state×disk 恢复矩阵 |

## 3. 最终验证证据

- [COMPUTED｜置信度：高] Golden JSON：1 个 block，可解析，重复键为 0。
- [COMPUTED｜置信度：高] `AC-001#1` 的 actor、delete stimulus、错误码与完整 state hash 保持均与 Stage 0B 一致。
- [COMPUTED｜置信度：高] ActionEnvelope 顶层字段机械计数为 28，与 ADR-004 一致。
- [COMPUTED｜置信度：高] generated 闭集冻结为 259 case files + 6 top-level artifacts = 265 files。
- [COMPUTED｜置信度：高] `git diff --check` 在冻结前通过。

## 4. 明确未完成

- [KNOWN｜置信度：高] 当前完成的是 Stage 0C 设计节点，不是 259 个 reviewed conversion、generated cases 或 sandbox runtime。
- [KNOWN｜置信度：高] `trusted_fixture_harness_smoke_verified`、S case execution、Core behavior、H/J verdict、catalog 与 release 均保持 false。
- [INFERRED｜置信度：高] 下一节点应编写并复审叶子级 Stage 0C 实施计划，然后按 TDD 顺序执行；不得从本记录直接跳到 Stage 0D。

[我打破的规则 / RULES I BROKE]：无。
