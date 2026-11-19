"""In-memory progress notifier for orchestration tests."""

from uuid import UUID

from src.app.contracts.progress import ProgressEvent, ProgressEventType


class FakeProgressNotifier:
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    async def publish(self, event: ProgressEvent) -> str:
        self.events.append(event)
        return f"{len(self.events)}-0"

    async def emit(self, document_id: UUID, event_type: ProgressEventType, **kwargs: object) -> str:
        event = ProgressEvent(document_id=document_id, event_type=event_type, **kwargs)  # type: ignore[arg-type]
        return await self.publish(event)
