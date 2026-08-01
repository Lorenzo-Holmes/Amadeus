import hashlib
import json
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_hash_scope_registry_digest_matches_json_txt_and_python() -> None:
    from amadeus_core.contracts import registry

    contracts = _root() / "src" / "amadeus_core" / "contracts"
    raw = (contracts / "hash_scope_registry_v0_1.json").read_bytes()
    digest_text = (contracts / "hash_scope_registry_digest.txt").read_text(encoding="ascii")
    digest = hashlib.sha256(raw).hexdigest()

    assert raw.endswith(b"\n")
    assert digest_text == f"{digest}\n"
    assert registry.HASH_SCOPE_REGISTRY_DIGEST == digest
    assert len(registry.HASH_SCOPE_REGISTRY) == 17


def test_hash_scope_registry_is_sorted_unique_and_matches_json() -> None:
    from amadeus_core.contracts import registry

    raw = (_root() / "src" / "amadeus_core" / "contracts" / "hash_scope_registry_v0_1.json").read_bytes()
    artifact = json.loads(raw)
    from_json = {
        (entry["record_type"], entry["schema_version"]): tuple(entry["hash_scope"])
        for entry in artifact["entries"]
    }

    assert from_json == dict(registry.HASH_SCOPE_REGISTRY)
    for pointers in from_json.values():
        assert pointers == tuple(sorted(set(pointers)))


def test_hash_scope_excludes_outputs_and_signatures_but_keeps_chain_fields() -> None:
    from amadeus_core.contracts.registry import HASH_SCOPE_REGISTRY

    ledger = HASH_SCOPE_REGISTRY[("LedgerEvent", "0.1")]
    governor = HASH_SCOPE_REGISTRY[("GovernorDecision", "0.1")]
    capability = HASH_SCOPE_REGISTRY[("VaultReadCapability", "0.1")]

    assert "/record_header/content_hash" not in ledger
    assert "/record_header/hash_scope" not in ledger
    assert "/record_header/hash_scope_registry_digest" not in ledger
    assert "/event_hash" not in ledger
    assert "/previous_event_hash" in ledger
    assert "/governor_signature" not in governor
    assert "/attestation" not in capability
    assert "/record_header/record_id" in ledger
    assert "/version" in ledger


def test_hash_registry_generator_check_has_zero_diff() -> None:
    from tools.compile_hash_registry import compile_hash_registry

    root = _root()
    report = compile_hash_registry(
        manifest_path=root / "src" / "amadeus_core" / "contracts" / "schema_manifest_v0_1.json",
        output_path=root / "src" / "amadeus_core" / "contracts" / "hash_scope_registry_v0_1.json",
        digest_output_path=root / "src" / "amadeus_core" / "contracts" / "hash_scope_registry_digest.txt",
        module_output_path=root / "src" / "amadeus_core" / "contracts" / "hash_scope.py",
        check=True,
    )
    assert report.registry_entries == 17
    assert report.changed_paths == ()
