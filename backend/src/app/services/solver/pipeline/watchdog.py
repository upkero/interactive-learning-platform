"""Recover stale part attempts and lost queue messages."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from prometheus_client import Counter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.solver.pipeline.part_recovery import ACTIVE, PartRecovery

logger = logging.getLogger(__name__)
WATCHDOG_ACTIONS = Counter("watchdog_actions_total", "Watchdog recovery actions", ["action"])


@dataclass(frozen=True, slots=True)
class WatchdogReport:
    requeued: int
    failed: int
    lost: int


class Watchdog:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        recovery: PartRecovery,
        dispatcher: TaskDispatcher,
        stuck_after: timedelta = timedelta(minutes=10),
        lost_after: timedelta = timedelta(minutes=30),
    ) -> None:
        self._sessions = session_factory
        self._parts = parts
        self._documents = documents
        self._recovery = recovery
        self._dispatcher = dispatcher
        self._stuck_after = stuck_after
        self._lost_after = lost_after

    async def tick(self) -> WatchdogReport:
        now = datetime.now(UTC)
        retry: list[UUID] = []
        lost_parts: list[UUID] = []
        lost_documents: list[UUID] = []
        failed = 0
        async with self._sessions() as session, session.begin():
            parts = self._parts(session)
            for part in await parts.lock_stale(statuses=ACTIVE, before=now - self._stuck_after, limit=50):
                if await self._recovery.retry_or_fail_in(session, part, reason="watchdog"):
                    retry.append(part.id)
                else:
                    failed += 1
            for part in await parts.lock_stale(
                statuses=frozenset({PartStatus.QUEUED}), before=now - self._lost_after, limit=50
            ):
                await parts.touch(part.id)
                lost_parts.append(part.id)
            documents = self._documents(session)
            for document in await documents.lock_stale_uploaded(before=now - self._lost_after, limit=50):
                await documents.touch(document.id)
                lost_documents.append(document.id)
        for part_id in [*retry, *lost_parts]:
            try:
                await self._dispatcher.enqueue_part(part_id, high=False)
            except Exception:
                logger.exception("watchdog.enqueue_part_failed", extra={"part_id": str(part_id)})
        for document_id in lost_documents:
            try:
                await self._dispatcher.enqueue_parse(document_id)
            except Exception:
                logger.exception("watchdog.enqueue_document_failed", extra={"document_id": str(document_id)})
        lost = len(lost_parts) + len(lost_documents)
        for action, count in (("requeued", len(retry)), ("failed", failed), ("lost", lost)):
            if count:
                WATCHDOG_ACTIONS.labels(action=action).inc(count)
        return WatchdogReport(requeued=len(retry), failed=failed, lost=lost)
