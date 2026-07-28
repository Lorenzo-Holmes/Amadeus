from tools.project_kb.cli import main


def test_check_reports_exact_ready_summary(kb_root, capsys) -> None:
    assert main(["--root", str(kb_root), "check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "project_kb_ready=true",
        "indexed_documents=2",
        "raw_paths_indexed=0",
    ]


def test_search_is_case_insensitive_reports_heading_and_honors_limit(
    kb_root,
    capsys,
) -> None:
    assert main([
        "--root",
        str(kb_root),
        "search",
        "NEEDLE",
        "--limit",
        "2",
    ]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "README.md:3 | Overview | Needle alpha",
        "README.md:4 | Overview | needle beta",
        "hits=2",
    ]


def test_search_zero_hits_is_success_and_does_not_read_raw(kb_root, capsys) -> None:
    assert main([
        "--root",
        str(kb_root),
        "search",
        "raw-only-secret",
    ]) == 0
    assert capsys.readouterr().out == "hits=0\n"


def test_search_preserves_leading_and_trailing_line_whitespace(
    kb_root,
    capsys,
) -> None:
    assert main([
        "--root",
        str(kb_root),
        "search",
        "indented",
    ]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "README.md:5 | Overview |   Indented needle  ",
        "hits=1",
    ]


def test_search_ignores_fenced_code_when_tracking_headings(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, _, sha256 = json_helpers
    readme = (
        "# Project KB\n"
        "## Real heading\n"
        "~~~~python\n"
        "# fenced heading\n"
        "fenced needle\n"
        "~~~~\n"
    ).encode("utf-8")
    (kb_root / "README.md").write_bytes(readme)
    manifest_path = kb_root / "knowledge" / "manifest.json"
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = sha256(readme)
    write(manifest_path, manifest)

    assert main([
        "--root",
        str(kb_root),
        "search",
        "fenced needle",
    ]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "README.md:5 | Real heading | fenced needle",
        "hits=1",
    ]


def test_search_uses_commonmark_atx_heading_boundaries(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, _, sha256 = json_helpers
    readme = (
        "# Project KB\n"
        "## C#\n"
        "csharp sample\n"
        "\t# tabbed text\n"
        "tab sample\n"
        "###\n"
        "empty sample\n"
    ).encode("utf-8")
    (kb_root / "README.md").write_bytes(readme)
    manifest_path = kb_root / "knowledge" / "manifest.json"
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = sha256(readme)
    write(manifest_path, manifest)

    assert main([
        "--root",
        str(kb_root),
        "search",
        "sample",
    ]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "README.md:3 | C# | csharp sample",
        "README.md:5 | C# | tab sample",
        "README.md:7 |  | empty sample",
        "hits=3",
    ]
