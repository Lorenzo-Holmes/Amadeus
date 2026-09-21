# Model Configuration Qualification

绑定 `APCORE_MODEL_QUALITY_ACCEPTANCE_1`。当前裁决：`CURRENT_CONFIGURATION_FAILED_MODEL_QUALITY_GATE`。总体真实错误率：UNKNOWN。不得把后一项未知覆盖前一项明确拒收。

## 当前实际配置身份

Provider 为 DeepSeek Official；已观察失败发生于 deepseek-v4-pro；接口 Responses API；reasoning=max；DIRECT_NO_PROXY；stream=true；source freeze 为 BOUNDED_CONVERSATION_STATE_BOUNDARY_P3_20260920_01。

磁盘 R16 FINAL_AUDIT 还表明：完整计划是 42 个 pro 槽位 + 2 个 flash 换模槽位，实际只运行 3 个 pro 槽位。资格对象必须绑定整个角色/槽位映射，不能误写成计划 44 个 pro，也不能归咎未观察到的 flash。请求边界为 max_input_bytes=24576、max_output_tokens=32768、timeout=600s。历史 guard=48.64 CNY 只是历史上限，不是本轮消费或新批次授权。

## 配置指纹与变化标准

未来指纹必须包含 source manifest、生成指导/consumer policy、provider、精确 model ID/可得版本、角色及切换槽位、API、路由、stream、reasoning、temperature/top_p/seed/penalties 的显式值或 NOT_SENT/UNSUPPORTED、输入/输出限制、超时、工具能力、evaluation policy 和数据/rubric/routing 哈希。服务端默认不可知时写 DEFAULT_UNVERIFIED，不能编造有效温度或独立性保证；默认/后端版本漂移时停止或声明证据适用范围受限。

日期、revision ID、session ID、seed 随机换值、重连或无效/被忽略的参数不构成实质配置变化。只换 Flash 而保留产生 Major 的主要生成角色，不构成对此缺陷的处置。新候选必须具有能关联生成推理质量的实质差异及独立于本题答案的选型依据；可以仍在同一 Provider，也可以不同 Provider，不预设必须保留或更换 DeepSeek。

## 有限资格流程

下一阶段只进行零调用配置选型，最多选定 **一个** 后继候选，先冻结候选、通用能力依据、兼容性、参数与定额，不用真实答题结果挑候选。没有合格候选即停止，不凭名称差异放行。

本政策给予该后继候选的设计上限为一次独立 fresh revision，44 turns / 176 criteria；本轮及下一份选型提示词均不启动它。后继候选失败后没有自动下一个候选额度，没有自动增加 K、切 Provider 或调温度的循环。进一步工作必须有新的独立证据与具名治理裁决，不能只以“还没 PASS”为依据。

当前完全相同 source + 配置：不得新建 fresh validation。当前 source 不变 + 实质不同且通过零调用预检的新配置：原则上允许以后 fresh validation；无需虚构生产代码缺陷。若现有驱动硬绑定旧 Provider/角色，记录 VALIDATION_BINDING_CHANGE_REQUIRED，先冻结有限验证接线合同；本政策不授权修改 production source，也不能把另一个 Provider 的 synthetic PASS 冒充 G6-07。

失败配置保留于全量资格表，后继候选结果另列；不得合并不同配置估计同一可靠率。后继合格仅允许追加“旧 finding 对新配置已被具名证据处置”的关系，不编辑 R16 OPEN_BLOCKING 原件，不声称已修复旧配置。当前没有此处置证据。
