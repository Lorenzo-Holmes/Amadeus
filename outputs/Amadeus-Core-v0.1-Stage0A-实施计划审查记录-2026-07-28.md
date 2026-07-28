# Amadeus Core v0.1 Stage 0A 实施计划审查记录（2026-07-28）

## 0. 反方结论

[INFERRED｜置信度：高] 将来源编译、人工拆句、fixture DSL、S 动作沙箱、H/L/J 裁判与 catalog 一次性压入 Stage 0，会让“来源行”“clause”“执行 case”三个数量被错误合并，也会让 Core 的 95 行未声明 oracle 被工程默认值替代。

[KNOWN｜置信度：高] 因此前一份全 Stage 0 草案已退出实施序列；当前批准对象只覆盖 Stage 0A 来源编译器及两份 pending 工作表。

## 1. 最终裁决

| [FRAME] 对象 | [KNOWN] 状态 | [COMPUTED] Critical | [COMPUTED] Important |
|---|---|---:|---:|
| `Amadeus-Core-v0.1-Stage0-场景夹具实施计划.md` | Approved for Stage 0A execution | 0 | 0 |
| 规格与来源合同复核 | 通过 | 0 | 0 |
| writing-plans 叶级执行复核 | 通过 | 0 | 0 |
| 静态代码块与计数复核 | 通过 | 0 | 0 |

[COMPUTED｜置信度：高] 三路独立复核均得到 0 Critical、0 Important。

## 2. 复核基线

| [FRAME] 项目 | [COMPUTED] 结果 |
|---|---|
| 实质内容复核 SHA-256 | `3200C9E294871BCF1AB90FA74ABF5B87B8D270518A29F7B06FBDA08C5A8949F5` |
| 状态提升后最终 SHA-256 | `CB26FD8F96A4013536116DBE026819511657122B056D02624942E0106EBF86A8` |
| Python 代码块 | 37 |
| Python 静态语法错误 | 0 |
| 冻结输入指纹匹配 | 5 / 5 |
| 解析来源行 | baseline 53 + increment 66 + Core 95 = 214 |

[KNOWN｜置信度：高] 两个计划指纹之间的变更只把状态从 Draft 提升为 Approved，并记录三路 0/0 复核结果；实施内容没有变化。

## 3. 已关闭的阻断

1. [COMPUTED｜置信度：高] 五份输入的精确 key、相对 path、source group 与 SHA-256 已成为闭集合同；配置原始字节 SHA-256 同时进入 source index 与 readiness report。
2. [COMPUTED｜置信度：高] 每个来源行保留文档、行号、原始行、原始单元格与两类摘要；测试从冻结文档回读并重算摘要。
3. [COMPUTED｜置信度：高] Core 95 行保持空 raw/canonical oracle 与 `oracle_provenance=undeclared`；它们进入 pending assignment，而非自动归类。
4. [COMPUTED｜置信度：高] Task 2、Task 4 与 Task 5 已拆为行为级红灯、最小实现和同测试绿灯，没有再用“模块缺失”一次覆盖多项行为。
5. [COMPUTED｜置信度：高] CLI 分别检测文档输入、配置身份、配置原始字节、已知工件内容与额外输出条目漂移；输入错误在写入前映射为稳定退出码 2。
6. [COMPUTED｜置信度：高] import 门禁拒绝未列入 allowlist 的绝对 import、动态 import、项目绝对 import 与越出当前 package 的父级相对 import。
7. [COMPUTED｜置信度：高] readiness 只声明 `source_toolchain_ready=true`；atomicity、case coverage、catalog 与 release 均保持 false。

## 4. 范围边界

[KNOWN｜置信度：高] 本轮完成的是实施计划及复核记录；Stage 0A Python 包、测试与四份 generated JSON 尚未生成。

[KNOWN｜置信度：高] 214 是来源行数，不是 fixture 数；119 是带源文档 oracle 的行为来源数，95 是等待显式 oracle 分配的 Core 来源数。

[FRAME｜置信度：高] Stage 0B 在四份 Stage 0A generated JSON 的 SHA-256 冻结后另写计划，负责 214 行 oracle/atomicity 人工裁决与 source-clause manifest。

[FRAME｜置信度：高] Stage 0C 才负责 fixture DSL、clause→case 绑定与 S 动作沙箱；Stage 0D 才负责盲化 H、第三人分歧裁决、L/J 校准、catalog 与两类报告。

## 5. 文档连续性

[KNOWN｜置信度：高] `Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md` 保持原字节不动，因为它是 Stage 0A 的五份冻结输入之一；本记录独立保存后续审查结论，避免让已冻结输入自引用漂移。

## 6. 下一动作

1. [INFERRED｜置信度：高] 按已批准计划执行 Task 0–5，生成来源编译器、两份 pending 工作表、readiness report 与对应测试。
2. [INFERRED｜置信度：高] 对实际生成物运行全套测试与 `check`，再冻结四份 JSON 的 SHA-256。
3. [INFERRED｜置信度：高] 只有在 Stage 0A 实际执行通过后，才编写 Stage 0B 人工裁决计划。

[我打破的规则 / RULES I BROKE]：无。
