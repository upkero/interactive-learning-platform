"""Deterministic time access for services (story 1.6.2).

Quota periods depend on "today": production uses the real UTC clock,
tests inject a fixed ``Clock`` to keep dates deterministic.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def today(self) -> date: ...


@dataclass(frozen=True, slots=True)
class SystemClock:
    def today(self) -> date:
        return datetime.now(UTC).date()
