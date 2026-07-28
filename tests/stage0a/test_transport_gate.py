from pathlib import Path

import pytest

from tools.stage0a_sources.transport_gate import check_imports


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "stage0a_sources"


def test_current_stage0a_package_respects_import_boundary_from_any_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert check_imports(PACKAGE) == []


def test_rejects_missing_package_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="package root must be a real directory"):
        check_imports(tmp_path / "missing")


def test_rejects_symlink_package_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    original_is_symlink = Path.is_symlink

    def mark_package_as_symlink(path: Path) -> bool:
        if path == package:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", mark_package_as_symlink)

    with pytest.raises(ValueError, match="package root must be a real directory"):
        check_imports(package)


def test_reports_symlink_entries_without_following_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    nested = package / "nested"
    nested.mkdir()
    (nested / "hidden.py").write_text(
        "import tools.hidden\n",
        encoding="utf-8",
    )
    linked_file = package / "linked.py"
    linked_file.write_text(
        "import tools.linked\n",
        encoding="utf-8",
    )
    marked_as_symlinks = {nested, linked_file}
    original_is_symlink = Path.is_symlink

    def mark_entries_as_symlinks(path: Path) -> bool:
        if path in marked_as_symlinks:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", mark_entries_as_symlinks)

    assert check_imports(package) == sorted(
        (
            f"{nested.as_posix()}:0:symlink-entry",
            f"{linked_file.as_posix()}:0:symlink-entry",
        )
    )


def test_reports_absolute_parent_relative_and_dynamic_imports(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    bad_source = package / "bad.py"
    bad_source.write_text(
        "\n".join(
            (
                "from .local import ok",
                "from ..sibling import hidden",
                "import tools.sibling",
                "from tools.other import x",
                "__import__('x')",
                "loader.import_module('x')",
            )
        ),
        encoding="utf-8",
    )
    source = bad_source.as_posix()

    assert check_imports(package) == sorted(
        (
            f"{source}:2:relative-parent",
            f"{source}:3:absolute-import:tools.sibling",
            f"{source}:4:absolute-import:tools.other",
            f"{source}:5:dynamic-import:__import__",
            f"{source}:6:dynamic-import:loader.import_module",
        )
    )


def test_reports_dynamic_import_references_before_they_are_called(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    bad_source = package / "aliases.py"
    bad_source.write_text(
        "\n".join(
            (
                "imp = __import__",
                "load = obj.import_module",
                "builtin_method = obj.__import__",
                "__builtins__['__import__']('os')",
            )
        ),
        encoding="utf-8",
    )
    source = bad_source.as_posix()

    assert check_imports(package) == sorted(
        (
            f"{source}:1:dynamic-import:__import__",
            f"{source}:2:dynamic-import:obj.import_module",
            f"{source}:3:dynamic-import:obj.__import__",
            f"{source}:4:dynamic-import:__builtins__['__import__']",
        )
    )
