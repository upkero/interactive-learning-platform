import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from src.app.api.v1.dependencies import get_container
from src.app.api.v1.routers import health as health_module
from src.main import app

pytestmark = pytest.mark.unit


class FakeContainer:
    """Подмена реального контейнера зависимостей в юнит-тестах (поля не вызываются)."""

    def __init__(self) -> None:
        self.session_factory = object()
        self.redis_client = object()
        self.llm_client = object()


class _BrokenLLM:
    """Если /health/ready решит пинговать LLM — тест упадёт."""

    async def ping(self) -> bool:
        raise AssertionError("LLM must not be pinged by /health/ready")


async def _call_health_ready(
    monkeypatch: pytest.MonkeyPatch,
    container: object,
    overrides: dict[str, object] | None = None,
) -> httpx.Response:
    # Readiness-проверки подменяем стабами: юнит-тесты не ходят в сеть
    async def ok_check(*args: object) -> str | None:
        return None

    patches: dict[str, object] = {"_check_db": ok_check, "_check_redis": ok_check, "_check_minio": ok_check}
    patches.update(overrides or {})
    for name, replacement in patches.items():
        monkeypatch.setattr(health_module, name, replacement)
    app.dependency_overrides[get_container] = lambda: container  # type: ignore[arg-type,return-value]
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()


async def test_health_live() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200


async def test_health_ready_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer()
    container.llm_client = _BrokenLLM()  # LLM недоступна, но в readiness не пингуется
    response = await _call_health_ready(monkeypatch, container)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_ready_reports_unhealthy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_db(*args: object) -> str | None:
        return "PostgreSQL unavailable"

    monkeypatch.setattr(health_module, "_check_db", fail_db)
    response = await _call_health_ready(monkeypatch, FakeContainer(), overrides={"_check_db": fail_db})
    assert response.status_code == 503
    assert "PostgreSQL" in response.json()["detail"]
