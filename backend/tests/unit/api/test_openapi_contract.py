"""OpenAPI exposes the same errors the HTTP handlers return."""

import inspect

import pytest
from fastapi.testclient import TestClient

from src.app.exceptions import auth, base, documents, llm, quizzes, quota, sharing, storage, users, widgets
from src.app.exceptions.base import BaseAppException
from src.main import create_app

pytestmark = pytest.mark.unit


def test_openapi_uses_unified_error_responses_and_lists_error_codes() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]
    assert "ErrorResponse" in components
    codes = set(components["ErrorCode"]["enum"])
    for module in (auth, base, documents, llm, quota, quizzes, sharing, storage, users, widgets):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseAppException):
                assert cls.error_code in codes
    assert {"queue_unavailable", "request_validation_error", "rate_limited"} <= codes
    for path, methods in schema["paths"].items():
        if path.startswith("/api/v1/"):
            for operation in methods.values():
                assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorResponse"
                }


@pytest.mark.parametrize("cookie", [None, "expired-or-invalid"])
def test_logout_clears_cookie_without_authentication(cookie: str | None) -> None:
    with TestClient(create_app()) as client:
        if cookie is not None:
            client.cookies.set("grasp_session", cookie)
        response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "max-age=0" in response.headers["set-cookie"].lower()
