import logging

import pytest

from src.app.bootstrap.container import ApplicationContainer
from src.app.core.log_context import bind_log_context, get_log_context
from src.app.core.logging import _RequestIdFilter
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


def test_context_is_nested_and_restored() -> None:
    with bind_log_context(part_id="part"):
        with bind_log_context(document_id="doc"):
            record = logging.LogRecord("test", logging.INFO, "", 0, "message", (), None)
            assert _RequestIdFilter().filter(record)
            assert record.part_id == "part"  # type: ignore[attr-defined]
            assert record.document_id == "doc"  # type: ignore[attr-defined]
        assert get_log_context() == {"part_id": "part"}
    assert get_log_context() == {}


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
