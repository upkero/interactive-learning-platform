from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from prometheus_client import REGISTRY, multiprocess

from src.app.observability import worker_metrics

pytestmark = pytest.mark.unit


def test_single_worker_uses_default_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    server = Mock()
    monkeypatch.setattr(worker_metrics, "start_http_server", server)
    worker_metrics.start_metrics_server(sender=SimpleNamespace(concurrency=1))
    assert server.call_args.kwargs["registry"] is REGISTRY


def test_prefork_without_directory_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    with pytest.raises(SystemExit, match="PROMETHEUS_MULTIPROC_DIR"):
        worker_metrics.start_metrics_server(sender=SimpleNamespace(concurrency=2))


def test_process_shutdown_marks_process_dead(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    mark_dead = Mock()
    monkeypatch.setattr(multiprocess, "mark_process_dead", mark_dead)
    worker_metrics.on_process_shutdown()
    mark_dead.assert_called_once()
