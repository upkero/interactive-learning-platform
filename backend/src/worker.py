"""Celery worker and scheduler configuration."""

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging as celery_setup_logging
from kombu import Exchange, Queue

from src.app.core.logging import setup_logging
from src.app.core.settings.celery import get_celery_settings
from src.app.core.settings.logging import get_logging_settings
from src.app.core.settings.solver import get_solver_settings
from src.app.tasks.names import (
    MAINTENANCE_QUEUE,
    NORMALIZE_LIBRARY_TASK,
    PARSE_DOCUMENT_TASK,
    PARTS_HIGH_QUEUE,
    PARTS_QUEUE,
    WATCHDOG_TICK_TASK,
)

setup_logging(get_logging_settings())


@celery_setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logging(**kwargs: object) -> None:
    setup_logging(get_logging_settings())


get_solver_settings()  # Validate before a worker can consume any messages.
celery_app = Celery(
    "grasp",
    broker=get_celery_settings().broker_url,
    include=["src.app.tasks.parts", "src.app.tasks.documents", "src.app.tasks.maintenance"],
)
celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=330,
    task_default_queue=PARTS_QUEUE,
    task_queues=tuple(
        Queue(name, exchange=Exchange(name, type="direct"), routing_key=name)
        for name in (MAINTENANCE_QUEUE, PARTS_HIGH_QUEUE, PARTS_QUEUE)
    ),
    task_routes={PARSE_DOCUMENT_TASK: {"queue": PARTS_HIGH_QUEUE}, "maintenance.*": {"queue": MAINTENANCE_QUEUE}},
    broker_transport="src.app.tasks.redis_transport:OrderedRedisTransport",
    broker_transport_options={"queue_order_strategy": "priority", "visibility_timeout": 3600},
    timezone="UTC",
    beat_schedule={
        "watchdog-tick": {"task": WATCHDOG_TICK_TASK, "schedule": 60.0, "options": {"expires": 55}},
        "normalize-library": {"task": NORMALIZE_LIBRARY_TASK, "schedule": crontab(minute=0, hour=3, day_of_week="mon")},
    },
)
