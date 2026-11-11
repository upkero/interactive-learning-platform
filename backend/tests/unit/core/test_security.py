"""Unit tests 1.4.2: password hashing and session JWT helpers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from src.app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)
from src.app.core.settings.auth import get_auth_settings
from src.app.exceptions.auth import NotAuthenticatedError

pytestmark = pytest.mark.unit


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct horse battery")
    # argon2: every hash is salted, storage never holds the plain password
    assert password_hash != "correct horse battery"
    assert password_hash.startswith("$argon2")
    assert hash_password("correct horse battery") != password_hash
    assert verify_password("correct horse battery", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_session_token_round_trip() -> None:
    user_id = uuid4()
    token = create_session_token(user_id)
    assert decode_session_token(token) == user_id


def test_expired_token_is_not_authenticated() -> None:
    user_id = uuid4()
    settings = get_auth_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": str(user_id), "iat": now - timedelta(days=8), "exp": now - timedelta(seconds=1)},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(NotAuthenticatedError):
        decode_session_token(expired)


def test_tampered_token_is_not_authenticated() -> None:
    token = create_session_token(uuid4())
    with pytest.raises(NotAuthenticatedError):
        decode_session_token(token + "x")


def test_token_signed_with_another_secret_is_not_authenticated() -> None:
    forged = jwt.encode({"sub": str(uuid4())}, "not-the-real-secret-not-the-real-secret", algorithm="HS256")
    with pytest.raises(NotAuthenticatedError):
        decode_session_token(forged)


def test_token_without_sub_is_not_authenticated() -> None:
    forged = jwt.encode(
        {"iat": datetime.now(UTC)}, get_auth_settings().jwt_secret.get_secret_value(), algorithm="HS256"
    )
    with pytest.raises(NotAuthenticatedError):
        decode_session_token(forged)
