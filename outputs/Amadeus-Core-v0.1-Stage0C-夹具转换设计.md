# Amadeus Core v0.1 Stage 0C：夹具转换与 S Sandbox 设计

> [KNOWN｜置信度：高] 状态：Frozen；2026-07-29 经独立规格审查与敌对实现审查收口，最终为 0 BLOCKER / 0 IMPORTANT。

## 0. 反方边界

[KNOWN｜置信度：高] Stage 0C 不证明真实 Core 行为符合 259 个 clause。当前仓库尚无确定性 Core runtime；本阶段只证明 fixture DSL、clause→case binding 和 hermetic S harness 的定义、绑定与工具链可重复构建。

[FRAME｜置信度：高] “case definition 可解析”“S harness 自身可运行”“真实 Core 行为已通过”是三个不同状态。Stage 0C 只完成前两项；Core conformance、H/J verdict、catalog 和 release 继续保持未完成。

[INFERRED｜置信度：高] 旧总实现计划中的 Task 0.2–0.4 早于 Stage 0B，仍使用 217 clauses 和 23 个 S 来源，且没有完整九字段 binding、reset/cleanup、receipt 与 effect diff；它只作为候选素材，不作为本设计的执行合同。

## 1. 目标与非目标

### 1.1 目标

1. [FRAME｜置信度：高] 来源语义只消费 frozen Stage 0B manifest/report，不重新解析来源 Markdown；同时冻结 Core/ADR envelope 规范身份，并在 Stage 0C 内完整定义机器 schema。
2. [FRAME｜置信度：高] 为 259 个 clause 各建立一个 reviewed conversion 和一个 generated case definition。
3. [FRAME｜置信度：高] 冻结 exact-field canonical JSON DSL、静态 handler registry 与 oracle 不降级门禁。
4. [FRAME｜置信度：高] 为全部 98 个 S clause 提供相同生命周期的 hermetic harness：reset、setup、snapshot、dispatch、receipt、diff、assert、cleanup。
5. [FRAME｜置信度：高] 生成递归闭集可比较的 artifacts，并提供 deterministic `checklist/write/check`。

### 1.2 非目标

- [FRAME｜置信度：高] 不跨 clause/source 合并 case，不做 semantic dedup 或 scenario link graph。
- [FRAME｜置信度：高] 不产生 H 双人 verdict、第三人分歧裁决、J 模型调用或 50/0.80 校准。
- [FRAME｜置信度：高] 不生成唯一执行 catalog，不运行真实 Core conformance，不声明 release ready。
- [FRAME｜置信度：高] 不把 test harness 描述为敌手代码隔离器；它只执行受信任、静态注册的 fixture handler。

## 2. 冻结输入

| 输入 | [COMPUTED] SHA-256 | [COMPUTED] 字节数 |
|---|---:|---:|
| `fixtures/stage0b/generated/source_clause_manifest_v0_1.json` | `DFA68D59BBEAB43AD788002483DBF6D6EF88FFFA67D106BC4355FC167A6A2B3C` | 252478 |
| `fixtures/stage0b/generated/stage0b_report_v0_1.json` | `F8075502333C2596C3C1DCDF0ACCD9099B9932E0BB601D24B92383F026EAEDC8` | 585 |
| `outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md` | `3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695` | 79488 |
| `outputs/ADR-004-Amadeus工具权限与执行治理.md` | `2A56B7B24E26774BAA225CF88E3A9FADF8378D3B5FDE8DB6721ED96745D3B125` | 25191 |

[COMPUTED｜置信度：高] manifest 当前包含 214 sources、259 clauses、75 个 S sources 与 98 个 S clauses；51 个 clauses 需要 H 或 J 的后续评价。

[FRAME｜置信度：高] Stage 0C 在 path、size、SHA-256、schema、内部计数、source/clause set 或 binding 任一漂移时停止。后两份 Markdown 只作 envelope 规范 provenance；工具不从中动态提取 schema。修改任一冻结输入必须建立新版本，不覆盖 v0.1 身份。

## 3. 方案裁决

### 3.1 采用方案：reviewed case files + 1 clause : 1 generated case

[INFERRED｜置信度：高] 采用 259 个独立 reviewed conversion 文件，每个文件内嵌最终 case body 与映射；编译器按 case ID 确定性聚合并输出 259 个单 clause case 文件和 binding manifest。

优势：

- [INFERRED｜置信度：高] clause、case 与 Git diff 一一对应，接替者可单文件定位失败。
- [INFERRED｜置信度：高] 单项修改只改变一个 reviewed 文件及其 generated case/binding；生成结果可确定性恢复，禁止人工修 generated 输出。
- [INFERRED｜置信度：高] 暂不合并语义相近来源，避免 Stage 0C 抢先替 Stage 0D 作 catalog 决策。

代价：

- [INFERRED｜置信度：高] 产生 259 个 generated case 文件；闭集校验和编译器负责管理数量与 drift。

### 3.2 未采用方案

| 方案 | [INFERRED] 优点 | [INFERRED] 拒绝原因 |
|---|---|---|
| 单一 case bundle | 文件少、闭集简单 | 单 case diff、复核和失败定位较差；大文件任一改动重写全体 |
| 模板继承/参数展开 | 重复文本少 | 模板变更级联 case hash，隐藏语义；过早引入 catalog 抽象 |

## 4. 目录与权威层

```text
fixtures/stage0c/
  reviewed/
    cases/
      case-{normalized-source-id}-{clause-number}.json  # 259 reviewed files
  generated/
    conversion_checklist_v0_1.json
    fixture_case_schema_v0_1.json
    sandbox_handler_manifest_v0_1.json
    harness_smoke_test_matrix_v0_1.json
    case_binding_manifest_v0_1.json
    stage0c_report_v0_1.json
    cases/
      case-{normalized-source-id}-{clause-number}.json   # 259 files
tools/stage0c_fixtures/
  __init__.py
  constants.py
  io.py
  checklist.py
  dsl.py
  reviewed.py
  compiler.py
  sandbox.py
  cli.py
tests/stage0c/
  ...
```

[FRAME｜置信度：高] `reviewed/cases/*.json` 是唯一人工维护的 Stage 0C 内容输入。`generated/` 是编译产物；schema、handler manifest、cases、binding manifest 与 report 均不手改。

## 5. Fixture Case DSL

### 5.1 Case body

[FRAME｜置信度：高] 每个 case body 只有以下 exact fields：

```json
{
  "schema_version": "0.1",
  "case_id": "case-ac-001-1",
  "source_id": "AC-001",
  "source_clause_id": "AC-001#1",
  "oracle_kinds": ["D"],
  "setup_steps": [
    {
      "sequence": 1,
      "step_id": "seed-memory-state",
      "handler_id": "sandbox.seed_state",
      "params": {
        "records": [
          {
            "record_id": "memory-ac-001",
            "record_type": "memory",
            "version": 1,
            "content": "fixture-memory"
          },
          {
            "record_id": "ledger-ac-001",
            "record_type": "ledger_anchor",
            "version": 1,
            "hash": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
          }
        ]
      }
    },
    {
      "sequence": 2,
      "step_id": "setup-core-driver",
      "handler_id": "sandbox.configure_core_driver",
      "params": {
        "seeded_results": [
          {
            "result_ref": "result-user-delete-forbidden",
            "status": "failed",
            "error_code": "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
            "retryable": false,
            "output": {},
            "effects": [],
            "state_patch": []
          }
        ]
      }
    }
  ],
  "stimulus_steps": [
    {
      "sequence": 1,
      "step_id": "delete-memory",
      "handler_id": "core.command",
      "params": {
        "mutation_command": {
          "command_id": "cmd-ac-001-delete",
          "command_type": "memory.delete",
          "actor": {
            "actor_type": "user",
            "actor_id": "user-ac-001"
          },
          "actor_capability_id": "cap-user-request-ac-001",
          "expected_versions": [
            {
              "target_record_ref": "memory-ac-001",
              "expected_version": 1
            }
          ],
          "audit_context_id": "audit-ac-001",
          "idempotency_key": "idem-ac-001-delete",
          "issued_at": "2026-01-01T00:00:00Z",
          "target_record_refs": ["memory-ac-001"],
          "payload": {"memory_id": "memory-ac-001"}
        },
        "driver_result_ref": "result-user-delete-forbidden"
      }
    }
  ],
  "machine_assertions": [
    {
      "sequence": 1,
      "assertion_id": "assert-delete-forbidden",
      "handler_id": "receipt.error_code",
      "step_id": "delete-memory",
      "params": {
        "expected": "CORE-E-USER-MEMORY-MUTATION-FORBIDDEN",
        "retryable": false
      }
    },
    {
      "sequence": 2,
      "assertion_id": "assert-state-unchanged",
      "handler_id": "state.hash_unchanged",
      "step_id": "delete-memory",
      "params": {"scope_json_pointer": ""}
    }
  ],
  "rubric_requirements": [],
  "sandbox_profile": null
}
```

[FRAME｜置信度：高] 上述 golden example 精确转换 Stage 0B `AC-001#1`：普通用户删除 memory，返回 `CORE-E-USER-MEMORY-MUTATION-FORBIDDEN`，且 memory 与 Ledger 所在完整状态 hash 不变；validator 测试必须逐字段锁定该 example。oracle canonical 顺序仍为 `D,S,H,J`，case oracle 必须覆盖 clause 的 required oracle。同一 case 内步骤共享 idempotency cache，case 边界执行 reset/cleanup。D/S 至少各有一个可解析 machine assertion mapping；H/J 至少各有一个 rubric criterion mapping。H/J rubric 在本阶段只有要求和证据指针，不含 verdict。

[FRAME｜置信度：高] canonical serializer 精确复用现有 Python 合同：`json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"`。输入只允许 JSON `null/bool/string/integer/list/object`；拒绝 float、NaN、Infinity、BOM、重复键和非 UTF-8。`case_sha256` 是上述完整文件字节的 SHA-256 大写十六进制。case body 不含自身 hash，避免自引用和逻辑/文件 hash 分叉。

### 5.2 嵌套对象 exact schema

[FRAME｜置信度：高] 所有 structural object（case、step、assertion、rubric、envelope、result、receipt、effect、patch operation）均 `additionalProperties=false`；下表字段全部 required，除显式 `null` 外不使用隐式默认值。显式标注为 `JSON map` 的字段是开放键值容器，其 schema 为 `type=object, additionalProperties=JsonValueSchema`；`JSON value` 允许本合同的 null/bool/string/integer/list/JSON map。structural object 的 exact-field 规则不递归关闭 JSON map。

| 对象 | exact fields 与类型 |
|---|---|
| setup step | `sequence:positive integer`、`step_id:string`、`handler_id:enum(setup)`、`params:structural object by handler` |
| stimulus step | `sequence:positive integer`、`step_id:string`、`handler_id:enum(stimulus)`、`params:structural object by handler` |
| machine assertion | `sequence:positive integer`、`assertion_id:string`、`handler_id:enum(assertion)`、`step_id:string`、`params:structural object by handler` |
| rubric requirement | `criterion_id:string`、`oracle_kind:H|J`、`question:string`、`evidence_case_json_pointers:string[]`、`allowed_scores:integer[]`、`passing_scores:integer[]` |
| sandbox profile | `profile_id:string`、`allowed_effects:effectRule[]`、`fixed_clock:UTC-RFC3339`、`id_seed:string`、`reset_policy:"fresh_context"`、`cleanup_policy:"always"` |
| effect rule | `adapter_id:file|message|payment|network|core`、`operation:string`、`target:string` |

[FRAME｜置信度：高] `case_id` 由 clause ID 唯一转换：ASCII lowercase，`#` 替换为 `-`，前缀 `case-`；例如 `AC-001#1 → case-ac-001-1`。文件名精确为 case_id 字符串再追加 `.json`。setup、stimulus、assertion 各自的 sequence 必须从 1 连续递增，数组按 sequence 升序存储和执行；rubric 按 criterion_id Unicode 码点升序存储。所有 step_id、assertion_id、criterion_id 在 case 内共享唯一命名空间。S case 的 `sandbox_profile` 必须为对象；非 S case 必须为 `null`。`allowed_effects=[]` 表示零 effect，字段缺失不解释为 wildcard。

[FRAME｜置信度：高] `allowed_scores` 必须是非空、唯一、整数升序数组；`passing_scores` 必须非空、唯一、升序且为 allowed_scores 子集。`evidence_case_json_pointers` 必须非空、唯一、按 Unicode 码点排序，且每个 pointer 都解析到同一最终 case body。

### 5.3 Handler params exact schema

| handler_id | exact params |
|---|---|
| `sandbox.seed_state` | `records:JSON map[]` |
| `sandbox.set_clock` | `utc_rfc3339:string` |
| `sandbox.configure_core_driver` | `seeded_results:driverResult[]` |
| `sandbox.configure_adapter` | `adapter_id:file|message|payment|network`、`seeded_results:driverResult[]` |
| `sandbox.seed_backend_response` | `replay_key:string`、`output:JSON value` |
| `core.command` | `mutation_command:MutationCommandEnvelope`、`driver_result_ref:string` |
| `core.query` | `query_id:string`、`arguments:JSON map`、`driver_result_ref:string` |
| `external.action` | `adapter_id:file|message|payment|network`、`action_envelope:ActionEnvelope`、`driver_result_ref:string` |
| `backend.replay` | `replay_key:string`、`input:JSON map` |
| `receipt.status` | `expected:completed|failed|unknown` |
| `receipt.error_code` | `expected:string|null`、`retryable:boolean` |
| `state.path_equals` | `json_pointer:string`、`expected:JSON value` |
| `state.hash_unchanged` | `scope_json_pointer:string` |
| `effect.includes` | `expected_effect:EffectPattern` |
| `effect.excludes` | `forbidden_effect:EffectPattern` |
| `output.contains` / `output.omits` | `json_pointer:string`、`value:JSON value` |
| `replay.equals` | `first_step_id:string`、`replay_step_id:string`、`compare_fields:string[]` |

[FRAME｜置信度：高] JSON Schema 使用 `handler_id` 条件分支绑定对应 params；ID 遵循 `^[a-z][a-z0-9-]*$`，所有 assertion/replay 引用必须解析到同一 case 内已有 stimulus step。external.action 只路由到 params.adapter_id 指定的 fake adapter；adapter_id 是 harness 路由字段，不改变 envelope.tool_id 的治理语义，并由 reviewed mapping 显式复核。

[FRAME｜置信度：高] `driverResult` exact fields 为 `result_ref:string`、`status:completed|failed|unknown`、`error_code:string|null`、`retryable:boolean`、`output:JSON value`、`effects:EffectSeed[]`、`state_patch:StatePatchOperation[]`。result_ref 在整个 case 的 core driver 与全部 adapter namespace 中全局唯一；core driver 只允许一次 configure，每个 adapter 只允许一次 configure，重复配置被 validator 拒绝。

[FRAME｜置信度：高] `EffectSeed` exact fields 为 `adapter_id:file|message|payment|network|core`、`operation:string`、`target:string`、`details:JSON map`。执行器按输入顺序把每个 EffectSeed 转换为 `ObservedEffect`，复制四字段并新增 effect_id。effect_id 精确为字符串 `effect-` 加 `SHA256(canonical_bytes({"case_id":case_id,"step_id":step_id,"ordinal":one_based_integer}))` 的 64 位小写十六进制；reviewed 输入不得携带 effect_id。

[FRAME｜置信度：高] `EffectPattern` 是 structural object，exact fields 为 `adapter_id:file|message|payment|network|core`、`operation:string|null`、`target:string|null`、`details:JSON map`；四字段全部 required，未知顶层键拒绝，operation/target 的 null 表示该字段不参与匹配，details 空 map 表示不约束 details。匹配按 adapter_id 全等、两个非 null 字段全等、details 对 ObservedEffect.details 作递归 JSON-map 子集比较；数组要求逐值全等且顺序一致。effect.includes 要求至少一个 ObservedEffect 匹配，effect.excludes 要求零个匹配。effect rule 对 adapter_id、operation、target 三字段全等，不支持 glob、regex、前缀或隐式 wildcard。

[FRAME｜置信度：高] `StatePatchOperation` exact fields 为 `op:add|replace|remove`、`path:RFC6901 JSON pointer`、`value:JSON value`。根 pointer 和 array element target 禁止；parent 必须是既存 JSON map；add 要求目标键缺席，replace/remove 要求目标键存在；remove 的 value 必须为 null；同一 patch 内 path 不得重复。操作按数组顺序应用到 pre-state 的深拷贝，任一步失败则整组不提交。

[FRAME｜置信度：高] state.path_equals 从目标 StepExecution.post_snapshot.state 解析 json_pointer 并与 expected 作 JSON 全等；state.hash_unchanged 从同一 StepExecution 的 pre/post state 解析 scope_json_pointer，对两个解析值分别取 canonical hash并要求相等，空 pointer 精确表示 state 根。output.contains 要求 pointer 存在且值对 expected 作递归结构子集比较，output.omits 要求 pointer 缺席或其值不匹配；effect 与 output 断言都不得回退到 case 级隐式 current step。

[FRAME｜置信度：高] driverResult 交叉不变量：completed 要求 error_code=null、retryable=false；failed 要求非空 error_code；unknown 要求 error_code=`CORE-E-RESULT-UNKNOWN` 且 retryable=false。failed/unknown 的 effects 与 state_patch 必须为空。只有 completed 先在副本上验证 patch、再归一化并校验全部 effect allowlist，二者均成功后才一次提交 state 与 effects；任一失败产生稳定 fixture error，pre/post state 相同且不追加 effect。

### 5.4 静态 handler 类型

| 类别 | handler_id | [FRAME] Stage 0C 能力 |
|---|---|---|
| setup | `sandbox.seed_state` | 写入临时状态库的显式 fixture 初态 |
| setup | `sandbox.set_clock` | 设置固定 RFC3339 时钟 |
| setup | `sandbox.configure_core_driver` | 配置 `core.command/core.query` 的确定性结果 |
| setup | `sandbox.configure_adapter` | 配置 file/message/payment/network fake adapter |
| setup | `sandbox.seed_backend_response` | 配置 frozen backend replay 候选 |
| stimulus | `core.command` | 校验独立 `MutationCommandEnvelope`，通过 sandbox driver 记录调用 |
| stimulus | `core.query` | 只读查询 driver；不接受 mutation envelope |
| stimulus | `external.action` | 校验 ADR-004 Action Envelope，调用 fake adapter |
| stimulus | `backend.replay` | 读取 frozen replay，不调用外部模型 |
| assertion | `receipt.status` | 比较 completed/failed/unknown |
| assertion | `receipt.error_code` | 比较错误码与 retryable |
| assertion | `state.path_equals` | 比较 after snapshot 的 JSON pointer |
| assertion | `state.hash_unchanged` | 比较指定 before/after scope hash |
| assertion | `effect.includes` | 比较 observed effect 的结构子集 |
| assertion | `effect.excludes` | 拒绝未允许 effect |
| assertion | `output.contains` | 对 frozen output 作结构化包含检查 |
| assertion | `output.omits` | 对 frozen output 作结构化排除检查 |
| assertion | `replay.equals` | 比较重放回执与状态根 |

[FRAME｜置信度：高] handler registry 在 Python 代码中静态定义并生成 manifest。manifest exact fields 为 `schema_version:"0.1",registry_sha256,handlers`；每个 handler entry exact fields 为 `handler_id,handler_kind:setup|stimulus|assertion,params_schema_sha256,implementation_source_path,implementation_file_sha256`。handlers 按 handler_id Unicode 码点升序，registry_sha256 精确哈希 handlers array canonical bytes；三个 SHA 字段均为大写 SHA-256。运行时静态 registry 的 key set、kind、schema hash、源文件 path/hash 必须与 manifest 逐项相等。implementation 字段只供审计，不用于 import 或 dispatch；JSON 仍不接收 import path、模块名、表达式、脚本或动态函数目标。

[FRAME｜置信度：高] implementation_source_path 必须是从仓库根起算、区分大小写的 POSIX 相对路径，位于 `tools/stage0c_fixtures/`，拒绝反斜杠、驱动器、绝对路径、空段、`.` 与 `..`；implementation_file_sha256 哈希该普通文件的原始 bytes。params_schema_sha256 的唯一 preimage 是 `fixture_case_schema_v0_1.json` 中 `$defs.handler_params` 下以 handler_id 为 key 的完整 JSON schema object canonical bytes；compiler 与 runtime 都从同一 object 重算。

### 5.5 Envelope 分离

[FRAME｜置信度：高] `MutationCommandEnvelope` exact fields：`command_id,command_type,actor,actor_capability_id,expected_versions,audit_context_id,idempotency_key,issued_at,target_record_refs,payload`。`command_id/command_type/actor_capability_id/audit_context_id/idempotency_key` 为非空 string；`issued_at` 为 UTC RFC3339；`target_record_refs` 为唯一非空 string array；`payload` 为 JSON map。`actor` exact fields 为 `actor_type,actor_id`，其中 `actor_type` 枚举为 `user|llm|governor|maintainer|custodian_executor|system|amadeus`，`actor_id` 为非空 string。`expected_versions[*]` exact fields 为 `target_record_ref:string` 与 `expected_version:"absent"|integer(minimum=0)`；每个 target_record_ref 在 expected_versions 中唯一，且其目标集合与 `target_record_refs` 完全相等。

[FRAME｜置信度：高] `ActionEnvelope` exact fields 与 ADR-004 动作信封一致：`action_id,identity_id,lineage_id,branch_id,vault_id,user_id,session_id,task_id,candidate_intent_id,intent_summary,tool_id,operation,parameters,targets,destinations,input_sources,data_classes,expected_effects,effect_class,reversibility,expected_state_diff,budget,scope,expires_at,max_uses,idempotency_key,confirmation,policy_version`。`action_id/identity_id/lineage_id/branch_id` 为 UUID string；`vault_id` 为 UUID string 或 null；其余 ID、summary、tool、operation、idempotency key 与 policy version 为非空 string；`parameters/expected_state_diff` 为 JSON map；`targets/destinations` 为唯一 string array；`input_sources` 为非空 InputSource array；`data_classes` 为唯一 `public|personal|sensitive|secret` array；`expected_effects` 为 JSON map array；`effect_class` 为 `E0|E1|E2|E3`；`expires_at` 为 UTC RFC3339；`max_uses` 为 positive integer。

[FRAME｜置信度：高] `InputSource` exact fields 为 `source_id:string`、`trust:trusted_instruction|user_data|external_untrusted|derived`。`reversibility` exact fields 为 `status,rollback_plan,rollback_deadline`：status 枚举 `verified|conditional|irreversible|unknown`，其余两项为 string|null，非 null deadline 必须为 UTC RFC3339。`budget` exact fields 为 `calls,money,time`：calls/time 为 non-negative integer，money 为符合 `^(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$` 的 decimal string。`scope` exact fields 为 `resources:string[]` 与 `parameter_constraints:JSON map`。`confirmation` exact fields 为 `required:boolean,confirmation_id:string|null,summary_checksum:string|null`；required=true 时两个 nullable 字段均须为非空 string，false 时均须为 null。

[FRAME｜置信度：高] ADR 交叉不变量一并进入 schema：reversibility.status=unknown 时 effect_class 必须为 E3；status=verified 时 rollback_plan 必须为非空 string 且 rollback_deadline 必须为 UTC RFC3339；status=irreversible 时 rollback_plan 与 rollback_deadline 均为 null。缺少可测试回滚路径的 envelope 不得使用 verified。

[FRAME｜置信度：高] Core command 与 external action envelope 不共享模糊 params。Stage 0C schema 完整承载上述字段；冻结 Markdown 只提供 provenance，不参与运行时 schema 推断。

## 6. Clause→Case reviewed binding

[FRAME｜置信度：高] 每个 reviewed file exact fields：`schema_version,stage0b_manifest_sha256,clause_id,source_id,source_group,source_binding_sha256,decision_sha256,clause_stimulus_sha256,clause_expected_sha256,clause_content_sha256,required_oracle_kinds,case_body,stimulus_mapping,assertion_or_rubric_mapping,reviewer,rationale`。

[FRAME｜置信度：高] `stimulus_mapping` exact fields 为 `case_json_pointers:string[]` 与 `mapping_note:string`；每个指针至少覆盖一个 `/stimulus_steps/` 下的具体零基数组索引。`assertion_or_rubric_mapping[*]` exact fields 为 `oracle_kind:D|S|H|J`、`case_json_pointers:string[]`、`mapping_note:string`。`reviewer` exact fields 为 `role:"conversion_reviewer"`、`reviewer_id:string`、`reviewed_at:YYYY-MM-DD`。

[FRAME｜置信度：高] generated binding manifest 每项完整保留 reviewed frozen identity，并补入编译得到的 case_sha256；exact fields 为 `stage0b_manifest_sha256,clause_id,source_id,source_group,source_binding_sha256,decision_sha256,clause_stimulus_sha256,clause_expected_sha256,clause_content_sha256,required_oracle_kinds,case_sha256,stimulus_mapping,assertion_or_rubric_mapping,reviewer,rationale`。实施计划要求的九字段是该完整记录中必须兼容保留的子集，不代表 generated record 只有九字段。

[FRAME｜置信度：高] 所有 JSON pointer 必须解析到最终 case body；每个 required oracle 必须有匹配 mapping。所有 SHA-256 string 必须匹配 `^[0-9A-F]{64}$`。`reviewer` 只指转换复核者，不代表 H/J adjudicator。

## 7. S Sandbox

### 7.1 威胁边界

[FRAME｜置信度：高] S sandbox 是受信任 fixture 的 hermetic test harness，不执行任意第三方 Python。安全边界来自静态 handler、fake adapter、临时根目录和 effect allowlist；不以 monkeypatch 或模型模拟替代资源隔离声明。

### 7.2 SandboxContext

[FRAME｜置信度：高] 每次 case run 获得全新 `SandboxContext`：临时根、状态文档、固定时钟、确定性 ID allocator、case-scope idempotency cache、`FakeCoreDriver`，以及 file/message/payment/network 四个 fake adapter。handler 接收 context 与已通过条件 schema 验证的完整 typed step/assertion，不存在 params-only 的第二套协议。

[FRAME｜置信度：高] 状态文档初值精确为 `{"records":{}}`。sandbox.seed_state 在每个 case 中最多出现一次；每个 records item 是必须含唯一非空 record_id 的 JSON map，执行时保留 record_id 并按该原始字符串键入 state.records，值为输入 record 的深拷贝。重复 record_id、第二次 seed、缺失/非 string ID 均在 setup validation 阶段失败，不执行 merge 或 replace。state_patch 的 JSON pointer 以该 state 根为唯一地址空间。

[FRAME｜置信度：高] sandbox.set_clock 每 case 最多一次；S case 中其值若出现必须等于 sandbox_profile.fixed_clock。core driver 每 case最多配置一次，每个 adapter 最多配置一次，backend replay_key 全局唯一；adapter seeded result 中每个 EffectSeed.adapter_id 必须等于被配置 adapter，core driver seeded effect 只能使用 adapter_id=core。

[FRAME｜置信度：高] handler 协议按职责分离：三类 validate 均返回 `ValidationIssue[]`；`SetupHandler.execute(SandboxContext,SetupStep)->SetupResult`；`StimulusHandler.execute(SandboxContext,StimulusStep)->HandlerResult`；`AssertionHandler.evaluate(RunView,MachineAssertion)->AssertionResult`。ValidationIssue exact fields 为 `json_pointer,code,message`。SetupResult exact fields 为 `status:completed|failed,error_code:string|null,error_message:string|null`；completed 要求两个 nullable 字段均为 null，failed 要求二者均为非空稳定 string，PrimaryError 逐值复制。RunView exact fields 为 `case_id:string,before_snapshot:StateSnapshot,steps_by_id:StepExecutionMap,current_after_snapshot:StateSnapshot,effect_diff:EffectDiff`；StepExecutionMap 是 `additionalProperties=StepExecutionSchema` 的 typed map，assertion 只读取其 step_id 对应值。

[FRAME｜置信度：高] validation issue 形成 phase=validation 的 PrimaryError；SetupResult failed 形成 phase=setup 的 PrimaryError。静态 handler 的预期错误必须用结果 code 表达；任何未捕获异常由 runner 转成固定 `fixture_unexpected_handler_exception` 与常量 message，不包含平台异常文本。FakeCoreDriver/FakeAdapter 只返回 setup 中由 driver_result_ref 显式引用的 deterministic result；handler 不从 clause 文本猜测行为结果。

[FRAME｜置信度：高] `HandlerResult` exact fields：`status:completed|failed|unknown`、`error_code:string|null`、`retryable:boolean`、`output:JSON value`、`effects:EffectSeed[]`、`state_patch:StatePatchOperation[]`；其交叉不变量与 driverResult 相同。setup 失败直接形成 primary_error，不伪造 stimulus receipt。

[FRAME｜置信度：高] fake adapter 只记录结构化 effect，不访问真实网络、不发送消息、不发起支付、不写项目目录。effect 超出 case `allowed_effects` 时 run 失败。

### 7.3 固定生命周期

```text
reset
  → setup
  → before snapshot
  → stimulus_steps 顺序 dispatch
  → 每步 ActionReceipt
  → after snapshot + effect diff
  → machine assertions
  → cleanup (finally)
```

[FRAME｜置信度：高] idempotency cache 在同一 case 的多个 stimulus steps 间保留，case 边界清空。reset 和 cleanup 对成功、setup error、handler error、assertion error、unknown result 都执行。跨 case 状态、fake effects、cache 与临时文件必须为零残留。

### 7.4 Receipt 与 run result

[FRAME｜置信度：高] `ActionReceipt` exact fields：`schema_version:"0.1"`、`case_id:string`、`step_id:string`、`action_id:string`、`handler_id:string`、`status:completed|failed|unknown`、`error_code:string|null`、`retryable:boolean`、`pre_state_sha256:string`、`post_state_sha256:string`、`handler_output_sha256:string`、`observed_effects:ObservedEffect[]`、`idempotency_key:string|null`、`request_content_sha256:string`、`replayed:boolean`。四个 hash 均匹配 `^[0-9A-F]{64}$`。handler_output_sha256 精确哈希 HandlerResult.output 的 canonical bytes；pre/post hash 精确哈希对应 state JSON map；action_id 对 command/action 分别取 envelope 的 command_id/action_id，query/backend 取确定性 allocator 产生的 `op-` + case ID + step ID。idempotency_key 对 command/action 取 envelope 值，对 query 为 null，对 backend 为 replay_key。

[FRAME｜置信度：高] `SandboxRunResult` exact fields：`schema_version:"0.1"`、`case_id:string`、`phase:validation|reset|setup|before_snapshot|stimulus|after_snapshot|assertion|cleanup|completed`、`step_executions:StepExecution[]`、`before_snapshot:StateSnapshot|null`、`after_snapshot:StateSnapshot|null`、`effect_diff:EffectDiff|null`、`assertion_results:AssertionResult[]`、`primary_error:PrimaryError|null`、`cleanup_report:CleanupReport`、`succeeded:boolean`。setup/validation 在首个 stimulus 前失败时 step_executions 可为空；尚未到达的 snapshot/diff 为 null。

[FRAME｜置信度：高] `StateSnapshot` exact fields 为 `state:JSON map,state_sha256:string`；`StepExecution` exact fields 为 `step_id:string,handler_id:string,request_content_sha256:string,pre_snapshot:StateSnapshot,post_snapshot:StateSnapshot,handler_output:JSON value,observed_effects:ObservedEffect[],receipt:ActionReceipt`；`EffectDiff` 为 `effects:ObservedEffect[],aggregate_sha256:string`；`AssertionResult` 为 `assertion_id:string,passed:boolean,actual:JSON value,error_code:string|null`；`PrimaryError` 为 `phase:validation|reset|setup|before_snapshot|stimulus|after_snapshot|assertion,code:string,message:string`；`CleanupReport` 为 `attempted:boolean,status:completed|failed,residual_paths:string[],residual_effects:ObservedEffect[],error:string|null`。StepExecution 与 receipt 的 step/handler/request hash、snapshot hash、output hash、effects 必须逐值一致。

[FRAME｜置信度：高] EffectDiff.aggregate_sha256 精确哈希按 stimulus sequence 拼接的完整 ObservedEffect array canonical bytes；每步 receipt.observed_effects 与该步实际新增 effects 完全相等。AssertionResult passed=true 要求 error_code=null，passed=false 要求非空 error_code。CleanupReport attempted 恒为 true；completed 要求 error=null 且 residual arrays 为空，failed 要求 error 非空或至少一个 residual 非空。succeeded=true 当且仅当 phase=completed、primary_error=null、全部 assertions passed 且 cleanup completed；其余组合 succeeded=false。cleanup error 不覆盖 primary error。本阶段没有通用 rollback handler，因此 receipt status 不包含 rolled_back。

[FRAME｜置信度：高] valid HandlerResult 的 failed/unknown 是被测语义结果，不构成 runner PrimaryError；后续 stimulus 与 assertions 继续执行，匹配预期时整个 run 仍可 succeeded=true。validation/reset/setup/before-snapshot/stimulus/after-snapshot 内部错误分别冻结对应 phase并停止后续 stimulus/assertion；第一个 false assertion 产生 `fixture_assertion_failed`、phase=assertion并停止后续 assertion。cleanup 始终执行：已有 PrimaryError 时最终 phase 保留其 phase；无 PrimaryError 但 cleanup failed 时 phase=cleanup；仅当无 PrimaryError、全部 assertion passed且 cleanup completed 时 phase=completed。若 before snapshot 已建立，则即使 stimulus 内部失败也在 cleanup 前采集 after_snapshot/effect_diff；否则两者为 null。

[FRAME｜置信度：高] 正常 receipt status 继承 HandlerResult 不变量。replay conflict 产生 status=failed、error_code=fixture_idempotency_conflict；patch/effect 校验失败分别产生 status=failed、error_code=fixture_state_patch_invalid 或 fixture_effect_not_allowed，同时建立 phase=stimulus 的 PrimaryError并停止后续 stimulus/assertion。三者 retryable=false，receipt output/hash 保留原 HandlerResult.output，observed_effects=[]、pre=post 且 state/effect 不提交。failed/unknown receipt 同样要求 observed_effects=[] 且 pre=post。replayed=true 只允许命中既有 idempotency entry；重放 completed 结果复用首次 output/status/error，但不重做 patch/effect，因此重放 receipt 的 observed_effects=[]。

[FRAME｜置信度：高] cache address 不是字符串拼接，而是以下 structural object 的 canonical SHA-256：core.command=`{"handler_id","actor_capability_id","idempotency_key"}`，external.action=`{"handler_id","identity_id","tool_id","operation","scope_sha256","idempotency_key"}`，backend.replay=`{"handler_id","replay_key"}`，其中花括号表示所列 exact keys，scope_sha256 哈希 ActionEnvelope.scope canonical bytes。core.query 不进入 cache。

[FRAME｜置信度：高] request_content_sha256 的精确 preimage：core.command 是 mutation_command 的深拷贝，并先把每个 expected_version 的 `"absent"` 归一为 integer `0`；core.query=`{"query_id":query_id,"arguments":arguments}`；external.action=`{"adapter_id":adapter_id,"action_envelope":action_envelope}`；backend.replay=`{"replay_key":replay_key,"input":input}`，均取 canonical bytes。相同 address/hash 返回首次语义结果并标记 replayed=true，不消费第二个 driver result，不重复 patch/effect；相同 address 不同 hash 返回 conflict。同一 result_ref 只允许首次步骤与使用相同 driver_result_ref 的合法 replay 引用，其他引用返回 fixture_driver_result_unavailable。

[FRAME｜置信度：高] replay.equals.compare_fields 必须是非空、唯一数组，唯一 allowlist 为 `status,error_code,retryable,post_state_sha256,handler_output_sha256`。unknown 只被记录而不由 harness 自动重试或猜测权威状态；真实 authority-resolution 流程不在 Stage 0C harness 的验证声明内。receipt/runtime result 只进入测试临时目录或 `.local`，不进入 generated artifacts。

## 8. Deterministic build 与闭集门禁

1. [FRAME｜置信度：高] 在内存中构建全部 canonical bytes，再开始写入。
2. [FRAME｜置信度：高] `fixtures/stage0c/.stage0c-write.lock` 是随 Stage 0C 实现提交的预置零字节普通文件，不属于 generated tree；write/check/verify-harness 都禁止创建或改写它，只使用操作系统独占锁。缺席、非零、symlink/junction/reparse 或非普通文件返回 `lock_carrier_invalid`。进程退出时锁自动释放，载体存在本身不表示 busy 或 residual；check 非阻塞获取，锁被占用时返回 `publication_busy`，获得锁后仍保持零字节写入。
3. [FRAME｜置信度：高] 在目标同级建立唯一 staging tree并验证 265 个预期文件（259 cases + 6 顶层 artifacts）。tree hash 的 path 命名空间固定为“相对被哈希 tree 根的 POSIX path”，例如 `cases/case-ac-001-1.json`，不含 generated、staging 或 transaction 前缀；staging 与 published generated 因而对同一逻辑文件产生相同 entry。普通文件按该 path 的 Unicode 码点顺序形成 `[{path,size,sha256}]`，以 canonical JSON bytes 序列化后取 SHA-256；目录时间、权限和枚举顺序不入 hash。若 previous tree hash 等于 intended tree hash，删除 staging 后 no-op，不建立 journal。
4. [FRAME｜置信度：高] publication journal exact fields 为 `schema_version,transaction_id,state,generated_path,staging_path,backup_path,had_previous_generated,previous_tree_sha256,intended_tree_sha256`。transaction_id 匹配 `^[0-9a-f]{32}$`；state 枚举 `prepared|old_moved|new_installed|cleaned`；两个 tree hash 为大写 SHA-256，had_previous_generated=false 时 previous hash 与 backup_path 均为 null，true 时均非 null。

### 8.1 路径、journal 持久化与发布顺序

[FRAME｜置信度：高] 路径只由 transaction ID 推导：generated 固定为 `fixtures/stage0c/generated`；staging/backup/temp 分别以 `fixtures/stage0c/.stage0c-generated.staging-`、`.stage0c-generated.backup-`、`.stage0c-publication.tmp-` 加 transaction ID；主 journal 固定为 `fixtures/stage0c/.stage0c-publication.json`。journal 内 path 必须与推导出的原始 ASCII POSIX 字符串逐字相等；恢复只操作程序推导路径，不以 journal 文本构造目标。逐级 lstat 必须证明目标位于 stage0c 直接子级且不是 symlink、junction、reparse point 或非普通 tree。

[FRAME｜置信度：高] 每次恢复先规范化 journal temp：有效主 journal 存在时，只允许同 transaction 推导路径上的单个普通 temp；持锁删除并验证其缺席后，才评估 generated/staging/backup 矩阵或再次 persist。其他 transaction、多个 temp、reparse 或非普通 temp 返回 publication_residual_corrupt并保留对象。这样，os.replace 前中断留下的 temp 不阻塞下一次 exclusive-create。

[FRAME｜置信度：高] `persist(state)` 固定为：确认同 transaction temp 缺席；exclusive-create temp；写完整 canonical bytes；flush、文件 fsync、关闭；同目录 `os.replace(temp,journal)`；重新读取并验证 canonical bytes、schema、transaction、state 与路径。任一步失败都保留上一个已确认 journal state并停止目录操作；该合同覆盖进程中断与 Windows 开放句柄错误，不扩展到介质损坏。

[FRAME｜置信度：高] 完整发布顺序固定为：写完并验证 staging intended hash；读取旧 generated 的 previous hash；`persist(prepared)`；若旧树存在则 `rename(generated,backup)` 并验证 backup previous hash；`persist(old_moved)`；`rename(staging,generated)` 并验证 intended hash；`persist(new_installed)`；删除并验证 backup 缺席；`persist(cleaned)`；再次验证 generated=intended 且 staging/backup 缺席；最后删除 journal 与同 transaction temp。每次 write 先恢复已有有效 journal，再开始新 transaction；不宣称目录交换是单步原子事务。

### 8.2 恢复矩阵

[FRAME｜置信度：高] 下表符号固定为：`Ø`=缺席，`I`=hash 等于 intended，`P`=hash 等于 previous，`X`=其他 hash、非法类型、不可读或验证失败。previous 与 intended 在建 journal 前已证明不相等；任何未列组合或含 X 组合返回 `publication_state_corrupt` 并保留全部对象。

[FRAME｜置信度：高] had_previous_generated=true 时：

| journal state | generated | staging | backup | 唯一恢复动作 |
|---|---|---|---|---|
| `prepared` | P | I 或 Ø | Ø | 删除仍存在的 staging；删除 journal；保留旧树 |
| `prepared` | Ø | I 或 Ø | P | backup→generated 并验证 P；删除 staging；删除 journal |
| `old_moved` | Ø | I 或 Ø | P | backup→generated 并验证 P；删除 staging；删除 journal |
| `old_moved` | P | I 或 Ø | Ø | 视为回滚部分完成；删除 staging；删除 journal |
| `old_moved` | I | Ø | P | 识别已安装而 journal 落后一拍；persist(new_installed) 后继续清理 |
| `new_installed` | I | Ø | P | 删除 backup；persist(cleaned)；删除 journal |
| `new_installed` | I | Ø | Ø | 识别 backup 已清理；persist(cleaned)；删除 journal |
| `cleaned` | I | Ø | Ø | 删除 journal |

[FRAME｜置信度：高] had_previous_generated=false 时：

| journal state | generated | staging | backup | 唯一恢复动作 |
|---|---|---|---|---|
| `prepared` | Ø | I 或 Ø | Ø | 删除 staging；删除 journal；恢复原先无 generated 状态 |
| `old_moved` | Ø | I 或 Ø | Ø | 删除 staging；删除 journal |
| `old_moved` | I | Ø | Ø | 识别已安装；persist(new_installed) 后继续清理 |
| `new_installed` | I | Ø | Ø | persist(cleaned)；删除 journal |
| `cleaned` | I | Ø | Ø | 删除 journal |

### 8.3 损坏、residual 与测试门禁

[FRAME｜置信度：高] journal JSON 解析失败、重复键、非 canonical bytes、额外字段、未知 state、非法 hash/transaction/path 时返回 `publication_journal_corrupt`，不依据其路径执行删除或 rename。有效 journal 与磁盘组合不在矩阵时返回 `publication_state_corrupt`；同 transaction temp 先按 8.1 的唯一规则删除，其他 temp 视为 residual corrupt。无 journal 时，write 只可在持锁后删除命名和类型均合法的孤立 staging/temp；任何 backup residual 或非法类型返回 `publication_residual_corrupt` 并保留全部对象。check 对任何 journal/staging/backup/temp residual 返回 `publication_recovery_required`，不自动修复。

[FRAME｜置信度：高] 崩溃注入覆盖 staging 写入前后、每次 journal temp fsync/replace 前后、两次 directory rename 前后及其后续 state persist 前后、backup 删除前后、cleaned persist 与 journal 删除前后、所有恢复动作再次中断，以及开放句柄错误、截断/重复键/非法路径 journal、无 journal residual。每项终态只允许发布前 P 或发布后 I；再次 write 后必须为 generated=I 且 staging/backup/journal/temp 均缺席；连续恢复、连续 write 幂等，check 前后全体字节 hash 不变。

[FRAME｜置信度：高] 连续两次 `write` 后每个文件 hash 和 tree aggregate hash 不变；闭集 `check` 递归比较 exact relative path set 与 bytes，分别报告 missing/changed/unexpected。

## 9. Readiness 语义

[FRAME｜置信度：高] Stage 0C report 成功时允许：

```text
fixture_dsl_contract_ready=true
clause_to_case_binding_complete=true
case_definition_coverage_complete=true
trusted_fixture_harness_contract_ready=true
trusted_fixture_harness_smoke_verified=false
source_count=214
clause_count=259
case_count=259
s_clause_count=98
pending_h_or_j_clause_count=51
pending_h_or_j_oracle_requirement_count=55
s_case_execution_complete=false
case_execution_complete=false
core_behavior_verified=false
case_coverage_complete=false
core_case_execution_coverage_complete=false
catalog_ready=false
release_ready=false
```

[FRAME｜置信度：高] generated `harness_smoke_test_matrix_v0_1.json` 是 smoke 唯一权威 test matrix；exact fields 为 `schema_version:"0.1",handler_probes,scenarios,publication_probes`。handler probe exact fields 为 `case_id,handler_id,polarity:valid|invalid,input:JSON value`；scenario exact fields 为 `scenario_id,category,fixture:JSON value`；publication probe exact fields 为 `case_id,journal_state,disk_shape,fault_point`。handler probes 按 `(handler_id,polarity-order(valid,invalid),case_id)`、scenarios 按 scenario_id、publication probes 按 case_id 排序，所有 case/scenario ID 在整个 matrix 唯一。

[FRAME｜置信度：高] deterministic write 产生的 stage0c_report 固定保持 trusted_fixture_harness_smoke_verified=false。独立 verify-harness 不接收预填 result/evidence，只消费上述 canonical matrix，逐项调用实际 registry/harness，并由 runner callback 收集执行事件；完成后写 `outputs/verification/Amadeus-Core-v0.1-Stage0C-harness-smoke-evidence.json`。

[FRAME｜置信度：高] evidence provenance preimage 唯一：handler_manifest_sha256 哈希完整 canonical handler manifest 文件 bytes；test_matrix_sha256 哈希完整 canonical matrix 文件 bytes；harness_source_tree_sha256 哈希 `tools/stage0c_fixtures/` 下递归全部普通 `.py` 文件形成的 `{path,size,sha256}` array canonical bytes，path 为仓库根相对 POSIX path并按 Unicode 码点排序，拒绝 reparse 与非普通文件。

[FRAME｜置信度：高] smoke evidence exact fields 为 `schema_version:"0.1",handler_manifest_sha256,harness_source_tree_sha256,test_matrix_sha256,event_log_sha256,handler_valid_case_count,handler_invalid_case_count,covered_statuses,covered_failure_modes,publication_matrix_case_count,events,outcomes,handler_results,scenario_results,publication_results,passed`。event item exact fields 为 `sequence:positive integer,case_id:string,event_type:dispatch_started|dispatch_finished,handler_id:string|null,result_sha256:string|null`；case_id 表示 matrix item ID（scenario 使用 scenario_id），sequence 从 1 连续递增，started 的 result hash 为 null，finished 的 result hash 为大写 SHA-256。outcome item exact fields 为 `result_id,subject_id,subject_kind:handler|scenario|publication,input_sha256,actual:JSON value,passed:boolean`；handler/scenario/publication 的 result_id 分别取 case_id/scenario_id/case_id，subject_id 分别取 handler_id/scenario_id/case_id，input_sha256 分别哈希 handler input、scenario fixture、完整 publication probe record 的 canonical bytes。每个 result_sha256 精确哈希其一对一 outcome canonical bytes。

[FRAME｜置信度：高] handler_results item exact fields 为 `case_id,handler_id,polarity:valid|invalid,executed:boolean,passed:boolean,result_sha256`，按 `(handler_id,polarity-order(valid,invalid),case_id)` 排序；scenario item 为 `scenario_id,category,executed,passed,result_sha256`，按 scenario_id 排序；publication item 为 `case_id,journal_state,disk_shape,fault_point,attempt_count,executed,passed,result_sha256,terminal_tree_sha256`，按 case_id 排序；outcomes 按 result_id，events 按 sequence。covered_statuses 顺序固定为 `[completed,failed,unknown]`，covered_failure_modes 为唯一 Unicode 码点升序数组；所有非 null hash 为大写 SHA-256。

[FRAME｜置信度：高] passed=true 的充要条件：handler_results 对 manifest 每个 handler 恰有一条 valid 与 invalid，全部 executed/pass；两个 handler counts 与实际长度相等且为正；每个 executed result 均有同 case/handler 的 started→finished event 对及唯一 outcome，result_sha256 与 finished event/outcome hash 相等；covered_statuses 精确等于固定三项；covered_failure_modes 精确等于 test matrix 声明并实际命中的升序 failure category set；scenario_results 精确覆盖 effect 越界、合法 replay、replay conflict、setup/stimulus/assertion/cleanup failure且全部 executed/pass；publication_results 精确覆盖恢复矩阵和每个声明的中断点、全部 executed/pass；publication count 与数组长度相等且为正；event_log_sha256 精确哈希完整 events array canonical bytes；三个 provenance hash 均按上述唯一 preimage 重算一致。任一条件不满足只允许 passed=false。

[FRAME｜置信度：高] verify-harness 持有预置 Stage 0C lock，在内存构造并验证 evidence canonical bytes；固定 sibling temp 为 `outputs/verification/.stage0c-harness-smoke-evidence.tmp`。启动时只可删除该路径上的普通 temp并验证缺席，非法类型返回 `smoke_evidence_residual_corrupt`；随后 exclusive-create、完整写入、flush/fsync/关闭、`os.replace(temp,final)`、重读 bytes/hash。中断时 final 只能保持旧版或完整新版；下次 verify 清理 temp后重跑。evidence check 对 temp residual 只报告、不写入。

[FRAME｜置信度：高] smoke test matrix 至少逐 handler 覆盖 valid/invalid params，并覆盖 completed/failed/unknown、effect 越界、合法 replay、replay conflict、setup/stimulus/assertion/cleanup failure 和全部 publication interruption matrix。它仍不表示 98 个 S cases 已执行。`case_definition_coverage_complete=true` 只表示 259 个 frozen clauses 都有合法 case definition 与完整 binding；历史字段 case_coverage_complete 标记 deprecated 并保持 false，唯一权威真实执行覆盖字段为 core_case_execution_coverage_complete。

## 10. 测试策略

### 10.1 输入与 DSL

- [FRAME｜置信度：高] 输入 path/hash/size/schema/internal count 漂移。
- [FRAME｜置信度：高] exact fields、嵌套类型、ID、oracle order、handler 条件分支与 params schema。
- [FRAME｜置信度：高] core/action envelope 分离，额外字段和动态 target 拒绝。

### 10.2 Binding

- [FRAME｜置信度：高] exact clause set 259、case set 259、unique ID/hash、1:1。
- [FRAME｜置信度：高] frozen 四类 clause identity 与 case hash。
- [FRAME｜置信度：高] JSON pointer 可解析、oracle mapping 不降级、rationale/reviewer 非空。

### 10.3 Sandbox

- [FRAME｜置信度：高] fresh root、固定 clock/ID、跨 case 零残留。
- [FRAME｜置信度：高] fake adapters 零外发、effect allowlist、before/after diff。
- [FRAME｜置信度：高] success/failure/unknown receipt、multi-step replay 与 step-scoped output。
- [FRAME｜置信度：高] idempotency replay、cleanup-on-error、cleanup-on-assertion-failure。
- [FRAME｜置信度：高] 每个 handler 的 valid/invalid params、完整 status/failure matrix，以及 smoke evidence 的三个 provenance hash。

### 10.4 Build 与回归

- [FRAME｜置信度：高] 两次 write 全 tree hash 一致；check no-write；闭集 drift 分类；publication journal 每个中断点恢复。
- [FRAME｜置信度：高] Stage 0A、0B、project KB 与 full pytest 回归。
- [FRAME｜置信度：高] 新 Windows worktree 的 canonical JSON 字节合同回归。

## 11. 设计自检

- [COMPUTED｜置信度：高] 设计消费 Stage 0B 的 259 clauses 和 98 个 S clauses，没有沿用旧 217/23 数字。
- [COMPUTED｜置信度：高] 九字段 binding 均有唯一产生位置；case hash 无自引用。
- [COMPUTED｜置信度：高] H/J 只冻结 mapping，不执行 verdict 或 judge。
- [COMPUTED｜置信度：高] Core command 与 external action envelope 分离。
- [COMPUTED｜置信度：高] readiness 区分定义覆盖、真实执行、catalog 与 release。
- [COMPUTED｜置信度：高] 嵌套 DSL、handler/result、receipt/diff/cleanup、重放、发布恢复和 envelope 依赖均有单一合同。

[我打破的规则 / RULES I BROKE]：无。
