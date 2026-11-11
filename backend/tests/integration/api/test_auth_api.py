"""Integration tests 1.4.2: the auth flow against the real API and Postgres.

Acceptance criteria (story): registering the same email in any case
gives 409 ``email_taken``; a wrong password gives 401
``invalid_credentials``; an expired token gives 401
``not_authenticated``; the 11th login attempt in a minute gives 429.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.core.settings.auth import get_auth_settings
from src.main import create_app

pytestmark = pytest.mark.integration

COOKIE = get_auth_settings().session_cookie_name


@pytest.fixture
def client() -> Iterator[TestClient]:
    # in-memory rate limit storage is shared between tests
    limiter.reset()
    # context manager runs the lifespan: the real DI container and engine
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def _register_payload(email: str | None = None) -> dict[str, str]:
    # example.com is fine for email-validator, .test is a reserved TLD it rejects
    return {"email": email or f"user-{uuid4()}@example.com", "password": "long-enough-password"}


def test_register_creates_user_and_sets_the_session_cookie(client: TestClient) -> None:
    payload = _register_payload()
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["id"] and body["locale"] == "ru"
    set_cookie = response.headers["set-cookie"]
    assert COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_register_same_email_in_any_case_is_409_email_taken(client: TestClient) -> None:
    email = _register_payload()["email"]
    assert client.post("/api/v1/auth/register", json=_register_payload(email)).status_code == 201

    response = client.post("/api/v1/auth/register", json=_register_payload(email.upper()))
    assert response.status_code == 409
    assert response.json()["error_code"] == "email_taken"


def test_register_with_a_short_password_is_422(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": _register_payload()["email"], "password": "short"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "request_validation_error"


def test_login_wrong_password_and_unknown_email_fail_identically(client: TestClient) -> None:
    email = _register_payload()["email"]
    assert client.post("/api/v1/auth/register", json=_register_payload(email)).status_code == 201

    wrong_password = client.post("/api/v1/auth/login", json={"email": email, "password": "not-the-password"})
    unknown_email = client.post("/api/v1/auth/login", json=_register_payload(f"ghost-{uuid4()}@example.com"))
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert (
        wrong_password.json()
        == unknown_email.json()
        == {
            "detail": "Invalid email or password.",
            "error_code": "invalid_credentials",
        }
    )


def test_login_returns_a_working_session(client: TestClient) -> None:
    payload = _register_payload()
    client.post("/api/v1/auth/register", json=payload)

    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    assert response.headers["set-cookie"].lower().startswith(COOKIE.lower())

    # the cookie from the client jar must authenticate the protected logout
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"status": "ok"}


def test_logout_drops_the_cookie(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=_register_payload())

    response = client.post("/api/v1/auth/logout")
    deleted = response.headers["set-cookie"].lower()
    assert COOKIE in deleted
    assert "max-age=0" in deleted or '="";' in deleted


def test_logout_without_a_cookie_is_401_not_authenticated(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error_code"] == "not_authenticated"


def test_expired_token_is_401_not_authenticated(client: TestClient) -> None:
    settings = get_auth_settings()
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {"sub": str(uuid4()), "iat": now - timedelta(days=8), "exp": now - timedelta(seconds=1)},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    client.cookies.set(COOKIE, expired_token)

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error_code"] == "not_authenticated"


def test_token_of_an_unknown_user_is_401_not_authenticated(client: TestClient) -> None:
    from src.app.core.security import create_session_token

    client.cookies.set(COOKIE, create_session_token(uuid4()))

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error_code"] == "not_authenticated"


def test_the_11th_login_in_a_minute_is_429(client: TestClient) -> None:
    payload = {"email": f"burst-{uuid4()}@example.com", "password": "long-enough-password"}
    statuses = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(11)]

    # unknown email: the first ten fail as invalid_credentials, the 11th
    # is cut off by the limiter before the service runs
    assert all(status == 401 for status in statuses[:10])
    assert statuses[10] == 429
    rate_limited = client.post("/api/v1/auth/login", json=payload)
    assert rate_limited.json()["error_code"] == "rate_limited"
