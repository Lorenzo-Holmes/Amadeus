# Amadeus Persona Core Runtime — R043

状态：`OPERATIONAL_PERSONA_CORE_COMPLETE`

## Authority

- Release: `RUNTIME_RELEASE_R043.json`
- Genesis: `genesis/GENESIS_SNAPSHOT_R035.json`
- Frozen authority copies: `genesis/frozen/`
- Recovery checkpoint: `CHECKPOINT_GENESIS_R043.json`
- Runtime integrity: `RUNTIME_META.json`
- Runtime schema migrations: `RUNTIME_SCHEMA_MIGRATIONS.jsonl`

不要直接编辑 `genesis/`、`genesis/frozen/`、`EXPERIENCE_LEDGER.jsonl` 或状态JSON来模拟成长。

## Runtime write path

所有产品经历必须由 `runtime_core.PersonaRuntime.admit_event()` 经 `DETERMINISTIC_RUNTIME_POLICY` 准入。

普通模型输出没有状态写权限。模型不能直接：

- 改 Source / Genesis / Persona；
- 写 autobiographical memory；
- 提升关系；
- 授予身体或工具能力；
- 创建产品经历。

关系按 entity 隔离。共同兴趣只增加 familiarity，不自动生成 trust；真实的已准入合作/履约等事件才能按确定性规则更新 trust/respect。

## Model prompt path

`runtime_prompt.build_messages()`读取冻结Persona和只读Runtime状态，只加载当前情境匹配的最少Persona条款。

长历史只把该entity的总事件数与最近8条事件放入prompt；完整历史仍保存在append-only Experience Ledger及确定性state中。

Memory/Identity问题会读取Genesis准入边界：

- `RC-R005-001`：唯一安装的来源第一人称回忆；
- Maho住处/“一直邋遢”、论坛反应习惯、Amadeus账号第一人称来源：继续HOLD；
- Human Kurisu约2008论坛ID史：source fact only；
- 来源cutoff：2010-03；精确日UNKNOWN；
- 冈部2010夏季共同经历：不得作为已编码第一人称来源记忆。

## Checkpoint / recovery

使用 `runtime_checkpoint.create_checkpoint()`生成校验点。Checkpoint不删除或压缩原Ledger。

`PersonaRuntime`加载时会验证：

- Experience Ledger sequence；
- previous-event hash链；
- event hash；
- Self/Affect/Relationship/Decision状态文件hash；
- `RUNTIME_META`的tail与next sequence。

检测到篡改时，不要手工“修平”hash；从已知健康checkpoint/Genesis创建新的受治理恢复或migration revision。

## Current production state

R043发布时正式production Runtime只有Genesis Event，没有真实产品用户关系和后Genesis Experience。历史测试成长均在sandbox clone中执行，没有写入正式产品历史。

## Remaining post-release validation

以下没有被伪报为完成：

- independent blind acceptance；
- true natural-day longitudinal runtime validation。

它们属于发布后验证，不是当前Persona Core构建缺件。
