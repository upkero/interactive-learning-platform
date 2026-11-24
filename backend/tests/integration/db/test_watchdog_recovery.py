import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.core.clock import SystemClock
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.quota.period import current_period
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
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
            document_id,
            [
                PartDraft(
                    index=1,
                    title="second",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=current_period(SystemClock().today(), None).start,
                )
            ],
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
    notifier = FakeProgressNotifier()
    recovery = PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        dispatcher=dispatcher,
        notifier=notifier,
        users=UserRepository,
        notifications=container.notification_service,
    )
    watchdog = Watchdog(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        recovery=recovery,
        dispatcher=dispatcher,
        metrics=RecordingMetricsCollector(),
    )
    reports = await asyncio.gather(watchdog.tick(), watchdog.tick())
    assert sum(r.requeued for r in reports) == 1
    assert sum(r.failed for r in reports) == 1
    assert dispatcher.calls == [("enqueue_part", (first_id, False))]
    assert len(notifier.events) == 2
    assert sorted((event[1], event[3]) for event in notifier.events) == [
        ("part_status", "failed"),
        ("part_status", "queued"),
    ]
    async with session_factory() as session:
        entries = (
            await session.scalars(select(GenerationLedger).where(GenerationLedger.op == LedgerOp.REFUND.value))
        ).all()
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
    notifier = FakeProgressNotifier()
    pipeline = StubPipeline(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        notifier=notifier,
        users=UserRepository,
        notifications=container.notification_service,
        delay=0,
    )
    await asyncio.gather(pipeline.process(part_id), pipeline.process(part_id))
    async with session_factory() as session:
        part = await DocumentPartRepository(session).get(part_id)
        assert part is not None and part.status is PartStatus.PUBLISHED and part.attempts == 1 and part.content
        doc = await DocumentRepository(session).get(document_id)
        assert doc is not None and doc.status is DocumentStatus.DONE
        entries = (
            await session.scalars(select(GenerationLedger).where(GenerationLedger.op == LedgerOp.CHARGE.value))
        ).all()
        assert len(entries) == 1 and entries[0].part_id == part_id
    assert [event[1] for event in notifier.events] == ["part_status"] * 4 + ["part_ready", "document_done"]
    await container.close()


async def test_poison_part_does_not_block_other_parts(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    _, document_id, first_id = part_ids
    container = ApplicationContainer()
    dispatcher = FakeTaskDispatcher()
    metrics = RecordingMetricsCollector()
    async with session_factory() as session, session.begin():
        parts = DocumentPartRepository(session)
        (poison,) = await parts.add_many(
            document_id,
            [
                PartDraft(
                    index=1, title="poison", topic_ids=[], source_markdown="x", token_count=1, quota_period_start=None
                )
            ],
        )
        for part_id in (first_id, poison.id):
            await parts.transition(part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await parts.transition(poison.id, frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await parts.transition(poison.id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
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
        notifier=FakeProgressNotifier(),
        users=UserRepository,
        notifications=container.notification_service,
    )
    watchdog = Watchdog(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        recovery=recovery,
        dispatcher=dispatcher,
        metrics=metrics,
    )
    report = await watchdog.tick()
    assert report.requeued == 1 and report.failed == 0
    assert dispatcher.calls == [("enqueue_part", (first_id, False))]
    assert ("watchdog_actions_total", {"action": "error"}, 1) in metrics.labeled_counters
    async with session_factory() as session:
        healthy = await DocumentPartRepository(session).get(first_id)
        bad = await DocumentPartRepository(session).get(poison.id)
        assert healthy is not None and healthy.status is PartStatus.QUEUED
        assert bad is not None and bad.status is PartStatus.MAIN_PASS
    await container.close()


async def test_lost_queue_threshold_and_failed_document(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, first_id = part_ids
    container = ApplicationContainer()
    dispatcher = FakeTaskDispatcher()
    notifier = FakeProgressNotifier()
    recovery = PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        dispatcher=dispatcher,
        notifier=notifier,
        users=UserRepository,
        notifications=container.notification_service,
    )
    watchdog = Watchdog(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        recovery=recovery,
        dispatcher=dispatcher,
        metrics=RecordingMetricsCollector(),
    )
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == first_id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    assert (await watchdog.tick()).lost == 0
    async with session_factory() as session, session.begin():
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == first_id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=31))
        )
    assert (await watchdog.tick()).lost == 1
    async with session_factory() as session, session.begin():
        parts = DocumentPartRepository(session)
        part = await parts.get(first_id)
        assert part is not None and part.attempts == 0
        await parts.transition(first_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await parts.transition(first_id, frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await parts.transition(first_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == first_id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    assert (await watchdog.tick()).failed == 1
    assert [(e[1], e[3]) for e in notifier.events] == [("part_status", "failed"), ("document_done", "failed")]
    async with session_factory() as session:
        document = await DocumentRepository(session).get(document_id)
        assert document is not None and document.status is DocumentStatus.FAILED
    await container.close()


async def test_uploaded_lock_touch_and_quota_lookup(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(updated_at=datetime.now(UTC) - timedelta(minutes=31))
        )
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        locked = await documents.lock_stale_uploaded(older_than=timedelta(minutes=30), limit=50)
        assert [d.id for d in locked] == [document_id]
        owner = await DocumentPartRepository(session).part_owner(part_id)
        assert owner is not None and (owner.user_id, owner.document_id) == (user_id, document_id)
        assert owner.quota_period_start is not None
        await documents.touch(document_id)
    async with session_factory() as session, session.begin():
        assert await DocumentRepository(session).lock_stale_uploaded(older_than=timedelta(minutes=30), limit=50) == []
    await container.close()
