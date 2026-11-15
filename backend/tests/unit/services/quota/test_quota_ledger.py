"""Unit tests 1.6.2: quota period computation and the read-only ledger."""

from datetime import date, datetime
from uuid import uuid4

import pytest

from src.app.contracts.quota import LedgerOp
from src.app.contracts.users import UserRecord
from src.app.core.clock import Clock
from src.app.services.quota.ledger import QuotaLedger, period_bounds, period_start_for
from tests.support.fakes.repositories.quota import FakeGenerationLedgerRepository
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


class _FixedClock(Clock):
    def __init__(self, today: date) -> None:
        self._today = today

    def today(self) -> date:
        return self._today


def _user(period_anchor: date | None = None, monthly_limit: int = 20) -> UserRecord:
    return UserRecord(
        id=uuid4(),
        email="u@example.com",
        password_hash="hash",
        display_name=None,
        locale="ru",
        monthly_limit=monthly_limit,
        period_anchor=period_anchor,
        profile={},
        notify_email=True,
        created_at=datetime(2026, 1, 1, tzinfo=None),
    )


def test_period_without_anchor_starts_on_the_first() -> None:
    start, end = period_bounds(date(2026, 11, 14), anchor_day=1)
    assert (start, end) == (date(2026, 11, 1), date(2026, 11, 30))


def test_period_with_anchor_and_clamping_for_short_months() -> None:
    # billing day 31 rolls to Nov 30: today (Nov 14) is still inside
    # the period that started on Oct 31
    start, end = period_bounds(date(2026, 11, 14), anchor_day=31)
    assert (start, end) == (date(2026, 10, 31), date(2026, 11, 29))
    # February: day 30 clamps to the 28th (2026 is not a leap year);
    # on Feb 10 the current period started on Jan 30
    assert period_start_for(date(2026, 2, 10), anchor_day=30) == date(2026, 1, 30)
    assert period_start_for(date(2026, 2, 28), anchor_day=30) == date(2026, 2, 28)


def test_period_start_uses_the_anchor_day_in_the_current_month() -> None:
    # billing day 15: on Nov 14 the period started on Oct 15
    start, end = period_bounds(date(2026, 11, 14), anchor_day=15)
    assert (start, end) == (date(2026, 10, 15), date(2026, 11, 14))
    # on the billing day itself the new period opens
    assert period_start_for(date(2026, 11, 15), anchor_day=15) == date(2026, 11, 15)


async def test_available_is_limit_plus_deltas_and_reads_nothing() -> None:
    users = FakeUserRepository()
    # billing day 15: the current period is Oct 15 - Nov 14
    user = _user(period_anchor=date(2000, 1, 15), monthly_limit=20)
    users._users[user.id] = user
    ledger = FakeGenerationLedgerRepository()
    # reserved 5 parts, refunded 1: available = 20 - 5 + 1
    await ledger.add(user_id=user.id, op=LedgerOp.RESERVE, delta=-5, period_start=date(2026, 10, 15))
    await ledger.add(user_id=user.id, op=LedgerOp.REFUND, delta=1, period_start=date(2026, 10, 20))
    # an entry from an older period does not count
    await ledger.add(user_id=user.id, op=LedgerOp.RESERVE, delta=-7, period_start=date(2026, 9, 1))

    quota = QuotaLedger(users=users, ledger=ledger, clock=_FixedClock(date(2026, 11, 14)))
    assert await quota.available(user.id) == 16

    # nothing written by a read
    assert len(ledger._entries) == 3
