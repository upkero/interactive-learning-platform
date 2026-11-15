"""Read and update the current user's profile."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.users import UserRecord
from src.app.contracts.users.profile_update import ProfileUpdate
from src.app.exceptions.auth import NotAuthenticatedError
from src.app.interfaces.repositories.users import UserRepositoryProtocol


class ProfileService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
    ) -> None:
        self._session_factory = session_factory
        self._users = users

    async def update(self, user_id: UUID, fields: ProfileUpdate) -> UserRecord:
        async with self._session_factory() as session, session.begin():
            user = await self._users(session).update_profile_fields(user_id, fields)
            if user is None:
                raise NotAuthenticatedError()
        return user
