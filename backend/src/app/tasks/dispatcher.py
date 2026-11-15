"""Celery-backed TaskDispatcher (story 1.4.3).

Tasks are addressed by name (``send_task``), so the API package stays
decoupled from the worker's task definitions: story 1.5 registers them
under the shared names from ``tasks/names.py``. Celery is a sync SDK,
every call goes through ``asyncio.to_thread`` — the dispatcher is only
used after commit, never inside a transaction.

A broker failure (Redis down, connection reset) is translated into
``TaskDispatchError`` so the API answers 503 ``queue_unavailable``
instead of leaking kombu internals.
"""

import asyncio
from uuid import UUID

from celery import Celery
from kombu.exceptions import KombuError

from src.app.core.settings.celery import CelerySettings
from src.app.exceptions.tasks import TaskDispatchError
from src.app.tasks.names import (
    FINISH_PENDING_WIDGETS_TASK,
    PARSE_DOCUMENT_TASK,
    PARTS_HIGH_QUEUE,
    PARTS_QUEUE,
    PROCESS_PART_TASK,
)


class CeleryTaskDispatcher:
    def __init__(self, settings: CelerySettings) -> None:
        self._app = Celery(broker=settings.broker_url, backend=None)

    async def enqueue_parse(self, document_id: UUID) -> None:
        # the parse task is routed to the high-priority queue explicitly:
        # the worker's task_routes do not apply to this separate app
        await self._send(PARSE_DOCUMENT_TASK, document_id, queue=PARTS_HIGH_QUEUE)

    async def enqueue_part(self, part_id: UUID, *, high: bool) -> None:
        await self._send(PROCESS_PART_TASK, part_id, queue=PARTS_HIGH_QUEUE if high else PARTS_QUEUE)

    async def enqueue_finish_pending(self, part_id: UUID) -> None:
        await self._send(FINISH_PENDING_WIDGETS_TASK, part_id, queue=PARTS_QUEUE)

    async def _send(self, task_name: str, task_id: UUID, *, queue: str) -> None:
        """Send one task; task arguments are always ``str(uuid)``."""
        try:
            await asyncio.to_thread(self._app.send_task, task_name, args=[str(task_id)], queue=queue)
        except (KombuError, OSError) as exc:
            raise TaskDispatchError(extra={"task": task_name}) from exc


__all__ = ["CeleryTaskDispatcher"]
