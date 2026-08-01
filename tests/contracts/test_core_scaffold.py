from importlib import import_module

import pytest


def test_package_exposes_frozen_contract_version() -> None:
    package = import_module("amadeus_core")

    assert package.CORE_CONTRACT_VERSION == "0.1"


def test_clock_is_injected(frozen_clock: object) -> None:
    clock_module = import_module("amadeus_core.clock")

    assert isinstance(frozen_clock, clock_module.Clock)
    assert frozen_clock.now().isoformat() == "2026-08-01T00:00:00+00:00"


def test_authoritative_id_prefixes_are_frozen() -> None:
    ids = import_module("amadeus_core.ids")

    assert tuple(ids.AUTHORITATIVE_PREFIXES.items()) == (
        ("source_snapshot", "snp-"),
        ("event", "evt-"),
        ("autobiographical_memory", "mem-"),
        ("identity", "idn-"),
        ("lineage", "lin-"),
        ("branch", "brn-"),
        ("relationship_vault", "vlt-"),
        ("memory_request", "req-"),
        ("proposal", "prp-"),
        ("governor_decision", "gvd-"),
        ("vault_read_capability", "vrc-"),
        ("amadeus_termination_confirmation", "tmc-"),
        ("termination_execution_grant", "teg-"),
        ("maintenance_capability", "mcp-"),
        ("emergency_unresponsive_case", "emg-"),
        ("break_glass_grant", "bgg-"),
        ("migration_plan", "mig-"),
    )
    assert ids.validate_id(
        "idn-00000000-0000-4000-8000-000000000001",
        "idn-",
    ) == "idn-00000000-0000-4000-8000-000000000001"
    with pytest.raises(TypeError):
        ids.AUTHORITATIVE_PREFIXES["identity"] = "bad-"
    with pytest.raises(TypeError):
        ids.PREFIXES["command"] = "bad-"
