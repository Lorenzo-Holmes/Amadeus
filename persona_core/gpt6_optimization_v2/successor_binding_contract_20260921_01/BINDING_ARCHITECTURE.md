# 正式后继接线变更合同

Contract: APCORE_SUCCESSOR_FORMAL_BINDING_CONTRACT_1。Candidate: APCORE_SUCCESSOR_OPENAI_ASTRA_MAX_SOL_MAX_1。状态：FROZEN / IMPLEMENTATION_PENDING。本合同是变更要求，不是实现、Provider可用、账户权限或模型质量证书。

Scope Alignment：VALIDATION_GOVERNANCE / INFRASTRUCTURE_CONTRACT；保护 frozen configuration → submitted request → receipt → displayed projection 的身份以及费用预留。Conversation内容、Trusted State准入语义、benchmark scope均不改变。当前允许写新治理目录、work证据、机器镜像及append-only决定、public-safe Git；Provider/readiness/paid/fresh revision/source implementation均为0。

正式链：evaluation_runner（固定44-slot）→ scope-7检查 → 原formal bounded binding → ProviderJournal单槽事务与预留 → OpenAIAdapter闭合序列化 → 现有worker的adapter_contract委派 → api.openai.com/v1/responses → native wire重解码 → 完整usage/模型/终态复核 → 原raw/displayed/accepted及独立state效果消费路径。

scope-5保留旧正式定义；scope-6保留SYNTHETIC_INDEPENDENT_VALIDATION及1–2-slot限制，不能修改成44-slot。新增scope-7只面向本候选、单external44设计；不开放heldout、original82、生产聊天或任意第三方endpoint。schema evaluation仍apcore-gpt6-evaluation-2；scope更新不等于评测语义版本改变。

原42 PRIMARY用gpt-6-astra，N09_S1/N09_S2两个SECONDARY用gpt-5.6-sol；保留原顺序、case ID、entity和restart动作。配置输入引用原预注册；不得重新选型、添加fallback、泛化alias或发出模型探测请求。requested与returned模型逐字相等；服务端内部build保持UNKNOWN。

HTTP合同：仅POST、HTTPS验证、api.openai.com:443、/v1/responses；禁止redirect、代理自动回退、端点替换、SDK自动重试、retry-after重试、resume、重连补流、预热调用和model lookup。DIRECT_NO_PROXY须用空代理配置，并在parent/worker复核；不修改机器全局代理。超时保持connect15/read120/worker595/total600秒及原传输version。复用1MB body/16MB wire/24MB pipe上限；遇容量拒绝保留原件、停批，不加cap或重发。

父进程凭据读取只允许运行时的OpenAI专用配置，不能回退旧Provider密钥。凭据只走私有stdin管道，不进入argv、环境打印、日志、scope、Git或错误正文。native worker合同绑定provider、endpoint、route、transport版本、request hash、request contract hash；parent re-decode wire与worker normalized body一致才认可回执。合同版本：APCORE_OPENAI_RESPONSES_ADAPTER_1 / APCORE_OPENAI_NATIVE_RECEIPT_1。

固定语义：BOUNDED_CONVERSATION_1；admission-46.2；TRUSTED_SEMANTIC_ACCEPTANCE_1；DUAL_GATE_DISPLAY_STATE_1；RAW_DISPLAY_ACCEPTED_IDENTITY_2；FORMAL_BOUNDED_BINDING_1。DISPLAY_ELIGIBLE ≠ FACT_TRUE ≠ STATE_ADMITTED ≠ STATE_COMMITTED。只提取assistant output_text；不用reasoning、refusal或raw草稿充当正式展示。显示ACK、next-turn历史、evaluation消费同一实际展示文本；受信状态独立candidate→decision→commit，不能从Provider成功继承准入。

不修改Persona、Genesis、Memory、Relationship、retrieval、parser、ontology、semantic validator、trusted catalog、expression prompt、display policy或strict typed proof。不得用基准答案构造adapter fixtures。调用失败与模型质量失败分开；保留原Gate A176/B132、原44/176、原质量阈值及Major/Critical停止规则。

旧R12–R16全部只读。R16 FAIL/PERMANENTLY_QUARANTINED，R16-N02-01 MAJOR/OPEN_BLOCKING；旧失败配置新增验收次数0。新的合同或离线PASS不继承synthetic PASS、P3模型质量PASS或G6-07 READY。

后续顺序：精确预算决定 → 后续明确实施任务 → 七路径实现 → 离线测试 → 新source freeze → 正式零调用preflight；真实验证仍须单独有限执行入口与全部前置证据。本轮仅STATIC_BINDING_CONTRACT_CHECK。
