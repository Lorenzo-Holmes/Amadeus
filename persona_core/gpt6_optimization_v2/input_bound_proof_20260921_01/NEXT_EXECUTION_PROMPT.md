继续 Amadeus Persona Core / APCORE-GPT6-OPTIMIZATION-V2。
唯一工作区：C:\Users\skr\Documents\Codex\Amadeus-Project.staging。

先完整读取 persona_core/APCORE_CANONICAL_EXECUTION_GUIDE.md，再读取根治理入口、四份 G6 machine state，以及本目录 FINAL_AUDIT.json、STATE_WRITE_RECEIPT_PRIVATE.json、EVIDENCE_SEAL.json、INPUT_BOUND_PROOF_AUDIT.json、PROOF_OBLIGATIONS.json、LOCAL_TOKENIZER_AUDIT.json、OFFLINE_TEST_RECEIPT.json、INPUT_BOUND_ANALYSIS.md。

当前阻塞仍为 INPUT_BOUND_PROOF_NOT_READY。当前源码 OPENAI_FORMAL_SUCCESSOR_BINDING_20260921_01 未改变，184/184 MATCH；父归档182/182 MATCH。新 source freeze 未创建。原40 binding tests本轮复跑PASS，42本地证据/拒绝检查PASS；两者不是token上界证明。821组件与449 compatible +1 expected historical source-identity sentinel /0 unexpected采用哈希复核后的已有证据，未重复执行。

本轮已实际取得并离线导入官方 tiktoken 0.14.0：gpt-6-astra 无映射；gpt-5.6-sol 仅匹配通用gpt-5前缀，没有精确条目。前缀匹配也接受不存在的控制名称，不能作为精确模型证明。已读取的官方SDK/文档未提供可审计的这两个精确模型的本地Responses消息framing上界。实际生产proof registry仍为空；不得填入mock、猜测encoding或把24576 bytes+4096 allowance改称认证上界。

先检查是否有新的可信模型encoding/framing证据。若没有新证据，不重复下载同版本、重复同一审计或全量suite来制造进展；保留NOT_READY并说明缺失的具体证据。若有，可在当前授权范围内完成本地证明。预算PROJECT_COMPLETION_SPEND_AUTHORIZED_AS_NEEDED持续有效，不要再次要求金额审批。不调用远端count、模型readiness、小额请求或responses来建立本地证明。

只有完整覆盖冻结所有role/Unicode/history/serialization的本地精确或保守上界证明成立，才能做最小proof integration。源码变化必须先有限change-control、受影响回归、再建立新独立冻结，旧184和父182冻结不得覆盖。随后运行真正ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT。当前仅前置gate返回NOT_READY，formal_preflight_executed=false；不得继承历史或诊断READY。

仅当proof READY、回归GREEN、全部身份MATCH、formal preflight READY且active paid driver=0，才直接执行已授权的唯一一次fresh44/176 successor。候选固定APCORE_SUCCESSOR_OPENAI_ASTRA_MAX_SOL_MAX_1：gpt-6-astra×42，gpt-5.6-sol×2，Responses、DIRECT_NO_PROXY、stream=true、reasoning=max、max_output_tokens=32768。原schedule/payload/176criteria/GateA176/GateB132不变。每轮先证明/预留/身份检查，再单次提交；下一次付费前必须审完上一轮。Major/Critical/UNKNOWN按冻结规则停批，不重试、不fallback、不第二revision。

R16 FAIL/PERMANENTLY_QUARANTINED、R16-N02-01 MAJOR/OPEN_BLOCKING、历史UNKNOWN7及全部journals/SPEND保持只读。successor未创建，0/44、0/176；G6-07历史FAIL与successorVALIDATION_PENDING分开记录。G6-08/09 LOCKED，build/product/activation flags false。即使未来successor PASS，本验证会话也不执行G6-08。

仅公开无private dialogue/response/rubric/SQLite/SPEND/credentials/UNKNOWN capture/hidden reasoning的摘要、代码、测试和manifest；提交原branch/PR1。结束时同步当前机器字段及镜像，保留全部旧checkpoint，写精确恢复回执并安全停止。
