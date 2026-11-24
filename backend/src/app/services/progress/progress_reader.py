"""Read Redis Streams without blocking a terminal document forever."""

from collections.abc import AsyncGenerator
from uuid import UUID

from redis.asyncio import Redis

from src.app.contracts.documents.readable_document import RunOutcome
from src.app.contracts.documents.statuses import TERMINAL_DOCUMENT_STATUSES, DocumentStatus
from src.app.contracts.progress import ProgressEvent, ProgressEventType
from src.app.contracts.progress.stream import stream_key
from src.app.contracts.progress.stream_entry import StreamEntry
from src.app.services.progress.messages import render_message


class ProgressReader:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def follow(
        self,
        document_id: UUID,
        cursor: str,
        *,
        finished_status: DocumentStatus,
        run_outcome: RunOutcome,
        locale: str = "ru",
    ) -> AsyncGenerator[StreamEntry, None]:
        key = stream_key(document_id)
        terminal = finished_status in TERMINAL_DOCUMENT_STATUSES
        while True:
            # A finished document can have a live stream with a missing final event.
            # Drain its remaining history immediately and then close.
            response = await self._redis.xread({key: cursor}, block=None if terminal else 15_000, count=100)
            entries = [
                StreamEntry.from_redis(entry_id, fields) for _, batch in response or () for entry_id, fields in batch
            ]
            for entry in entries:
                cursor = entry.id
                yield entry
                if entry.type == ProgressEventType.DOCUMENT_DONE.value:
                    return
            if terminal and len(entries) < 100:
                event = ProgressEvent(
                    document_id,
                    ProgressEventType.DOCUMENT_DONE,
                    stage=finished_status.value,
                    message=render_message(
                        locale, ProgressEventType.DOCUMENT_DONE, finished_status.value, {"outcome": run_outcome}
                    ),
                )
                yield StreamEntry(id=cursor, type=event.event_type.value, data=event.to_json())
                return
