"""Ledger transaction and period isolation on PostgreSQL."""

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.quota import LedgerOp
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.user import User
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository

pytestmark = pytest.mark.integration


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
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    try:
        async with session_factory() as session, session.begin():
            repo = GenerationLedgerRepository(session)
            for month in (10, 11):
                await repo.add(
                    user_id=user_id,
                    document_id=document_id,
                    op=LedgerOp.RESERVE,
                    delta=-1,
                    period_start=date(2026, month, 1),
                )
            await session.execute(
                update(DocumentPart).where(DocumentPart.id == part_id).values(quota_period_start=date(2026, 10, 1))
            )
        async with session_factory() as session, session.begin():
            await container.quota_ledger.refund(session, part_id=part_id)
            await container.quota_ledger.charge(session, part_id=part_id)
        async with session_factory() as session:
            repo = GenerationLedgerRepository(session)
            assert await repo.sum_delta(user_id, date(2026, 10, 1)) == 0
            assert await repo.sum_delta(user_id, date(2026, 11, 1)) == -1
            entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == part_id))).all()
            assert {entry.period_start for entry in entries} == {date(2026, 10, 1)}
    finally:
        await container.close()


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
