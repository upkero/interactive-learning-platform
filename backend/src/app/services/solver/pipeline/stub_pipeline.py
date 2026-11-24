"""Temporary deterministic pipeline for the published-content contract."""

import asyncio
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import UUID

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import TERMINAL_DOCUMENT_STATUSES, PartStatus
from src.app.contracts.progress import ProgressEventType
from src.app.core.fixtures import PUBLISHED_PART_FIXTURE
from src.app.core.log_context import bind_log_context
from src.app.interfaces.notifications.service import DocumentNotifications
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.observability.decision_log import DecisionLog
from src.app.observability.noop_metrics_collector import NoopMetricsCollector
from src.app.observability.usage_tracker import UsageTracker, bind_usage_tracker
from src.app.services.progress.messages import render_message
from src.app.services.quota.quota_ledger import QuotaLedger

logger = logging.getLogger(__name__)

_CONTENT_ADAPTER = TypeAdapter(dict[str, JsonValue])


class StubPipeline:
    """Publish deterministic sample content while the real solver is unavailable."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        ledger: QuotaLedger,
        notifier: ProgressNotifier,
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        notifications: DocumentNotifications,
        metrics: MetricsCollector | None = None,
        delay: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._ledger = ledger
        self._notifier = notifier
        self._users = users
        self._notifications = notifications
        self._metrics = metrics
        self._content: dict[str, JsonValue] | None = None
        self._delay = delay

    async def process(self, part_id: UUID) -> None:
        started = perf_counter()
        accepted = False
        published = False
        try:
            async with self._session_factory() as session, session.begin():
                parts = self._parts(session)
                if not await parts.transition(
                    part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True
                ):
                    logger.info("part.skip", extra={"part_id": str(part_id)})
                    return
                accepted = True
                part = await parts.get(part_id)
                if part is None:
                    raise RuntimeError("Part disappeared after transition")
                document_id = part.document_id
                document = await self._documents(session).get(document_id)
                locale = await self._users(session).get_locale_by_document(document_id)
                start_index = document.generation_start_index if document is not None else 0
                part_name = str(part.index - start_index + 1)
            content = await self._load_content()
            tracker = UsageTracker(
                part_id=str(part_id), document_id=str(document_id), metrics=self._metrics, started=started
            )

            def record_published() -> None:
                nonlocal published
                published = True
                self._observe_part(perf_counter() - started, "published")
                DecisionLog(metrics=self._metrics or NoopMetricsCollector()).part_summary(tracker.summary())

            with bind_log_context(document_id=str(document_id), part_id=str(part_id)), bind_usage_tracker(tracker):
                await self._run_stages(document_id, part_id, content, locale, part_name, tracker, record_published)
        except BaseException:
            if accepted and not published:
                self._observe_part(perf_counter() - started, "failed")
            raise

    def _observe_part(self, duration: float, outcome: str) -> None:
        if self._metrics is not None:
            self._metrics.observe_histogram(
                "part.processing_duration_seconds",
                duration,
                labels={"outcome": outcome},
                buckets=(10, 30, 60, 120, 180, 240, 300, 330),
            )

    async def _load_content(self) -> dict[str, JsonValue]:
        """Read and validate the fixture once for this pipeline instance."""
        if self._content is not None:
            return self._content
        raw = await asyncio.to_thread(PUBLISHED_PART_FIXTURE.read_text, encoding="utf-8")
        try:
            fixture = json.loads(raw)
            content = _CONTENT_ADAPTER.validate_python(fixture["content"])
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise RuntimeError(f"Invalid published part fixture {PUBLISHED_PART_FIXTURE}: {exc}") from exc
        if (
            content.get("schema_version") != 1
            or not isinstance(content.get("title"), str)
            or not isinstance(content.get("markdown"), str)
            or not isinstance(content.get("widgets"), dict)
            or not isinstance(content.get("quizzes"), list)
            or not isinstance(content.get("answer_keys"), dict)
        ):
            raise RuntimeError(
                f"Invalid published part fixture {PUBLISHED_PART_FIXTURE}: "
                "expected schema_version=1, title, markdown, widgets, quizzes and answer_keys"
            )
        self._content = content
        return content

    async def _run_stages(
        self,
        document_id: UUID,
        part_id: UUID,
        content: dict[str, JsonValue],
        locale: str,
        part_name: str,
        tracker: UsageTracker,
        record_published: Callable[[], None],
    ) -> bool:
        async def emit(
            event_type: ProgressEventType,
            stage: str | None = None,
            *,
            outcome: str | None = None,
        ) -> None:
            await self._notifier.emit(
                document_id,
                event_type,
                part_id=part_id if event_type is not ProgressEventType.DOCUMENT_DONE else None,
                stage=stage,
                message=render_message(
                    locale,
                    event_type,
                    stage,
                    (
                        {"part": part_name}
                        if event_type is ProgressEventType.PART_STATUS
                        else {"outcome": outcome}
                        if outcome is not None
                        else {}
                    ),
                ),
            )

        await emit(ProgressEventType.PART_STATUS, PartStatus.MAIN_PASS.value)
        current = PartStatus.MAIN_PASS
        for next_status in (PartStatus.RESOLVING, PartStatus.ASSEMBLING, PartStatus.PUBLISHED):
            # Time spent in the current stage, before transitioning to the next status.
            with tracker.stage(current.value):
                await asyncio.sleep(self._delay)
            document_done = False
            document_status = None
            async with self._session_factory() as session, session.begin():
                transitioned = await self._parts(session).transition(
                    part_id,
                    frozenset({current}),
                    next_status,
                    content=content if next_status is PartStatus.PUBLISHED else None,
                )
                if not transitioned:
                    logger.info("part.skip", extra={"part_id": str(part_id)})
                    return False
                if next_status is PartStatus.PUBLISHED:
                    await self._ledger.charge(session, part_id=part_id)
                    documents = self._documents(session)
                    await documents.refresh_status(document_id)
                    document = await documents.get(document_id)
                    document_done = document is not None and document.status in TERMINAL_DOCUMENT_STATUSES
                    document_status = document.status if document is not None else None
                    current_parts = [
                        item
                        for item in await self._parts(session).list_by_document(document_id)
                        if document is None or item.index >= document.generation_start_index
                    ]
                    outcome = (
                        "failed" if not any(item.status is PartStatus.PUBLISHED for item in current_parts) else "ready"
                    )
                else:
                    outcome = None
            if next_status is PartStatus.PUBLISHED:
                record_published()
            await emit(ProgressEventType.PART_STATUS, next_status.value)
            if next_status is PartStatus.PUBLISHED:
                await emit(ProgressEventType.PART_READY)
                if document_done:
                    await emit(
                        ProgressEventType.DOCUMENT_DONE,
                        document_status.value if document_status else None,
                        outcome=outcome,
                    )
                    await self._notifications.on_document_finished(document_id)
            current = next_status
        return True
