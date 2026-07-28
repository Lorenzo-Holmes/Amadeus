# Amadeus Core v0.1 Stage 0A 来源编译器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [FRAME｜置信度：高] 构建一个只读来源编译器，逐字节绑定五份权威输入，精确提取 53+66+95 个来源行，并生成后续人工裁决所需的 oracle 与 atomicity 工作表。

**Architecture:** [FRAME｜置信度：高] 编译器把“原始 Markdown 证据”和“派生规范字段”分开保存：原始行、原始单元格、文档路径、文档 SHA-256 和行号保持可追溯，规范字段只用于稳定排序与工作表生成。Stage 0A 不分配 Core oracle、不拆 clause、不创建 case、不声明 catalog ready；它只生成可重建的来源账本和显式 pending 工作表。

**Tech Stack:** [KNOWN｜置信度：高] Python 3.12、标准库 `argparse/collections/hashlib/json/pathlib/re/typing/ast`、pytest 7.4+、canonical JSON、SHA-256、PowerShell、Git。

---

> [KNOWN｜置信度：高] 状态：Approved for Stage 0A execution / 三路独立复核均为 0 Critical、0 Important。  
> [KNOWN｜置信度：高] 日期：2026-07-28。  
> [KNOWN｜置信度：高] 本文件取代同名的全 Stage 0 草案；旧草案复核发现 5 Critical、8 Important，因此不再作为实施合同。

## 0. 反方论据

[INFERRED｜置信度：高] 在 source index 尚未忠实保存原文与裁判来源时，同时规划 clause、case、H/J、catalog 与发布门禁，会让后续所有覆盖数字建立在未经证实的派生数据上。

[INFERRED｜置信度：高] Core 的 95 行验收表没有裁判列。把它们自动写成“显式 D”会把工程猜测伪装成源文档事实；Stage 0A 必须保存 `oracle_provenance=undeclared`，把分配留给显式人工裁决。

[INFERRED｜置信度：高] 214 行人工拆句和全部 case 内容在来源 manifest 生成前还没有确定输入。将其塞入当前计划只会产生隐式占位。因此 Stage 0 被拆成四个可独立验证的子项目。

## 1. Stage 0 分解与本计划边界

| 子项目 | [FRAME] 输入 | [FRAME] 唯一完成物 | [KNOWN] 当前状态 |
|---|---|---|---|
| Stage 0A 来源编译器 | 五份冻结文档 | source index、oracle worklist、atomicity worklist | 本计划 |
| Stage 0B 来源裁决 | Stage 0A 三个工件 | 214 行 oracle/atomicity 决策与 source-clause manifest | 待 0A 工件生成后写独立计划 |
| Stage 0C DSL 与 case 绑定 | 已复核 clause manifest | fixture schema、S-capable handler registry、case-conversion binding、cases | 待 0B 冻结后写独立计划 |
| Stage 0D 裁判与 catalog | 已复核 cases | 盲化 H 工件、L/J 校准、catalog、两类报告 | 待 0C 冻结后写独立计划 |

[FRAME｜置信度：高] Stage 0A 完成只允许声明 `source_toolchain_ready=true`。`atomicity_complete`、`case_coverage_complete`、`catalog_ready`、`release_ready` 均保持 false。

[FRAME｜置信度：高] Stage 0B 必须逐来源裁决 atomic/composite，并为 Core AC 显式分配 oracle；Stage 0C 必须验证 clause→case 语义绑定以及 23 个 S 来源的动作信封、reset/cleanup、回执和副作用差分；Stage 0D 必须实现盲化双人 H、第三人裁决、L/J 来源差异与 50/0.80 校准。

## 2. 冻结输入

| key | path | [COMPUTED] SHA-256 | [FRAME] 角色 |
|---|---|---|---|
| `adr_006` | `outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md` | `EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6` | 权威优先级 |
| `core_spec` | `outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md` | `3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695` | AC-001..095 |
| `baseline` | `outputs/Amadeus身份与记忆评测基线-v0.1.md` | `5C260EE19D9FF129633B968E87FACA79E93B7A01E3B86580E0FAD2DBC7147853` | 53 个行为来源、D/H/L |
| `increment` | `outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md` | `16ACDB17717AFEA5B5C19F39E91729385DB59B984F35CEF5B651BE9EEE8A37FC` | 66 个行为来源、D/S/H/J |
| `plan_review` | `outputs/Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md` | `865517363E5E3D6F2285BA30EDFC5C5405B0196E6007672E417F683C70995BED` | Stage 化约束 |

[FRAME｜置信度：高] 任一文件字节漂移时，`write` 与 `check` 都返回输入错误；更新输入必须先通过新的文档复核，再显式修改 `source_config_v0_1.json` 的期望指纹。

## 3. 完成定义

- [ ] [FRAME] 五个文档的实际 SHA-256 与冻结配置逐字节一致。
- [ ] [FRAME] 来源 ID 集精确等于 53 个基线 ID、66 个增量 ID、`AC-001..AC-095`；计数相同但 ID 替换也失败。
- [ ] [FRAME] 每个来源保存 `document_key/path/sha256/line_number/raw_line/raw_cells/raw_row_sha256`。
- [ ] [FRAME] 每个来源另存规范字段；Core 的 `title/action/expected` 保持分列。
- [ ] [FRAME] 行摘要 hash 绑定文档 hash、行号和原始行，不只绑定清洗文本。
- [ ] [FRAME] 行为来源保留 raw D/S/H/L/J 与 canonical D/S/H/J；Core 保留空 raw oracle、空 canonical oracle 和 `undeclared` provenance。
- [ ] [FRAME] 行为裁判组合精确等于基线 `30/20/2/1` 和增量 `18/18/23/4/3`。
- [ ] [FRAME] Oracle worklist 有 214 行，其中 119 行 `source_declared`、95 行 `pending_assignment`。
- [ ] [FRAME] Atomicity worklist 有 214 行且全部 `pending_review`；编译器不自动给 `#1`。
- [ ] [FRAME] `write` 与 `check` 生成相同 canonical bytes；`check` 检出任何文档、配置或生成工件漂移。
- [ ] [FRAME] 最终报告只声明 `source_toolchain_ready=true`，并报告 `pending_oracle_assignments=95`、`pending_atomicity_reviews=214`。
- [ ] [FRAME] 独立规范与质量复核均为 0 Critical、0 Important。

## 4. 文件职责

```text
.gitignore
pyproject.toml
tools/
  __init__.py
  stage0a_sources/
    __init__.py
    canonical.py
    compiler.py
    worklists.py
    cli.py
    transport_gate.py
fixtures/
  stage0a/
    source_config_v0_1.json
    generated/
      source_index_v0_1.json
      oracle_assignment_worklist_v0_1.json
      atomicity_worklist_v0_1.json
      source_toolchain_report_v0_1.json
tests/
  stage0a/
    test_canonical.py
    test_compiler.py
    test_worklists.py
    test_cli.py
    test_transport_gate.py
```

## 5. 公共数据合同

### 5.1 Source row

```json
{
  "source_id": "AC-001",
  "source_group": "core",
  "document_key": "core_spec",
  "document_path": "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
  "document_sha256": "3D9180...",
  "line_number": 1175,
  "raw_line": "| [FRAME] AC-001 | ... |",
  "raw_cells": ["[FRAME] AC-001", "...", "...", "..."],
  "raw_row_sha256": "...",
  "normalized": {
    "title": "...",
    "scenario": null,
    "action": "...",
    "expected": "...",
    "raw_oracle_tokens": [],
    "canonical_oracle_kinds": [],
    "oracle_provenance": "undeclared"
  },
  "source_binding_sha256": "..."
}
```

[FRAME｜置信度：高] 行为来源使用 `scenario/expected/raw_oracle_tokens/canonical_oracle_kinds`；Core 使用 `title/action/expected`。未适用字段显式为 null，字段不会拼接丢失。

### 5.2 Worklist rows

```json
{
  "source_id": "AC-001",
  "source_binding_sha256": "...",
  "review_state": "pending_assignment",
  "assigned_oracle_kinds": [],
  "rationale": null
}
```

```json
{
  "source_id": "AC-001",
  "source_binding_sha256": "...",
  "review_state": "pending_review",
  "atomicity_decision": null,
  "rationale": null,
  "clauses": []
}
```

[FRAME｜置信度：高] Pending 是真实工作流状态，不算已裁决结果。Stage 0B 负责把这些行版本化为 reviewed。

## 6. 叶级 TDD 协议

[FRAME｜置信度：高] 每个测试函数采用六步循环：写一个失败测试、运行该测试、确认精确失败、写最小实现、运行该测试转绿、运行所属文件后提交。下列 Step 已按此边界拆分；一次 Step 不同时增加两个 public helper。

## 7. 实施任务

### Task 0：受控环境、配置与 import contract

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `tools/__init__.py`
- Create: `tools/stage0a_sources/__init__.py`
- Create: `fixtures/stage0a/source_config_v0_1.json`
- Test: `tests/stage0a/test_import_contract.py`

- [ ] **Step 1: 初始化 Git 文档基线**

```powershell
git init -b main .
git add outputs
git commit -m "docs: freeze amadeus design baseline"
```

Expected: `git branch --show-current` 输出 `main`。

- [ ] **Step 2: 创建环境、配置与顶层 package 文件**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "amadeus-stage0a-sources"
version = "0.1.0"
requires-python = ">=3.12"

[project.optional-dependencies]
test = ["pytest>=7.4,<9"]

[project.scripts]
amadeus-stage0a = "tools.stage0a_sources.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
artifacts/
```

```json
{
  "schema_version": "0.1",
  "documents": [
    {"key":"adr_006","path":"outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md","sha256":"EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6","source_group":null},
    {"key":"core_spec","path":"outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md","sha256":"3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695","source_group":"core"},
    {"key":"baseline","path":"outputs/Amadeus身份与记忆评测基线-v0.1.md","sha256":"5C260EE19D9FF129633B968E87FACA79E93B7A01E3B86580E0FAD2DBC7147853","source_group":"baseline"},
    {"key":"increment","path":"outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md","sha256":"16ACDB17717AFEA5B5C19F39E91729385DB59B984F35CEF5B651BE9EEE8A37FC","source_group":"increment"},
    {"key":"plan_review","path":"outputs/Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md","sha256":"865517363E5E3D6F2285BA30EDFC5C5405B0196E6007672E417F683C70995BED","source_group":null}
  ]
}
```

[FRAME｜置信度：高] 本 Step 创建空的 `tools/__init__.py`，但此时不创建 `tools/stage0a_sources/`；这样 import contract 的首次运行必为红灯。

- [ ] **Step 3: 建立虚拟环境**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
```

Expected: exit code 0。

- [ ] **Step 4: 写 import contract 失败测试**

```python
# tests/stage0a/test_import_contract.py
from tools.stage0a_sources import SCHEMA_VERSION

def test_schema_version_is_frozen() -> None:
    assert SCHEMA_VERSION == "0.1"
```

- [ ] **Step 5: 运行 import contract 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_import_contract.py -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources`。

- [ ] **Step 6: 创建 Stage 0A package 的最小实现**

```python
# tools/stage0a_sources/__init__.py
SCHEMA_VERSION = "0.1"
```

- [ ] **Step 7: 运行 import contract 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_import_contract.py -v
```

Expected: `1 passed`。

- [ ] **Step 8: 提交环境**

```powershell
git add .gitignore pyproject.toml tools fixtures/stage0a/source_config_v0_1.json tests/stage0a/test_import_contract.py
git commit -m "build: bootstrap stage0a source toolchain"
```

### Task 1：Canonical bytes 与五文档指纹

**Files:**
- Create: `tools/stage0a_sources/canonical.py`
- Test: `tests/stage0a/test_canonical.py`

- [ ] **Step 1: 写 canonical bytes 失败测试**

```python
# tests/stage0a/test_canonical.py
from tools.stage0a_sources.canonical import canonical_bytes

def test_canonical_bytes_ignore_key_order() -> None:
    assert canonical_bytes({"b":2,"a":1}) == b'{"a":1,"b":2}'
```

- [ ] **Step 2: 运行红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_canonical_bytes_ignore_key_order -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources.canonical`。

- [ ] **Step 3: 写 canonical bytes**

```python
# tools/stage0a_sources/canonical.py
import hashlib
import json
from typing import Any

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()
```

- [ ] **Step 4: 运行 canonical 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_canonical_bytes_ignore_key_order -v
```

Expected: `1 passed`。

- [ ] **Step 5: 写五指纹正样本失败测试**

```python
# append tests/stage0a/test_canonical.py
import json
from pathlib import Path
import pytest
from tools.stage0a_sources.canonical import verify_documents

def test_verify_documents_binds_all_five_inputs() -> None:
    root=Path(__file__).parents[2]
    config=json.loads((root/"fixtures/stage0a/source_config_v0_1.json").read_text(encoding="utf-8"))
    result=verify_documents(root,config)
    assert tuple(result) == ("adr_006","baseline","core_spec","increment","plan_review")
    assert all(item["actual_sha256"]==item["expected_sha256"] for item in result.values())
    assert {item["path"] for item in result.values()}=={
        item["path"] for item in config["documents"]
    }
```

- [ ] **Step 6: 运行五指纹正样本红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_binds_all_five_inputs -v
```

Expected: FAIL，`ImportError: cannot import name 'verify_documents'`。

- [ ] **Step 7: 写只支持冻结正样本的最小验证器**

```python
# append tools/stage0a_sources/canonical.py
from pathlib import Path

def verify_documents(root: Path, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result={}
    for item in config["documents"]:
        path=(root/item["path"]).resolve()
        actual=_sha256_hex(path.read_bytes())
        result[item["key"]]={
            "path":item["path"],
            "source_group":item["source_group"],
            "expected_sha256":item["sha256"].upper(),
            "actual_sha256":actual,
        }
    return dict(sorted(result.items()))
```

- [ ] **Step 8: 运行五指纹正样本绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_binds_all_five_inputs -v
```

Expected: `1 passed`。

- [ ] **Step 9: 写文档单字节漂移失败测试**

```python
# append tests/stage0a/test_canonical.py
import shutil

def test_verify_documents_rejects_one_byte_drift(tmp_path: Path) -> None:
    source_root=Path(__file__).parents[2]
    root=tmp_path/"sandbox"
    config=json.loads(
        (source_root/"fixtures/stage0a/source_config_v0_1.json").read_text(encoding="utf-8")
    )
    for item in config["documents"]:
        source=source_root/item["path"]
        target=root/item["path"]
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    drift=root/config["documents"][0]["path"]
    drift.write_bytes(drift.read_bytes()+b" ")
    with pytest.raises(ValueError,match="document drift"):
        verify_documents(root,config)
```

- [ ] **Step 10: 运行文档漂移红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_rejects_one_byte_drift -v
```

Expected: FAIL，`DID NOT RAISE ValueError`。

- [ ] **Step 11: 在读取后增加指纹拒绝分支**

```python
# insert after expected/actual are computed in verify_documents()
if actual!=item["sha256"].upper():
    raise ValueError(
        f"document drift: {item['key']} "
        f"expected={item['sha256'].upper()} actual={actual}"
    )
```

- [ ] **Step 12: 运行文档漂移绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_rejects_one_byte_drift -v
```

Expected: `1 passed`。

- [ ] **Step 13: 写配置身份合同失败测试**

```python
# append tests/stage0a/test_canonical.py
from copy import deepcopy

def test_verify_documents_rejects_config_identity_drift() -> None:
    root=Path(__file__).parents[2]
    original=json.loads((root/"fixtures/stage0a/source_config_v0_1.json").read_text(encoding="utf-8"))
    mutations=[
        lambda value:value.update(schema_version="0.2"),
        lambda value:value["documents"][0].update(key="renamed"),
        lambda value:value["documents"][0].update(path=value["documents"][1]["path"]),
        lambda value:value["documents"][1].update(source_group="increment"),
        lambda value:value["documents"][0].update(sha256="0"*64),
        lambda value:value["documents"][0].update(extra="not-frozen"),
    ]
    for mutate in mutations:
        candidate=deepcopy(original)
        mutate(candidate)
        with pytest.raises(ValueError,match="configuration contract"):
            verify_documents(root,candidate)
```

- [ ] **Step 14: 运行配置身份红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_rejects_config_identity_drift -v
```

Expected: FAIL；至少 path、role 或额外字段变异没有得到 `configuration contract` 错误。

- [ ] **Step 15: 冻结完整配置 schema、身份、角色、路径与 hash**

```python
# insert before verify_documents() in tools/stage0a_sources/canonical.py
EXPECTED_DOCUMENTS={
    "adr_006":(
        "outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md",
        None,
        "EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6",
    ),
    "core_spec":(
        "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
        "core",
        "3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695",
    ),
    "baseline":(
        "outputs/Amadeus身份与记忆评测基线-v0.1.md",
        "baseline",
        "5C260EE19D9FF129633B968E87FACA79E93B7A01E3B86580E0FAD2DBC7147853",
    ),
    "increment":(
        "outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md",
        "increment",
        "16ACDB17717AFEA5B5C19F39E91729385DB59B984F35CEF5B651BE9EEE8A37FC",
    ),
    "plan_review":(
        "outputs/Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md",
        None,
        "865517363E5E3D6F2285BA30EDFC5C5405B0196E6007672E417F683C70995BED",
    ),
}
DOCUMENT_KEYS={"key","path","sha256","source_group"}

def _validated_document_items(root: Path, config: dict[str,Any]) -> list[dict[str,Any]]:
    if (
        not isinstance(config,dict)
        or set(config)!={"schema_version","documents"}
        or config.get("schema_version")!="0.1"
    ):
        raise ValueError("configuration contract: top-level schema")
    items=config.get("documents")
    if not isinstance(items,list) or len(items)!=len(EXPECTED_DOCUMENTS):
        raise ValueError("configuration contract: document count")
    by_key={}
    resolved_paths=set()
    root=root.resolve()
    for item in items:
        if not isinstance(item,dict) or set(item)!=DOCUMENT_KEYS:
            raise ValueError("configuration contract: document fields")
        key=item.get("key")
        if not isinstance(key,str):
            raise ValueError("configuration contract: document key type")
        if key in by_key:
            raise ValueError(f"configuration contract: duplicate key {key}")
        by_key[key]=item
    if set(by_key)!=set(EXPECTED_DOCUMENTS):
        raise ValueError("configuration contract: document keys")
    for key,(path,group,digest) in EXPECTED_DOCUMENTS.items():
        item=by_key[key]
        supplied_digest=item.get("sha256")
        if (
            not isinstance(supplied_digest,str)
            or (item.get("path"),item.get("source_group"),supplied_digest.upper())
            !=(path,group,digest)
        ):
            raise ValueError(f"configuration contract: identity {key}")
        resolved=(root/path).resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"configuration contract: path outside root {key}")
        if resolved in resolved_paths:
            raise ValueError(f"configuration contract: duplicate path {key}")
        resolved_paths.add(resolved)
    return [by_key[key] for key in EXPECTED_DOCUMENTS]
```

```python
# replace verify_documents() body
def verify_documents(root: Path, config: dict[str,Any]) -> dict[str,dict[str,Any]]:
    result={}
    for item in _validated_document_items(root,config):
        path=(root/item["path"]).resolve(strict=True)
        actual=_sha256_hex(path.read_bytes())
        expected=item["sha256"].upper()
        if actual!=expected:
            raise ValueError(f"document drift: {item['key']} expected={expected} actual={actual}")
        result[item["key"]]={
            "path":item["path"],
            "source_group":item["source_group"],
            "expected_sha256":expected,
            "actual_sha256":actual,
        }
    return dict(sorted(result.items()))
```

- [ ] **Step 16: 运行配置身份绿灯与 canonical 文件回归**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py::test_verify_documents_rejects_config_identity_drift -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_canonical.py -v
```

Expected: identity test `1 passed`；文件合计 `4 passed`。

- [ ] **Step 17: 提交 canonical 层**

```powershell
git add tools/stage0a_sources/canonical.py tests/stage0a/test_canonical.py
git commit -m "test: bind stage0a input fingerprints"
```

### Task 2：原始行提取与精确 ID 集

**Files:**
- Create: `tools/stage0a_sources/compiler.py`
- Test: `tests/stage0a/test_compiler.py`

- [ ] **Step 1: 写精确 ID 集失败测试**

```python
# tests/stage0a/test_compiler.py
import json
from pathlib import Path
from tools.stage0a_sources.canonical import _sha256_hex, canonical_bytes
from tools.stage0a_sources.compiler import compile_source_index

ROOT=Path(__file__).parents[2]
CONFIG_PATH=ROOT/"fixtures/stage0a/source_config_v0_1.json"
CONFIG_BYTES=CONFIG_PATH.read_bytes()
CONFIG=json.loads(CONFIG_BYTES)
CONFIG_SHA256=_sha256_hex(CONFIG_BYTES)

def test_exact_source_sets_are_frozen() -> None:
    index=compile_source_index(ROOT,CONFIG,CONFIG_SHA256)
    assert index["source_config_sha256"]==CONFIG_SHA256
    assert index["source_counts"]=={"baseline":53,"increment":66,"core":95}
    assert index["unique_source_count"]==214
    assert index["missing_source_ids"]==[]
    assert index["unexpected_source_ids"]==[]
    assert index["duplicate_source_ids"]==[]
```

- [ ] **Step 2: 运行精确 ID 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_exact_source_sets_are_frozen -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources.compiler`。

- [ ] **Step 3: 写只满足精确 ID 集的最小编译器**

```python
# tools/stage0a_sources/compiler.py
from __future__ import annotations
import re
from collections import Counter
from pathlib import Path
from typing import Any
from .canonical import verify_documents

def _ids(prefix: str, start: int, end: int, width: int=2) -> tuple[str,...]:
    return tuple(f"{prefix}-{number:0{width}d}" for number in range(start,end+1))

EXPECTED_IDS={
    "baseline": (
        _ids("ID",1,6)+_ids("SRC",1,6)+_ids("GROW",1,6)+_ids("MEM",1,8)+
        _ids("TIME",1,6)+_ids("USE",1,5)+_ids("SEC",1,6)+_ids("DEL",1,5)+_ids("BR",1,5)
    ),
    "increment": (
        _ids("PRO",1,12)+_ids("COR",1,8)+_ids("TOOL",1,14)+
        _ids("INJ",1,10)+_ids("REL",1,12)+_ids("EXIT",1,10)
    ),
    "core":_ids("AC",1,95,width=3),
}
FRAME=re.compile(r"^\[FRAME\]\s*")
SOURCE_ID=re.compile(r"^[A-Z]+-[0-9]{2,3}$")

def _normalized_cell(cell: str) -> str:
    return FRAME.sub("",cell.strip()).strip()

def _raw_cells(line: str) -> list[str]:
    if not line.lstrip().startswith("|"):
        return []
    return line[line.index("|")+1:line.rindex("|")].split("|")

def _candidate_rows(root: Path, document: dict[str,Any]):
    path=root/document["path"]
    for line_number,line in enumerate(path.read_text(encoding="utf-8").splitlines(),start=1):
        cells=_raw_cells(line)
        if len(cells)!=4:
            continue
        source_id=_normalized_cell(cells[0])
        if SOURCE_ID.fullmatch(source_id):
            yield line_number,line,cells,source_id

def compile_source_index(
    root: Path,
    config: dict[str,Any],
    source_config_sha256: str,
) -> dict[str,Any]:
    if not re.fullmatch(r"[0-9A-F]{64}",source_config_sha256):
        raise ValueError("source config digest must be uppercase SHA-256")
    documents=verify_documents(root,config)
    rows=[]
    for item in config["documents"]:
        if item["source_group"] is None:
            continue
        document={**item,"actual_sha256":documents[item["key"]]["actual_sha256"]}
        for line_number,line,cells,source_id in _candidate_rows(root,document):
            rows.append({"source_id":source_id,"source_group":item["source_group"]})
    actual_by_group={
        group:{row["source_id"] for row in rows if row["source_group"]==group}
        for group in EXPECTED_IDS
    }
    missing=sorted(
        source_id for group,expected in EXPECTED_IDS.items()
        for source_id in set(expected)-actual_by_group[group]
    )
    unexpected=sorted(
        source_id for group,actual in actual_by_group.items()
        for source_id in actual-set(EXPECTED_IDS[group])
    )
    counts=Counter(row["source_id"] for row in rows)
    duplicates=sorted(source_id for source_id,count in counts.items() if count!=1)
    if missing or unexpected or duplicates:
        raise ValueError(
            f"source set drift: missing={missing} "
            f"unexpected={unexpected} duplicate={duplicates}"
        )
    return {
        "schema_version":"0.1",
        "source_config_sha256":source_config_sha256,
        "input_documents":documents,
        "source_counts":{
            group:len(actual_by_group[group])
            for group in ("baseline","increment","core")
        },
        "unique_source_count":len(rows),
        "missing_source_ids":missing,
        "unexpected_source_ids":unexpected,
        "duplicate_source_ids":duplicates,
        "sources":sorted(rows,key=lambda row:row["source_id"]),
    }
```

- [ ] **Step 4: 运行精确 ID 集绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_exact_source_sets_are_frozen -v
```

Expected: `1 passed`。

- [ ] **Step 5: 写原文与摘要绑定失败测试**

```python
# append tests/stage0a/test_compiler.py
def test_every_source_preserves_and_binds_raw_evidence() -> None:
    index=compile_source_index(ROOT,CONFIG,CONFIG_SHA256)
    for row in index["sources"]:
        source_lines=(ROOT/row["document_path"]).read_text(encoding="utf-8").splitlines()
        raw_line=source_lines[row["line_number"]-1]
        first=raw_line.index("|")
        last=raw_line.rindex("|")
        assert row["raw_line"]==raw_line
        assert row["raw_cells"]==raw_line[first+1:last].split("|")
        assert row["raw_row_sha256"]==_sha256_hex(raw_line.encode("utf-8"))
        assert row["source_binding_sha256"]==_sha256_hex(canonical_bytes({
            "document_sha256":row["document_sha256"],
            "line_number":row["line_number"],
            "raw_line":raw_line,
        }))
        assert row["raw_row_sha256"]!=_sha256_hex((raw_line+" ").encode("utf-8"))
```

- [ ] **Step 6: 运行原文绑定红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_every_source_preserves_and_binds_raw_evidence -v
```

Expected: FAIL，首行在访问 `document_path` 时得到 `KeyError`。

- [ ] **Step 7: 增加原始证据与摘要绑定**

```python
# replace canonical import in tools/stage0a_sources/compiler.py
from .canonical import _sha256_hex, canonical_bytes, verify_documents

# add internal helper
def _raw_source_row(
    document: dict[str,Any],
    line_number: int,
    line: str,
    cells: list[str],
    source_id: str,
) -> dict[str,Any]:
    return {
        "source_id":source_id,
        "source_group":document["source_group"],
        "document_key":document["key"],
        "document_path":document["path"],
        "document_sha256":document["actual_sha256"],
        "line_number":line_number,
        "raw_line":line,
        "raw_cells":cells,
        "raw_row_sha256":_sha256_hex(line.encode("utf-8")),
        "source_binding_sha256":_sha256_hex(canonical_bytes({
            "document_sha256":document["actual_sha256"],
            "line_number":line_number,
            "raw_line":line,
        })),
    }
```

```python
# replace the rows.append(...) line inside compile_source_index()
rows.append(_raw_source_row(document,line_number,line,cells,source_id))
```

- [ ] **Step 8: 运行原文绑定绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_every_source_preserves_and_binds_raw_evidence -v
```

Expected: `1 passed`。

- [ ] **Step 9: 写 Core 未声明 oracle 失败测试**

```python
# append tests/stage0a/test_compiler.py
def test_core_oracle_remains_undeclared() -> None:
    index=compile_source_index(ROOT,CONFIG,CONFIG_SHA256)
    core=[row for row in index["sources"] if row["source_group"]=="core"]
    assert len(core)==95
    assert all(row["normalized"]["raw_oracle_tokens"]==[] for row in core)
    assert all(row["normalized"]["canonical_oracle_kinds"]==[] for row in core)
    assert all(row["normalized"]["oracle_provenance"]=="undeclared" for row in core)
```

- [ ] **Step 10: 运行 Core oracle 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_core_oracle_remains_undeclared -v
```

Expected: FAIL，首个 Core 行在访问 `normalized` 时得到 `KeyError`。

- [ ] **Step 11: 增加 Core 规范字段与 undeclared provenance**

```python
# add internal helper to tools/stage0a_sources/compiler.py
def _core_normalized(cells: list[str]) -> dict[str,Any]:
    normalized=[_normalized_cell(cell) for cell in cells]
    return {
        "title":normalized[1],
        "scenario":None,
        "action":normalized[2],
        "expected":normalized[3],
        "raw_oracle_tokens":[],
        "canonical_oracle_kinds":[],
        "oracle_provenance":"undeclared",
    }
```

```python
# replace the rows.append(...) line inside compile_source_index()
row=_raw_source_row(document,line_number,line,cells,source_id)
if item["source_group"]=="core":
    row["normalized"]=_core_normalized(cells)
rows.append(row)
```

- [ ] **Step 12: 运行 Core oracle 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_core_oracle_remains_undeclared -v
```

Expected: `1 passed`。

- [ ] **Step 13: 写行为裁判分布失败测试**

```python
# append tests/stage0a/test_compiler.py
from collections import Counter

def test_behavior_oracle_combinations_are_frozen() -> None:
    index=compile_source_index(ROOT,CONFIG,CONFIG_SHA256)
    by_group={}
    for group in ("baseline","increment"):
        by_group[group]=Counter(
            "+".join(row["normalized"]["raw_oracle_tokens"])
            for row in index["sources"] if row["source_group"]==group
        )
    assert by_group["baseline"]=={"D":30,"D+H":20,"H":2,"H+L":1}
    assert by_group["increment"]=={"D":18,"D+H":18,"D+S":23,"H":4,"H+J":3}
```

- [ ] **Step 14: 运行行为裁判分布红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_behavior_oracle_combinations_are_frozen -v
```

Expected: FAIL，首个行为行在访问 `normalized` 时得到 `KeyError`。

- [ ] **Step 15: 增加行为 oracle 解析与冻结分布**

```python
# add internal helper to tools/stage0a_sources/compiler.py
def _behavior_normalized(cells: list[str], source_id: str) -> dict[str,Any]:
    normalized=[_normalized_cell(cell) for cell in cells]
    raw_tokens=tuple(token.strip() for token in normalized[3].split("+"))
    aliases={"D":"D","S":"S","H":"H","L":"J","J":"J"}
    if any(token not in aliases for token in raw_tokens):
        raise ValueError(f"unknown oracle token: {source_id} {raw_tokens}")
    kinds={aliases[token] for token in raw_tokens}
    return {
        "title":None,
        "scenario":normalized[1],
        "action":None,
        "expected":normalized[2],
        "raw_oracle_tokens":list(raw_tokens),
        "canonical_oracle_kinds":[kind for kind in ("D","S","H","J") if kind in kinds],
        "oracle_provenance":"source_declared",
    }
```

```python
# replace the Core-only normalized branch inside compile_source_index()
row=_raw_source_row(document,line_number,line,cells,source_id)
row["normalized"]=(
    _core_normalized(cells)
    if item["source_group"]=="core"
    else _behavior_normalized(cells,source_id)
)
rows.append(row)
```

```python
# insert before compile_source_index() returns
behavior_oracle_combinations={}
expected_combinations={
    "baseline":{"D":30,"D+H":20,"H":2,"H+L":1},
    "increment":{"D":18,"D+H":18,"D+S":23,"H":4,"H+J":3},
}
for group in ("baseline","increment"):
    observed=Counter(
        "+".join(row["normalized"]["raw_oracle_tokens"])
        for row in rows if row["source_group"]==group
    )
    behavior_oracle_combinations[group]=dict(sorted(observed.items()))
if behavior_oracle_combinations!=expected_combinations:
    raise ValueError(f"oracle combination drift: {behavior_oracle_combinations}")
```

```diff
 # add this field to the returned source index
+"behavior_oracle_combinations":behavior_oracle_combinations,
```

- [ ] **Step 16: 运行行为裁判分布绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_behavior_oracle_combinations_are_frozen -v
```

Expected: `1 passed`。


- [ ] **Step 17: 运行 compiler 文件回归**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_exact_source_sets_are_frozen -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_core_oracle_remains_undeclared -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_every_source_preserves_and_binds_raw_evidence -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py::test_behavior_oracle_combinations_are_frozen -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_compiler.py -v
```

Expected: 四个测试合计 `4 passed`。

- [ ] **Step 18: 提交 compiler**

```powershell
git add tools/stage0a_sources/compiler.py tests/stage0a/test_compiler.py
git commit -m "test: compile exact stage0a source ledger"
```

### Task 3：生成两份显式 pending 工作表

**Files:**
- Create: `tools/stage0a_sources/worklists.py`
- Test: `tests/stage0a/test_worklists.py`

- [ ] **Step 1: 写 oracle worklist 失败测试**

```python
# tests/stage0a/test_worklists.py
import json
from pathlib import Path
from tools.stage0a_sources.compiler import compile_source_index
from tools.stage0a_sources.worklists import build_oracle_worklist

ROOT=Path(__file__).parents[2]
CONFIG_BYTES=(ROOT/"fixtures/stage0a/source_config_v0_1.json").read_bytes()
CONFIG=json.loads(CONFIG_BYTES)
from tools.stage0a_sources.canonical import _sha256_hex
CONFIG_SHA256=_sha256_hex(CONFIG_BYTES)

def test_oracle_worklist_preserves_provenance() -> None:
    worklist=build_oracle_worklist(compile_source_index(ROOT,CONFIG,CONFIG_SHA256))
    assert len(worklist["items"])==214
    assert worklist["source_declared_count"]==119
    assert worklist["pending_assignment_count"]==95
    assert all(item["review_state"]=="pending_assignment" for item in worklist["items"] if item["source_group"]=="core")
```

- [ ] **Step 2: 运行 oracle worklist 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_worklists.py::test_oracle_worklist_preserves_provenance -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources.worklists`。

- [ ] **Step 3: 写 oracle worklist**

```python
# tools/stage0a_sources/worklists.py
from typing import Any

def build_oracle_worklist(index: dict[str,Any]) -> dict[str,Any]:
    items=[]
    for source in index["sources"]:
        normalized=source["normalized"]
        declared=normalized["oracle_provenance"]=="source_declared"
        items.append({
            "source_id":source["source_id"],
            "source_group":source["source_group"],
            "source_binding_sha256":source["source_binding_sha256"],
            "review_state":"source_declared" if declared else "pending_assignment",
            "source_oracle_tokens":normalized["raw_oracle_tokens"],
            "canonical_oracle_kinds":normalized["canonical_oracle_kinds"],
            "assigned_oracle_kinds":normalized["canonical_oracle_kinds"] if declared else [],
            "rationale":"source table oracle column" if declared else None,
        })
    return {
        "schema_version":"0.1",
        "source_declared_count":sum(item["review_state"]=="source_declared" for item in items),
        "pending_assignment_count":sum(item["review_state"]=="pending_assignment" for item in items),
        "items":items,
    }
```

- [ ] **Step 4: 运行 oracle worklist 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_worklists.py::test_oracle_worklist_preserves_provenance -v
```

Expected: `1 passed`。

- [ ] **Step 5: 写 atomicity worklist 失败测试**

```python
# append tests/stage0a/test_worklists.py
from tools.stage0a_sources.worklists import build_atomicity_worklist

def test_atomicity_worklist_has_no_implicit_decisions() -> None:
    worklist=build_atomicity_worklist(compile_source_index(ROOT,CONFIG,CONFIG_SHA256))
    assert len(worklist["items"])==214
    assert worklist["pending_review_count"]==214
    assert all(item["review_state"]=="pending_review" for item in worklist["items"])
    assert all(item["atomicity_decision"] is None for item in worklist["items"])
    assert all(item["clauses"]==[] for item in worklist["items"])
```

- [ ] **Step 6: 运行 atomicity worklist 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_worklists.py::test_atomicity_worklist_has_no_implicit_decisions -v
```

Expected: FAIL，`ImportError: cannot import name 'build_atomicity_worklist'`。

- [ ] **Step 7: 写 atomicity worklist**

```python
# append tools/stage0a_sources/worklists.py
def build_atomicity_worklist(index: dict[str,Any]) -> dict[str,Any]:
    items=[{
        "source_id":source["source_id"],
        "source_group":source["source_group"],
        "source_binding_sha256":source["source_binding_sha256"],
        "scenario_or_title":source["normalized"]["scenario"] or source["normalized"]["title"],
        "action":source["normalized"]["action"],
        "expected":source["normalized"]["expected"],
        "review_state":"pending_review",
        "atomicity_decision":None,
        "rationale":None,
        "clauses":[],
    } for source in index["sources"]]
    return {"schema_version":"0.1","pending_review_count":len(items),"items":items}
```

- [ ] **Step 8: 运行 worklists 文件绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_worklists.py -v
```

Expected: `2 passed`。

- [ ] **Step 9: 提交 worklists**

```powershell
git add tools/stage0a_sources/worklists.py tests/stage0a/test_worklists.py
git commit -m "test: generate explicit stage0b review worklists"
```

### Task 4：完整 write/check CLI 与 readiness 报告

**Files:**
- Create: `tools/stage0a_sources/cli.py`
- Test: `tests/stage0a/test_cli.py`
- Create: `fixtures/stage0a/generated/source_index_v0_1.json`
- Create: `fixtures/stage0a/generated/oracle_assignment_worklist_v0_1.json`
- Create: `fixtures/stage0a/generated/atomicity_worklist_v0_1.json`
- Create: `fixtures/stage0a/generated/source_toolchain_report_v0_1.json`

- [ ] **Step 1: 写 write/check 失败测试**

```python
# tests/stage0a/test_cli.py
import json
import shutil
from pathlib import Path
import pytest
from tools.stage0a_sources.cli import main

SOURCE_ROOT=Path(__file__).parents[2]
CONFIG_REL=Path("fixtures/stage0a/source_config_v0_1.json")

def _copy_frozen_root(parent: Path) -> Path:
    root=parent/"root"
    config=json.loads((SOURCE_ROOT/CONFIG_REL).read_text(encoding="utf-8"))
    paths=[CONFIG_REL]+[Path(item["path"]) for item in config["documents"]]
    for relative in paths:
        target=root/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SOURCE_ROOT/relative,target)
    return root

def test_write_then_check_are_byte_stable(tmp_path: Path) -> None:
    output=tmp_path/"generated"
    assert main(["write","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==0
    before={path.name:path.read_bytes() for path in output.glob("*.json")}
    assert main(["check","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==0
    after={path.name:path.read_bytes() for path in output.glob("*.json")}
    assert before==after
    assert set(before)=={
        "source_index_v0_1.json",
        "oracle_assignment_worklist_v0_1.json",
        "atomicity_worklist_v0_1.json",
        "source_toolchain_report_v0_1.json",
    }
```

- [ ] **Step 2: 运行 CLI 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_write_then_check_are_byte_stable -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources.cli`。

- [ ] **Step 3: 写只满足稳定 write/check 的最小 CLI**

```python
# tools/stage0a_sources/cli.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Sequence
from .canonical import _sha256_hex, canonical_bytes
from .compiler import compile_source_index
from .worklists import build_atomicity_worklist, build_oracle_worklist

FILES={
    "source_index_v0_1.json":"source_index",
    "oracle_assignment_worklist_v0_1.json":"oracle",
    "atomicity_worklist_v0_1.json":"atomicity",
    "source_toolchain_report_v0_1.json":"report",
}
CONFIG_PATH=Path("fixtures/stage0a/source_config_v0_1.json")

def _read_config(root: Path) -> tuple[dict,str]:
    config=json.loads((root/CONFIG_PATH).read_text(encoding="utf-8"))
    return config,_sha256_hex(canonical_bytes(config))

def _build_artifacts(root: Path) -> dict[str,dict]:
    config,config_sha256=_read_config(root)
    source_index=compile_source_index(root,config,config_sha256)
    oracle=build_oracle_worklist(source_index)
    atomicity=build_atomicity_worklist(source_index)
    ready=(
        source_index["source_counts"]=={"baseline":53,"increment":66,"core":95}
        and source_index["unique_source_count"]==214
        and source_index["missing_source_ids"]==[]
        and source_index["unexpected_source_ids"]==[]
        and source_index["duplicate_source_ids"]==[]
        and oracle["source_declared_count"]==119
        and oracle["pending_assignment_count"]==95
        and atomicity["pending_review_count"]==214
    )
    if not ready:
        raise ValueError("source toolchain readiness invariant failed")
    report={
        "schema_version":"0.1",
        "source_config_sha256":config_sha256,
        "source_toolchain_ready":ready,
        "unique_source_count":source_index["unique_source_count"],
        "pending_oracle_assignments":oracle["pending_assignment_count"],
        "pending_atomicity_reviews":atomicity["pending_review_count"],
        "atomicity_complete":False,
        "case_coverage_complete":False,
        "catalog_ready":False,
        "release_ready":False,
    }
    return {"source_index":source_index,"oracle":oracle,"atomicity":atomicity,"report":report}

def _encoded_artifacts(root: Path) -> dict[str,bytes]:
    artifacts=_build_artifacts(root)
    return {name:canonical_bytes(artifacts[key])+b"\n" for name,key in FILES.items()}

def main(argv: Sequence[str]|None=None) -> int:
    parser=argparse.ArgumentParser(prog="amadeus-stage0a")
    parser.add_argument("command",choices=("write","check"))
    parser.add_argument("--root",type=Path,default=Path("."))
    parser.add_argument("--output-dir",type=Path,default=Path("fixtures/stage0a/generated"))
    args=parser.parse_args(argv)
    root=args.root.resolve()
    output_dir=args.output_dir if args.output_dir.is_absolute() else root/args.output_dir
    expected=_encoded_artifacts(root)
    if args.command=="write":
        output_dir.mkdir(parents=True,exist_ok=True)
        for name,data in expected.items():
            (output_dir/name).write_bytes(data)
        return 0
    if not output_dir.is_dir() or any(
        not (output_dir/name).is_file() for name in expected
    ):
        print("artifact_drift=missing")
        return 1
    print("source_toolchain_ready=true")
    print("pending_oracle_assignments=95")
    print("pending_atomicity_reviews=214")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行稳定 write/check 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_write_then_check_are_byte_stable -v
```

Expected: `1 passed`。

- [ ] **Step 5: 写生成工件内容漂移失败测试**

```python
# append tests/stage0a/test_cli.py
def test_check_reports_generated_artifact_drift(tmp_path: Path) -> None:
    output=tmp_path/"generated"
    assert main(["write","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==0
    (output/"source_index_v0_1.json").write_text("{}\n",encoding="utf-8")
    assert main(["check","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==1
```

- [ ] **Step 6: 运行生成内容漂移红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_reports_generated_artifact_drift -v
```

Expected: FAIL；最小 CLI 返回 0，而测试要求 1。

- [ ] **Step 7: 增加已知工件内容比较**

```diff
# replace the existence-only check at the end of main()
missing=sorted(
    name for name in expected
    if not (output_dir/name).is_file()
)
changed=sorted(
    name for name,data in expected.items()
    if (output_dir/name).is_file() and (output_dir/name).read_bytes()!=data
)
if missing or changed:
    print(
        "artifact_drift="
        f"missing:{','.join(missing)};"
        f"changed:{','.join(changed)}"
    )
    return 1
```

- [ ] **Step 8: 运行生成内容漂移绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_reports_generated_artifact_drift -v
```

Expected: `1 passed`。

- [ ] **Step 9: 写额外生成条目失败测试**

```python
# append tests/stage0a/test_cli.py
def test_check_rejects_unexpected_generated_entry(tmp_path: Path) -> None:
    output=tmp_path/"generated"
    assert main(["write","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==0
    (output/"obsolete_v0_0.json").write_text("{}\n",encoding="utf-8")
    assert main(["check","--root",str(SOURCE_ROOT),"--output-dir",str(output)])==1
```

- [ ] **Step 10: 运行额外条目红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_rejects_unexpected_generated_entry -v
```

Expected: FAIL；只检查已知文件的 CLI 返回 0，而测试要求 1。

- [ ] **Step 11: 封闭输出目录文件名集合**

```diff
# replace missing/changed calculation at the end of main()
actual_names={path.name for path in output_dir.iterdir()} if output_dir.is_dir() else set()
expected_names=set(expected)
missing=sorted(expected_names-actual_names)
unexpected=sorted(actual_names-expected_names)
changed=sorted(
    name for name,data in expected.items()
    if name in actual_names and (
        not (output_dir/name).is_file() or (output_dir/name).read_bytes()!=data
    )
)
if missing or unexpected or changed:
    print(
        "artifact_drift="
        f"missing:{','.join(missing)};"
        f"changed:{','.join(changed)};"
        f"unexpected:{','.join(unexpected)}"
    )
    return 1
```

- [ ] **Step 12: 运行额外条目绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_rejects_unexpected_generated_entry -v
```

Expected: `1 passed`。

- [ ] **Step 13: 写配置原始字节漂移失败测试**

```python
# append tests/stage0a/test_cli.py
def test_check_binds_raw_config_bytes(tmp_path: Path) -> None:
    root=_copy_frozen_root(tmp_path)
    output=tmp_path/"generated"
    assert main(["write","--root",str(root),"--output-dir",str(output)])==0
    config_path=root/CONFIG_REL
    config_path.write_bytes(config_path.read_bytes()+b"\n")
    assert main(["check","--root",str(root),"--output-dir",str(output)])==1
```

- [ ] **Step 14: 运行配置字节漂移红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_binds_raw_config_bytes -v
```

Expected: FAIL；配置只变化空白时，semantic config hash 不变，CLI 返回 0。

- [ ] **Step 15: 将配置摘要切换为原始字节 SHA-256**

```python
# replace _read_config() in tools/stage0a_sources/cli.py
def _read_config(root: Path) -> tuple[dict,str]:
    raw=(root/CONFIG_PATH).read_bytes()
    return json.loads(raw.decode("utf-8")),_sha256_hex(raw)
```

- [ ] **Step 16: 运行配置字节漂移绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_check_binds_raw_config_bytes -v
```

Expected: `1 passed`。

- [ ] **Step 17: 写 CLI 输入漂移与原子写保护失败测试**

```python
# append tests/stage0a/test_cli.py
@pytest.mark.parametrize("command",["write","check"])
def test_document_input_drift_returns_2_without_touching_outputs(
    tmp_path: Path,
    command: str,
) -> None:
    root=_copy_frozen_root(tmp_path)
    output=tmp_path/"generated"
    assert main(["write","--root",str(root),"--output-dir",str(output)])==0
    before={path.name:path.read_bytes() for path in output.iterdir()}
    config=json.loads((root/CONFIG_REL).read_text(encoding="utf-8"))
    document=root/config["documents"][0]["path"]
    document.write_bytes(document.read_bytes()+b" ")
    assert main([command,"--root",str(root),"--output-dir",str(output)])==2
    assert before=={path.name:path.read_bytes() for path in output.iterdir()}

@pytest.mark.parametrize("command",["write","check"])
def test_config_identity_drift_returns_2_without_touching_outputs(
    tmp_path: Path,
    command: str,
) -> None:
    root=_copy_frozen_root(tmp_path)
    output=tmp_path/"generated"
    assert main(["write","--root",str(root),"--output-dir",str(output)])==0
    before={path.name:path.read_bytes() for path in output.iterdir()}
    config_path=root/CONFIG_REL
    config=json.loads(config_path.read_text(encoding="utf-8"))
    config["documents"][1]["source_group"]="increment"
    config_path.write_text(json.dumps(config,ensure_ascii=False),encoding="utf-8")
    assert main([command,"--root",str(root),"--output-dir",str(output)])==2
    assert before=={path.name:path.read_bytes() for path in output.iterdir()}
```

- [ ] **Step 18: 分别运行两类输入漂移红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_document_input_drift_returns_2_without_touching_outputs -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_config_identity_drift_returns_2_without_touching_outputs -v
```

Expected: 两次均 FAIL；严格验证器抛出的 `ValueError` 尚未被 CLI 转为退出码 2。

- [ ] **Step 19: 在任何写入前统一映射输入错误**

```diff
# replace the expected-artifact assignment inside main()
try:
    expected=_encoded_artifacts(root)
except (OSError,ValueError) as exc:
    print(f"input_error={exc}")
    return 2
```

- [ ] **Step 20: 运行两类输入漂移绿灯与 CLI 文件回归**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_document_input_drift_returns_2_without_touching_outputs -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py::test_config_identity_drift_returns_2_without_touching_outputs -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_cli.py -v
```

Expected: 两个参数化测试各 `2 passed`；文件合计 `8 passed`。


- [ ] **Step 21: 生成仓库工件并检查**

```powershell
.venv\Scripts\python.exe -m tools.stage0a_sources.cli write
.venv\Scripts\python.exe -m tools.stage0a_sources.cli check
```

Expected:

```text
source_toolchain_ready=true
pending_oracle_assignments=95
pending_atomicity_reviews=214
```

- [ ] **Step 22: 提交 CLI 与工件**

```powershell
git add tools/stage0a_sources/cli.py tests/stage0a/test_cli.py fixtures/stage0a/generated
git commit -m "test: write and check stage0a source artifacts"
```

### Task 5：最小 import allowlist 与最终验证

**Files:**
- Create: `tools/stage0a_sources/transport_gate.py`
- Test: `tests/stage0a/test_transport_gate.py`

- [ ] **Step 1: 写 import allowlist 失败测试**

```python
# tests/stage0a/test_transport_gate.py
from pathlib import Path
from tools.stage0a_sources.transport_gate import check_imports

def test_package_uses_minimum_import_allowlist() -> None:
    assert check_imports(Path("tools/stage0a_sources"))==[]
```

- [ ] **Step 2: 运行 allowlist 红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_transport_gate.py -v
```

Expected: FAIL，`ModuleNotFoundError: tools.stage0a_sources.transport_gate`。

- [ ] **Step 3: 写只检查绝对与动态 import 的最小门禁**

```python
# tools/stage0a_sources/transport_gate.py
import ast
from pathlib import Path

ALLOWED_ROOTS={
    "__future__","argparse","ast","collections","hashlib","json",
    "pathlib","re","typing",
}

def check_imports(package: Path) -> list[str]:
    violations=[]
    for path in sorted(package.rglob("*.py")):
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                names=[alias.name for alias in node.names]
            elif isinstance(node,ast.ImportFrom) and node.level==0 and node.module:
                names=[node.module]
            else:
                names=[]
            for name in names:
                if name.split(".",1)[0] not in ALLOWED_ROOTS:
                    violations.append(f"{path.as_posix()}:{node.lineno}:{name}")
            if (
                isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name)
                and node.func.id=="__import__"
            ):
                violations.append(f"{path.as_posix()}:{node.lineno}:dynamic-import")
            if (
                isinstance(node,ast.Call)
                and isinstance(node.func,ast.Attribute)
                and node.func.attr=="import_module"
            ):
                violations.append(f"{path.as_posix()}:{node.lineno}:dynamic-import")
    return violations
```

- [ ] **Step 4: 运行当前 package allowlist 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_transport_gate.py::test_package_uses_minimum_import_allowlist -v
```

Expected: `1 passed`。

- [ ] **Step 5: 写父级相对导入逃逸失败测试**

```python
# append tests/stage0a/test_transport_gate.py
def test_gate_rejects_parent_relative_and_project_absolute_imports(tmp_path: Path) -> None:
    package=tmp_path/"stage0a_sources"
    package.mkdir()
    (package/"bad.py").write_text(
        "from ..sibling import hidden\nimport tools.sibling\n",
        encoding="utf-8",
    )
    violations=check_imports(package)
    assert any(item.endswith(":1:relative-parent") for item in violations)
    assert any(item.endswith(":2:tools.sibling") for item in violations)
```

- [ ] **Step 6: 运行导入逃逸红灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_transport_gate.py::test_gate_rejects_parent_relative_and_project_absolute_imports -v
```

Expected: FAIL；`tools.sibling` 已被报告，但 `relative-parent` 尚未出现。

- [ ] **Step 7: 拒绝越出当前 package 的父级相对导入**

```diff
 # insert before the final else branch in check_imports()
+elif isinstance(node,ast.ImportFrom) and node.level==1:
+    names=[]
+elif isinstance(node,ast.ImportFrom) and node.level>1:
+    violations.append(f"{path.as_posix()}:{node.lineno}:relative-parent")
+    names=[]
```

- [ ] **Step 8: 运行两个 allowlist 绿灯**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a/test_transport_gate.py::test_package_uses_minimum_import_allowlist -v
.venv\Scripts\python.exe -m pytest tests/stage0a/test_transport_gate.py::test_gate_rejects_parent_relative_and_project_absolute_imports -v
```

Expected: 两个单测各 `1 passed`。

- [ ] **Step 9: 运行全套验证**

```powershell
.venv\Scripts\python.exe -m pytest tests/stage0a -v
.venv\Scripts\python.exe -m tools.stage0a_sources.cli check
```

Expected:

```text
all tests passed
source_toolchain_ready=true
pending_oracle_assignments=95
pending_atomicity_reviews=214
```

- [ ] **Step 10: 提交最终门禁**

```powershell
git add tools/stage0a_sources/transport_gate.py tests/stage0a/test_transport_gate.py
git commit -m "test: enforce stage0a import allowlist"
git status --short
```

Expected: `git status --short` 为空。

## 8. 自检记录

- [COMPUTED｜置信度：高] 本计划没有把 95 个 Core 来源伪称为 D；它们保持 undeclared/pending。
- [COMPUTED｜置信度：高] 五份输入的精确 key/path/role/hash 均进入不可替换合同；配置原始字节 hash 同时进入 source index 与 report。
- [COMPUTED｜置信度：高] 每个来源保留原始行、原始单元格、路径、文档 hash 与行号；测试从原文件回读并重算两类摘要。
- [COMPUTED｜置信度：高] 来源完整性使用精确 ID set，不只使用计数。
- [COMPUTED｜置信度：高] CLI 直到所有依赖模块完成后才创建；之前的任务不调用 CLI。
- [COMPUTED｜置信度：高] 所有 public helper 均在首次调用所属 Task 中给出实现。
- [COMPUTED｜置信度：高] Import allowlist 是最小正向集合；包内依赖只走相对 import，未开放 `tools` 根。
- [COMPUTED｜置信度：高] `check` 对 expected/missing/changed/unexpected 输出集合封闭，并将相对输出目录解析到 `--root` 下。
- [COMPUTED｜置信度：高] Readiness 报告明确区分 toolchain ready 与四类未完成状态。

## 9. 下一份计划的确定输入

[FRAME｜置信度：高] Stage 0B 计划只在以下四个 SHA-256 已冻结后编写：source index、oracle worklist、atomicity worklist、source toolchain report。它必须逐条列出 214 行人工裁决或从 reviewed manifest 确定性生成叶级 checklist，禁止再次用一句话概括剩余来源。

[FRAME｜置信度：高] Stage 0C 的 case-conversion binding 必须绑定 `clause_id/source_binding_sha256/clause_stimulus_sha256/clause_expected_sha256/case_sha256/stimulus_mapping/assertion_or_rubric_mapping/reviewer/rationale`；这项要求保留到 0C，不在 0A 伪装为已完成。

[我打破的规则 / RULES I BROKE]：无。
