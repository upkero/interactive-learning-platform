"""Registration, login and session issuing (story 1.4.2).

The service owns the transaction; repositories only flush. Passwords are argon2,
emails are normalized to lowercase, and login never reveals whether the
email exists — unknown email and wrong password answer the same
``invalid_credentials``.
"""

import asyncio
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.users import UserRecord
from src.app.core.security import create_session_token, decode_session_token, hash_password, verify_password
from src.app.core.settings.auth import AuthSettings
from src.app.core.settings.quota import QuotaSettings
from src.app.exceptions.auth import EmailTakenError, InvalidCredentialsError, NotAuthenticatedError
from src.app.exceptions.users import UserAlreadyExistsError
from src.app.interfaces.repositories.users import UserRepositoryProtocol

_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$kzFBuvljyJUv1mVjzVIuxw$8+5ueZuhBmI8tB+tnK1YFu4flhopdgzTW+c6CkUoCXA"
)


class AuthService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        settings: AuthSettings,
        quota_settings: QuotaSettings,
    ) -> None:
        self._session_factory = session_factory
        self._users = users
        self._settings = settings
        self._quota_settings = quota_settings

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> UserRecord:
        password_hash = await asyncio.to_thread(hash_password, password)
        try:
            async with self._session_factory() as session, session.begin():
                user = await self._users(session).create(
                    email=email.strip().lower(),
                    password_hash=password_hash,
                    display_name=display_name,
                    monthly_limit=self._quota_settings.default_monthly_limit,
                )
        except UserAlreadyExistsError as exc:
            # the API contract speaks in email_taken (409), the repository
            # stays generic about the users table
            raise EmailTakenError from exc
        return user

    async def login(self, *, email: str, password: str) -> UserRecord:
        async with self._session_factory() as session:
            user = await self._users(session).get_by_email(email.strip().lower())
        # Verify a dummy hash as well for unknown email addresses, avoiding
        # the large timing difference caused by skipping Argon2 entirely.
        valid = await asyncio.to_thread(verify_password, password, user.password_hash if user else _DUMMY_PASSWORD_HASH)
        if user is None or not valid:
            raise InvalidCredentialsError
        return user

    async def issue_session_token(self, user_id: UUID) -> str:
        return create_session_token(user_id, self._settings)

    async def get_current_user(self, token: str) -> UserRecord:
        user_id = decode_session_token(token, self._settings)
        async with self._session_factory() as session:
            user = await self._users(session).get(user_id)
        if user is None:
            raise NotAuthenticatedError()
        return user
