"""Recover stale part attempts and lost queue messages."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import ACTIVE_PART_STATUSES, PartStatus
from src.app.exceptions.tasks import TaskDispatchError
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.observability.noop_metrics_collector import NoopMetricsCollector
from src.app.services.solver.pipeline.part_recovery import PartRecovery

logger = logging.getLogger(__name__)
BATCH_SIZE = 50


@dataclass(frozen=True, slots=True)
class WatchdogReport:
    requeued: int
    failed: int
    lost: int


class Watchdog:
    """Recover stale work in isolated savepoints and dispatch after commit."""

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
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._recovery = recovery
        self._dispatcher = dispatcher
        self._stuck_after = stuck_after
        self._lost_after = lost_after
        self._metrics = metrics or NoopMetricsCollector()

    async def tick(self) -> WatchdogReport:
        retry: list[UUID] = []
        lost_parts: list[UUID] = []
        lost_documents: list[UUID] = []
        failed = 0
        errors = 0
        async with self._session_factory() as session, session.begin():
            parts = self._parts(session)
            for part in await parts.lock_stale(
                statuses=ACTIVE_PART_STATUSES, older_than=self._stuck_after, limit=BATCH_SIZE
            ):
                try:
                    async with session.begin_nested():
                        requeued = await self._recovery.retry_or_fail_in(session, part, reason="watchdog")
                    if requeued:
                        retry.append(part.id)
                    else:
                        failed += 1
                except Exception:
                    errors += 1
                    logger.exception("watchdog.part_failed", extra={"part_id": str(part.id)})
            for part in await parts.lock_stale(
                statuses=frozenset({PartStatus.QUEUED}), older_than=self._lost_after, limit=BATCH_SIZE
            ):
                try:
                    async with session.begin_nested():
                        await parts.touch(part.id)
                    lost_parts.append(part.id)
                except Exception:
                    errors += 1
                    logger.exception("watchdog.part_failed", extra={"part_id": str(part.id)})
            documents = self._documents(session)
            for document in await documents.lock_stale_uploaded(older_than=self._lost_after, limit=BATCH_SIZE):
                try:
                    async with session.begin_nested():
                        await documents.touch(document.id)
                    lost_documents.append(document.id)
                except Exception:
                    errors += 1
                    logger.exception("watchdog.document_failed", extra={"document_id": str(document.id)})
        for part_id in [*retry, *lost_parts]:
            try:
                await self._dispatcher.enqueue_part(part_id, high=False)
            except TaskDispatchError:
                logger.exception("watchdog.enqueue_part_failed", extra={"part_id": str(part_id)})
        for document_id in lost_documents:
            try:
                await self._dispatcher.enqueue_parse(document_id)
            except TaskDispatchError:
                logger.exception("watchdog.enqueue_document_failed", extra={"document_id": str(document_id)})
        lost = len(lost_parts) + len(lost_documents)
        for action, count in (("requeued", len(retry)), ("failed", failed), ("lost", lost), ("error", errors)):
            if count:
                self._metrics.increment_counter("watchdog_actions_total", labels={"action": action}, by=count)
        return WatchdogReport(requeued=len(retry), failed=failed, lost=lost)
