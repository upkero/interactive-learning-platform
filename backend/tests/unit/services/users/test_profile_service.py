"""Profile updates preserve fields that were not provided."""

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.users.profile_update import ProfileUpdate
from src.app.exceptions.auth import NotAuthenticatedError
from src.app.services.users.profile_service import ProfileService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


async def test_patch_changes_only_provided_field() -> None:
    users, session = FakeUserRepository(), FakeSession()
    original = await users.create(email="profile@example.com", password_hash="hash", display_name="Name")
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = ProfileService(session_factory=factory, users=lambda _: users)
    result = await service.update(original.id, ProfileUpdate(provided=frozenset({"notify_email"}), notify_email=False))
    assert result.notify_email is False
    assert result.email == original.email and result.display_name == original.display_name
    assert result.locale == original.locale and result.profile == original.profile
    assert session.committed == 1 and session.rolled_back == 0


async def test_unknown_user_rolls_back() -> None:
    session, users = FakeSession(), FakeUserRepository()
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = ProfileService(session_factory=factory, users=lambda _: users)
    with pytest.raises(NotAuthenticatedError):
        await service.update(uuid4(), ProfileUpdate(provided=frozenset()))
    assert session.committed == 0 and session.rolled_back == 1
