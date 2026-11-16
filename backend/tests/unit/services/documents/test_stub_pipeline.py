from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import PartStatus
from src.app.core.settings.progress import ProgressSettings
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeDocumentRepository
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_stub_publishes_once_and_duplicate_delivery_is_noop() -> None:
    parts = FakeDocumentPartRepository()
    documents = FakeDocumentRepository()
    part = (
        await parts.add_many(
            uuid4(), [PartDraft(index=0, title="test", topic_ids=[], source_markdown="text", token_count=1)]
        )
    )[0]
    session = FakeSession()
    ledger = AsyncMock(spec=QuotaLedger)
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: parts,
        documents=lambda _: documents,
        ledger=ledger,
        redis=cast(Redis, object()),
        progress_settings=ProgressSettings(),
        delay=0,
    )
    pipeline._progress = AsyncMock()  # type: ignore[method-assign]
    await pipeline.process(part.id)
    await pipeline.process(part.id)
    result = await parts.get(part.id)
    assert result is not None and result.status is PartStatus.PUBLISHED
    assert result.attempts == 1 and result.content is not None
    assert result.content["schema_version"] == 1
    ledger.charge.assert_awaited_once()
    assert pipeline._progress.await_count == 4


@pytest.mark.asyncio
async def test_recovery_retries_once_then_refunds_and_ignores_terminal() -> None:
    parts = FakeDocumentPartRepository()
    documents = FakeDocumentRepository()
    part = (
        await parts.add_many(
            uuid4(), [PartDraft(index=0, title="test", topic_ids=[], source_markdown="text", token_count=1)]
        )
    )[0]
    session = FakeSession()
    ledger = AsyncMock(spec=QuotaLedger)
    dispatcher = FakeTaskDispatcher()
    recovery = PartRecovery(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: parts,
        documents=lambda _: documents,
        ledger=ledger,
        dispatcher=dispatcher,
    )
    assert await parts.transition(part.id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
    await recovery.retry_or_fail(part.id, reason="soft_time_limit")
    result = await parts.get(part.id)
    assert result is not None and result.status is PartStatus.QUEUED and result.attempts == 1
    assert session.committed == 1 and dispatcher.calls == [("enqueue_part", (part.id, False))]
    assert await parts.transition(part.id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
    await recovery.retry_or_fail(part.id, reason="soft_time_limit")
    await recovery.retry_or_fail(part.id, reason="duplicate")
    result = await parts.get(part.id)
    assert result is not None and result.status is PartStatus.FAILED and result.attempts == 2
    ledger.refund.assert_awaited_once()
    assert len(dispatcher.calls) == 1
