"""Temporary deterministic pipeline for the published-content contract."""

import asyncio
import json
import logging
from collections.abc import Callable
from uuid import UUID

from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import TERMINAL_DOCUMENT_STATUSES, PartStatus
from src.app.contracts.progress import ProgressEventType
from src.app.core.fixtures import PUBLISHED_PART_FIXTURE
from src.app.core.log_context import bind_log_context
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.interfaces.services.progress_notifier import ProgressNotifier
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
        delay: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._ledger = ledger
        self._notifier = notifier
        self._content: dict[str, JsonValue] | None = None
        self._delay = delay

    async def process(self, part_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            parts = self._parts(session)
            if not await parts.transition(
                part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True
            ):
                logger.info("part.skip", extra={"part_id": str(part_id)})
                return
            part = await parts.get(part_id)
            if part is None:
                raise RuntimeError("Part disappeared after transition")
            document_id = part.document_id
        content = await self._load_content()
        with bind_log_context(document_id=str(document_id)):
            await self._run_stages(document_id, part_id, content)

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

    async def _run_stages(self, document_id: UUID, part_id: UUID, content: dict[str, JsonValue]) -> None:
        await self._notifier.emit(
            document_id, ProgressEventType.PART_STATUS, part_id=part_id, stage=PartStatus.MAIN_PASS.value
        )
        current = PartStatus.MAIN_PASS
        for next_status in (PartStatus.RESOLVING, PartStatus.ASSEMBLING, PartStatus.PUBLISHED):
            await asyncio.sleep(self._delay)
            document_done = False
            async with self._session_factory() as session, session.begin():
                transitioned = await self._parts(session).transition(
                    part_id,
                    frozenset({current}),
                    next_status,
                    content=content if next_status is PartStatus.PUBLISHED else None,
                )
                if not transitioned:
                    logger.info("part.skip", extra={"part_id": str(part_id)})
                    return
                if next_status is PartStatus.PUBLISHED:
                    await self._ledger.charge(session, part_id=part_id)
                    documents = self._documents(session)
                    await documents.refresh_status(document_id)
                    document = await documents.get(document_id)
                    document_done = document is not None and document.status in TERMINAL_DOCUMENT_STATUSES
            await self._notifier.emit(
                document_id, ProgressEventType.PART_STATUS, part_id=part_id, stage=next_status.value
            )
            if next_status is PartStatus.PUBLISHED:
                await self._notifier.emit(document_id, ProgressEventType.PART_READY, part_id=part_id)
                if document_done:
                    await self._notifier.emit(document_id, ProgressEventType.DOCUMENT_DONE)
            current = next_status
