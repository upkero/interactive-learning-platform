"""Celery-backed TaskDispatcher (story 1.4.3).

Tasks are addressed by name (``send_task``), so the API package stays
decoupled from the worker's task definitions: story 1.5 registers them
under the same names. Celery is a sync SDK, every call goes through
``asyncio.to_thread`` — the dispatcher is only used after commit, never
inside a transaction.
"""

import asyncio
from uuid import UUID

from celery import Celery

from src.app.core.settings.celery import CelerySettings

PARSE_DOCUMENT_TASK = "grasp.parse_document"
PROCESS_PART_TASK = "grasp.process_part"
FINISH_PENDING_PART_TASK = "grasp.finish_pending_part"


class CeleryTaskDispatcher:
    def __init__(self, settings: CelerySettings) -> None:
        self._app = Celery(broker=settings.broker_url, backend=None)

    async def enqueue_parse(self, document_id: UUID) -> None:
        await asyncio.to_thread(self._app.send_task, PARSE_DOCUMENT_TASK, args=[str(document_id)])

    async def enqueue_part(self, part_id: UUID, *, high: bool = False) -> None:
        await asyncio.to_thread(
            self._app.send_task,
            PROCESS_PART_TASK,
            args=[str(part_id)],
            queue="parts.high" if high else "parts",
        )

    async def enqueue_finish_pending(self, part_id: UUID) -> None:
        await asyncio.to_thread(self._app.send_task, FINISH_PENDING_PART_TASK, args=[str(part_id)])
