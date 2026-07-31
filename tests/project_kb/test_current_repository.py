import hashlib
import json
import re
import shutil
import subprocess
import tomllib
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.project_kb.cli import main


ROOT = Path(__file__).resolve().parents[2]
_MARKDOWN_LINK = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")


def test_project_kb_console_script_is_registered() -> None:
    configuration = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert configuration["project"]["scripts"]["amadeus-project-kb"] == (
        "tools.project_kb.cli:main"
    )


def test_current_manifest_is_complete_and_ready(capsys) -> None:
    assert main(["--root", str(ROOT), "check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "project_kb_ready=true",
        "indexed_documents=34",
        "raw_paths_indexed=0",
    ]

    manifest = json.loads(
        (ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8")
    )
    paths = [document["path"] for document in manifest["documents"]]
    assert len(paths) == 34
    assert len(set(paths)) == 34
    assert all(document["index"] is True for document in manifest["documents"])
    assert not any(path.startswith("knowledge/90_raw/") for path in paths)


def test_current_readme_and_authority_document_are_searchable(capsys) -> None:
    assert main([
        "--root",
        str(ROOT),
        "search",
        "权威本地目录",
    ]) == 0
    readme_output = capsys.readouterr().out.splitlines()
    assert any(line.startswith("README.md:") for line in readme_output)

    assert main([
        "--root",
        str(ROOT),
        "search",
        "TerminationExecutionGrant",
        "--limit",
        "100",
    ]) == 0
    authority_output = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(
            "outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md:"
        )
        for line in authority_output
    )


def test_stage0a_fenced_comment_is_not_reported_as_a_heading(capsys) -> None:
    assert main([
        "--root",
        str(ROOT),
        "search",
        "# pyproject.toml",
        "--limit",
        "5",
    ]) == 0
    output = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith(
            "outputs/Amadeus-Core-v0.1-Stage0-场景夹具实施计划.md:180"
        )
        and " | Task 0：受控环境、配置与 import contract | "
        "# pyproject.toml" in line
        for line in output
    )


def test_handoff_markdown_relative_links_exist() -> None:
    for source in (ROOT / "README.md", ROOT / "knowledge" / "data_structure.md"):
        text = source.read_text(encoding="utf-8")
        for raw_target in _MARKDOWN_LINK.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or target.startswith("#"):
                continue
            relative = unquote(parsed.path)
            assert relative
            resolved = (source.parent / relative).resolve()
            resolved.relative_to(ROOT.resolve())
            assert resolved.exists(), f"missing link target: {source}: {target}"


STAGE0C_APPROVED_DRAFT_PLAN_SHA256 = "777A4FFDC327D8D5210B3BDCB0FF1F840F48A8C780252B9207676D1ED287CCE9"
STAGE0C_APPROVED_FROZEN_PLAN_SHA256 = "D42258FB05AD818FE94409AA11FE4FDB9C163E437A30FCCC636CDCA043939069"
STAGE0C_APPROVED_REVIEW_SHA256 = "DC1C3E27A4C10103D814F5B3E4C0E375A99F5E7E29E17116ADFD0076A6C3FD72"


def test_stage0c_plan_is_frozen_and_review_is_approved() -> None:
    plan_path = (
        ROOT / "outputs" / "Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md"
    )
    review_path = (
        ROOT
        / "outputs"
        / "Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md"
    )
    plan_raw = plan_path.read_bytes()
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_FROZEN_PLAN_SHA256,
    )
    assert hashlib.sha256(plan_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_FROZEN_PLAN_SHA256
    )
    plan_text = plan_raw.decode("utf-8")
    assert plan_text.encode("utf-8") == plan_raw
    assert plan_text.endswith("\n")
    assert "\r" not in plan_text
    assert not any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in plan_text
        if character != "\n"
    )

    fence_open_pattern = re.compile(
        r"`{3}(?P<info>markdown|text|python|powershell|gitattributes|json)?"
    )
    fence_token_pattern = re.compile(r"`{3,}|~{3,}")
    container_prefix_pattern = re.compile(
        r"[ \t]*(?:"
        r">[ \t]*|"
        r"[*+\-](?:[ \t]+|$)|"
        r"[0-9]{1,9}[.)](?:[ \t]+|$)"
        r")"
    )
    atx_heading_marker_pattern = re.compile(
        r"[ \t]*(#{1,6})(?!#)(?=[ \t]|$)"
    )
    canonical_heading_pattern = re.compile(
        r"(#{1,6})[ \t]+(?=\S)[^\r\n]*\S"
    )
    raw_html_tag_pattern = re.compile(
        r"[ \t]*</?[A-Za-z][^\r\n]*>",
        flags=re.IGNORECASE,
    )
    raw_html_reserved_open_pattern = re.compile(
        r"[ \t]*<(?:script|pre|style|textarea|address|article|aside|base|"
        r"basefont|blockquote|body|caption|center|col|colgroup|dd|"
        r"details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
        r"footer|form|frame|frameset|h[1-6]|head|header|hr|html|"
        r"iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|"
        r"optgroup|option|p|param|search|section|summary|table|tbody|"
        r"td|tfoot|th|thead|title|tr|track|ul)(?=[ \t/>]|$)",
        flags=re.IGNORECASE,
    )
    html_heading_pattern = re.compile(
        r"</?h[1-6](?=[ \t/>])[^\r\n]*>",
        flags=re.IGNORECASE,
    )
    html_entity_pattern = re.compile(
        r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);"
    )
    setext_line_pattern = re.compile(r"[ \t]*(?:=+|-+)[ \t]*")
    thematic_line_pattern = re.compile(
        r"[ \t]*(?:(?:\*[ \t]*){3,}|"
        r"(?:_[ \t]*){3,}|(?:-[ \t]*){3,})"
    )

    def structural_views(line: str) -> list[tuple[int, str]]:
        views = [(0, line)]
        payload = line
        for depth in range(1, 65):
            marker = container_prefix_pattern.match(payload)
            if marker is None:
                return views
            assert marker.end() > 0
            payload = payload[marker.end() :]
            views.append((depth, payload))
        raise AssertionError("excessive Markdown container nesting")

    plan_line_records = []
    plan_heading_records = []
    plan_leaf_heading_records = []
    offset = 0
    inside_fence = False
    fence_marker_count = 0
    fence_open_counts = {}
    active_fence_info = None

    for line_number, raw_line in enumerate(
        plan_text.splitlines(keepends=True),
        start=1,
    ):
        assert raw_line.endswith("\n")
        line = raw_line[:-1]
        start = offset
        offset += len(raw_line)

        fence_token = fence_token_pattern.search(line)
        if fence_token is not None:
            fence_marker_count += 1
            if not inside_fence:
                fence_open_match = fence_open_pattern.fullmatch(line)
                assert fence_open_match is not None
                fence_info = fence_open_match.group("info") or ""
                fence_open_counts[fence_info] = (
                    fence_open_counts.get(fence_info, 0) + 1
                )
                active_fence_info = fence_info
                inside_fence = True
            else:
                assert line == "`" * 3
                active_fence_info = None
                inside_fence = False
            plan_line_records.append(
                {
                    "number": line_number,
                    "start": start,
                    "end": offset,
                    "line": line,
                    "top_level": False,
                    "fence_marker": True,
                }
            )
            continue

        top_level = not inside_fence
        record = {
            "number": line_number,
            "start": start,
            "end": offset,
            "line": line,
            "top_level": top_level,
            "fence_marker": False,
            "fence_info": None if top_level else active_fence_info,
        }
        plan_line_records.append(record)

        if not top_level:
            continue

        assert "<!--" not in line
        assert "-->" not in line
        assert "<?" not in line
        assert "<![CDATA[" not in line
        assert "<!" not in line
        assert html_entity_pattern.search(line) is None

        views = structural_views(line)
        previous_record = (
            plan_line_records[-2] if len(plan_line_records) >= 2 else None
        )
        for depth, payload in views:
            assert raw_html_tag_pattern.match(payload) is None
            assert raw_html_reserved_open_pattern.match(payload) is None
            assert html_heading_pattern.search(payload) is None
            if thematic_line_pattern.fullmatch(payload) is not None:
                assert depth == 0
                assert (line_number, line) == (11, "---")
            elif setext_line_pattern.fullmatch(payload) is not None:
                short_plain_text_after_blank = (
                    depth == 0
                    and payload == line
                    and len(payload.strip()) <= 2
                    and previous_record is not None
                    and previous_record.get("top_level") is True
                    and previous_record["line"] == ""
                )
                if not short_plain_text_after_blank:
                    assert depth == 0
                    assert (line_number, line) == (11, "---")

        heading_candidates = [
            (depth, match)
            for depth, payload in views
            if (
                match := atx_heading_marker_pattern.match(payload)
            )
            is not None
        ]
        if not heading_candidates:
            continue

        assert len(heading_candidates) == 1
        assert heading_candidates[0][0] == 0
        canonical_heading = canonical_heading_pattern.fullmatch(line)
        assert canonical_heading is not None
        heading_level = len(canonical_heading.group(1))
        assert heading_level <= 5
        heading_record = {
            "number": line_number,
            "start": start,
            "level": heading_level,
            "line": line,
        }
        if heading_level <= 3:
            plan_heading_records.append(heading_record)
        else:
            plan_leaf_heading_records.append(heading_record)

    assert offset == len(plan_text)
    assert not inside_fence
    assert fence_marker_count == 748
    assert fence_open_counts == {
        "gitattributes": 1,
        "json": 1,
        "markdown": 1,
        "powershell": 252,
        "python": 23,
        "text": 96,
    }

    frozen_status = "> [KNOWN｜置信度：高] 状态：Frozen。"
    draft_status = "> [KNOWN｜置信度：高] 状态：Draft。"
    status_prefix = "> [KNOWN｜置信度：高] 状态："

    top_level_records = [
        record for record in plan_line_records if record["top_level"]
    ]
    status_records = [
        record
        for record in top_level_records
        if "状态：" in record["line"]
    ]
    assert [
        (record["number"], record["line"])
        for record in status_records
    ] == [(13, frozen_status)]

    frozen_metadata_raw = "".join(
        plan_text.splitlines(keepends=True)[:16]
    ).encode("utf-8")
    assert hashlib.sha256(frozen_metadata_raw).hexdigest().upper() == (
        "4F7191C8313CBBA8E3439DD7C6A1F41F"
        "38512F307DF7DE3A33376B6B77A1AB25"
    )

    metadata_locations = (
        (3, "> **For agentic workers:**"),
        (5, "**Goal:**"),
        (7, "**Architecture:**"),
        (9, "**Tech Stack:**"),
        (13, status_prefix),
        (14, "> [KNOWN｜置信度：高] 唯一规格："),
        (15, "> [KNOWN｜置信度：高] 本计划不修改冻结设计"),
    )
    for expected_line_number, prefix in metadata_locations:
        matches = [
            record
            for record in top_level_records
            if record["line"].startswith(prefix)
        ]
        assert [record["number"] for record in matches] == [
            expected_line_number
        ]

    assert len(plan_heading_records) == 57
    assert {
        level: sum(
            record["level"] == level for record in plan_heading_records
        )
        for level in (1, 2, 3)
    } == {1: 1, 2: 13, 3: 43}
    assert hashlib.sha256(
        "\n".join(
            record["line"] for record in plan_heading_records
        ).encode("utf-8")
    ).hexdigest().upper() == (
        "399C44BD770E36317D9C6D7B0B547012"
        "780F0B141B5E9CF02B8611741E980B39"
    )
    assert {
        level: sum(
            record["level"] == level
            for record in plan_leaf_heading_records
        )
        for level in (4, 5)
    } == {4: 34, 5: 17}
    assert hashlib.sha256(
        "\n".join(
            record["line"] for record in plan_leaf_heading_records
        ).encode("utf-8")
    ).hexdigest().upper() == (
        "F3806B1E984203525F2D2C9D836028C2"
        "53E64DC43318110A9556688E3F4E4D29"
    )

    expected_h1 = [
        "# Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan"
    ]
    expected_h2 = [
        "## 0. 反方边界",
        "## 1. 冻结输入",
        "## 2. 完成定义",
        "## 3. 文件职责",
        "## 4. 依赖图与并行边界",
        "## 5. 统一叶级 TDD 与 Git 协议",
        "## 6. 实施任务",
        "## 7. Reviewed case 的 13 个审计批次",
        "## 8. Static registry 与 S Sandbox",
        "## 9. Publication、handler manifest 与 smoke matrix",
        "## 10. Final compiler、verification、CLI 与关闭门",
        "## 11. Git 节点清单",
        "## 12. 计划自检",
    ]
    assert [
        record["line"]
        for record in plan_heading_records
        if record["level"] == 1
    ] == expected_h1
    assert [
        record["line"]
        for record in plan_heading_records
        if record["level"] == 2
    ] == expected_h2

    expected_tasks = (
        ("P00",)
        + tuple(f"F{number:02d}" for number in range(1, 10))
        + tuple(f"B{number:02d}" for number in range(1, 14))
        + ("F10",)
        + tuple(f"R{number:02d}" for number in range(1, 9))
        + tuple(f"P{number:02d}" for number in range(1, 4))
        + tuple(f"M{number:02d}" for number in range(1, 3))
        + ("C01", "V00", "L01", "V01", "Q01", "D01")
    )

    task_heading_records = [
        record
        for record in plan_heading_records
        if record["level"] == 3
    ]
    task_ids = []
    for record in task_heading_records:
        match = re.fullmatch(
            r"### Task ([A-Z][0-9]{2})：[^\r\n]+",
            record["line"],
        )
        assert match is not None
        task_ids.append(match.group(1))
    assert tuple(task_ids) == expected_tasks

    plan_task_hashes = {}
    h2_heading_records = [
        record
        for record in plan_heading_records
        if record["level"] == 2
    ]
    for index, (task_id, record) in enumerate(
        zip(task_ids, task_heading_records, strict=True)
    ):
        if index + 1 < len(task_heading_records):
            section_end = task_heading_records[index + 1]["start"]
        else:
            later_h2 = [
                heading
                for heading in h2_heading_records
                if heading["start"] > record["start"]
            ]
            assert later_h2
            section_end = later_h2[0]["start"]

        assert section_end > record["start"]
        section_raw = plan_text[
            record["start"] : section_end
        ].encode("utf-8")
        plan_task_hashes[task_id] = hashlib.sha256(
            section_raw
        ).hexdigest().upper()

    outside_fence_lines = [
        record["line"] for record in top_level_records
    ]
    rpv_level4_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 4
        and (
            match := re.fullmatch(
                r"#### ((?:R|P|V)\d{2}(?:-[A-Z])?)：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    rpv_level5_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 5
        and (
            match := re.fullmatch(
                r"##### ((?:R|P|V)\d{2}-[A-Z]\d+)：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    assert len(rpv_level4_ids) == len(set(rpv_level4_ids)) == 32
    assert len(rpv_level5_ids) == len(set(rpv_level5_ids)) == 17
    split_parent_ids = {
        parent
        for parent in rpv_level4_ids
        if any(child.startswith(parent) for child in rpv_level5_ids)
    }
    assert len(split_parent_ids) == 4
    structured_rpv_leaf_count = (
        len(rpv_level4_ids)
        - len(split_parent_ids)
        + len(rpv_level5_ids)
    )
    direct_rpv_leaf_ids = [
        task_id
        for task_id in task_ids
        if task_id in {"R01", "V01"}
    ]
    c01_leaf_ids = [
        match.group(1)
        for record in plan_leaf_heading_records
        if record["level"] == 4
        and (
            match := re.fullmatch(
                r"#### (C01-[A-Z])：[^\r\n]+",
                record["line"],
            )
        )
        is not None
    ]
    assert structured_rpv_leaf_count == 45
    assert direct_rpv_leaf_ids == ["R01", "V01"]
    rpv_leaf_count = (
        structured_rpv_leaf_count + len(direct_rpv_leaf_ids)
    )
    assert rpv_leaf_count == 47
    assert c01_leaf_ids == ["C01-A", "C01-B"]
    assert rpv_leaf_count + len(c01_leaf_ids) == 49

    powershell_source = (
        "\n".join(
            record["line"]
            for record in plan_line_records
            if record.get("fence_info") == "powershell"
        )
        + "\n"
    )
    assert hashlib.sha256(
        powershell_source.encode("utf-8")
    ).hexdigest().upper() == (
        "8F805AAD277E8532770C5754ED08E12C7"
        "DA4085036B33E42F5213E8AC7542E8F"
    )
    powershell_executable = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell_executable is not None
    powershell_ast_probe = r"""
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$source = [Console]::In.ReadToEnd()
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput(
  $source,
  [ref]$tokens,
  [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
  [Console]::Error.WriteLine(($parseErrors.Message -join " | "))
  exit 2
}
$commands = @(
  $ast.FindAll(
    {
      param($node)
      $node -is [System.Management.Automation.Language.CommandAst]
    },
    $true
  )
)
$gitCommands = @(
  $commands | Where-Object {
    $name = $_.GetCommandName()
    ($name -ceq "git") -or ($name -ceq "git.exe")
  }
)
foreach ($command in $gitCommands) {
  if (
    ($command.CommandElements.Count -lt 2) -or
    ($command.CommandElements[1] -isnot
      [System.Management.Automation.Language.StringConstantExpressionAst])
  ) {
    [Console]::Error.WriteLine("dynamic git subcommand forbidden")
    exit 3
  }
}
$gitCommandExtents = @(
  $gitCommands | ForEach-Object { $_.Extent.Text }
)
$commitCommands = @(
  $commands | Where-Object {
    ($_.CommandElements.Count -ge 2) -and
    ($_.CommandElements[1] -is
      [System.Management.Automation.Language.StringConstantExpressionAst]) -and
    ($_.CommandElements[1].Value -ceq "commit")
  } | ForEach-Object { $_.Extent.Text }
)
ConvertTo-Json -InputObject (
  [ordered]@{
    git = @($gitCommandExtents)
    commits = @($commitCommands)
  }
) -Compress
"""
    powershell_ast_result = subprocess.run(
        [
            powershell_executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            powershell_ast_probe,
        ],
        input=powershell_source,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert powershell_ast_result.returncode == 0, (
        powershell_ast_result.stderr
    )
    powershell_ast_payload = json.loads(powershell_ast_result.stdout)
    assert set(powershell_ast_payload) == {"git", "commits"}
    ast_git_extents = powershell_ast_payload["git"]
    assert isinstance(ast_git_extents, list)
    assert len(ast_git_extents) == 417
    assert all(isinstance(extent, str) for extent in ast_git_extents)
    assert hashlib.sha256(
        "\n".join(ast_git_extents).encode("utf-8")
    ).hexdigest().upper() == (
        "77CFCB59FC6BB835C8D5891CC1392EFB"
        "FA30D77898FBD4A1F37FE114134F1A0B"
    )
    ast_commit_extents = powershell_ast_payload["commits"]
    assert isinstance(ast_commit_extents, list)
    commit_messages = []
    for extent in ast_commit_extents:
        assert isinstance(extent, str)
        match = re.fullmatch(r'git commit -m "([^"]+)"', extent)
        assert match is not None
        commit_messages.append(match.group(1))
    assert len(commit_messages) == 91
    assert len(set(commit_messages)) == 91
    assert hashlib.sha256(
        "\n".join(commit_messages).encode("utf-8")
    ).hexdigest().upper() == (
        "6948B1439B6E5ECC9F9C99CE6ECFE27A"
        "386A9BFBD93744324D2EB940C49E20AD"
    )

    ledger_heading_index = outside_fence_lines.index(
        "## " + "11. Git 节点清单"
    )
    ledger_end_index = outside_fence_lines.index(
        "## " + "12. 计划自检"
    )
    assert ledger_heading_index < ledger_end_index
    ledger_rows = []
    for line in outside_fence_lines[
        ledger_heading_index + 1 : ledger_end_index
    ]:
        for depth, payload in structural_views(line):
            candidate = payload.lstrip(" \t")
            if re.match(r"\d+[.)](?:[ \t]+|$)", candidate) is None:
                continue
            assert depth == 0
            assert payload == line == candidate
            match = re.fullmatch(r"(\d+)\. `([^`]+)`", line)
            assert match is not None
            ledger_rows.append((int(match.group(1)), match.group(2)))
    assert [ordinal for ordinal, _ in ledger_rows] == list(range(1, 92))
    assert [message for _, message in ledger_rows] == commit_messages

    batch_heading_index = outside_fence_lines.index(
        "## " + "7. Reviewed case 的 13 个审计批次"
    )
    batch_end_index = outside_fence_lines.index(
        "## " + "8. Static registry 与 S Sandbox"
    )
    assert batch_heading_index < batch_end_index
    batch_table_lines = []
    for line in outside_fence_lines[
        batch_heading_index + 1 : batch_end_index
    ]:
        for depth, payload in structural_views(line):
            candidate = payload.lstrip(" \t")
            if "|" not in candidate:
                continue
            assert depth == 0
            assert payload == line == candidate
            batch_table_lines.append(line)

    batch_rows = []
    for line in batch_table_lines:
        match = re.fullmatch(
            r"\| (\d+) \| (B\d{2}) \| (\d+) \| "
            r"([^|]+?) \| `([^`]+)` \|",
            line,
        )
        if match is not None:
            batch_rows.append(match.groups())
        else:
            assert line in {
                "| ordinal | batch_id | batch_ordinal | "
                "exact clause ID | exact filename |",
                "|---:|---|---:|---|---|",
            }
    frozen_manifest_path = (
        ROOT
        / "fixtures"
        / "stage0b"
        / "generated"
        / "source_clause_manifest_v0_1.json"
    )
    frozen_manifest_raw = frozen_manifest_path.read_bytes()
    assert hashlib.sha256(frozen_manifest_raw).hexdigest().upper() == (
        "DFA68D59BBEAB43AD788002483DBF6D6E"
        "F88FFFA67D106BC4355FC167A6A2B3C"
    )
    frozen_manifest = json.loads(frozen_manifest_raw.decode("utf-8"))
    expected_batch_rows = [
        (
            str(ordinal),
            f"B{((ordinal - 1) // 20) + 1:02d}",
            str(((ordinal - 1) % 20) + 1),
            clause["clause_id"],
            f"case-{clause['clause_id'].lower().replace('#', '-')}.json",
        )
        for ordinal, clause in enumerate(
            frozen_manifest["clauses"],
            start=1,
        )
    ]
    assert len(batch_rows) == 259
    assert batch_rows == expected_batch_rows
    expected_batch_table_lines = []
    for batch_number in range(1, 14):
        batch_id = f"B{batch_number:02d}"
        expected_batch_table_lines.extend(
            [
                "| ordinal | batch_id | batch_ordinal | "
                "exact clause ID | exact filename |",
                "|---:|---|---:|---|---|",
            ]
        )
        expected_batch_table_lines.extend(
            (
                f"| {ordinal} | {row_batch_id} | {batch_ordinal} | "
                f"{clause_id} | `{filename}` |"
            )
            for (
                ordinal,
                row_batch_id,
                batch_ordinal,
                clause_id,
                filename,
            ) in expected_batch_rows
            if row_batch_id == batch_id
        )
    assert len(batch_table_lines) == 285
    assert batch_table_lines == expected_batch_table_lines

    status_record = status_records[0]
    approved_draft_text = (
        plan_text[: status_record["start"]]
        + draft_status
        + plan_text[status_record["start"] + len(frozen_status) :]
    )
    approved_draft_raw = approved_draft_text.encode("utf-8")
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_DRAFT_PLAN_SHA256,
    )
    assert hashlib.sha256(approved_draft_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_DRAFT_PLAN_SHA256
    )

    expected_attestation = {
        "schema_version": "0.1",
        "reviewed_plan_path": (
            "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md"
        ),
        "approved_draft_plan_sha256": hashlib.sha256(
            approved_draft_raw
        ).hexdigest().upper(),
        "reviewed_plan_sha256": hashlib.sha256(plan_raw).hexdigest().upper(),
        "frozen_design_path": (
            "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换设计.md"
        ),
        "frozen_design_sha256": (
            "7A7626B69893A743CAED07146E04C71061EC4482D740044259F79A7FC7C5F813"
        ),
        "reviewed_at": "2026-07-31",
        "frozen_transition": "Draft->Frozen-only",
        "draft_reviews": [
            {
                "reviewer_id": "stage0c-final-spec-v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    approved_draft_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
            {
                "reviewer_id": "/root/stage0c_quality_final_v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    approved_draft_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
        ],
        "final_reads": [
            {
                "reviewer_id": "stage0c-final-spec-v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    plan_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
            {
                "reviewer_id": "/root/stage0c_quality_final_v3",
                "reviewed_plan_sha256": hashlib.sha256(
                    plan_raw
                ).hexdigest().upper(),
                "findings": {"blocker": 0, "important": 0, "minor": 0},
            },
        ],
        "findings": {"blocker": 0, "important": 0, "minor": 0},
        "verdict": "approved",
    }

    coverage_body = "\n".join(
        [
            "| Task | Verdict | Evidence |",
            "|---|---|---|",
            *[
                (
                    f"| {task_id} | PASS | "
                    f"plan-section-sha256:{plan_task_hashes[task_id]} |"
                )
                for task_id in expected_tasks
            ],
        ]
    )

    review_h1 = (
        "# Amadeus Core v0.1 Stage 0C "
        "实施计划审查记录（2026-07-29）"
    )
    review_h2 = (
        "## 1. 审查身份与输入",
        "## 2. Frozen 设计覆盖矩阵",
        "## 3. 叶级 TDD 与 Git 节点审查",
        "## 4. 259-case 批次与语义 mapping 审查",
        "## 5. Sandbox、publication、smoke 与 CLI 审查",
        "## 6. BLOCKER / IMPORTANT / MINOR",
        "## 7. 裁决",
    )

    section_1_body = (
        "<!-- stage0c-plan-review-attestation-v0.1\n"
        + json.dumps(
            expected_attestation,
            ensure_ascii=False,
            indent=2,
        )
        + "\n-->"
    )
    section_3_body = (
        "[COMPUTED｜置信度：高] 已核验 47 个实际 R/P/V TDD leaves、"
        "49 个风险 leaves 与 91 个唯一 commit；ledger 与 91 个 "
        "commit 节点按顺序一一对应。"
    )
    section_4_body = (
        "[COMPUTED｜置信度：高] 已核验 13 个批次按 "
        "12×20+19=259 完整覆盖 frozen manifest；每批 Author 与 "
        "Reviewer 角色分离，逐条语义 mapping 可追溯。"
    )
    section_5_body = (
        "[KNOWN｜置信度：高] 已核验 Sandbox、publication、smoke 与 "
        "CLI 叶节点、失败路径、恢复边界和验收命令。"
    )
    section_6_body = "\n".join(
        [
            (
                "[KNOWN｜置信度：高] 已关闭此前记录的 manifest/navigation、"
                "attestation、external approved SHA pin、leaf/commit/table candidate closure、Task/heading/section hash、canonical Markdown/JSON、PowerShell 状态连续性、reparse 分类与 README 130/34 状态缺口；当前开放项如下。"
            ),
            "",
            "| Level | Open |",
            "|---|---:|",
            "| BLOCKER | 0 |",
            "| IMPORTANT | 0 |",
            "| MINOR | 0 |",
        ]
    )
    section_7_body = (
        "[INFERRED｜置信度：高] 裁决：approved。"
    )

    review_bodies = (
        section_1_body,
        coverage_body,
        section_3_body,
        section_4_body,
        section_5_body,
        section_6_body,
        section_7_body,
    )
    expected_review_text = "\n\n".join(
        [
            review_h1,
            *[
                f"{heading}\n\n{body}"
                for heading, body in zip(
                    review_h2,
                    review_bodies,
                    strict=True,
                )
            ],
        ]
    ) + "\n"

    review_raw = review_path.read_bytes()
    assert re.fullmatch(
        r"[0-9A-F]{64}",
        STAGE0C_APPROVED_REVIEW_SHA256,
    )
    assert hashlib.sha256(review_raw).hexdigest().upper() == (
        STAGE0C_APPROVED_REVIEW_SHA256
    )
    review_text = review_raw.decode("utf-8")
    assert review_text.encode("utf-8") == review_raw
    assert review_text.endswith("\n")
    assert "\r" not in review_text
    assert not any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in review_text
        if character != "\n"
    )

    assert review_text.count("<!--") == 1
    assert review_text.count("-->") == 1
    assert review_text.count(section_1_body) == 1
    review_without_attestation = review_text.replace(
        section_1_body,
        "",
        1,
    )
    assert "<" not in review_without_attestation
    assert ">" not in review_without_attestation
    assert "&" not in review_without_attestation

    claim_tag_pattern = re.compile(
        r"\[(?:KNOWN|COMPUTED|INFERRED|COMMON|FRAME|GUESS)"
        r"(?:｜置信度：(?:高|中|低|极低|未知))?\]"
    )
    canonical_review_lines = []
    for line in review_without_attestation.splitlines():
        matches = list(claim_tag_pattern.finditer(line))
        if matches:
            assert len(matches) == 1
            match = matches[0]
            assert match.start() == 0
            assert line[match.end() :].startswith(" ")
            assert not line[match.end() :].startswith("  ")
            line = line[match.end() + 1 :]
        canonical_review_lines.append(line)

    assert not re.search(
        r"[*_`~&<>\[\]]",
        "\n".join(canonical_review_lines),
    )
    assert review_text == expected_review_text


def test_stage0c_plan_and_independent_review_are_indexed() -> None:
    manifest = json.loads(
        (ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest) == {"schema_version", "documents"}
    documents = manifest["documents"]
    by_id = {row["doc_id"]: row for row in documents}
    expected = {
        "stage0c-fixture-conversion-plan": {
            "doc_id": "stage0c-fixture-conversion-plan",
            "title": "Amadeus Core v0.1 Stage 0C 夹具转换 Implementation Plan",
            "path": "outputs/Amadeus-Core-v0.1-Stage0C-夹具转换实施计划.md",
            "kind": "implementation-plan",
            "authority": "canonical",
            "status": "approved",
            "stage": "stage0c",
            "index": True,
            "sensitivity": "internal",
        },
        "stage0c-implementation-plan-review-2026-07-29": {
            "doc_id": "stage0c-implementation-plan-review-2026-07-29",
            "title": "Amadeus Core v0.1 Stage 0C 实施计划审查记录（2026-07-29）",
            "path": "outputs/Amadeus-Core-v0.1-Stage0C-实施计划审查记录-2026-07-29.md",
            "kind": "plan-review",
            "authority": "canonical",
            "status": "approved",
            "stage": "stage0c",
            "index": True,
            "sensitivity": "internal",
        },
    }
    assert set(expected) <= set(by_id)
    assert len(documents) == 34
    assert len(by_id) == 34
    for doc_id, expected_row in expected.items():
        row = by_id[doc_id]
        assert set(row) == set(expected_row) | {"sha256"}
        assert {key: row[key] for key in expected_row} == expected_row
        raw = (ROOT / expected_row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]

    new_doc_ids = tuple(expected)
    design_review_index = next(
        index
        for index, row in enumerate(documents)
        if row["doc_id"] == "stage0c-design-review-2026-07-29"
    )
    assert tuple(
        row["doc_id"]
        for row in documents[design_review_index + 1 : design_review_index + 3]
    ) == new_doc_ids

    existing_documents = [
        row for row in documents if row["doc_id"] not in expected
    ]
    assert len(existing_documents) == 32
    existing_projection = [
        {
            key: value
            for key, value in row.items()
            if not (
                key == "sha256"
                and row["doc_id"] in {"root-readme", "kb-navigation"}
            )
        }
        for row in existing_documents
    ]
    existing_canonical = json.dumps(
        existing_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(existing_canonical).hexdigest() == (
        "9e70f62779019c2e7545f7731045d8ed59ee712b18a13608b756c63fc7e22df6"
    )

    def authority_section(path: Path, heading: str) -> str:
        text = path.read_text(encoding="utf-8")
        prefix, separator, remainder = text.partition(f"{heading}\n")
        assert prefix or separator
        assert separator == f"{heading}\n"
        return remainder.split("\n## ", 1)[0]

    readme_section = authority_section(
        ROOT / "README.md",
        "## 权威文档阅读顺序",
    )
    navigation_section = authority_section(
        ROOT / "knowledge" / "data_structure.md",
        "## 5. 权威恢复入口",
    )
    for expected_row in expected.values():
        target = expected_row["path"]
        assert _MARKDOWN_LINK.findall(readme_section).count(target) == 1
        assert _MARKDOWN_LINK.findall(navigation_section).count(f"../{target}") == 1
    assert hashlib.sha256((ROOT / "README.md").read_bytes()).hexdigest() == (
        "e629fe5e639a6cf72ec98646560b0edf739a9e9dd619043d3130366ed62ef2c0"
    )
    assert hashlib.sha256(
        (ROOT / "knowledge" / "data_structure.md").read_bytes()
    ).hexdigest() == (
        "426720562e2f9363ff6b56148f7e538bcc1a5a6a6b83c995a133dcb7224cbdb0"
    )

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
