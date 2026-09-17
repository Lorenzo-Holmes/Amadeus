# Amadeus vNext foundation — 下一会话交接

本文件是 feature 分支的工程交接，不是新的任务状态机。不得依据这里的离线 PASS 修改 G6 canonical 状态。

## 从哪里继续

仓库：`Lorenzo-Holmes/Amadeus`。

工作分支：`feat/amadeus-runtime-vnext-foundation`。

公开源码 baseline：`34ae8a3d95dbe1cc565893b81306be235a36a4cb`；对应现有分支 `codex/persona-core-operations-v1-20260917`。PR 以这个分支为 base，而不是 main。默认分支 main 的已观察提交为 `a6ffaa388ebdab03620070c3990ffc9788425e8f`。下一会话必须重新读取 refs；不要用这些记录覆盖之后产生的新提交。

优先阅读 [BASELINE.md](BASELINE.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[SEMANTIC_CONTRACT.md](SEMANTIC_CONTRACT.md)、[VALIDATION.md](VALIDATION.md)。完整测试输出与机器记录均在本目录，不需要从聊天重建。

## 本轮提交顺序与目的

| Commit | 目的 |
|---|---|
| `b5fb58be822b97f6ab3939d9d9b11ab6b9a89231` | 固定实际 GitHub 观察，先记录 canonical 缺失和旧状态不可继承。 |
| `61d97b1c521e285c06859b44c784cb6a07e7f5c2` | 提交基于已读取源码的架构、契约和后续门禁，不另建 Persona Core。 |
| `23a472b0a080d79099fe831c7049b035fd989028` | 提交离线语义参考及 40 个合成测试；代码 blob 与本地执行文件已核对。 |
| 包含本文件的记录 commit | 保存真实验证结果、完整日志、未完成事项及回滚方法；用 `git log` 或 PR commits 获取它的 SHA。 |

所有 commit 均追加到新分支，没有 force push、reset、历史改写、删除历史分支或自动合并。最终分支 SHA 与 PR 链接以 GitHub 实际 refs/PR 为准，避免在文件中伪造自身 commit hash。

## 已交付的有限成果

F0 交付包括源码地图、单一 Core 的扩展架构候选、六维语义契约、无 I/O 的可执行参考、合成测试及逐文件哈希。参考实现能保留结构与核对原文绑定，但没有解析自然语言，也没有判断命题真伪或执行授权。

源码位置 `tools/runtime_vnext/semantic_contract.py` 是刻意未接入生产的开发参考，不是新的人格运行时。以后接入时应根据真实 G6 代码复用/迁入既有类型和准入链，不能永久维持两套生产语义权威。

## 仍然阻塞的工作

当前公开 baseline 缺少 `persona_core/gpt6_optimization_v2/`、R8 原始失败材料、当前运行数据库及未知请求原始账本。`PERSONA_CORE_PROGRESS.md` 的 G6 header 与用户预期的本地 phase 不同。没有核验用户 Windows 工作区，也没有理由把公开旧快照当作完整 G6 canonical。

因此：R8-N02-01 / R8-N06-01 未复现、未修复、未重新评审；G6-07 不关闭。InterpretationReview、真实宿主证据适配、effect-specific admission、长期记忆/检索/表达端到端贯通、派生撤销、schema 迁移、Windows/Python 3.12 与全仓库回归、真实 provider 和产品验收均未完成。

现有 Persona Core、Genesis、Source、trusted-state 枚举/语义、provider submission 和生产状态没有被本分支修改。架构提出未来变更不代表现在已经实施。

## 下一步执行顺序

1. 重新读取 GitHub default branch、feature/base HEAD、PR diff 和当前 G6 源码可用性；记录与本交接的差异，不重置分支。检查新旧提交关系及并发改动。
2. 通过用户授权的同步途径取得实际 G6 canonical 代码与必要证据。公开仓库只上传经过许可的 public-safe 源码/摘要；不要自动公开原始对话、凭据、运行数据库或私人 provider captures。不得根据进度摘要重建并冒充原始 evidence。
3. 对真实 canonical 文件、Git 状态和已绑定证据重新核验，再选生产修复 baseline。在此之前只允许继续独立离线设计，不修改 main 或升级生产。
4. 查清原始 R8 失败在表示、解释、准入、持久化、检索或表达的具体断点；先建立真实回归，再修一般性结构与准入。禁止 prompt patch、测试 ID 特判、关键词白名单或伪造 PASS。
5. 在真实既有模块中实现 InterpretationReview 与语义绑定，复用现有 AdmissionController / RuntimeStore；运行源证据、六维变形、自然语言留出与完整兼容测试。参考模块的 BOUND 不能映射为 ADMIT。
6. 取得实际需要的独立语义、provider 与自然日证据后，才由 canonical 自身规则决定状态推进；文档、mock、时间模拟和开发自评不能代替这些证据。

以上是后续工作顺序，不是本会话的后台任务或已经开始的自动执行。

## UNKNOWN 请求的不可绕过边界

公开进度记录一个未知 `N06_T4`，但本轮没有原始账本重核验。这不是允许忽略该请求的理由。凡 `SUBMITTED_STATUS_UNKNOWN`：保留原记录；禁止重发、SDK 自动重试、换 request ID、换 slot、换模型/供应商或恢复任务时绕过。原结果缺失、进程结束和取消任务均不等于请求未提交。只可依据原请求身份核对原结果，不因此重新发起效果。

## 测试复跑

```sh
python -m unittest discover -s tests/runtime_vnext -p 'test_*.py' -v
```

该命令只跑新参考测试。每次代码变更后重新保存准确的执行环境、结果及哈希，不继承本次 40/40。全仓库测试需先检查收集、fixture、导入和后台线程是否可能请求 provider，不能直接因为名为 test 就运行。

## 文件范围

新增：本目录的 README、BASELINE、baseline_observation、ARCHITECTURE、SEMANTIC_CONTRACT、VALIDATION、validation_result、test_output、HANDOFF，以及 `tools/runtime_vnext/semantic_contract.py`、`tests/runtime_vnext/test_semantic_contract.py`，共 11 个文件。

相对公开 baseline 修改的既有文件：无。删除文件：无。既有 Persona Core 代码：无修改。可信状态语义：无修改。没有新 canonical 状态文件，也没有生产激活。

## 回滚

未合并时不采用该 feature 分支即可，保留分支历史和 PR 讨论。合并后如需撤回，通过新的 revert commit 按依赖逆序撤销本分支变更；若采用 merge commit，先由维护者确认主线 parent 后做对应 revert。若采用 squash，撤销实际 squash commit。不要假定未来合并方式。

禁止 force push、删除历史分支、重写 baseline、用旧数据库覆盖后续真实经历。此阶段没有 runtime 状态或 schema 迁移，所以撤销这些新增开发文件不需要恢复 Persona 数据库，也不能声称远端 UNKNOWN 已被撤销。
