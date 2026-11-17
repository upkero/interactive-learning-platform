"""Recording fake for progress events."""

from collections.abc import Callable
from uuid import UUID

from src.app.contracts.progress import ProgressEventType


class FakeProgressNotifier:
    def __init__(self, *, committed: Callable[[], int] | None = None) -> None:
        self.events: list[tuple[UUID, ProgressEventType, UUID | None, str | None, str]] = []
        # Snapshot the caller's commit counter at emit time: events must only
        # leave the service after the transaction that produced them committed.
        self._committed = committed
        self.committed_at_emit: list[int | None] = []

    async def emit(
        self,
        document_id: UUID,
        event_type: ProgressEventType,
        *,
        part_id: UUID | None = None,
        stage: str | None = None,
        message: str = "",
    ) -> None:
        self.committed_at_emit.append(self._committed() if self._committed is not None else None)
        self.events.append((document_id, event_type, part_id, stage, message))
