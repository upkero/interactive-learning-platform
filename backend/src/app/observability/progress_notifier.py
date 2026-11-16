"""Redis Streams implementation of the 1.7 progress event contract."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.app.core.settings.progress import ProgressSettings

logger = logging.getLogger(__name__)


class RedisProgressNotifier:
    """Publish JSON events with a bounded stream and renewable expiry."""

    def __init__(self, redis: Redis, settings: ProgressSettings) -> None:
        self._redis = redis
        self._settings = settings

    async def emit(
        self,
        document_id: UUID,
        event_type: str,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
    ) -> None:
        event: dict[str, str] = {"type": event_type, "message": message, "ts": datetime.now(UTC).isoformat()}
        if part_id is not None:
            event["part_id"] = str(part_id)
        if stage is not None:
            event["stage"] = stage
        key = f"progress:{document_id}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.xadd(
                    key,
                    {"data": json.dumps(event, ensure_ascii=False)},
                    maxlen=self._settings.stream_maxlen,
                    approximate=True,
                )
                pipe.expire(key, self._settings.stream_ttl_seconds)
                await pipe.execute()
        except RedisError:
            logger.warning("progress.publish_failed", exc_info=True)
