"""Billing boundaries, including short months and year changes."""

from datetime import date

import pytest

from src.app.services.quota.period import current_period

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("today", "anchor", "start", "end"),
    [
        (date(2026, 1, 1), None, date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 12, 31), None, date(2026, 12, 1), date(2027, 1, 1)),
        (date(2026, 2, 10), date(2000, 1, 30), date(2026, 1, 30), date(2026, 2, 28)),
        (date(2026, 2, 28), date(2000, 1, 30), date(2026, 2, 28), date(2026, 3, 30)),
        (date(2024, 2, 28), date(2000, 1, 31), date(2024, 1, 31), date(2024, 2, 29)),
        (date(2024, 2, 29), date(2000, 1, 31), date(2024, 2, 29), date(2024, 3, 31)),
        (date(2025, 2, 27), date(2000, 1, 31), date(2025, 1, 31), date(2025, 2, 28)),
        (date(2025, 2, 28), date(2000, 1, 31), date(2025, 2, 28), date(2025, 3, 31)),
        (date(2026, 4, 30), date(2000, 1, 31), date(2026, 4, 30), date(2026, 5, 31)),
        (date(2026, 11, 14), date(2000, 1, 15), date(2026, 10, 15), date(2026, 11, 15)),
        (date(2026, 11, 15), date(2000, 1, 15), date(2026, 11, 15), date(2026, 12, 15)),
        (date(2026, 11, 16), date(2000, 1, 15), date(2026, 11, 15), date(2026, 12, 15)),
        (date(2026, 1, 1), date(2000, 1, 15), date(2025, 12, 15), date(2026, 1, 15)),
        (date(2026, 12, 31), date(2000, 1, 31), date(2026, 12, 31), date(2027, 1, 31)),
    ],
)
def test_period_boundaries(today: date, anchor: date | None, start: date, end: date) -> None:
    period = current_period(today, anchor)
    assert (period.start, period.end) == (start, end)
