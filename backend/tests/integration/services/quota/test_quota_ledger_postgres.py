"""Ledger transaction and period isolation on PostgreSQL."""

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents import PartDraft
from src.app.contracts.quota import LedgerOp
from src.app.exceptions.quota import QuotaReservationNotFoundError
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.user import User
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.quota.quota_ledger import QuotaLedger
from tests.support.fakes.core.clock import FixedClock

pytestmark = pytest.mark.integration


async def test_user_lock_refreshes_previously_loaded_quota(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, _, _ = part_ids
    async with session_factory() as first, first.begin():
        cached = await first.get(User, user_id)
        assert cached is not None and cached.monthly_limit == 20
        async with session_factory() as second, second.begin():
            await second.execute(update(User).where(User.id == user_id).values(monthly_limit=7))
        locked = await UserRepository(first).lock_for_update(user_id)
        assert locked is not None and locked.monthly_limit == 7
        assert cached.monthly_limit == 7


@pytest.mark.parametrize("operation", ["charge", "refund"])
async def test_unreserved_part_cannot_be_accounted(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
    operation: str,
) -> None:
    _, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        await session.execute(update(DocumentPart).where(DocumentPart.id == part_id).values(quota_period_start=None))
    async with session_factory() as session, session.begin():
        with pytest.raises(QuotaReservationNotFoundError):
            await getattr(container.quota_ledger, operation)(session, part_id=part_id)
    async with session_factory() as session:
        assert (await session.scalars(select(GenerationLedger))).all() == []


async def test_duplicate_refund_preserves_outer_transaction(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, part_id = part_ids
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
    async with session_factory() as session, session.begin():
        await ledger.refund(session, part_id=part_id)
        await ledger.refund(session, part_id=part_id)
        await session.execute(update(User).where(User.id == user_id).values(display_name="transaction survives"))
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == part_id))).all()
        assert [(e.op, e.delta) for e in entries] == [(LedgerOp.REFUND.value, 1)]
        assert await session.scalar(select(User.display_name).where(User.id == user_id)) == "transaction survives"
        assert (await ledger.available(session, user_id=user_id)).available == 20


async def test_sum_delta_excludes_other_periods(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, _ = part_ids
    async with session_factory() as session, session.begin():
        repo = GenerationLedgerRepository(session)
        for month, delta in ((10, -2), (11, -3), (12, -5)):
            await repo.add(
                user_id=user_id,
                document_id=document_id,
                op=LedgerOp.RESERVE,
                delta=delta,
                period_start=date(2026, month, 1),
            )
        assert await repo.sum_delta(user_id, date(2026, 11, 1)) == -3


async def test_old_part_refund_ignores_newer_document_reservation(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, _ = part_ids
    clock = FixedClock(date(2026, 10, 31))
    ledger = QuotaLedger(
        users_factory=UserRepository,
        ledger_factory=GenerationLedgerRepository,
        parts_factory=DocumentPartRepository,
        clock=clock,
    )
    batch_parts: list[UUID] = []
    for index, today in enumerate((date(2026, 10, 31), date(2026, 11, 1)), start=1):
        clock.value = today
        async with session_factory() as session, session.begin():
            state = await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
            (part,) = await DocumentPartRepository(session).add_many(
                document_id,
                [
                    PartDraft(
                        index=index,
                        title="Batch",
                        topic_ids=[],
                        source_markdown="text",
                        token_count=1,
                        quota_period_start=state.period.start,
                    )
                ],
            )
            batch_parts.append(part.id)
    async with session_factory() as session, session.begin():
        await ledger.refund(session, part_id=batch_parts[0])
        await ledger.charge(session, part_id=batch_parts[0])
    async with session_factory() as session:
        repo = GenerationLedgerRepository(session)
        assert await repo.sum_delta(user_id, date(2026, 10, 1)) == 0
        assert await repo.sum_delta(user_id, date(2026, 11, 1)) == -1
        assert (await ledger.available(session, user_id=user_id)).available == 19
        entries = (
            await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == batch_parts[0]))
        ).all()
        assert {(entry.op, entry.period_start) for entry in entries} == {
            (LedgerOp.REFUND.value, date(2026, 10, 1)),
            (LedgerOp.CHARGE.value, date(2026, 10, 1)),
        }


async def test_old_reservation_refunded_in_original_period(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, part_id = part_ids
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await session.execute(
            update(GenerationLedger)
            .where(GenerationLedger.document_id == document_id)
            .values(period_start=date(2000, 1, 1))
        )
        await session.execute(
            update(DocumentPart).where(DocumentPart.id == part_id).values(quota_period_start=date(2000, 1, 1))
        )
    async with session_factory() as session, session.begin():
        await ledger.refund(session, part_id=part_id)
        await ledger.charge(session, part_id=part_id)
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == part_id))).all()
        assert {(e.op, e.period_start) for e in entries} == {
            (LedgerOp.REFUND.value, date(2000, 1, 1)),
            (LedgerOp.CHARGE.value, date(2000, 1, 1)),
        }
        assert (await ledger.available(session, user_id=user_id)).available == 20
