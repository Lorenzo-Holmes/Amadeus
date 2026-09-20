# 唯一后继配置选择

Task: G6-07-MODEL-CONFIGURATION-QUALIFICATION-PLAN-V1。Policy: APCORE_MODEL_QUALITY_ACCEPTANCE_1。配置设计已冻结；尚未获得执行资格。

[INFERRED / MED] 公开能力说明不能证明候选将在本项目通过。当前独立依据足以选择一个有实质差异的候选进入接线与预算审查，不能给出模型总体可靠率或供应商胜负结论。

选择 **OpenAI Official：42 × gpt-6-astra / max + 2 × gpt-5.6-sol / max**，作为一个整体配置。第二模型只占原有两个换模位置，不构成第二候选、补样或失败后回退。主角色从 deepseek-v4-pro 换成不同的正式模型；日期、seed、session 和 revision ID 不作为差异依据。

[KNOWN] 官方将 [gpt-6-astra](https://developers.openai.com/api/docs/models/gpt-6-astra) 定位于复杂推理和困难任务，提供 max reasoning、Responses 和流式文本能力。其 [使用说明](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra) 讨论指令遵循、上下文连贯及科学工作，也明确有偏详细、格式化表达的倾向。后者是待验证的自然度风险，不通过改 prompt 或降低质量门规避。

[INFERRED / MED] 这些通用能力与项目的推理、任务完成、指代、连续性需求相符，因此采用它承担主角色。辅助使用同一官方后端的 [gpt-5.6-sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)，保留真正的跨模型连续性测试，并减少引入第二种支付/路由协议的变量。两个角色均固定最高公开 max effort；没有采样比较。

[KNOWN] [DeepSeek 官方价格与型号页面](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) 仍将失败主模型映射到同一 Pro 版本；[推理说明](https://api-docs.deepseek.com/guides/thinking_mode/) 的 max 已是现用档位。没有找到足以支持“同主模型再换名或重抽一次”的独立变化证据。未运行的辅助槽位不能解释主角色失败。现有 OpenRouter 接线只实现独立 synthetic 路径和固定小模型，其 PASS 不构成正式质量资格依据。本次检索不是穷尽所有服务商的排名。

[COMPUTED / HIGH] 本地证据来自源码/合同哈希、旧请求的参数键和正式 driver 静态检查。未打开 PRIVATE_RUBRIC 的内容作选型；哈希读取不提取答案。恢复历史审计时可见的既有 finding 不参与候选排序或参数选择，不复制到提示词。没有构造或发送任何新 benchmark 请求。

[COMPUTED / HIGH] 正式驱动不兼容，状态为 VALIDATION_BINDING_CHANGE_REQUIRED；19 CNY 上限不足，另列 BUDGET_NOT_READY。完整费用设计为 85.46304 USD，条件化人民币建议上界 753 CNY。汇率上限与费用预留是计划控制参数，不是官方汇率或已批准预算。无法用平均费用、缓存命中预测或低输出上限使其合规。

官方公开 snapshot ID 原样采用 gpt-6-astra / gpt-5.6-sol；未发布的服务端 build 记 UNKNOWN，不编造日期后缀。保留相同 source、Persona、Genesis、上下文、display/state/strict policies、44/176 与原换模位置。后续若修改接线文件，必须生成新 source freeze 并与当前 P3 父版本衔接；不能继续宣称新字节仍匹配旧182成员。
