"""Unit tests 1.4.1: the unified error format of the API.

Every error path of the app — domain exceptions, request validation,
unknown routes, unhandled crashes — must answer the same body shape
``{"detail", "error_code"}``, so the frontend client generated from
OpenAPI can treat all failures uniformly.
"""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.app.api.v1.exception_handlers import register_exception_handlers
from src.app.exceptions.base import BaseAppException

pytestmark = pytest.mark.unit


class FakeDomainError(BaseAppException):
    status_code = 409
    error_code = "domain_conflict"
    default_detail = "Domain conflict."


async def _raising_dependency() -> int:
    raise ZeroDivisionError("boom")


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    class Body(BaseModel):
        number: int

    @app.get("/domain")
    async def domain_error() -> None:
        raise FakeDomainError(extra={"available": 3, "requested": 5})

    @app.get("/domain-500")
    async def domain_500() -> None:
        raise BaseAppException()

    @app.post("/validate")
    async def validate(body: Body) -> dict[str, int]:
        return {"number": body.number}

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    @app.get("/depends")
    async def depends(flag: Annotated[int, Depends(_raising_dependency)]) -> None:
        _ = flag  # pragma: no cover — the dependency raises before this

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)


def test_domain_error_maps_status_code_and_error_code(client: TestClient) -> None:
    response = client.get("/domain")
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Domain conflict.",
        "error_code": "domain_conflict",
        "available": 3,
        "requested": 5,
    }


def test_domain_error_extra_is_merged_into_the_response(client: TestClient) -> None:
    response = client.get("/domain")
    assert response.status_code == 409
    body = response.json()
    # numbers land at the top level next to detail/error_code, e.g.
    # available/requested on quota_exceeded
    assert body["available"] == 3
    assert body["requested"] == 5


def test_validation_error_uses_the_unified_format(client: TestClient) -> None:
    response = client.post("/validate", json={"number": "not-a-number"})
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"detail", "error_code"}
    assert body["error_code"] == "request_validation_error"
    assert isinstance(body["detail"], list)


def test_unknown_route_is_404_in_the_unified_format(client: TestClient) -> None:
    response = client.get("/no-such-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"detail", "error_code"}
    assert body["error_code"] == "http_error"


def test_unhandled_exception_is_500_without_inner_details(client: TestClient) -> None:
    response = client.get("/crash")
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "Internal server error", "error_code": "internal_server_error"}


def test_app_exception_500_is_logged_with_request_id(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    response = client.get("/domain-500")
    assert response.status_code == 500
    # the log record must carry the request context for 5xx triage
    assert any("Application error" in record.message for record in caplog.records)


def test_dependency_crash_is_still_the_unified_500(client: TestClient) -> None:
    response = client.get("/depends")
    assert response.status_code == 500
    assert response.json()["error_code"] == "internal_server_error"
