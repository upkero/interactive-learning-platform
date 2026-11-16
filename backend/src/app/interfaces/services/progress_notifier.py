"""Progress events for the document stream."""

from typing import Protocol
from uuid import UUID


class ProgressNotifier(Protocol):
    async def emit(
        self,
        document_id: UUID,
        event_type: str,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
    ) -> None: ...
