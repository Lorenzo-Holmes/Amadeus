import importlib.util
import marshal
import sys
from pathlib import Path

import pytest

from tools.stage0a_sources.transport_gate import check_imports


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools" / "stage0a_sources"


def _write_verified_cache(
    source: Path,
    *,
    optimization: int = 0,
) -> Path:
    source_bytes = source.read_bytes()
    optimization_text = str(optimization) if optimization else ""
    cache = Path(importlib.util.cache_from_source(
        str(source),
        optimization=optimization_text,
    ))
    cache.parent.mkdir(parents=True, exist_ok=True)
    code = compile(
        source_bytes,
        str(source),
        "exec",
        dont_inherit=True,
        optimize=optimization,
    )
    cache.write_bytes(
        importlib.util.MAGIC_NUMBER
        + (3).to_bytes(4, "little")
        + importlib.util.source_hash(source_bytes)
        + marshal.dumps(code)
    )
    return cache


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


def test_rejects_package_below_real_symlink_ancestor(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-parent"
    package = real_parent / "package"
    package.mkdir(parents=True)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(
        ValueError,
        match="package root must be a real directory",
    ):
        check_imports(linked_parent / "package")


def test_rejects_external_pycache_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    monkeypatch.setattr(
        sys,
        "pycache_prefix",
        str(tmp_path / "external-cache"),
    )

    with pytest.raises(
        ValueError,
        match="external pycache prefix is not supported",
    ):
        check_imports(package)


def test_scopes_extra_dependencies_to_exact_gate_files(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "cli.py").write_text(
        "import tempfile\n",
        encoding="utf-8",
    )
    (package / "transport_gate.py").write_text(
        "import importlib.util\nimport marshal\nimport sys\n",
        encoding="utf-8",
    )
    loader = package / "loader.py"
    loader.write_text(
        "\n".join(
            (
                "import importlib.util",
                "import marshal",
                "import tempfile",
                "import sys",
            )
        ),
        encoding="utf-8",
    )
    source = loader.as_posix()

    assert check_imports(package) == [
        f"{source}:1:absolute-import:importlib.util",
        f"{source}:2:absolute-import:marshal",
        f"{source}:3:absolute-import:tempfile",
        f"{source}:4:absolute-import:sys",
    ]


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
    cache_link = package / "__pycache__"
    cache_link.mkdir()
    (cache_link / "hidden.py").write_text(
        "import tools.cached\n",
        encoding="utf-8",
    )
    marked_as_symlinks = {nested, linked_file, cache_link}
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
            f"{cache_link.as_posix()}:0:symlink-entry",
        )
    )


def test_reports_junction_directory_without_traversing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    junction = package / "junction"
    junction.mkdir()
    (junction / "hidden.py").write_text(
        "import tools.hidden\n",
        encoding="utf-8",
    )
    original_is_junction = Path.is_junction

    def mark_entry_as_junction(path: Path) -> bool:
        if path == junction:
            return True
        return original_is_junction(path)

    monkeypatch.setattr(Path, "is_junction", mark_entry_as_junction)

    assert check_imports(package) == [
        f"{junction.as_posix()}:0:junction-entry"
    ]


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
                "bare_loader = import_module",
                "mapped_loader = __builtins__.get('__import__')",
                "registry_loader = registry.get('import_module')",
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
            f"{source}:5:dynamic-import:import_module",
            f"{source}:6:dynamic-import:"
            "__builtins__.get('__import__')",
            f"{source}:7:dynamic-import:"
            "registry.get('import_module')",
        )
    )


def test_reports_nested_subscripts_and_getattr_import_references(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    bad_source = package / "indirect.py"
    bad_source.write_text(
        "\n".join(
            (
                "globals()['__builtins__']['__import__']('os')",
                "load = registry['import_module']",
                "builtin = getattr(obj, '__import__')",
                "module_loader = getattr(obj, 'import_module')",
            )
        ),
        encoding="utf-8",
    )
    source = bad_source.as_posix()

    assert check_imports(package) == sorted(
        (
            f"{source}:1:dynamic-import:"
            "globals()['__builtins__']['__import__']",
            f"{source}:2:dynamic-import:registry['import_module']",
            f"{source}:3:dynamic-import:getattr(obj, '__import__')",
            f"{source}:4:dynamic-import:getattr(obj, 'import_module')",
        )
    )


def test_scans_casefolded_python_and_flags_unscanned_importables(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    upper_source = package / "hidden.PY"
    upper_source.write_text("import os\n", encoding="utf-8")
    opaque_files = [
        package / "cached.pyc",
        package / "optimized.pyo",
        package / "native.pyd",
        package / "unix.so",
    ]
    for opaque_file in opaque_files:
        opaque_file.write_bytes(b"opaque")
    cache = package / "__pycache__"
    cache.mkdir()
    cache_source = cache / "evil.py"
    cache_source.write_text("import os\n", encoding="utf-8")
    upper_cache_source = cache / "upper.PY"
    upper_cache_source.write_text(
        "import os\n",
        encoding="utf-8",
    )
    cache_opaque_files = [
        cache / "evil.pyc",
        cache / "optimized.pyo",
        cache / "native.pyd",
        cache / "unix.so",
    ]
    for opaque_file in cache_opaque_files:
        opaque_file.write_bytes(b"opaque")
    supported_source = package / "module.py"
    supported_source.write_text("import json\n", encoding="utf-8")
    _write_verified_cache(supported_source)
    _write_verified_cache(supported_source, optimization=1)
    orphan_cache = Path(importlib.util.cache_from_source(
        str(package / "orphan.py"),
    ))
    orphan_cache.write_bytes(b"opaque")

    assert check_imports(package) == sorted(
        (
            f"{upper_source.as_posix()}:1:absolute-import:os",
            f"{cache_source.as_posix()}:1:absolute-import:os",
            f"{upper_cache_source.as_posix()}:1:absolute-import:os",
            *(
                f"{path.as_posix()}:0:"
                f"unscanned-importable:{path.suffix.casefold()}"
                for path in (
                    *opaque_files,
                    *cache_opaque_files,
                    orphan_cache,
                )
            ),
        )
    )


def test_does_not_exempt_cache_backed_by_symlink_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    source = package / "linked.py"
    source.write_text("import json\n", encoding="utf-8")
    cached = _write_verified_cache(source)
    original_is_symlink = Path.is_symlink

    def mark_source_as_symlink(path: Path) -> bool:
        if path == source:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", mark_source_as_symlink)

    assert check_imports(package) == sorted(
        (
            f"{source.as_posix()}:0:symlink-entry",
            f"{cached.as_posix()}:0:unscanned-importable:.pyc",
        )
    )


def test_rejects_cache_with_valid_header_and_different_code_body(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    source = package / "payload.py"
    source.write_text("VALUE = 'benign'\n", encoding="utf-8")
    cached = _write_verified_cache(source)
    valid_payload = cached.read_bytes()
    different_code = compile(
        b"import os\n",
        str(source),
        "exec",
        dont_inherit=True,
    )
    cached.write_bytes(valid_payload[:16] + marshal.dumps(different_code))

    assert check_imports(package) == [
        f"{cached.as_posix()}:0:unscanned-importable:.pyc"
    ]
