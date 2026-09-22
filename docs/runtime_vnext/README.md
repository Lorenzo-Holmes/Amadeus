# Amadeus runtime vNext：持久交接入口

本目录是 `feat/amadeus-runtime-vnext-foundation` 的架构与工程交接记录，不是新的 Persona Core，也不是 G6 canonical 状态系统。

## 必须先读

1. [BASELINE.md](BASELINE.md)：实际 GitHub baseline、与用户本地 G6 主线的差异、缺失证据和允许范围。
2. [ARCHITECTURE.md](ARCHITECTURE.md)：基于已读取源码的复用边界、目标架构、接口、迁移与分阶段门禁。
3. [SEMANTIC_CONTRACT.md](SEMANTIC_CONTRACT.md)：Claim/Evidence 表示与离线参考实现的承诺、限制及生产接入条件。
4. [VALIDATION.md](VALIDATION.md)：实际执行的测试、文件绑定和未执行项目。
5. [HANDOFF.md](HANDOFF.md)：下一会话的恢复步骤、已知未完成项和回滚方式。

机器可读的 [baseline_observation.json](baseline_observation.json) 是来源观察，不得当成 canonical `TASK_STATE`。测试结果也不得使旧状态文件、产品验收或生产激活自动变为完成。

## 当前范围

已经读取并固定的公开源码快照：`34ae8a3d95dbe1cc565893b81306be235a36a4cb`。这个快照不包含 `persona_core/gpt6_optimization_v2/`。因此本分支只承载架构、**未接入生产的离线语义契约参考实现**及其合成测试；不宣称修复或复现 R8-N02-01 / R8-N06-01。

运行新测试，无第三方依赖、无 provider 请求：

```sh
python -m unittest discover -s tests/runtime_vnext -p 'test_*.py' -v
```

测试直接按文件路径加载新参考模块，不导入旧 runtime、不运行 pytest 的全仓库收集或 conftest。正式架构和下一步均以本目录中经过提交的文件为交接依据；聊天不是唯一事实源。
