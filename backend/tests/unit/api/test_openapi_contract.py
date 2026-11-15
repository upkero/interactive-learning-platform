"""OpenAPI exposes the same errors the HTTP handlers return."""

import importlib
import pkgutil

import pytest
from fastapi.testclient import TestClient

import src.app.exceptions as exceptions
from src.app.exceptions.base import BaseAppException
from src.main import create_app

pytestmark = pytest.mark.unit


def test_openapi_uses_unified_error_responses_and_lists_error_codes() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]
    assert "ErrorResponse" in components
    codes = set(components["ErrorCode"]["enum"])
    for module in pkgutil.walk_packages(exceptions.__path__, exceptions.__name__ + "."):
        importlib.import_module(module.name)

    def descendants(cls: type[BaseAppException]) -> set[type[BaseAppException]]:
        children = set(cls.__subclasses__())
        return children | {child for subclass in children for child in descendants(subclass)}

    public_codes = {cls.error_code for cls in descendants(BaseAppException) if cls.public}
    assert codes == public_codes | {"request_validation_error", "http_error", "internal_server_error"}
    for path, methods in schema["paths"].items():
        if path.startswith("/api/v1/"):
            for operation in methods.values():
                if "422" in operation["responses"]:
                    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
                        "$ref": "#/components/schemas/ErrorResponse"
                    }


def test_openapi_responses_are_specific_to_operations() -> None:
    paths = create_app().openapi()["paths"]
    assert "402" not in paths["/api/v1/auth/login"]["post"]["responses"]
    assert "401" not in paths["/api/v1/auth/logout"]["post"]["responses"]
    assert "413" not in paths["/api/v1/me"]["get"]["responses"]
    assert "415" not in paths["/api/v1/me"]["get"]["responses"]
    assert "402" in paths["/api/v1/documents/{document_id}/generate"]["post"]["responses"]


def test_document_error_code_is_limited_to_document_error_enum() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    error_code = schemas["DocumentOut"]["properties"]["error_code"]
    assert {"$ref": "#/components/schemas/DocumentErrorCode"} in error_code["anyOf"]
    assert set(schemas["DocumentErrorCode"]["enum"]) == {
        "parse_failed",
        "gdocs_not_public",
        "gdocs_import_failed",
        "too_many_pages",
        "empty_document",
        "enqueue_failed",
    }


@pytest.mark.parametrize("cookie", [None, "expired-or-invalid"])
def test_logout_clears_cookie_without_authentication(cookie: str | None) -> None:
    with TestClient(create_app()) as client:
        if cookie is not None:
            client.cookies.set("grasp_session", cookie)
        response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "max-age=0" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/documents"),
        ("POST", "/api/v1/documents/import"),
        ("GET", "/api/v1/documents/00000000-0000-0000-0000-000000000000"),
        ("GET", "/api/v1/documents/00000000-0000-0000-0000-000000000000/topics"),
        ("POST", "/api/v1/documents/00000000-0000-0000-0000-000000000000/plan"),
        ("POST", "/api/v1/documents/00000000-0000-0000-0000-000000000000/generate"),
        ("GET", "/api/v1/parts/00000000-0000-0000-0000-000000000000"),
        ("POST", "/api/v1/quiz-attempts"),
        ("POST", "/api/v1/materials/share"),
        ("POST", "/api/v1/widgets/00000000-0000-0000-0000-000000000000/reports"),
        ("GET", "/api/v1/me"),
        ("PATCH", "/api/v1/me"),
        ("GET", "/api/v1/me/quota"),
        ("GET", "/api/v1/me/materials"),
    ],
)
def test_protected_endpoints_require_authentication(method: str, path: str) -> None:
    with TestClient(create_app()) as client:
        response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["error_code"] == "not_authenticated"
