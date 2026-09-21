# Revision Sampling Policy

版本 APCORE_MODEL_QUALITY_ACCEPTANCE_1。Multi-revision reliability acceptance：NO。对当前失败配置新增 revision 数：0。对以后一个合格后继候选：预注册数=1，上限44次生成，176个原判断；不是 K 次取最好一次。

原 external44 场景、顺序、每场轮数、换模位置、原 criterion ID/措辞和 P1 routing 全部保留。下一候选若改变模型角色绑定，需要显式登记原位置的映射；不删换模考题、不偷换成44个独立单轮问答。严禁将 PRIVATE_RUBRIC 或本案例答案、failure quote、评审结论投影给生成模型。

新 revision 必须新隔离存储、新 session/实例标识和独立 journal，只按原合同复制干净来源/Genesis 基线，不继承测试对话、runtime memory、旧模型输出或评分。每个场景内部保留真实展示历史和既定连续性；不得在出错后重置上下文、补答、插入人工纠正或替换显示来获得成功。

抽样独立性只作工程隔离要求，不承诺服务端样本独立同分布。44轮有多轮依赖、同一回答有多个相关评分；176 criterion 和308子判断均不可作为独立 Bernoulli 样本数。单 revision 无跨 revision 可靠率估计。

首个 blocking quality Major 后取消剩余未提交槽位并保留 UNREVIEWED；不是缩小分母，也不是将剩余槽位当 FAIL。所有已提交原件、终态、显示、评分和费用证据保留。全部可用已捕获回答完成原标准评审，不能只展示出错前的成功部分。

任何 UNKNOWN 立即停整个 campaign、保留费用预留、隔离，不重发、不替代、不把 UNKNOWN 标成语义失败或成功。已知终态拒绝同样停止，标 EXECUTION_INCOMPLETE / NOT_ACCEPTED，缺失判断仍未评；不凭无文本推断语义错误。若同时已有质量失败，保留 FAIL 优先事实和独立执行状态。

Retry-until-pass：FORBIDDEN。失败→新 revision→失败→再新 revision，改变 seed、session、日期、窗口、供应商别名或者政策版本来重置机会，均禁止。
