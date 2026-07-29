import json
import tempfile
from pathlib import Path
from typing import Any

from .checklist import checklist_bytes
from .constants import (
    CHECKLIST_PATH,
    MANIFEST_PATH,
    REPORT_PATH,
    REVIEWED_PATH,
)
from .io import canonical_bytes, sha256_hex
from .schema import validate_reviewed_manifest


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _reviewed_value(root: Path, checklist: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    path = root / REVIEWED_PATH
    if _is_link_or_junction(path) or not path.is_file():
        raise ValueError("stage0b reviewed manifest file identity")
    payload = path.read_bytes()
    try:
        reviewed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("stage0b reviewed manifest JSON contract") from error
    validate_reviewed_manifest(reviewed, checklist)
    if payload != canonical_bytes(reviewed) + b"\n":
        raise ValueError("stage0b reviewed manifest canonical bytes")
    return reviewed, payload


def build_generated_values(root: str | Path) -> dict[str, dict[str, Any]]:
    root_path = Path(root).resolve(strict=True)
    checklist_payload = checklist_bytes(root_path)
    checklist = json.loads(checklist_payload.decode("utf-8"))
    reviewed, reviewed_payload = _reviewed_value(root_path, checklist)

    source_records = []
    clause_records = []
    for decision in reviewed["decisions"]:
        decision_sha256 = sha256_hex(canonical_bytes(decision))
        clause_ids = [clause["clause_id"] for clause in decision["clauses"]]
        source_records.append({
            "source_id": decision["source_id"],
            "source_group": decision["source_group"],
            "source_binding_sha256": decision["source_binding_sha256"],
            "assigned_oracle_kinds": decision["assigned_oracle_kinds"],
            "atomicity_decision": decision["atomicity_decision"],
            "decision_sha256": decision_sha256,
            "required_clause_ids": clause_ids,
        })
        for clause in decision["clauses"]:
            record = {
                "clause_id": clause["clause_id"],
                "source_id": decision["source_id"],
                "source_group": decision["source_group"],
                "source_binding_sha256": decision["source_binding_sha256"],
                "decision_sha256": decision_sha256,
                "stimulus_scope": clause["stimulus_scope"],
                "expected_scope": clause["expected_scope"],
                "required_oracle_kinds": clause["required_oracle_kinds"],
                "clause_stimulus_sha256": sha256_hex(
                    clause["stimulus_scope"].encode("utf-8")
                ),
                "clause_expected_sha256": sha256_hex(
                    clause["expected_scope"].encode("utf-8")
                ),
            }
            record["clause_content_sha256"] = sha256_hex(
                canonical_bytes(record)
            )
            clause_records.append(record)

    atomic_count = sum(
        decision["atomicity_decision"] == "atomic"
        for decision in reviewed["decisions"]
    )
    composite_count = len(reviewed["decisions"]) - atomic_count
    manifest = {
        "schema_version": "0.1",
        "stage0a_input_artifacts": reviewed["input_artifacts"],
        "checklist_sha256": sha256_hex(checklist_payload),
        "reviewed_manifest_sha256": sha256_hex(reviewed_payload),
        "source_count": len(source_records),
        "atomic_source_count": atomic_count,
        "composite_source_count": composite_count,
        "clause_count": len(clause_records),
        "sources": source_records,
        "clauses": clause_records,
    }
    manifest_payload = canonical_bytes(manifest) + b"\n"
    report = {
        "schema_version": "0.1",
        "checklist_sha256": sha256_hex(checklist_payload),
        "reviewed_manifest_sha256": sha256_hex(reviewed_payload),
        "source_clause_manifest_sha256": sha256_hex(manifest_payload),
        "source_adjudication_ready": True,
        "reviewed_sources": len(source_records),
        "atomic_sources": atomic_count,
        "composite_sources": composite_count,
        "clause_count": len(clause_records),
        "pending_oracle_assignments": 0,
        "pending_atomicity_reviews": 0,
        "atomicity_complete": True,
        "case_coverage_complete": False,
        "catalog_ready": False,
        "release_ready": False,
    }
    return {"manifest": manifest, "report": report}


def generated_artifacts(root: str | Path) -> dict[str, bytes]:
    values = build_generated_values(root)
    return {
        CHECKLIST_PATH.name: checklist_bytes(root),
        MANIFEST_PATH.name: canonical_bytes(values["manifest"]) + b"\n",
        REPORT_PATH.name: canonical_bytes(values["report"]) + b"\n",
    }


def _output_directory(root: Path, output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return root / CHECKLIST_PATH.parent
    candidate = Path(output_dir)
    return candidate if candidate.is_absolute() else root / candidate


def _prepare_output_directory(path: Path) -> None:
    if path.exists():
        if _is_link_or_junction(path) or not path.is_dir():
            raise OSError("stage0b output root must be a real directory")
        return
    path.mkdir(parents=True)
    if _is_link_or_junction(path) or not path.is_dir():
        raise OSError("stage0b output root must be a real directory")


def _plain_file(path: Path) -> bool:
    return path.is_file() and not _is_link_or_junction(path)


def _drift(
    output_dir: Path,
    artifacts: dict[str, bytes],
) -> tuple[list[str], list[str], list[str]]:
    if not output_dir.exists():
        return sorted(artifacts), [], []
    if _is_link_or_junction(output_dir) or not output_dir.is_dir():
        raise OSError("stage0b output root must be a real directory")
    entries = {entry.name: entry for entry in output_dir.iterdir()}
    missing = sorted(name for name in artifacts if name not in entries)
    unexpected = sorted(name for name in entries if name not in artifacts)
    changed = []
    for name, expected in artifacts.items():
        if name not in entries:
            continue
        entry = entries[name]
        if not _plain_file(entry) or entry.read_bytes() != expected:
            changed.append(name)
    return missing, sorted(changed), unexpected


def write_generated(
    root: str | Path,
    output_dir: str | Path | None = None,
) -> None:
    root_path = Path(root).resolve(strict=True)
    artifacts = generated_artifacts(root_path)
    destination = _output_directory(root_path, output_dir)
    _prepare_output_directory(destination)
    entries = {entry.name: entry for entry in destination.iterdir()}
    unexpected = sorted(name for name in entries if name not in artifacts)
    if unexpected:
        raise OSError(f"stage0b unexpected output: {','.join(unexpected)}")
    for name in artifacts:
        if name in entries and not _plain_file(entries[name]):
            raise OSError(f"stage0b unsafe output entry: {name}")
    for name, payload in artifacts.items():
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{name}.",
                suffix=".tmp",
                dir=destination,
                delete=False,
            ) as handle:
                handle.write(payload)
                temporary_path = Path(handle.name)
            temporary_path.replace(destination / name)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def check_generated(
    root: str | Path,
    output_dir: str | Path | None = None,
) -> tuple[list[str], list[str], list[str]]:
    root_path = Path(root).resolve(strict=True)
    artifacts = generated_artifacts(root_path)
    destination = _output_directory(root_path, output_dir)
    return _drift(destination, artifacts)
