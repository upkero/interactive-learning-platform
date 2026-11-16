"""Recover timed-out parts, with quota refund in the same transaction."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import (
    ACTIVE_PART_STATUSES,
    DocumentStatus,
    PartStatus,
)
from src.app.contracts.progress import ProgressEventType
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.quota.quota_ledger import QuotaLedger

TERMINAL_DOCUMENT_STATUSES = frozenset({DocumentStatus.DONE, DocumentStatus.FAILED})


@dataclass(frozen=True, slots=True)
class _PendingEvent:
    """A progress event created inside a transaction and published after commit."""

    document_id: UUID
    event_type: ProgressEventType
    part_id: UUID | None = None
    stage: PartStatus | None = None


class PartRecovery:
    """Retry a stale attempt once or fail it and refund within the transaction."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        ledger: QuotaLedger,
        dispatcher: TaskDispatcher,
        notifier: ProgressNotifier,
        max_attempts: int = 2,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._ledger = ledger
        self._dispatcher = dispatcher
        self._notifier = notifier
        self._max_attempts = max_attempts
        self._pending_events: list[_PendingEvent] = []

    async def retry_or_fail_in(self, session: AsyncSession, part: PartRecord, *, reason: str) -> bool:
        """Move a part inside the caller's transaction; events wait for its commit."""
        if part.status not in ACTIVE_PART_STATUSES:
            return False
        parts = self._parts(session)
        if part.attempts < self._max_attempts:
            transitioned = await parts.transition(part.id, ACTIVE_PART_STATUSES, PartStatus.QUEUED, error=reason)
            if transitioned:
                self._queue_event(part, PartStatus.QUEUED)
            return transitioned
        if await parts.transition(part.id, ACTIVE_PART_STATUSES, PartStatus.FAILED, error=reason):
            await self._ledger.refund(session, part_id=part.id)
            documents = self._documents(session)
            await documents.refresh_status(part.document_id)
            document = await documents.get(part.document_id)
            document_done = document is not None and document.status in TERMINAL_DOCUMENT_STATUSES
            self._queue_event(part, PartStatus.FAILED)
            if document_done:
                self._pending_events.append(_PendingEvent(part.document_id, ProgressEventType.DOCUMENT_DONE))
        return False

    async def retry_or_fail(self, part_id: UUID, *, reason: str) -> None:
        retry = False
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            if part is not None:
                retry = await self.retry_or_fail_in(session, part, reason=reason)
        await self.publish_pending()
        if retry:
            await self._dispatcher.enqueue_part(part_id, high=False)

    async def fail(self, part_id: UUID, *, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            if part is not None and await self._parts(session).transition(
                part_id, ACTIVE_PART_STATUSES, PartStatus.FAILED, error=reason
            ):
                await self._ledger.refund(session, part_id=part_id)
                documents = self._documents(session)
                await documents.refresh_status(part.document_id)
                document = await documents.get(part.document_id)
                document_done = document is not None and document.status in TERMINAL_DOCUMENT_STATUSES
                self._queue_event(part, PartStatus.FAILED)
                if document_done:
                    self._pending_events.append(_PendingEvent(part.document_id, ProgressEventType.DOCUMENT_DONE))
        await self.publish_pending()

    async def publish_pending(self) -> None:
        """Publish buffered events after the caller's transaction has committed."""
        events, self._pending_events = self._pending_events, []
        for event in events:
            await self._notifier.emit(
                event.document_id,
                event.event_type,
                part_id=event.part_id,
                stage=event.stage.value if event.stage is not None else None,
            )

    def _queue_event(self, part: PartRecord, stage: PartStatus) -> None:
        self._pending_events.append(
            _PendingEvent(part.document_id, ProgressEventType.PART_STATUS, part_id=part.id, stage=stage)
        )
