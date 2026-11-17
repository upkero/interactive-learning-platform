"""Recover timed-out parts, with quota refund in the same transaction."""

from collections.abc import Callable, Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.recovery_outcome import RecoveryOutcome
from src.app.contracts.documents.statuses import (
    ACTIVE_PART_STATUSES,
    TERMINAL_DOCUMENT_STATUSES,
    PartStatus,
)
from src.app.contracts.progress import ProgressEvent, ProgressEventType
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.quota.quota_ledger import QuotaLedger


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

    async def retry_or_fail_in(self, session: AsyncSession, part: PartRecord, *, reason: str) -> RecoveryOutcome:
        """Move a part inside the caller's transaction and return its events.

        The caller publishes them only after committing, so a concurrent
        recovery cannot leak events from an uncommitted transaction.
        """
        if part.status not in ACTIVE_PART_STATUSES:
            return RecoveryOutcome()
        parts = self._parts(session)
        if part.attempts < self._max_attempts:
            transitioned = await parts.transition(part.id, ACTIVE_PART_STATUSES, PartStatus.QUEUED, error=reason)
            events = (self._part_status_event(part, PartStatus.QUEUED),) if transitioned else ()
            return RecoveryOutcome(requeued=transitioned, events=events)
        return await self._fail_in(session, part, reason=reason)

    async def retry_or_fail(self, part_id: UUID, *, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            outcome = (
                await self.retry_or_fail_in(session, part, reason=reason) if part is not None else RecoveryOutcome()
            )
        await self.publish(outcome.events)
        if outcome.requeued:
            await self._dispatcher.enqueue_part(part_id, high=False)

    async def fail(self, part_id: UUID, *, reason: str) -> None:
        outcome = RecoveryOutcome()
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).lock(part_id)
            if part is not None:
                outcome = await self._fail_in(session, part, reason=reason)
        await self.publish(outcome.events)

    async def publish(self, events: Iterable[ProgressEvent]) -> None:
        """Publish events after the caller's transaction has committed."""
        for event in events:
            await self._notifier.emit(
                event.document_id,
                event.event_type,
                part_id=event.part_id,
                stage=event.stage,
                message=event.message,
            )

    async def _fail_in(self, session: AsyncSession, part: PartRecord, *, reason: str) -> RecoveryOutcome:
        """Fail and refund once, returning the events for the caller to publish."""
        if not await self._parts(session).transition(part.id, ACTIVE_PART_STATUSES, PartStatus.FAILED, error=reason):
            return RecoveryOutcome()
        await self._ledger.refund(session, part_id=part.id)
        documents = self._documents(session)
        await documents.refresh_status(part.document_id)
        document = await documents.get(part.document_id)
        events = [self._part_status_event(part, PartStatus.FAILED)]
        if document is not None and document.status in TERMINAL_DOCUMENT_STATUSES:
            events.append(ProgressEvent(part.document_id, ProgressEventType.DOCUMENT_DONE))
        return RecoveryOutcome(failed=True, events=tuple(events))

    @staticmethod
    def _part_status_event(part: PartRecord, stage: PartStatus) -> ProgressEvent:
        return ProgressEvent(
            part.document_id,
            ProgressEventType.PART_STATUS,
            part_id=part.id,
            stage=stage.value,
        )
