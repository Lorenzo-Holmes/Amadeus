# 基线、依据与本轮核对范围

日期：2026-09-07。本文区分“会话中已给出的历史信息”与“本轮实际读取”。

## A. 本轮实际成功读取

通过DevSpace工作区 `ws_ec7ee2708d` 成功读取：

- `AGENTS.md`：仍指向人物内核默认主线及旧Source-to-Genesis阶段。
- `AMADEUS_PERSONA_CORE_MASTER_GOAL.md`：仍标R043为ACHIEVED，并保留世界线/记忆/状态分层原则。
- `PERSONA_CORE_PROGRESS.md` 第190行起至结尾：仍以GOAL_COMPLETE作为NEXT_ACTION，且记载R043发布后仅剩部分外部验证。
- `PERSONA_CORE_CONTINUATION_PROTOCOL.md`：包含2026-09-07项目级持续授权；来源边界、恢复机制继续有效。

随后读取Decision Log两次、exec一次、读取runtime_cli一次、open_workspace一次及再次读取Progress均返回502。本轮未重新完成代码审计、没有运行项目测试、没有重新核验R043/Genesis哈希、没有确认任何Windows写入。

## B. 上一轮只读检查作为立项依据

以下代码已在本会话上一轮工具结果中展示；本构建文档沿用其所揭示的风险，要求R044-01再次固定到实际文件字节。

| 依据 | 位置 | 观察与限制 |
|---|---|---|
| E-R033 | `persona_core/rebaseline_20260907_r033/tools/validate_r033.py::main` | 逐项构造`verdict=PASS`；静态guard只能说明命中条件，不能证明原语义标准全通过 |
| E-CLI | `persona_core/runtime/runtime_cli.py::main` | `--event-json`/`--snapshot`接口；未在该文件看到交互式自然语言闭环 |
| E-PROMPT | `persona_core/runtime/runtime_prompt.py::build_messages` | 由调用者传tags；构造system和user；每对象取最后8事件；这不能证明整个仓库没有其它入口，故R044需做限定范围入口盘点 |
| E-STORE | `persona_core/runtime/runtime_core.py::admit_event` | Ledger先写，随后多文件状态写；有authority字符串检查。结构显示需要故障与信任边界验证，本轮没有实际注入崩溃 |
| E-CP | `persona_core/runtime/runtime_checkpoint.py::create_checkpoint` | 写出哈希/计数/摘要；该函数不是完整恢复实现。R046应查找现有恢复代码并实际演练，而非默认完全不存在 |

文档中提到的“问题”若当前已由新代码解决，应绑定新证据，更新任务状态；不能仅因历史讨论而重写已正确的实现。

## C. 历史标识，只作定位线索

- Release：`AMADEUS-PERSONA-CORE-R043`。
- 会话历史记载Release SHA-256：`99f6612745c473ae07cfb4c7452b93b725a91e788b603e3a923e5362e431bc8c`。
- Genesis：`AMADEUS-KURISU-GENESIS-R035`。
- 会话历史记载Genesis SHA-256：`9f10697003d72c9f33ae88ff72618092fb24ea8d9a4b1e5e1021d4f0ade0f840`。
- 历史记忆准入：`RC-R005-001`；其它具名HOLD、Source fact、2010-03截止月份及精确日未知需按实际Genesis核对。

以上哈希本轮未重新计算，不是本包对原发布的完整性认证。不要将本构建包MANIFEST当成R043原数据清单。

## D. 本轮交付边界

交付的是Markdown构建说明、机器可读任务/验收表、续作入口、根目录同步补丁及文档校验工具。项目模型调用数为0；新语义评审数为0；R044–R047完成任务数为0。

Windows同步因502未验证。下载包可作为下次会话的恢复输入；其来源仍是本会话的构建文档，不是已写入本机的权威状态。
