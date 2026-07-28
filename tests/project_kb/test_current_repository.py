import json
import re
import tomllib
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
        "indexed_documents=27",
        "raw_paths_indexed=0",
    ]

    manifest = json.loads(
        (ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8")
    )
    paths = [document["path"] for document in manifest["documents"]]
    assert len(paths) == 27
    assert len(set(paths)) == 27
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
