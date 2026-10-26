import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app

pytestmark = pytest.mark.unit


async def test_health_live() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
