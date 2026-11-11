"""Auth dependencies: service construction and the current user (1.4.2)."""

from typing import Annotated

from fastapi import Depends, Request

from src.app.api.v1.dependencies.db import DBSessionDep
from src.app.contracts.users import UserRecord
from src.app.core.security import decode_session_token
from src.app.core.settings.auth import get_auth_settings
from src.app.exceptions.auth import NotAuthenticatedError
from src.app.repositories.user_repository import UserRepository
from src.app.services.auth.auth_service import AuthService


def get_auth_service(session: DBSessionDep) -> AuthService:
    """Session-scoped service, built like the other DB-bound services."""
    return AuthService(session=session, users=UserRepository(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(request: Request, session: DBSessionDep) -> UserRecord:
    """Read the session cookie, validate the JWT and load the user.

    Missing cookie, bad signature, expiry and unknown user all answer
    the same ``not_authenticated`` — nothing about the failure reason
    leaks to the client.
    """
    token = request.cookies.get(get_auth_settings().session_cookie_name)
    if not token:
        raise NotAuthenticatedError()
    user_id = decode_session_token(token)
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise NotAuthenticatedError()
    return user


CurrentUserDep = Annotated[UserRecord, Depends(get_current_user)]
