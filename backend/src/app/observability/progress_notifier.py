"""Redis Streams implementation of the 1.7 progress event contract."""

import json
import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.app.contracts.progress import ProgressEvent, ProgressEventType
from src.app.contracts.progress.stream import stream_key
from src.app.core.settings.progress import ProgressSettings

logger = logging.getLogger(__name__)


class RedisProgressNotifier:
    """Publish JSON events with a bounded stream and renewable expiry."""

    def __init__(self, redis: Redis, settings: ProgressSettings) -> None:
        self._redis = redis
        self._settings = settings

    async def publish(self, event: ProgressEvent) -> str | None:
        key = stream_key(event.document_id)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.xadd(
                    key,
                    {"data": json.dumps(event.to_payload(), ensure_ascii=False)},
                    maxlen=self._settings.stream_maxlen,
                    approximate=True,
                )
                pipe.expire(key, self._settings.stream_ttl_seconds)
                entry_id, _ = await pipe.execute()
        except RedisError:
            logger.warning(
                "Progress event was not published.", extra={"event_type": event.event_type.value}, exc_info=True
            )
            return None
        return str(entry_id)

    async def emit(
        self,
        document_id: UUID,
        event_type: ProgressEventType,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
    ) -> str | None:
        return await self.publish(
            ProgressEvent(
                document_id=document_id,
                event_type=event_type,
                part_id=part_id,
                stage=stage,
                message=message,
            )
        )
