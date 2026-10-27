"""Repository of users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.users.user_record import UserRecord
from src.app.models.user import User


class UserRepository:
    """CRUD-style access to the users table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: User) -> UserRecord:
        return UserRecord(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            display_name=row.display_name,
            locale=row.locale,
            monthly_limit=row.monthly_limit,
            period_anchor=row.period_anchor,
            profile=dict(row.profile),
            notify_email=row.notify_email,
            created_at=row.created_at,
        )

    async def get(self, user_id: UUID) -> UserRecord | None:
        row = await self._session.get(User, user_id)
        return self._to_record(row) if row is not None else None

    async def get_by_email(self, email: str) -> UserRecord | None:
        row = (await self._session.scalars(select(User).where(User.email == email))).first()
        return self._to_record(row) if row is not None else None

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None = None,
        locale: str = "ru",
        monthly_limit: int = 20,
    ) -> UserRecord:
        row = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            locale=locale,
            monthly_limit=monthly_limit,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def lock_for_update(self, user_id: UUID) -> UserRecord | None:
        """Select a user with ``FOR UPDATE`` inside the caller's transaction."""
        row = (await self._session.scalars(select(User).where(User.id == user_id).with_for_update())).first()
        return self._to_record(row) if row is not None else None
