"""Auth dependencies: service construction and the current user (1.4.2)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.contracts.users import UserRecord
from src.app.core.log_context import bind_log_context
from src.app.core.settings.auth import AuthSettings
from src.app.exceptions.auth import NotAuthenticatedError
from src.app.services.auth.auth_service import AuthService


def get_auth_service(container: ContainerDep) -> AuthService:
    return container.auth_service


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_auth_settings(container: ContainerDep) -> AuthSettings:
    return container.auth_settings


AuthSettingsDep = Annotated[AuthSettings, Depends(get_auth_settings)]


async def get_current_user(
    request: Request, service: AuthServiceDep, settings: AuthSettingsDep
) -> AsyncIterator[UserRecord]:
    """Read the session cookie, validate the JWT and load the user.

    Missing cookie, bad signature, expiry and unknown user all answer
    the same ``not_authenticated`` — nothing about the failure reason
    leaks to the client.
    """
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise NotAuthenticatedError()
    user = await service.get_current_user(token)
    with bind_log_context(user_id=user.id):
        yield user


CurrentUserDep = Annotated[UserRecord, Depends(get_current_user)]
