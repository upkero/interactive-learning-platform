"""In-memory notification deduplication with an injectable Redis outage."""

from uuid import UUID, uuid4

from redis.exceptions import RedisError


class FakeNotificationClaims:
    def __init__(self) -> None:
        self.claims: dict[UUID, str] = {}
        self.fail_reset = False
        self.reset_calls: list[UUID] = []

    async def claim(self, document_id: UUID, ttl_seconds: int) -> str | None:
        assert ttl_seconds > 0
        if document_id in self.claims:
            return None
        token = str(uuid4())
        self.claims[document_id] = token
        return token

    async def release(self, document_id: UUID, token: str) -> None:
        if self.claims.get(document_id) == token:
            del self.claims[document_id]

    async def reset(self, document_id: UUID) -> None:
        self.reset_calls.append(document_id)
        if self.fail_reset:
            raise RedisError("unavailable")
        self.claims.pop(document_id, None)
