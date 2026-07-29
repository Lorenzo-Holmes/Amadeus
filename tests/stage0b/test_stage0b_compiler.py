import hashlib
import json
from pathlib import Path

from tools.stage0b_adjudication.compiler import build_generated_values
from tools.stage0b_adjudication.io import canonical_bytes


ROOT = Path(__file__).resolve().parents[2]


def test_compiler_binds_all_sources_clauses_and_reviewed_bytes() -> None:
    values = build_generated_values(ROOT)
    manifest = values["manifest"]
    report = values["report"]

    assert manifest["source_count"] == 214
    assert manifest["atomic_source_count"] == 185
    assert manifest["composite_source_count"] == 29
    assert manifest["clause_count"] == 259
    assert len(manifest["sources"]) == 214
    assert len(manifest["clauses"]) == 259
    assert len({item["source_id"] for item in manifest["sources"]}) == 214
    assert len({item["clause_id"] for item in manifest["clauses"]}) == 259

    reviewed_bytes = (
        ROOT / "fixtures/stage0b/reviewed/source_decisions_v0_1.json"
    ).read_bytes()
    assert manifest["reviewed_manifest_sha256"] == hashlib.sha256(
        reviewed_bytes
    ).hexdigest().upper()

    first = manifest["clauses"][0]
    assert first["clause_id"] == "AC-001#1"
    assert first["source_id"] == "AC-001"
    assert first["clause_stimulus_sha256"] == hashlib.sha256(
        first["stimulus_scope"].encode("utf-8")
    ).hexdigest().upper()
    assert first["clause_expected_sha256"] == hashlib.sha256(
        first["expected_scope"].encode("utf-8")
    ).hexdigest().upper()
    content = {
        key: first[key]
        for key in (
            "clause_id",
            "source_id",
            "source_group",
            "source_binding_sha256",
            "decision_sha256",
            "stimulus_scope",
            "expected_scope",
            "required_oracle_kinds",
            "clause_stimulus_sha256",
            "clause_expected_sha256",
        )
    }
    assert first["clause_content_sha256"] == hashlib.sha256(
        canonical_bytes(content)
    ).hexdigest().upper()

    assert report["source_adjudication_ready"] is True
    assert report["reviewed_sources"] == 214
    assert report["pending_oracle_assignments"] == 0
    assert report["pending_atomicity_reviews"] == 0
    assert report["atomicity_complete"] is True
    assert report["case_coverage_complete"] is False
    assert report["catalog_ready"] is False
    assert report["release_ready"] is False


def test_compiler_is_deterministic() -> None:
    first = build_generated_values(ROOT)
    second = build_generated_values(ROOT)
    assert canonical_bytes(first) == canonical_bytes(second)
