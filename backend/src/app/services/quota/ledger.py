"""Quota accounting over the generation ledger (story 1.6).

The balance is never stored on the user row: it is derived from the
deltas of the append-only ``generation_ledger`` table,
``available = monthly_limit + sum(delta)`` over the current period.
The period starts on the 1st of the current month, or on the billing
anchor day when the user has one (clamped to short months).
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from src.app.contracts.users import UserRecord
from src.app.core.clock import Clock, SystemClock
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol


def period_start_for(today: date, anchor_day: int) -> date:
    """The start of the period that ``today`` falls into.

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


def period_bounds(today: date, anchor_day: int) -> tuple[date, date]:
    """``(period_start, period_end)`` of the current period, inclusive."""
    start = period_start_for(today, anchor_day)
    next_month = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    next_start = min(anchor_day, calendar.monthrange(next_month.year, next_month.month)[1])
    end = next_month.replace(day=next_start) - timedelta(days=1)
    return start, end


@dataclass(frozen=True, slots=True)
class QuotaPeriod:
    period_start: date
    period_end: date
    monthly_limit: int
    available: int


class QuotaLedger:
    """Read/reserve accounting; all writes lock the users row first."""

    def __init__(
        self,
        *,
        users: UserRepositoryProtocol,
        ledger: GenerationLedgerRepositoryProtocol,
        clock: Clock | None = None,
    ) -> None:
        self._users = users
        self._ledger = ledger
        self._clock: Clock = clock or SystemClock()

    def _period(self, user: UserRecord) -> tuple[date, date]:
        anchor_day = user.period_anchor.day if user.period_anchor is not None else 1
        return period_bounds(self._clock.today(), anchor_day)

    async def status(self, user_id: UUID) -> QuotaPeriod:
        """Read-only quota status: limit, remaining balance and period bounds."""
        user = await self._users.get(user_id)
        if user is None:
            raise KeyError(f"User {user_id} does not exist")
        start, end = self._period(user)
        used = await self._ledger.sum_delta(user_id, start)
        return QuotaPeriod(
            period_start=start,
            period_end=end,
            monthly_limit=user.monthly_limit,
            # deltas: reserve is negative, refund positive (story 1.6.1)
            available=user.monthly_limit + used,
        )

    async def available(self, user_id: UUID) -> int:
        status = await self.status(user_id)
        return status.available
