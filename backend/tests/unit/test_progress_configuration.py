import pytest
import redis.asyncio as aioredis

from src.app.bootstrap import container as container_module
from src.app.bootstrap.container import ApplicationContainer
from src.app.core.settings.progress import ProgressSettings

pytestmark = pytest.mark.unit


def test_progress_redis_uses_configured_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = ProgressSettings(socket_timeout=23.5)
    calls: list[tuple[str, dict[str, object]]] = []
    client = object()

    def from_url(url: str, **kwargs: object) -> object:
        calls.append((url, kwargs))
        return client

    monkeypatch.setattr(container_module, "get_progress_settings", lambda: settings)
    monkeypatch.setattr(aioredis.Redis, "from_url", staticmethod(from_url))

    result = ApplicationContainer().progress_redis

    assert result is client
    assert calls == [(str(settings.url), {"socket_timeout": 23.5})]
