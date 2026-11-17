"""Worker task used exclusively by the Redis queue-order integration test."""

import redis

from src.app.core.settings.celery import get_celery_settings
from src.worker import celery_app


@celery_app.task(name="tests.record_priority")  # type: ignore[untyped-decorator]
def record_priority(key: str, value: str) -> None:
    redis.Redis.from_url(get_celery_settings().broker_url).rpush(key, value)
