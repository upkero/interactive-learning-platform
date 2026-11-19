"""Redis Stream reader used by the document progress SSE endpoint."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from src.app.contracts.progress import ProgressEventType
from src.app.observability.progress_notifier import RedisProgressNotifier


@dataclass(frozen=True, slots=True)
class StreamEntry:
    id: str
    type: str
    data: str

    @classmethod
    def from_redis(cls, entry_id: str | bytes, fields: dict[str | bytes, str | bytes]) -> "StreamEntry":
        raw = fields.get("data", fields.get(b"data", "{}"))
        data = raw.decode() if isinstance(raw, bytes) else raw
        payload = json.loads(data)
        value = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
        return cls(id=value, type=str(payload.get("type", "error")), data=data)

    @classmethod
    def synthetic_done(cls, document_id: UUID, status: str) -> "StreamEntry":
        data = json.dumps({
            "type": ProgressEventType.DOCUMENT_DONE.value,
            "stage": status,
            "message": "Материал готов" if status == "done" else "Обработка завершилась с ошибкой",  # noqa: RUF001
        }, ensure_ascii=False)
        return cls(id="synthetic-0", type=ProgressEventType.DOCUMENT_DONE.value, data=data)


class ProgressReader:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def follow(self, document_id: UUID, cursor: str, *, finished_status: str) -> AsyncIterator[StreamEntry]:
        key = RedisProgressNotifier.stream_key(document_id)
        if finished_status in ("done", "failed") and not await self._redis.exists(key):
            yield StreamEntry.synthetic_done(document_id, finished_status)
            return
        while True:
            response = await self._redis.xread({key: cursor}, block=15_000, count=100)
            for _key, entries in response or ():
                for entry_id, fields in entries:
                    entry = StreamEntry.from_redis(entry_id, fields)
                    cursor = entry.id
                    yield entry
