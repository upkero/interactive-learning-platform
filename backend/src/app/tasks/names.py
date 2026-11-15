"""Task names and queues shared by the API dispatcher and the worker (story 1.5).

Story 1.5 registers its Celery tasks with these names, so the API and
the worker cannot drift apart. The API only sends; it never defines
tasks.
"""

from typing import Final

PARSE_DOCUMENT_TASK: Final[str] = "documents.parse_document"
PROCESS_PART_TASK: Final[str] = "parts.process_part"
FINISH_PENDING_WIDGETS_TASK: Final[str] = "parts.finish_pending_widgets"

MAINTENANCE_QUEUE: Final[str] = "maintenance"
PARTS_HIGH_QUEUE: Final[str] = "parts.high"
PARTS_QUEUE: Final[str] = "parts"

__all__ = [
    "FINISH_PENDING_WIDGETS_TASK",
    "MAINTENANCE_QUEUE",
    "PARSE_DOCUMENT_TASK",
    "PARTS_HIGH_QUEUE",
    "PARTS_QUEUE",
    "PROCESS_PART_TASK",
]
