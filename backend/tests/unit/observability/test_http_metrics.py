from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from src.app.api.v1.exception_handlers import register_exception_handlers
from src.app.api.v1.middleware.metrics import register_metrics
from src.app.api.v1.middleware.request_id import register_request_id_middleware

pytestmark = pytest.mark.unit


def test_unmatched_and_route_templates_do_not_leak_paths() -> None:
    app = FastAPI()
    register_metrics(app)
    router = APIRouter(prefix="/api/v1")

    @router.get("/items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    app.include_router(router)
    client = TestClient(app)
    first, second = str(uuid4()), str(uuid4())
    client.get(f"/missing/{first}")
    client.get(f"/missing/{second}")
    client.get(f"/api/v1/items/{first}")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'route="unmatched"' in response.text
    assert 'route="/api/v1/items/{item_id}"' in response.text
    assert first not in response.text and second not in response.text
    assert 'route="/metrics"' not in response.text


def test_unhandled_error_records_500_and_duration() -> None:
    app = FastAPI()
    register_request_id_middleware(app)
    register_metrics(app)
    register_exception_handlers(app)

    @app.get("/failing-observability-test/{item_id}")
    async def fail(item_id: str) -> None:
        raise RuntimeError("test failure")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/failing-observability-test/123")
    assert response.status_code == 500
    metrics = client.get("/metrics").text
    assert 'route="/failing-observability-test/{item_id}",status="500"} 1.0' in metrics
    assert (
        'http_request_duration_seconds_count{method="GET",route="/failing-observability-test/{item_id}"} 1.0' in metrics
    )
