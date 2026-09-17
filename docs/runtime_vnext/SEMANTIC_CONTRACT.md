# Claim / Evidence 离线契约参考 v1

实现：`tools/runtime_vnext/semantic_contract.py`。测试：`tests/runtime_vnext/test_semantic_contract.py`。

## 1. 地位与非目标

这是生产接入前的可执行契约参考，不是第二个 Core、自然语言解析器、事实裁判或权限服务。模块只使用 Python 标准库，无 runtime 导入、网络、凭据、数据库、文件写入或 provider 调用。实际 G6 canonical 缺失，因此没有接入 `AdmissionController`、`RuntimeStore` 或现有 expression 管线。

`BOUND` **只表示传入的原文、哈希、跨度、作用域与外层 speaker 能对上**。它不表示 AST 正确解释了原文，也不表示命题为真、前提成立、说话者有领域 authority 或动作获得授权。`EvidenceRecord` 是普通只读测试输入，不是宿主签发的证据 token；不能将它从模型 JSON 构造后当成可信 receipt。

## 2. 完整 Claim 形状

顶层必需字段且不接受未知字段：

```text
schema_version = amadeus.claim-reference.v1
claim_id
speaker = {entity_id, resolution: RESOLVED | UNRESOLVED}
scope = {principal_id, entity_id, mode}
phase = {kind, reference, valid_from, valid_until}
proposition = Expression
evidence = [{evidence_id, sha256, start, end, quote}, ...]
authority = {asserted_grant_id}
```

`scope.entity_id` 是关系/记录可见范围；`speaker.entity_id` 是外层言说归属；命题的主体位于 `atom.arguments`。三者不能互相替代。speaker 未解决时必须显式 `UNRESOLVED` 且 ID 为 null，而不是自动取当前用户或 Amadeus。

mode 复用当前源码的 `PRODUCT_RUNTIME`、`CHARACTER_SIMULATION`、`SOURCE_AUDIT` 名称。传入这些字符串不等于认证身份；生产必须由既有 handle 生成可信作用域。

phase.kind 是 CURRENT_RUNTIME、HISTORICAL_RUNTIME、SOURCE、PLANNED 或 UNKNOWN。已知阶段必须提供明确 reference；UNKNOWN 的 reference 为 null。有效区间采用带时区时间、左闭右开语义；null 表示该边界未提供，不证明无限有效或当前有效。参考模块只验证格式与区间顺序，不用系统时钟推断适用性。观察发生与记录时间留在生产 HostEnvelope，不能从 phase 自动补造。

`authority.asserted_grant_id` 只是内容中的授权声称/引用。参考实现永不返回 grants_authority=true。生产授权必须从可信宿主边界独立解析，并核验 issuer、principal、resource、action、environment、用途、有效期、撤销与审批；asserted ID 不能自行成为 grant。

## 3. Expression：条件与否定必须有作用域

封闭的带标签结构：

```text
atom(predicate, arguments[])
not(operand)
and(operands[]) / or(operands[])
if(condition, consequence)
said(speaker, body)
attitude(actor, kind, body)
during(phase, body)
```

JSON 用 `op` 标签；例如 `{"op":"not","operand":...}`、`{"op":"if","condition":...,"consequence":...}`。attitude.kind 为 KNOWS、BELIEVES、INTENDS、WISHES 或 QUESTIONS。标识符与 predicate 不设自然语言关键词清单；测试编号和业务场景不参与解析。

这能保留而不混淆：

```text
said(A, not(P))       != not(said(A, P))
not(KNOWS(A, P))      != KNOWS(A, not(P))
if(C, P)             != P
not(if(C, P))        != if(C, not(P))
during(HISTORICAL, P) != during(CURRENT, P)
INTENDS(A, P)         != P
```

这些不等式指表示必须可区分，不是参考模块实现了完整逻辑求值。尤其是 `if` 没有默认求值为 material implication；自然语言条件、反事实和必要/充分条件仍须由真实解释器/审查协议消歧。不得因为 JSON 结构合法就删除条件、消去否定、把愿望变成能力或执行。

嵌套阶段由 `during` 明确表达。未知、替代解释和不确定作用域在生产解释层必须保留；本 v1 不实现指代消解、量词、完整时间逻辑、自由文本的同义规范化或多候选解释排名。无法无损表达的输入应留在原始观察/未决解释，不塞进 atom 字符串后当已解析事实。

## 4. 原文绑定与输出

`sha256` 对完整 EvidenceRecord.text 的 UTF-8 字节计算，不对规范化摘要计算。`start/end` 是 Python Unicode code point 索引，区间 `[start, end)`；不是字节、UTF-16 code unit 或可见字素索引。终端/JS 适配器必须显式转换，禁止 NFC/NFKC 等静默改写后继续使用旧 offsets/hash。

同一个证据可以引用多个不同跨度；完全重复的跨度拒绝。候选的 principal/entity/mode 必须与证据一致；缺失记录不能自动联网补取；哈希、引用、说话者或 scope 冲突返回 REJECT。缺失证据、未决 speaker/顶层 phase 或已撤销证据返回 HOLD。多证据中 REJECT 优先于 HOLD，不能用一条缺失记录遮住另一条已知冲突。

`check_bindings` 的 BOUND/HOLD/REJECT 属于**离线绑定检查命名空间**，不是项目的持久准入枚举。所有结果均 `proves_proposition=false`、`grants_authority=false`。外部事实核验和解释核验完全未在此实现。

`project_claim` 验证 target scope 完全匹配，返回完整深拷贝。不做内容截断，不省略条件/否定/authority assertion。它不调用 check_bindings，也不暗示证据通过；调用方不能把投影存在当作准入成功。生产必须以已有准入与有效性结果限制可投影记录。

`fingerprint` 是带版本的表示身份哈希，不是语义等价判定，不替换 RuntimeStore 的既有 semantic key。字段 key 排序稳定，列表顺序保留；改写同义词可能产生不同哈希。更换 claim_id 也改变表示身份，不能拿它防御重提交外部动作。

## 5. 输入边界与版本兼容

封闭字段集合、明确枚举、整数 span（拒绝 bool）、带时区正区间、UTF-8 合法性、重复 JSON key 拒绝、非有限 JSON 数值拒绝。表达式深度上限 24、节点上限 256；编码后 Claim 上限 65536 字节；至多 16 个 evidence spans，每段至多 8000 code points。限制是参考实现的资源界限，不是人物心理或知识边界。

旧记录缺失必需语义字段时不自动补默认值。参考模块拒绝未知版本；生产迁移须保留旧原文/哈希，并以显式新 interpretation 版本表达补充解释，不能重写旧 ledger。

## 6. 生产接入的必要后续工作

取得真实 G6 canonical 后，首先确认现有 Claim/Evidence 类型和抽取器；必要时将本参考的结构/不变量迁入既有模块，而不是保留两套生产实现。然后绑定 InterpretationReview 与原始来源、闭合 effect-specific admission、接通无损投影和派生失效机制。

所有写入继续由现有 RuntimeStore 与宿主准入控制。重新解释不是重新发送 provider；UNKNOWN 请求原始状态必须保留。R8 原始失败、自然语言留出集、重启/检索/摘要路径、authority 撤销与全兼容回归均须单独通过。参考测试通过不使任何 G6 或产品状态转为 PASS。
