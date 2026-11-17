"""Unit tests 1.6.2: quota period computation and the ledger."""

from datetime import date, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.part_owner import PartOwner
from src.app.contracts.quota import LedgerOp
from src.app.contracts.users import UserRecord
from src.app.exceptions.quota import QuotaExceededError, QuotaPartNotFoundError, QuotaReservationNotFoundError
from src.app.services.quota.quota_ledger import QuotaLedger
from tests.support.fakes.core.clock import FixedClock
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository
from tests.support.fakes.repositories.quota import FakeGenerationLedgerRepository
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


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
        created_at=datetime(2026, 1, 1),
    )


def _ledger(users: FakeUserRepository, ledger: FakeGenerationLedgerRepository, today: date) -> QuotaLedger:
    return QuotaLedger(
        users_factory=lambda _: users,
        ledger_factory=lambda _: ledger,
        parts_factory=lambda _: FakeDocumentPartRepository(),
        clock=FixedClock(today),
    )


async def test_available_is_limit_plus_deltas_and_reads_nothing() -> None:
    users = FakeUserRepository()
    # billing day 15: the current period is Oct 15 - Nov 15 (exclusive)
    user = _user(period_anchor=date(2000, 1, 15), monthly_limit=20)
    users._users[user.id] = user
    entries = FakeGenerationLedgerRepository()
    # reserved 5 parts, refunded 1: available = 20 - 5 + 1
    await entries.add(user_id=user.id, op=LedgerOp.RESERVE, delta=-5, period_start=date(2026, 10, 15))
    await entries.add(user_id=user.id, op=LedgerOp.REFUND, delta=1, period_start=date(2026, 10, 15))
    # an entry from an older period does not count
    await entries.add(user_id=user.id, op=LedgerOp.RESERVE, delta=-7, period_start=date(2026, 9, 1))
    # a future period is excluded too
    await entries.add(user_id=user.id, op=LedgerOp.RESERVE, delta=-3, period_start=date(2026, 11, 15))

    ledger = _ledger(users, entries, date(2026, 11, 14))
    session = cast(AsyncSession, FakeSession())
    state = await ledger.available(session, user_id=user.id)
    assert state.available == 16
    assert state.monthly_limit == 20
    assert state.period.start == date(2026, 10, 15)
    assert state.period.end == date(2026, 11, 15)

    # nothing written by a read
    assert len(entries._entries) == 4


async def test_reserve_writes_a_negative_delta_and_replays_the_balance() -> None:
    users = FakeUserRepository()
    user = _user(monthly_limit=3)
    users._users[user.id] = user
    entries = FakeGenerationLedgerRepository()
    ledger = _ledger(users, entries, date(2026, 11, 14))
    session = cast(AsyncSession, FakeSession())
    document_id = uuid4()

    state = await ledger.reserve(session, user_id=user.id, document_id=document_id, parts=2)

    assert state.available == 1
    assert [(e.op, e.delta, e.document_id, e.period_start) for e in entries._entries] == [
        (LedgerOp.RESERVE, -2, document_id, date(2026, 11, 1))
    ]
    # the balance is derived from the journal, not cached on the user row
    assert (await ledger.available(session, user_id=user.id)).available == 1


async def test_insufficient_quota_does_not_write() -> None:
    users = FakeUserRepository()
    user = _user(monthly_limit=1)
    users._users[user.id] = user
    entries = FakeGenerationLedgerRepository()
    ledger = _ledger(users, entries, date(2026, 11, 14))
    with pytest.raises(QuotaExceededError) as error:
        await ledger.reserve(cast(AsyncSession, FakeSession()), user_id=user.id, document_id=uuid4(), parts=2)
    assert error.value.extra == {"available": 1, "requested": 2}
    assert not entries.entries


async def test_charge_and_refund_are_idempotent_and_use_reservation_period() -> None:
    users = FakeUserRepository()
    user = _user()
    users._users[user.id] = user
    entries = FakeGenerationLedgerRepository()
    parts = FakeDocumentPartRepository()
    document_id, part_id = uuid4(), uuid4()
    parts.owners[part_id] = PartOwner(user_id=user.id, document_id=document_id, quota_period_start=date(2026, 10, 1))
    await entries.add(
        user_id=user.id, document_id=document_id, op=LedgerOp.RESERVE, delta=-1, period_start=date(2026, 10, 1)
    )
    ledger = QuotaLedger(
        users_factory=lambda _: users,
        ledger_factory=lambda _: entries,
        parts_factory=lambda _: parts,
        clock=FixedClock(date(2026, 11, 14)),
    )
    session = cast(AsyncSession, FakeSession())
    for _ in range(2):
        await ledger.charge(session, part_id=part_id)
        await ledger.refund(session, part_id=part_id)
    assert [(entry.op, entry.delta, entry.period_start) for entry in entries.entries] == [
        (LedgerOp.RESERVE, -1, date(2026, 10, 1)),
        (LedgerOp.CHARGE, 0, date(2026, 10, 1)),
        (LedgerOp.REFUND, 1, date(2026, 10, 1)),
    ]


async def test_part_operations_reject_missing_part_and_reservation() -> None:
    users = FakeUserRepository()
    user = _user()
    users._users[user.id] = user
    entries = FakeGenerationLedgerRepository()
    parts = FakeDocumentPartRepository()
    ledger = QuotaLedger(
        users_factory=lambda _: users,
        ledger_factory=lambda _: entries,
        parts_factory=lambda _: parts,
        clock=FixedClock(date(2026, 11, 14)),
    )
    session = cast(AsyncSession, FakeSession())
    part_id = uuid4()
    with pytest.raises(QuotaPartNotFoundError):
        await ledger.refund(session, part_id=part_id)
    parts.owners[part_id] = PartOwner(user_id=user.id, document_id=uuid4(), quota_period_start=None)
    with pytest.raises(QuotaReservationNotFoundError):
        await ledger.charge(session, part_id=part_id)
