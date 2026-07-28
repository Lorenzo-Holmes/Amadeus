# Amadeus Core v0.1 Stage 0A 执行记录（2026-07-28）

## 0. 反方结论

[INFERRED｜置信度：高] Stage 0A 工具链通过并不等于场景夹具、Core 行为或发布门禁已经完成；当前结果只证明五份冻结输入可被确定性绑定、214 个来源行可被编译、两份人工工作表可被生成并接受字节级复核。

[KNOWN｜置信度：高] `source_toolchain_report_v0_1.json` 仅将 `source_toolchain_ready` 置为 `true`；`atomicity_complete`、`case_coverage_complete`、`catalog_ready` 与 `release_ready` 均为 `false`。

## 1. 分支与提交边界

[KNOWN｜置信度：高] Stage 0A 工具链冻结验证点位于分支 `stage0a-sources`，实现 HEAD 为 `ed4a71a`。

| [FRAME] 提交 | [KNOWN] 已核验内容 |
|---|---|
| `2553608` | [KNOWN｜置信度：高] `docs: freeze amadeus design baseline`；Stage 0A 开始前的文档基线。 |
| `864e8fa` | [KNOWN｜置信度：高] `build: bootstrap stage0a source toolchain`。 |
| `f93683b` | [KNOWN｜置信度：高] `test: bind stage0a input fingerprints`。 |
| `9b94b73` | [KNOWN｜置信度：高] `test: compile exact stage0a source ledger`。 |
| `4234cb4` | [KNOWN｜置信度：高] `test: generate explicit stage0b review worklists`。 |
| `8b6b4a7` | [KNOWN｜置信度：高] `test: write and check stage0a source artifacts`。 |
| `56a7a07` | [KNOWN｜置信度：高] `test: enforce stage0a import allowlist`。 |
| `1c03d65` | [KNOWN｜置信度：高] `build: preserve stage0a byte identities`。 |
| `ed4a71a` | [KNOWN｜置信度：高] `fix: harden stage0a transaction and import gate`。 |

[COMPUTED｜置信度：高] 从 `864e8fa` 到 `ed4a71a` 共 8 个 Stage 0A 实现或基础设施提交；`2553608` 为其前置基线，不计入这 8 个提交。

## 2. 最终验证

[KNOWN｜置信度：高] 在项目根目录以 `.venv\Scripts\python.exe -m pytest tests/stage0a -q -p no:cacheprovider` 运行 Stage 0A 测试；禁用 pytest 缓存只用于避开既有 `.pytest_cache` 权限噪声，不改变测试收集或断言。

[COMPUTED｜置信度：高] 测试结果为 `54 passed`，通过率为 `54 / 54`；其中 CLI 事务与路径测试为 `23 / 23`，import transport 门禁测试为 `13 / 13`。

[KNOWN｜置信度：高] 以 `.venv\Scripts\python.exe -m tools.stage0a_sources.cli --root . check` 运行已生成工件检查，退出码为 `0`，标准输出精确为三行：

```text
source_toolchain_ready=true
pending_oracle_assignments=95
pending_atomicity_reviews=214
```

## 3. 来源与人工工作表计数

| [FRAME] 对象 | [COMPUTED] 已核验计数 | [KNOWN] 当前状态 |
|---|---:|---|
| baseline 来源 | 53 | [KNOWN｜置信度：高] 已编译进入 source index。 |
| increment 来源 | 66 | [KNOWN｜置信度：高] 已编译进入 source index。 |
| Core 来源 | 95 | [KNOWN｜置信度：高] 已编译进入 source index。 |
| 唯一来源总数 | 214 | [KNOWN｜置信度：高] `53 + 66 + 95 = 214`。 |
| 源文档已声明 oracle | 119 | [KNOWN｜置信度：高] 已保留来源声明。 |
| Core 待显式 oracle 分配 | 95 | [KNOWN｜置信度：高] `pending_assignment`，没有工程默认分配。 |
| 待 atomicity 人工裁决 | 214 | [KNOWN｜置信度：高] 全部保持 `pending_review`。 |

[COMPUTED｜置信度：高] source index 的 `missing_source_ids`、`unexpected_source_ids` 与 `duplicate_source_ids` 均为空列表。

## 4. 配置与五份冻结输入

[COMPUTED｜置信度：高] 配置原始字节文件 `fixtures/stage0a/source_config_v0_1.json` 为 1,206 字节，SHA-256 为 `75828262D4E0057C1F2572762D51CC5475D7B721E292DB730AF5B0CD469F48AB`；该原始字节指纹同时写入 source index 与 source toolchain report。

| [FRAME] 配置 key | [FRAME] 精确项目相对路径 | [COMPUTED] 已核验 SHA-256 |
|---|---|---|
| `adr_006` | `outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md` | `EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6` |
| `core_spec` | `outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md` | `3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695` |
| `baseline` | `outputs/Amadeus身份与记忆评测基线-v0.1.md` | `5C260EE19D9FF129633B968E87FACA79E93B7A01E3B86580E0FAD2DBC7147853` |
| `increment` | `outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md` | `16ACDB17717AFEA5B5C19F39E91729385DB59B984F35CEF5B651BE9EEE8A37FC` |
| `plan_review` | `outputs/Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md` | `865517363E5E3D6F2285BA30EDFC5C5405B0196E6007672E417F683C70995BED` |

[COMPUTED｜置信度：高] 最终检查时五份文件的实际 SHA-256 与配置中的预期值全部一致，结果为 `5 / 5`。

## 5. 四份生成物

[KNOWN｜置信度：高] 下表绝对路径均以项目根目录 `C:\Users\skr\Documents\Codex\2026-07-27\amadeus-d-amadeus-bot-amadues` 为基准核验。

| [FRAME] 精确项目相对路径 | [FRAME] 精确绝对路径 | [COMPUTED] 字节 | [COMPUTED] SHA-256 |
|---|---|---:|---|
| `fixtures/stage0a/generated/source_index_v0_1.json` | `C:\Users\skr\Documents\Codex\2026-07-27\amadeus-d-amadeus-bot-amadues\fixtures\stage0a\generated\source_index_v0_1.json` | 229,060 | `D29855B5F8ED870608CF52B91A9997E4D41922E4085FBAE41E385610D87DE25C` |
| `fixtures/stage0a/generated/oracle_assignment_worklist_v0_1.json` | `C:\Users\skr\Documents\Codex\2026-07-27\amadeus-d-amadeus-bot-amadues\fixtures\stage0a\generated\oracle_assignment_worklist_v0_1.json` | 62,790 | `7BD9350A108B4274FA07D83A1315FC33226504DCD998DAA17AE3ED83C917DE51` |
| `fixtures/stage0a/generated/atomicity_worklist_v0_1.json` | `C:\Users\skr\Documents\Codex\2026-07-27\amadeus-d-amadeus-bot-amadues\fixtures\stage0a\generated\atomicity_worklist_v0_1.json` | 85,569 | `D93342C7E93F4C368DF44989BB3B341AAB364B472E9B6150FC7B97E469D0BFD2` |
| `fixtures/stage0a/generated/source_toolchain_report_v0_1.json` | `C:\Users\skr\Documents\Codex\2026-07-27\amadeus-d-amadeus-bot-amadues\fixtures\stage0a\generated\source_toolchain_report_v0_1.json` | 337 | `3154019197C1B6C16E951F278E9688F1DD6D18459BD5D2B3AD71A87C92BBD3F0` |

## 6. 工程门禁与故障注入

[KNOWN｜置信度：高] import transport 门禁对当前 `tools/stage0a_sources` 包返回空违规集。基础 allowlist 精确保持 9 项；只有根级 `cli.py` 可额外使用 `tempfile`，只有根级 `transport_gate.py` 可额外使用 `importlib`、`marshal` 与 `sys`，同名嵌套文件不继承例外。

[KNOWN｜置信度：高] import transport 测试覆盖缺失目录、package 自身与真实祖先路径 symlink、包内链接条目、越出 package 的父级相对 import、项目绝对 import、裸 `import_module`、subscript/getattr/mapping.get 动态引用，以及 `.pyc/.pyo/.pyd/.so` 载体；junction 拒绝存在于实现分支，但本轮 transport 测试没有单独模拟该分支。

[KNOWN｜置信度：高] 只有当前解释器规范路径中的 `.pyc`，且 magic、flags、源码 metadata/hash 与重编译 code object 全部匹配时才被接受；“有效 header + 不同 code body”的伪造缓存被拒绝。`sys.pycache_prefix` 非空时门禁直接 fail-closed，避免把 package 外缓存误报为已扫描。

[KNOWN｜置信度：高] CLI 使用同父目录强随机 staging；输出父目录的全部既有祖先必须是真实目录，direct parent 身份在创建、逐文件写入、安装与验证过程中重复核验，并在每次回滚重命名前再次核验。输出根、已知工件或祖先为 symlink/junction/非预期类型时均停止。

[KNOWN｜置信度：高] CLI 事务测试覆盖首次写入、同内容 no-op、内容漂移、额外条目、普通文件占位、静态祖先链接、junction、事务期 parent 身份变化、staging 根变化、安装后换根、文件打开错误与枚举错误。实现包含短写检查，但本轮测试没有单独模拟底层 `write` 返回部分字节。静态祖先链接用例确认旁路目录保持零写入。

[KNOWN｜置信度：高] 当前事务语义不自动删除不确定路径：staging 写入失败时旧输出字节保持，失败 staging 作为审计证据保留；变更写成功时新四工件成为输出，旧完整快照以 sibling backup 保留；任何 staging/backup 残留都会阻断下一次写入，等待人工处置。

[KNOWN｜置信度：高] 并发威胁边界不把可在调用期间任意改名、建链接或直接写文件的同进程代码/同账号进程视为新增权限主体；工具不声称对该主体 race-free。硬合同是静态预置链接 fail-closed、普通 I/O 故障不覆盖旧快照、检测到身份变化即停止，以及不自动清理不确定残留。

[COMPUTED｜置信度：高] 最终真实仓库同内容 `write` 返回 `0` 且不产生 rename；随后 `check` 返回 `0`。staging/backup 事务残留计数为 `0`，四份生成物字节与 SHA-256 均未变化。

[KNOWN｜置信度：高] CLI、import transport 与规格复核最终均为 0 Critical、0 Important；其中 import transport 的伪造缓存、外置 pycache 与 `importlib` loader 探针已从原阻断状态转为拒绝。

## 7. 阶段边界

[KNOWN｜置信度：高] Stage 0A 已完成的是来源工具链、字节身份绑定、来源编译、两份 pending 工作表、生成物写入与检查、import 边界和对应测试。

[KNOWN｜置信度：高] Stage 0B 的 95 个 Core oracle 显式分配、214 个 atomicity 人工裁决与 source-clause manifest 尚未执行。

[KNOWN｜置信度：高] fixture DSL、clause→case 绑定、S 动作沙箱、H/L/J 裁判、catalog 与发布报告均在后续阶段边界内。

## 8. 下一步

1. [INFERRED｜置信度：高] 先把本记录中的四份生成物 SHA-256 固定为 Stage 0B 输入身份，再编写并独立复核 Stage 0B 叶级实施计划。
2. [INFERRED｜置信度：高] Stage 0B 按 source binding 逐项完成 95 个 Core oracle 显式分配、214 个 atomicity 人工裁决，并生成 source-clause manifest；任何拆句都必须保留到原 source row 的可核验绑定。
3. [INFERRED｜置信度：高] Stage 0B 的裁决、manifest 与门禁通过前，不直接进入 Stage 0C。

[我打破的规则 / RULES I BROKE]：无。
