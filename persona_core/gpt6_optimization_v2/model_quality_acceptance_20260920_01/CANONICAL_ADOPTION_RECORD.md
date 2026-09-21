

## 39. Model Quality Policy Adoption — ADR-MQA-20260920-01

采用时间：2026-09-20T15:31:19.138678+00:00。Task：G6-07-MODEL-QUALITY-ACCEPTANCE-DECISION-V1。正式采用 `APCORE_MODEL_QUALITY_ACCEPTANCE_1`，合同目录 `persona_core/gpt6_optimization_v2/model_quality_acceptance_20260920_01/`，以 POLICY_FREEZE_MANIFEST.json 绑定。选择 C（配置资格审查）并以 A（单 revision 严格门）实施；不采用多 revision 容错聚合，不新增 Major 容忍率。保留原44/176、P1 A176/B132及所有质量阈值。普通Conversation与Trusted State冻结架构不变。

当前配置已未满足模型质量门，进入 MODEL_CONFIGURATION_REQUALIFICATION_REQUIRED；这是本次工程资格拒收，不是整体错误率或Provider能力的统计结论。无通用产品缺陷证据，不修改源码。R16永久FAIL/隔离，原Major OPEN_BLOCKING保留。同source+同有效配置不得通过换revision再抽样；以后同source+有实质差异的一个候选须先完整预注册、零调用绑定预检，再按新会话范围进行一次44/176。当前没有新revision。

本版quality Major也停止采样；原因是严格门已不能满足，不是将对话错误升级成状态逃逸。安全/状态hard stop、UNKNOWN隔离、0自动retry不变。此记录细化§27 P4失败后的处理：没有产品缺陷时转配置审查，不能要求无依据修产品，也不能retry-until-pass。G6-07保持FAIL，G6-08/09 LOCKED，build flags false；本任务所有Provider/readiness/paid calls为0。下一恢复点为上述目录FINAL_AUDIT.json；旧章节的历史状态不被重写。
