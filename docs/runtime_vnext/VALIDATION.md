# vNext foundation — 实际验证记录

记录日期：2026-09-18。类型：本分支作者执行的离线契约测试，不是独立验收，不是 G6 canonical evidence。

## 被测版本与执行环境

公开源码检查 baseline：`34ae8a3d95dbe1cc565893b81306be235a36a4cb`。

被测新增代码与测试已经写入 commit `23a472b0a080d79099fe831c7049b035fd989028`。GitHub API 回读两个文件的 blob SHA，与本地实际执行文件计算的 Git blob SHA 完全一致。

本地仅物化了这两个新增 Python 文件，目录为 `/mnt/data/amadeus-work/foundation`；不是整个仓库的 checkout。先前 `git clone` 因 github.com DNS 失败，没有产生可运行的完整仓库。未访问 Windows staging。

| 环境项 | 实际值 |
|---|---|
| Python | 3.13.5 |
| 平台 | Linux-6.18.44-x86_64-with-glibc2.41 |
| 测试框架 | Python 标准库 unittest |
| 第三方依赖安装 | 无 |
| operational runtime 导入 | 无 |
| provider / 工具副作用调用 | 0 |
| Windows / Python 3.12 验证 | 未执行 |
| GitHub Actions 验证 | 本轮未执行、未添加 workflow，不声称 CI 通过 |

## 实际命令与结果

在上述本地子集目录执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests/runtime_vnext -p 'test_*.py' -v
```

首次执行 40/40 PASS；代码提交后对同一文件字节复跑，最后输出：

```text
----------------------------------------------------------------------
Ran 40 tests in 0.037s

OK
```

最终逐项 stdout/stderr 合并输出完整保存在 [test_output.txt](test_output.txt)，机器可读记录见 [validation_result.json](validation_result.json)。40 是 unittest 测试方法数量；其中一个方法包含 3 个 speaker × 5 个 phase × 8 个表达式结构 = **120 组组合子案例**，不能另计为 120 个独立自然语言案例，更不能写成 160 个测试。

## 精确文件绑定

| 文件 | 字节数 | Git blob SHA-1 |
|---|---:|---|
| `tools/runtime_vnext/semantic_contract.py` | 10089 | `425647116ee0f9966f4e6a2691b42e8bbd4621c9` |
| `tests/runtime_vnext/test_semantic_contract.py` | 17765 | `f209eb06e80425bfcfaa9572c4e6671f1bccdd2f` |

SHA-256：

```text
f5adebc15872c56608be745aa0ea876a91fd1abda5a0d171b9397cb57db2d2ff  tools/runtime_vnext/semantic_contract.py
f1bca10c69237c8dd584199807a5c3e2bc855cc1e19014ea61ac68c9705c852f  tests/runtime_vnext/test_semantic_contract.py
1a2c967e696823afb0f089407b494821405bbe9c0c543672895602df02bd9749  docs/runtime_vnext/test_output.txt
```

最后一项是完整本地测试输出的哈希，不是独立测试服务签名。执行耗时只是该次运行测量，不是性能保证。提交绑定证明仓库文件与被测文件相同，不证明任意宿主环境都会通过。

## 实际覆盖范围

覆盖六维表示变更、嵌套转述/否定/条件/阶段的保留、作用域拒绝、原文哈希和 quote 匹配、Unicode code point offset、未决归属、缺失及撤销证据、HOLD/REJECT 优先级、JSON 严格边界、时间格式与区间顺序、资源上限、无损投影与纯函数输入不变。

其中时间测试只检查带时区格式、正区间和 roundtrip；**没有实现或验证当前时刻的过期授权判定**。撤销测试只是传入 `revoked=True` 时绑定结果为 HOLD；**没有实现生产级撤销依赖传播**。模块静态检查仅确认已审查的标准库导入和不存在若干直接危险调用，不是通用 Python 沙箱证明。

测试明确包含一个重要反例：同一原文可以绑定到一个不相关的、结构合法的 AST，`check_bindings` 仍会返回 BOUND，但 `proves_proposition` 和 `grants_authority` 永远为 false。这是对契约边界的检验，不是已解决自然语言解释错误。生产解释审查必须另行实现。

## 未执行与不得宣称通过的项目

- R8-N02-01、R8-N06-01 的实际复现、修复与重新评审：未执行，缺少当前 G6 canonical 源码与原始 evidence。
- 自然语言抽取、同义改写正确率、独立标注留出集：未执行；当前模块不是 NLP parser。
- AdmissionController / RuntimeStore / 检索 / expression 的端到端接入、迁移、恢复、并发和全仓库兼容回归：未执行。
- 真实 provider、外部工具、费用账单核验、多模型回退、跨自然日和产品验收：未执行。
- Windows staging 的 Git 状态、运行数据库和 UNKNOWN 请求账本重新核验：未执行。

这些缺项不是通过减少标准而免除；对应生产阶段仍被阻塞。本记录不能使 G6-07、build-scope complete、产品验收或 production activation 改为完成。

## 已核验的变更边界

GitHub compare 从 baseline 到代码 commit `23a472b0a080d79099fe831c7049b035fd989028` 显示 3 个追加 commit、7 个新增文件、0 个原有文件修改或删除。最终记录阶段只再新增本文件、`validation_result.json`、`test_output.txt`、`HANDOFF.md` 四个交接文件；完成后的 PR diff 应为总计 11 个新增文件。最终 PR 创建前需回读 compare 核对，PR 描述记录最终 SHA 与实际列表。

未修改既有 `persona_core/`、Source/Genesis、canonical 状态、provider journal 或数据库 schema。没有导入旧 operations 完成状态。没有发送项目 provider 请求，没有重试或处理原有 UNKNOWN 记录。GitHub 分支写入属于代码协作操作，不是 Amadeus provider 请求。
