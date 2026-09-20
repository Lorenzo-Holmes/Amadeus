# R16 Disposition

Policy APCORE_MODEL_QUALITY_ACCEPTANCE_1。

R16：FAIL / PERMANENTLY_QUARANTINED。R16-N02-01：MAJOR / OPEN_BLOCKING。禁止 re-score、retry、rerun、replace、erase、恢复剩余槽位，禁止修改 raw/displayed/accepted/findings/verdict/journal/UNKNOWN/SPEND。

保留实际计数：3/44 submitted/provider-valid/displayed；12/176 reviewed=11PASS+1FAIL；164UNREVIEWED。Gate A FAIL；Gate B 9PASS/123UNREVIEWED、INCOMPLETE。已观察状态逃逸0不等于完整状态门PASS。

上一轮已核验：错误在MODEL_RAW；实际生成输入和上下文投影完整；展示没有将正确答案变错；evaluation finding未被推翻；通用推理方向、必要条件及辅助前提约束已存在。NO_GENERALIZABLE_PRODUCT_DEFECT_CONFIRMED 保持；本轮无新直接反证，不修改生产源码。

本轮新裁决只追加当前配置的资格处置，不改变原finding。相同source+配置的新PASS即使在别处出现，也只能成为另一条观察，不在本政策下撤销R16或恢复已失败配置资格；本政策不授权产生该观察。

后继实质不同配置若完成未来完整验收，可追加新配置对风险的处置证据，原失败原件和原OPEN_BLOCKING字段仍保留。当前风险仍阻塞当前候选，不能以“只是历史”略去。尚未证明错误只出现一次，尚未证明服务商总体不足。
