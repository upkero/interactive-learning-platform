"""Registration, login and session issuing (story 1.4.2).

The service owns the transaction: repositories only flush, the commit
happens here after the domain work succeeded. Passwords are argon2,
emails are normalized to lowercase, and login never reveals whether the
email exists — unknown email and wrong password answer the same
``invalid_credentials``.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.users import UserRecord
from src.app.core.security import create_session_token, hash_password, verify_password
from src.app.exceptions.auth import EmailTakenError, InvalidCredentialsError
from src.app.exceptions.users import UserAlreadyExistsError
from src.app.interfaces.repositories.users import UserRepositoryProtocol


class AuthService:
    def __init__(self, *, session: AsyncSession, users: UserRepositoryProtocol) -> None:
        self._session = session
        self._users = users

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> UserRecord:
        try:
            user = await self._users.create(
                email=email.strip().lower(),
                password_hash=hash_password(password),
                display_name=display_name,
            )
        except UserAlreadyExistsError as exc:
            # the API contract speaks in email_taken (409), the repository
            # stays generic about the users table
            raise EmailTakenError from exc
        await self._session.commit()
        return user

    async def login(self, *, email: str, password: str) -> UserRecord:
        user = await self._users.get_by_email(email.strip().lower())
        # one branch for both failures: no timing/wording difference that
        # would let a client enumerate registered emails
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        return user

    async def issue_session_token(self, user_id: UUID) -> str:
        return create_session_token(user_id)
