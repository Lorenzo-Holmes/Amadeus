# Amadeus

## 先说非目标（反方论据）

[KNOWN｜置信度：高] 这个仓库尚不是已经完成的 Amadeus v0.1，也不是可直接发布的聊天产品。当前可核验完成项是 Stage 0A 来源工具链与 Stage 0B 来源裁决；可执行行为 fixture、确定性 Core 与模型接入仍在后续阶段。

[FRAME｜置信度：高] 本项目不把单一 system prompt、某个模型供应商、某个聊天界面或一批向量记录等同于长期身份。它也不以复刻某个既有角色、证明意识、无限扩张工具权限或收集未经整理的原始资料为目标。

## 项目定位与三条线

[FRAME｜置信度：高] Amadeus 的工程目标是建立一个可审计、可回放、可迁移的长期数字人格运行时：身份、记忆、关系边界、主动性和执行权分别受明确契约约束。

| 线 | 定位 | 当前作用 |
|---|---|---|
| [FRAME] A — Amadeus Soul | 插件形态的低成本行为实验台 | [KNOWN] 用于快速验证表达与交互假设，不决定身份、记忆、主动性或权限边界 |
| [FRAME] B — Amadeus Core v0.1 | 当前工程落地点 | [KNOWN] 先完成来源裁决、fixture、确定性状态机与门禁，再接模型 |
| [FRAME] C — 独立 Amadeus | 产品主线 | [KNOWN] 以单一 Core 和多个隔离 Relationship Vault 承载长期身份；B 为其当前实现路径 |

## 架构边界

[FRAME｜置信度：高] Terminal 只负责终端输入输出；Core 持有系统边界；Memory Governor 是正常自传体记忆状态迁移的确定性唯一提交者；每个 Relationship Vault 是单一关系的硬可见边界。

~~~mermaid
flowchart LR
    T1["Terminal：文本 / Web / IM / 未来语音"]
    T2["受限维护入口"]
    C["Core：身份、事件、策略与生命周期"]
    G["Memory Governor：确定性状态迁移"]
    S["Source Snapshot"]
    L["Experience Ledger"]
    A["Autobiographical Memory"]
    V1["Relationship Vault A"]
    V2["Relationship Vault B"]
    M["可替换模型后端：只生成 Proposal"]

    T1 --> C
    T2 --> C
    M --> C
    C --> G
    G --> S
    G --> L
    G --> A
    C --> V1
    C --> V2
~~~

[FRAME｜置信度：高] 多个 Terminal 不各自持有人格副本；模型 Proposal 也不直接获得记忆提交权或工具执行权。

## 当前可核验状态

| 检查项 | 当前结果 |
|---|---|
| [KNOWN] Stage 0A 自动化测试 | [COMPUTED] 56 / 56 |
| [KNOWN] Stage 0B 自动化测试 | [COMPUTED] 33 / 33 |
| [KNOWN] 完整自动化测试 | [COMPUTED] 130 / 130 |
| [KNOWN] 唯一来源行 | [COMPUTED] 214 |
| [KNOWN] Core oracle 裁决 | [COMPUTED] 95 / 95；pending 0 |
| [KNOWN] atomicity 裁决 | [COMPUTED] 214 / 214；185 atomic、29 composite、259 clauses |
| [KNOWN] 当前 Stage 0 readiness 声明 | [KNOWN] <code>source_toolchain_ready=true</code>、<code>source_adjudication_ready=true</code> |

[KNOWN｜置信度：高] <code>catalog_ready</code>、行为 case coverage、Core release 与 Amadeus v0.1 均未完成；不能从 Stage 0A 的绿色结果外推这些状态。

## 权威仓库位置

- [KNOWN｜置信度：高] 权威本地目录：<code>D:\amadues bot\Amadeus</code>
- [KNOWN｜置信度：高] GitHub：<https://github.com/Lorenzo-Holmes/Amadeus>

[COMMON｜置信度：高] 开发命令应从权威本地目录执行。仓库文档链接使用相对路径，避免绑定个人目录或具体基础设施入口。

## 快速安装

[KNOWN｜置信度：高] 项目要求 Python 3.12 或更高版本；当前验证目标是 Python 3.12。

~~~powershell
cd 'D:\amadues bot\Amadeus'
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
~~~

## 测试与 CLI

### 完整与专项测试

~~~powershell
python -m pytest
python -m pytest tests/project_kb -q
python -m pytest tests/stage0a -q
python -m pytest tests/stage0b -q
~~~

### Stage 0A 来源工具链

~~~powershell
python -m tools.stage0a_sources.cli check --root . --output-dir fixtures/stage0a/generated
~~~

[KNOWN｜置信度：高] 当前成功输出必须是：

~~~text
source_toolchain_ready=true
pending_oracle_assignments=95
pending_atomicity_reviews=214
~~~

### Stage 0B 来源裁决工具链

~~~powershell
python -m tools.stage0b_adjudication.cli check --root .
amadeus-stage0b check --root .
~~~

[KNOWN｜置信度：高] 当前成功输出包含 <code>source_adjudication_ready=true</code>、<code>reviewed_sources=214</code>、两个 pending 均为 0，并继续声明 <code>case_coverage_complete=false</code>、<code>catalog_ready=false</code>、<code>release_ready=false</code>。

### 项目开发知识库

~~~powershell
python -m tools.project_kb.cli --root . check
python -m tools.project_kb.cli --root . search "Memory Governor" --limit 10
amadeus-project-kb --root . check
~~~

[KNOWN｜置信度：高] 检索只读取 manifest 明确批准且 SHA-256 匹配的 Markdown；不会创建数据库、chunk 或 embedding。每条命中包含仓库相对路径、行号、最近 Markdown 标题和原行。

## 目录说明

| 路径 | 作用 |
|---|---|
| [KNOWN] [outputs/](outputs/) | 当前 ADR、候选数据契约、评测、实施计划、审查与执行记录 |
| [KNOWN] [fixtures/stage0a/](fixtures/stage0a/) | Stage 0A 冻结配置与四份 generated JSON |
| [KNOWN] [fixtures/stage0b/](fixtures/stage0b/) | Stage 0B deterministic checklist、reviewed decisions、source-clause manifest 与 report |
| [KNOWN] [tools/stage0a_sources/](tools/stage0a_sources/) | 只处理 Stage 0A 来源绑定、worklist 与 readiness check |
| [KNOWN] [tools/stage0b_adjudication/](tools/stage0b_adjudication/) | Stage 0B 冻结输入、strict schema、编译器与 write/check 门禁 |
| [KNOWN] [tools/project_kb/](tools/project_kb/) | 纯标准库、只读的开发知识库校验与逐行检索 |
| [KNOWN] [tests/stage0a/](tests/stage0a/) | Stage 0A 回归与路径边界测试 |
| [KNOWN] [tests/stage0b/](tests/stage0b/) | Stage 0B 输入、schema、当前裁决、编译器与 CLI 回归 |
| [KNOWN] [tests/project_kb/](tests/project_kb/) | manifest、policy、路径安全与搜索合同测试 |
| [KNOWN] [knowledge/](knowledge/) | 开发者知识导航、curated legacy 与 raw 隔离区 |
| [KNOWN] [work/](work/) | 研究辅助文件；不构成运行时产品接口 |

## 权威文档阅读顺序

1. [KNOWN｜置信度：高] [ADR-006：记忆主权与 Core 生命周期治理](outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md) — 当前批准的 C′ 架构裁决。
2. [KNOWN｜置信度：高] [Core v0.1 数据契约与状态机规范](outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md) — Draft v0.1 / Normative candidate，不是已完成实现。
3. [KNOWN｜置信度：高] [研究与设计交付索引](outputs/Amadeus研究与设计交付索引-2026-07-27.md) — 状态、阅读顺序和已冻结方向的总入口。
4. [KNOWN｜置信度：高] [Stage 0A 执行记录](outputs/Amadeus-Core-v0.1-Stage0A-执行记录-2026-07-28.md) — 56 项测试、四份 generated JSON 与门禁证据。
5. [KNOWN｜置信度：高] [Stage 0A 来源编译器实施计划](outputs/Amadeus-Core-v0.1-Stage0-场景夹具实施计划.md) 与 [Stage 0A 审查记录](outputs/Amadeus-Core-v0.1-Stage0A-实施计划审查记录-2026-07-28.md) — 已完成边界和 Stage 0B 入口。
6. [KNOWN｜置信度：高] [Stage 0B 来源裁决实施计划](outputs/Amadeus-Core-v0.1-Stage0B-来源裁决实施计划.md) 与 [Stage 0B 审查记录](outputs/Amadeus-Core-v0.1-Stage0B-实施计划审查记录-2026-07-29.md) — 214 项来源、95 个 Core oracle 与 atomicity 裁决的叶级执行合同。
7. [KNOWN｜置信度：高] [Stage 0B 执行记录](outputs/Amadeus-Core-v0.1-Stage0B-执行记录-2026-07-29.md) — 95/95 oracle、214/214 atomicity、259 clauses、产物 hash 与 readiness 证据。
8. [KNOWN｜置信度：高] [Stage 0C 夹具转换设计](outputs/Amadeus-Core-v0.1-Stage0C-夹具转换设计.md) 与 [设计审查记录](outputs/Amadeus-Core-v0.1-Stage0C-设计审查记录-2026-07-29.md) — 259 个单 clause case、完整 frozen binding、98 个 S clause、可恢复构建与 readiness 边界。
9. [KNOWN｜置信度：高] [Stage 0C 夹具转换实施计划](outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md) 与 [实施计划审查记录](outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md) — 已冻结的 259-case 转换、sandbox、publication、smoke 与 CLI 叶级执行合同。
10. [KNOWN｜置信度：高] [ADR-001](outputs/ADR-001-Amadeus身份与成长模型.md) → [ADR-002](outputs/ADR-002-Amadeus记忆生命周期.md) → [ADR-003](outputs/ADR-003-Amadeus主动性与事件循环.md) → [ADR-004](outputs/ADR-004-Amadeus工具权限与执行治理.md) → [ADR-005](outputs/ADR-005-Amadeus关系安全与退出协议.md) — 支持性裁决。
11. [KNOWN｜置信度：高] [身份与记忆评测基线](outputs/Amadeus身份与记忆评测基线-v0.1.md) 是 Draft / 待实现；[主动性、权限及关系安全评测增量](outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md) 是 Frozen-candidate；两者都尚待转为可执行 fixture。
12. [KNOWN｜置信度：高] [项目开发知识库导航](knowledge/data_structure.md) — 00/10/20/30/40/90/99 分层及更新合同。

## 如何使用项目开发知识库

[KNOWN｜置信度：高] [knowledge/data_structure.md](knowledge/data_structure.md) 是唯一逻辑导航入口；[knowledge/manifest.json](knowledge/manifest.json) 是逐文档 SHA-256 allowlist；[knowledge/index-policy.json](knowledge/index-policy.json) 实行默认拒绝且 exclude 优先。

~~~powershell
python -m tools.project_kb.cli --root . check
python -m tools.project_kb.cli --root . search "QUERY"
python -m tools.project_kb.cli --root . search "QUERY" --limit 5
~~~

[KNOWN｜置信度：高] 修改已索引文档后，必须用当前字节重新计算 SHA-256、更新 manifest、运行 check 与相关测试，并把文档和 manifest 放在同一 Git 节点。任何 stale hash 都会令 check 非零退出。

## Git 节点提交与推送协议

[COMMON｜置信度：高] 一个节点只承载一个可复核目的；显式暂存文件，不使用模糊的全仓库暂存来掩盖无关改动。

~~~powershell
git status --short --branch
git diff --check
python -m pytest
python -m tools.stage0a_sources.cli check --root . --output-dir fixtures/stage0a/generated
python -m tools.stage0b_adjudication.cli check --root .
python -m tools.project_kb.cli --root . check

git add README.md knowledge/data_structure.md knowledge/index-policy.json knowledge/manifest.json tools/project_kb tests/project_kb pyproject.toml
git diff --cached --check
git diff --cached --stat
git commit -m "type: describe one verified node"
git status --short --branch
~~~

[COMMON｜置信度：高] 推送前再次核验分支名、节点 SHA、上游和工作区；推送动作与本地提交分开决定。

~~~powershell
git branch --show-current
git rev-parse HEAD
git remote -v
git push -u origin HEAD
~~~

## 下一步严格顺序

1. [KNOWN｜置信度：高] **Stage 0B 已完成**：四输入身份、95 个 Core oracle、214 个 atomicity 决策和 259 个 source clause 已冻结。
2. [INFERRED｜置信度：高] **Stage 0C**：消费 Stage 0B manifest，实现 fixture DSL、clause→case 绑定与 S 动作沙箱。
3. [INFERRED｜置信度：高] **Stage 0D**：仅在 0C 门禁通过后实现 H/L/J、catalog 与分项报告门禁。
4. [INFERRED｜置信度：高] **确定性 Core**：先实现无 LLM 的契约/哈希、事件存储与 genesis、Memory Governor、Vault、Branch、生命周期、恢复与回放。
5. [INFERRED｜置信度：高] **模型对照**：最后以固定输入比较 API 与本地模型的质量、延迟、成本、隐私和可用性；模型结果不得覆盖确定性规则。

[KNOWN｜置信度：高] Stage 0C 必须消费 Stage 0B 的 clause/hash 绑定，不重新解析 Markdown 取代 reviewed decisions；模型输出仍不作为 Core 基线。

## Backlog

- [KNOWN｜置信度：高] Stage 0C 的 fixture DSL、259 个 clause 到 executable case 的绑定与 S 动作沙箱。
- [KNOWN｜置信度：高] 119 条行为测试候选到可执行 fixture 的转换与 Core 基线运行。
- [KNOWN｜置信度：高] ADR-001 至 ADR-005 在实现反馈后的状态复裁决。
- [KNOWN｜置信度：高] 数字人格治理研究的剩余全文研读。
- [KNOWN｜置信度：高] API / 本地后端同条件模型对照。
- [KNOWN｜置信度：高] 真实用户主动阈值、关系体验与长期结果校准。
- [INFERRED｜置信度：高] 分支冲突只生成报告，不自动合并；物化视图必须可从权威事件重建。

## 隐私、raw 与索引规则

- [FRAME｜置信度：高] GitHub 仓库的治理目标是持续保持 Private；每次交接和推送前复核可见性。Private 访问控制仍与内容脱敏并行执行，凭证和具体基础设施入口只留在本地 raw 隔离区。
- [KNOWN｜置信度：高] <code>knowledge/90_raw/</code> 是隔离区，<code>index=false</code>；raw 文件不得进入 manifest，策略 exclude 优先。
- [KNOWN｜置信度：高] 开发者知识库与 Amadeus runtime memory 完全分离；前者不写入 Source Snapshot、Experience Ledger、Autobiographical Memory 或 Relationship Vault。
- [COMMON｜置信度：高] 进入 curated 区前删除凭证、个人身份信息、私有基础设施入口与不必要的原始会话内容。
- [KNOWN｜置信度：高] README、manifest 与导航只使用仓库相对路径；权威本地目录和公开 GitHub 地址是明确例外。

## 接替开发恢复清单

- [ ] [KNOWN] 进入 <code>D:\amadues bot\Amadeus</code>，运行 <code>git status --short --branch</code>；先处理任何未知改动。
- [ ] [KNOWN] 运行 <code>git branch --show-current</code>、<code>git rev-parse HEAD</code> 与 <code>git log -5 --oneline</code>，确认接替节点。
- [ ] [COMMON] 建立 Python 3.12 venv 并执行 <code>python -m pip install -e ".[test]"</code>。
- [ ] [KNOWN] 按“权威文档阅读顺序”阅读 ADR-006、数据契约、交付索引与 Stage 0A/0B 执行记录。
- [ ] [KNOWN] 运行 Stage 0A CLI check；只接受 95 / 214 和 <code>source_toolchain_ready=true</code>。
- [ ] [KNOWN] 运行 Stage 0B CLI check；只接受 214 reviewed、0 / 0 pending、<code>source_adjudication_ready=true</code> 和三个下游 false。
- [ ] [KNOWN] 运行项目知识库 check；当前应报告 34 个索引文档与 0 个 raw 路径。
- [ ] [COMMON] 运行完整 pytest 与 <code>git diff --check</code>。
- [ ] [KNOWN] 核对 <code>fixtures/stage0a/generated/</code> 未漂移，且 <code>outputs/</code> 与 Stage 0A 逻辑没有被接替准备工作改写。
- [ ] [INFERRED] 从第一个尚未通过门禁的阶段继续：Stage 0C → 0D → 确定性 Core → 模型对照。

[我打破的规则 / RULES I BROKE]：无。
