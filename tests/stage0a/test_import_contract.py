from tools.stage0a_sources import SCHEMA_VERSION


def test_schema_version() -> None:
    assert SCHEMA_VERSION == "0.1"
