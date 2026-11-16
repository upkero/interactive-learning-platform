"""Recover timed-out parts, with quota refund in the same transaction."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import PartStatus
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.quota.quota_ledger import QuotaLedger

ACTIVE = frozenset({PartStatus.MAIN_PASS, PartStatus.RESOLVING, PartStatus.ASSEMBLING})


class PartRecovery:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        ledger: QuotaLedger,
        dispatcher: TaskDispatcher,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._ledger = ledger
        self._dispatcher = dispatcher

    async def retry_or_fail_in(self, session: AsyncSession, part: PartRecord, *, reason: str) -> bool:
        if part.status not in ACTIVE:
            return False
        parts = self._parts(session)
        if part.attempts < 2:
            return await parts.transition(part.id, ACTIVE, PartStatus.QUEUED, error=reason)
        if await parts.transition(part.id, ACTIVE, PartStatus.FAILED, error=reason):
            await self._ledger.refund(session, part_id=part.id)
            await self._documents(session).refresh_status(part.document_id)
        return False

    async def retry_or_fail(self, part_id: UUID, *, reason: str) -> None:
        retry = False
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            if part is not None:
                retry = await self.retry_or_fail_in(session, part, reason=reason)
        if retry:
            await self._dispatcher.enqueue_part(part_id, high=False)

    async def fail(self, part_id: UUID, *, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            if part is not None and await self._parts(session).transition(
                part_id, ACTIVE, PartStatus.FAILED, error=reason
            ):
                await self._ledger.refund(session, part_id=part_id)
                await self._documents(session).refresh_status(part.document_id)
