import hashlib
import json
from pathlib import Path

import pytest


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _document(doc_id: str, title: str, path: str, data: bytes) -> dict:
    return {
        "doc_id": doc_id,
        "title": title,
        "path": path,
        "kind": "developer-documentation",
        "authority": "canonical",
        "status": "active",
        "stage": "cross-stage",
        "index": True,
        "sensitivity": "internal",
        "sha256": _sha256(data),
    }


@pytest.fixture
def kb_root(tmp_path: Path) -> Path:
    readme = (
        b"# Project KB\n"
        b"## Overview\n"
        b"Needle alpha\n"
        b"needle beta\n"
        b"  Indented needle  \n"
    )
    navigation = (
        "# Data structure\n"
        "## Navigation\n"
        "Needle gamma\n"
    ).encode("utf-8")

    (tmp_path / "README.md").write_bytes(readme)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "data_structure.md").write_bytes(navigation)
    raw = knowledge / "90_raw"
    raw.mkdir()
    (raw / "secret.md").write_text(
        "# Raw\nraw-only-secret\n",
        encoding="utf-8",
    )

    policy = {
        "version": 1,
        "path_style": "repo-relative-posix",
        "glob_syntax": "gitwildmatch",
        "exclude_precedence": True,
        "default_index": False,
        "follow_gitignore": False,
        "include": [
            "README.md",
            "knowledge/data_structure.md",
            "outputs/**/*.md",
            "knowledge/30_research/legacy/*.md",
            "knowledge/40_history/legacy/*.md",
        ],
        "exclude": [
            "knowledge/90_raw/**",
            ".git/**",
            ".local/**",
            ".worktrees/**",
        ],
    }
    _write_json(knowledge / "index-policy.json", policy)

    manifest = {
        "schema_version": "0.1",
        "documents": [
            _document("root-readme", "Project KB", "README.md", readme),
            _document(
                "kb-navigation",
                "Data structure",
                "knowledge/data_structure.md",
                navigation,
            ),
        ],
    }
    _write_json(knowledge / "manifest.json", manifest)
    return tmp_path


@pytest.fixture
def json_helpers():
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    return load, _write_json, _document, _sha256
