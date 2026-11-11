"""Unit tests 1.4.2: AuthService over the in-memory user repository fake."""

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.users import UserRecord
from src.app.exceptions.auth import EmailTakenError, InvalidCredentialsError
from src.app.exceptions.users import UserAlreadyExistsError
from src.app.services.auth.auth_service import AuthService
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


class _FakeSession:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True


def _service() -> tuple[AuthService, FakeUserRepository, _FakeSession]:
    session = _FakeSession()
    users = FakeUserRepository()
    return AuthService(session=cast(AsyncSession, session), users=users), users, session


async def test_register_normalizes_email_and_hashes_password() -> None:
    service, users, session = _service()

    user = await service.register(email="  Alice@Example.COM ", password="long-enough-password")

    stored = await users.get_by_email("alice@example.com")
    assert stored is not None and stored.id == user.id
    # citext is case-insensitive too, but the stored value is lowercase
    assert user.email == "alice@example.com"
    assert user.password_hash.startswith("$argon2")
    assert user.password_hash != "long-enough-password"
    assert getattr(session, "committed", False) is True


async def test_register_same_email_in_any_case_is_email_taken() -> None:
    service, _users, _session = _service()
    await service.register(email="alice@example.com", password="long-enough-password")

    with pytest.raises(EmailTakenError):
        await service.register(email="ALICE@example.com", password="long-enough-password")


async def test_login_success() -> None:
    service, _users, _session = _service()
    await service.register(email="bob@example.com", password="long-enough-password")

    user = await service.login(email="Bob@Example.com", password="long-enough-password")
    assert user.email == "bob@example.com"


async def test_unknown_email_and_wrong_password_fail_identically() -> None:
    service, _users, _session = _service()
    await service.register(email="bob@example.com", password="long-enough-password")

    # the acceptance criterion: both failures raise the same exception —
    # the client must not learn whether the email is registered
    with pytest.raises(InvalidCredentialsError):
        await service.login(email="ghost@example.com", password="long-enough-password")
    with pytest.raises(InvalidCredentialsError):
        await service.login(email="bob@example.com", password="wrong-password-123")


async def test_repository_conflict_maps_to_email_taken() -> None:
    class ConflictingRepository(FakeUserRepository):
        async def create(
            self,
            *,
            email: str,
            password_hash: str,
            display_name: str | None = None,
            locale: str = "ru",
            monthly_limit: int = 20,
        ) -> UserRecord:
            raise UserAlreadyExistsError

    users = ConflictingRepository()
    service = AuthService(session=cast(AsyncSession, _FakeSession()), users=users)
    with pytest.raises(EmailTakenError):
        await service.register(email="x@example.com", password="long-enough-password")
