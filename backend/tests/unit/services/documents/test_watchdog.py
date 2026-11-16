from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import PartStatus, SourceType
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeDocumentRepository
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.unit


async def test_watchdog_retries_fails_and_recovers_lost_messages() -> None:
    parts, documents, session = FakeDocumentPartRepository(), FakeDocumentRepository(), FakeSession()
    dispatcher = FakeTaskDispatcher()
    ledger = AsyncMock(spec=QuotaLedger)
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    recovery = PartRecovery(
        session_factory=factory,
        parts=lambda _: parts,
        documents=lambda _: documents,
        ledger=ledger,
        dispatcher=dispatcher,
    )
    watchdog = Watchdog(
        session_factory=factory,
        parts=lambda _: parts,
        documents=lambda _: documents,
        recovery=recovery,
        dispatcher=dispatcher,
    )
    drafts = [PartDraft(index=i, title="test", topic_ids=[], source_markdown="x", token_count=1) for i in range(4)]
    records = await parts.add_many(uuid4(), drafts)
    stale = datetime.now(UTC) - timedelta(minutes=31)
    for index, (status, attempts) in enumerate(
        ((PartStatus.MAIN_PASS, 1), (PartStatus.ASSEMBLING, 2), (PartStatus.QUEUED, 0), (PartStatus.PUBLISHED, 1))
    ):
        parts._parts[records[index].id] = replace(
            records[index], status=status, attempts=attempts, stage_changed_at=stale
        )
    doc = await documents.create(
        owner_id=uuid4(),
        title="lost",
        source_type=SourceType.UPLOAD,
        object_key="x",
        mime_type="text/plain",
        size_bytes=1,
        checksum="x",
    )
    documents._documents[doc.id] = replace(doc, updated_at=stale)
    report = await watchdog.tick()
    assert (report.requeued, report.failed, report.lost) == (1, 1, 2)
    assert (await parts.get(records[0].id)).status is PartStatus.QUEUED  # type: ignore[union-attr]
    assert (await parts.get(records[1].id)).status is PartStatus.FAILED  # type: ignore[union-attr]
    assert (await parts.get(records[2].id)).attempts == 0  # type: ignore[union-attr]
    assert (await parts.get(records[3].id)).status is PartStatus.PUBLISHED  # type: ignore[union-attr]
    assert dispatcher.calls == [
        ("enqueue_part", (records[0].id, False)),
        ("enqueue_part", (records[2].id, False)),
        ("enqueue_parse", (doc.id,)),
    ]
    assert session.committed == 1
    ledger.refund.assert_awaited_once()
    assert (await watchdog.tick()).lost == 0
