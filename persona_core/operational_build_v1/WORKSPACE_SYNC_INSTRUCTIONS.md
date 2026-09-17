# 将本包同步到项目工作区

此步骤用于连接恢复后的助手执行。不要让用户逐个手工修改文件。

## 1. 检查现状

确认工具确实指向`C:\Users\skr\Documents\Codex\Amadeus-Project.staging`，读取根目录及相关下级AGENTS。检查是否已存在`persona_core/operational_build_v1/`、R044以后目录、未完成的模型请求或新版任务状态。

若出现新进展，先合并恢复。不得用本包所有任务未开始的初始状态覆盖已经验证的成果。

## 2. 保全旧入口

在变更根文件之前，将下列文件按原始字节保存至唯一、不覆盖的项目内备份目录，并记录路径/大小/哈希：

`AGENTS.md`、`AMADEUS_PERSONA_CORE_MASTER_GOAL.md`、`PERSONA_CORE_PROGRESS.md`、`PERSONA_CORE_CONTINUATION_PROTOCOL.md`、`PERSONA_CORE_DECISION_LOG.md`。

本步骤只是入口文档备份，不代替R044-01对Runtime和评测基线的完整保全。

## 3. 安装文档

将本包内全部文件导入`persona_core/operational_build_v1/`。通过DevSpace可用写入工具操作；源码/文本修改遵循其apply_patch约定。不要通过模型API或未经批准的公网服务传输项目文件。

逐文件核对MANIFEST中的哈希。MANIFEST本身不自哈希；它是交付快照，不是未来每次状态更新都必须保持不变的锁。

## 4. 更新恢复入口

`WORKSPACE_ENTRYPOINT_PATCH.patch`基于本轮及最近会话读取的旧文档生成，**尚未在Windows验证或应用**。先检查每个上下文仍匹配。若文件已变，按相同意图生成最小补丁，保留更新内容和历史，不强行覆盖整份文件。

补丁意图：

- AGENTS增加活动阶段入口，取消自动停在旧R043完成标记。
- Master Goal保留长期原则，将R043归为历史发布，当前目标转向可用性与可靠性。
- Progress将NEXT_ACTION改为读取本包任务状态并执行R044-01；历史R043完成记录保留为历史，不改冻结包。
- Continuation Protocol增补本阶段依赖执行、真实证据与平台边界要求。
- Decision Log增加具名裁决，说明为何重开验收；若DEC-047已被使用，选择下一空闲编号，不能覆盖。

不得更改`persona_core/runtime/genesis/`、生产Ledger、原始响应或R043发布清单。此同步只是文档入口变更。

## 5. 验证同步与下一步

重新读取根目录入口，确认只存在一个活动NEXT_ACTION；执行：

```text
python -B persona_core/operational_build_v1/tools/validate_plan.py --root persona_core/operational_build_v1
```

确认本包和入口实际落盘后，在TASK_STATE更新`workspace_sync_status=VERIFIED`及真实时间/备份引用；追加CHANGELOG。维护后的文件可以产生新文档清单版本，不篡改原下载清单来假装未变化。

更新根Progress的恢复点。随后直接执行第一个尚未完成且依赖满足的任务，初始为R044-01；不要把“文档同步完成”计作基线保全或语义复核完成。

## 6. 工具仍不可用时

保留本包原样和尝试记录，明确本机未同步。不要声明已更新Progress，也不要通过无关工具越过实际项目访问限制。
