"""Registration, login and logout (story 1.4.2).

CSRF tokens are deliberately not used: the session cookie is
``SameSite=Lax``, so cross-site POSTs never carry it (story ADR).
Register and login are capped at 10 attempts per minute per IP; the 429
answers the unified error format (story 1.4.1).
"""

from fastapi import APIRouter, Request, Response

from src.app.api.v1.dependencies.auth import AuthServiceDep, CurrentUserDep
from src.app.api.v1.middleware.rate_limit import limiter
from src.app.contracts.users import UserRecord
from src.app.core.security import create_session_token
from src.app.core.settings.auth import get_auth_settings
from src.app.schemas.auth import AuthUserOut, LoginRequest, RegisterRequest, SessionStatusOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_auth_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _drop_session_cookie(response: Response) -> None:
    response.delete_cookie(key=get_auth_settings().session_cookie_name, path="/")


def _to_auth_user_out(user: UserRecord) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        created_at=user.created_at,
    )


@router.post("/register", status_code=201, response_model=AuthUserOut, operation_id="auth_register")
@limiter.limit("10/minute")
async def register(
    request: Request, response: Response, payload: RegisterRequest, service: AuthServiceDep
) -> AuthUserOut:
    user = await service.register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    _set_session_cookie(response, create_session_token(user.id))
    return _to_auth_user_out(user)


@router.post("/login", response_model=AuthUserOut, operation_id="auth_login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, payload: LoginRequest, service: AuthServiceDep) -> AuthUserOut:
    user = await service.login(email=payload.email, password=payload.password)
    _set_session_cookie(response, create_session_token(user.id))
    return _to_auth_user_out(user)


@router.post("/logout", response_model=SessionStatusOut, operation_id="auth_logout")
async def logout(response: Response, _user: CurrentUserDep) -> SessionStatusOut:
    _drop_session_cookie(response)
    return SessionStatusOut(status="ok")
