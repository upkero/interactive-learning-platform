"""Unit tests 1.4.1: slowapi rate limiting answers the unified error format."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.app.api.v1.exception_handlers import register_exception_handlers
from src.app.api.v1.middleware.rate_limit import limiter, register_rate_limit

pytestmark = pytest.mark.unit


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    register_rate_limit(app)

    @app.get("/limited")
    @limiter.limit("2/minute")
    async def limited(request: Request) -> dict[str, str]:
        return {"ok": "1"}

    return app


# Built once on purpose: slowapi registers the decorated endpoint's limits
# in the shared module-level Limiter keyed by the function name, so every
# app rebuild would stack another limit onto the same endpoint.
_APP = _build_app()


@pytest.fixture
def client() -> TestClient:
    limiter.reset()  # in-memory storage is shared between tests
    return TestClient(_APP)


def test_requests_within_the_limit_pass(client: TestClient) -> None:
    assert client.get("/limited", headers={"x-forwarded-for": "1.2.3.4"}).status_code == 200
    assert client.get("/limited", headers={"x-forwarded-for": "1.2.3.4"}).status_code == 200


def test_limit_exceeded_is_429_in_the_unified_format(client: TestClient) -> None:
    headers = {"x-forwarded-for": "1.2.3.4"}
    for _ in range(2):
        assert client.get("/limited", headers=headers).status_code == 200
    response = client.get("/limited", headers=headers)
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests.", "error_code": "rate_limited"}


def test_the_limit_is_per_client_ip(client: TestClient) -> None:
    assert client.get("/limited", headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
    assert client.get("/limited", headers={"x-forwarded-for": "2.2.2.2"}).status_code == 200
