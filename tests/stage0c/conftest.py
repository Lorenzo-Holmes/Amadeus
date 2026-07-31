# tests/stage0c/conftest.py
from pathlib import Path

import pytest

from tools.stage0c_fixtures.io import load_frozen_inputs


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def frozen_inputs(repository_root: Path):
    return load_frozen_inputs(repository_root)
