"""Password hashing (argon2) and session JWT helpers (story 1.4.2).

The JWT carries ``sub`` (user id), ``iat`` and ``exp`` (7 days) and is
signed HS256 with ``AUTH_JWT_SECRET``. Token failures surface as
``NotAuthenticatedError`` so the API answers the unified error format.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from src.app.core.settings.auth import get_auth_settings
from src.app.exceptions.auth import NotAuthenticatedError

_ALGORITHM = "HS256"
_HASHER = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Argon2 hash for storage in ``users.password_hash``."""
    return _HASHER.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _HASHER.verify(plain_password, password_hash)


def create_session_token(user_id: UUID) -> str:
    settings = get_auth_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=settings.session_ttl_seconds),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=_ALGORITHM,
    )


def decode_session_token(token: str) -> UUID:
    """Validate signature and expiry, return the user id from ``sub``."""
    settings = get_auth_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise NotAuthenticatedError("Session token is invalid or expired.") from exc
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise NotAuthenticatedError("Session token is invalid or expired.") from exc
