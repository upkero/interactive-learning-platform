"""Dedicated Celery application for the isolated multiprocess smoke test."""

import os
import time

from celery import Celery

from src.app.observability import worker_metrics  # noqa: F401

app = Celery(
    "observability_smoke", broker=os.environ["TEST_CELERY_REDIS_URL"], backend=os.environ["TEST_CELERY_REDIS_URL"]
)


@app.task(name="observability.smoke")  # type: ignore[untyped-decorator]
def probe() -> dict[str, str | int]:
    time.sleep(1)
    return {"pid": os.getpid(), "broker": app.conf.broker_url, "backend": app.conf.result_backend}
