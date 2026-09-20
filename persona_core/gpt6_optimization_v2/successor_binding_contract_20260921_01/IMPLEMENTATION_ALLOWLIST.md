# 精确 implementation allowlist

合同冻结，当前实施授权为零。实现只允许以下 **7 个精确路径**（5 个修改、2 个新增）；禁止目录通配符、重构便利性扩项及未列出 production/test edits。对应字节基线见 IMPLEMENTATION_ALLOWLIST.json。

| 路径 | 操作 | 有限责任 / 七路径充分性 |
|---|---|---|
| `persona_core/operational_runtime_v1/provider_openai.py` | ADD | OpenAIAdapter: exact host/models; closed serializer; private credential reader; native SSE/HTTP decoding; native usage preservation; worker contract; validated token-bound receipt consumption. The existing native worker delegates to an adapter-owned worker_exchange and decode_http_result. OpenAI differences stay here. |
| `persona_core/operational_runtime_v1/provider_adapters.py` | MODIFY | registry/select/native-worker registration of OpenAIAdapter; preserve strict independent wire re-decode in verified_result. The registry already supports provider-owned serialization, transport, decoding, rates and terminal methods. |
| `persona_core/operational_runtime_v1/provider_contract.py` | MODIFY | Add FORMAL_SCOPE_VERSION=apcore-provider-scope-7 and a separate formal checker, scope-7 generation identity, Decimal cache-aware accounting and reserve checks. Keep SCOPE_VERSION=scope-6 unchanged. Scope-6 hardcodes synthetic purpose and 1–2 slots. A separate formal branch avoids reinterpreting it; no generic endpoint support. |
| `persona_core/operational_runtime_v1/provider.py` | MODIFY | Route only scope-7 through formal adapter; journal/reservation before network; bind native receipt and usage; get_call/summary distinguish complete vs bounded estimate; retain immutable request, wire and lineage. ProviderJournal already owns transactional call contract rows, capture and stop state. Scope-7 can use these storage surfaces without transcript schema source edits. |
| `persona_core/gpt6_optimization_v2/tools/evaluation_runner.py` | MODIFY | Scope-7 branches in load_suite, checked_pricing, build_scope, prepare, validate_rows, worker/run/status: exact 44 role schedule, formal source/config construction, adapter request/wire/accounting verification and explicit execute guard. The old five-field serializer, DeepSeek rates and verify_responses_wire(scope-4/5) must not run on scope-7. Use adapter re-decode in this branch. |
| `persona_core/gpt6_optimization_v2/tools/formal_binding_preflight.py` | MODIFY | Configuration-driven ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT; temporary root only under work; 44 metadata bindings, seven initial contexts, source/policy/consumer checks; no call, credential, revision allocation or network. Existing preflight hardcodes old models and calls prepare into formal evidence. Add explicit offline construction destination, implemented in runner; no other allocator edit. |
| `persona_core/gpt6_optimization_v2/tools/test_openai_formal_binding.py` | ADD | Independent neutral fixtures and minimum offline coverage; network-denied child worker harness; mutation, crash/restart and idempotency tests. One test module may contain fixture bytes and temporary harness code; no benchmark answer fixture or new production helper. |

原七路径逐项审查结果：足够作为此有限实现的设计边界；新增 proposed scope 路径为 0。这是接口级判断，尚未经实现测试。provider_http_worker.py 与 provider_transport.py 的 adapter_contract 委派、private wire capture 和生命周期上限可复用；OpenAI SSE 差异由新增 adapter 处理，不改共享 DeepSeek parser。

semantic_binding.py::provider_identity 对除了 allocation/slots/self-binding 的 scope 字段进行摘要；将 schedule_identity、dataset_identity、rubric_identity 显式放到 scope 后，它们也受到 provider identity 绑定。formal_acceptance.py、accepted_output.py、chat.py、admission.py 全部只读，复用其双门与记录语义。

每一变更的共同风险：分支误入旧 scope、模型或价目漂移、回执伪完成、费用低估。每条 diff 必须指向上表职责和 OFFLINE_TEST_PLAN 的反例。若实现证明不够，停止并逐项提交 exact path、七路径无法完成的理由、合同条款、非架构扩展理由、风险、回滚；不得先改后补单。

回滚：离线实现开始前保存五个现有文件的精确字节并校验本清单基线；保留两新增文件及测试结果的审计副本。未启用新批次前可仅恢复这五文件并从活动源码成员中移除两新增文件，重新验证旧182身份。已有新scope会话须隔离，不降级为旧scope、不恢复付费抽样、不删除证据。任何历史数据库、旧freeze、raw/finding/verdict不回滚。

允许另写的非源码产物仅是本治理包、work内离线临时文件和之后具名的新implementation evidence目录。它们不扩大上述七路径。未来source manifest/acceptance config/test receipts是生成工件，不是假称新增源码路径。
