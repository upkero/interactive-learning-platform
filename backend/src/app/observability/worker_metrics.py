"""Prometheus metrics for Celery workers in multiprocess mode."""

import os
from time import perf_counter

from celery.signals import task_postrun, task_prerun, worker_init, worker_process_shutdown
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Histogram, multiprocess, start_http_server

from src.app.core.settings.observability import get_observability_settings

celery_tasks = Counter("celery_tasks", "Celery tasks by final state", ["task", "state"])
celery_task_duration = Histogram(
    "celery_task_duration_seconds", "Celery task duration", ["task"], buckets=(1, 5, 15, 30, 60, 120, 180, 300, 330)
)
_started: dict[str, float] = {}


@worker_init.connect  # type: ignore[untyped-decorator]
def start_metrics_server(sender: object = None, **_: object) -> None:
    directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if directory:
        if not os.path.isdir(directory) or not os.access(directory, os.W_OK):
            raise SystemExit("PROMETHEUS_MULTIPROC_DIR must be a writable directory")
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    else:
        if getattr(sender, "concurrency", 1) > 1:
            raise SystemExit("PROMETHEUS_MULTIPROC_DIR is required when worker concurrency is greater than 1")
        registry = REGISTRY
    start_http_server(get_observability_settings().worker_metrics_port, registry=registry)


@task_prerun.connect  # type: ignore[untyped-decorator]
def on_task_prerun(task_id: str, **_: object) -> None:
    _started[task_id] = perf_counter()


@task_postrun.connect  # type: ignore[untyped-decorator]
def on_task_postrun(task_id: str, task: object, state: str | None = None, **_: object) -> None:
    name = getattr(task, "name", "unknown")
    celery_tasks.labels(task=name, state=(state or "unknown").lower()).inc()
    if (started := _started.pop(task_id, None)) is not None:
        celery_task_duration.labels(task=name).observe(perf_counter() - started)


@worker_process_shutdown.connect  # type: ignore[untyped-decorator]
def on_process_shutdown(**_: object) -> None:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.mark_process_dead(os.getpid())  # type: ignore[no-untyped-call]
