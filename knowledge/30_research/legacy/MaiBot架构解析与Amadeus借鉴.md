> 脱敏说明：本文由本地原档脱敏派生。
> 原档 SHA-256：`924F61F2EA6A3A35A70F652E60F6894F92E20775CEA8D35034218F5AC9F3BC51`

# MaiBot 架构解析与 Amadeus 借鉴

研究对象：`MaiM-with-u/MaiBot` v1.1.0（main 分支，2026\-07\-26 网页快照）。撰写目的：为 Amadeus 的领域边界、核心模块、数据流、接口契约、部署拓扑与演进路线提供经过实证的参照系。

**标签约定**：沿用项目标签体系（\[KNOWN\] / \[COMPUTED\] / \[INFERRED\] / \[COMMON\] / \[GUESS\]），并扩展一个标签 **\[REPO\]** \= 本次会话中从仓库源码或官方文档站实际抓取到的事实（区别于训练记忆）。置信度：高 ≥80%，中 50–80%，低 20–50%。本文正文中凡未显式标注的具体机制、类名、路径、数值，默认为 \[REPO·高\]；推断、常识与猜测一律显式标注。

* * *

## 0\. 反方论据：三个不该学 MaiBot 的理由

**其一，场景错配风险。** \[REPO·高\] MaiBot 是为「QQ 群聊里的拟人化赛博网友」这一单一场景演化出来的单机、单租户系统：SQLite 单文件（WAL 模式）、进程内记忆内核、无任何水平扩展设计、部署单位是一台个人机器或一个 docker\-compose。\[INFERRED·高\] 若 Amadeus 的目标形态包含服务化或多租户，MaiBot 的部署拓扑与存储层几乎没有可直接迁移的部分——能迁移的只有概念结构。

**其二，许可证污染。** \[REPO·高\] MaiBot 采用 GPL\-3.0。\[COMMON·高\] 借鉴架构思想不受版权约束，但复制代码（包括其独立记忆子系统 A\_Memorix）会触发 copyleft 传染。若 Amadeus 存在闭源或商用可能，必须保持「清洁室」边界：读它的设计，不碰它的代码。（此为版权领域常识，非法律意见。）

**其三，你想抄的东西很可能已经被它自己删了。** \[REPO·高\] MaiBot 最广为流传的几个「招牌」认知模块，在当前代码中已不存在：情绪系统于 0.12.0 被移除（changelog 明载）；「海马体」记忆图与 LPMM 知识库整体消失，配置树中无任何残余；normal\_chat / focus\_chat（HFC 心流）双模与「意愿系统」「兴趣度」被单一 Agent 工具循环整体取代。今天照着网上旧文章或旧版本去学 MaiBot，等于捡起人家扔掉的东西。

**反方之反方**：它仍然值得深读，理由恰恰藏在上面第三条里——\[INFERRED·高\] MaiBot 是中文社区罕见的、经受了真实群聊流量和多年迭代检验的开源拟人 Agent，它删过的每一个模块都是一次替 Amadeus 付过学费的实验。**本报告最大的价值不是「它有什么」，而是「它删了什么、为什么删、收敛到了什么」。** 其 v1.1.0 收敛形态（Agent 工具循环 \+ 规则闸门 \+ 分层记忆 \+ 进程隔离插件）与业界主流 agent 架构同构，可作为 Amadeus 的最近邻参照。

* * *

## 1\. 证据与方法

\[COMPUTED·高\] 本会话无法 git clone（沙箱仓库权限未开通），改经 `raw.githubusercontent.com` 逐文件抓取源码、`docs.mai-mai.org` 抓取官方开发文档，由三个并行研究代理沿 import 图爬行，共约 130 余次抓取、覆盖约 60 个源码文件与 20 余个文档页；其中六个承重事实（内置工具清单、回复必要性打分常量、22 张数据表、遥测端点、插件 Runner 进程模型、A\_Memorix 进程内内核）由我本人二次独立复核，全部一致。

**保真链警示**：源码 → 网页抓取摘要 → 研究代理 → 本文，共三级转录。全部 verbatim 标识符均经双源交叉或亲自复核，但仍不排除个别转录失真；关键决策落地前应以 clone 后的源码为准。快照锚点：`version = 1.1.0`、`CONFIG_VERSION = "8.14.33"`、`MODEL_CONFIG_VERSION = "1.17.6"`（commit hash 因 API 受限未能获取）。

已知信息缺口（诚实声明）：内置插件（`src/plugins/built_in/`）名单未取得；A\_Memorix 元数据表的完整列定义未取得（长文件截断）；部分配置类字段仅从调用点反推。

* * *

## 2\. MaiBot 是什么

\[REPO·高\] 自我定位：「基于大语言模型的可交互智能体」，README 语言为「致力于理解你、以真人风格交互的数字生命」——刻意回避工具型 bot 的效率叙事，主打温度与拟人。当前代内核代号 **MaiSaka**。Python ≥3.12（官方镜像实际跑 3.13），FastAPI \+ SQLModel \+ structlog \+ Pydantic \+ TOML 热重载，uv 管理依赖，GPL\-3.0，约 5.6k stars。

* * *

## 3\. 进程与部署拓扑

\[REPO·高\] 单容器内的真实形态是**一个进程组，而非单体进程**：

```
┌── container: maim-bot-core ────────────────────────────────┐
│ [进程1] bot.py → MainSystem（主 asyncio loop）              │
│   ├─ ConfigManager + FileWatcher（TOML 热重载, 600ms 去抖） │
│   ├─ PluginRuntimeManager ──┬─ UDS/命名管道 Envelope RPC   │
│   ├─ A_Memorix host（记忆内核，进程内）                     │
│   ├─ chat 管线 + MaiSaka 决策运行时                         │
│   ├─ maim_message WS 服务器 :8000/ws（legacy 适配器通道）   │
│   ├─ MCPManager → stdio/http 外部 MCP 服务器               │
│   └─ SQLite（data/MaiBot.db, WAL）                          │
│ [线程] WebUI：uvicorn :8001，独立事件循环，前端 SPA 以      │
│         PyPI 包 maibot-dashboard 分发预构建产物             │
│ [进程2] 插件 Runner（group=builtin ← src/plugins/built_in/）│
│ [进程3] 插件 Runner（group=third_party ← plugins/）         │
│           └─ QQ 适配器即插件（@MessageGateway）             │
└─────────────────────────────────────────────────────────────┘
  compose 同网络：NapCat 容器（QQ 协议端, :3001/:6099）、
  sqlite-web（只读库浏览）、可选 caddy 反代
```

三个值得注意的结构判断：

1. \[REPO·高\] **平台接入是双轨过渡态**：legacy 路径（适配器作为独立进程经 WebSocket \+ maim\_message 协议连入 :8000）与新路径（适配器作为 `plugin_type="adapter"` 的插件跑在 Runner 子进程内，经 IPC `host.route_message` 入站）并存，由 `platform_io` 层的 `DriverKind{legacy, plugin}` 统一路由。docker\-compose 中 8000 端口已被注释——官方主推插件化适配器。\[INFERRED·高\] 这是「外挂进程适配器 → 适配器即插件」迁移做到一半的化石层。
2. \[REPO·高\] **WebUI 跑在独立线程的独立事件循环**里，LLM 客户端缓存键因此按事件循环隔离（`(loop, provider)` 二元组）——跨 loop 复用 httpx/openai 客户端会崩，这是一个用架构换来的教训细节。
3. \[REPO·高\] **崩溃隔离粒度是 Runner 组，不是单插件**：一个第三方插件可以拖崩整个 third\_party 组（组内全部插件一起重启），但拖不崩内置组和主进程。这是有意识的折中，不是「每插件沙箱」。

* * *

## 4\. 核心链路：一条消息如何变成一次回复

### 4\.1 入站管线（协议层 → 会话层）

\[REPO·高\] `MainSystem._register_message_handlers()` 把 `ChatBot.message_process` 注册为 maim\_message 服务器的消息回调。`ChatBot.receive_message()` 依序执行：会话定位（`SessionUtils.calculate_session_id` → `ChatManager.get_or_create_session`）→ hook `chat.receive.before_process` → 入站图片压缩 → notice 类消息短路 → `message.process()` 组件级解析（图片走 VLM 描述、语音按 `voice.enable_asr` 走 ASR，转成 `[语音: text]` 文本）→ hook `chat.receive.after_process` → 违禁词/正则过滤 → 适配器生命周期命令 → 清空上下文命令 → 插件命令拦截（被拦截的命令消息单独落库）→ 交 `HeartFCMessageReceiver.process_message()`：消息异步落库、`Person.register_person()` 注册人物、投递给会话运行时。

\[REPO·高\] 会话运行时池 `HeartflowManager`：OrderedDict LRU，上限 100 个活跃会话，24 小时不活跃者淘汰，每会话一把 `asyncio.Lock`。

### 4\.2 会话运行时与唤醒模型

\[REPO·高\] 每个会话一个 `MaisakaHeartFlowChatting` 状态机（STOP / WAIT / RUNNING），核心是一条 `asyncio.Queue[Literal["message","timeout","proactive"]]` 轮次队列。**没有全局心跳、没有定时思考循环**——唤醒源只有三个：新消息、`wait` 工具到期、插件触发的主动任务（`enqueue_proactive_task`，构造不落库的合成触发消息）。重启后 `_restore_recent_context_from_db()` 恢复短期上下文并注入「醒来」文案。

### 4\.3 触发闸门：LLM 之前的廉价决策层

这是 MaiBot 当前架构里最值得抄的设计之一。「要不要开一轮思考」完全不花 LLM 调用，由规则层完成，两套互斥闸门按配置切换：

- \[REPO·高\] **频率阈值门** `FrequencyThresholdTurnGate`：`pending 条数 + 空闲等效条数 ≥ 阈值` 即触发；阈值与「有效回复频率」反相关；空闲等效数封顶为阈值\-1，保证至少要有一条真实消息。
- \[REPO·高\] **回复必要性门** `ReplyNecessityTurnGate` → `score_reply_necessity()`，纯规则打分 0–100、阈值 80：相关性（@命中 100 / 名字提及 80 / 私聊 40 / 普通群消息 0）\+ 内容分（疑问 \+15、直接请求 \+20、征求意见 \+20、长文加分、纯「哈哈/6/？」短反应批次 −25）\+ 积压压力分（比值平方升至 50，超阈后对数升至 100，空闲 \+15）− 在场惩罚（最近窗口内自己发言占比 ≥0.60 扣满 25，防刷屏）；总分再乘频率系数。词表硬编码中文语用（「帮我」「你觉得」……），甚至有一条正则识别「这句话是在叫 DeepSeek/ChatGPT/Kimi 等别家 AI」而降权。
- \[REPO·高\] 外围还有三层：**指数退避**（连续空转轮次后 `base × 2^n` 延迟，仅群聊生效，积压超阈直通）；**focus 槽位配额**（`FocusModeManager`，同 scope 内同时只允许一个会话占用决策槽，冷却默认 120s——注意：这个「focus」与旧版「专注聊天模式」同名不同义，现在是注意力配额器）；**planner 可中断**（新消息到达可打断正在跑的 planner 请求，受连续打断次数上限约束，打断后等消息静默窗口再重启）。

\[INFERRED·高\] 设计原则提炼：**高频小决策（值不值得醒）用规则，低频大决策（说什么做什么）用 LLM。** MaiBot 旧版曾用「意愿值/兴趣度」等仿生数值系统做这件事，最终收敛为可解释、可调参的显式规则打分——仿生隐喻输给了工程可控性。

### 4\.4 决策：单 planner 调用 \+ 工具循环

\[REPO·高\] 一轮 \= 一次 planner LLM 请求（`task_name="planner"`）。回复不是「决策之后调用生成器」，而是 planner 主动调用名为 `reply` 的工具；一轮不调任何工具即为沉默（`planner_no_tool_end`）。动作空间 \= 10 个内置工具（`reply / wait / send_emoji / send_image / query_memory / query_person_profile / fetch_history / view_forward_message / tool_search / switch_chat`，已复核）\+ 插件工具 \+ MCP 工具 \+ 浏览器工具，统一经 `ToolRegistry` 的 provider 机制装配；工具太多时用 **deferred tools \+ `tool_search` 懒加载**（与 Claude Code 的延迟工具同构）。planner 上下文由多个注入器组装：中期记忆摘要、人物画像、黑话参照、行为经验参照、群聊注意力块、时间块。

### 4\.5 生成与发送

\[REPO·高\] `reply` 工具 → `ReplyerManager`（按会话缓存生成器）→ 独立的 replyer LLM 请求（`task_name="replyer"`，模板 `maisaka_replyer`，注入人格、回复风格、表达习惯；hook 可置 retry，上限 3 次）；表达方式由一个**子 Agent**（`expression_selector`）从向量索引召回的候选中挑选。生成后处理：颜文字保护 → 按句切分（`response_splitter.max_length / max_split_num`）→ **中文错别字注入**（`chinese_typo.*`，拟人化噪声）→ 逐段发送，仅第一段带引用；`send_service` 按字数模拟打字延迟（中文 0.3s/字），出站 hook 两枚，经 `platform_io` 路由到 driver。发送后：**message\_id 回执对账**（适配器回传 `message_id_echo`，把内部 ID 替换为平台真实 ID）、自发消息落库、通知记忆自动化服务、回写 MaiSaka 历史。

\[REPO·中\] 防复读不是文本级去重，而是把「你最近已回过这条」作为提醒注入上下文的软约束；另有 `ReplyEffectTracker` 对回复效果做事后 LLM 评估。

* * *

## 5\. 认知子系统

### 5\.1 长期记忆 A\_Memorix 2.0

\[REPO·高\] 独立命名、独立版本（2.0.0）、独立作者署名的仓库内子系统，形态是「**进程内内核 \+ RPC 形状的门面**」：`MemoryService`（门面/DTO）→ `AMemorixHostService.invoke(component_name, args, timeout_ms)`（18 个具名组件 \+ 模糊修改组件）→ `SDKMemoryKernel`（进程内构造，已复核非子进程）。\[INFERRED·高\] 接口做成 RPC 形状是在为未来「记忆外置为独立服务」预留切割线——边界先行，进程后置，这个手法本身值得学。

**存储四件套**：SQLite 元数据（19 张表：`paragraphs / entities / relations / episodes / fact_claims / fact_evidence / fact_transitions / person_profile_refresh_queue / memory_feedback_tasks / delete_operations …`，含 FTS 全文索引）\+ faiss 双向量池（段落池与图池分离，带自动迁移循环）\+ 稀疏矩阵图存储（实体\-关系三元组）\+ BM25 稀疏检索（jieba 分词）。检索走双路召回融合（`DualPathRetriever / FusionConfig`，细节未深查）。

**写入两条自动回写路径**（均可配置开关，默认开）：

1. \[REPO·高\] **人物事实回写**：bot 每次发言后触发 → 队列（容量 256）→ 过滤寒暄类短语（`_looks_ephemeral`，「好的」「晚安」）→ 收集用户侧证据 → LLM 抽取事实 → `ingest_text` 落库，metadata 携带 `person_id`、证据消息 ID、来源标签 `user_supported`。
2. \[REPO·高\] **会话摘要回写**：每 36 条消息触发一次摘要入库；重启后从元数据恢复游标防重复。

另有导入中心（WebUI 批量导入原始资料）与**冷启动写队列**：内核未就绪时写入先落 JSONL（`startup_write_queue.jsonl / .done / .failed`），就绪后回放——启动期数据不丢（已复核）。

**读取三条路径，主次分明**：

1. \[REPO·高\] **主路径 \= LLM 主动调 `query_memory` 工具**（默认开）：5 种模式（search/time/hybrid/episode/aggregate），person 过滤无命中自动降级为关键词检索，结果以 `【长期记忆检索结果-内部参考】` 标记回填上下文。
2. \[REPO·高\] **启发式被动召回**（**默认关**）：先让 LLM 生成「当前聊天印象」，以印象为 query 检索，注入上限 900 字符、最小间隔 180s、要求 60 条新消息——门控极重。
3. \[REPO·高\] **人物画像注入**（默认开）：最多 3 人。

\[INFERRED·高\] 结论：MaiBot 用真实流量投票选择了「**记忆检索 Agent 化**」——让模型自己决定何时查、查什么，而不是每轮强行 RAG 注入；被动注入保留为重门控的补充。这与旧版海马体「每条消息都激活记忆图」的思路完全反转。

**维护与生命周期**：\[REPO·高\] 内核内 9 个后台循环（自动保存、向量索引训练、情景物化、画像刷新队列、维护循环→冻结/剪枝/孤儿回收等）；对外动作 `reinforce / freeze / protect / restore / 回收站`；changelog 描述为「随时间自然衰减，被采纳或有新证据时强化」。反馈纠错子系统（用户否定旧记忆 → 任务队列 → 软标记/硬过滤/画像强刷）存在但**默认关**。

**人物画像的七段文本协议**（\[REPO·高\]，硬契约，全文已取）：`# 人物画像` \+ 七个固定小节（身份设定/关系设定/稳定了解/相处偏好/近期互动/不确定信息/维护备注），每节条数封顶（4/4/6/5/3/3），注入时裁掉「不确定信息」「维护备注」两节、近期互动再截到 2 条；人工覆写（manual\_override）优先于自动画像。\[INFERRED·高\] 把「模型生成的画像」约束进一个可校验、可裁剪、可人工覆写的文本 schema，是对抗画像漂移与上下文膨胀的低技术高收益手段。

### 5\.2 三套学习系统

\[REPO·高\] 全部挂在同一个触发点上：**当消息被裁剪出上下文窗口时学习**（`_trigger_trimmed_history_learning`）——即「遗忘之际，沉淀经验」。

1. **表达方式学习**：LLM 从将被遗忘的对话里抽取「情境 → 说话风格」对（prompt `learn_style`），存 `expressions` 表（含使用计数、最后激活时间、人工核验位），检索侧走独立向量索引 \+ 选择子 Agent，选中的表达习惯注入 replyer 的 system prompt。至少 10 条可学消息才起批，带并发上限。
2. **黑话/梗学习**：`jargons` 表（含证据消息、含义推断、是否黑话/是否完整/是否全局、推断轮数），经 `jargon_context_matcher` 在相关语境出现时注入参照。
3. **行为经验学习**（新一代，旧版无对应物）：五张表（经验路径/场景簇/场景标签簇/动作/结果），记录「在什么场景做了什么动作得到什么结果」，含观察学习与自我反思两类；决策时场景分析子 Agent 打分召回 top\-3 注入 planner。\[INFERRED·中\] 这是把强化学习的 credit assignment 用「LLM \+ 结构化经验库」的离散方式近似——工程上激进，效果未知，Amadeus 应观望而非跟进。

### 5\.3 人格与情绪

\[REPO·高\] 人格 \= 纯配置注入：`personality`（人设）、`behavior_style`、`reply_style`、`multiple_reply_style[]`（按概率随机切换的备选风格）五个字段，直接进 prompt 模板，无运行时人格状态。**有状态的情绪系统已于 0.12.0 删除**，残留一个 `build_personality_emotion_suffix` 后缀函数；情绪的功能位由表情包选择与多风格随机切换承接。WebUI 提供「自然语言 → 结构化人格配置」的生成器。

\[INFERRED·高\] 教训：情绪状态机是拟人 Agent 最诱人也最先被删的模块——用户感知微弱、状态维护成本高、与 LLM 自身的语气生成能力重复。Amadeus 若要做情绪，必须先定义「用户可感知的差异」验收标准，否则不做。

### 5\.4 人物双层模型

\[REPO·高\] 轻量身份层（主库 `person_info` 表：跨平台身份、昵称、群名片、认识时间/次数）与重量语义层（A\_Memorix 画像 \+ fact\_claims/fact\_evidence/fact\_transitions 事实三表）分离。旧版「关系值/印象系统」已消失，功能位由画像协议承接。

### 5\.5 表情包子系统

\[REPO·高\] 完整闭环：偷图（`steal_emoji`）→ VLM 生成描述 → 内容审核 → 注册（满额时 LLM 决定替换谁）→ 使用（`send_emoji` 工具把候选表情拼成**带编号九宫格**交给子 Agent 选择，模型回退链：emoji 专用模型 → 支持视觉的 planner 模型 → VLM）。存储复用 `images` 表。\[INFERRED·中\] 九宫格拼图选表情是用「一次视觉调用替代 N 次文本比对」的取巧，值得记入模式库。

* * *

## 6\. 支撑层

### 6\.1 插件运行时

\[REPO·高\] 要点：manifest v2（`_manifest.json`：插件 ID 反域名式、语义化版本、host/sdk 版本区间、依赖、能力声明、i18n）；SDK 独立发包（`maibot-plugin-sdk`），8 个组件装饰器（`@Tool @Command @HookHandler @EventHandler @API @MessageGateway @HomeCard @LLMProvider`，`@Action` 已 Legacy）；生命周期三钩子（`on_load / on_unload / on_config_update`）缺一拒载；`ctx` 上 17 个能力代理，对应 **73 个具名 capability**（`send.* / llm.* / database.* / chat.* / message.* / person.* / emoji.* / maisaka.* / render.html2png …`），Host 侧按能力授权。IPC 为 UDS/命名管道上的 Envelope RPC（`protocol_version / request_id / message_type / method / plugin_id / timeout_ms / payload / error`），Host→Runner 17 方法、Runner→Host 白名单仅 3 个裸方法；调试流量落 JSONL。热重载带 600ms 去抖、依赖反向级联、跨组重载拒绝；健康检查 30s、重启上限 3 次、熔断状态上 WebUI。

\[REPO·高\] 两个隐性契约值得警惕：Runner 子进程 `stdout=DEVNULL`（插件 print 直接消失，日志必须走 IPC 批量通道）；隔离粒度为组非插件。

### 6\.2 事件与 Hook 双轨

\[REPO·高\] 粗粒度 EventType 11 个（ON\_START/ON\_MESSAGE/ON\_PLAN/POST\_LLM/AFTER\_SEND…）\+ 细粒度具名 hook 16\+ 个（`chat.receive.* / maisaka.planner.* / maisaka.replyer.* / send_service.* / expression.* / jargon.* / emoji.*`），hook 支持 blocking（串行可中止、可改参）与 observe（并发旁观）两种模式，五级确定性排序（mode → slot → 内置优先 → plugin ID → handler 名）。\[INFERRED·高\] 「事件粗轨 \+ hook 细轨」的双轨扩展面比单一事件总线表达力强，Amadeus 可直接采用该分层。

### 6\.3 LLM 编排

\[REPO·高\] 三层：`LLMServiceClient` 门面 → `LLMOrchestrator`（任务化模型池：**12 个任务角色** replyer/planner/memory/mid\_memory/utils/learner/expression\_use/emoji/vlm/voice/embedding/tool\_calling，每任务独立模型列表 \+ 温度/超时/慢阈值；选择策略 balance（默认，按累计 token\+惩罚项最小化）/random/sequential；重试与故障转移分类精细——429/5xx/空响应耗重试、413 触发图片压缩且不耗重试、400 换模型、其余 4xx 立即失败；失败请求快照落盘限 128 份）→ 客户端仅两类：openai 兼容 \+ gemini 原生，其余厂商全走 openai 兼容层。用量（含 cache 命中/未命中 token）入库并小时聚合。

\[INFERRED·高\] 「任务角色 × 模型池 × 策略」是小团队多模型运维的最简可用形态，Amadeus 应原样采纳概念（非代码）。

### 6\.4 配置体系

\[REPO·高\] 双 TOML（`bot_config.toml` 25 节 / `model_config.toml`），各自独立版本号（8.14.33 / 1.17.6）\+ 7 个版本化升级钩子 \+ legacy 迁移边界；Pydantic 模型即 schema（模板文件已取消，默认值由代码生成，WebUI 暴露 `/config/schema`）；FileWatcher 600ms 去抖热重载，scope 化传播（bot/model/self）经 RPC 广播到插件，带 1s 最小间隔、20s 超时、回调异常隔离与失败回滚。

### 6\.5 存储

\[REPO·高\] 主库 SQLite 单文件（WAL、`user_version` 驱动的 35 步前向迁移、无降级），22 张表（消息/会话/人物/表达/黑话/行为×5/图片/工具记录/用量/统计聚合×4/监控事件/维护任务）；A\_Memorix 自带独立存储（自有 SQLite \+ faiss 文件 \+ 图文件）。\[INFERRED·高\] 「主库管运行数据、记忆引擎管认知数据」的双库切分干净利落；但 SQLite 锁定了单机命运。

### 6\.6 WebUI 与可观测性

\[REPO·高\] WebUI \= FastAPI :8001 全套管理面（配置/插件商店与镜像源/记忆管理/表达/黑话/行为/统计/日志 WS 推送），前端产物以 PyPI wheel（`maibot-dashboard`）分发——后端零 Node 依赖即可带 SPA，这个分发技巧可抄。可观测性：structlog 三 handler（文件 JSONL/控制台/WebSocket）；`maisaka_monitor_events` 表 \= **推理过程事件账本**（每轮 planner/工具/回复的结构化留痕）；LLM 失败快照；用量小时聚合。

\[REPO·高\] **反面教材一枚**：遥测默认开启（文档口径），端点为明文 HTTP 的裸主机名 `http://HOST:PORT`（已复核），上报 UUID、系统信息、token 用量与成本。功能无恶意（不含聊天内容），但「默认开 \+ 明文 \+ 不可审计端点」三连是 Amadeus 必须显式反着做的合规决策。

* * *

## 7\. 演进墓地：MaiBot 删掉了什么

| 死者 | 死因（\[INFERRED·中\]，基于架构变迁反推） | 对 Amadeus 的启示 |
| --- | --- | --- |
| 情绪状态机（0.12.0 删） | 用户感知弱；与 LLM 语气能力重复；状态维护成本高 | 情绪先定义可感知验收，否则不立项 |
| 海马体记忆图 \+ LPMM 知识库 | 两套各自为政的认知存储，被统一内核（段落\+图\+向量\+情景多视图）取代 | 记忆要一个引擎多种视图，不要多个引擎 |
| normal/focus 双模 \+ 意愿/兴趣度系统 | 仿生数值系统不可解释不可调参；双模切换复杂度爆炸 | 「要不要醒」用显式规则打分；「说什么」交给单一工具循环 |
| 回复频率自动调整（0.12.0 删） | 同上，隐式自适应输给显式配置 | 先给用户旋钮，再谈自动化 |
| 独立适配器进程（进行中） | 部署复杂、生命周期难管，迁往「适配器即插件」 | Amadeus 一开始就单轨：适配器是受管扩展，不是伴生进程 |

\[REPO·高\] 快速 pivot 的化石随处可见：目录还叫 `heart_flow`、类名还叫 `HeartFCMessageReceiver` / `MaisakaHeartFlowChatting`，文档写着已迁走的 `runner_manager.py`、已改名的 `trymai.db`，manifest 示例与能力注册表格式不一致。\[COMMON·高\] 教训是通用的：概念重构必须连带命名与文档一起迁移，否则每个后来者（包括 AI 助手）都会被旧名字带进沟里。

* * *

## 8\. 优缺点系统评估

评价基准声明：评价对象是 v1.1.0 当前形态；基准是 Amadeus 的真实语境（见 §12 定位约束与项目库《amadeus\-soul\-设计方案》）：小规模自托管、拟人陪伴方向、且 MaiBot 目前同时是 **Amadeus 的宿主平台**与**未来独立系统的参照系**。同一特性换语境结论会反转（例：SQLite 单文件在本语境是优点，在多租户语境是硬伤），下列每条均按本语境下结论。

### 8\.1 优点（十项，按对 Amadeus 的价值排序）

1. **认知成本外置——规则闸门拦住高频决策。** \[REPO·高 机制 / INFERRED·高 评价\] 「要不要醒」全由零 LLM 成本的打分与退避完成，LLM 只在值得的轮次被唤醒。这是它能在活跃群聊里长期运行的经济基础；值得注意的是 Amadeus Soul 插件独立发明了同构的分权（思考权在 LLM、约束权在代码）——两个项目在无交流前提下收敛到同一结构，互为佐证。
2. **决策收敛为单 Agent 工具循环。** \[REPO·高\] 动作空间统一（回复即工具）、扩展即插工具、无双模切换复杂度；与业界主流 agent 架构同构，也与《naga\-架构评审》第一条决策（原生 function calling）天然兼容。
3. **记忆读写路径「主动为主、被动重门控」。** \[REPO·高\] 检索 Agent 化（query\_memory 工具）而非每轮强制 RAG；写路径异步队列不阻塞对话；冷启动写队列不丢数据。这是用真实流量投票选出的反教条设计。
4. **接口先行的可置换性。** \[REPO·高\] MemoryService 的 RPC 形状门面、platform\_io 的 driver 抽象、ClientRegistry 的 provider 注册——三处都为替换留了缝，边界先行、进程后置。
5. **任务角色化模型池 \+ 精细故障转移。** \[REPO·高\] 12 个任务角色各配模型列表与策略；413 压缩不耗重试、400 换模型的分类处置是生产级细节。
6. **工程韧性细节密度高。** \[REPO·高\] message\_id 回执对账、画像七段硬协议、推理事件账本、LLM 失败快照、配置升级钩子\+失败回滚、插件熔断——这些「无聊」细节是真实流量磨出来的，也最难凭空想到。
7. **扩展面分层完整。** \[REPO·高\] EventType 粗轨 \+ 具名 hook 细轨 \+ capabilities 声明授权 \+ MCP 原生；对插件作者（包括 Amadeus Soul）表达力充足。
8. **拟人化后处理成体系。** \[REPO·高\] 分段/错别字/打字节奏/表情包闭环/表达学习——开源界少见的完整「说人话」流水线，对拟人定位的 Amadeus 是现成的需求清单。
9. **配置即 schema。** \[REPO·高\] Pydantic 生成默认值与 WebUI 表单，模板文件消灭，版本化\+热重载\+scope 传播到插件。与 naga 评审第六条（零硬编码）同向。
10. **运营面完整度超出同类。** \[REPO·高\] WebUI 全托管（插件商店/镜像源/记忆管理/统计/日志流），前端以 PyPI wheel 分发、后端零 Node 依赖。

### 8\.2 缺点（十项，按对 Amadeus 的风险排序）

1. **插件「隔离」不是安全边界。** \[INFERRED·高，由进程模型推出\] Runner 是同 UID 子进程，capabilities 只约束宿主中介的 API，不约束 OS 资源（文件/网络任意访问）。装第三方插件 \= 本机代码执行。Amadeus 若开放三方生态必须补真沙箱；自用则风险可控。
2. **隐式 LLM 成本扇出。** \[REPO·高 调用点存在 / INFERRED·中 无预算机制\] 一轮可能触发 planner\+replyer\+表达选择子agent\+表情选择子agent\+回复效果评估\+事实抽取\+摘要\+学习批次约 8 类调用，靠任务池配便宜模型缓解，但无全局预算闸。
3. **复杂度与维护者规模不成比例。** \[REPO·高 数字 / INFERRED·高 评价\] 25 配置节、33\+ 记忆配置类、19 张记忆表、9 个后台循环、73 能力、26 RPC 方法——配置面已大于多数用户的调参能力，对单人项目是认知负担而非资产。
4. **单机天花板。** \[REPO·高\] SQLite\+进程内记忆内核\+进程内会话池，无租户概念。对当前定位无害，但是定位变更时的硬墙。
5. **双轨过渡债。** \[REPO·高\] legacy WS 适配器与插件适配器并存，无拆除时间表；新旧概念同名异义（focus）加剧理解成本。
6. **文档\-代码漂移已发生。** \[REPO·高\] trymai.db vs MaiBot.db、已迁走的 runner\_manager.py、manifest 能力格式两套口径——**Amadeus Soul 的防御性代码（EventType 双路 import、stream 多键名解析、命令 match 兑底）就是这条缺点的受害者实证**。
7. **命名化石与概念残影。** \[REPO·高\] heart\_flow 目录、HeartFC 类名、focus 语义翻转；新贡献者与 AI 助手都会被旧名带偏。
8. **语用硬编码。** \[REPO·高\] 打分词表、寒暄过滤、AI 称呼正则全是简中字面量，多语言即失效；Amadeus 三平台（含自有前端）必然撞上。
9. **遥测默认开 \+ 明文 HTTP \+ 裸主机端点。** \[REPO·高\] 功能无恶意（不含聊天内容），但三连组合是合规反面教材。
10. **测试与评测薄弱。** \[REPO·中—仅见顶层 pytests/ 目录，内容与 CI 未查明，此条置信度打折\] 推理质量回归无回放体系，调参靠人肉。

### 8\.3 综合判断

\[INFERRED·高\] MaiBot 的架构智慧集中在**运行时形态**（闸门/循环/记忆读写/拟人后处理），它的债集中在**工程治理**（安全边界/成本/文档/测试/命名）。Amadeus 借鉴前者时，后者恰好是设计伊始零成本做对的事；而作为宿主使用时，缺点 6/7（漂移与化石）意味着**一切以文档为准的插件开发都必须用源码二次验证**（§11 有具体案例）。

## 9\. 扩展方向

分两类：MaiBot 自身轨迹内的（它大概率会做，Amadeus 跟随即可），与 Amadeus 应主动开拓、MaiBot 没做或做不了的。

### 9\.1 MaiBot 轨迹内（跟进即可，无需抢跑）

\[INFERRED·中，由代码中的未完成态推出\] 适配器全面插件化收尾（legacy WS 拆除）；记忆内核外置为独立服务（RPC 门面已备）；@Action → 工具体系迁移收尾；插件商店生态（镜像源/统计代理已在）。这些方向上 Amadeus 只需观察宿主版本更新，不必自建。

### 9\.2 Amadeus 应主动开拓的七个方向

1. **跨平台身份图谱。** \[REPO·高 现状 / INFERRED·高 缺口\] MaiBot 的 person\_id 由 (platform, user\_id) 派生，同一个人在 TG/QQ/自有前端是三个互不相认的人。Amadeus 三平台并行 \+ 长期陪伴定位，身份合并（可验证的手动绑定为主、概率提示为辅）是记忆一致性的前置条件，属独立系统 P1 必做；插件形态下的多目标支持（Soul P2）是其雏形。
2. **评测与回放体系。** \[INFERRED·高\] 以事件账本（账本设计抄 MaiBot 的 maisaka\_monitor\_events）为地基做「决策回放」：同一段历史流量在新 prompt/新闸门参数下重放对比。MaiBot 有账本无回放，这是低成本高杠杆的差异化点；Soul P1 计划的「每次思考落一行 JSON」就是这个方向的第一步，建议把字段定成可回放格式（输入快照\+参数\+输出\+是否开口）。
3. **成本治理层。** \[INFERRED·高\] per\-会话/日预算、任务级降级策略（预算尽→只用便宜模型\+提高触发阈值）、缓存感知的 prompt 布局。把预算做成闸门层的一个输入，而非事后账单。
4. **真安全沙箱（若开三方生态）。** \[COMMON·高\] 进程隔离升级为容器/WASM/seccomp；capabilities 从「API 白名单」升级为「资源配额」。若不开生态，MCP\-first 绕开整个问题。
5. **自有前端一等契约。** \[INFERRED·高\] 流式 token、打字指示、消息编辑/撤回、富组件（卡片/按钮）——IM 适配器是能力交集，自有前端是能力全集；契约按全集设计、向交集降级。呼应 naga 评审第四条（真流式）。
6. **语音与实时。** \[REPO·高 现状\] MaiBot 只有 ASR 入站，无 TTS 出站管线；双工可打断的对话式语音是拟人陪伴的下一个可感知台阶（Amadeus 的原作设定也正是语音存在）。注意墓地法则：先出可感知 demo 再立项。
7. **多 Agent 礼仪。** \[REPO·高 线索\] MaiBot 已用正则识别「用户在叫别家 AI」并降权；群内多 bot 共存的显式协议（让话/接话/互相引用）尚无人做，而多平台场景必然遇到。

### 9\.3 刻意不做清单（负空间同样是设计）

\[INFERRED·高\] 有状态情绪引擎、仿生数值外显（好感度/心情值）、每消息强制 RAG、微调专属模型（数据不足）、分布式部署——前三条是 MaiBot 用删除投过票的，后两条与定位约束冲突。

## 10\. Amadeus 借鉴映射

**前提更新**（本节初稿时定位为 \[GUESS\]，现已被文档证实）：项目库《amadeus\-soul\-设计方案》确认 Amadeus 的第一落地形态为 MaiBot 插件（QQ 私聊、红莉栖人设、主动意识），独立系统定位仍在预研（见 §12）。本节按「未来独立系统的参照」书写；对当前插件形态的即时建议见 §11。若最终定位改变，第 10.5 节的分叉结论优先于正文。

### 10\.1 领域边界（限界上下文提案）

\[INFERRED·高\] MaiBot 的模块群可以整理成八个域，其边界在 MaiBot 里是模糊的（`chat/`、`maisaka/`、`services/`、`learners/` 互相穿插），Amadeus 应把它们做成显式契约：

1. **接入域**：平台无关消息 schema、RouteKey 路由、送达回执与 ID 对账。（对应 maim\_message \+ platform\_io）
2. **会话与注意力域**：会话运行时池、触发闸门、退避、焦点配额、打断。（对应 heartflow \+ turn\_scheduler/gates）
3. **决策域**：Agent 循环、工具注册表、动作空间管理、延迟工具。（对应 reasoning\_engine \+ tooling）
4. **表达域**：人格注入、回复生成、风格/表达选择、拟人化后处理、节奏模拟。（对应 replyer \+ utils）
5. **认知域**：记忆内核（多视图存储、读写路径、生命周期）、画像协议、学习系统。（对应 A\_Memorix \+ learners \+ person\_info）
6. **能力域**：插件运行时、MCP 集成、能力授权。（对应 plugin\_runtime \+ mcp\_module）
7. **模型域**：任务化模型池、编排、计量、故障转移。（对应 llm\_models \+ services/llm\_service）
8. **运营域**：配置、管理面、可观测性、部署、遥测。（对应 config \+ webui \+ logger \+ telemetry）

判定标准：任何跨域调用必须走门面接口（MaiBot 的 `MemoryService` / `LLMServiceClient` 是正例）；任何域内实现变更不得泄漏到另一域的 import 里（MaiBot 的 `chat/replyer` 直接 import `maisaka` 是反例）。

### 10\.2 核心模块：直接采纳的六个形态

\[INFERRED·高，均为「采纳概念、清洁室重写」\]

1. **单 Agent 工具循环**为决策核心：一轮一次 planner 调用，回复/等待/查记忆/换会话全部工具化，不调工具即沉默。这是 MaiBot 三年迭代的收敛点，也与业界同构。
2. **规则闸门层**置于 LLM 之前：必要性打分 \+ 频率等效 \+ 指数退避 \+ 在场惩罚 \+ 可中断。Amadeus 的打分维度可换，但「零 LLM 成本的唤醒决策」这一层必须存在。
3. **任务角色化模型池**：按任务（planner/replyer/记忆/嵌入/视觉…）配模型列表与策略，故障转移分类处置。
4. **记忆 \= 门面 \+ 进程内内核 \+ RPC 形状接口**：读路径以工具调用为主、被动注入重门控为辅；写路径自动回写（事实抽取 \+ 摘要阈值）\+ 冷启动写队列；生命周期显式（衰减/冻结/回收站）。
5. **画像文本协议**：固定小节、条数封顶、注入时裁剪、人工覆写优先。
6. **事件粗轨 \+ hook 细轨**的扩展面，hook 带 blocking/observe 与确定性排序。

### 10\.3 数据流（Amadeus 目标闭环）

\[INFERRED·高\] 值得整体继承的完整环：

```
平台事件 → 接入域(schema归一/去重/路由)
  → 会话域(闸门: 规则打分→轮次调度→可中断)
  → 决策域(planner×1 → 工具调用×N)
      ├→ 认知域读(记忆工具/画像注入)
      └→ 表达域(replyer×1 → 拟人后处理 → 节奏化发送)
  → 接入域(送达回执→ID对账)
  → 认知域写(事实回写/摘要回写, 异步队列)
  → 学习(上下文裁剪时触发, 异步)
  → 运营域(推理事件账本/用量计量, 全程旁路)
```

三个易被忽略但已被 MaiBot 验证的细节：ID 对账（平台真实 message\_id 回填，引用/撤回/去重都依赖它）；冷启动写队列（认知写入不因启动时序丢失）；推理事件账本（每轮决策结构化留痕，是调参与回归的地基）。

### 10\.4 接口契约

\[INFERRED·高\] 四个契约面按 MaiBot 形态起草即可：平台消息 schema（组件化 Seg，文本/图/at/引用/语音/文件/转发节点；媒体 Base64 内联在聊天尺度够用，\[INFERRED·中\] 大媒体应改引用式）；扩展 RPC（Envelope：协议版本/请求 ID/方法/超时/错误码，双向白名单）；扩展清单（manifest：语义化版本 \+ host/sdk 兼容区间 \+ 能力声明式授权）;工具契约（JSON Schema 参数 \+ provider 注册 \+ 延迟加载）。MCP 作为第一方扩展协议原生支持（MaiBot 已如此：stdio/http 两传输、保留名冲突检测、stdout 容错过滤）。

### 10\.5 部署拓扑（条件分叉）

- **若 Amadeus 是个人/自托管单实例**（MaiBot 同类）：\[INFERRED·高\] 直接继承「单容器进程组」形态：主进程 \+ 扩展子进程（隔离崩溃域）\+ 管理面独立线程/进程 \+ 嵌入式存储（SQLite WAL \+ 本地向量文件）。不要过早引入外部数据库与消息队列。
- **若 Amadeus 是服务化/多租户**：\[INFERRED·高\] MaiBot 拓扑不可迁移，但其**切割线**可迁移：记忆门面的 RPC 形状接口 → 记忆独立服务；platform\_io 的 driver 抽象 → 接入网关独立部署；任务化模型池 → 集中式模型网关。每租户一个「会话运行时」的 LRU 池模型仍然成立，只是宿主从进程变成分片。
- 无论哪种：\[COMMON·高\] 遥测默认关、HTTPS、端点可审计；崩溃域粒度（组 vs 单扩展）作为显式 ADR 决策而非默认。

### 10\.6 技术债防范清单（从 MaiBot 的债反着学）

\[REPO·高 债的存在 / INFERRED·高 对策\] ① 概念改名必须连带目录、类名、文档同步（heart\_flow 化石）；② 文档从代码生成（配置文档由 Pydantic schema 生成，MaiBot 已做对；数据库/路径文档手写导致 trymai.db 类漂移，做错）；③ 双轨过渡要有拆除时间表（legacy WS 通道至今未拆）；④ 隐性契约显式化（插件 stdout 丢弃应写进 SDK 文档与 lint）；⑤ 硬编码语用词表（中文打分词表）应做成可配置数据文件——Amadeus 若面向多语言，这是第一处要抽象的地方。

### 10\.7 演进路线建议（吸收 MaiBot 的删除史）

\[INFERRED·高\] 分四期，每期以「用户可感知差异」为立项门槛：

- **P0 骨架**：接入域 schema \+ 单 Agent 工具循环 \+ 规则闸门 \+ 任务化模型池 \+ 版本化配置 \+ 推理事件账本。此为最小可对话体，不含长期记忆。
- **P1 认知**：记忆门面 \+ 内核 v1（段落\+向量\+画像三视图即可，图与情景后置）\+ 两条自动回写 \+ `query_memory` 工具。画像协议同步落地。
- **P2 生态**：先 MCP\-only（成本低、生态现成），插件运行时（进程隔离 \+ manifest \+ capabilities）仅在出现真实第三方需求后立项——MaiBot 的插件系统复杂度极高（73 能力 × 26 RPC 方法 × 双 Runner），是其多年社区生态倒逼的结果，Amadeus 没有这个前提。
- **P3 拟人深化**：表达学习、黑话、行为经验、主动性策略——全部以 A/B 可感知为验收，随时准备像 MaiBot 删情绪系统一样删掉它们。

对应建议立项的 ADR：ADR\-001 定位与租户模型；ADR\-002 决策循环形态（采纳单 Agent 工具循环的论证）；ADR\-003 记忆引擎边界（门面接口 \+ 内核可置换）;ADR\-004 扩展战略（MCP\-first vs 插件运行时）；ADR\-005 许可证与清洁室边界（GPL 参照物处理规程）。

* * *

## 11\. 对当前落地形态 Amadeus Soul 的直接建议

本节是本报告与《amadeus\-soul\-设计方案》的交叉产物：用 MaiBot 源码事实直接回答插件的待决问题。按优先级排序。

**其一，插件加载路径——你的 P0 问题 \#3 有确定答案，且很可能是命令失效的真因。** \[REPO·高\] 宿主只扫描两个根：`src/plugins/built_in/`（builtin 组）与仓库根 `plugins/`（third\_party 组）；`src/plugins/<名字>` 不在任一扫描范围内。你的安装目标 `/opt/MaiBot/src/plugins/amadeus_soul` 若属实，插件从未被加载——CMD\_PATCH\_V2 修的是症状不是病根 \[INFERRED·高\]。行动：裸机部署移到 `/opt/MaiBot/plugins/amadeus_soul`；若是官方 compose，放入映射到容器 `/MaiMBot/plugins` 的宿主机目录（官方默认 `./data/MaiMBot/plugins`）。验收：WebUI 插件页或 `GET /api/webui/plugins/installed` 出现 Amadeus Soul。

**其二，部署重启对象存疑，而且其实可以不重启。** \[REPO·高\] 宿主对插件源码有 FileWatcher 热重载（600ms 去抖、依赖级联），WebUI 另有安装/重载 API（`POST /api/webui/plugins/install` 支持仓库地址安装）。你的一键脚本重启的是 `maim-bot-napcat`（QQ 协议端），它不会重载 MaiBot 插件 \[INFERRED·高\]。行动：脚本只负责传文件，重载交给热重载或 WebUI。顺带：官方 compose 的 core 容器 `TZ=Asia/Shanghai` \[REPO·高\]，若沿用则你的时区债 \#10 不存在。

**其三，日志：别用 print，用 ctx.logger，然后在 WebUI 看。** \[REPO·高\] Runner 子进程 `stdout=DEVNULL`，print 直接消失；`ctx.logger` 经 IPC 汇入宿主日志管线，WebUI `/ws/logs` 可实时流看。这直接满足你 P1「免上服务器看日志」的诉求：SSH 隧道 18001 端口即可，不必 tail 日志文件。

**其四，主动链路的架构选择：两套嗓音问题。** 现状是「插件自思考 \+ ctx.send.text 直发」，绕开了宿主的人格/表达习惯/错别字/分段管线——她的主动消息和被动回复是两套嗓音 \[INFERRED·高\]。宿主提供 `maisaka.proactive.trigger` 能力（对应 `enqueue_proactive_task(plugin_id, intent, reason)`，合成触发消息不落库，走完整 planner→工具→replyer 链路）\[REPO·高\]。两个自洽方案：A. 保持自发送（完全控制文风），但补 `maisaka.context.append` 把主动消息写进宿主推理历史，消除「宿主不知道她说过什么」的割裂；B. 插件退化为「刺激源\+闸门」，开口交给宿主 proactive 轮次——嗓音统一、记忆/表达全套生效，代价是内容控制权下降。建议：拿「随机灵感」场景先试 B，早晚安等仪式性场景留在 A，用真实体感定徒。

**其五，AFTER\_SEND 双记验证（你的债 \#4）。** \[REPO·中\] `send.*` 能力经宿主 send\_service 出站，该链路带 POST\_SEND/AFTER\_SEND 事件桥——插件自己发的消息大概率也会触发你的 observe\_send。按你的计划验证后删手动 push 即可；若采纳方案 B，此问题自然消失。

**其六，记忆分工与语义去重（你的债 \#6/\#7）。** \[REPO·高\] 宿主有 A\_Memorix（人物事实自动回写 \+ `knowledge.search`/person 能力）。建议分工：约定/纪念日（需要「到期回访」语义）留插件本地；一般事实交宿主记忆，插件经能力查询。精确串去重可用 `ctx.llm.embed`（该能力存在 \[REPO·高\]）做余弦阈值合并，顺带替掉 `_is_repeat` 的字符集 Jaccard。

**其七，版本契约防御的正解。** \[REPO·高\] 你的 EventType 双路 import、stream 多键名解析、命令 match 兑底，根因是宿主快速迭代\+文档漂移（§8.2 第 6 条的受害者实证）。manifest v2 有 `host_application{min,max}` 与 `sdk{min,max}` 兼容区间——把范围钉死，升宿主前先读 changelog，比运行时兑底更省。

**其八，人格单一来源。** 插件内置红莉栖人设与宿主 `[personality]` 是两个真相源，会漂移。短期人工保持一致（你已在 README 提示）；中期插件经 `config.get` 读宿主人格作基底，自身只叠加「主动场景专用」增量 \[INFERRED·中，能力存在但字段粒度未验证\]。

一句总结：先把插件搬到对的目录（其一），再用宿主的日志通道建立观测（其三），然后再谈嗓音统一（其四）——顺序颠倒会在看不见的地方白费力气。

## 12\. 定位约束与推论（2026\-07\-26 会话答复更新）

原开放问题已获用户答复（来源：本会话问答，非推测）。逐条记录答复及其对本文结论的修正：

**其一，定位：尚未定型，先预研。** 推论：\[INFERRED·高\] 本文所有条件分叉保留原状；P0 骨架必须对「拟人陪伴／助理混合／多租户」三种定位保持中立——具体而言，人格与拟人化后处理（错别字、打字节奏）不得下沉进表达域核心，须作为可整体关停的策略层。

**其二，部署：小规模自托管（自己 \+ 少量群/好友）。** 推论：\[INFERRED·高\] §10.5 取「单实例 \+ 预留切割线」分支：嵌入式存储（SQLite WAL \+ 本地向量文件）够用且正确，不引入外部数据库与消息队列；但记忆门面、接入网关、模型编排三处接口按 RPC 形状设计，为日后可能的服务化留缝。MaiBot 的进程组拓扑（主进程 \+ 扩展子进程 \+ 管理面独立线程）可直接继承。

**其三，许可证：纯开源，GPL 可接受。** 推论：\[COMMON·高\] 清洁室约束解除——§0 反方论据其二的严格程度由「读设计、不碰代码」放宽为「可直接复用 MaiBot / A\_Memorix 代码」。但注意不可逆性：一旦复用 GPL\-3.0 代码，Amadeus 的许可证选择空间永久收窄至 GPL 兼容族，且日后若想转商用闭源需完整剥离。此决策应显式落为 ADR\-005，而非默认发生。

**其四，平台：Telegram/Discord \+ QQ \+ 自有前端（网页/App）三线并行。** 推论：\[INFERRED·高\] 这是四个答复中对架构影响最大的一个——平台无关消息内核由「值得借鉴」升级为**强制需求**；适配器单轨制（适配器 \= 受管扩展，无 legacy 双轨）进入 P0；自有前端意味着接入域必须同时暴露一等公民的 API/WS 契约（MaiBot 的 maim\_message「API\-Server 模式」——API Key 鉴权 \+ 用户隔离——可作参照）。消息 schema 设计时须以三平台能力交集为核心组件、以扩展组件承载平台特性（QQ 的戳一戳、Discord 的 embed 等），否则内核会被最复杂平台绑架。

**补记（2026\-07\-27 凌晨）**：答复后数小时内，项目库新增《amadeus\-soul\-设计方案》——Amadeus 已有第一个落地形态（MaiBot 插件，QQ 私聊主动意识，红莉栖人设）。与「定位尚未定型」不矛盾：插件是最短路径的探索载体；它使本报告从「参照系分析」同时升级为「宿主手册」，对插件的直接建议见 §11。

**修正后的 ADR 立项顺序**：ADR\-001（定位）合法延后；先行四项在三种定位下同构——ADR\-002 决策循环形态（单 Agent 工具循环）、ADR\-003 记忆引擎边界（门面 \+ 可置换内核）、ADR\-004 扩展战略（MCP\-first，插件运行时后置）、ADR\-005 GPL 代码复用决策（含 A\_Memorix 直接复用 vs 形态重写的成本对比）。

## 13\. 附录：关键事实速查与未查明清单

**速查**（全部 \[REPO·高\]，已交叉/复核）：内置工具 10 个；必要性打分阈值 80；会话池 LRU 100 个/24h；摘要回写阈值 36 条消息；画像七段协议注入裁 2 节；主库 22 表；A\_Memorix 元数据 19 表；配置 25 节双 TOML（8.14.33 / 1.17.6）；EventType 11 / 具名 hook 16\+；插件能力 73 项 / RPC 方法 17\+9；模型任务角色 12 个；端口 8000(WS)/8001(WebUI)/8090(API)/3001(NapCat)；遥测 `http://HOST:PORT`（600s 心跳 / 11451s 统计）。

**未查明**（后续 clone 后补）：内置插件名单；A\_Memorix 表列定义与检索融合公式；`ExpressionConfig` 等四个配置类全字段；`plugin_type` 十值与运行时三值的关系；NapCat 适配器仓库组织名；builtin 工具的 stage 划分规则。

* * *

**\[我打破的规则 / RULES I BROKE\]**

1. **扩展了标签体系**：新增 \[REPO\] 标签（本会话实证），因原六标签无「当次会话从外部来源实取的事实」类别，用 \[KNOWN\]（训练记忆）标注它们反而是错误归因。为准确性而破格。
2. **未逐句标签化**：对机制描述采用「节首标签 \+ 默认 \[REPO·高\]」的批量标注约定，仅对推断/常识/猜测逐条显式标注。逐句标签会使文档不可读；已在文首声明该约定。
3. **保真链非一手**：约 85% 的代码事实经由研究代理的网页抓取转录（二手），我仅亲自复核了六个承重事实。文中置信度已按此打折，但严格说「\[REPO·高\]」中仍含未逐一亲验的条目。
