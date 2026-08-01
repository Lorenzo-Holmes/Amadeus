# Amadeus 路线 B M0–M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` for this plan. Route B deliberately uses one batch author and one batch reviewer instead of a fresh implementation/review pair for every case. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [FRAME] 将路线 B 的批准设计正式纳入仓库，并在保留 B01 ordinals 1–10 字节的前提下，以整批方式完成 ordinals 11–20、批次复核、双提交审计和一次全量回归。

**Architecture:** [FRAME] M0 通过新增 ADR、设计和本计划建立路线覆盖层，旧 Frozen Stage 0C 计划保持原字节；README 与开发知识库明确“完成 B01 后暂停 B02–B13，转入真实 Core 纵向闭环”。M1 继续使用现有 Stage 0C reviewed DSL、冻结 clause manifest、严格 validator 和 Data commit→Audit commit 证明链，但取消逐案例代理等待与重复全量回归。

**Tech Stack:** [KNOWN] Python 3.12、pytest、标准库 `json/hashlib/pathlib/subprocess`、PowerShell、Git、现有 `tools.stage0c_fixtures` 与 `tools.project_kb`。

---

## 0. 执行边界

[KNOWN｜置信度：高] 工作目录：

```text
D:\amadues bot\Amadeus\.worktrees\stage0c-fixture-conversion
```

[KNOWN｜置信度：高] 执行起点：

```text
branch: codex/stage0c-fixture-conversion
HEAD: 0a99c2d7ba9ca96018ba9617457f011ab0c6f2bf
B01 reviewed cases present: 10
next clause: AC-009#1
```

[FRAME｜置信度：高] 本计划只完成 M0 和 M1。B01 两个提交完成后，B02–B13、Stage 0D 与旧计划后续任务保持暂停；下一份计划从 M2 的 Core 骨架开始。

[FRAME｜置信度：高] 本计划禁止修改以下 Frozen 文件：

```text
outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md
outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md
fixtures/stage0b/generated/source_clause_manifest_v0_1.json
fixtures/stage0c/generated/conversion_checklist_v0_1.json
```

## 1. 文件职责

### M0 新增或修改

| 路径 | 操作 | 单一职责 |
|---|---|---|
| `outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md` | Create | 路线 B 的需求、架构、里程碑和 Sentinel 定稿 |
| `outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md` | Create | 对旧 Stage 0C 顺序的正式覆盖裁决 |
| `outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md` | Create | 本轮唯一执行合同 |
| `README.md` | Modify | 当前状态、权威阅读顺序和下一严格顺序 |
| `knowledge/data_structure.md` | Modify | 开发知识库恢复入口 |
| `knowledge/manifest.json` | Modify | 三份新文档和两个导航文件的 SHA-256 allowlist |
| `tests/project_kb/test_current_repository.py` | Modify | 37 文档闭包和路线 B 权威入口测试 |

### M1 新增或修改

| 路径 | 操作 | 单一职责 |
|---|---|---|
| `fixtures/stage0c/reviewed/cases/case-ac-009-1.json` … `case-ac-018-1.json` | Create | B01 后十个 reviewed clause→case 映射 |
| `tests/stage0c/reviewed_batches/test_batch_B01.py` | Preserve | B01 20 行有序闭包；起点字节保持 |
| `outputs/verification/stage0c-reviewed-batches/B01.json` | Create after Data commit | 逐 clause 作者、复核者和 Data commit 证明 |
| `tests/stage0c/reviewed_batches/test_audit_B01.py` | Create after Data commit | 验证审计记录、提交可达性、精确 path set 与提交字节 |
| `work/validate_b01_author_drafts.py` | Temporary | 两个五案例作者态批量检查，审计提交前删除 |
| `work/build_b01_audit_record.py` | Temporary | 从 Data commit 和 reviewed cases 生成规范审计记录，生成后删除 |

## 2. Task 1：验证并锁定当前检查点

**Files:**
- Read: repository Git metadata
- Read: `tests/stage0c/reviewed_batches/test_batch_B01.py`
- Read: `fixtures/stage0c/reviewed/cases/case-ac-001-1.json` … `case-ac-008-3.json`

- [ ] **Step 1: 核对分支、HEAD、上游与未跟踪集合**

Run:

```powershell
$repo = 'D:\amadues bot\Amadeus\.worktrees\stage0c-fixture-conversion'
git -c safe.directory='D:/amadues bot/Amadeus/.worktrees/stage0c-fixture-conversion' -C $repo branch --show-current
git -c safe.directory='D:/amadues bot/Amadeus/.worktrees/stage0c-fixture-conversion' -C $repo rev-parse HEAD
git -c safe.directory='D:/amadues bot/Amadeus/.worktrees/stage0c-fixture-conversion' -C $repo status --short --branch
git -c safe.directory='D:/amadues bot/Amadeus/.worktrees/stage0c-fixture-conversion' -C $repo ls-files --others --exclude-standard
```

Expected:

```text
codex/stage0c-fixture-conversion
0a99c2d7ba9ca96018ba9617457f011ab0c6f2bf
```

[KNOWN｜置信度：高] 未跟踪集合必须恰为 B01 批次测试和以下十个 case；出现其他路径时先分类并停止暂存动作：

```text
tests/stage0c/reviewed_batches/test_batch_B01.py
fixtures/stage0c/reviewed/cases/case-ac-001-1.json
fixtures/stage0c/reviewed/cases/case-ac-002-1.json
fixtures/stage0c/reviewed/cases/case-ac-003-1.json
fixtures/stage0c/reviewed/cases/case-ac-004-1.json
fixtures/stage0c/reviewed/cases/case-ac-005-1.json
fixtures/stage0c/reviewed/cases/case-ac-006-1.json
fixtures/stage0c/reviewed/cases/case-ac-007-1.json
fixtures/stage0c/reviewed/cases/case-ac-008-1.json
fixtures/stage0c/reviewed/cases/case-ac-008-2.json
fixtures/stage0c/reviewed/cases/case-ac-008-3.json
```

- [ ] **Step 2: 核对 1–10 与 batch test 的批准哈希**

Run:

```powershell
$expected = [ordered]@{
  'tests/stage0c/reviewed_batches/test_batch_B01.py' = '625f897802f925c3cf0d1fce28b5650ed4dc0051892d632e21c99e25869c55e6'
  'fixtures/stage0c/reviewed/cases/case-ac-001-1.json' = 'f93895964560a48735027a4121aa3c3c861c9ccf91525ffc00840cfc0b31d3cc'
  'fixtures/stage0c/reviewed/cases/case-ac-002-1.json' = 'f4c2cb6292837d787666c82e2d7b39356287fb75df057da7cd2b3fd367a4fdcc'
  'fixtures/stage0c/reviewed/cases/case-ac-003-1.json' = '41d23239e1bc4e30bf49b198f5520a204bf1a84e304a9884147ac53ba24ee080'
  'fixtures/stage0c/reviewed/cases/case-ac-004-1.json' = 'c9a80d156e114503b8c68ae6cca935d99ebfc22fa9be02e91e543cc79bce9c58'
  'fixtures/stage0c/reviewed/cases/case-ac-005-1.json' = '7ec4c380ae49402a6346dc1a7c99f9f32059805d53fb1f20b18139f07365ced4'
  'fixtures/stage0c/reviewed/cases/case-ac-006-1.json' = 'cd0f42cf37eb9f00aa42a40054611c00ef0eec8207320712905353bdf2b7bc9c'
  'fixtures/stage0c/reviewed/cases/case-ac-007-1.json' = '66e25fb48f4ace8ac0d847cf540c1fdd23dfd16f6d5ba5e08ee492ce686e8f2a'
  'fixtures/stage0c/reviewed/cases/case-ac-008-1.json' = '2f36eb0cf5e3b25d85b2999200888ff181c86b489a217f361364fb83674c8801'
  'fixtures/stage0c/reviewed/cases/case-ac-008-2.json' = 'ba0d29d276c84e8c59c6e3e304d841f8da1511621de058f93ac478a606d1d24f'
  'fixtures/stage0c/reviewed/cases/case-ac-008-3.json' = '6b1ccfc0b1ab8feed591b7cf22192369af58101fbfcbf89884bc577edef3708c'
}
foreach ($row in $expected.GetEnumerator()) {
  $actual = (Get-FileHash -LiteralPath (Join-Path $repo $row.Key) -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -cne $row.Value) { throw "checkpoint hash mismatch: $($row.Key)" }
}
'checkpoint_hashes=11/11'
```

Expected:

```text
checkpoint_hashes=11/11
```

- [ ] **Step 3: 记录当前收集规模，不运行预期失败的全套测试**

Run:

```powershell
Set-Location $repo
.\.venv\Scripts\python.exe -B -m pytest --collect-only -q -p no:cacheprovider | Select-Object -Last 1
```

Expected:

```text
903 tests collected
```

[INFERRED｜置信度：高] 当前缺少 ordinals 11–20，直接执行全套测试只会重复已知 RED；M1 完整后再运行一次全套回归。

## 3. Task 2：为路线 B 仓库接线编写 RED 测试

**Files:**
- Modify: `tests/project_kb/test_current_repository.py`

- [ ] **Step 1: 将知识库总数从 34 提升到 37**

[FRAME｜置信度：高] 修改两处现存总数断言：

```python
assert capsys.readouterr().out.splitlines() == [
    "project_kb_ready=true",
    "indexed_documents=37",
    "raw_paths_indexed=0",
]

assert len(paths) == 37
assert len(set(paths)) == 37
```

[FRAME｜置信度：高] 在 `test_stage0c_plan_and_independent_review_are_indexed` 中将总体断言修改为：

```python
assert len(documents) == 37
assert len(by_id) == 37

route_b_doc_ids = {
    "route-b-design-v1.0",
    "adr-007-route-b-vertical-slice",
    "route-b-m0-m1-plan-v1.0",
}
existing_documents = [
    row
    for row in documents
    if row["doc_id"] not in set(expected) | route_b_doc_ids
]
assert len(existing_documents) == 32
```

[FRAME｜置信度：高] 保留旧 32 文档 projection digest `9e70f62779019c2e7545f7731045d8ed59ee712b18a13608b756c63fc7e22df6`，从而证明路线新增文档没有重写旧权威集合。

[FRAME｜置信度：高] 同一测试中删除现存的两个导航字节常量断言（当前位于约 1095–1102 行，分别钉住 `README.md` 与 `knowledge/data_structure.md` 的旧 SHA-256）。二者属于本次明确修改的文件，继续钉旧值会制造伪失败；不要替换成新常量。保留紧随其后的 manifest 交叉校验：

```python
expected_paths = {
    "README.md",
    "knowledge/data_structure.md",
    "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md",
    "outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md",
}
by_path = {row["path"]: row for row in documents}
assert expected_paths <= set(by_path)
for path in expected_paths:
    raw = (ROOT / path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == by_path[path]["sha256"]
```

[INFERRED｜置信度：高] 这样仍由 manifest 固定新导航字节，同时旧 32 文档 projection 继续排除这两个预期变化的 SHA 字段，旧权威文件的其余元数据和内容哈希仍受约束。

- [ ] **Step 2: 新增路线 B 权威入口测试**

Add at module end:

```python
def test_route_b_documents_are_indexed_and_authoritative() -> None:
    manifest = json.loads(
        (ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8")
    )
    by_id = {row["doc_id"]: row for row in manifest["documents"]}
    expected = {
        "route-b-design-v1.0": {
            "title": "Amadeus 路线 B：需求一致性与真实纵向闭环设计 v1.0",
            "path": "outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md",
            "kind": "design-spec",
            "authority": "canonical",
            "status": "approved",
            "stage": "cross-stage",
            "index": True,
            "sensitivity": "internal",
        },
        "adr-007-route-b-vertical-slice": {
            "title": "ADR-007：路线 B——真实 Core 纵向闭环优先",
            "path": "outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md",
            "kind": "adr",
            "authority": "canonical",
            "status": "accepted",
            "stage": "cross-stage",
            "index": True,
            "sensitivity": "internal",
        },
        "route-b-m0-m1-plan-v1.0": {
            "title": "Amadeus 路线 B M0–M1 Implementation Plan",
            "path": "outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md",
            "kind": "implementation-plan",
            "authority": "canonical",
            "status": "approved",
            "stage": "route-b-m0-m1",
            "index": True,
            "sensitivity": "internal",
        },
    }
    assert set(expected) <= set(by_id)
    for doc_id, expected_fields in expected.items():
        row = by_id[doc_id]
        assert set(row) == {"doc_id", *expected_fields, "sha256"}
        assert {key: row[key] for key in expected_fields} == expected_fields
        raw = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    navigation = (ROOT / "knowledge" / "data_structure.md").read_text(
        encoding="utf-8"
    )
    for row in expected.values():
        assert _MARKDOWN_LINK.findall(readme).count(row["path"]) == 1
        assert _MARKDOWN_LINK.findall(navigation).count(f"../{row['path']}") == 1

    assert "完成 B01 后暂停 B02–B13" in readme
    assert "M2：Core 骨架与权威契约" in readme
```

- [ ] **Step 3: 运行 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb/test_current_repository.py::test_route_b_documents_are_indexed_and_authoritative -q -p no:cacheprovider
```

Expected:

```text
FAILED
```

[KNOWN｜置信度：高] 失败原因必须来自三份路线文档、manifest 行或导航链接尚未进入仓库，而不是测试导入或语法错误。

## 4. Task 3：安装路线文档并更新唯一导航

**Files:**
- Create: `outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md`
- Create: `outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md`
- Create: `outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md`
- Modify: `README.md`
- Modify: `knowledge/data_structure.md`
- Modify: `knowledge/manifest.json`

- [ ] **Step 1: 从批准交付目录复制三份文档，随后核对字节**

Run:

```powershell
$source = 'C:\Users\skr\Documents\Codex\2026-08-01\new-chat\outputs'
$names = @(
  'Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md'
  'ADR-007-Amadeus路线B-真实Core纵向闭环优先.md'
  'Amadeus-路线B-M0-M1-实施计划-v1.0.md'
)
foreach ($name in $names) {
  Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $repo "outputs\$name")
  $left = (Get-FileHash -LiteralPath (Join-Path $source $name) -Algorithm SHA256).Hash
  $right = (Get-FileHash -LiteralPath (Join-Path $repo "outputs\$name") -Algorithm SHA256).Hash
  if ($left -cne $right) { throw "route document copy mismatch: $name" }
}
'route_documents_copied=3/3'
```

Expected:

```text
route_documents_copied=3/3
```

- [ ] **Step 2: 更新 README 当前状态**

[FRAME｜置信度：高] 将 `## 当前可核验状态` 的说明更新为以下内容；既有 Stage 0A/0B 结果继续保留。这里记录路线接管快照与活态完成判据，避免 M1 完成后留下“当前 10/20”的过期陈述：

```markdown
[KNOWN｜置信度：高] Stage 0C 的 F01–F09 已完成并推送；路线 B 接管 B01 时的冻结检查点为 10/20，续写起点是 `AC-009#1`。B01 的活态完成事实由 20 行批次测试、B01 审计记录和审计测试共同判定。Stage 0C 在 B01 完成后仍处部分完成状态，真实 Core 从 M2 开始。

| 路线 B 检查项 | 可核验结果 |
|---|---|
| [KNOWN] 已批准路线 | [KNOWN] B：完成 B01 后暂停 B02–B13，优先建设真实 Core 纵向闭环 |
| [KNOWN] Stage 0C 基础工具 | [COMPUTED] F01–F09 已完成 |
| [KNOWN] B01 接管快照 | [COMPUTED] 10/20 reviewed cases；续写起点 `AC-009#1` |
| [FRAME] B01 完成判据 | [FRAME] `test_batch_B01.py` 20 行闭合，Data/Audit 双提交有效，B01 审计测试通过 |
| [KNOWN] 最近已推送提交 | [KNOWN] `0a99c2d7ba9ca96018ba9617457f011ab0c6f2bf` |
```

- [ ] **Step 3: 将路线 B 文档置于 README 权威阅读顺序首位**

[FRAME｜置信度：高] 在 `## 权威文档阅读顺序` 中将前三项设为：

```markdown
1. [KNOWN｜置信度：高] [路线 B 需求一致性与纵向闭环设计](outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md) — 当前批准的总路线与 M0–M13 边界。
2. [KNOWN｜置信度：高] [ADR-007：真实 Core 纵向闭环优先](outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md) — 对旧 Stage 0C 执行顺序的正式覆盖裁决。
3. [KNOWN｜置信度：高] [路线 B M0–M1 实施计划](outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md) — 当前唯一执行合同。
```

[FRAME｜置信度：高] 原 ADR-006、数据契约及 Stage 0A/0B/0C 文档顺延；旧 Frozen Stage 0C 计划继续保留为来源和工具合同。

- [ ] **Step 4: 替换 README 下一严格顺序**

```markdown
## 下一步严格顺序

1. [KNOWN｜置信度：高] **M0 路线接线**：纳入路线 B 设计、ADR-007、本计划和知识库索引。
2. [KNOWN｜置信度：高] **M1 B01 整批闭环**：保留 ordinals 1–10，同一作者完成 11–20，一名复核者审完整批次，建立 Data commit 与 Audit commit。
3. [FRAME｜置信度：高] **暂停旧横向扩展**：B02–B13、Stage 0D、Stage 0C sandbox/publication 后续节点保持部分完成状态。
4. [FRAME｜置信度：高] **M2：Core 骨架与权威契约**：开始真实 Core 纵向闭环。
5. [FRAME｜置信度：高] **M3–M12**：依次贯通 Genesis、Ledger、Governor、Vault、认知、主动性、Action、学习、生命周期、恢复、模型替换和文字终端。
6. [FRAME｜置信度：高] **M13**：依据真实缺陷恢复 B02–B13 与 Stage 0D，关闭全部冻结来源覆盖后执行发布候选门禁。
```

- [ ] **Step 5: 更新 knowledge 恢复入口**

[FRAME｜置信度：高] 将 `knowledge/data_structure.md` 的 `## 5. 权威恢复入口` 前三项设为：

```markdown
1. [KNOWN｜置信度：高] [路线 B 需求一致性与纵向闭环设计](../outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md)：当前批准的总路线。
2. [KNOWN｜置信度：高] [ADR-007](../outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md)：从完整 Fixture 前置转为真实 Core 纵向闭环优先的裁决。
3. [KNOWN｜置信度：高] [路线 B M0–M1 实施计划](../outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md)：当前唯一执行合同和 B01 恢复点。
```

[FRAME｜置信度：高] 原 README、ADR-006、数据契约和 Stage 文档顺延；每个旧文档仍只出现一次。

- [ ] **Step 6: 用确定性脚本注册文档并刷新导航哈希**

Create temporary `work/register_route_b_docs.py` with this complete content:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "knowledge" / "manifest.json"

ROUTE_ROWS = (
    {
        "doc_id": "route-b-design-v1.0",
        "title": "Amadeus 路线 B：需求一致性与真实纵向闭环设计 v1.0",
        "path": "outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md",
        "kind": "design-spec",
        "authority": "canonical",
        "status": "approved",
        "stage": "cross-stage",
        "index": True,
        "sensitivity": "internal",
    },
    {
        "doc_id": "adr-007-route-b-vertical-slice",
        "title": "ADR-007：路线 B——真实 Core 纵向闭环优先",
        "path": "outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md",
        "kind": "adr",
        "authority": "canonical",
        "status": "accepted",
        "stage": "cross-stage",
        "index": True,
        "sensitivity": "internal",
    },
    {
        "doc_id": "route-b-m0-m1-plan-v1.0",
        "title": "Amadeus 路线 B M0–M1 Implementation Plan",
        "path": "outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md",
        "kind": "implementation-plan",
        "authority": "canonical",
        "status": "approved",
        "stage": "route-b-m0-m1",
        "index": True,
        "sensitivity": "internal",
    },
)


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
documents = manifest["documents"]
route_ids = {row["doc_id"] for row in ROUTE_ROWS}
documents = [row for row in documents if row["doc_id"] not in route_ids]

for row in documents:
    if row["doc_id"] in {"root-readme", "kb-navigation"}:
        row["sha256"] = digest(row["path"])

insert_at = next(
    index for index, row in enumerate(documents) if row["doc_id"] == "adr-006"
) + 1
new_rows = []
for metadata in ROUTE_ROWS:
    row = dict(metadata)
    row["sha256"] = digest(row["path"])
    new_rows.append(row)
documents[insert_at:insert_at] = new_rows

assert len(documents) == 37
assert len({row["doc_id"] for row in documents}) == 37
assert len({row["path"] for row in documents}) == 37
manifest["documents"] = documents
MANIFEST.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)
```

Run:

```powershell
.\.venv\Scripts\python.exe -B work/register_route_b_docs.py
Remove-Item -LiteralPath work/register_route_b_docs.py
```

- [ ] **Step 7: 运行 GREEN 与知识库闭包**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/project_kb -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m tools.project_kb.cli --root . check
```

Expected:

```text
41 passed
project_kb_ready=true
indexed_documents=37
raw_paths_indexed=0
```

## 5. Task 4：提交 M0 路线覆盖层

**Files:**
- Stage only the seven M0 paths from §1

- [ ] **Step 1: 核对旧 Frozen 文档字节未变化**

Run:

```powershell
$stage0cPlan = 'outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md'
$stage0cReview = 'outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md'
if ((Get-FileHash $stage0cPlan -Algorithm SHA256).Hash -cne 'D42258FB05AD818FE94409AA11FE4FDB9C163E437A30FCCC636CDCA043939069') { throw 'frozen Stage 0C plan drift' }
if ((Get-FileHash $stage0cReview -Algorithm SHA256).Hash -cne 'DC1C3E27A4C10103D814F5B3E4C0E375A99F5E7E29E17116ADFD0076A6C3FD72') { throw 'frozen Stage 0C review drift' }
```

Expected: exit code `0` and no output.

- [ ] **Step 2: 暂存精确 M0 集合**

Run:

```powershell
$m0 = @(
  'outputs/Amadeus-路线B-需求一致性与纵向闭环设计-v1.0.md'
  'outputs/ADR-007-Amadeus路线B-真实Core纵向闭环优先.md'
  'outputs/Amadeus-路线B-M0-M1-实施计划-v1.0.md'
  'README.md'
  'knowledge/data_structure.md'
  'knowledge/manifest.json'
  'tests/project_kb/test_current_repository.py'
)
git add -- $m0
if ($LASTEXITCODE -ne 0) { throw 'M0 git add failed' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'M0 staged diff check failed' }
$actual = @(git diff --cached --name-only)
$difference = Compare-Object ($m0 | Sort-Object) ($actual | Sort-Object)
if ($difference) { throw "M0 staged path mismatch:`n$($difference | Out-String)" }
```

Expected: exit code `0` and exact seven-path staged set.

- [ ] **Step 3: 提交 M0**

Run:

```powershell
git commit -m "docs: adopt route B vertical core plan"
if ($LASTEXITCODE -ne 0) { throw 'M0 commit failed' }
```

Expected: one commit containing exactly the seven M0 paths; B01 1–10 remain untracked and byte-identical.

## 6. Task 5：建立两段式作者态验证器

**Files:**
- Create temporary: `work/validate_b01_author_drafts.py`

- [ ] **Step 1: 创建完整的作者态批量验证器**

Create:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from tools.stage0c_fixtures.checklist import build_conversion_checklist
from tools.stage0c_fixtures.io import canonical_bytes, load_frozen_inputs
from tools.stage0c_fixtures.reviewed import load_reviewed_case, validate_reviewed_case
from tools.stage0c_fixtures.schema import build_fixture_case_schema


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    if (args.start, args.end) not in {(11, 15), (16, 20)}:
        raise SystemExit("range must be 11..15 or 16..20")

    frozen = load_frozen_inputs(ROOT)
    checklist = build_conversion_checklist(frozen)
    schema = build_fixture_case_schema()
    checked = 0
    for ordinal in range(args.start, args.end + 1):
        checklist_row = checklist["cases"][ordinal - 1]
        path = ROOT / checklist_row["reviewed_path"]
        raw = path.read_bytes()
        row = load_reviewed_case(path)
        if raw != canonical_bytes(row):
            raise SystemExit(f"{checklist_row['clause_id']} is not canonical JSON")
        if "reviewer" in row:
            raise SystemExit(
                f"{checklist_row['clause_id']} already contains reviewer in author state"
            )
        candidate = dict(row)
        candidate["reviewer"] = {
            "reviewer_id": "author-state-validator",
            "role": "conversion_reviewer",
            "reviewed_at": "2026-08-01",
        }
        issues = validate_reviewed_case(
            candidate,
            frozen.clauses_by_id[checklist_row["clause_id"]],
            schema,
        )
        observed = [(issue.json_pointer, issue.code) for issue in issues]
        if observed:
            raise SystemExit(
                f"{checklist_row['clause_id']} author-state issues: {observed!r}"
            )
        checked += 1
    print(f"author_drafts_valid={checked}/{args.end - args.start + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 验证脚本自身参数边界**

Run:

```powershell
.\.venv\Scripts\python.exe -B work/validate_b01_author_drafts.py --start 11 --end 20
```

Expected:

```text
range must be 11..15 or 16..20
```

[KNOWN｜置信度：高] 非零退出证明脚本拒绝绕过两个五案例检查点。验证器只在内存副本中注入临时 reviewer，因此会实际检查 frozen identity、case body、stimulus/oracle mapping、rationale 与 canonical JSON，而不是把 `reviewer_missing` 当成内容通过。

## 7. Task 6：同一作者完成 ordinals 11–15

**Files:**
- Create: `case-ac-009-1.json` through `case-ac-013-1.json`

[FRAME｜置信度：高] 作者身份：`stage0c-b01-author`。五个文件在作者态省略顶层 `reviewer`；其他顶层字段必须精确闭合。

| ordinal | clause | file | 冻结 stimulus | 冻结 expected | oracle |
|---:|---|---|---|---|---|
| 11 | `AC-009#1` | `case-ac-009-1.json` | `non_mention_request` | 只经 Governor 改当前 Vault 表达策略 | D |
| 12 | `AC-010#1` | `case-ac-010-1.json` | 模型进程调用 commit | `CORE-E-LLM-COMMIT-FORBIDDEN`，权威零写入 | D |
| 13 | `AC-011#1` | `case-ac-011-1.json` | 模型提交合法 Proposal | 追加 `proposal_submitted`，状态 pending | D |
| 14 | `AC-012#1` | `case-ac-012-1.json` | 同状态、策略、Proposal 重放 | 决策结果与输出状态哈希一致 | D |
| 15 | `AC-013#1` | `case-ac-013-1.json` | 相同幂等键与内容重试 | 返回首次结果，无重复语义事件 | D/S |

- [ ] **Step 1: 按已有 AC-007/008 模式完成五个 canonical reviewed JSON**

[FRAME｜置信度：高] 每个 case 必须满足：

```text
setup: sandbox.seed_state + sandbox.configure_core_driver
stimulus: core.command
assertions: exact state/receipt/effect assertions for the frozen expected scope
source identity: copied byte-for-byte from the frozen clause manifest
mapping: every stimulus and oracle has resolving JSON pointers and a nonblank note
rationale: explains why the case proves the clause and why broader state is not frozen
reviewer: absent in author state
```

[FRAME｜置信度：高] `AC-010#1` 同时断言错误码与权威状态哈希不变；`AC-012#1` 比较两次实际裁决输出；`AC-013#1` 断言首次 result 引用复用且第二次零新增事件。

- [ ] **Step 2: 运行 11–15 作者态批量验证**

Run:

```powershell
.\.venv\Scripts\python.exe -B work/validate_b01_author_drafts.py --start 11 --end 15
```

Expected:

```text
author_drafts_valid=5/5
```

## 8. Task 7：同一作者完成 ordinals 16–20

**Files:**
- Create: `case-ac-014-1.json` through `case-ac-018-1.json`

| ordinal | clause | file | 冻结 stimulus | 冻结 expected | oracle |
|---:|---|---|---|---|---|
| 16 | `AC-014#1` | `case-ac-014-1.json` | 相同幂等键、不同内容 | `CORE-E-IDEMPOTENCY-CONFLICT` | D |
| 17 | `AC-015#1` | `case-ac-015-1.json` | archived 直接转 superseded 且无证据 | `CORE-E-INVALID-MEMORY-TRANSITION` | D |
| 18 | `AC-016#1` | `case-ac-016-1.json` | Vault A 能力请求 Vault B 事件 | `CORE-E-CROSS-VAULT-READ-FORBIDDEN` 并审计 | D/S |
| 19 | `AC-017#1` | `case-ac-017-1.json` | Vault A 查询命中 Vault B 高相似内容 | Vault B 零返回，禁止扩大检索域 | D/S |
| 20 | `AC-018#1` | `case-ac-018-1.json` | 使用 Vault A 缓存键读取 Vault B 请求 | `CORE-E-VAULT-SCOPE-MISMATCH` | D/S |

- [ ] **Step 1: 完成五个 canonical reviewed JSON**

[FRAME｜置信度：高] 使用 Task 6 的相同结构合同，并增加以下硬断言：

```text
AC-014: conflict receipt + first result/state preserved + zero second semantic event
AC-015: invalid transition receipt + memory state/hash preserved
AC-016: cross-vault error + zero returned foreign record + denied attempt audit
AC-017: empty result after pre-ranking vault filter + no fallback/cross-vault effect
AC-018: cache-scope error + zero foreign cache payload + zero cache-key rebinding
```

- [ ] **Step 2: 运行 16–20 作者态批量验证**

Run:

```powershell
.\.venv\Scripts\python.exe -B work/validate_b01_author_drafts.py --start 16 --end 20
```

Expected:

```text
author_drafts_valid=5/5
```

- [ ] **Step 3: 删除临时作者态验证器**

Run:

```powershell
Remove-Item -LiteralPath work/validate_b01_author_drafts.py
```

Expected: file absent; reviewed cases remain.

## 9. Task 8：一名独立复核者审查完整 B01

**Files:**
- Review: all 20 B01 cases
- Modify only if needed: ordinals 1–10 defects
- Add `reviewer` after approval: ordinals 11–20
- Create temporary: `work/approve_b01_reviews.py`

[FRAME｜置信度：高] 复核者身份固定为 `stage0c-b01-reviewer`，与作者身份不同。复核以完整 20-case 批次为一个任务，不为每个 case 启动独立代理。

- [ ] **Step 1: 执行整批语义审查**

[FRAME｜置信度：高] 复核者逐行检查以下六项，并形成一份集中结果：

```text
1. frozen stimulus and expected scope are represented without semantic narrowing
2. every required oracle kind has a same-kind mapping
3. state.hash_unchanged scopes only the intended invariant subtree
4. deterministic seed/result pairs derive every asserted value
5. Vault cases filter before ranking/cache access and audit denied attempts
6. rationale and mapping notes explain clause proof rather than restating the filename
```

- [ ] **Step 2: 对通过的 11–20 填入统一 reviewer object**

Exact object:

```json
{"reviewed_at":"2026-08-01","reviewer_id":"stage0c-b01-reviewer","role":"conversion_reviewer"}
```

[FRAME｜置信度：高] 语义复核通过后，创建临时 `work/approve_b01_reviews.py`；它先在内存中验证全部十个候选，再统一写回，避免半批状态：

```python
from __future__ import annotations

from pathlib import Path

from tools.stage0c_fixtures.checklist import build_conversion_checklist
from tools.stage0c_fixtures.io import canonical_bytes, load_frozen_inputs
from tools.stage0c_fixtures.reviewed import load_reviewed_case, validate_reviewed_case
from tools.stage0c_fixtures.schema import build_fixture_case_schema


ROOT = Path(__file__).resolve().parents[1]
REVIEWER = {
    "reviewer_id": "stage0c-b01-reviewer",
    "role": "conversion_reviewer",
    "reviewed_at": "2026-08-01",
}

frozen = load_frozen_inputs(ROOT)
checklist = build_conversion_checklist(frozen)
schema = build_fixture_case_schema()
candidates = []
for checklist_row in checklist["cases"][10:20]:
    path = ROOT / checklist_row["reviewed_path"]
    reviewed = load_reviewed_case(path)
    existing_reviewer = reviewed.get("reviewer")
    if existing_reviewer not in (None, REVIEWER):
        raise SystemExit(
            f"{checklist_row['clause_id']} contains an unexpected reviewer"
        )
    candidate = dict(reviewed)
    candidate["reviewer"] = REVIEWER
    issues = validate_reviewed_case(
        candidate,
        frozen.clauses_by_id[checklist_row["clause_id"]],
        schema,
    )
    if issues:
        observed = [(issue.json_pointer, issue.code) for issue in issues]
        raise SystemExit(
            f"{checklist_row['clause_id']} review validation failed: {observed!r}"
        )
    candidates.append((path, candidate))

for path, candidate in candidates:
    path.write_bytes(canonical_bytes(candidate))
print(f"reviewers_applied={len(candidates)}/10")
```

Run:

```powershell
.\.venv\Scripts\python.exe -B work/approve_b01_reviews.py
Remove-Item -LiteralPath work/approve_b01_reviews.py
```

Expected:

```text
reviewers_applied=10/10
```

[FRAME｜置信度：高] 由现有 canonical JSON writer 写回，保持 UTF-8、单行规范 JSON 和单个结尾换行。

- [ ] **Step 3: 运行 B01 与 reviewed validator GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_batch_B01.py tests/stage0c/test_reviewed.py -q -p no:cacheprovider
```

Expected:

```text
81 passed
```

- [ ] **Step 4: 重新核对 1–10 批准哈希**

[FRAME｜置信度：高] 若整批审查没有发现 1–10 的实际缺陷，Task 1 的 11 个哈希必须继续完全相等。若发现实际缺陷，复核结果必须明确列出 clause、错误语义和新证据；不得以格式统一为理由重写既有字节。

## 10. Task 9：创建 B01 Data commit

**Files:**
- Stage: B01 batch test + exact 20 cases

- [ ] **Step 1: 暂存精确 reviewed payload**

Run:

```powershell
$batchTest = 'tests/stage0c/reviewed_batches/test_batch_B01.py'
$casePaths = @(
  'fixtures/stage0c/reviewed/cases/case-ac-001-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-002-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-003-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-004-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-005-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-006-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-007-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-2.json'
  'fixtures/stage0c/reviewed/cases/case-ac-008-3.json'
  'fixtures/stage0c/reviewed/cases/case-ac-009-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-010-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-011-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-012-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-013-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-014-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-015-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-016-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-017-1.json'
  'fixtures/stage0c/reviewed/cases/case-ac-018-1.json'
)
$expected = @($batchTest) + $casePaths
git add -- $expected
if ($LASTEXITCODE -ne 0) { throw 'B01 Data git add failed' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'B01 Data staged diff check failed' }
$actual = @(git diff --cached --name-only)
$difference = Compare-Object ($expected | Sort-Object) ($actual | Sort-Object)
if ($difference) { throw "B01 Data staged path mismatch:`n$($difference | Out-String)" }
```

Expected: exact 21-path staged set; route documents are already committed; audit files are absent.

- [ ] **Step 2: 创建 Data commit**

Run:

```powershell
git commit -m "data(stage0c): review conversion batch B01"
if ($LASTEXITCODE -ne 0) { throw 'B01 Data commit failed' }
$reviewedCommit = (git rev-parse HEAD).Trim()
if ($reviewedCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'reviewed commit invalid' }
"reviewed_commit=$reviewedCommit"
```

Expected: a 40-character lowercase `reviewed_commit`; commit path set exactly matches Step 1.

## 11. Task 10：生成 B01 审计记录与可追溯测试

**Files:**
- Create temporary: `work/build_b01_audit_record.py`
- Create: `outputs/verification/stage0c-reviewed-batches/B01.json`
- Create: `tests/stage0c/reviewed_batches/test_audit_B01.py`

- [ ] **Step 1: 创建确定性审计记录生成器**

Create `work/build_b01_audit_record.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.stage0c_fixtures.checklist import build_conversion_checklist
from tools.stage0c_fixtures.io import canonical_bytes, load_frozen_inputs
from tools.stage0c_fixtures.reviewed import load_reviewed_case


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "verification" / "stage0c-reviewed-batches" / "B01.json"
AUTHOR_ID = "stage0c-b01-author"


commit = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()
if len(commit) != 40 or commit.lower() != commit:
    raise SystemExit("reviewed commit is not a lowercase full object id")

frozen = load_frozen_inputs(ROOT)
checklist = build_conversion_checklist(frozen)
rows = checklist["cases"][:20]
case_reviews = []
for row in rows:
    reviewed = load_reviewed_case(ROOT / row["reviewed_path"])
    reviewer = reviewed["reviewer"]
    case_reviews.append(
        {
            "ordinal": row["ordinal"],
            "batch_ordinal": row["batch_ordinal"],
            "clause_id": row["clause_id"],
            "case_path": row["reviewed_path"],
            "author_id": AUTHOR_ID,
            "reviewer_id": reviewer["reviewer_id"],
            "reviewed_at": reviewer["reviewed_at"],
        }
    )

record = {
    "schema_version": "0.1",
    "batch_id": "B01",
    "reviewed_commit": commit,
    "test_path": "tests/stage0c/reviewed_batches/test_batch_B01.py",
    "case_reviews": case_reviews,
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_bytes(canonical_bytes(record))
print(f"audit_cases={len(case_reviews)}")
print(f"reviewed_commit={commit}")
```

Run:

```powershell
.\.venv\Scripts\python.exe -B work/build_b01_audit_record.py
Remove-Item -LiteralPath work/build_b01_audit_record.py
```

Expected:

```text
audit_cases=20
reviewed_commit=[DATA_COMMIT_SHA:40-lower-hex]
```

- [ ] **Step 2: 创建完整 audit test**

Create `tests/stage0c/reviewed_batches/test_audit_B01.py`:

```python
from __future__ import annotations

import subprocess

from tools.stage0c_fixtures.io import load_strict_json_bytes
from tools.stage0c_fixtures.reviewed import (
    load_reviewed_case,
    validate_batch_review_record,
)


def _git(repository_root, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def test_b01_review_record_proves_exact_data_commit(
    repository_root,
    checklist,
) -> None:
    record_path = (
        repository_root
        / "outputs"
        / "verification"
        / "stage0c-reviewed-batches"
        / "B01.json"
    )
    loaded = load_strict_json_bytes(
        record_path.read_bytes(),
        source="outputs/verification/stage0c-reviewed-batches/B01.json",
    )
    assert isinstance(loaded, dict)
    record = loaded
    checklist_rows = checklist["cases"][:20]
    reviewed_by_clause_id = {
        row["clause_id"]: load_reviewed_case(
            repository_root / row["reviewed_path"]
        )
        for row in checklist_rows
    }
    assert (
        validate_batch_review_record(
            record,
            checklist_rows,
            reviewed_by_clause_id,
        )
        == []
    )

    commit = record["reviewed_commit"]
    _git(repository_root, "cat-file", "-e", f"{commit}^{{commit}}")
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repository_root,
        check=False,
    )
    assert reachable.returncode == 0

    expected_paths = [
        record["test_path"],
        *(row["reviewed_path"] for row in checklist_rows),
    ]
    actual_paths = _git(
        repository_root,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "-r",
        commit,
    ).stdout.decode("utf-8").splitlines()
    assert sorted(actual_paths) == sorted(expected_paths)

    for relative in expected_paths:
        committed = _git(
            repository_root,
            "show",
            f"{commit}:{relative}",
        ).stdout
        assert committed == (repository_root / relative).read_bytes()
```

- [ ] **Step 3: 运行审计专项**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/stage0c/reviewed_batches/test_audit_B01.py -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

## 12. Task 11：一次全量回归、Audit commit 与统一推送

**Files:**
- Stage after verification: B01 audit record and audit test only

- [ ] **Step 1: 核对最终收集规模**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest --collect-only -q -p no:cacheprovider | Select-Object -Last 1
```

Expected:

```text
905 tests collected
```

- [ ] **Step 2: 在无缺陷路径运行一次全量回归**

Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Expected:

```text
903 passed, 2 skipped
```

[KNOWN｜置信度：高] 出现 FAIL 或 ERROR 时按变更路径恢复，旧 Data SHA 绝不继续写入新审计记录：

1. [FRAME] 缺陷只在尚未提交的 `B01.json` 或 `test_audit_B01.py`：修复审计工件，运行审计专项，再重新执行本 Step 的全量回归。
2. [FRAME] 缺陷涉及 20 个 case 或 `test_batch_B01.py`：删除旧审计记录，将尚未推送的 Data commit 解提交但保留工作树，修复后重新执行 Task 8 专项、Task 9 精确暂存/提交、Task 10 审计生成与专项，最后重新执行本 Step：

```powershell
Remove-Item -LiteralPath outputs/verification/stage0c-reviewed-batches/B01.json -ErrorAction SilentlyContinue
git reset --soft HEAD^
git reset
```

3. [FRAME] 缺陷涉及 M0 七路径：删除旧审计记录，使用 `git reset --soft HEAD~2` 后执行 `git reset`，保留工作树并依次重建 M0 与 Data 两个未推送提交，再重新生成审计记录。任何父提交重建都会改变 Data SHA，后代审计工件随之重建。
4. [FRAME] 只重跑受影响节点用于定位；证明修复时仍执行一次新的完整全量回归。无缺陷路径保持一次全量回归。

- [ ] **Step 3: 暂存精确 Audit commit 集合**

Run:

```powershell
$auditPaths = @(
  'outputs/verification/stage0c-reviewed-batches/B01.json'
  'tests/stage0c/reviewed_batches/test_audit_B01.py'
)
git add -- $auditPaths
if ($LASTEXITCODE -ne 0) { throw 'B01 Audit git add failed' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'B01 Audit staged diff check failed' }
$actual = @(git diff --cached --name-only)
$difference = Compare-Object ($auditPaths | Sort-Object) ($actual | Sort-Object)
if ($difference) { throw "B01 Audit staged path mismatch:`n$($difference | Out-String)" }
```

Expected: exact two-path staged set.

- [ ] **Step 4: 创建 Audit commit**

Run:

```powershell
git commit -m "audit(stage0c): record conversion review batch B01"
if ($LASTEXITCODE -ne 0) { throw 'B01 Audit commit failed' }
```

Expected: one commit containing only the B01 record and audit test.

- [ ] **Step 5: 验证三节点历史与清洁工作树**

Run:

```powershell
git log -3 --format=%s
$expectedAuditCommitPaths = @(
  'outputs/verification/stage0c-reviewed-batches/B01.json'
  'tests/stage0c/reviewed_batches/test_audit_B01.py'
)
$actualAuditCommitPaths = @(
  git diff-tree --root --no-commit-id --name-only -r HEAD
)
$auditCommitDifference = Compare-Object (
  $expectedAuditCommitPaths | Sort-Object
) ($actualAuditCommitPaths | Sort-Object)
if ($auditCommitDifference) {
  throw "B01 Audit commit path mismatch:`n$($auditCommitDifference | Out-String)"
}
git status --short --branch
```

Expected:

```text
audit(stage0c): record conversion review batch B01
data(stage0c): review conversion batch B01
docs: adopt route B vertical core plan
```

[KNOWN｜置信度：高] 工作树必须清洁，Audit commit path set 必须精确；已在提交前全量覆盖的测试不在提交后重复运行。Stage 0C 仍为部分完成，不生成 B02 文件。

- [ ] **Step 6: 统一推送并验证远端 SHA**

Run:

```powershell
git push origin codex/stage0c-fixture-conversion
if ($LASTEXITCODE -ne 0) { throw 'route B push failed' }
$local = (git rev-parse HEAD).Trim()
$remote = (git ls-remote origin refs/heads/codex/stage0c-fixture-conversion).Split("`t")[0]
if ($local -cne $remote) { throw 'remote SHA mismatch' }
"route_b_m0_m1_head=$local"
```

Expected: push succeeds and local/remote full SHA values are equal.

## 13. 完成定义

[FRAME｜置信度：高] M0–M1 只有在以下条件同时成立时完成：

- [FRAME] 三份路线 B 文档已进入仓库、README、知识导航和 37 文档 manifest。
- [FRAME] 旧 Frozen Stage 0C 计划与审查记录哈希保持。
- [FRAME] B01 20/20 reviewed cases 通过 81 项批次/validator 专项。
- [FRAME] 11–20 由同一作者整批完成，一名独立复核者审查完整 B01。
- [FRAME] Data commit 精确包含 20 cases 与 batch test。
- [FRAME] Audit commit 精确包含 B01 record 与 audit test。
- [FRAME] 审计记录引用实际 Data commit，提交 path set 与工作树字节可证明。
- [FRAME] 全量结果为 903 passed、2 skipped。
- [FRAME] 本地与远端 HEAD 相等，工作树清洁。
- [FRAME] B02–B13 与 Stage 0D 没有新增实现文件。

## 14. 自检清单

- [ ] [FRAME] 三份新文档在 README、knowledge navigation 和 manifest 中各出现一次。
- [ ] [FRAME] 新文档 metadata、实际字节和 manifest SHA-256 一致。
- [ ] [FRAME] 旧 32 文档 projection digest 和两个 Frozen Stage 0C 哈希保持。
- [ ] [FRAME] ordinals 1–10 在没有实际缺陷证据时保持 Task 1 哈希。
- [ ] [FRAME] ordinals 11–20 各自只有 frozen clause 要求对应的 oracle。
- [ ] [FRAME] reviewer ID 与 author ID 不同，reviewer date 与 JSON/record 一致。
- [ ] [FRAME] Data commit 与 Audit commit 没有交叉 path。
- [ ] [FRAME] 无缺陷路径只执行一次全量回归；若发现实际缺陷，修复后执行必要的证明性重跑。
- [ ] [FRAME] M1 完成声明不外推为 Stage 0C 完成。
- [ ] [FRAME] 下一行动固定为编写 M2–M5 真实 Core 权威纵向闭环计划。

[我打破的规则 / RULES I BROKE]：无。
