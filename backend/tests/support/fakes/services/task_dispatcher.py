"""In-memory fake of TaskDispatcher: records the calls in order."""

from uuid import UUID

from src.app.interfaces.services.task_dispatcher import TaskDispatcher


class FakeTaskDispatcher(TaskDispatcher):
    """Appends every enqueue to ``calls``; API tests assert on the log.

    ``fail_with`` makes every enqueue raise that error instead, which is
    how tests exercise the "broker is down after commit" branch.
    """

    def __init__(self, *, fail_with: BaseException | None = None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.fail_with = fail_with

    def _record(self, name: str, args: tuple[object, ...]) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((name, args))

    async def enqueue_parse(self, document_id: UUID) -> None:
        self._record("enqueue_parse", (document_id,))

    async def enqueue_part(self, part_id: UUID, *, high: bool) -> None:
        self._record("enqueue_part", (part_id, high))

    async def enqueue_finish_pending(self, part_id: UUID) -> None:
        self._record("enqueue_finish_pending", (part_id,))

    def reset(self) -> None:
        self.calls.clear()
