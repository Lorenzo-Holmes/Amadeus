import ast
from pathlib import Path


__all__ = ["check_imports"]

_ALLOWED_ROOTS = frozenset(
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
        and node.id == "__import__"
    ):
        return node.id
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Load)
        and node.attr in {"import_module", "__import__"}
    ):
        return ast.unparse(node)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Load)
        and isinstance(node.value, ast.Name)
        and node.value.id == "__builtins__"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "__import__"
    ):
        return ast.unparse(node)
    return None


def _real_package_root(package: Path) -> Path:
    if package.is_symlink():
        raise ValueError("package root must be a real directory")
    try:
        resolved = package.resolve(strict=True)
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ValueError("package root must be a real directory") from error
    if not resolved.is_dir():
        raise ValueError("package root must be a real directory")
    return resolved


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
            elif entry.is_dir():
                child_directories.append(entry)
            elif entry.is_file() and entry.suffix == ".py":
                sources.append(entry)
        pending.extend(reversed(child_directories))
    return sorted(sources), violations


def check_imports(package: Path) -> list[str]:
    package_root = _real_package_root(package)
    source_paths, violations = _package_sources(package_root)
    for source_path in source_paths:
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for node in ast.walk(tree):
            for module in _absolute_imports(node):
                if module.split(".", 1)[0] not in _ALLOWED_ROOTS:
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
