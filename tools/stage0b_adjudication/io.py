import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import INPUT_ARTIFACTS


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _real_root(root: str | Path) -> Path:
    lexical = Path(root).absolute()
    lineage = [lexical]
    while lineage[-1].parent != lineage[-1]:
        lineage.append(lineage[-1].parent)
    for path in reversed(lineage):
        if _is_link_or_junction(path) or not path.is_dir():
            raise ValueError("stage0b input root must contain only real directories")
    return lexical.resolve(strict=True)


def _read_frozen_artifact(root: Path, name: str) -> Any:
    contract = INPUT_ARTIFACTS[name]
    path = root / contract["path"]
    lineage = []
    cursor = path.parent
    while cursor != root:
        lineage.append(cursor)
        if root not in cursor.parents:
            raise ValueError(f"stage0b input path containment: {name}")
        cursor = cursor.parent
    for directory in reversed(lineage):
        if _is_link_or_junction(directory) or not directory.is_dir():
            raise ValueError(f"stage0b input directory identity: {name}")
    if _is_link_or_junction(path) or not path.is_file():
        raise ValueError(f"stage0b input file identity: {name}")
    payload = path.read_bytes()
    if len(payload) != contract["size"]:
        raise ValueError(f"stage0b input size drift: {name}")
    actual_sha256 = sha256_hex(payload)
    if actual_sha256 != contract["sha256"]:
        raise ValueError(f"stage0b input sha256 drift: {name}")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"stage0b input JSON contract: {name}") from error
    if type(value) is not dict:
        raise ValueError(f"stage0b input top-level type: {name}")
    return value


def load_stage0a_inputs(root: str | Path) -> dict[str, Any]:
    root_path = _real_root(root)
    return {
        name: _read_frozen_artifact(root_path, name)
        for name in INPUT_ARTIFACTS
    }
