"""Real PostgreSQL row locks serialize quota reservations and refunds."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.exceptions.quota import QuotaExceededError
from src.app.models.generation_ledger import GenerationLedger

pytestmark = pytest.mark.integration


async def test_parallel_reserves_never_overspend(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, _ = part_ids
    container = ApplicationContainer()
    ledger = container.quota_ledger

    async def reserve() -> bool:
        try:
            async with session_factory() as session, session.begin():
                await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=5)
            return True
        except QuotaExceededError:
            return False

    results = await asyncio.gather(*(reserve() for _ in range(6)))
    assert sum(results) == 4
    async with session_factory() as session:
        assert (await ledger.available(session, user_id=user_id)).available == 0
        assert await session.scalar(select(func.count()).select_from(GenerationLedger)) == 4
    await container.close()


async def test_parallel_refunds_are_recorded_once(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)

    async def refund() -> None:
        async with session_factory() as session, session.begin():
            await ledger.refund(session, part_id=part_id)

    await asyncio.gather(refund(), refund())
    async with session_factory() as session:
        assert (await ledger.available(session, user_id=user_id)).available == 20
        assert (
            await session.scalar(
                select(func.count()).select_from(GenerationLedger).where(GenerationLedger.op == "refund")
            )
            == 1
        )
    await container.close()


async def test_reserve_racing_refund_never_overspends(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=20)

    async def refund() -> None:
        async with session_factory() as session, session.begin():
            await ledger.refund(session, part_id=part_id)

    async def reserve() -> bool:
        try:
            async with session_factory() as session, session.begin():
                await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
            return True
        except QuotaExceededError:
            return False

    _, reserved = await asyncio.gather(refund(), reserve())
    async with session_factory() as session:
        assert (await ledger.available(session, user_id=user_id)).available == (0 if reserved else 1)
    await container.close()
