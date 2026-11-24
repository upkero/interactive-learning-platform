from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from src.app.api.v1.middleware.metrics import register_metrics

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
