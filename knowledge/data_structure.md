# Amadeus 项目开发知识库：数据结构与唯一导航

## 0. 反方边界

[KNOWN｜置信度：高] 这个知识库不是 Amadeus 的 runtime memory，也不是把仓库全部文本自动喂给模型的入口。开发者文档不会自动写入 Source Snapshot、Experience Ledger、Autobiographical Memory 或 Relationship Vault；运行时记忆也不会反向进入本索引。

[KNOWN｜置信度：高] 本文件是项目开发知识库的唯一逻辑导航入口。现有权威文档保留在 [outputs/](../outputs/) 原位，由 [manifest.json](manifest.json) 显式引用；不为追求目录整齐而复制或搬迁。

## 1. 逻辑分层

| 层 | 逻辑内容 | 当前物理位置与入口 | 索引规则 |
|---|---|---|---|
| [FRAME] 00 Entry | 新开发者接替、导航、manifest 与 policy | [README.md](../README.md)、本文件、[manifest.json](manifest.json)、[index-policy.json](index-policy.json) | [KNOWN] README 与本文件显式 allowlist；JSON 自身不作为可搜索文档 |
| [FRAME] 10 Authority | 已批准架构裁决与候选实现合同 | [ADR-006](../outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md)、[Core 数据契约](../outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md) | [KNOWN] 保持 outputs 原位；manifest 逐字节绑定 |
| [FRAME] 20 Delivery | 支持 ADR、评测、实施计划、审查与执行证据 | [outputs/](../outputs/) | [KNOWN] 只有 manifest 列出的 Markdown 可检索 |
| [FRAME] 30 Research | 研究清单、全文研读、综合结论和 curated legacy research | [outputs/](../outputs/)、[30_research/legacy/](30_research/legacy/) | [KNOWN] curated 文档可索引；原始下载不在本层 |
| [FRAME] 40 History | 定位约束、历史方案与会话总结的去敏 curated 版本 | [40_history/legacy/](40_history/legacy/) | [KNOWN] 仅保留有接替价值的版本 |
| [FRAME] 90 Raw | 原始导出、敏感原档、未整理材料 | [90_raw/](90_raw/) | [KNOWN] <code>index=false</code>；禁止进入 manifest |
| [FRAME] 99 Operations | 校验器、检索器、测试和 Git 节点协议 | [tools/project_kb/](../tools/project_kb/)、[tests/project_kb/](../tests/project_kb/)、[README.md](../README.md) | [KNOWN] 工具只读，不生成数据库、chunk 或 embedding |

## 2. 索引合同

1. [KNOWN｜置信度：高] [index-policy.json](index-policy.json) 的 <code>default_index=false</code>；未明确批准即不索引。
2. [KNOWN｜置信度：高] exclude 优先于 include；<code>knowledge/90_raw/**</code>、<code>.git/**</code>、<code>.local/**</code> 与 <code>.worktrees/**</code> 始终排除。
3. [KNOWN｜置信度：高] [manifest.json](manifest.json) 中每项必须有 <code>doc_id</code>、<code>title</code>、<code>path</code>、<code>kind</code>、<code>authority</code>、<code>status</code>、<code>stage</code>、<code>index</code>、<code>sensitivity</code> 与 <code>sha256</code>。
4. [KNOWN｜置信度：高] 每项 <code>index=true</code>，路径为唯一的 POSIX 仓库相对路径，SHA-256 绑定当前 UTF-8 Markdown 字节。
5. [KNOWN｜置信度：高] 路径穿越、绝对路径、symlink、junction、raw、隐藏本地目录、非 Markdown、无效 UTF-8、重复 ID/路径与 stale hash 都会令 check 非零退出。

## 3. 查询合同

~~~powershell
python -m tools.project_kb.cli --root . check
python -m tools.project_kb.cli --root . search "QUERY"
python -m tools.project_kb.cli --root . search "QUERY" --limit 10
~~~

[KNOWN｜置信度：高] 查询只读取 manifest allowlist。每条命中返回：

~~~text
仓库相对路径:行号 | 最近的 Markdown 标题 | 命中原行
~~~

[KNOWN｜置信度：高] 默认上限为 20；零命中正常返回 0 并输出 <code>hits=0</code>。

## 4. 更新流程

1. [COMMON｜置信度：高] 先确定逻辑层、权威级别、阶段、状态和 sensitivity；raw 一律留在 90 层且 <code>index=false</code>。
2. [COMMON｜置信度：高] 先做 curated：移除凭证、个人身份信息、私有基础设施入口和无接替价值的原始内容。
3. [KNOWN｜置信度：高] 新文档只有在 policy 明确 include 后才可加入 manifest；不要扩大通配符来绕过逐文档审批。
4. [COMMON｜置信度：高] 对最终字节计算 SHA-256：

~~~powershell
python -c "import hashlib,pathlib; p=pathlib.Path('PATH'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
~~~

5. [KNOWN｜置信度：高] 新增或更新 manifest 项；保持 <code>doc_id</code> 和 <code>path</code> 唯一，<code>index=true</code>。
6. [KNOWN｜置信度：高] 运行 check、目标查询、项目知识库专项测试和完整测试：

~~~powershell
python -m tools.project_kb.cli --root . check
python -m tools.project_kb.cli --root . search "UNIQUE_TERM" --limit 5
python -m pytest tests/project_kb -q
python -m pytest
git diff --check
~~~

7. [COMMON｜置信度：高] 文档、policy（若变更）与 manifest 在同一 Git 节点提交；任何后续字节改动都必须同步刷新 SHA-256。

## 5. 权威恢复入口

1. [KNOWN｜置信度：高] [根 README](../README.md)：项目定位、安装、状态、命令、顺序与接替清单。
2. [KNOWN｜置信度：高] [ADR-006](../outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md)：已批准架构边界。
3. [KNOWN｜置信度：高] [Core 数据契约](../outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md)：Draft v0.1 候选合同。
4. [KNOWN｜置信度：高] [研究与设计交付索引](../outputs/Amadeus研究与设计交付索引-2026-07-27.md)：全部交付与研究阅读顺序。
5. [KNOWN｜置信度：高] [Stage 0A 执行记录](../outputs/Amadeus-Core-v0.1-Stage0A-执行记录-2026-07-28.md)：当前已完成节点和 Stage 0B 边界。

[我打破的规则 / RULES I BROKE]：无。
