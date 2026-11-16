import logging

import pytest

from src.app.bootstrap.container import ApplicationContainer
from src.app.core.log_context import bind_log_context, get_log_context
from src.app.core.logging import _ContextFilter
from src.app.tasks.names import NORMALIZE_LIBRARY_TASK, WATCHDOG_TICK_TASK
from src.app.tasks.redis_transport import OrderedChannel
from src.app.tasks.runner import run_async
from src.worker import celery_app

pytestmark = pytest.mark.unit


def test_worker_config() -> None:
    conf = celery_app.conf
    assert conf.task_acks_late and conf.task_ignore_result
    assert conf.worker_prefetch_multiplier == 1
    assert conf.broker_transport_options["queue_order_strategy"] == "priority"
    assert [queue.name for queue in conf.task_queues] == ["maintenance", "parts.high", "parts"]
    assert (conf.task_soft_time_limit, conf.task_time_limit) == (300, 330)


def test_beat_schedule_and_routes() -> None:
    conf = celery_app.conf
    assert conf.beat_schedule["watchdog-tick"]["task"] == WATCHDOG_TICK_TASK
    assert conf.beat_schedule["watchdog-tick"]["schedule"] == 60.0
    weekly = conf.beat_schedule["normalize-library"]
    assert weekly["task"] == NORMALIZE_LIBRARY_TASK
    assert weekly["schedule"].minute == {0}
    assert weekly["schedule"].hour == {3}
    assert weekly["schedule"].day_of_week == {1}
    assert conf.timezone == "UTC"
    assert conf.task_routes["maintenance.*"]["queue"] == "maintenance"


def test_context_is_nested_and_restored() -> None:
    with bind_log_context(part_id="part"):
        with bind_log_context(document_id="doc"):
            record = logging.LogRecord("test", logging.INFO, "", 0, "message", (), None)
            assert _ContextFilter().filter(record)
            assert record.part_id == "part"  # type: ignore[attr-defined]
            assert record.document_id == "doc"  # type: ignore[attr-defined]
        assert get_log_context() == {"part_id": "part"}
    assert get_log_context() == {}


def test_transport_preserves_consumer_order() -> None:
    channel = object.__new__(OrderedChannel)
    channel._active_queues = ["maintenance", "parts.high", "parts", "parts.high"]
    channel.active_fanout_queues = set()
    assert channel.active_queues == ["maintenance", "parts.high", "parts"]


def test_runner_closes_container_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = []

    async def close(self: ApplicationContainer) -> None:
        closed.append(self)

    async def fail(container: ApplicationContainer) -> None:
        assert get_log_context() == {"part_id": "42"}
        raise ValueError("failed")

    monkeypatch.setattr(ApplicationContainer, "close", close)
    with pytest.raises(ValueError, match="failed"):
        run_async(fail, part_id="42")
    assert len(closed) == 1
    assert get_log_context() == {}
