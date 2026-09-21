# Formal driver compatibility：CHANGE_REQUIRED

配置 APCORE_SUCCESSOR_OPENAI_ASTRA_MAX_SOL_MAX_1；静态审查，无运行 prepare/run/preflight，无 Provider 调用。现有 synthetic PASS 仅属既有证据，未重跑。

| 检查 | 当前事实和资格结论 |
|---|---|
| Provider adapter | provider_adapters.py::registry 仅注册 DeepSeek、local fixture、OpenRouter；无 OpenAI Official adapter。CHANGE_REQUIRED。 |
| API / route | evaluation_runner.py::build_scope 固定 DeepSeek endpoint 与 scope-4/5。OpenAI /v1/responses 和 DIRECT_NO_PROXY 必须有独立 host allowlist。CHANGE_REQUIRED。 |
| 模型与原角色 | load_suite 要求两个模型均在 provider.RATES；新模型不在其中。不得把新型号伪装成 DeepSeek。原42/2与两处换模位置保留。 |
| Reasoning / 参数 | 旧 validate_rows 只接受旧五字段 Responses payload。新明确 service_tier/store/tools/cache 等字段无法通过；完整请求身份需绑定。 |
| Streaming / terminal | ResponsesAssembly 有终态基础能力，但 OpenAI 事件、拒绝/取消、usage 与 wire verification 尚未由正式路径证实。HTTP 200 或 EOF 不能当完成。 |
| Token accounting | 旧 usage 归一化只处理 hit/miss 与 reasoning；新 cache_write_tokens 不可丢失或按旧 miss 费率收费。输出 cap 含 reasoning。 |
| UNKNOWN | 复用 journal-first 和单槽幂等原则；无可信终态则UNKNOWN、全额保留预留并停批。不得新增查询后重发/自动补样。 |
| raw / displayed lineage | 保留不可变 wire/raw、显示ACK、accepted投影及各自哈希。新的decoder必须进入同一正式路径；synthetic记录不得当正式回执。 |
| state-effect path | admission-46.2、host evidence、candidate→decision→commit 不变；新配置未执行，不能报告 State Gate PASS。 |
| Consumer projection | 保留 RAW_DISPLAY_ACCEPTED_IDENTITY_2、DUAL_GATE_DISPLAY_STATE_1 与 consumer matrix。现有 provider_identity 可覆盖新增 scope 控制，但旧 binding 不能替新候选授权。 |
| Spend | checked_pricing 只认 DeepSeek 价格域与RATES，旧guard≤150 CNY；无该候选美元/缓存写入/汇率与独立批准合同。CHANGE_REQUIRED。 |
| Source binding | runner、provider、contract均在182-member freeze内。修改后必须新freeze；不得编辑原manifest或继承新模型质量PASS。 |
| Preflight | formal_binding_preflight.py 硬编码旧42/2模型，并调用prepare建立mock revision目录。不得用于本候选READY或在本轮运行。 |

## 最小有限接线计划（本轮没有实施）

下一轮先采用具名接线合同与精确allowlist。可以围绕原 runtime 接口接入正式 adapter，不触碰人物和语义层。建议的有界文件范围：

| 文件（相对工作区） | 最小变更与目的 |
|---|---|
| persona_core/operational_runtime_v1/provider_openai.py（新增） | 仅官方OpenAI主机/Responses；两精确ID；封闭payload；DIRECT_NO_PROXY；禁止redirect/fallback/retry；OpenAI usage含cache-write与可靠终态规范化；凭据仅运行时读取、私有管道传递。 |
| persona_core/operational_runtime_v1/provider_adapters.py | 显式注册该adapter，沿用已有worker委派入口，不扩大任意endpoint能力。 |
| persona_core/operational_runtime_v1/provider_contract.py | 增加具名formal provider scope版本，保留scope-6的1–2-slot synthetic限制；冻结44-slot schedule、完整参数、source与批准预算，增加非加法cache-write计价。 |
| persona_core/operational_runtime_v1/provider.py | 仅新增正式scope分支的journal-first、整数费用预留/上限检查和receipt验证；旧scope行为、旧150 CNY限制和历史DB不变。 |
| persona_core/gpt6_optimization_v2/tools/evaluation_runner.py | 在新schema分支支持两模型角色、独立价目与预算身份、adapter序列化及wire复核；移除该分支对DeepSeek固定期望的依赖；原题输入/顺序/分母不动。 |
| persona_core/gpt6_optimization_v2/tools/formal_binding_preflight.py | 接收冻结配置；离线构造/检查44项绑定，所有网络与Provider call入口拒绝。隔离临时存储放work，不在正式evidence注册revision。 |
| persona_core/gpt6_optimization_v2/tools/test_openai_formal_binding.py（新增） | 有限、独立作者的中性fixtures，覆盖参数/模型/费用/source漂移、cache-write、完整/不完整/失败/截断流、UNKNOWN不重试、显示与状态隔离。禁止私题答案fixture。 |

provider_http_worker.py已有adapter_contract委派；provider_transport.py已有Responses组装基础。优先复用而不修改，必要的OpenAI差异留在新adapter内。若这七个路径不足，先报告精确原因并修订allowlist；不得顺手扩张。formal_acceptance.py与semantic_binding.py的provider_identity覆盖scope的能力应复用；不改固定display/state/strict规则。

任何上表runtime修改均属于新的source字节，**本轮明确禁止且未发生**。下一阶段即使只改验证接线，也须新的source freeze、旧冻结存档、受影响组件/consumer回归和正式零调用预检；不可在旧manifest内替换哈希。首轮只能离线，未解决预算前不跑付费验证。

主要风险：原provider schema分支误混、模型身份漂移、cache-write漏计、终态与质量状态混淆、显示/next-turn分叉、复用测试状态污染、新source冒充旧freeze。退出条件是各项离线证据和批准预算均具名，不是synthetic PASS数量。保留原政策的quality Major / integrity Major / Critical三类停止及全部历史失败。
