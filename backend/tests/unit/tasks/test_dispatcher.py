"""Task dispatcher routing and broker error translation."""

from uuid import UUID, uuid4

import pytest
from kombu.exceptions import OperationalError

from src.app.core.settings.celery import CelerySettings
from src.app.exceptions.tasks import TaskDispatchError
from src.app.tasks.dispatcher import CeleryTaskDispatcher

pytestmark = pytest.mark.unit


async def test_task_names_queues_and_serialized_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatcher = CeleryTaskDispatcher(CelerySettings(broker_url="memory://"))
    calls: list[tuple[str, list[str], str]] = []

    def record(name: str, *, args: list[str], queue: str) -> None:
        calls.append((name, args, queue))

    monkeypatch.setattr(dispatcher._app, "send_task", record)
    document, first, other = uuid4(), uuid4(), uuid4()
    await dispatcher.enqueue_parse(document)
    await dispatcher.enqueue_part(first, high=True)
    await dispatcher.enqueue_part(other, high=False)
    await dispatcher.enqueue_finish_pending(other)
    assert calls == [
        ("documents.parse_document", [str(document)], "parts.high"),
        ("parts.process_part", [str(first)], "parts.high"),
        ("parts.process_part", [str(other)], "parts"),
        ("parts.finish_pending_widgets", [str(other)], "parts"),
    ]


@pytest.mark.parametrize("cause", [OperationalError("kombu failure"), OSError("network failure")])
@pytest.mark.parametrize("part", [False, True])
async def test_broker_failure_is_private_and_retains_cause(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, cause: Exception, part: bool
) -> None:
    dispatcher = CeleryTaskDispatcher(CelerySettings(broker_url="memory://"))

    def fail(name: str, *, args: list[str], queue: str) -> None:
        raise cause

    monkeypatch.setattr(dispatcher._app, "send_task", fail)
    with pytest.raises(TaskDispatchError) as caught:
        if part:
            await dispatcher.enqueue_part(UUID(int=1), high=True)
        else:
            await dispatcher.enqueue_parse(UUID(int=1))
    assert caught.value.__cause__ is cause
    assert "task" not in caught.value.extra
    records = [record for record in caplog.records if record.message == "Task dispatch failed."]
    assert len(records) == 1
    assert vars(records[0])["task"] == ("parts.process_part" if part else "documents.parse_document")
    assert vars(records[0])["task_arg"] == str(UUID(int=1))
    assert records[0].exc_info is not None
