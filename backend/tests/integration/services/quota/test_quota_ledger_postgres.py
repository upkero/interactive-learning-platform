"""Ledger transaction and period isolation on PostgreSQL."""

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.user import User

pytestmark = pytest.mark.integration


async def test_duplicate_refund_preserves_outer_transaction(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
    async with session_factory() as session, session.begin():
        await ledger.refund(session, part_id=part_id)
        await ledger.refund(session, part_id=part_id)
        await session.execute(update(User).where(User.id == user_id).values(display_name="transaction survives"))
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == part_id))).all()
        assert [(e.op, e.delta) for e in entries] == [("refund", 1)]
        assert await session.scalar(select(User.display_name).where(User.id == user_id)) == "transaction survives"
        assert (await ledger.available(session, user_id=user_id)).available == 20
    await container.close()


async def test_old_reservation_refunded_in_original_period(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await session.execute(
            update(GenerationLedger)
            .where(GenerationLedger.document_id == document_id)
            .values(period_start=date(2000, 1, 1))
        )
    async with session_factory() as session, session.begin():
        await ledger.refund(session, part_id=part_id)
        await ledger.charge(session, part_id=part_id)
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.part_id == part_id))).all()
        assert {(e.op, e.period_start) for e in entries} == {("refund", date(2000, 1, 1)), ("charge", date(2000, 1, 1))}
        assert (await ledger.available(session, user_id=user_id)).available == 20
    await container.close()
