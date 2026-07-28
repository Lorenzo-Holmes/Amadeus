import ast
import importlib.util
import marshal
import re
import sys
from pathlib import Path


__all__ = ["check_imports"]

_BASE_ALLOWED_ROOTS = frozenset(
    {
        "__future__",
        "argparse",
        "ast",
        "collections",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "typing",
    }
)
_SOURCE_ALLOWED_ROOTS = {
    "cli.py": frozenset({"tempfile"}),
    "transport_gate.py": frozenset(
        {"importlib", "marshal", "sys"}
    ),
}
_DYNAMIC_IMPORT_NAMES = frozenset({"__import__", "import_module"})
_UNSCANNED_IMPORTABLE_SUFFIXES = frozenset(
    {".pyc", ".pyo", ".pyd", ".so"}
)
_CPYTHON_CACHE_NAME = re.compile(
    r"^(?P<source_stem>.+)\.cpython-[0-9]+"
    r"(?:\.opt-(?P<optimization>[12]))?\.pyc$"
)


def _absolute_imports(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module]
    return []


def _dynamic_import_reference(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in _DYNAMIC_IMPORT_NAMES
    ):
        return node.id
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and node.attr in _DYNAMIC_IMPORT_NAMES
    ):
        return ast.unparse(node)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Load)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value in _DYNAMIC_IMPORT_NAMES
    ):
        return ast.unparse(node)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value in _DYNAMIC_IMPORT_NAMES
    ):
        return ast.unparse(node)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in _DYNAMIC_IMPORT_NAMES
    ):
        return ast.unparse(node)
    return None


def _real_package_root(package: Path) -> Path:
    lexical = package.absolute()
    lineage = [lexical]
    while lineage[-1].parent != lineage[-1]:
        lineage.append(lineage[-1].parent)
    for ancestor in reversed(lineage):
        if (
            ancestor.is_symlink()
            or ancestor.is_junction()
            or not ancestor.is_dir()
        ):
            raise ValueError("package root must be a real directory")
    try:
        resolved = lexical.resolve(strict=True)
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError("package root must be a real directory") from error
    if not resolved.is_dir():
        raise ValueError("package root must be a real directory")
    return resolved


def _cache_body_matches_source(
    entry: Path,
    source: Path,
    optimization: int,
) -> bool:
    try:
        source_bytes = source.read_bytes()
        payload = entry.read_bytes()
        if (
            len(payload) < 16
            or payload[:4] != importlib.util.MAGIC_NUMBER
        ):
            return False
        flags = int.from_bytes(payload[4:8], "little")
        if flags not in {0, 1, 3}:
            return False
        if flags == 0:
            status = source.stat()
            expected_metadata = (
                (int(status.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
                + (len(source_bytes) & 0xFFFFFFFF).to_bytes(4, "little")
            )
        else:
            expected_metadata = importlib.util.source_hash(source_bytes)
        if payload[8:16] != expected_metadata:
            return False
        cached_code = marshal.loads(payload[16:])
        expected_code = compile(
            source_bytes,
            str(source),
            "exec",
            dont_inherit=True,
            optimize=optimization,
        )
        return (
            type(cached_code) is type(expected_code)
            and cached_code == expected_code
        )
    except (EOFError, OSError, SyntaxError, TypeError, ValueError):
        return False


def _is_verified_source_cache(entry: Path) -> bool:
    if entry.parent.name != "__pycache__":
        return False
    match = _CPYTHON_CACHE_NAME.fullmatch(entry.name)
    if match is None:
        return False
    source = (
        entry.parent.parent
        / f"{match.group('source_stem')}.py"
    )
    if source.is_symlink() or source.is_junction() or not source.is_file():
        return False
    optimization_text = match.group("optimization")
    optimization = (
        int(optimization_text)
        if optimization_text is not None
        else 0
    )
    expected_cache = Path(importlib.util.cache_from_source(
        str(source),
        optimization=optimization_text or "",
    ))
    return (
        entry == expected_cache
        and _cache_body_matches_source(entry, source, optimization)
    )


def _package_sources(package_root: Path) -> tuple[list[Path], list[str]]:
    sources: list[Path] = []
    violations: list[str] = []
    pending = [package_root]
    while pending:
        directory = pending.pop()
        child_directories: list[Path] = []
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                violations.append(
                    f"{entry.as_posix()}:0:symlink-entry"
                )
            elif entry.is_junction():
                violations.append(
                    f"{entry.as_posix()}:0:junction-entry"
                )
            elif entry.is_dir():
                child_directories.append(entry)
            elif entry.is_file():
                suffix = entry.suffix.casefold()
                if suffix == ".py":
                    sources.append(entry)
                elif (
                    suffix in _UNSCANNED_IMPORTABLE_SUFFIXES
                    and not _is_verified_source_cache(entry)
                ):
                    violations.append(
                        f"{entry.as_posix()}:0:"
                        f"unscanned-importable:{suffix}"
                    )
        pending.extend(reversed(child_directories))
    return sorted(sources), violations


def check_imports(package: Path) -> list[str]:
    package_root = _real_package_root(package)
    if sys.pycache_prefix is not None:
        raise ValueError("external pycache prefix is not supported")
    source_paths, violations = _package_sources(package_root)
    for source_path in source_paths:
        source_key = source_path.relative_to(package_root).as_posix()
        allowed_roots = (
            _BASE_ALLOWED_ROOTS
            | _SOURCE_ALLOWED_ROOTS.get(source_key, frozenset())
        )
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for node in ast.walk(tree):
            for module in _absolute_imports(node):
                if module.split(".", 1)[0] not in allowed_roots:
                    violations.append(
                        f"{source_path.as_posix()}:{node.lineno}:"
                        f"absolute-import:{module}"
                    )
            if isinstance(node, ast.ImportFrom) and node.level > 1:
                violations.append(
                    f"{source_path.as_posix()}:{node.lineno}:relative-parent"
                )
            dynamic_reference = _dynamic_import_reference(node)
            if dynamic_reference is not None:
                violations.append(
                    f"{source_path.as_posix()}:{node.lineno}:"
                    f"dynamic-import:{dynamic_reference}"
                )
    return sorted(violations)
