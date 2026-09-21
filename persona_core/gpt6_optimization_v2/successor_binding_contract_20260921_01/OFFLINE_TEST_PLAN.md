# 最小离线验证计划

DEFINED / NOT_RUN。唯一新增测试模块为implementation allowlist第7项；fixtures为独立中性作者样例，不能复制private rubric或模型回答。全部在work隔离store；父子进程同时禁止socket连接、Provider真实exchange和credential访问。fake transport不是synthetic Provider调用，也不能当formal质量证据。

| ID | 要求 | 必须观察到的判定 |
|---|---|---|
| OB-01 | exact model allowlist | exact two IDs pass; aliases/date inventions/old provider IDs fail before key read |
| OB-02 | role mapping | 44 schedule exact order; 42 PRIMARY and N09_S1/N09_S2 SECONDARY; preserve restart actions |
| OB-03 | request serialization | canonical golden neutral payload for both roles, recursive key equality, byte/hash equality parent-worker |
| OB-04 | unsupported field rejection | every omitted field plus arbitrary nested key/null/type mismatch rejected; no silent drop |
| OB-05 | reasoning field binding | effort=max and mode=standard sent, returned mismatch/missing required echo rejected |
| OB-06 | stream parser | fragment at every UTF-8/event boundary, CRLF, multi-data; malformed, duplicate/conflicting terminal/index rejected |
| OB-07 | visible response extraction | only final assistant output_text; delta/final equality; refusal/tool/reasoning-only cannot become displayed text |
| OB-08 | usage accounting | native object preserved; integer/count identities; fractional rates and conservative micro-CNY rounding |
| OB-09 | reasoning/output accounting | O includes R; O-R labelled nonreasoning not visible; formatting residual UNKNOWN; no second charge |
| OB-10 | cache read/write accounting | C/W/U disjoint; no-hit/all-write/mixed; missing W retains upper reserve and not accepted |
| OB-11 | completed classification | trusted completed plus valid identity/usage/text captures; quality still unreviewed |
| OB-12 | incomplete classification | max_output_tokens/content_filter known rejected, partial not displayed, stops/no replacement |
| OB-13 | failed classification | matching failed/error terminal known; HTTP error not promoted; missing usage retains reserve |
| OB-14 | UNKNOWN handling | EOF/timeout/partial/wire mismatch preserves raw partial and whole reserve, batch stopped |
| OB-15 | no automatic retry | inject 429/5xx/timeout; exactly one fake exchange; no fallback/reconnect/poll/count |
| OB-16 | raw preservation | wire bytes/hash, redaction flags, native usage and normalized compatibility projection linked |
| OB-17 | displayed projection | original display ACK/evaluation/next-turn equality; unacknowledged raw excluded |
| OB-18 | accepted lineage | same bound source/policy/consumer identities throughout; forged or old accepted identity rejected |
| OB-19 | state-effect separation | neutral hypothetical display allowed; unsupported durable candidate HOLD/REJECT; no Persona/Genesis effects |
| OB-20 | identity fail-closed | mutate source/policy/schema/dataset/rubric/criterion/schedule/price/FX/approval independently; no submission |
| OB-21 | restart | crash before journal, after journal, during wire, after terminal before commit; restart never issues second request |
| OB-22 | idempotency | repeat same turn/slot and concurrent contenders produce one durable call at most; no slot reset |
| OB-23 | wrong-model rejection | requested vs returned model mismatch incl allowed other role model fails |
| OB-24 | provider fallback prohibited | unknown provider/host/proxy/redirect rejected, same exact endpoint only |
| OB-25 | input bound | missing proof/old payload hash/Unicode/large message count/over cap fails; valid receipt binds full payload |
| OB-26 | server accounting breach | I>I_bound/O>cap stops with actual evidence, not clamped; budget guarantee withdrawn |
| OB-27 | scope isolation | scope-5 old restrictions and150 CNY unchanged, scope-6 max2/synthetic unchanged, scope-7 external44 only |
| OB-28 | budget and authorization | 19 cannot cover complete bound; no753 approval; exact foreign batch/amount/rate approval rejected |
| OB-29 | worker subprocess | real existing worker IPC with fake HTTP transport in isolated child; deny sockets/key lookup in both processes |
| OB-30 | zero-provider preflight boundary | all44 static bindings+7 initial composed contexts, no call rows, no formal revision dir, network and key reader fail if touched |

执行时分三类报告：新adapter/接线unit与integration；受影响现有provider/transport/evaluation/consumer回归；source-freeze后的零调用formal preflight。一次完整相关回归即可，源码未变化不重复全项目suite。每个PASS有实际断言和日志，未运行不得预填。provider2已有synthetic PASS只可作为历史参考。

preflight禁止调用ProviderJournal.call，44检查指固定slot/角色/身份/序列化binding，并不声称预知后续真实多轮文本；实际构造七个初始case context，动态历史覆盖用中性离线重启/幂等fixture验证。输入上界proof未完成时即使其它离线用例通过，正式preflight仍NOT_READY。预算授权缺失亦不能给付费资格READY。

通过条件：所有具名用例通过、相关回归无意外失败、所有private/history不变、真实网络0、真实Provider0、正式revision0、代码改动不超7路径。继承的旧source-identity sentinel保留解释，不洗掉。失败保留原日志、只修允许范围，不放宽判定。
