"""Clock boundary and immutable trusted Clock implementations."""

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware instant."""


class SystemClock:
    """Final stateless UTC wall Clock for production composition roots."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("SystemClock is final")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("SystemClock configuration is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("SystemClock configuration is immutable")

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Final immutable UTC Clock for deterministic trusted execution."""

    __slots__ = ("_instant",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("FixedClock is final")

    def __init__(self, instant: datetime) -> None:
        if type(instant) is not datetime or instant.utcoffset() != timedelta(0):
            raise ValueError("FixedClock instant must be an exact UTC datetime")
        object.__setattr__(self, "_instant", instant)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("FixedClock configuration is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("FixedClock configuration is immutable")

    def now(self) -> datetime:
        return self._instant


__all__ = ["Clock", "FixedClock", "SystemClock"]
