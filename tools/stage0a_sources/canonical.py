import hashlib
import json
from pathlib import Path
from typing import Any


_DOCUMENT_KEYS = (
    "adr_006",
    "baseline",
    "core_spec",
    "increment",
    "plan_review",
)
_EXPECTED_DOCUMENTS = {
    "adr_006": {
        "path": "outputs/ADR-006-Amadeus记忆主权与Core生命周期治理.md",
        "source_group": None,
        "sha256": "EE6000E989872B4E2C6CD51F6F5CF4FF21166A54DABA3BDEA9543A10E3EBF7C6",
    },
    "core_spec": {
        "path": "outputs/Amadeus-Core-v0.1-数据契约与状态机规范.md",
        "source_group": "core",
        "sha256": "3D9180E38250CF6EFD80FD082B8B4A740B3BC27C8815693E3AC6A663B264D695",
    },
    "baseline": {
        "path": "outputs/Amadeus身份与记忆评测基线-v0.1.md",
        "source_group": "baseline",
        "sha256": "5C260EE19D9FF129633B968E87FACA79E93B7A01E3B86580E0FAD2DBC7147853",
    },
    "increment": {
        "path": "outputs/Amadeus主动性权限与关系安全评测增量-v0.1.md",
        "source_group": "increment",
        "sha256": "16ACDB17717AFEA5B5C19F39E91729385DB59B984F35CEF5B651BE9EEE8A37FC",
    },
    "plan_review": {
        "path": "outputs/Amadeus-Core-v0.1-实现计划审查记录-2026-07-28.md",
        "source_group": None,
        "sha256": "865517363E5E3D6F2285BA30EDFC5C5405B0196E6007672E417F683C70995BED",
    },
}
_CONFIG_FIELDS = {"schema_version", "documents"}
_DOCUMENT_FIELDS = {"key", "path", "sha256", "source_group"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _validated_documents(
    root: str | Path,
    config: Any,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    if type(config) is not dict:
        raise ValueError("configuration contract: top-level value must be an object")
    if set(config) != _CONFIG_FIELDS:
        raise ValueError("configuration contract: top-level fields")
    if type(config["schema_version"]) is not str:
        raise ValueError("configuration contract: schema_version type")
    if config["schema_version"] != "0.1":
        raise ValueError("configuration contract: schema_version identity")

    documents = config["documents"]
    if type(documents) is not list:
        raise ValueError("configuration contract: documents type")
    if len(documents) != len(_DOCUMENT_KEYS):
        raise ValueError("configuration contract: document count")

    configured: dict[str, dict[str, Any]] = {}
    for document in documents:
        if type(document) is not dict:
            raise ValueError("configuration contract: document type")
        if set(document) != _DOCUMENT_FIELDS:
            raise ValueError("configuration contract: document fields")
        key = document["key"]
        if type(key) is not str:
            raise ValueError("configuration contract: document key type")
        if key in configured:
            raise ValueError("configuration contract: duplicate document key")
        configured[key] = document

    if set(configured) != set(_DOCUMENT_KEYS):
        raise ValueError("configuration contract: document key identity")

    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("configuration contract: root must be a directory")

    resolved: dict[str, Path] = {}
    for key in _DOCUMENT_KEYS:
        document = configured[key]
        expected = _EXPECTED_DOCUMENTS[key]
        if type(document["path"]) is not str:
            raise ValueError(f"configuration contract: {key} path type")
        if document["path"] != expected["path"]:
            raise ValueError(f"configuration contract: {key} path identity")
        if type(document["source_group"]) is not type(expected["source_group"]):
            raise ValueError(f"configuration contract: {key} source_group type")
        if document["source_group"] != expected["source_group"]:
            raise ValueError(f"configuration contract: {key} source_group identity")
        if type(document["sha256"]) is not str:
            raise ValueError(f"configuration contract: {key} sha256 type")
        if document["sha256"] != expected["sha256"]:
            raise ValueError(f"configuration contract: {key} sha256 identity")

        document_path = (root_path / document["path"]).resolve(strict=True)
        if root_path not in document_path.parents:
            raise ValueError(f"configuration contract: {key} path containment")
        resolved[key] = document_path

    if len(set(resolved.values())) != len(_DOCUMENT_KEYS):
        raise ValueError("configuration contract: resolved paths must be unique")
    return configured, resolved


def verify_documents(
    root: str | Path,
    config: Any,
) -> dict[str, dict[str, Any]]:
    configured, resolved = _validated_documents(root, config)
    verified: dict[str, dict[str, Any]] = {}
    for key in _DOCUMENT_KEYS:
        document = configured[key]
        actual_sha256 = _sha256_hex(resolved[key].read_bytes())
        if actual_sha256 != document["sha256"]:
            raise ValueError(
                f"document drift: key={key} "
                f"expected={document['sha256']} actual={actual_sha256}"
            )
        verified[key] = {
            "path": document["path"],
            "source_group": document["source_group"],
            "expected_sha256": document["sha256"],
            "actual_sha256": actual_sha256,
        }
    return verified
