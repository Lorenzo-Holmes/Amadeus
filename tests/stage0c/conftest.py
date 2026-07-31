# tests/stage0c/conftest.py
from pathlib import Path

import pytest

from tools.stage0c_fixtures.checklist import build_conversion_checklist
from tools.stage0c_fixtures.io import load_frozen_inputs
from tools.stage0c_fixtures.schema import build_fixture_case_schema


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def frozen_inputs(repository_root: Path):
    return load_frozen_inputs(repository_root)


@pytest.fixture
def checklist(frozen_inputs):
    return build_conversion_checklist(frozen_inputs)


@pytest.fixture
def fixture_schema():
    return build_fixture_case_schema()
