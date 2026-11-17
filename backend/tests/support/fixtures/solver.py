"""Builders for solver pipeline and recovery tests."""

from dataclasses import dataclass, replace
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_owner import PartOwner
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus, SourceType
from src.app.core.clock import SystemClock
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeDocumentRepository
from tests.support.fakes.repositories.quota import FakeGenerationLedgerRepository
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher


@dataclass
class RecoveryFixture:
    part: PartRecord
    parts: FakeDocumentPartRepository
    documents: FakeDocumentRepository
    ledger: FakeGenerationLedgerRepository
    dispatcher: FakeTaskDispatcher
    recovery: PartRecovery
    quota: QuotaLedger
    notifier: FakeProgressNotifier
    document: DocumentRecord
    session: FakeSession


async def build_recovery(status: PartStatus, attempts: int) -> RecoveryFixture:
    session = FakeSession()
    parts = FakeDocumentPartRepository()
    documents = FakeDocumentRepository()
    documents.attach_parts(parts)
    entries = FakeGenerationLedgerRepository()
    users = FakeUserRepository()
    notifier = FakeProgressNotifier(committed=lambda: session.committed)
    user = await users.create(email="recovery@example.com", password_hash="hash")
    document = await documents.create(
        owner_id=user.id,
        title="recovery document",
        source_type=SourceType.UPLOAD,
        object_key="documents/recovery.md",
        mime_type="text/markdown",
        size_bytes=1,
        checksum="c" * 64,
    )
    updated = await documents.set_status(document.id, DocumentStatus.GENERATING)
    assert updated is not None
    document = updated
    (part,) = await parts.add_many(
        document.id, [PartDraft(index=0, title="part", topic_ids=[], source_markdown="x", token_count=1)]
    )
    part = replace(part, status=status, attempts=attempts)
    parts.store_record(part)
    parts.owners[part.id] = PartOwner(user_id=user.id, document_id=document.id)
    quota = QuotaLedger(
        users_factory=lambda _: users,
        ledger_factory=lambda _: entries,
        parts_factory=lambda _: parts,
        clock=SystemClock(),
    )
    await quota.reserve(cast(AsyncSession, session), user_id=user.id, document_id=document.id, parts=1)
    dispatcher = FakeTaskDispatcher()
    recovery = PartRecovery(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: parts,
        documents=lambda _: documents,
        ledger=quota,
        dispatcher=dispatcher,
        notifier=notifier,
    )
    return RecoveryFixture(
        part=part,
        parts=parts,
        documents=documents,
        ledger=entries,
        dispatcher=dispatcher,
        recovery=recovery,
        quota=quota,
        notifier=notifier,
        document=document,
        session=session,
    )
