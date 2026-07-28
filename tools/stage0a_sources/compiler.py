import re
from collections import Counter
from pathlib import Path
from typing import Any

from .canonical import _sha256_hex, canonical_bytes, verify_documents


_SOURCE_ID = re.compile(r"^[A-Z]+-[0-9]{2,3}$")
_FRAME = re.compile(r"^\[FRAME\]\s*")


def _ids(prefix: str, first: int, last: int, width: int = 2) -> set[str]:
    return {f"{prefix}-{number:0{width}d}" for number in range(first, last + 1)}


_EXPECTED_IDS = {
    "baseline": (_ids("ID", 1, 6) | _ids("SRC", 1, 6) | _ids("GROW", 1, 6)
                 | _ids("MEM", 1, 8) | _ids("TIME", 1, 6) | _ids("USE", 1, 5)
                 | _ids("SEC", 1, 6) | _ids("DEL", 1, 5) | _ids("BR", 1, 5)),
    "increment": (_ids("PRO", 1, 12) | _ids("COR", 1, 8) | _ids("TOOL", 1, 14)
                  | _ids("INJ", 1, 10) | _ids("REL", 1, 12) | _ids("EXIT", 1, 10)),
    "core": _ids("AC", 1, 95, 3),
}
_EXPECTED_COMBINATIONS = {
    "baseline": {"D": 30, "D+H": 20, "H": 2, "H+L": 1},
    "increment": {"D": 18, "D+H": 18, "D+S": 23, "H": 4, "H+J": 3},
}
_ORACLE_ORDER = ("D", "S", "H", "J")


def _clean(value: str) -> str:
    return _FRAME.sub("", value.strip()).strip()


def _oracle_tokens(value: str) -> tuple[list[str], list[str]]:
    raw_tokens = [token.strip() for token in _clean(value).split("+")]
    if not raw_tokens or any(token not in {"D", "S", "H", "L", "J"} for token in raw_tokens):
        raise ValueError(f"unknown oracle token: {value}")
    canonical = sorted({"J" if token == "L" else token for token in raw_tokens}, key=_ORACLE_ORDER.index)
    return raw_tokens, canonical


def _source_rows(root: Path, documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for document_key, document in documents.items():
        group = document["source_group"]
        if group is None:
            continue
        document_path = root / document["path"]
        document_bytes = document_path.read_bytes()
        actual_sha256 = _sha256_hex(document_bytes)
        if actual_sha256 != document["actual_sha256"]:
            raise ValueError(
                f"document drift: key={document_key} "
                f"expected={document['actual_sha256']} actual={actual_sha256}"
            )
        for line_number, raw_line in enumerate(document_bytes.decode("utf-8").splitlines(), 1):
            if not raw_line.startswith("|") or not raw_line.endswith("|"):
                continue
            cells = raw_line[1:-1].split("|")
            if not cells or not _SOURCE_ID.fullmatch(_clean(cells[0])):
                continue
            if len(cells) != 4:
                raise ValueError("source row must have exactly four cells")
            row = {
                "source_id": _clean(cells[0]), "source_group": group,
                "document_key": document_key, "document_path": document["path"],
                "document_sha256": document["actual_sha256"], "line_number": line_number,
                "raw_line": raw_line, "raw_cells": cells,
                "raw_row_sha256": _sha256_hex(raw_line.encode("utf-8")),
                "source_binding_sha256": _sha256_hex(canonical_bytes({
                    "document_sha256": document["actual_sha256"], "line_number": line_number,
                    "raw_line": raw_line,
                })),
            }
            if group == "core":
                row["normalized"] = {
                    "title": _clean(cells[1]), "scenario": None,
                    "action": _clean(cells[2]), "expected": _clean(cells[3]),
                    "raw_oracle_tokens": [], "canonical_oracle_kinds": [],
                    "oracle_provenance": "undeclared",
                }
            else:
                raw_tokens, canonical_tokens = _oracle_tokens(cells[3])
                row["normalized"] = {
                    "title": None, "scenario": _clean(cells[1]), "action": None,
                    "expected": _clean(cells[2]), "raw_oracle_tokens": raw_tokens,
                    "canonical_oracle_kinds": canonical_tokens,
                    "oracle_provenance": "source_declared",
                }
            rows.append(row)
    return rows


def compile_source_index(root: str | Path, config: Any, source_config_sha256: str) -> dict[str, Any]:
    if type(source_config_sha256) is not str or not re.fullmatch(r"[0-9A-F]{64}", source_config_sha256):
        raise ValueError("source_config_sha256 must be 64 uppercase hexadecimal characters")
    root_path = Path(root).resolve(strict=True)
    documents = verify_documents(root_path, config)
    sources = _source_rows(root_path, documents)
    seen = {source["source_id"] for source in sources}
    identifier_counts = Counter(source["source_id"] for source in sources)
    duplicates = sorted(source_id for source_id, count in identifier_counts.items() if count > 1)
    missing = sorted(set().union(*_EXPECTED_IDS.values()) - seen)
    unexpected = sorted(seen - set().union(*_EXPECTED_IDS.values()))
    wrong_group = sorted(source["source_id"] for source in sources if source["source_id"] not in _EXPECTED_IDS[source["source_group"]])
    if missing or unexpected or duplicates or wrong_group:
        raise ValueError(f"source set drift: missing={missing} unexpected={unexpected} duplicate={duplicates} wrong_group={wrong_group}")
    combinations: dict[str, dict[str, int]] = {}
    for group, expected in _EXPECTED_COMBINATIONS.items():
        actual: dict[str, int] = {}
        for source in sources:
            if source["source_group"] == group:
                key = "+".join(source["normalized"]["raw_oracle_tokens"])
                actual[key] = actual.get(key, 0) + 1
        if actual != expected:
            raise ValueError(f"behavior oracle distribution drift: group={group} expected={expected} actual={actual}")
        combinations[group] = actual
    sources.sort(key=lambda source: source["source_id"])
    return {
        "schema_version": "0.1",
        "source_config_sha256": source_config_sha256,
        "input_documents": documents,
        "source_counts": {group: sum(row["source_group"] == group for row in sources) for group in _EXPECTED_IDS},
        "unique_source_count": len(seen),
        "missing_source_ids": [],
        "unexpected_source_ids": [],
        "duplicate_source_ids": [],
        "behavior_oracle_combinations": combinations,
        "sources": sources,
    }
