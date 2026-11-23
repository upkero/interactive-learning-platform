"""Celery task entry points for part processing."""

import logging
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from src.app.tasks.names import FINISH_PENDING_WIDGETS_TASK, PROCESS_PART_TASK
from src.app.tasks.runner import run_async
from src.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name=PROCESS_PART_TASK)  # type: ignore[untyped-decorator]
def process_part(part_id: str) -> None:
    pid = UUID(part_id)
    try:
        run_async(lambda c: c.processing_pipeline.process(pid), part_id=part_id)
    except SoftTimeLimitExceeded:
        run_async(lambda c: c.part_recovery.retry_or_fail(pid, reason="soft_time_limit"), part_id=part_id)
    except Exception:
        logger.exception("part.processing_failed", extra={"part_id": part_id})
        run_async(lambda c: c.part_recovery.fail(pid, reason="pipeline_error"), part_id=part_id)
        raise


@celery_app.task(name=FINISH_PENDING_WIDGETS_TASK)  # type: ignore[untyped-decorator]
def finish_pending_widgets(part_id: str) -> None:
    UUID(part_id)
    raise NotImplementedError("Pending widget processing is not available until story 2.7")
