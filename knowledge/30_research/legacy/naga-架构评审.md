# NagaAgent 架构评审报告（供 Amadeus 借鉴）

> 基于 NagaAgent 3.0 源码逐层验证。标签：[KNOWN] 源码直接验证 · [INFERRED] 逻辑推演未运行。置信度 HIGH/MED/LOW。未运行程序，运行期结论为 [INFERRED]。
> 完整版工作文档见 Cowork 会话；本文为 Amadeus 项目留存的精要版。

## 一、结论（反方开篇）
naga 不是"值得整体学习的架构"，而是"值得解剖的反面教材 + 少数可提取的局部零件"（HIGH）。整体照搬会继承三个结构性错误：自造文本工具协议、把进程内方法调用误命名为"MCP"、大量"写完从未跑通"的半成品（含 2 个语法错误无法 import 的 agent）。正方位置：作为单人快速拼装的能跑 demo 是成功的；manifest 插件发现、pydantic 配置、TTS 并发生成串行播放等局部正确。**把 naga 当"需求清单 + 踩坑地图"，不要当"参考实现"。**

## 二、系统概览
单进程多线程：main.py 同进程内拉起 PyQt GUI（主线程）+ FastAPI:8000（后台线程）+ Flask TTS:5050（后台线程）。分层：编排核心 conversation_core / 插件层 mcpserver / 记忆 summer_memory / 思考 thinking / 语音 voice / UI ui / 配置 config。
**病根信号**：编排核心 `NagaConversation` 一次启动被实例化 4 次（main.py:24,135；pyqt:310；api_server.py:70），靠 3 个模块级全局布尔量防重初始化——用全局标志打补丁替代单例/依赖注入（HIGH）。

## 三、核心数据流的三个错误决策
| 决策 | naga 做法 | 问题 |
|---|---|---|
| 工具契约 | 自造文本协议 `「始」…「末」`+正则 | 放弃原生 function calling 的结构化保证（HIGH） |
| 流式 | 非流式拿全量→按行切 yield | 首 token 延迟=整段生成时间，假流式（HIGH） |
| 思考旁路 | 每轮额外发一次 LLM 判难度 | 固定多一次调用/延迟，开关硬编码无法关（HIGH） |

## 四、逐层评估要点
- **conversation_core（33KB 上帝对象）**：无接口边界；库代码劫持内建 print；GRAG 调用整段注释而非配置关闭。
- **mcpserver（叫 MCP 非 MCP）**：manifest 驱动发现方向对（HIGH 亮点）；但 unified_call 是纯进程内 `handle_handoff` 方法调用，manifest 的 protocol/timeout 是死字段；真 MCP 仅 playwright 一处；三套注册表 + 同名方法互相覆盖。
- **工具契约**：解析逻辑在 core 与 api_server 各写一遍；api_server.py:526-544 缩进逻辑错乱。
- **summer_memory（GRAG）**：LLM 抽三元组→双写 triples.json+Neo4j→关键词 CONTAINS 召回；无向量/无多跳；Cypher 注入（graph.py:95）；hash 去重跨进程失效；json 全量读改写无锁；默认禁用。
- **thinking（重灾区/伪算法）**：变异禁用（genetic_pruning.py:356 return []）；树只一层；打分从不回写节点；中文 split() 使多样性维度恒失效；线程池零 submit；每轮强制多一次 LLM 调用且硬编码开；quick_model_manager 37KB 纯死代码。价值为负。
- **voice**：TTS 输出可用且"并发生成+串行播放"正确；ASR 调用不存在的 SDK 方法不可用；Minimax 分支不可达；websocket_tts/audio_player 死代码；劫持全进程 stdout。
- **ui + apiserver**：600 行巨型类，__init__ 同步构造核心阻塞 GUI；设置项 signal key 与处理端常量对不上→UI 开关全失效；/memory/stats 引用不存在属性；FastAPI /chat 双 /v1 必失败（GUI 走 SDK 不受影响，两链路各写各的）。
- **config（本项目最高质量层，可整体借鉴）**：pydantic 集中配置+校验+兼容层。但硬编码疑似真实 API Key（config.py:65,570）；开发者本机路径入库；2 个 agent 真语法错误被静默吞掉；system_control os.system shutdown + 全局键盘钩子不 unhook。

## 五、可提取的亮点
1. manifest 驱动插件发现（声明式 capabilities 可喂 LLM）——但运行时须真正兑现 manifest。
2. pydantic 集中配置 + 兼容层（密钥须改走环境变量）。
3. TTS 并发生成 + 串行播放。
4. 真 MCP client 样板（playwright.py:278，MCPServerStdio + finally 释放）。
5. 难度分级温度阶梯采样 + `<think>` 标签清洗。
6. 响应解析多层兜底（本质是上游契约不稳的补丁，Amadeus 应从源头统一契约）。

## 六、对 Amadeus 的七条决策
1. **契约优先**：工具调用用原生 function calling + JSON schema 校验，别自造文本协议。
2. **一个核心对象、一处所有权**：单例/依赖注入，GUI/API/CLI 都是客户端，不各自 new。
3. **发现与调用对齐**：保留声明式 manifest，但运行时真正读取协议/超时/schema；要么真 MCP（进程隔离）要么诚实叫"进程内插件"，别用 MCP 命名非 MCP。
4. **真流式**：token 级 SSE。
5. **可选能力统一开关、默认关**：汇入统一配置，不硬编码、不用注释关功能。
6. **密钥/路径/端点零硬编码**：密钥走密钥管理。
7. **显式进程模型**：明确哪些进程内、哪些独立服务，各自 event loop 与失败隔离边界。

一句话：复用 naga 的需求分解与踩坑地图，但**编排核心 / 工具契约 / 进程模型 / 配置密钥**四件事重新设计，不继承其实现。

## 七、未验证边界
未运行程序（结论为静态可判定的 [INFERRED]）；API Key 是否有效未知（假设已泄露应轮换）；仅读 config.json.example 未读设备真实 config.json；agent_word_office 未逐行复核。

**[我打破的规则]**：无。全部主张附 文件:行号 或标注 [INFERRED]；无框架→现实映射；无捏造引文；反方开篇；无免责/赞美。
