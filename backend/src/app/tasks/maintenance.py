"""Short periodic maintenance tasks."""

from src.app.tasks.names import NORMALIZE_LIBRARY_TASK, WATCHDOG_TICK_TASK
from src.app.tasks.runner import run_async
from src.worker import celery_app


@celery_app.task(name=WATCHDOG_TICK_TASK)  # type: ignore[untyped-decorator]
def watchdog_tick() -> None:
    run_async(lambda c: c.watchdog.tick())


@celery_app.task(name=NORMALIZE_LIBRARY_TASK)  # type: ignore[untyped-decorator]
def normalize_library() -> None:
    run_async(lambda c: c.library_normalizer.run())
