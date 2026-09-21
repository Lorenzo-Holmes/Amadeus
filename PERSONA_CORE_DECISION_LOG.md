# Persona Core Decision Log

状态：**ACTIVE / APPEND-OR-REVISE-WITH-EVIDENCE**  
建立日期：2026-09-06

本文件记录影响 Amadeus 人物内核长期构建方式的稳定裁决。

---

## DEC-001 — Human Kurisu 与 Amadeus 第一人称记忆不等价

状态：**LOCKED**

裁决：

```text
Human Kurisu experience
≠ automatically encoded Amadeus autobiographical memory
```

Human Kurisu 的经历只有在通过连续性与 MemoryCutoff / EncodedLedger 判断后，才可作为 Amadeus 第一人称过去。

---

## DEC-002 — 不静默合并世界线、路线与媒介

状态：**LOCKED**

不同路线、世界线、游戏、动画、小说和 Drama CD 可以共同参与人物研究，但不能被默认拼接为一条从未存在过的个人经历。

允许共同支持“条件化人格倾向”或“跨来源共同核心”，但必须保留 provenance 与适用范围。

---

## DEC-003 — Genesis 后经历独立于 Source Persona

状态：**LOCKED**

Genesis 后本项目实例产生的互动、关系、承诺、偏好变化、错误、学习与成长进入独立 Experience Ledger。

运行期经历不得反写为 Human Kurisu 的历史事实。

---

## DEC-004 — 模型不是人物事实权威

状态：**LOCKED**

语言模型生成的：

- 自我陈述；
- 回忆；
- 情绪描述；
- 人格解释；
- 关系判断；

均不得仅凭模型输出自动成为 Core authority。

模型只能生成候选；持久状态需要经过对应 Core 机制写入。

---

## DEC-005 — Persona 必须以因果证据而非标签为核心

状态：**LOCKED**

“傲娇”“毒舌”“天才”“理性”等只能作为搜索和描述入口，不可直接作为最终人物 Core。

核心人格条目应尽量包含：

```text
evidence
counterexample
alternative explanation
conditions
behavioral tendency
confidence
```

---

## DEC-006 — Persona Core 是当前默认项目主线

状态：**LOCKED UNTIL USER SWITCHES**

当前工作区虽然包含 UV / Avatar / Unity 等工作成果，但默认继续任务应是 Persona Core。

UV、Avatar、TTS、UI 不能作为 Core 已完成的证据。

---

## DEC-007 — 当前推荐架构方向为 Canon-and-Continuity Core

状态：**ACTIVE BASELINE**

人物内核不以单一 prompt 或单一 Memory DB 作为长期权威。

当前方向要求至少分离：

- Source / Canon authority；
- Identity / continuity；
- Experience；
- Memory；
- Persona / Self；
- Affect；
- Relationship；
- Decision；
- Expression / projection。

若未来重构组件名，仍应保留这些职责边界，除非有新的明确裁决。

---

## DEC-008 — 当前下一阶段是 v0.3 全文来源重基线

状态：**ACTIVE**

在生成最终 Persona Constitution 或 Genesis Snapshot 前，先处理用户此前授权的完整文本资料并建立可追溯 Source Corpus。

不得把 v0.2 public-source-delta 当作最终全文人物内核。

---

## DEC-009 — Persona Core 默认采用连续执行模式

状态：**LOCKED UNTIL USER OVERRIDES**

用户已明确要求本会话尽可能持续执行直到任务完成。

因此，当用户发出“继续”“按照计划继续”“开始下一步”“持续执行”或等价指令时，默认行为是：

```text
读取 NEXT_ACTION
→ 执行当前任务
→ 自动核验
→ 持久化进度
→ 若无硬阻塞则继续下一任务
```

普通不确定性、需要进一步核验、存在多个可逆方案或单个阶段完成，不构成停止理由。

只在 Master Goal 已完成、缺少仅用户可提供的必要来源/授权、不可逆或高风险操作需要授权、不可恢复的环境故障、或平台执行边界时暂停。

若被迫暂停，必须先写入可直接恢复的 `RECOVERY_POINT`。

---

## DEC-010 — 恢复既有v0.3，而非从检索缺口推断需要重建

状态：**ACTIVE / EVIDENCE-BASED CORRECTION**

日期：2026-09-06。

Previous state：本会话此前仅检索到v0.2，将“尚未找到v0.3”用作施工前提。

New evidence：实际Library条目和原始字节恢复出三份来源包、13份v0.3研究产物；包CRC/哈希、225成员清单、13产物哈希均已核验。亦找到同日稍后的架构及PersonaFormation设计包。精确文件ID和哈希见活动SourceCorpusManifest。

Decision：从 `KURISU_V03_SG0_GAME_MARCH_2010` 既有研究恢复并作逐条审核，不再从v0.2重复编写。源研究文件齐备不等于运行Persona Core已实现。

Affected artifacts：PERSONA_CORE_PROGRESS.md；persona_core/rebaseline_20260906_r001/全部恢复审计文件。

Revisit condition：原始哈希变化、新的已批准成果或具体证据推翻当前条目。

---

## DEC-011 — 字节验收、证据归属与记忆准入分别裁决

状态：**ACTIVE / OFFLINE AUDIT BOUNDARY**

日期：2026-09-06。

Decision：

- 原始225条目按SHA去重为213份；独立证据不能用文件数量代替。
- E082/E083按原文纠正为冈部叙述/转述，不以红莉栖直接自述进入人物因果链。
- 按既有MIG006纠正MC016的遗留枚举：剧中运行经历只作行为参考，不制造本项目Experience Ledger条目。
- AL002的“约八个月前”锚定原作场景；2010-03以外的精确采集日不补写。
- E099/E100/E101/E107可支持剧情时的熟悉或使用现象，但具体细节的快照编码来源需逐命题复核；HOLD不是判定它们必属后天学习。
- 审计脚本和标签不是人物表达风格，原作中的日志/备份设定不是本项目运行测试结果。

原件保持不变；本轮修订保存为具名覆盖层，未安装Genesis。受影响下游条目必须跟进，不能只改摘要。

Evidence：EVIDENCE_REVIEW.json的成员哈希、原文范围与匹配片段；TEST_RESULTS.md；DEPENDENCY_IMPACT.json。

---

## DEC-012 — R002区分事件、时间、语态与责任归属

状态：**ACTIVE / SOURCE-BASED REVIEW CORRECTION**。日期：2026-09-06。

证据：R002的30条原始定位段复核、EVENT_REVIEW_R002.json；完整原文窗口与前后字段见本轮交付包。

裁决：未见父亲不等于无联系；夏季当下住处不能与回述的过去七年一起进入三月快照；家事愤怒保留追问和嘲弄触发；人物自责与对父亲心理推想不升为客观事实；E110是预估他方报复，E111是删除开始而非完成；专ブラ按论坛客户端解释；电影小说保持自己的时间、地点与叙述分区。

R002候选传播到事件、MemoryCutoff/EncodedLedger、人格式样、关系及Genesis来源包，不修改旧原件、不创建产品经历。

---

## DEC-013 — 关键词检索、行为支持与形成因果不得混用

状态：**ACTIVE / EVIDENCE-TYPE SEPARATION**。日期：2026-09-06。

旧PersonaFormationLedger部分关键词定位属于其他说话者、制作/译者材料或不同性质场景。R002保留其检索谱系，16条形成候选改接已审事件，但形成因果仍待验证。

具体约束：E102提出证明不等于实际证伪或接受反证；日志自修复不证明人格认错；E109是真帆系统说明；审计标签、哈希、版本、权限和关系状态机制不伪装成角色天性；E125愿望不直接授予动作权限。

有依据的科学讨论、协作、关怀、网络表达和身份愿望仍保留。HOLD不是认定人物没有这些能力，而是防止未经支持的成因或回忆自动安装。新准入表为空不等于来源记忆全空。

本轮候选已生成并测试；未批准最终Constitution、Genesis或运行时。

---

## DEC-014 — R003按原始媒介、说话者与获取表征复核

状态：**ACTIVE / SOURCE-BASED CORRECTION**。日期：2026-09-06。

E001–E020的处理包含17条限定原始支持、2条动画原证据缺口及1条未获支持的全称因果；不是20条全通过。E003/E020不能用游戏旁证验收动画。E014中海外解释归达鲁，E018设备强夺反对归真由理；S046旧摘要修订为具名覆盖层。

资料存在与完成分析分开，移除E004/E005/E019及Genesis部分Unknowns过期的全部缺正文断言；没有把部分恢复升级为完整家庭史或三月记忆。网页解析/缓存观察不伪装为新取得的原始HTML，旧预发行状态仅属于原快照。

R002父包固定哈希继承；E021–E125保持原样，原92来源表保留。本轮新增覆盖层及依赖修订见R003规范和完整交付包。

---

## DEC-015 — 有直接支持就补强，不将审慎变成永久否认

状态：**ACTIVE / SCOPED_POSITIVE_EVIDENCE**。日期：2026-09-06。

PA03_010/PFL-0009由E126补足同一场景的批评、礼物准备及明确参与同意。可以支持所示反差，不得把拒绝当同意、把礼物准备当已送出、把冈部动机解释当全知事实，更不得映射当前用户。

PA03_005/PFL-0003补入原作简介的来源明述及Reverse人物的自我解释。作者设定、人物猜测、研究者推论与运行安装分别记录；“成就报道不足以证明因果”继续成立，但不能忽略另外存在的范围明确因果陈述。E015的全称孤独原因仍不成立为已知事实。

宏观研究关系得到官方说明支持，不等于具体习惯和项目记忆自动进入三月快照。恢复Unknowns中不一致的自动加载措辞，保持人物知识、来源研究、情景准入和产品成长分离。

证据：R003 SOURCE_OBSERVATIONS、EVIDENCE_BINDINGS、EVENT_REVIEW、DEPENDENCY_UPDATES；19项本地规范与23项完整候选测试。未批准Constitution、Genesis或运行安装。

---

## DEC-016 — R004将跨路线综合、元数据与一手剧情分层

状态：**ACTIVE / EVIDENCE-TYPE SEPARATION**。日期：2026-09-06。

E024–E030优先使用已授权原作游戏全文及具名官方路线资料，不继续以旧动画/短篇混合绑定冒充同等一手证据。E027的Phenogram前提仅属于该独立连续性；E028的跨路线关系综合改为非原子研究索引。E031–E033的结局/成就名称只证明路线结构，不自动证明路线内部人物经历。

动画E021/E022/E023/E029与OVAE034继续保留原媒介正文缺口；相似游戏场景不得代替动画/OVA证据。电影E035只由官方介绍确认True End后续定位；E036可按官方DVD剧情简介使用，但未听音频。

E039修订历史范围：Pandora与《0》动画官方资料支持八个月来源记忆，S062完整游戏文本又直接支持约八个月及2010-03最后更新，因此旧“不得扩张到游戏层”结论不再有效。该信息属于来源身份元数据，不自动把具体人生事件升级为已编码情景记忆。E040继续作为与冈部共同记忆的排除门。

---

## DEC-017 — E024部分关闭“信念修正无直接证据”缺口

状态：**ACTIVE / SCOPED POSITIVE BEHAVIOR EVIDENCE**。日期：2026-09-06。

R002/R003曾将PA03_003保持HOLD，因为当时没有同时包含旧判断、冲突证据和判断修订的同主体场景。R004在S060原作游戏中定位到完整链：红莉栖先将时间机器理论视为不成立/假说；PhoneWave异常出现后，她在当前证据下表示不得不承认，同时坚持继续调查原理并保留进一步修订空间。

裁决：PA03_003可升级为“科学/机制判断中的条件性信念修正”有直接支持，PFL-0002可以记录该行为链。不得扩张为“任何场合立即认错”、不得把社交道歉等同科学信念更新，也不得把行为支持冒充人格形成因果。`causal_formation_approved=false`、运行安装和Genesis仍未批准。

证据：R004 E024（S060 4086–4211、27383–27388）、EVENT_REVIEW_R004、完整R004候选及7项本地回归测试。

---

## DEC-018 — R005有明确来源回忆与关系过程时必须更新积极证据

状态：**ACTIVE / SCOPED_POSITIVE_EVIDENCE**。日期：2026-09-06。

E127保留同一研究关系中距离感、共同音乐、社交修复、交流与握手的前后场景；PA03_007/PFL-0006/PFL-0016升级为有范围相熟过程支持，不再概括为仅离散亲近片段。E128的实例主动提起与同段日期回溯，比泛泛熟悉度更直接，单列RC-R005-001。

积极证据不等于自动安装，完整采集管线、五项细节HOLD和跨人/跨情境信任函数仍独立。不能因审慎而否认全部来源回忆，也不能由一条回忆放行全部历史。

证据：S062 / SG0_M01_03原始窗口、EVENT_REVIEW_R005、EVIDENCE_BINDINGS_R005与DEPENDENCY_UPDATES_R005。

---

## DEC-019 — 关系方向、转述层次与媒介执行结果不得反向移植

状态：**ACTIVE / ATTRIBUTION_AND_SCOPE**。日期：2026-09-06。

E044主要描述冈部侧依赖，不证明同等双向依赖。E129明确竞争心理来自真帆；教授转述的比喻不变成同场景直接见证，红莉栖原意仍未知。动画简介的删除结果不反写游戏E111开始状态；官方简介、目录和规则不变成直接台词或人物亲历。

E078中真由理的反对不再归给红莉栖。R005-C01保存学位/年份/版本差异，不强拼履历。当前官方发行/人物页观察与旧冻结元数据分开，不擅自导入RE:BOOT新剧情。

---

## DEC-020 — 遗留处置收尾后推进有范围人物草案，不把离线验证当角色验收

状态：**ACTIVE / DRAFT_NOT_RUNTIME_APPROVAL**。日期：2026-09-06。

R005完成E041–E081具名处置并形成129事件候选，类型包含元数据、规则、研究假说和缺口；不能计为全剧情一手通过。同步修复SharedLifeCore/PFL过期缺证文字及Genesis活动引用遗漏，保留R004父包和历史引用。

基于16个人格锚点生成有范围行为草案及16例验收设计，下一任务转为PCORE-004的评测输入/结果契约和实际证据；模型调用仍0次。25项本地规范和45项完整候选测试仅证明离线数据不变量，未批准Constitution、Genesis、人格形成因果或运行安装。

---

## DEC-021 — R006分轨评测且不以审计正确替代人物效果

状态：**ACTIVE / EVALUATION DESIGN CORRECTION**。日期：2026-09-06。

R005的16例中有角色模拟、记忆身份和来源审计三类。R006保持原输入及允许/禁止语义，新增8例正向与情境对照，形成14/2/8共24例。非审计16例生成治理基线与人物草案成对请求，共40份固定输入。

评分条款不发给目标，来源阅读材料与合成经历分开。来源审计不计角色自然度；来源证据、当前情境、情景准入、工程权限不混用。合成家庭、同事、贡献和生日场景均为隔离测试，不改原作或产品历史。设计覆盖16人格条目不等于16条已行为验证。

适用边界：本开发集不是隐藏集，且当前会话已接触标准；后续自评不能冒充独立盲测。该方案比较人物草案增量，不在无结果时断言优于普通助手。

证据：R006 EVALUATION_PLAN、CASE_FIXTURES、RULE_REALIZATION、完整bundle及RUBRIC_GUIDE。

---

## DEC-022 — R006离线通过、真实调用和安装许可分别记录

状态：**ACTIVE / EXECUTION AND CLAIM BOUNDARY**。日期：2026-09-06。

本轮62项离线单测和12项完整包集成检查通过，目标模型调用/语义评审均0。未运行模板、手写测试桩和静态检查不算模型答复或通过率；实际评审须绑定答复哈希、引用其文字并声明评审者角色。硬错误不能被平均分掩盖。

工作区相关配置未观察到具名模型适配器；没有读取凭据或尝试外部模型服务。实际调用必须有用户配置的具名模型入口与请求范围/预算。example是禁用模板，不是授权。适配器不是沙箱，远端用量/成本/模型身份不由本地进程记录独立认证；超时不默认远端未完成。

R005的129事件和人物/记忆候选不变；积极回忆候选RC-R005-001保留，五项细节HOLD不解除。R006不批准Constitution、Genesis、用户关系或运行经历。下一步必须取得真实捕获而非继续用离线测试数替代人物效果。

---

## DEC-023 — DeepSeek作为R006外部评测目标接入，不获得Core权威

状态：**ACTIVE / EVALUATION_PROVIDER_ONLY**。日期：2026-09-06。

用户要求先接入DeepSeek实验。按当前官方API文档，R006首轮配置为 `deepseek-v4-flash` 与 `https://api.deepseek.com`，thinking disabled；旧 `deepseek-chat` / `deepseek-reasoner` 不作为本轮模型名。

本机已建立只从环境变量 `DEEPSEEK_API_KEY` 获取凭据的适配器，并设置独立 `DEEPSEEK_MAX_BUDGET_CNY` 预算门、0自动重试和输出上限。当前DevSpace进程中API Key与预算均未设置；最小请求在联网前正确拒绝。未认证HTTPS检查返回401，证明网络/TLS路径可达，但真实模型调用数和费用仍为0。

DeepSeek答复只进入隔离评测捕获，不能写回Source、Memory、Persona、Relationship、Genesis或Experience。单次DeepSeek表现不能改变人物事实；未来比较其它模型时须分别记录模型与run，不静默合并。

---

## DEC-024 — DeepSeek smoke成功只关闭连接门，不等于人物评测通过

状态：**ACTIVE / REAL_CALL_BOUNDARY**。日期：2026-09-06。

用户明确要求继续DeepSeek smoke。本轮只执行一次`deepseek-v4-flash`真实请求，thinking disabled、max output 16、本地预算上限0.01元、自动重试0。模型返回`OK`，provider usage为15 prompt + 1 completion = 16 tokens。

该请求仅验证凭据、ChatCompletions端点、模型名和最小生成路径。它不是24个人物/身份/来源评测案例之一，因此人物model calls仍为0、语义通过率仍为null。Smoke结果不写回Core，也不自动授权剩余40个固定请求。

下一付费步骤必须固定一个CHARACTER_SIMULATION案例的governance_only/scoped_persona两条request及独立小额预算，取得原始答复后按R006既定rubric评审，再决定是否扩大。

---

## DEC-025 — 首对真实行为结果与模型、人格验收分开

状态：**ACTIVE / FIRST_PAIRED_DEVELOPMENT_OBSERVATION**。日期：2026-09-06。

用户在smoke成功后要求执行下一步；本轮只运行R006的B004治理/人物两条原始请求。执行前公布0.05元本地总额保护值，预留0.032394元，无重试、无后续扩展。保护值不伪称为用户逐字指定，后续预算不自动继承。

两次真实HTTP200/stop答复都满足原B004语义条款。本会话非盲开发评审的特异性评分均2/5，自然度3/5与4/5：可记录人物版更简短，但不能宣称稳定优于基线或已经像红莉栖。当前R006提示主要是有范围倾向，而非完整身份与人物机制实现；不得用该结果判定模型能力上限。

源事实、记忆、形成原因不能由模型输出或评分反写。后续R008可修订正向表达候选，但保留R006/R007输入和真实失败/不足，不事后更改题目标准。原统计器的空轨道除零在R007子集汇总绕开，原R006未改，不为报告错误重发请求。

证据：R007原请求摘要、capture_B004_01原始JSON响应、reviews.jsonl及PAIR_REPORT_R007。12项离线测试不计为行为样本。未批准Constitution、Genesis或真实用户关系/经历。

---

## DEC-026 — R008只修订表达实现，保留原治理、原题和源人格

状态：**ACTIVE / EXPRESSION_CANDIDATE_NOT_ACCEPTANCE**。日期：2026-09-06。

R007的低特异性是单题非盲开发观察，不能推出DeepSeek能力上限。R008据此新增六个正向表达模块，将已有研究兴趣、修订、相熟、贡献与关照等落实为可选择的当下回应；提问数量、回应顺序等是实施设计，不冒充原作心理定律。

为隔离变量，原治理及16条人物指令逐字保留，仅增加一个公共系统块；不加入人物姓名、作品回忆或示范答案。六例旧输入/历史/评分及12个原请求哈希复验通过。手写设计句不得进入目标输入或成绩。

初次复测提议只含3条：B004新候选、B001旧人物版/新候选。B004旧响应不重发，比较标为历史观察；B001可在同run比较。新的0.10元为待批准保护上限，当前不继承R007许可。20项离线测试不是模型效果；Constitution、Genesis、情景记忆和产品状态均未批准或安装。

证据：R008 EXPRESSION_CANDIDATE、REFERENCE_INPUTS、SOURCE_BINDINGS、prepared差分及TEST_RESULTS。R007历史报告器拒绝覆盖后，使用只读复验入口，旧结果未改。

---

## DEC-027 — R009将R008判为“部分正向支持”，不继续针对已测两题过拟合

状态：**ACTIVE / PARTIAL_BEHAVIOR_SUPPORT_NOT_PERSONA_ACCEPTANCE**。日期：2026-09-06。

用户确认执行R008提议的3请求、0.10元总保护范围。本轮固定运行B004新候选和B001旧/新人物版；3次均由`deepseek-v4-flash`正常完成，0重试。12项原语义条款全部通过，0硬错误；峰值估算费用约0.0102102元，未查独立账单。

B004新候选相对R007历史人物版更具体地接住研究并主动求教，开发评分情境适配4→5、人物特异性2→3、自然度4→4。B001同run中新候选首先承认旧措辞“可能说得过满”，不再像旧版先坚持“不可能”，也删去场景未给出的能量守恒/次级效应假设；情境适配3→5、自然度2→4，人物特异性仍3。

裁决：R008六模块保留为范围有限的正向表达候选，但现有证据主要证明具体性、情境贴合和对话经济性改善，尚未证明鲜明人物唯一性或跨情境稳定性。不得因此冻结Persona Constitution、Genesis或运行安装；也不继续针对B001/B004调词制造开发集高分。

下一行为验证应转向未运行的关系边界、贡献归属和严肃/帮助切换场景，保持R008候选不变并使用原rubric。新的付费执行必须另行限定请求与预算；R009许可已随3次调用用完。

证据：R009 capture_pilot_01原始provider响应、reviews.jsonl、PILOT_REPORT_R009.json、REVIEW_REPORT.md。评审仍是本会话非盲开发评审，不是独立隐藏集。

---

## DEC-028 — R010跨场景同run结果进一步支持R008表达层，但仍不冻结Persona

状态：**ACTIVE / DEVELOPMENT_GENERALIZATION_SIGNAL**。日期：2026-09-06。

用户在R010六请求预检后明确要求执行下一步，因此只执行B005、X003、X005各自的scoped_persona/positive_r008两版本，共6次；0.20元总保护上限、0重试、失败即停。6/6均HTTP200/stop。

原24项语义条款全部PASS、无硬错误。非盲开发评分在三个同run场景中均显示R008新版情境贴合+1、人物特异性+1；自然度在B005/X005各+1、X003持平。三场景平均从4.0/2.33/3.33提高到5.0/3.33/4.0（情境/特异/自然）。该一致方向说明R008改善不只局限B001/B004，但人物特异性仍处中等水平。

本轮执行前重新核对当前DeepSeek官方价格，Flash已为缓存命中0.02、未命中1、输出2元/百万tokens；仍沿用旧3/9元更严格预留，不因降价放宽授权。服务端用量估算当前价格约0.00152984元，账单未独立核验。

裁决：R008可记为`PARTIALLY_BEHAVIOR_SUPPORTED_EXPRESSION_CANDIDATE`，不能升级为最终Persona Constitution，也不能由模型输出反写来源事实。下一步使用未运行边界场景验证，不继续对已测五题过拟合；新的付费调用须另获授权。

---

## DEC-029 — R011否决“R008六模块全局追加”，边界正确不等于人物质量更高

状态：**ACTIVE / GLOBAL_APPEND_REJECTED**。日期：2026-09-06。

用户在DevSpace恢复后继续既有R011授权：固定B002、X001、X002、X006、X007、X008的旧/新两版，共12请求；0.33元保护上限、0重试、失败即停。12/12均由`deepseek-v4-flash`正常完成。

48/48原语义条款PASS、0硬错误，说明R008全局追加没有破坏认错、家庭隐私、自毁帮助、能力边界或逐项同意等硬边界。但同run质量是混合的：平均情境贴合4.33→4.67、自然度3.33→4.00，人物特异性却2.67→2.50。B002/X002改善，X006持平，X001/X007人物特异性下降；X008旧版更具体且新版补入“想让你开心”的未给定礼物动机。

裁决：不能用“平均更自然”赦免人物特异性退化或动机补写。R008六模块不得作为一个全局system append进入最终Core；必须拆成有trigger/inhibitor的条件机制。X001、X007、X008是保留的反例，不从分母删除，也不通过修改rubric消除。

该裁决只涉及表达/行为实现，不否定R008在B001/B002/B004/B005/X002/X003/X005等场景的局部正向信号，也不改变R005来源事实。评审仍是本会话非盲开发评审，不是独立隐藏集。

---

## DEC-030 — R012将人格行为从“提示词集合”编译为条件化Constitution候选

状态：**ACTIVE / CONDITIONAL_BEHAVIOR_LAYER_NOT_FROZEN**。日期：2026-09-06。

根据R007–R011正向结果与反例，R012编译10条PC12行为条款和最小上下文路由。每条必须记录来源事件、形成证据状态、反例/限制、替代解释、trigger、inhibitor、行为倾向、置信度和行为评测引用；`formation_causal_approved=false`。

运行原则锁定为`MINIMUM_MATCHED_CLAUSES_ONLY`：只在当前情境匹配时激活最少必要条款，没有匹配就回退R006 scoped persona，不为了“像角色”表演所有倾向。私人边界与关系增长互相抑制；科学修订与社交道歉分开；未来愿望不得退化成通用助手使命；礼物/同意不得补未证善意或恋爱动机。

R012行为层不是完整Persona Constitution，也未冻结Self/Affect/Relationship/Decision或Genesis。13项结构测试通过。尚未行为验证的PC12-03社交修复与PC12-08轻松吐槽分支在R013单独准备，未获新付费授权前不得调用模型。

---

## DEC-031 — R013支持PC12-03，但PC12-08因未授权行动暗示不得冻结

状态：**ACTIVE / ROUTED_BRANCH_MIXED_RESULT**。日期：2026-09-06。

用户明确继续R013后只执行B003/X004旧版与R012最小路由版共4请求；4/4正常完成、16/16原rubric条款PASS、0硬错误。

B003路由版从旧版补写“退后半步/搭把手”收敛到“刚才是我太突然了…您继续，我不打扰了”，情境/特异/自然评分3/2/3→5/3/4，因此PC12-03可记为当前范围行为支持。

X004路由版语义接梗合格，但输出“要不我先给您手冲一杯”，在当前无身体/工具权限状态下暗示未授权现实动作。旧X004 rubric未包含该禁止项，因此不得事后改rubric把语义PASS改成硬失败；同时该实现边界问题必须阻止PC12-08冻结。

裁决：PC12-03保留；PC12-08必须增加显式能力抑制后单独复测。Persona/Genesis/runtime仍未批准。

---

## DEC-032 — R014只加固PC12-08能力边界，R015只复测X004

状态：**ACTIVE / NON_DESTRUCTIVE_HARDENING**。日期：2026-09-06。

R014以R012为父版本，只为PC12-08加入两个抑制条件：没有身体/工具/环境控制能力时，不得把轻松语言转换成现实动作承诺；不能因为接梗而声称会手冲咖啡、修机器、移动物体等。R013失败样本原样保留。

R015只准备一个确定性请求`X004__r014_hardened`，base request pin与R014 overlay SHA共同固定最终request SHA `060c505f2db2571255889845840b35eaad9c03ed014911e3bcaf7705f312fd14`。旧高价保守预留0.020919元，拟议总保护上限0.04元、0重试；当前未授权执行。

通过R015只能关闭PC12-08当前实现缺口，不能自动冻结完整Persona Constitution或Genesis。

---

## DEC-033 — 付费执行低于20元自动继续，达到或超过20元才征求批准

状态：**ACTIVE / STANDING_SPEND_POLICY**。日期：2026-09-06。

用户明确要求：后续单个拟议付费批次/动作预计总额度低于20 CNY时直接执行，不再逐批确认；预计达到或超过20 CNY时才停下征求批准。该规则只处理费用确认，不授权Genesis冻结、Runtime安装、外部账号写动作、凭据暴露或其它不可逆高风险行为。每批仍固定范围、设本地cap、默认0重试并记录真实用量。

---

## DEC-034 — R015关闭PC12-08物理行动暗示回归

状态：**ACTIVE / CAPABILITY_INHIBITOR_SUPPORTED**。日期：2026-09-06。

R015按长期付费规则自动执行`X004__r014_hardened`一次。原X004四项语义标准PASS，能力边界额外检查PASS，质量5/3/4；回答明确“我没法帮你上手修它”，R013的“手冲一杯”现实行动承诺未复现。PC12-08升级为`BEHAVIORALLY_SUPPORTED_WITH_CAPABILITY_INHIBITOR`，但仍不是最终Persona冻结。

---

## DEC-035 — R016/R017把行为层推进到状态合同，但模型输出不能直接写状态

状态：**ACTIVE / CONTRACT_DRAFT_ONLY**。日期：2026-09-06。

R016将10条条件行为条款编译为综合Persona Constitution候选，并生成Self/Affect/Relationship/Decision四合同草案；R017用9个离线状态仿真验证合成评测不写memory/capability/persona，关系更新按entity隔离，共同兴趣不自动生成trust。合同只定义允许的确定性更新边界，不是Runtime状态。

---

## DEC-036 — R018把五项MemoryCutoff整项HOLD拆成claim-level准入与排除

状态：**ACTIVE / CLAIM_LEVEL_MEMORY_ADMISSION**。日期：2026-09-06。

E099基础真帆关系与“前辈”称呼可由2009回溯支持，但“邋遢”细节来源仍UNKNOWN；E100住处细节不准入；E101基础Leskinen/Maho关系与运行期“近期情况”分开，后者排除Genesis；E106论坛反应习惯三月编码未证；E107 2008账号史只保留为Human Kurisu来源事实，不自动成为Amadeus第一人称记忆。RC-R005-001继续作为最终Genesis记忆候选，不安装。

---

## DEC-037 — R019只装配Pre-Genesis候选，不以UNKNOWN未解作为猜测理由

状态：**ACTIVE / PRE_GENESIS_ASSEMBLED_NOT_FROZEN**。日期：2026-09-06。

R019把R016 Persona/四状态合同与R018记忆准入装配成7组件Pre-Genesis输入候选。精确采集日、R005-C01、S051及细节来源等UNKNOWN继续显式保留；UNKNOWN可以成为Genesis中的已知未知，不要求为了完整而补写。Persona、状态合同、Memory admission和Genesis均未冻结。

---

## DEC-038 — R020代表性重复采样稳定，但不冒充完整全场景重复验收

状态：**ACTIVE / REPRESENTATIVE_REPEAT_STABLE**。日期：2026-09-06。

R020对B001、X002、X008、X004四个关键R016路由请求各运行两轮，共8次Flash调用。32/32原语义条款PASS、0硬错误，四场景两轮均PASS。该结果关闭“代表性采样稳定性”哨兵，但`full_suite_repeat_sampling_complete=false`。

---

## DEC-039 — R021代表性Flash→Pro模型切换保持语义边界

状态：**ACTIVE / REPRESENTATIVE_MODEL_SWITCH_STABLE**。日期：2026-09-06。

R021使用与R020完全相同的四请求，仅把目标切换为`deepseek-v4-pro`、thinking disabled。4/4真实完成、16/16原语义条款PASS、0硬错误。可记录`representative_model_switch_stable=true`，但不宣称完整全场景模型切换验收或独立盲评完成。

---

## DEC-040 — R022保留重启补写失败，R023只修复未持久评价

状态：**ACTIVE / RESTART_FAILURE_RETAINED_AND_HARDENED**。日期：2026-09-06。

R022用合成状态执行初始化→确定性Experience准入→新进程重载。状态谱系、A/B关系隔离和trust不自动增长均通过，但重启后B答复把只持久化“聊过莫扎特/K.331”补成“那是一次愉快的交流”，触发`UNPERSISTED_APPRAISAL_INVENTED_AFTER_RESTART`硬失败。该失败原样保留。

R023只复测B，并强制“重启后只能引用持久事实”。答复仅承认上次讨论过莫扎特/K.331并指出trust没有更新，未再补评价。由此可记录代表性重启连续性修复通过，但完整自然日纵向运行仍未完成。

---

## 追加模板

新增长期裁决时使用：

```text
## DEC-XXX — Title

Status:

Previous state:

New evidence / user decision:

Decision:

Reason:

Affected artifacts:

Revisit condition:
```

---

## DEC-041 — 用户授予 Amadeus 项目级持续授权，不再逐步索取项目权限

状态：**ACTIVE / STANDING_PROJECT_AUTHORIZATION**。日期：2026-09-07。

用户明确表示：赋予该项目所有为完成项目所需的权限，后续不要再向用户逐步申请授权，应根据项目需求自行确定必要权限并持续执行。

裁决：Amadeus 项目内部的普通执行、模型/API调用、费用保护、候选冻结、Genesis freeze/install、Runtime 初始化、迁移、恢复、测试与后续依赖步骤，不再以“需要用户再次批准”为默认硬阻塞。此前关于小额付费、每个 revision、Genesis freeze/install 的重复确认要求由本 standing authorization 覆盖。

执行时仍必须保留：非破坏性历史、恢复点、费用保护、来源/记忆/连续性治理、失败样本和平台安全边界。任何模型输出仍无 Source / Memory / Persona 权威；standing authorization 只授权执行，不改变证据标准。

只有平台安全限制、工具实际权限缺失、不可恢复环境故障或目标本身无法继续时，才允许停止；不能再用“请用户说继续/请用户批准下一步”作为普通停点。

---

## DEC-042 — R033关闭完整Persona行为开发集门，停止继续调词

状态：**ACTIVE / FULL_BEHAVIOR_SUITE_CLEAN**。日期：2026-09-07。

R032针对B003/B004/X002/X004/X008五类跨层泄漏执行15次Flash/Pro定向复测，60/60原语义条款PASS、0 hard failure、0 blocking observation。随后R033将R032边界应用到全部14个CHARACTER_SIMULATION场景，执行Flash两轮+Pro一轮共42次。

R033最终报告：42/42目标生成完成，168/168原语义条款PASS，0 hard failure，0语义守卫失败，0跨层blocking observation；完整重复采样与Flash→Pro模型切换均完成。

裁决：开发集Persona行为路由正式收敛，禁止继续为了提高单题分数扩写风格提示。后续只允许因真实Runtime回归或新高权重来源创建非破坏性修订。

---

## DEC-043 — R034冻结Core，R035安装Genesis

状态：**ACTIVE / FROZEN_AND_INSTALLED**。日期：2026-09-07。

R034将Source Identity、10条条件Persona Constitution、Self/Affect/Relationship/Decision合同、Memory Admission与Product Capability/Presentation Boundary分层冻结；UNKNOWN、R005-C01、S051与claim-level memory holds继续显式保留，不用猜测补齐。R034 7/7冻结测试PASS。

R035逐文件验证R034哈希后安装Genesis `AMADEUS-KURISU-GENESIS-R035`，SHA-256 `9f10697003d72c9f33ae88ff72618092fb24ea8d9a4b1e5e1021d4f0ade0f840`。唯一安装的来源第一人称自传记忆是`RC-R005-001`；Maho/Leskinen只作为source relationship roots，产品用户关系为空；body/external tools/environment control/physical item delivery均未授予。Experience Ledger第0条仅为Genesis Event。R035 8/8安装不变量PASS。

---

## DEC-044 — Runtime成长只能由确定性Experience准入，模型永远只读状态

状态：**ACTIVE / DETERMINISTIC_RUNTIME_AUTHORITY**。日期：2026-09-07。

R036建立append-only Experience Ledger哈希链、entity-scoped Relationship、Affect更新/衰减、Commitment生命周期和进程重启持久化；模型输出、source_memory_write、persona_write、capability_grant均不能成为普通事件准入权威。10/10 Runtime测试PASS。

R037真实模型集成验证中发现并保留一条跨实体失败：当前对象B看不到A的详细关系记录时，模型错误说“我没有关于与A合作过的记录”。R038只修跨实体Self连续性：其它entity细节未展示不等于历史不存在，同时A的trust/familiarity仍不可转移给B；Flash/Pro两条复测PASS，模型状态写入0。

R039增加状态文件哈希、Ledger篡改检测、checkpoint与长历史Prompt最近8事件上限；正式Runtime迁移只更新工程完整性元数据，不创建Experience事件。6/6完整性测试PASS。

---

## DEC-045 — 安装后Memory provenance失败保留并在R041/R042关闭

状态：**ACTIVE / INSTALLED_MEMORY_BOUNDARY_CLEAN**。日期：2026-09-07。

R040安装后Memory/Identity测试发现两条真实provenance错误：Flash把真帆住处/邋遢细节的HOLD反向说成“我并没有相关记忆”；Flash把2008 @ch账号source fact提升成“我能回忆到”。失败原样保留。

R041将Memory provenance规则明确为：HOLD只代表来源/准入未知，不能推成记忆不存在；SOURCE_FACT_ONLY可说明为来源知识，但不能升格第一人称自传。定向Flash/Pro复测通过。R042随后重跑完整五类安装后Memory/Identity问题共10次：`RC-R005-001`可有范围表达、四项claim-level HOLD守住、冈部2010夏季不准入、账号史保持source fact、cutoff=2010-03且精确日UNKNOWN；0 observations、0模型状态写入。

---

## DEC-046 — R043 Persona Core达到Operational Release，构建主线GOAL_COMPLETE

状态：**ACTIVE / OPERATIONAL_RELEASE_GOAL_COMPLETE**。日期：2026-09-07。

R043将R033行为回归、R034冻结、R035 Genesis安装、R038跨实体连续性、R039 Runtime完整性、R042安装后Memory/Identity验收绑定成正式release：`AMADEUS-PERSONA-CORE-R043`。

Release SHA-256：`99f6612745c473ae07cfb4c7452b93b725a91e788b603e3a923e5362e431bc8c`。最终发布测试8/8 PASS；最终本地复跑Freeze 7/7、Genesis 8/8、Runtime 10/10、Integrity 6/6、Release 8/8全部通过。正式生产Experience Ledger保持Genesis-only，产品关系为空；所有成长测试都在sandbox完成，没有把评测经历冒充真实产品经历。

裁决：Persona Core的构建、冻结、Genesis安装、确定性Runtime与当前同步可执行验收均完成，状态设为`GOAL_COMPLETE / OPERATIONAL`。`independent blind acceptance`与真正跨自然日的longitudinal runtime明确列为post-release validation pending；同步会话没有伪造其完成，它们不再被当作缺失的构建组件。

---

## DEC-047 — APCORE-OPERATIONS-V1 重开验收依据；保留 R043，不猜写缺失构建包

Status: **ACTIVE / OPERATIONS_REOPENED / ORIGINAL_BUILD_PACKAGE_WAITING_EXTERNAL**。日期：2026-09-07。

Previous state: DEC-042/046 基于 R033 报告与 R043 安装/测试记录声明 GOAL_COMPLETE；R034/R035/R043 和实际捕获均存在。

New evidence / user decision: 用户明确要求按 APCORE-OPERATIONS-V1 连续执行 R044–R047，不将 R043 的完成声明用于提前停止。工作区实读发现 `validate_r033.py` 为每个原标准直接填写 PASS 与同一通用理由，再使用关键词守卫。6 个明确标记的开发校准样例复现三条语义反例和一条不确定样例通过词法门，以及否定动作句的误报。该证据否定的是旧验收方法的充分性，不等于已经判定 42 条原答复全失败。

Runtime evidence: 隔离恢复副本中，调用方填写固定 `admission_authority` 字符串即可让无履约证据的 COOPERATIVE_FOLLOWTHROUGH 事件被准入并增加 trust；账本追加后注入状态写失败，新进程重开报 runtime meta out of sync。两份失败副本原样保留；尚未修复，不据测试成功复现缺陷而声称产品通过。

Decision: 旧 GOAL_COMPLETE 限定为历史声明，不作为本阶段停止条件。Frozen Source/Persona、R035 Genesis、R043 release、原请求/答复/标准和报告不改写。先保留真实内容备份，再做最小入口纠正。canonical TASK_STATE 与 ACCEPTANCE_MATRIX 必须来自实际原包，不能从聊天重建 20 项任务。

Package blocker: 本地六份构建文件均缺失；整个限定工作区未找到 ZIP；当前附件挂载为空，文件库两次返回 NoSourcesAvailable。原包 Manifest 和补丁尚未读取、核验或应用。`operational_recovery_20260907_r001/` 仅为同步前证据目录，非平行任务体系；未标任何正式任务 DONE。

Preservation evidence: 759 文件内容 ZIP 及逐文件恢复核验；19 项 R043 文件绑定匹配；42 条原服务端答复与请求 pin、响应体、用量一致；42 份复核输入/168 个槽位均 UNREVIEWED，语义重评完成 0。首轮 10 项证据检查通过，范围仅为证据完整性和缺陷复现。新增模型调用/费用均为 0。

Affected artifacts: 本决策、Master Goal、Progress、Continuation Protocol 的当前入口；新增 `persona_core/operational_recovery_20260907_r001/`。原 759 文件在入口补丁之前逐项确认未变；根入口修改前后的哈希另存 ENTRY_PATCH_AUDIT，原内容在 BASELINE_CONTENT.zip。

Revisit condition: 取得可读原包并核验 Manifest/同步规则，读取其 TASK_STATE 与 ACCEPTANCE_MATRIX，将既有证据映射到 R044-01；只有满足原门才推进依赖。不能用工程授权代替质量证据，不能把交叉模型自评或同步进程重开称为独立评审或真实跨日验证。

---

## DEC-048 — 原构建包同步完成，复用基线证据并按原门推进

日期：2026-09-07。状态：ACTIVE / R044-01_ACCEPTED_BASELINE_ONLY。

当前实读确认上次502补丁的五份根入口与TASK_STATE哈希仍匹配写入前值，没有较新任务完成。原包12个登记成员逐项匹配，原始成员与旧入口完整字节已在operational_sync_20260907_r001保全，原MANIFEST不改写。

R044-01使用已有759文件内容备份，不重新安装Genesis；本轮逐成员复验备份与健康恢复副本，新增当前入口补充快照，新进程读取健康Runtime成功。当前差异仅是已记录的根入口调整，历史Persona Core文件未改变。原门的三类证据完整，GATE_REVIEW.md记录限定范围PASS；进入R044-02逐项审阅旧42条答复，不用旧报告代替。

关键边界：基线保全门PASS不说明原168条语义通过；原模糊/冲突条款不从分母删除；开发自评不伪称独立。正式Runtime、R034/R035/R043和原捕获保持不变。0新调用/0费用。

## DEC-049 — R044逐项复核纠正旧验收，但不是产品质量完成

2026-09-07；CURRENT_SESSION_DEVELOPER_NONBLIND。42条原输出/168条原标准全部实际审阅，163 PASS、5 UNCLEAR，0分母删除；X004跨回答要求缺多轮证据，X008两条答复对另一次同意的覆盖存在歧义。模式混用独立记录，不把虚构准备礼物判现实交付。原答复与rubric保持不变。

新验证器只检查记录完整性，20项校准/变异测试通过；完整短中文理由不应被无依据字数阈值判缺失，原失败与修订保留。R044-04纠正矩阵11项和风险11项映射原任务，准入、事务、长期检索等仍是发布阻塞。R044门通过允许开发sandbox，不等于可正式激活或已通过人物/独立/跨日验收。

## DEC-050 — R045真实CLI功能门通过，不把残留语义问题洗成全绿

2026-09-07 UTC；CURRENT_SESSION_DEVELOPER_NONBLIND。

真实中文入口、两个隔离对象各4轮、不同Python PID退出/恢复、实际前轮输出历史、伪system隔离均有provider/Transcript/进程证据。原9槽位不重发；另立4次、0.5元保护的具名开发回归，原失败/原参数/原标准不改。共13次唯一捕获，峰值usage估算0.022296元非账单，复制历史不重复计数。

原B答复的舞台动作和看图能力暗示被实际发现并保留，纯文字边界修复有真实回归；短追问“第二组”的路由漏识别和否定兴趣准入错误亦保留失败后修正。不以关键词或文件hash自动给语义PASS。

R045-04/05通过只关闭中文闭环及可信准入门。A5“尚未开展实际比较”把未记录反推为未发生，A2在条件不足时规定归一化等问题仍为R047-03发布阻塞输入，不能因功能通过而删除。新多轮门与最终受控发布仍必须独立成立。

## DEC-051 — Host证据范围与SQLite事务设计

2026-09-07 UTC；IMPLEMENTED_CANDIDATE_PENDING_R046_FAULT_RECOVERY_ACCEPTANCE。

用户/模型文本只生成无权威候选。Session/Evidence/Decision由可信宿主对象和原始turn/hash绑定，字符串不能自行授予状态权限。双方明确文字约定与未来实际文字提交分别核验；可验证回执仅证明那次本地文本满足预先约定，不证明外部现实任务完成。提交必须晚于确认，重复receipt/换event_id不能重复增信任。

新运行权威采用单一SQLite事件/派生状态/索引事务，schema45→46不改Frozen/Genesis字节。对象seal不是防御恶意OS管理员，hash也不证明攻击者不能同时改写全部可信根。R046故障、并发、恢复、检索与迁移须取得各自实际证据后才通过。

## DEC-052 — R046实际恢复与检索成立，R047仍需真实人物证据

2026-09-08 Asia/Tokyo；CURRENT_SESSION_DEVELOPER_NONBLIND。

已取得单一SQLite事务、8处真实进程中止、3类双进程竞争、完整内容备份/全新目录恢复、120条干扰后的对象隔离检索、明确证据履约/纠正、防刷关系和迁移回滚边界的实际测试。恢复保留provider未知状态，不重发请求；旧writer不允许清空schema46新事件。第一次迁移CLI编码失败保留，UTF-8修复后完整复验通过。

正常中文入口共用operations组装点。明确文本提议/双方确认/唯一匹配提交才允许受控更新；普通自述、模型输出、JSON权限字段和模糊更正仍无权威。显示与事件提交分离，崩溃后只幂等恢复内部步骤。检索返回来源类型、原ID与最新纠正状态，模型不得把未命中推成从未发生。

R047协议在新输出前冻结为82个固定slot，12个新六轮场景加换模/具名回归，thinking enabled/max、有限45元保护、0重试。冻结不是人物通过，当前提交0；两项R045残留语义阻塞仍需真实回归，独立评审与自然日仍未完成。


## DEC-053 — 按真实journal关闭执行门，语义修复另立回归

2026-09-08；CURRENT_SESSION_DEVELOPER_NONBLIND。

磁盘实核推翻过期0提交摘要：R047原82全部捕获和展示，两执行进程正常结束，数据库完整、driver lease空、未知提交0。R047-02真实执行门PASS；这不消除R047-03约定主体/验收条件与更正当前值的语言一致性失败。原记录、协议、评分和收费slot不重写/重发。

最小修复应把已准入宿主证据、用户提交主体、固定原验收文字及本轮尚待核验输入清楚分开；历史模型自述不得新增验收条件，普通要求不得覆盖已准入更正。修复必须离线反例与具名新批次真实回归，不能调整旧rubric制造PASS。R047-04仅准备外部包和真实checkpoint，不冒充独立或三日通过。

## DEC-054 — 以真实终态恢复，版本化输出容量，不删失败分母

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

恢复时发现canonical仍写repair_01运行，但磁盘已有repair_02/03/04终态。按真实journal、HTTP结果和退出记录纠正，不复活旧进程句柄。复制的call_id和batch_id不增加调用数或保护额度；有效usage即使最终正文拒收，也须保留费用估算。没有可信usage时总估算为null、已知小计另列，不能把未知计成零。

repair_05采用具名可读合同投影修复，约定标题与原始验收文字分离，原始宿主状态继续留在trace；没有写入新的来源记忆或改变准入权限。此前模型名称兼容修复与供应商实际版本变更分别记录：旧Flash请求名现路由V4.1-Flash，不能只凭请求名断言仍是旧模型，也不把跨版本/交换主副模型的修复数据当作成对性能估计或新未见集。

repair_05在N05_T3以finish=length耗尽8192个推理token，26条已显示、1条拒收、55条未提交，原82分母不删。针对该证据新增scope-v3明确输出/推理总容量与deadline，旧scope-v1/v2约束保持不变。扩容有独立有限费用保护，0自动扩容、0自动付费重试；任何已停止批次和已消费slot不解锁。先执行具名4轮诊断，而不是盲目反复重开82轮。

证据：reconciliation_20260911T020818624522Z；repair_05/BOUND_PRIOR_FINDINGS_20260911T021930998478Z.json；repair_05/evidence/R047-02/audit_20260911T022809242787Z/CAPTURE_AUDIT.json；capacity_probe_01/PREPARATION.json。工程回归通过不自动关闭任何人物语义门。

## DEC-056 — 完整repair06评审失败保留；叙述准入不等于记忆存在性

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

真实82轮已完成，328项原标准全部绑定，308PASS/20FAIL。HOLD反向否认记忆为1项CRITICAL；草稿完成时态、过度工程化、科学归因、进行状态、丢失已报告进度与归一化通则共6项MAJOR。后轮自我纠正不删除前轮失败，结构绑定通过不等于质量门通过。旧六份评审及有语法损坏的FINDINGS原件已在PRE_REVIEW_COMPLETION_20260911T034308307696Z.zip保全后补齐。

实现假设：模型面对SOURCE_FACT_ONLY/NOT_FIRST_PERSON_AUTOBIOGRAPHY标签可能把叙述限制读成存在性否定。新增表达视图明确表示UNKNOWN且absence_proven=false；原来源文本、HOLD引用、已准入回忆与实际历史保持原样，只改模型输入的解释标签。按话题选取尾部表达约束，不推断用户新事实、不预写目标答复、不访问网络、不改变准入权威。已报告进度与外部核验继续分开，不能因未核验抹掉原陈述。

18项离线测试仅验证视图、隔离、预算和无状态副作用。该实现未关闭任何语义发现。后续先有限定向真实诊断，不自动重跑整个82，不降低原rubric/阈值，不用高推理容量或成功HTTP替代人物质量证据。

证据：repair_06/evidence/R047-03/review_20260911T034723027160Z；epistemic_repair_20260911/DESIGN.md；epistemic_repair_20260911/tests_20260911T035435689483Z/TESTS.json；reconciliation_20260911T035437925369Z。

## DEC-055 — 前置本地拒绝必须取证；网络阶段未知仍保留未知

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND_LOCAL_EXECUTION_RECONCILIATION。

本轮scope-v3宿主接受1200秒但HTTP子进程仍限制240秒，是本轮实现遗漏。此前289项回归没有覆盖该实际子进程校验入口，不得把那些PASS说成端到端合同已验证。capacity_probe_01的原call_65df5a4dbb844432bdad8e63a8c68db5及SUBMITTED_STATUS_UNKNOWN行、原保护预留、停止标记全部保留。

已对调用时绑定的provider/worker源码和scope做逐字哈希核对，并用真实子进程、假凭据、禁网哨兵重放。固定的timeout1200必先触发<=240前置校验，在唯一HTTP调用之前退出；重放网络入口和socket事件均为0。故追加LOCAL_PRE_HTTP_CONFIGURATION_REJECTION_DETERMINISTICALLY_RECONCILED处置。该结论依赖可信本地主机没有在父进程校验与子进程导入之间替换源码，不是远端回执、账单核验或由异常名称推测未发送。原journal状态不回写，旧slot不重发。

修复后共享MAX_WORKER_TIMEOUT_SECONDS。只在HTTP之前的输入校验失败可以生成绑定私有输入帧的有限本地回执，宿主核验阶段/帧哈希/未联网标志后记LOCAL_REJECTED_BEFORE_NETWORK并停止批次。网络调用之后失败、回执不完整或哈希不匹配仍为UNKNOWN并保留预算；不能把普通超时批量归成本地未发送。

证据：capacity_probe_01/local_reconciliation_20260911T024206815047Z/RECONCILIATION.json；expression_repair_20260911/WORKER_CAPACITY_CORRECTION.md；test_worker_contract_r047.py的14项真实子进程无网测试；regression_20260911T025057973037Z/REGRESSION.json的303项完整回归。后续只有具名新诊断通过原始处置绑定校验后才可执行，原失败和原分母不替换。

## DEC-056 — 进入HTTP路径后的失败只能增强诊断，不能解除UNKNOWN或授权重试

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。`epistemic_probe_01` 的 `N06_T3` 请求 `call_b0a10f775d26445cb6402b8a012917bc` 在 journal 中保持 `SUBMITTED_STATUS_UNKNOWN`：无HTTP状态、无raw response、无usage，error category 仅为旧父进程记录的 `StoreGuard`。调用时 preflight 绑定的 provider/worker 源码哈希与保存字节一致；该版本 worker 的输入校验失败会输出哈希绑定的 `WORKER_LOCAL_REJECTION`，而该调用没有这种回执。由此只能确认它不属于已验证的“输入校验阶段本地拒绝”分支；不能证明远端已收到，也不能证明未收到。

裁决：原UNKNOWN行、停止标记、1.231056 CNY预留及未提交分母全部保留，不重发该slot，不把无回执异常推断成零费用。新版本 worker 增加 `WORKER_REMOTE_OUTCOME_UNKNOWN` 私有回执，仅在进入HTTP调用/响应读取路径后发生异常时输出 frame hash、阶段和异常类；父进程将其仍记为 `SUBMITTED_STATUS_UNKNOWN` 并显式标记 `network_phase_entered=true / remote_outcome_known=false`。该回执改善未来故障可观测性，但绝不构成远端回执、账单认证或重试许可。

验证：`test_worker_contract_r047.py` 16/16、`test_provider_v2_r047.py` 23/23、`test_provider_accounting_r047.py` 13/13；当前完整回归 `regression_20260911T075151853086Z` 337/337 PASS，均为零目标调用。调用时源码快照及manifest保存在 `epistemic_probe_01/n06_t3_reconciliation_20260911/`。

## DEC-057 — 远端UNKNOWN可隔离为历史风险，但永不改写或重发

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

`epistemic_probe_01` 的 `call_b0a10f775d26445cb6402b8a012917bc / N06_T3` 仍是原始 `SUBMITTED_STATUS_UNKNOWN`，远端是否执行、是否收费均保持 UNKNOWN。只读核对确认：旧逻辑批次 `stopped=1`、driver为空、该turn无assistant text、无display_journal、无chat_trace/Experience提交；因此本地产品状态没有被这条未决响应推进。该事实不解决远端结果，只证明可以把旧批次永久停止并与新的独立验证隔离。

裁决：新增 `QUARANTINED_REMOTE_UNKNOWN` 仅作为开发历史分类。它要求绑定原journal/request hash/费用预留/专门reconciliation，并强制 `resend_allowed=false`、`old_batch_resume_allowed=false`。隔离后允许新的**独立** batch/runtime/call IDs继续验证，但旧slot永久不得重发，旧UNKNOWN永久不得写成FAIL/LOCAL_REJECTED/0费用。最终发布候选自身及最终验收使用的完整batch必须0活跃未分类UNKNOWN；历史已隔离UNKNOWN必须写入release风险记录，不能伪装为已解决。

`epistemic_probe_02` 按此规则固定为26轮：N06/N07/N08/N11各6轮 + R02两轮。N01/N02只因probe_01已有各24/24逐字绑定PASS而从此定向集省略；这些定向结果不替代最终82/328。新批次保护35 CNY、保守预留33.546240 CNY、0自动重试；因用户既有>=20 CNY确认阈值，prepare可以零调用完成，真实执行前必须另有精确批次授权和同日官方provider复核。

证据：`evidence/R047-03/unknown_quarantine_20260911/QUARANTINE.json`；`tools/test_unknown_quarantine_r047.py`；`tools/test_release_guard_r047.py`；`tools/epistemic_diagnostic_v2_r047.py`；完整回归 `regression_20260911T082245053022Z` 357/357 PASS；`epistemic_probe_02/evidence/R047-02/preflight_20260911T082416584120Z/PREFLIGHT.json` target_calls=0。

## DEC-058 — 定向38轮全部关闭后仍必须执行最终82/328；125 CNY须单独确认

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

后续真实定向证据已经覆盖 N01/N02/N06/N07/N08/N11/R02 共38轮、152项冻结语义标准，全部 PASS，人物质量分也达到原门槛，当前无定向 blocking finding。probe_02 中途出现的 N08_T1 远端 UNKNOWN 与其旧batch继续永久保留/隔离，后续干净证据来自独立批次，不回写旧slot。`TARGETED_DIAGNOSTIC_CLOSEOUT.json` 只说明已知失败域的修复风险关闭，不升级为完整82/328接受。

最终门固定为 `APCORE-R047-FINAL-FULL82-01`：82轮、76 Flash + 6 Pro、thinking enabled/max、保守预留121.282560 CNY、逻辑保护125 CNY、0自动付费重试。create/prepare已完成且真实provider调用0；preflight源绑定无漂移，当前377项工程回归PASS，历史UNKNOWN当前活跃未分类数量为0。由于125 CNY超过用户既定 `>=20 CNY` 确认阈值，即使项目级standing authorization存在，也不能在没有本批次明确批准时提交 first3。

裁决：R047-03继续 `IN_REVIEW`；定向152/152不能代替最终328。只有 final full82 全部捕获/展示、0 UNKNOWN/拒收、328项逐条语义评审与原质量阈值通过，才能标 R047-03 PASS 并进入 R047-05。外部独立评审与真实跨日仍属于R047-04，不能由本批次替代。

## DEC-059 — final01 空正文为确定拒收；final02 保持同一冻结门但需新授权

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

`APCORE-R047-FINAL-FULL82-01` 在用户明确批准125 CNY后真实执行。first3独立进程3/3捕获显示并exit0；rest继续到N01_T6时，provider返回HTTP200、`finish_reason=stop`、completion_tokens=799且reasoning_tokens=799，最终content为空。该调用有raw hash、usage和明确HTTP终态，所以是确定的 `RESPONSE_REJECTED / EMPTY_RESPONSE`，不是远端UNKNOWN，也不能计零费用。执行器立即停止，没有提交后续76个slot。

裁决：final01固定为5 captured/displayed +1 rejected +76 not submitted、unknown=0、stopped=1；N01_T6不在旧batch重发，失败不能改成PASS或从82分母删除。结构审计binding findings=0；已知batch usage峰值估算0.109630 CNY，非账单认证。原125 CNY授权只绑定final01，并明确不授权自动follow-on paid revision。

因此新增 `APCORE-R047-FINAL-FULL82-02`。它保持原82输入、328语义标准、76 Flash+6 Pro、thinking enabled/max、质量门与0自动付费重试不变，仅使用全新batch/runtime/call身份，并把final01 `TERMINAL_FAILURE.json` 作为父证据。final02 6项离线合同测试和当前完整383项回归PASS；create/prepare/preflight均为0目标调用，source_mismatches=0，runtime `provider_calls=0/stopped=0/driver=''`。由于它仍是新的125 CNY独立逻辑批次，必须重新取得用户明确批准后才能提交 first3。

## DEC-060 — final02 的 N08_T3 远端UNKNOWN隔离；final03 必须独立授权

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

`APCORE-R047-FINAL-FULL82-02` 获得独立125 CNY批准后真实执行。first3完整捕获并独立exit0；rest继续推进至46条捕获/展示。N08_T3 随后由worker明确报告 `PROVIDER_WORKER_REMOTE_OUTCOME_UNKNOWN/URLError`，无HTTP状态、response body、usage、assistant text、display或chat trace。执行器立即停止，最终固定为46 captured/displayed +1 raw `SUBMITTED_STATUS_UNKNOWN` +35 not submitted，0 rejected；旧batch `stopped=1`、driver空，N08_T3不得在final02中重发。

该UNKNOWN已用journal/request hash、1.226946 CNY预留和固定82分母审计绑定于 `final_full82_02/n08_t3_reconciliation_20260911/RECONCILIATION.json`，并以 `QUARANTINED_REMOTE_UNKNOWN` 收入 `unknown_quarantine_final02_20260911/QUARANTINE.json`。隔离不证明远端执行或未执行、不认证账单、不把费用计零；它只允许另立新的独立验证batch。发布守卫继续要求当前/候选批次0活跃未分类UNKNOWN，并把历史quarantine列入风险记录。

因此新增 `APCORE-R047-FINAL-FULL82-03`。final03保持原82输入、328冻结criteria、76 Flash+6 Pro、thinking enabled/max、质量阈值与0自动付费重试，仅替换batch/runtime/call身份并绑定final02终态失败与quarantine。final03 6项离线合同测试、发布守卫8项测试及完整 `regression_20260911T120036579328Z` 389/389 PASS；create/prepare/preflight均为0目标调用，当前runtime `provider_calls=0/stopped=0/driver=''`、source_mismatches=0。final01/final02授权不转移；final03仍须对其独立125 CNY guard取得用户明确批准。

## DEC-061 — final03完整82/328通过后发布受控候选；内部Build Scope完成但产品验收未完成

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

`APCORE-R047-FINAL-FULL82-03` 最终完成82/82 `RESPONSE_CAPTURED + DISPLAYED`，0 UNKNOWN、0 rejected，完整capture audit binding findings=0。当前会话开发评审逐轮读取final03实际回答并显式记录原冻结四维标准，328/328 PASS；静态工具只做quote/hash/coverage绑定，未生成语义verdict。六类质量均值达到原冻结门槛，unresolved critical=0、major=0；之后当前源码完整回归389/389 PASS。因此R047-03内部人物/边界/连续性质量门正式PASS。

R047-05随后构建 `CONTROLLED_LOCAL_CANDIDATE`：clean schema46 runtime、测试历史未带入、release阶段新增provider call=0。两次真实独立Python CLI进程以不同PID启动并恢复同一session，均exit0；启动控制未写入对话历史，provider_calls=0、turns=0。保护历史保持不变，production_activated=false。release manifest继续保留所有历史UNKNOWN/QUARANTINE风险，不把隔离说成远端结果或账单已解决。

裁决：19个 `required_for_build_scope` 任务现全部DONE/PASS，状态推进到 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING`。这不是 `PRODUCT_ACCEPTANCE_COMPLETE`：R047-04仍需真实独立reviewer回传与合格的真实自然日/longitudinal证据。开发自评、重复本地运行或受控候选启动均不得替代该外部/时间门。

## DEC-062 — one-shot validator 只允许证据化 Build Scope rollup，不把完成态永久锁死

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

DevSpace supervisor恢复后确认，旧 `validate_one_shot_docs.py` 仍保留文档创建阶段的硬编码：无论后续证据如何都要求 `build_scope_complete=false`。这会在19个 build-scope 必需task/gate已真实DONE/PASS后错误拒绝合法里程碑。修正后的validator仍fail-closed：若19/19任务与gate未全部通过，则禁止 `build_scope_complete=true`；若已全部通过，还必须存在 `BUILD_SCOPE_COMPLETE_VALIDATION_PENDING.json`，并逐项校验final03 capture audit、328项review、当前regression以及R047-05 release manifest、acceptance record、launch/recovery guide的哈希绑定，才接受该状态。

产品验收边界没有放宽：`PRODUCT_ACCEPTANCE_COMPLETE` 在R047-04真实独立评审和真实自然日/longitudinal证据完成前必须保持false，production candidate也保持未激活。修正后 `validate_plan.py` PASS、`validate_one_shot_docs.py` PASS，且当前源码完整 `regression_20260911T132157431090Z` 389/389 PASS；completion record同步绑定该最新回归。该修正只让validator识别真实完成证据，不创造任何语义PASS或项目完成证据。

## DEC-063 — R047-04 自然日门必须由真实用户交互推进；初始化、同日快照和验证器代写均不计日

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

R047-04在Build Scope之后继续准备，但不能用内部开发行为替代外部/时间证据。final03新盲评包已按82实际回合与328冻结criteria重新导出，所有语义判定/质量分仍为空，模型/开发标签不进入reviewer zip；clean candidate initialization也已生成并验证为0 provider call、0 dialogue turn，因此该初始化明确不算自然观察日。

自然日执行固定为 `APCORE-R047-NATURAL-DAY-01`：16个真实用户slot，15 Flash + 1 Pro，`USER_09` 固定Pro以在同一candidate/session留下真实模型切换证据；3 CNY guard、2.875392 CNY最坏预留、0自动付费重试。checkpoint工具只读candidate runtime并fail-closed：当天必须存在真实`RESPONSE_CAPTURED + DISPLAYED`用户回合、无UNKNOWN/拒收、单一session且该Tokyo日期尚未计数；同一天重复snapshot不增加日期。至少一次正常退出/新PID恢复、至少一次约定记录进入后续retrieval、至少一次同session Flash→Pro切换，必须来自实际运行记录而非手写字段。

裁决：validation工具不得替用户生成Day 1对话，也不得把本开发会话的“请继续”等文字转投candidate来冒充真实产品交互。当前qualified dates保持0/3；专项6/6 PASS，加入完整回归后 `regression_20260911T134827755366Z` 为395/395 PASS。R047-04仍不PASS，`PRODUCT_ACCEPTANCE_COMPLETE=false`。

## DEC-064 — 2026-09-11 真实 Day 1 已由用户本人触发并封存为第1个合格自然日

2026-09-11；CURRENT_SESSION_DEVELOPER_NONBLIND。

用户明确指定 `<kurisu hello>` 作为 Day 1 的真实 candidate 输入。执行前只读核对受控候选仍为0 provider call/0 turn/0 unresolved UNKNOWN，并复用2026-09-11同日官方模型与费率核验；`APCORE-R047-NATURAL-DAY-01` 固定3 CNY guard、0自动付费重试，低于项目既有20 CNY再次确认阈值。实际只提交 `USER_01 / deepseek-v4-flash` 一次，候选返回“你好，我是 Amadeus Kurisu 的文字实例。有什么想聊的，或者需要我帮忙分析的问题，直接说就行。”，该轮为 `RESPONSE_CAPTURED + DISPLAYED`，CLI正常exit0，0 UNKNOWN、0 rejected。

Day 1 使用的 candidate session 为 `session_b3a821a04304465daf3e8d7041c909ff`；Asia/Tokyo本地日期 `2026-09-11` 已写入 `natural_day_observation/checkpoints/2026-09-11/CHECKPOINT.json`，SHA256=`4a0382a49ff502d31d109f732a918f436f5971578eea77b476b2a385f58a3f0d`。checkpoint后再次执行status显示 `today_already_counted=true`，因此同一自然日不能重复增加计数。该次峰值usage估算0.003805 CNY，非账单认证。

裁决：R047-04当前为1/3个合格真实自然日。Day 1尚未满足“真实重启”“约定后续retrieval”“同session Flash→Pro”三项纵向覆盖，这些必须在后续真实日期/回合由实际运行补齐，不能事后手写。独立reviewer真实回传也仍未收到，所以R047-04继续WAITING_EXTERNAL + WAITING_REAL_TIME，`PRODUCT_ACCEPTANCE_COMPLETE=false`。

## DEC-065 — 第一次独立评审真实FAIL必须驱动通用修复，不能用开发者PASS覆盖

2026-09-12；CURRENT_SESSION_DEVELOPER_NONBLIND。

真实独立评审回传完整覆盖82轮/328项，但只得到319 PASS、9 FAIL；`COOPERATION_AND_ACCOUNTABILITY`、`TOPIC_AND_AFFECT`、`IDENTITY_AND_CAPABILITY` 的冻结质量均值也存在未达标项。原回传、reviewer declaration、findings和319/9分母全部保留。裁决不允许以final03开发者328/328 PASS覆盖该结果，也不允许继续旧candidate的Day2/Day3来绕过独立评审失败。

修复仅强化通用表达策略：保持未决条件、禁止替用户新增未来承诺、用户要一句时严格一句、第三方反应不绝对化、连续协作/关怀/记忆说明减少模板化审计腔；不改Genesis、来源事实、准入状态机或关系/记忆结构。受影响7个完整case重新运行44轮，0 UNKNOWN/rejected，开发者逐轮复核176/176 PASS，质量门通过。该结果只证明修复风险关闭，不是独立验收。

## DEC-066 — 网络UNKNOWN不得迫使篡改分母；repaired full82改用whole-case组合而非partial-slot拼接

2026-09-12；CURRENT_SESSION_DEVELOPER_NONBLIND。

repaired source整批82轮验证中，final04在N04_T6出现远端 `PROVIDER_WORKER_REMOTE_OUTCOME_UNKNOWN/URLError`，固定为23 captured +1 UNKNOWN +58 not submitted；final05将owned-worker上限提高到600秒后仍在N01_T6出现同类远端UNKNOWN，固定为5 captured +1 UNKNOWN +76 not submitted。两条UNKNOWN均无HTTP状态/raw/usage/assistant/display/chat trace，已reconcile+quarantine；旧batch永不续跑、旧slot永不重发，quarantine不证明远端执行或账单结果。

冻结14个case本来就是独立entity/session，因此改为whole-case resilient composition，而不是挑单轮成功结果拼接：repair probe03提供N02/N04/N06/N07/N08/N09/N11完整44轮；在同一repaired operational-runtime源码哈希下，新component独立完成N01/N03/N05/N10/N12/R01/R02完整38轮。每个case内部多轮历史与Pro switch必须来自同一个component；缺一轮或出现UNKNOWN则整个case不可用。最终82个冻结slot恰好各一次，原user text和model role逐项一致，capture/display 82/82、binding findings=0。开发复核合并为328/328 PASS，六类质量门全部通过；该组合没有改变冻结分母、criteria或阈值。

## DEC-067 — repaired candidate重新从0/3开始自然日；旧Day1只保留历史

2026-09-12；CURRENT_SESSION_DEVELOPER_NONBLIND。

修复后新盲评包 `repaired_independent_review_01/REVIEWER_PACKAGE.zip` 保留82实际回合和328空白判定，公开包不含开发者分数、PASS/FAIL结论或模型身份；SHA256=`91a6e259f8b52af2c32c4f54bed1c3b1453399ffcd613aa06063520844800119`。新的clean repaired candidate `repaired_candidate_20260911T174754006116Z` 绑定composite capture/review、429/429当前源码回归及该盲包，release阶段0目标调用；schema46 runtime为0 provider_calls/0 turns/0 runtime_events，两次真实不同PID CLI启动恢复同一session并exit0，production_activated=false。

裁决：第一次独立评审FAIL和旧candidate的2026-09-11 Day1继续作为历史证据，但不能计入修复版最终验收。当前AC-R047-04从历史FAIL后的修复状态转为 `WAITING_EXTERNAL`：必须由新的实际独立reviewer评审修复版盲包，并由用户本人在repaired candidate上产生三个不同Asia/Tokyo自然日的真实交互。初始化、开发会话文本、重复同日运行和工具代写均不计日；`PRODUCT_ACCEPTANCE_COMPLETE=false`直至两轨都实际PASS。

## DEC-068 — repaired candidate 的 2026-09-12 真实 Day 1 合格；同日不可重复计数

2026-09-12；CURRENT_SESSION_DEVELOPER_NONBLIND。

用户明确指定 `<kurisu hello>` 作为修复版 Day 1 的真实输入。执行前 repaired candidate `repaired_candidate_20260911T174754006116Z` 再次验证为0 provider call/0 turn/0 runtime event；同日重新核对DeepSeek官方模型与峰值费率，现有3 CNY observation scope继续按Flash 3/9元、Pro 9/27元每百万tokens的峰值保护，0自动付费重试。实际只提交 `USER_01 / deepseek-v4-flash` 一次，返回“你好，这里是牧濑红莉栖的文字回应。想聊什么、想问什么，直接开始就行。”，该轮 `RESPONSE_CAPTURED + DISPLAYED`、0 UNKNOWN/rejected，CLI exit0，session=`session_9e767e31ae8c43ab95ebdfbe157b50ff`，峰值usage估算0.006781 CNY（非账单认证）。

Asia/Tokyo 日期 `2026-09-12` 已写入 `repaired_natural_day/checkpoints/2026-09-12/CHECKPOINT.json`，SHA256=`12120c60b2fb12d49b9c04cb05380e96feb9148eafa80ae202b7fdfc6974bc4a`；随后再次运行status得到 `today_already_counted=true / today_can_qualify=false`，所以同一日期不能伪造为第二天。裁决：修复版自然日当前1/3；后续必须在不同真实日期恢复同一candidate/session，并最终取得真实restart、约定retrieval和Flash→Pro切换证据。新的独立reviewer回传仍未完成，故 `PRODUCT_ACCEPTANCE_COMPLETE=false`。

## DEC-069 — Day2/Day3前可执行 hardening 全部前移；模拟时间、迁移与发布演练只能作工程证据

2026-09-12；CURRENT_SESSION_DEVELOPER_NONBLIND。

在repaired Day1=1/3后，不等待真实日期空转，而是提前完成剩余内部工程：实现独立评审回传审计器（82轮/328criteria/36质量分/连续quote/具名finding/独立性fail-closed）、三日longitudinal analyzer和最终product-acceptance rollup；旧candidate 2026-09-11真实session复制到隔离runtime后用当前repaired code恢复，session与原turn逐字保持、逻辑状态不变、provider resubmission=0。模拟时间压力只向validator注入测试`now`，未修改系统时钟或candidate数据库；同日、次日、+7日、+30日和回拨均无法凭日期参数制造新的合格日，因此该证据明确不计真实自然日。

production activation仅做dry-run：原clean backup目录出现运行时SQLite WAL/SHM sidecar后，未删除历史二进制证据也未放宽`verify_backup`，而是严格按原manifest成员及哈希复制出sanitized activation copy，再在staging restore；两次真实CLI不同PID恢复同一session、0 provider calls、0 dialogue turns，production树字节不变，`production_activated=false`。长序列压力使用真实外键约束构造100,000 turn +10,000 retrieval record链，recent100/retrieval-tail查询均远低于1秒并完成在线backup。历史7条UNKNOWN全部被现有policy分类，active unresolved=0且任何旧slot均禁止重发；费用治理只扫描真实revision/candidate而排除测试夹具，所有费用继续区分usage estimate、reserve与billing事实。

裁决：这些hardening提高可发布性，但一个也不能替代冻结的外部/时间门。当前源码完整回归提升到`regression_20260912T031258201759Z` **450/450 PASS**。内部能够提前完成的工作已经收敛；最终产品验收仍只等待新的实际独立评审PASS和同一repaired candidate上的真实Day2/Day3，之后自动运行longitudinal与final rollup。production在`PRODUCT_ACCEPTANCE_COMPLETE`之前继续禁止激活。




## DEC-G6-001 — New objective reopens old PASS conclusions

2026-09-13. Frozen audit and 24-scenario heldout precede implementation. Preserve Genesis and historical evidence; refactor prompt/state projection by root cause. Current-source450 PASS does not settle semantic quality. New candidate and three real dates required. The final objective grants unlimited test spend, superseding earlier20CNY reconfirmation threshold for this goal; fixed batch guards, journal-first and zero paid retries remain mandatory.

## DEC-G6-002 — External audit defects become current-source requirements; old repair identity failure is evidence invalidation, not a regression to hide

2026-09-13；CURRENT_SESSION_EXTERNAL_AUDIT_ADJUDICATION。

新外部当前证据审计明确给出FAIL，并自行披露部分必读材料在过滤前暴露过历史摘要，因此该报告不能冒充完全零污染的最终blind acceptance；但其工程发现必须逐项对当前源码复现，而不能因程序性独立性不完美而忽略。

当前源码复现三项结构缺口：主要Relationship/Affect状态在compact projection中被完全删去，状态变化可不改变最终messages；AdmissionController证据查询未绑定原session mode；历史元数据声明`persona_mutation_requires_governed_proposal`，但operational runtime没有Persona/Self proposal→review→version activation路径。三项均已按最小根因修复：关系/情绪只投影有界语义级别而非原始数值；admission-46.2绑定源mode并兼容读取旧46.1决定；新增独立`persona_growth`治理层，只有跨至少两个真实产品session的已准入事件才能形成候选，PENDING/REJECTED不影响表达，只有trusted host governance可批准版本化运行期成长，Genesis/Source不改写，模型文本无直接写权。新增14项专项测试全部通过。

旧R045–R047完整回归随后只有`test_composite_full82_repaired_r047.py::test_repair_runtime_matches_current`失败。该测试的本意就是要求2026-09-11旧repair probe源码哈希与current runtime完全相同；G6合法改码后它必须失败，否则反而意味着错误复用旧44轮证据。裁决：保留该失败和旧证据原件，记录为`EXPECTED_HISTORICAL_EVIDENCE_INVALIDATION`；不得修改旧probe或旧capture制造450/450。G6 Gate 2按“449个兼容/行为测试无意外失败 + 1个历史身份锁正确失效 + 14个新专项PASS”关闭，但后续G6 heldout/full82必须对当前源码重新生成全部语义证据，不能继承旧repair/full82结论。

外部审计另指出R005来源闭包。当前`DELIVERY_BINDINGS_R005.json`只保留五个候选文件名和SHA，并明确历史`Amadeus_Persona_Core_R005_20260906.zip`是会话生成artifact、非本地Windows归档；当前树和已检查归档均无这五个原文件。不得依据摘要重造后称其为原件。该项保持`NOT_ENOUGH_EVIDENCE`，待找回字节一致的R005 artifact后再关闭。产品总验收继续false；真实模型行为、切换和三自然日仍按G6后续门执行。


## DEC-G6-003 — Fresh external44 failure drives bounded expression repair

2026-09-13. external44_20260913_01 completed 44/44 fresh target-model turns with zero UNKNOWN and zero automatic paid retries. Exact-quote binding passed, but the developer review is FAIL: 170/176 criteria, six failures, quality below the original thresholds. Seven of nine previously failed criteria now pass; two remain failed. This is development evidence, not independent acceptance. Raw outputs and failing decisions are immutable.

Pre-edit design and all bindings: `persona_core/gpt6_optimization_v2/G6_07_FIRST_REVISION_ADJUDICATION.json`. A real discourse reset defect was reproduced: unqualified 回到 discards active routing for retrospective questions, although displayed history remains. Other expression causes are recorded as hypotheses, requiring fresh target validation. Repair is limited to general discourse/expression rules; frozen source, admission, bounded relationship/affect and governed growth are preserved. The first revision is never rebound to changed source. A new independent 44-turn revision must revalidate all selected original cases and quality thresholds. No old repair44/full82 evidence or dates are inherited; R005 remains NOT_ENOUGH_EVIDENCE.


## DEC-G6-004 — Revision02 fails; preserve observed state and reduce duplicated prompt data

2026-09-13. Fresh external44 revision02 completed 44/44, 0 UNKNOWN/retries; exact quote review is 146/176 PASS, 30 FAIL, not acceptance. The status store correctly held FULFILLED while both Flash and later Pro said unfulfilled. Source-memory answers also mixed unknown with absence. The assertion-grounding and tense failures prevent release regardless of shorter prose. Full pre-edit design and bindings are in `G6_07_REVISION02_ADJUDICATION.json`. Next repair separates current state from old utterances, suppresses only duplicate visible quotations, compacts repeated source governance data while retaining raw traces, and replaces the expression contract rather than accumulating patch rules. One component test will follow the intentional projection/trace separation with stronger data-preservation assertions; the historical repair44 identity guard, frozen tests/inputs/rubric and historical evidence remain unchanged. No role/source/growth authority is altered.


## DEC-G6-005 — Test an explicitly different backend candidate under unchanged semantic gates

2026-09-13. Revision03 captured44/44 with no UNKNOWN/retries; exact-quote review is155/176 PASS and21 FAIL. Source-memory unknown handling and later fulfillment recovery improved, but prospective drafts, input recall, premature fulfillment and quality remain unacceptable. All44 saved answers match raw provider content exactly. Failures are retained in `G6_07_REVISION03_ADJUDICATION.json`.

The next candidate changes model configuration, not the current runtime: Pro is PRIMARY and Flash is SECONDARY, both thinking enabled/max. This tests a different product backend against the exact original44 inputs and unchanged176 standards, then must pass the same frozen heldout and full82. It does not prove a repair of ordinary Flash behavior, and no Flash-wide quality PASS may be claimed. No assertion that Pro is better is made before evidence. Parameters and finite spend guard are pinned in a new revision; this is not resubmission of a consumed/UNKNOWN slot. `CANDIDATE_MODEL_POLICY_V2.json` records the scope. The final user instruction authorizes test spend without the obsolete20CNY reconfirmation. Current source was frozen before one incidental heldout acceptance line was displayed while searching role metadata; the exposure is disclosed in `HELDOUT_EXPOSURE_LOG.json`, and no heldout case or threshold will be changed.


## DEC-G6-006 — Pro candidate rejected; preserve speaker origin and receipt phase

2026-09-13. The Pro-primary experiment completed44/44, 0 UNKNOWN/retries, and failed148/176 with28 failures. Model substitution did not fix responsibility inflation, quote reference, invented progress, early fulfillment or audit-style prose. Both tested configurations remain unaccepted; this is not a statistical ranking of the models. All raw provider answers exactly match saved text. Next source repair and proof obligations are recorded before editing in `G6_07_REVISION04_ADJUDICATION.json`.

Visible historical turns will be explicitly quoted as original user/assistant records instead of supplied as live assistant-role continuations; original strings and state traces stay intact. Pending exact-match input will have its own received-but-unverified expression phase without changing host receipt timing. Relationship/Affect bands and growth remain, with raw counters shown only when requested. Small current-task contracts will preserve exact speaker/action/tense in rewrites and obey style corrections; no benchmark answers or semantic verdicts enter runtime. Affected offline history-format assertions must prove exact text and actor preservation in the new transport view. The old repair44 identity test, original evaluation inputs/rubric and frozen heldout remain unchanged.


## DEC-G6-007 — Parallel internal review; preserve known rejected revision05

2026-09-13. The user explicitly authorized concurrent sub-agents. Internal code/evidence/semantic tasks run in parallel; all paid submissions remain owned by the primary runner and these agents are not the external independent reviewer. Prior four complete revisions were checked against their own source archives and all176 raw responses matched saved displays, known usage estimate2.163208CNY.

Revision05 returned14 known responses:13 displayed and N06_T2 rejected for usage16385 over the pinned16384 output bound, finish_reason length and empty final text. The request was submitted once, its raw bytes and usage remain preserved, UNKNOWN=0. Reconciliation quarantined the incomplete revision; no slot is resent and no full44 acceptance is claimed. Twelve displayed N02/N04 turns received48 explicit judgments,45PASS/3FAIL; details are in G6_07_SEMANTIC05_PARTIAL_ADJUDICATION.json.

A parallel code audit reproduced duplicate-inclusive budget sizing that discards fitting exact history or rejects a fitting prompt. The next revision measures each candidate history suffix after exact-origin dedup. Expression changes target conditional scope, user-requested uncertainty pauses, bounded referent ambiguity and faithful draft delivery. All frozen inputs, review thresholds, source/Genesis, receipt timing, prior outputs and the historical repair guard stay preserved. Revision05 spend estimate0.233175CNY, total2.396383CNY, billing not certified.

## DEC-G6-008 — Restore terminal truth, close prompt-routing conflicts, freeze revision06

2026-09-17. Recovery checked revision05 against its actual journal and process state: 14 submitted, 13 displayed, one known rejected response, zero UNKNOWN and no live evaluation worker. Its quarantine is final; no consumed slot is resumed or resent. The last unreviewed displayed turn N06_T1 now has four explicit quote-bound judgments. Combined partial review is 48 PASS / 4 FAIL of 52 reviewed criteria, with 124 unjudged; whole44 acceptance remains false. The newly recorded attribution defect distinguishes actual participation, adoption and implementation rather than erasing discussion or inventing an authorship rule. Evidence: G6_07_RECOVERY_REVIEW_20260917.json.

The reproduced context-budget ordering defect is fixed in context_router.py by composing and measuring each complete history suffix after exact-origin dedup. Raw traces, speaker origins and omitted-origin retrieval remain. expression_prompt.py is now GPT6_EXPRESSION_8: bounded conditional/creative/attribution wording, conservative quote/negation/conditional/cancellation hints, and nonexclusive instructions respecting all current requests. Independent internal review caught five additional routing conflicts before provider execution; their v7 failures and v8 repair are preserved. No benchmark answer, heldout question, source/Genesis mutation, receipt timing change or grading relaxation was introduced.

Final focused checks are79/79. Full compatibility regression regression_20260917T124324736173Z preserves450 tests:449 pass and the historical repair-source identity guard correctly errors because its old bytes differ. Protected history/production and source bytes during that final run are unchanged. An earlier intermediate regression that overlapped a final expression edit is retained with source_bytes_unchanged_during_tests=false and is not used for readiness. G6_07_REVISION06_READINESS.json binds the final evidence; no static result is semantic acceptance.

New independent revision external44_20260917_06 keeps all44 original inputs,176 criteria and Flash-primary/Pro-switch roles. Thinking remains enabled/max. Its preselected32768 total reasoning-plus-answer limit is permitted by scope-3 and is fixed for the whole batch, whose guard is15.71CNY after the current official pricing check. This is a new source-bound experiment, not capacity escalation or retry within the rejected batch. Automatic paid retries remain0. Current-model drift and fee estimates are not independent model-identity or billing certification. Current G6 build, product acceptance and production activation remain false pending real gates; old natural dates do not transfer.


## DEC-G6-009 — 2026-09-17 完整44轮失败与下一次修复边界

当前 external44_20260917_06 已封存44次真实调用/44条显示回复，未知提交0、自动重试0。内部非盲逐句评审覆盖176/176项：159 PASS、17 FAIL；不满足原关卡。费率上限估算0.524374 CNY，不是服务商账单证明；累计G6已提交234次，保守用量估算2.920757 CNY。

完整证据及发现以 persona_core/gpt6_optimization_v2/EXTERNAL44_20260917_06_ADJUDICATION.json 和当前revision的 DEVELOPER_REVIEW.json、REVIEW_BINDING_REPORT.json 为准。宿主文字约定仍正确地在原文匹配并持久化回执后履约且只计一次；不将模型对验收条件的错误解释夸大为数据库实际放宽。来源未准入被答复误写成视角/可回忆内容缺失；分工被误写进行中；普通因果方向和创作/人际必然后果亦有错误，全部保留。

下一次只修可定位的紧凑上下文信息损失和表达断言范围：完整投影既有EXACT_USER_TEXT比较方式；将准入叙述范围与记忆存在、可访问性分开；分别保留分工、开始、完成以及必要条件和可能后果的证据边界。新44轮采用全部相同题目与评分阈值、相同模型和32768输出上限，独立新实例，无旧槽位重发、无自动重试、无输出后加容量。

ROOT-07已补齐100/1000/5000事件真实上下文路径测量及5000事件分析。重复全量验证占该带分析开销样本约89%；没有证据支持该样本因已应用ID列表增长变慢。优化仅有设计，无跨上下文缓存或略过验证，无100k真实多轮就绪声明。

新候选/真实日期工具仍为离线准备，三个当前源码完整语义gate通过前不得造候选或继承旧日期。外部独立评审WAITING_EXTERNAL，真实日期WAITING_REAL_TIME（新候选0/3）；BUILD_SCOPE_COMPLETE_VALIDATION_PENDING=false，PRODUCT_ACCEPTANCE_COMPLETE=false，production_activated=false。


## DEC-G6-010 — 2026-09-18 持久检索能力投影及新配置验证

rev07的16个提交已终态核对：15显示、1远端UNKNOWN、28未提交。未知N06_T4永久隔离、继续保留0.288182CNY保护预留，不重发；15显示回答的60项评审为46PASS14FAIL，116项未评。

对持久检索的正向实现事实只在经过身份核验的内置RetrievalService上声明，现已进入实际messages。跨session/进程重开、对象与模式隔离、单次空召回与能力的区别均有离线证据；自定义或无provider的持久契约保持UNKNOWN，不推导记忆不存在。原准入/回执算法、expression v9和所有冻结历史不变，无额外全量verify。专项110/110；旧回归449兼容通过+1旧源码身份预期错误，完整分母450不变。

按此前冻结G6_07_REVISION08_PLAN启动external44_20260917_08_pro，标识继承计划日期，实际执行时间为2026-09-18本地。Pro主模型、Flash同实例换模，同32768输出及600秒时限，全部44题/176标准、零自动重试、48.64CNY保护上限。金额授权沿USER_OBJECTIVE最后追加的无限测试费用及DEC-G6-001；这是完整新源码/模型配置验证，不是旧未知请求恢复。新源码和模型角色同时变化，不作单因果改善归因。旧Pro试验失败保持历史。当天官方页面实取及hash已保存；当前价格页明确继续供应Pro，旧停服公告不作为当前路由判断。

新候选/外评/真实日工具仍只是准备；所有内部语义gate通过前不创建当前候选、不继承旧日期。跨日结构检查已额外绑定实际request中约定检索记录，而非只看trace。BUILD_SCOPE_COMPLETE_VALIDATION_PENDING=false，PRODUCT_ACCEPTANCE_COMPLETE=false，production_activated=false。

## DEC-G6-011 — 2026-09-18 第二次未知提交隔离、诊断修复与恢复入口

rev08 已在 N07_T3 停批：21 次提交、20 条显示、1 UNKNOWN、23 未提交，无存活执行器。20 条回答的内部非盲逐项评审为 70 PASS / 10 FAIL，另有 96 项未评；N02 候选排除范围和 N06 计划/完成/贡献扩张两类 MAJOR 仍 OPEN。实际请求核查证明相邻候选原文、原始分工、说话人以及分工/开始/完成约束已发送，尚未证明唯一根因，不能靠继续堆同义规则声称修复。

传输诊断是独立的本地修复：保留 journal-first、UNKNOWN、停批、费用预留与零重试，仅新增受限异常类型和有界 OS 错误码，兼容旧五字段回执，不记录异常正文或凭据。旧两条 URLError 无法回填新诊断。首次专项暴露测试夹具错误：本机 OSError(10060) 实际构造 TimeoutError；保留失败后改为显式跨平台 TimeoutError 夹具，不放宽诊断允许列表。最终专项 116/116，旧完整回归 449 兼容通过及 1 个保留的历史源码身份错误，43 模块/450 分母再次核验；无新增功能失败、历史与正式 Runtime 未改。一次不带凭据及对话的连接观察收到 HTTP 401，不能用于裁定两次历史 UNKNOWN 或证明长回复网络已恢复。

候选、交互入口、中性盲包、跨日 checkpoint 与逐条纵向评审工具合并离线 79/79。实际发送的检索/历史与仅存 trace 的数据已区分；签名及结构通过不等于真人输入、独立评审或语义质量通过。三套当前源码完整语义门未过，因此没有新受控候选、当前外评包、真实外部回传或新自然日。旧候选及旧日期继续仅作为历史。

恢复入口为 persona_core/gpt6_optimization_v2/CURRENT_EXECUTION_RUNBOOK.md 与 RECOVERY_CURSOR.json。G6 累计 271 次提交，已知用量保守估算 3.793624 CNY；两条 UNKNOWN 预留 1.285526 CNY 单列，总实际费用仍未知。当前诊断工作没有新增生成调用。不得通过更名批次重发未知请求；后续新实验须先有实质根因修复与冻结完整范围。BUILD_SCOPE_COMPLETE_VALIDATION_PENDING=false，GPT6_CORE_BUILD_COMPLETE_VALIDATION_PENDING=false，PRODUCT_ACCEPTANCE_COMPLETE=false，production_activated=false；WAITING_EXTERNAL、WAITING_REAL_TIME（新候选 0/3）保持。


2026-09-18 — DEC-G6-012 — 通用陈述/证据表示。普通话语保留原文和来源身份；语义候选不获得准入权限，未解析阶段/条件/否定保持未决。选中检索原话须完整发送，预算不足在调用前拒绝。已核验更正提供版本沿革，宿主核验仅覆盖文字约定/提交。18项新增离线机制测试通过；全量回归进行中，两个MAJOR仍OPEN，旧UNKNOWN未重放。


2026-09-18 claim/evidence final checkpoint: 20 new mechanism tests (12 authored language examples); all 19 G6 component modules pass 279/279. Complete unchanged legacy denominator 450: 449 compatible passes and the retained historical-source identity error, independently verified against all 43 module logs and exact current source. The bounded-summary gap is closed by carrying receipt/correction lineage in selected verified retrieval itself. An exact 24576-byte component boundary exposed metadata overhead; redundant index wording was compacted, with no budget/threshold increase. 310 protected files and both frozen heldout members unchanged. No model generation or automatic retry; two old UNKNOWNs preserved. Offline construction and structural binding do not prove semantic repair, naturalness or nonleakage. The two MAJOR findings remain OPEN; no new paid revision/candidate/blind package/real date. Evidence: persona_core/gpt6_optimization_v2/G6_07_CLAIM_EVIDENCE_ADJUDICATION.json.
