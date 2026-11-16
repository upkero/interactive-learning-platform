from dataclasses import dataclass, replace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_owner import PartOwner
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.core.clock import SystemClock
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeDocumentRepository
from tests.support.fakes.repositories.quota import FakeGenerationLedgerRepository
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.unit


@dataclass
class RecoveryFixture:
    part: PartRecord
    parts: FakeDocumentPartRepository
    documents: FakeDocumentRepository
    ledger: FakeGenerationLedgerRepository
    dispatcher: FakeTaskDispatcher
    recovery: PartRecovery
    quota: QuotaLedger


async def build_recovery(status: PartStatus, attempts: int) -> RecoveryFixture:
    session = FakeSession()
    parts, documents, entries, users = (
        FakeDocumentPartRepository(),
        FakeDocumentRepository(),
        FakeGenerationLedgerRepository(),
        FakeUserRepository(),
    )
    user = await users.create(email="recovery@example.com", password_hash="hash")
    document_id = uuid4()
    (part,) = await parts.add_many(
        document_id, [PartDraft(index=0, title="part", topic_ids=[], source_markdown="x", token_count=1)]
    )
    part = replace(part, status=status, attempts=attempts)
    parts.store_record(part)
    parts.owners[part.id] = PartOwner(user_id=user.id, document_id=document_id)
    quota = QuotaLedger(
        users_factory=lambda _: users,
        ledger_factory=lambda _: entries,
        parts_factory=lambda _: parts,
        clock=SystemClock(),
    )
    await quota.reserve(cast(AsyncSession, session), user_id=user.id, document_id=document_id, parts=1)
    dispatcher = FakeTaskDispatcher()
    recovery = PartRecovery(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: parts,
        documents=lambda _: documents,
        ledger=quota,
        dispatcher=dispatcher,
    )
    return RecoveryFixture(part, parts, documents, entries, dispatcher, recovery, quota)


async def test_first_attempt_is_requeued() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.QUEUED and part.attempts == 1
    assert case.dispatcher.calls == [("enqueue_part", (case.part.id, False))]


async def test_exhausted_attempt_is_failed_and_refunded_once() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    await case.recovery.retry_or_fail(case.part.id, reason="duplicate")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.FAILED
    assert [entry.op for entry in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.REFUND]
    assert case.documents.refreshed == [case.part.document_id]
    assert case.dispatcher.calls == []


async def test_published_part_is_ignored() -> None:
    case = await build_recovery(PartStatus.PUBLISHED, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.PUBLISHED
    assert len(case.ledger.entries) == 1 and case.dispatcher.calls == []
