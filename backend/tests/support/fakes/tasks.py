"""In-memory fake of TaskDispatcher: records the calls in order."""

from uuid import UUID

from src.app.interfaces.services.task_dispatcher import TaskDispatcher


class FakeTaskDispatcher(TaskDispatcher):
    """Appends every enqueue to ``calls``; API tests assert on the log."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_parse(self, document_id: UUID) -> None:
        self.calls.append(("enqueue_parse", (document_id,)))

    async def enqueue_part(self, part_id: UUID, *, high: bool = False) -> None:
        self.calls.append(("enqueue_part", (part_id, high)))

    async def enqueue_finish_pending(self, part_id: UUID) -> None:
        self.calls.append(("enqueue_finish_pending", (part_id,)))

    def reset(self) -> None:
        self.calls.clear()
