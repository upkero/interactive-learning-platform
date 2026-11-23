"""Idempotency claim store for document notifications."""

from typing import Protocol
from uuid import UUID


class NotificationClaims(Protocol):
    async def claim(self, document_id: UUID, ttl_seconds: int) -> str | None: ...

    async def release(self, document_id: UUID, token: str) -> None: ...

    async def reset(self, document_id: UUID) -> None: ...
