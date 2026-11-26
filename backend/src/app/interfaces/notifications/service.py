"""Completion notification interface used by processing orchestration."""

from typing import Protocol
from uuid import UUID


class DocumentNotifications(Protocol):
    async def on_document_finished(self, document_id: UUID) -> None: ...
