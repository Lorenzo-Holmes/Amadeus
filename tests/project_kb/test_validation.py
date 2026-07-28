import os
import subprocess
from pathlib import Path

import pytest

import tools.project_kb.manifest as manifest_module
from tools.project_kb.cli import main


def _paths(root: Path) -> tuple[Path, Path]:
    knowledge = root / "knowledge"
    return knowledge / "manifest.json", knowledge / "index-policy.json"


def _run_check(root: Path, capsys) -> tuple[int, str]:
    result = main(["--root", str(root), "check"])
    return result, capsys.readouterr().out.strip()


@pytest.mark.parametrize(
    ("bad_path", "detail"),
    [
        ("../outside.md", "parent traversal"),
        ("/outside.md", "absolute path"),
        ("C:/outside.md", "absolute path"),
    ],
)
def test_rejects_traversal_and_absolute_manifest_paths(
    kb_root,
    json_helpers,
    capsys,
    bad_path,
    detail,
) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    manifest["documents"][0]["path"] = bad_path
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output.startswith("path_error=")
    assert detail in output


@pytest.mark.parametrize("field", ["doc_id", "path"])
def test_rejects_duplicate_document_identity(
    kb_root,
    json_helpers,
    capsys,
    field,
) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    manifest["documents"][1][field] = manifest["documents"][0][field]
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output.startswith("manifest_error=duplicate ")
    assert field in output


def test_rejects_stale_document_hash(kb_root, json_helpers, capsys) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = "0" * 64
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "content_error=sha256 mismatch: README.md"


def test_rejects_index_false(kb_root, json_helpers, capsys) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    manifest["documents"][0]["index"] = False
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "manifest_error=index must be true: root-readme"


def test_rejects_raw_even_if_policy_and_manifest_include_it(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, document, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    raw_path = kb_root / "knowledge" / "90_raw" / "secret.md"
    manifest = load(manifest_path)
    manifest["documents"].append(
        document(
            "raw-secret",
            "Raw secret",
            "knowledge/90_raw/secret.md",
            raw_path.read_bytes(),
        )
    )
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == (
        "path_error=raw or hidden-local path: knowledge/90_raw/secret.md"
    )


def test_rejects_hidden_local_path_even_if_policy_includes_it(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, document, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    hidden = kb_root / ".local"
    hidden.mkdir()
    private = hidden / "private.md"
    private.write_text("# Private\n", encoding="utf-8")
    manifest = load(manifest_path)
    manifest["documents"].append(
        document("hidden-private", "Private", ".local/private.md", private.read_bytes())
    )
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "path_error=raw or hidden-local path: .local/private.md"


def test_rejects_document_outside_policy_allowlist(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, document, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    docs = kb_root / "docs"
    docs.mkdir()
    private = docs / "private.md"
    private.write_text("# Private\n", encoding="utf-8")
    manifest = load(manifest_path)
    manifest["documents"].append(
        document("docs-private", "Private", "docs/private.md", private.read_bytes())
    )
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "policy_error=path is not allowed: docs/private.md"


def test_rejects_invalid_utf8_after_hash_verification(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, _, sha256 = json_helpers
    manifest_path, _ = _paths(kb_root)
    invalid = b"# Invalid\n\xff\n"
    (kb_root / "README.md").write_bytes(invalid)
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = sha256(invalid)
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "content_error=invalid UTF-8: README.md"


def test_rejects_manifested_file_symlink(kb_root, json_helpers, capsys) -> None:
    load, write, _, sha256 = json_helpers
    manifest_path, _ = _paths(kb_root)
    external = kb_root.parent / f"{kb_root.name}-external.md"
    external.write_text("# External\n", encoding="utf-8")
    readme = kb_root / "README.md"
    readme.unlink()
    try:
        readme.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = sha256(external.read_bytes())
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "path_error=link or junction: README.md"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_rejects_manifested_file_below_junction(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, document, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    external = kb_root.parent / f"{kb_root.name}-external-dir"
    external.mkdir()
    outside = external / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    outputs = kb_root / "outputs"
    outputs.mkdir()
    junction = outputs / "linked"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(external)],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"junction unavailable: {created.stderr or created.stdout}")
    try:
        manifest = load(manifest_path)
        manifest["documents"].append(
            document(
                "junction-doc",
                "Outside",
                "outputs/linked/outside.md",
                outside.read_bytes(),
            )
        )
        write(manifest_path, manifest)

        code, output = _run_check(kb_root, capsys)
        assert code == 1
        assert output == "path_error=link or junction: outputs/linked"
    finally:
        if junction.exists():
            os.rmdir(junction)


def test_rejects_policy_contract_drift(kb_root, json_helpers, capsys) -> None:
    load, write, _, _ = json_helpers
    _, policy_path = _paths(kb_root)
    policy = load(policy_path)
    policy["default_index"] = True
    write(policy_path, policy)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "policy_error=default_index must be false"


def test_rejects_policy_scope_expansion(kb_root, json_helpers, capsys) -> None:
    load, write, _, _ = json_helpers
    _, policy_path = _paths(kb_root)
    policy = load(policy_path)
    policy["include"].append("docs/**/*.md")
    write(policy_path, policy)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "policy_error=unexpected include pattern: docs/**/*.md"


def test_rejects_unimplemented_gitignore_semantics(
    kb_root,
    json_helpers,
    capsys,
) -> None:
    load, write, _, _ = json_helpers
    _, policy_path = _paths(kb_root)
    policy = load(policy_path)
    policy["follow_gitignore"] = True
    write(policy_path, policy)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "policy_error=follow_gitignore must be false"


def test_rejects_duplicate_json_keys(kb_root, capsys) -> None:
    manifest_path, _ = _paths(kb_root)
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace(
            '"schema_version": "0.1",',
            '"schema_version": "0.1",\n  "schema_version": "0.1",',
            1,
        ),
        encoding="utf-8",
    )

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "manifest_error=duplicate JSON key: schema_version"


@pytest.mark.parametrize(
    ("bad_path", "detail"),
    [
        ("outputs/file:stream.md", "Windows alias syntax"),
        ("outputs/trailing./doc.md", "Windows alias syntax"),
        ("outputs/CON/document.md", "reserved Windows path component"),
        ("outputs/CONIN$.md", "reserved Windows path component"),
        ("outputs/COM¹.md", "reserved Windows path component"),
        ("outputs/bad?.md", "Windows alias syntax"),
        ("Knowledge/90_RAW/secret.md", "raw or hidden-local path"),
    ],
)
def test_rejects_windows_aliases_and_casefolded_raw_paths(
    kb_root,
    json_helpers,
    capsys,
    bad_path,
    detail,
) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    manifest["documents"][0]["path"] = bad_path
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output.startswith("path_error=")
    assert detail in output


def test_rejects_manifested_hard_link(kb_root, json_helpers, capsys) -> None:
    load, write, _, sha256 = json_helpers
    manifest_path, _ = _paths(kb_root)
    external = kb_root.parent / f"{kb_root.name}-hardlink-source.md"
    data = b"# External hard link\n"
    external.write_bytes(data)
    readme = kb_root / "README.md"
    readme.unlink()
    try:
        os.link(external, readme)
    except OSError as error:
        pytest.skip(f"hard link unavailable: {error}")
    manifest = load(manifest_path)
    manifest["documents"][0]["sha256"] = sha256(data)
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "path_error=hard link: README.md"


def test_open_fstat_guard_rejects_swap_before_any_document_read(
    kb_root,
    capsys,
    monkeypatch,
) -> None:
    readme = kb_root / "README.md"
    moved = kb_root / "README-moved.md"
    external = kb_root.parent / f"{kb_root.name}-swap-target.md"
    external.write_bytes(readme.read_bytes())
    original_open = manifest_module.os.open
    original_fdopen = manifest_module.os.fdopen
    swapped_fd = None

    def swap_before_open(path, flags):
        nonlocal swapped_fd
        if Path(path) == readme and swapped_fd is None:
            readme.rename(moved)
            try:
                readme.symlink_to(external)
            except OSError as error:
                moved.rename(readme)
                pytest.skip(f"symlink unavailable: {error}")
            swapped_fd = original_open(path, flags)
            return swapped_fd
        return original_open(path, flags)

    def reject_read(fd, *args, **kwargs):
        if fd == swapped_fd:
            pytest.fail("swapped descriptor was read before fstat rejection")
        return original_fdopen(fd, *args, **kwargs)

    monkeypatch.setattr(manifest_module.os, "open", swap_before_open)
    monkeypatch.setattr(manifest_module.os, "fdopen", reject_read)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "path_error=path changed before read: README.md"


def test_rejects_manifest_schema_drift(kb_root, json_helpers, capsys) -> None:
    load, write, _, _ = json_helpers
    manifest_path, _ = _paths(kb_root)
    manifest = load(manifest_path)
    del manifest["documents"][0]["title"]
    write(manifest_path, manifest)

    code, output = _run_check(kb_root, capsys)
    assert code == 1
    assert output == "manifest_error=missing field: root-readme.title"
