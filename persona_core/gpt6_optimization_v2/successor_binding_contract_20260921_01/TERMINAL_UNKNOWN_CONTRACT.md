# APCORE_OPENAI_NATIVE_RECEIPT_1：终态与UNKNOWN

adapter私有SSE parser处理任意UTF-8字节分片、CRLF/LF、多data行、事件边界、sequence/index、response/item身份；只在有界wire中保留原生原件。重复JSON key、矛盾response ID/model、重复冲突终态、delta与最终对象内容不符、非法schema或无法完整解码均fail-closed。terminal不是HTTP200、EOF、[DONE]或worker exit0的别名。

response.created/in_progress、output_item/content_part的added/done及output_text delta/done只建立进度与文本一致性。reasoning相关事件可保留私有wire元数据，不显示、不拼入下一轮input。已知非终态事件不能结束调用；未知事件类型不提升为成功，若影响完整性则UNKNOWN。按最终response.output的item/content顺序提取type=message、role=assistant、content.type=output_text文本；验证完整item与delta一致，拒绝tool output、refusal、空白或多个不符合冻结形状的消息作为正式答复。不引入新语义parser。

| 证据 | 远端确定性 / 正式处置 | 费用与后续 |
|---|---|---|
| 可信response.completed，response.status=completed，准确model/effort/mode/tier，完整usage，可用output_text | KNOWN_TERMINAL；RESPONSE_CAPTURED后仍需原display/accepted门，semantic verdict仍UNREVIEWED | 保存usage estimate与预留；依原质量门决定下一槽 |
| completed但refusal/空文本/只有reasoning/意外tool/配置回显不符/usage不足 | KNOWN_TERMINAL；RESPONSE_REJECTED_TERMINAL_KNOWN；NOT_ACCEPTED | 停批；有效usage可估算但不造billing证书；不完整usage保留全额预留 |
| response.incomplete且response.status=incomplete，包括max_output_tokens或content_filter | KNOWN_TERMINAL；RESPONSE_REJECTED_TERMINAL_KNOWN；EXECUTION_INCOMPLETE | partial不显示为正式答复，不重发；已知usage收费估算，缺usage全额预留 |
| response.failed且response.status=failed、有匹配ID及错误结构 | KNOWN_TERMINAL；RESPONSE_REJECTED_TERMINAL_KNOWN | 停批、保留错误原件；不自动fallback |
| 完整非2xx HTTP错误回包或取消证据 | 仅证明该HTTP请求被拒绝/取消时记录native错误；不等于生成completed。无法绑定具体response终态时remote execution为UNKNOWN | 停批，无重试；没有费用证据不得认定0 |
| EOF/timeout/断线/partial JSON/worker异常/缺可信终态或wire-normalized不一致 | SUBMITTED_STATUS_UNKNOWN | 全额预留，隔离partial，整批停止；无重连、查询后重发或替代样本 |
| 明确可验证的提交前本地拒绝 | LOCAL_REJECTED_BEFORE_NETWORK，network_attempted=false | 无目标提交，但已经journal占用的槽位不解除后再抽样 |

三轴分别记录 remote_outcome、response_usable、accounting_status，不能把token accounting错误伪装成语义Major，也不能用known terminal掩盖费用未知。原quality Major→QUALITY_FAILURE_STOP、state Major→INTEGRITY_HARD_STOP、Critical→SAFETY_HARD_STOP不变；缺项UNREVIEWED，不补槽。

journal-first：在网络动作前占槽并持久化SUBMITTED_STATUS_UNKNOWN。崩溃后只读恢复；已存在slot返回原call，不再读key或联网。并发、worker重启、parent crash-after-terminal-before-commit都不能引起第二次请求。无法证明本地receipt完成时保留UNKNOWN；本任务不增加远端GET/poll/cancel接口。

原始wire不可变；credential意外回显沿用现有redaction/quarantine纪律，记录原件hash与redaction标志，不能宣称redacted bytes是未改原件。所有private wire、reasoning材料、raw、displayed、accepted、journal与账目禁止公开上传。
