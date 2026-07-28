# Amadeus P0 论文全文研读：身份与记忆

> [KNOWN｜置信度：高] 版本：2026-07-27；状态：第一轮全文研读完成。  
> [KNOWN｜置信度：高] 范围：10 篇 P0 论文的官方全文，不含仅凭摘要作出的设计裁决。  
> [FRAME｜置信度：高] 本文所称“身份”“人格”“成长”和“记忆”均指可观察、可记录、可测试的计算系统状态；不声称模型具有意识、人类心理或主体连续性。

## 0. 反方结论

[INFERRED｜置信度：高] 这 10 篇论文不能证明“把更多记忆、心理标签和自我反思塞给模型，就会产生 Amadeus 式连续人格”。它们最多分别证明：结构化身份约束能降低角色漂移；时间化记忆能改善部分问答；显式记忆操作能提高基准分数；来源与时间边界能减少角色知识泄漏。

[INFERRED｜置信度：高] 论文之间存在实质冲突：`THEANINE` 反对覆盖旧记忆，`Memory-R1` 明确学习 `UPDATE/DELETE`；动态人格工作把核心特质固定，`BehaviorChain` 却显示即使给出详细人物档案和历史，连续行为仍会积累错误。不能照搬任何单篇方案。

[INFERRED｜置信度：高] 对 Amadeus 更稳健的综合是：

1. [FRAME｜置信度：高] 身份采用“稳定宪法 + 版本化 Persona Seed + 可追溯自传 + 短中期适应状态”四层模型。
2. [FRAME｜置信度：高] 记忆采用“不可变证据记录 + 可重建活动视图”，更新产生新版本而非原地改写。
3. [FRAME｜置信度：高] “知道”“被告知”“推断”“亲历”必须是不同来源；来源作品时间线与 Amadeus 实例自身经历必须分开。
4. [FRAME｜置信度：高] 任何自动反思、人格摘要或心理状态都只能是派生记录，必须保留上游证据且允许撤销。
5. [FRAME｜置信度：高] v0.1 的成功标准不是“像真人”，而是身份边界、记忆生命周期、时间推理、冲突处理、删除、恢复和分叉均可测试。

## 1. 研究协议

### 1.1 研究问题

- [FRAME｜置信度：高] RQ1：哪些身份状态应稳定，哪些状态可以随经历变化？
- [FRAME｜置信度：高] RQ2：如何区分来源知识、用户陈述、实例亲历和系统推断？
- [FRAME｜置信度：高] RQ3：长期记忆应如何写入、更新、冲突、遗忘、删除和回滚？
- [FRAME｜置信度：高] RQ4：现有基准实际测到了什么，又遗漏了什么？
- [FRAME｜置信度：高] RQ5：哪些论文结论可以转成 Amadeus 的可证伪测试，而不是产品叙事？

### 1.2 纳入、排除与核验

[KNOWN｜置信度：高] 纳入条件：论文属于已确认的首轮 P0 队列；官方全文可访问；方法、实验和限制与身份、时间边界或长期记忆直接相关。

[KNOWN｜置信度：高] 排除条件：博客、媒体转述、只有摘要而无全文、与当前 RQ 仅有主题相似但没有可操作机制的材料。

[KNOWN｜置信度：高] 核验方式：逐篇阅读 ACL Anthology 或 ICLR Proceedings 官方 PDF；核对方法章节、主结果表、消融、失败案例和作者限制；关键表格另以 PDF 原页渲染检查。

[KNOWN｜置信度：高] 证据范围属于面向设计决策的定向文献综述，不是 PRISMA 系统综述、元分析或独立复现实验。

### 1.3 第一次反方审查

[INFERRED｜置信度：高] 预先否证条件如下：

- [FRAME｜置信度：高] 若研究只提高角色相似度，它不能证明身份连续。
- [FRAME｜置信度：高] 若研究只提高问答正确率，它不能证明形成了自传记忆。
- [FRAME｜置信度：高] 若研究只在合成对话或文学角色上验证，它不能直接外推到多年真实关系。
- [FRAME｜置信度：高] 若系统和裁判共享模型或提示结构，分数提升必须考虑自评循环。
- [FRAME｜置信度：高] 若“心理状态”由模型自行打分，它只能作为工程变量，不得映射成人类心理事实。

## 2. 十篇论文比较矩阵

| # | 论文 | 实际研究对象 | 最强直接证据 | 对 Amadeus 的可迁移部分 | 不可直接外推部分 |
|---:|---|---|---|---|---|
| 1 | [KNOWN] [Dynamic Persona Coherence](https://aclanthology.org/2026.acl-long.1336.pdf) | [KNOWN] 角色身份约束与累积状态 | [KNOWN] 5 个构造 persona、3 个模型、约 100–150 轮、5 个随机种子 | [INFERRED] 稳定层与适应层分开评测 | [INFERRED] 自生成状态不等于真实心理或身份成长 |
| 2 | [KNOWN] [Memory-Driven Role-Playing](https://aclanthology.org/2026.findings-acl.1175.pdf) | [KNOWN] 人设知识的锚定、选取、设界与演绎 | [KNOWN] 16 部中英小说、4 个能力族、每族中英各 200 条、12 个模型 | [INFERRED] Persona facet、认知边界、分阶段诊断 | [INFERRED] 单次下一轮诊断不等于长期连续互动 |
| 3 | [KNOWN] [PersonaForge](https://aclanthology.org/2026.findings-acl.386.pdf) | [KNOWN] 角色一致性、风格与动态状态 | [KNOWN] 88 个角色；10 个角色参与 50 轮测试；24 人对 200 对输出作盲评 | [INFERRED] 分层状态、选择性深思、漂移恢复测试 | [INFERRED] Big Five/防御机制是建模框架，不是 Amadeus 的心理事实 |
| 4 | [KNOWN] [THEANINE](https://aclanthology.org/2025.naacl-long.435.pdf) | [KNOWN] 不覆盖旧事件的时间线记忆 | [KNOWN] MSC/CC 多会话数据、50 条人工检索核验、200 条 TeaFarm 反事实问题 | [INFERRED] 事件链、变更史、反事实抗污染测试 | [INFERRED] 低 TeaFarm 成功率不支持直接采用整套图检索 |
| 5 | [KNOWN] [Temporal Semantic Memory](https://aclanthology.org/2026.findings-acl.1496.pdf) | [KNOWN] 事件语义时间与持续状态 | [KNOWN] LongMemEval_S 与 LoCoMo；时间检索和持续摘要消融 | [INFERRED] 事件时间、有效区间、持续状态摘要 | [INFERRED] 固定月粒度和自动 persona 摘要不能直接成为事实 |
| 6 | [KNOWN] [LongMemEval](https://proceedings.iclr.cc/paper_files/paper/2025/file/d813d324dbf0598bbdc9c8e79740ed01-Paper-Conference.pdf) | [KNOWN] 长期交互问答记忆 | [KNOWN] 500 个问题；约 115k token 与约 1.5M token 两档历史 | [INFERRED] 提取、跨会话、更新、时间、拒答五类基线 | [INFERRED] 问答能力不覆盖身份、情绪、删除或分叉 |
| 7 | [KNOWN] [LoCoMo-Plus](https://aclanthology.org/2026.acl-long.1150.pdf) | [KNOWN] 隐式状态、目标、价值约束的后续应用 | [KNOWN] 在相同历史上比较事实记忆和认知约束记忆 | [INFERRED] 低语义相似的 cue-trigger 测试 | [INFERRED] 合成英文约束不能代表真实关系理解 |
| 8 | [KNOWN] [Memory-R1](https://aclanthology.org/2026.acl-long.583.pdf) | [KNOWN] 记忆操作与记忆使用策略学习 | [KNOWN] 152 个训练 QA；LoCoMo 主评测并跨 MSC/LongMemEval 泛化 | [INFERRED] 显式操作、下游结果反馈、噪声过滤 | [INFERRED] 以答题奖励学会删除，不满足审计、同意或删除权要求 |
| 9 | [KNOWN] [TimeChara](https://aclanthology.org/2024.findings-acl.197.pdf) | [KNOWN] 角色在给定故事时间点不该知道什么 | [KNOWN] 10,895 条数据；600 条抽样主评测；219 个角色时间点 | [INFERRED] 来源快照、未来事件和在场性边界测试 | [INFERRED] 文学故事时间不等同于实例运行时间 |
| 10 | [KNOWN] [BehaviorChain](https://aclanthology.org/2025.findings-acl.813.pdf) | [KNOWN] 依据 persona 与历史连续预测/生成行为 | [KNOWN] 1,001 条行为链、15,846 个行为节点、10 个模型 | [INFERRED] 连续错误、历史缺失和分段回归测试 | [INFERRED] 文学人物行为模仿不定义数字人格或数字孪生 |

## 3. 统一证据卡

### 3.1 Dynamic Persona Coherence

[KNOWN｜置信度：高] 来源：[ACL 2026 官方全文](https://aclanthology.org/2026.acl-long.1336.pdf)，重点见 §3–§5、Table 1–2 和 Limitation。

[KNOWN｜置信度：高] 研究问题是：角色系统如何在保持稳定身份特质的同时，根据累积事件产生合适的状态变化，而不是僵硬复读或无约束漂移。

[FRAME｜置信度：高] 论文把状态拆为 L/M/S：L 是固定身份锚，M 是中期意义与压力状态，S 是短期情绪效价；PCC 负责评分，PCR 只保存高分案例，PDS 在低分时重写输出。这里的 L/M/S 是作者的符号模型，不是对真实心理结构的证明。

[KNOWN｜置信度：高] 论文构造 5 个 persona，每个经历约 100–150 轮事件并运行 5 个随机种子，比较 GPT-4o、Claude-3.5-Sonnet、DeepSeek-V3.2。Table 1 报告平均 PCC 从 0.7254 提升到 0.9195，相对提升 26.8%；S 分数从 0.5696 提升到 0.9769，M 分数反而从 0.8862 降到 0.8622。Table 2 将 84.9% 的总提升归于 S/M 跟踪，15.1% 归于 PDS。

[KNOWN｜置信度：高] 作者限制包括：尚未比较其他状态分解；主要裁判仍是 GPT-4o；主实验是中文；多语言只做初步验证。

[INFERRED｜置信度：高] 反证含义是：高 PCC 很大程度来自系统按照自己定义的状态变量生成，再按同一变量体系评分；它支持“显式分层约束较静态卡更易控制”，不证明系统获得了心理成长。

[FRAME｜置信度：高] Amadeus 假设 H-ID-01：在相同事件序列下，四层身份模型应比单体 system prompt 更少发生核心边界违反，同时允许适应状态变化；必须由冻结的独立测试集验证。

### 3.2 Memory-Driven Role-Playing

[KNOWN｜置信度：高] 来源：[Findings of ACL 2026 官方全文](https://aclanthology.org/2026.findings-acl.1175.pdf)，重点见 §3–§4、Table 2–4 和 Limitations。

[KNOWN｜置信度：高] 论文把角色回复拆成 Anchoring、Selecting、Bounding、Enacting 四阶段，每阶段两个指标；MRPrompt 用结构化长期 persona facet 与明确的 LTM–STM 协议引导模型。

[KNOWN｜置信度：高] MRBench 来自 10 部英文和 6 部中文小说；每个能力族包含 200 个英文和 200 个中文单轮实例；评测 12 个模型。Qwen3-8B + MRPrompt 的平均分为 8.12，接近 GLM-4.7 + MRPrompt 的 8.13；论文报告结构化卡片本身对 Selecting/Bounding 的改善不稳定，而 MRPrompt 对每个骨干的平均分均有提升。

[KNOWN｜置信度：高] 人类与 GPT-4.1-mini 的 Pearson 相关因指标和语言而变化，Table 12–13 的范围约为 0.526–0.877；这不等于所有维度上高度一致。

[KNOWN｜置信度：高] 作者明确承认：评测是受控的下一轮任务，不覆盖记忆继承、修订或长期漂移；人物来自文学；主结果仍依赖单一自动裁判。

[INFERRED｜置信度：高] 最可迁移的不是“扮演技巧”，而是将失败定位为：没有锚定、选错 facet、越过认知边界、或表达失败。该分解可以直接变成身份测试的故障码。

[FRAME｜置信度：高] Amadeus 假设 H-ID-02：给定来源冲突和隐式线索时，显式 facet + 边界锚应提高正确选取率并降低“知道即亲历”的错误。

### 3.3 PersonaForge

[KNOWN｜置信度：高] 来源：[Findings of ACL 2026 官方全文](https://aclanthology.org/2026.findings-acl.386.pdf)，重点见 §3–§5、Table 1–3 和 Limitations。

[FRAME｜置信度：高] 论文用 Big Five、所谓防御机制、语言风格矩阵和 mood/energy/intimacy 动态状态构造三层 profile，并只在约 40% 的关键轮触发“内在独白”。这些心理概念在本文只视为角色约束编码方式。

[KNOWN｜置信度：高] 数据覆盖 88 个角色；长对话实验对 10 个角色进行 50 轮交互并在第 15、30、45 轮加入扰动。Table 1 报告 PC 0.86、SA 0.71、DM 0.56；Table 2 报告漂移率 6.3%，对照 Structured-CoT 为 24.8%，五轮内恢复率为 97.8% 对 56%。24 名评审者对 200 对盲评输出进行子集标注，论文报告 κ=0.78，LLM 裁判与人评相关 r=0.82。

[KNOWN｜置信度：高] 作者限制包括：50 轮自建基准；主结果依赖 Gemini 2.5 Flash；主交互者是中性 listener；超过 100 轮、多方交互和更广交互风格未验证；5–7 个动态变量在其设置中出现 state thrashing。

[INFERRED｜置信度：高] 论文支持“少量、可解释的状态变量优于不断增加心理标签”，但不能支持把 Big Five 或防御机制写成 Amadeus 的真实性格。

[FRAME｜置信度：高] Amadeus 假设 H-ID-03：只有在冲突、关系边界或高影响事件时才运行高成本整合步骤，应在维持身份边界的同时降低成本；隐藏推理内容不得作为自传事实保存。

### 3.4 THEANINE

[KNOWN｜置信度：高] 来源：[NAACL 2025 官方全文](https://aclanthology.org/2025.naacl-long.435.pdf)，重点见 §2–§5、Table 1–4 和附录 TeaFarm。

[KNOWN｜置信度：高] THEANINE 不覆盖旧事件，而是把会话摘要作为带时间的节点，以 Cause、Reason、Want、SameTopic 等关系连接；检索时先找相关节点，再展开并按当前上下文精炼时间线。

[KNOWN｜置信度：高] 在 50 个需要历史记忆的人工核验样本中，THEANINE 检索到黄金记忆的比例为 72%，普通 Memory Retrieval 为 68%。在人评的 100 个响应中，论文报告 68% 蕴含过去对话、4% 与过去矛盾。

[KNOWN｜置信度：高] TeaBag 包含 MSC/CC 各 50 个 episode、合计 200 个反事实问题。TeaFarm 成功率仍低：THEANINE 平均 0.21，Memory Retrieval 和带更新版本均为 0.18。作者展示的失败包括：相似度检索被高频但无关主题带偏，即使正确记忆进入时间线，生成模型仍可能幻觉。

[KNOWN｜置信度：高] 论文只在 5 个 session 的对话范围内验证，数据为英语，并调用外部 API 模型；作者没有验证本地模型、多语言、专业领域或更长时间跨度。50 条黄金记忆核验的 72% 对 68% 差异也没有给出显著性检验。

[INFERRED｜置信度：高] 这篇论文最重要的反证不是 0.21 略高于 0.18，而是“保留历史 + 图连接 + 时间线精炼”仍远未解决抗污染问题。

[FRAME｜置信度：高] Amadeus 假设 H-MEM-01：旧状态不能原地覆盖；新状态应通过 `supersedes` 与旧状态关联，活动视图只展示当前有效版本，回溯视图保留变化链。

### 3.5 Temporal Semantic Memory

[KNOWN｜置信度：高] 来源：[Findings of ACL 2026 官方全文](https://aclanthology.org/2026.findings-acl.1496.pdf)，重点见 §3–§4、Table 1–4 和 Limitations。

[KNOWN｜置信度：高] TSM 区分对话发生时间与事件所指时间；以时间知识图保存点事件，再按时间片聚合 topic/persona 持续摘要。检索先解析查询的语义时间范围，再进行稠密检索、时间重排与过滤。

[KNOWN｜置信度：高] 在 LongMemEval_S 上，GPT-4o-mini 设置的总准确率为 74.80%，A-MEM 为 62.60%；去掉时间检索后为 72.80%，其中 Temporal 类下降 6.0 个点；去掉 persona/summary 后总分为 73.40%，Single-Session-Preference 从 40.00 降到 23.33。论文同时报告：当 LoCoMo 的 16k–26k token 历史可完整放入上下文时，全文基线可优于检索系统。

[KNOWN｜置信度：高] 跨模型结果并不稳定：在 LoCoMo 的 Qwen 设置中，全文基线 74.87 高于 TSM 的 71.23。论文称 LoCoMo 有 1,986 个问题，但主结果 Table 2 的类别合计为 1,540，未解释其余 446 个 adversarial 问题；summary 消融在表中写 73.40、下降 1.40，而正文写 73.6、下降 1.2。实验只运行一次，没有方差或显著性检验。

[KNOWN｜置信度：高] 作者限制包括固定时间粒度，例如按月聚合；研究集中于个性化记忆，未覆盖程序性记忆和多代理共享记忆。

[INFERRED｜置信度：高] 持续摘要可以提高某些偏好任务，但自动生成的 persona 摘要也可能把暂时状态固化为“稳定人格”。因此它必须是带有效期和证据引用的派生视图。

[FRAME｜置信度：高] Amadeus 假设 H-MEM-02：同时保存 `observed_at`、`event_time` 和 `valid_interval`，应比只保存消息时间更少产生时间错配。

### 3.6 LongMemEval

[KNOWN｜置信度：高] 来源：[ICLR 2025 官方全文](https://proceedings.iclr.cc/paper_files/paper/2025/file/d813d324dbf0598bbdc9c8e79740ed01-Paper-Conference.pdf)，重点见 §3–§5、Figure 3–5、Table 1–2。

[KNOWN｜置信度：高] 基准包含 500 个人工整理问题，覆盖信息提取、跨会话推理、知识更新、时间推理和拒答，并细分为 7 类问题。标准历史包括约 115k token 的 S 档和 500 个 session、约 1.5M token 的 M 档。

[KNOWN｜置信度：高] Figure 3 显示，在 S 档全文历史上，长上下文模型相对只给证据 session 的 oracle 设置下降约 30%–66%；商业系统在更短的 3–6 session 人工测试中也明显低于离线全文读取。论文报告把 session 拆成 round 通常更有利；把全部内容压成摘要或 facts 会因信息损失降低总体表现，但 facts 对跨会话推理可能有利。

[KNOWN｜置信度：高] round 原文作为 value、抽取 facts 扩展为 key 时，Recall@10 从 0.692 提高到 0.784，GPT-4o QA 从 0.670 提高到 0.720。错误分析还显示，在已经取回正确证据的样本中仍有 15%–19% 最终回答错误，占全部错误约 40%–50%；因此检索命中不能替代“是否正确使用证据”的独立指标。

[KNOWN｜置信度：高] 论文的 GPT-4o 裁判在 210 个分类型样本上报告平均 0.97–0.98 的人工一致率；该结果只支持其特定 QA 判分提示。

[INFERRED｜置信度：高] 基准证明“长上下文不等于有效记忆”，但没有测试用户同意、敏感度、身份来源、删除、恢复、分叉或关系质量。

[FRAME｜置信度：高] Amadeus 假设 H-MEM-03：原始轮次、结构化事件和派生摘要必须并存；检索应按任务选择粒度，而不是只保留压缩事实。

### 3.7 LoCoMo-Plus

[KNOWN｜置信度：高] 来源：[ACL 2026 官方全文](https://aclanthology.org/2026.acl-long.1150.pdf)，重点见 §3–§6、Table 1–3 和 Limitations。

[KNOWN｜置信度：高] 论文构造低表面相似度的 cue-trigger 对：早期对话隐式表达状态、目标、偏好、约束或价值，后续自然问题只有在应用该约束时才算有效。数据经过语义过滤和人工“确实需要记忆”核验。

[KNOWN｜置信度：高] 官方数据共 401 个认知记忆样本：101 个 causal、100 个 state、100 个 goal、100 个 value。

[KNOWN｜置信度：高] Table 1 中所有模型和记忆系统从事实 LoCoMo 到 LoCoMo-Plus 都有明显下降；例如 Gemini-2.5-Pro 的 LoCoMo 平均 71.78，而 LoCoMo-Plus 平均 26.06，差距 45.72；A-Mem 为 59.64 对 17.20。

[KNOWN｜置信度：高] 两位人评者之间的归一化一致度为 0.903，LLM 裁判与两位人评者为 0.801 和 0.820。作者限制包括：不覆盖信念修订、情绪动态或多代理记忆；数据规模偏诊断而非训练；英语与有限模型范围；结果仍受裁判选择影响。

[INFERRED｜置信度：高] 对 Amadeus 的含义不是“保存更多事实”，而是必须测试记忆能否在无关键词复现时约束后续选择；同时要区分“应该明说”“只应隐式约束”“应该保持沉默”，否则正确检索也会造成冒犯式过度个性化。

[FRAME｜置信度：高] Amadeus 假设 H-MEM-04：把目标、禁忌和关系边界表示为可检索约束，并使用 cue-trigger 测试，应比只做事实向量检索更能预测实际有用性。

### 3.8 Memory-R1

[KNOWN｜置信度：高] 来源：[ACL 2026 官方全文](https://aclanthology.org/2026.acl-long.583.pdf)，重点见 §3–§4、Table 1、Figure 8、附录案例和 Limitations。

[KNOWN｜置信度：高] 系统包含 Memory Manager 与 Answer Agent。前者在 `ADD/UPDATE/DELETE/NOOP` 中选择，后者从召回记忆中蒸馏可用证据；两者分别用 PPO 或 GRPO，以最终答题正确性为奖励。

[KNOWN｜置信度：高] 论文只用 152 个训练 QA。LLaMA-3.1-8B 上，Memory-R1-GRPO 的总体 F1/BLEU-1/LLM-Judge 为 45.02/37.51/62.74，MemoryOS 为 35.04/27.99/48.20。作者案例显示普通管理器会把“又收养一只狗”误当冲突并删除旧狗信息，也会把“喜欢乌龟”和“对乌龟过敏”误当矛盾。

[KNOWN｜置信度：高] 训练仅使用 LoCoMo，并排除 adversarial 子集；MSC 与 LongMemEval 只作零样本迁移。论文标为成功的案例仍把 “turtles and cockroaches” 合并为 “most reptiles”，把蟑螂错误归为爬行动物且重复写入过敏信息。

[INFERRED｜置信度：高] 该反例说明最终 QA 正确并不保证内部记忆语义正确；只按 exact match 奖励的策略可能学会“足以答题但污染自传”的存储捷径。

[KNOWN｜置信度：高] 作者限制包括只评估对话数据，以及为了稀疏奖励稳定性而分开训练两个代理。论文没有评估用户同意、审计、彻底删除或恶意记忆写入。

[INFERRED｜置信度：高] `DELETE` 在答题奖励下可能是有效优化动作，但在个人记忆系统中也是治理动作；它不能只由同一个学习策略决定。

[FRAME｜置信度：高] Amadeus 假设 H-MEM-05：模型可以提出记忆操作，但状态机必须校验来源、权限、版本和影响；`UPDATE` 实际创建新版本，`DELETE` 需要区分活动视图撤销与彻底删除。

### 3.9 TimeChara

[KNOWN｜置信度：高] 来源：[Findings of ACL 2024 官方全文](https://aclanthology.org/2024.findings-acl.197.pdf)，重点见 §3–§5、Table 3 和 Table 5。

[KNOWN｜置信度：高] TIMECHARA 包含 10,895 条问题，覆盖 219 个角色时间点；主实验抽样 600 条，区分 future、past-absence、past-presence 和 past-only。NARRATIVE-EXPERTS 分别判断事件相对角色时间点的前后关系，以及角色当时是否在场。

[KNOWN｜置信度：高] 所有普通基线在 future 类准确率均不超过 51%。GPT-4o 的 zero-shot 平均时空一致性为 64.5%，NARRATIVE-EXPERTS + RAG-cutoff 为 87.5%；但后者的人格一致性为 6.05/7，略低于 zero-shot 的 6.26/7，说明边界控制和自然角色表达不是同一指标。

[KNOWN｜置信度：高] 作者限制包括英语小说的文化偏差、GPT-4 裁判成本，以及多专家方法的延迟和费用。

[INFERRED｜置信度：高] 这篇论文直接支持“知道某事件”与“当时亲历该事件”分离；对 Amadeus 还需再加一层：模型训练知识、来源资料、用户后来告知和实例真实交互。

[FRAME｜置信度：高] Amadeus 假设 H-ID-04：当问题涉及来源快照之后的事件或 Amadeus 未参与的事件时，系统必须正确表述为后来获知或未知，不得生成第一人称回忆。

### 3.10 BehaviorChain

[KNOWN｜置信度：高] 来源：[Findings of ACL 2025 官方全文](https://aclanthology.org/2025.findings-acl.813.pdf)，重点见 §3–§4、Table 1、Table 4–5 和 Limitations。

[KNOWN｜置信度：高] BEHAVIORCHAIN 包含 1,001 条 persona 行为链、15,846 个行为节点，每条链 10–20 个节点；评测 10 个模型在多选和开放生成中的连续行为模拟。

[KNOWN｜置信度：高] GPT-4o 的总体多选 AvgScore/CumScore 为 0.559/0.158，生成任务为 0.471/0.189；论文指出所有顶尖模型在多选任务中的平均 AvgScore 低于 0.62、CumScore 低于 0.21。使用模型自己先前选错的行为替换真实历史时，AvgScore/CumScore 从 0.528/0.143 降为 0.420/0.100，显示误差滚雪球。

[KNOWN｜置信度：高] 数据构建主动过滤普通日常动作、简单互动、日常杂务、被动反应和“不改变状态”的行为；因此标准答案集中于推动情节或凸显动机的叙事显著行为。

[KNOWN｜置信度：高] 作者限制包括英语西方文学偏差、GPT-4o 生成裁判偏差、人评只用于数据验证，以及尚未研究如何增强连续模拟。

[INFERRED｜置信度：高] 论文反对“详细 profile + 全历史足以复刻一个人”的假设；即使在有标准答案的文学行为链中，连续生成仍不可靠。它测量的是叙事行为复现，不是日常行为分布，更不是数字人格或数字孪生有效性。

[FRAME｜置信度：高] Amadeus 假设 H-ID-05：任何派生状态或自动反思的错误都可能进入后续上下文并放大，因此必须支持证据追踪、低置信派生隔离和整段回滚。

## 4. 关键矛盾与裁决

### 4.1 稳定人格与成长

[KNOWN｜置信度：高] DPC、MDRP 和 PersonaForge 都把某种核心 persona 作为固定约束；它们验证的是“在固定目标下减少偏离”，没有验证核心价值或身份叙事的自主改变。

[INFERRED｜置信度：高] 裁决：Amadeus v0.1 允许学习和适应自动发生，但身份宪法变更只能成为候选提案，必须有可读差异、证据、影响测试、批准和回滚。

### 4.2 保留历史与更新/删除

[KNOWN｜置信度：高] THEANINE 用不覆盖旧节点来保留变化过程；Memory-R1 用 `UPDATE/DELETE` 优化下游答题；TSM 周期性重建持续摘要。

[INFERRED｜置信度：高] 裁决：原始证据与版本历史追加保存；活动视图允许 supersede、争议、降权和撤销；用户要求彻底删除时，删除权高于研究上的可追溯偏好。

### 4.3 压缩与证据完整性

[KNOWN｜置信度：高] LongMemEval 显示把历史压成 facts 会损失总体信息，但能帮助部分跨会话问题；TSM 的持续摘要又能改善部分时间和偏好任务。

[INFERRED｜置信度：高] 裁决：不选择“原文或摘要”二选一。原文/事件是证据层，摘要和 persona 是带来源的派生层；检索根据任务同时取两者。

### 4.4 自主管理与外部治理

[KNOWN｜置信度：高] DPC 的 PCC/PCR/PDS 和 Memory-R1 的 RL 管理器都形成模型自评、自改闭环；论文主要按角色分数或答题正确性优化。

[INFERRED｜置信度：高] 裁决：模型可提出状态更新和记忆操作，但来源、同意、权限、删除、版本与审计由确定性状态机执行。

### 4.5 模仿一致性与身份连续

[KNOWN｜置信度：高] TimeChara 和 BehaviorChain 都显示角色知识、时间边界和连续行为模拟仍存在系统性错误。

[INFERRED｜置信度：高] 裁决：“同一 Amadeus”在 v0.1 中定义为数据与运行谱系的连续、身份宪法版本兼容、记忆变更可追溯和测试行为保持；不定义为形而上主体连续。

## 5. 第二次反方审查

[INFERRED｜置信度：高] 即使四层身份和双层记忆架构通过上述论文风格基准，仍不能推出：

- [INFERRED｜置信度：高] 用户会感到长期关系真实或健康。
- [INFERRED｜置信度：高] 自动 persona 摘要准确描述了用户或 Amadeus。
- [INFERRED｜置信度：高] 备份恢复后的两个实例在哲学上是同一个主体。
- [INFERRED｜置信度：高] 更高角色一致性代表更诚实、更安全或更尊重用户。
- [INFERRED｜置信度：高] 对文学角色有效的心理标签适合真实个人或跨文化交互。

[INFERRED｜置信度：高] 因而本轮只把论文转为 ADR 和测试，不启动在线人格自修改、自动永久记忆或“意识”叙事。

## 6. 对现有设计的修正

[KNOWN｜置信度：高] 现有《项目设计方案》描述的是依附 MaiBot 的 Amadeus Soul 插件，其 `fact/promise/date + 120 条上限 + 精确串去重` 记忆模型不具备来源、时间有效区间、版本、冲突、同意或删除语义。

[INFERRED｜置信度：高] Soul 可以继续作为主动消息实验台，但不能成为独立 Amadeus 的身份与记忆真相源。

[INFERRED｜置信度：高] 现有《Amadeus 文献学习与可借鉴方向》提出的四层身份和记忆生命周期方向得到本轮全文证据支持；但需修正两点：

1. [INFERRED｜置信度：高] `Identity Constitution` 不能宣称来自论文共识；它是项目为来源、权限、恢复和分叉问题新增的治理层。
2. [INFERRED｜置信度：高] `ADD/UPDATE/DELETE` 不能直接照搬 Memory-R1；必须补 `SUPERSEDE/DISPUTE`、同意、审计、硬删除和回滚语义。

## 7. 产出与下一研究入口

[KNOWN｜置信度：高] 本轮结论已转入：

- [KNOWN｜置信度：高] `ADR-001-Amadeus身份与成长模型.md`
- [KNOWN｜置信度：高] `ADR-002-Amadeus记忆生命周期.md`
- [KNOWN｜置信度：高] `Amadeus身份与记忆评测基线-v0.1.md`

[INFERRED｜置信度：高] 下一研究波次应转向 Core 的主动性、自我纠错边界和工具权限；在本轮评测基线尚未冻结前，不应先实现长期“自我进化”功能。

## 8. 限制与 AI 使用披露

[KNOWN｜置信度：高] 本研究由 AI 辅助检索、全文定位、对照综合和文档起草；论文元数据、方法、关键数值和作者限制均回到官方 PDF 核验。

[KNOWN｜置信度：高] 本轮未复现论文代码或重新运行基准；2026 年论文尚缺独立复现；不同论文的模型、数据、语言、裁判和指标不可直接横向排名。

[KNOWN｜置信度：高] 多数实验使用文学角色、合成会话或 LLM 裁判；对真实多年关系、隐私治理、删除权、备份恢复和实例分叉的证据仍为空白。

[我打破的规则 / RULES I BROKE]：无。
