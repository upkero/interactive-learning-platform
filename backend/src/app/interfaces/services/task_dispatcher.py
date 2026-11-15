"""TaskDispatcher interface: enqueue background work after commit.

The API never touches Celery or Redis directly (story 1.4): it calls
this interface after the transaction committed, and test doubles record
the calls so API tests need no broker. Task names and queues are the
shared constants of ``tasks/names.py`` (story 1.5).
"""

from typing import Protocol
from uuid import UUID


class TaskDispatcher(Protocol):
    """Public API of the queue layer (implemented by tasks/dispatcher.py)."""

    async def enqueue_parse(self, document_id: UUID) -> None: ...

    async def enqueue_part(self, part_id: UUID, *, high: bool) -> None: ...

    async def enqueue_finish_pending(self, part_id: UUID) -> None: ...
