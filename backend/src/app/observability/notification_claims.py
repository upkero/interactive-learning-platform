"""Redis-backed notification claim store."""

from collections.abc import Awaitable
from typing import cast
from uuid import UUID, uuid4

from redis.asyncio import Redis

_RELEASE = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0"


class RedisNotificationClaims:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(document_id: UUID) -> str:
        return f"notified:{document_id}"

    async def claim(self, document_id: UUID, ttl_seconds: int) -> str | None:
        token = str(uuid4())
        claimed = await self._redis.set(self._key(document_id), token, nx=True, ex=ttl_seconds)
        return token if claimed else None

    async def release(self, document_id: UUID, token: str) -> None:
        await cast(Awaitable[int], self._redis.eval(_RELEASE, 1, self._key(document_id), token))

    async def reset(self, document_id: UUID) -> None:
        await self._redis.delete(self._key(document_id))
