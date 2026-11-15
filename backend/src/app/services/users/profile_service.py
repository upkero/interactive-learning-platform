"""Read and update the current user's profile."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.users import UserRecord
from src.app.exceptions.auth import NotAuthenticatedError
from src.app.interfaces.repositories.users import UserRepositoryProtocol


class ProfileService:
    def __init__(self, *, session: AsyncSession, users: UserRepositoryProtocol) -> None:
        self._session = session
        self._users = users

    async def update(self, user_id: UUID, fields: dict[str, Any]) -> UserRecord:
        try:
            user = await self._users.update_profile_fields(user_id, fields)
            if user is None:
                raise NotAuthenticatedError()
            await self._session.commit()
            return user
        except Exception:
            await self._session.rollback()
            raise
