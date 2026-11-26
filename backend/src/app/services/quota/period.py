"""Billing period of one user (story 1.6)."""

import calendar
from datetime import date

from src.app.contracts.quota import QuotaPeriod


def _period_start_for(today: date, anchor_day: int) -> date:
    """The first day of the period that ``today`` falls into.

    ``anchor_day`` is the user's billing day; it is clamped to the last
    day of short months (Feb 29 -> Feb 28, day 30/31 -> 28/29/30) and
    the period rolls on that day: before it, the current period is the
    previous month's.
    """
    clamped = min(anchor_day, calendar.monthrange(today.year, today.month)[1])
    if today.day >= clamped:
        return today.replace(day=clamped)
    if today.month == 1:
        previous_year, previous_month = today.year - 1, 12
    else:
        previous_year, previous_month = today.year, today.month - 1
    previous_clamped = min(anchor_day, calendar.monthrange(previous_year, previous_month)[1])
    return date(previous_year, previous_month, previous_clamped)


def current_period(today: date, anchor: date | None) -> QuotaPeriod:
    """``(start, end)`` of the current period; ``end`` is the next period's start."""
    anchor_day = anchor.day if anchor is not None else 1
    start = _period_start_for(today, anchor_day)
    next_year, next_month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    end = date(next_year, next_month, min(anchor_day, calendar.monthrange(next_year, next_month)[1]))
    return QuotaPeriod(start=start, end=end)


__all__ = ["current_period"]
