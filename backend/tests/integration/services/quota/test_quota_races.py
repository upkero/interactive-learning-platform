"""Real PostgreSQL row locks serialize quota reservations and refunds."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents import PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.exceptions.quota import QuotaExceededError
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.integration


async def test_parallel_reserves_never_overspend(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, _ = part_ids
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


async def test_worker_and_watchdog_refund_only_once(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, part_id = part_ids
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        parts = DocumentPartRepository(session)
        await parts.transition(part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await parts.transition(part_id, frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await parts.transition(part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
    recovery = PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        dispatcher=FakeTaskDispatcher(),
        notifier=FakeProgressNotifier(),
    )
    await asyncio.gather(recovery.fail(part_id, reason="worker"), recovery.retry_or_fail(part_id, reason="watchdog"))
    async with session_factory() as session:
        assert (await container.quota_ledger.available(session, user_id=user_id)).available == 20
        assert (
            await session.scalar(
                select(func.count()).select_from(GenerationLedger).where(GenerationLedger.op == LedgerOp.REFUND.value)
            )
            == 1
        )


async def test_parallel_refunds_are_recorded_once(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, part_id = part_ids
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
                select(func.count()).select_from(GenerationLedger).where(GenerationLedger.op == LedgerOp.REFUND.value)
            )
            == 1
        )


async def test_reserve_racing_refund_never_overspends(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    user_id, document_id, part_id = part_ids
    ledger = container.quota_ledger
    async with session_factory() as session, session.begin():
        await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=20)

    async def reserve() -> None:
        async with session_factory() as session, session.begin():
            await ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)

    async with session_factory() as session:
        async with session.begin():
            await ledger.refund(session, part_id=part_id)
            task = asyncio.create_task(reserve())
            try:
                await asyncio.sleep(0.3)
                assert not task.done()
            except BaseException:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
        await task
    async with session_factory() as session:
        assert (await ledger.available(session, user_id=user_id)).available == 0
