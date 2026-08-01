from dataclasses import dataclass
from datetime import UTC, datetime

import pytest


@dataclass(frozen=True, slots=True)
class FrozenClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


@pytest.fixture
def frozen_clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 8, 1, tzinfo=UTC))
