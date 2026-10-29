import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from src.app.api.v1.dependencies import get_container
from src.app.api.v1.routers import health as health_module
from src.main import app

pytestmark = pytest.mark.unit


class FakeContainer:
    """Stands in for the real DI container in unit tests (fields are never called)."""

    def __init__(self) -> None:
        self.session_factory = object()
        self.redis_client = object()
        self.llm_client = object()
        self.object_storage = object()


class _BrokenLLM:
    """Fails the test if /health/ready decides to ping the LLM."""

    async def ping(self) -> bool:
        raise AssertionError("LLM must not be pinged by /health/ready")


async def _call_health_ready(
    monkeypatch: pytest.MonkeyPatch,
    container: object,
    overrides: dict[str, object] | None = None,
) -> httpx.Response:
    # Readiness checks are stubbed out: unit tests never touch the network
    async def ok_check(*args: object) -> str | None:
        return None

    patches: dict[str, object] = {"_check_db": ok_check, "_check_redis": ok_check, "_check_object_storage": ok_check}
    patches.update(overrides or {})
    for name, replacement in patches.items():
        monkeypatch.setattr(health_module, name, replacement)
    app.dependency_overrides[get_container] = lambda: container
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
    container.llm_client = _BrokenLLM()  # LLM is down, but readiness never pings it
    response = await _call_health_ready(monkeypatch, container)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_ready_reports_unhealthy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_db(*args: object) -> str | None:
        return "PostgreSQL unavailable"

    response = await _call_health_ready(monkeypatch, FakeContainer(), overrides={"_check_db": fail_db})
    assert response.status_code == 503
    assert "PostgreSQL" in response.json()["detail"]


async def test_health_ready_fails_when_minio_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stopped MinIO must turn /health/ready into 503 (ticket 1.3.1)."""

    async def fail_storage(*args: object) -> str | None:
        return "MinIO unavailable"

    response = await _call_health_ready(monkeypatch, FakeContainer(), overrides={"_check_object_storage": fail_storage})
    assert response.status_code == 503
    assert "MinIO" in response.json()["detail"]
