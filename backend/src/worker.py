from celery import Celery

from src.app.core.logging import setup_logging
from src.app.core.settings.celery import get_celery_settings
from src.app.core.settings.logging import get_logging_settings

setup_logging(get_logging_settings())
settings = get_celery_settings()

celery_app = Celery(
    "grasp",
    broker=str(settings.broker_url),
)

celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=330,
    task_default_queue="parts",
)