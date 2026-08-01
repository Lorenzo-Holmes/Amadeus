"""Clock boundary used by deterministic Core services."""

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware instant."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
