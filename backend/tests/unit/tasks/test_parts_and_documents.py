import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.app.tasks import parts
from src.app.tasks.documents import parse_document
from src.app.tasks.names import PARSE_DOCUMENT_TASK
from src.worker import celery_app

pytestmark = pytest.mark.unit


def test_parse_task_has_contract_and_limits() -> None:
    assert parse_document.name == PARSE_DOCUMENT_TASK
    assert parse_document.soft_time_limit == 600 and parse_document.time_limit == 660
    assert celery_app.conf.task_routes[PARSE_DOCUMENT_TASK]["queue"] == "parts.high"


def test_unavailable_real_pipeline_is_rejected_before_worker_starts() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import src.worker"],
        env={**os.environ, "SOLVER_PIPELINE": "real"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "pipeline" in result.stderr


def test_pipeline_error_triggers_atomic_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    part_id = uuid4()
    failure = AsyncMock()
    calls = 0

    def runner(fn: object, **context: str) -> None:
        nonlocal calls
        calls += 1
        assert context["part_id"] == str(part_id)
        if calls == 1:
            raise RuntimeError("solver failed")
        assert callable(fn)
        asyncio.run(fn(SimpleNamespace(part_recovery=SimpleNamespace(fail=failure))))

    monkeypatch.setattr(parts, "run_async", runner)
    with pytest.raises(RuntimeError, match="solver failed"):
        parts.process_part.run(str(part_id))
    failure.assert_awaited_once_with(part_id, reason="pipeline_error")
