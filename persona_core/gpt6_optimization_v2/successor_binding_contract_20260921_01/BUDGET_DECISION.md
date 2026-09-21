# 精确候选与单批预算决定

Candidate: APCORE_SUCCESSOR_OPENAI_ASTRA_MAX_SOL_MAX_1。Batch design: APCORE_SUCCESSOR_EXTERNAL44_ASTRA_SOL_MAX_SINGLE_BATCH_1；这是设计ID，不是fresh revision登记。当前BUDGET_NOT_READY；现有上限19.00 CNY；本会话没有对应新金额批准，753 CNY明确NOT APPROVED。旧48.64 CNY和宽泛历史授权均不继承。本轮支出0、Provider API/readiness/paid请求0。

当日官方Standard价（USD/百万token）：

| 模型 | input | cache read | cache write | output（含reasoning） |
|---|---:|---:|---:|---:|
| gpt-6-astra | 10 | 1 | 12.5 | 50 |
| gpt-5.6-sol | 4 | 0.4 | 5 | 20 |

来源：[官方定价](https://developers.openai.com/api/docs/pricing)。新GET抓取时间与原文哈希见OFFICIAL_PRICING_EVIDENCE.json；相同哈希表示当天取得相同内容，并非沿用本地旧缓存。实际账户可用性、FX、税费未知，未探测。

| 角色 | 槽位 | input reserve | output+reasoning等总cap | 单槽USD | 合计USD |
|---|---:|---:|---:|---:|---:|
| PRIMARY | 42 | 28672 | 32768 | 1.9968 | 83.8656 |
| SECONDARY | 2 | 28672 | 32768 | 0.79872 | 1.59744 |

全批API设计上界 = 42×(28672×12.5+32768×50)/10^6 + 2×(28672×5+32768×20)/10^6 = **85.46304 USD**。
在input bound成立、Standard、非regional endpoint、FX≤8 CNY/USD、额外税费/支付费总加成≤10%时，全批条件上界 **752.0747520 CNY**，向上整元建议 **753 CNY**。按单槽micro-CNY向上预留：PRIMARY 17,571,840；SECONDARY 7,028,736；全44槽752,074,752 micro-CNY。无cache-hit折扣假设，reasoning没有重复计费。

这个数值不是无条件担保：28672输入上界仍需INPUT_BOUND_CONTRACT的证明，实际FX/fee尚未知。任一条件未满足不得提交；预算批准本身不使这些条件变成已证明。官方长context阈值272000高于本设计cap；不能在超界时自动切换premium价并继续。

五种数值必须区分：①API技术容量：input922000/output128000；②protocol requested ceiling：原24576 bytes、output32768；③历史观察：metadata-only分布见私有审计，来自旧Provider及停止批次；④pre-submit reservation：可信I_bound+32768输出，当前28672只为候选设计；⑤acceptance budget guard：19.00，只有精确用户决定才可提高。历史均值/中位数/最大观察都不是可提交上界，更不是新模型reasoning分布。

是否过度夸大：input的bytes+4096是保守设计而非技术最大，可能可收紧但尚未证明；output32768是用户保持的实际请求cap而非128000技术容量。即使忽略全部input，原44槽输出cap之和仍为70.12352 USD（这是同一cap下的输出预算组成，不是实际最低费用）。仅准确输入计数不能把该cap预算压进19 CNY。不得通过均值、通常用不满、停流、删context、减turn/criterion或降reasoning降预算。

未来可收紧条件：对每个槽完整动态上下文建立可验证I_bound_j，保留全部质量/上下文要求，再用固定费率加总；没有这样的全分支证明时金额保持本条件方案。当前不提出更低金额。官方计数endpoint是另一类Provider API调用，不在本轮/零调用实施/44次生成范围内，不能隐含启用。

后续决策需要用户明确指定本candidate、此单批44槽及精确金额，并保留FX≤8/fee≤10%、0readiness、0retry、0额外样本和完整原质量规格。若批准753，只记预算授权事实；输入proof、实现、tests、freeze、preflight与真实执行授权仍各自核验。若不批准或未回复，维持19/BUDGET_NOT_READY，不实施代码。
