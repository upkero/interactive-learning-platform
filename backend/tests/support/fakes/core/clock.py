"""Controllable clock for billing tests."""

from datetime import date

from src.app.core.clock import Clock


class FixedClock(Clock):
    def __init__(self, today: date) -> None:
        self.value = today

    def today(self) -> date:
        return self.value
