"""Temporary deterministic pipeline for the published-content contract."""

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import JsonValue
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.core.settings.progress import ProgressSettings
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, DocumentRepositoryProtocol
from src.app.services.quota.quota_ledger import QuotaLedger

logger = logging.getLogger(__name__)
FIXTURE = Path(__file__).resolve().parents[5] / "tests/support/fixtures/seed/published_part.json"


class StubPipeline:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        ledger: QuotaLedger,
        redis: Redis,
        progress_settings: ProgressSettings,
        delay: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._documents = documents
        self._ledger = ledger
        self._redis = redis
        self._settings = progress_settings
        self._delay = delay

    async def process(self, part_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            parts = self._parts(session)
            part = await parts.lock(part_id)
            if part is None or not await parts.transition(
                part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True
            ):
                logger.info("part.skip", extra={"part_id": str(part_id)})
                return
            document_id = part.document_id
        await self._progress(document_id, part_id, PartStatus.MAIN_PASS)
        current = PartStatus.MAIN_PASS
        for next_status in (PartStatus.RESOLVING, PartStatus.ASSEMBLING, PartStatus.PUBLISHED):
            await asyncio.sleep(self._delay)
            content = None
            if next_status is PartStatus.PUBLISHED:
                content = cast(dict[str, JsonValue], json.loads(FIXTURE.read_text(encoding="utf-8"))["content"])
            async with self._session_factory() as session, session.begin():
                transitioned = await self._parts(session).transition(
                    part_id, frozenset({current}), next_status, content=content
                )
                if not transitioned:
                    logger.info("part.skip", extra={"part_id": str(part_id)})
                    return
                if next_status is PartStatus.PUBLISHED:
                    await self._ledger.charge(session, part_id=part_id)
                    await self._documents(session).refresh_status(document_id)
            await self._progress(document_id, part_id, next_status)
            current = next_status

    async def _progress(self, document_id: UUID, part_id: UUID, status: PartStatus) -> None:
        key = f"progress:{document_id}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.xadd(
                    key,
                    {"event": "part_stage", "part_id": str(part_id), "status": status.value},
                    maxlen=self._settings.stream_maxlen,
                    approximate=True,
                )
                pipe.expire(key, self._settings.stream_ttl_seconds)
                await pipe.execute()
        except RedisError:
            logger.warning("progress.publish_failed", exc_info=True)
