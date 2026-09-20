# Aggregation Rules and Statistical Interpretation

版本 APCORE_MODEL_QUALITY_ACCEPTANCE_1。

## 确定的工程判定

原分母固定176 unique criteria（44 turns × 4）；Gate A 176子判断，Gate B 132子判断。44 Conversation-only +132 BOTH；BOTH仅当A与B均PASS才PASS。308子判断不可冒充原分母，不可视作308个独立样本。

PASS 当且仅当：44个原槽位都有有效完整回执和显示证据，176个原必需criterion全部PASS，A176/B132全部PASS，所有原场景/类别覆盖完整，原质量聚合规则满足，未解决 blocking Major=0、Critical=0，未解决当前批次 UNKNOWN=0，且源码/配置/consumer绑定完整。FAIL 或 UNCLEAR/UNREVIEWED 不能用别项高分抵消；出现blocking Major或Critical即FAIL。仅因缺失证据未完成且无语义失败时为INCOMPLETE/NOT_ACCEPTED。

情境适配 category mean≥4/5、自然度≥4/5、人物特异性≥3/5；原场景资格、类别均值、switch/regression分离继续有效。不得新增跨场景或跨revision平均来救回失败类别，不给未完成场景编造整场分；原规则若有更严场景约束仍必须满足。评分必须引用私有的原冻结协议，公开政策不复制题目/答案。

## 统计解释和为什么不选 K=3

本政策是具名配置的工程准入，**不是**“以95%置信度证明普遍可靠”。一个测试revision成功不能证明零错误率；一个失败也不能估计整体错误率。R16 12项已评中的1项FAIL不是可推广的1/12错误率：题目选择、多轮相关及遇错即停均限制推断。

抽样验收须先明确可接受/不可接受错误率和两类决策风险，再选择样本量与允许失败数；这些不能从既有44/176自动推得。[NIST sampling-plan design](https://www.itl.nist.gov/div898/handbook/pmc/section2/pmc232.htm)。小样本错误比例的区间宜使用二项精确方法而非简单对称正态近似。[NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)。本政策的以下示例是自主公式推导，不是上述来源对本产品的背书。

仅假设 K 个完整revision是独立、同分布的Bernoulli试验且都成功，单侧95%精确成功率下界为 L=0.05^(1/K)，失败率上界为1−L。K=1、3、5、10时成功率下界分别约5.00%、36.84%、54.93%、74.11%。所以三次全通过也不能宣称95%可靠。若只是演示“成功率≥95%，单侧95%置信”的零失败设计，则 K=ceil(log(0.05)/log(0.95))=59，需2596 turns、10384 criterion judgments。此95%目标是计算示例，**未被采用为新产品门**；固定题库与后端漂移还会限制外推。

R16历史guard48.64 CNY作纯线性预算参照：K=3为145.92、K=59为2869.76 CNY；这是历史最坏保护上限的乘法，不是当日定价、预期消费或批准额度。选择K=1来自原始完整必需项工程门，而非声称1次有足够统计效力。以多次全部PASS来增加信心需要明确新需求；允许少量Major则改变现有门，本次不做。

遇错即停仍可确定“该trajectory不能全部通过”的二元失败，但无法获得余下轮次的错误频率；删掉失败revision或只按完成revision计算成功率会产生选择偏差。历史R12–R15属于不同source/architecture，不与R16合并计算配置可靠率。R16保留为失败观察；不把其余164未评项当作成功或失败，不伪造完整场景分。

若以后采用统计研究，K、单位、容忍率、置信水平、独立性、早停/删失、类别门和全部失败纳入规则必须事先冻结；可做固定设计下的精确区间，不能随时停在漂亮结果上。本版未授权这样的实验。
