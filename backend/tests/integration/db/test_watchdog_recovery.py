import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.core.settings.progress import ProgressSettings
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.integration


async def test_concurrent_watchdog_ticks_refund_only_once(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, first_id = part_ids
    container = ApplicationContainer()
    dispatcher = FakeTaskDispatcher()
    async with session_factory() as session, session.begin():
        parts = DocumentPartRepository(session)
        (second,) = await parts.add_many(
            document_id, [PartDraft(index=1, title="second", topic_ids=[], source_markdown="x", token_count=1)]
        )
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=2)
        await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
        for part_id in (first_id, second.id):
            await parts.transition(part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await parts.transition(second.id, frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await parts.transition(second.id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.document_id == document_id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    recovery = PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        dispatcher=dispatcher,
    )
    watchdog = Watchdog(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        recovery=recovery,
        dispatcher=dispatcher,
    )
    reports = await asyncio.gather(watchdog.tick(), watchdog.tick())
    assert sum(r.requeued for r in reports) == 1
    assert sum(r.failed for r in reports) == 1
    assert dispatcher.calls == [("enqueue_part", (first_id, False))]
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.op == "refund"))).all()
        assert len(entries) == 1 and entries[0].part_id == second.id and entries[0].delta == 1
        first = await DocumentPartRepository(session).get(first_id)
        assert first is not None and first.status is PartStatus.QUEUED and first.attempts == 1
    await container.close()


async def test_stub_pipeline_publishes_and_charges_once(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
    pipeline = StubPipeline(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        redis=cast(Redis, object()),
        progress_settings=ProgressSettings(),
        delay=0,
    )
    pipeline._progress = AsyncMock()  # type: ignore[method-assign]
    await asyncio.gather(pipeline.process(part_id), pipeline.process(part_id))
    async with session_factory() as session:
        part = await DocumentPartRepository(session).get(part_id)
        assert part is not None and part.status is PartStatus.PUBLISHED and part.attempts == 1 and part.content
        doc = await DocumentRepository(session).get(document_id)
        assert doc is not None and doc.status is DocumentStatus.DONE
        entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.op == "charge"))).all()
        assert len(entries) == 1 and entries[0].part_id == part_id
    await container.close()
