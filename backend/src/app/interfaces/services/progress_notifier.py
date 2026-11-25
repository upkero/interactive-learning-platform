"""Progress events for the document stream."""

from typing import Protocol
from uuid import UUID

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.contracts.progress import ProgressEventType


class ProgressNotifier(Protocol):
    async def reset(self, document_id: UUID) -> None: ...

    async def emit(
        self,
        document_id: UUID,
        event_type: ProgressEventType,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
        error_code: DocumentErrorCode | None = None,
    ) -> str | None: ...
