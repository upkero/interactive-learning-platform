"""Recording fake for progress events."""

from uuid import UUID

from src.app.contracts.progress import ProgressEventType


class FakeProgressNotifier:
    def __init__(self) -> None:
        self.events: list[tuple[UUID, ProgressEventType, UUID | None, str | None, str]] = []

    async def emit(
        self,
        document_id: UUID,
        event_type: ProgressEventType,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
    ) -> None:
        self.events.append((document_id, event_type, part_id, stage, message))
