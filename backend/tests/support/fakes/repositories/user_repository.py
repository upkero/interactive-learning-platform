"""In-memory fake of UserRepository."""

from uuid import UUID, uuid4

from src.app.contracts.users.user_record import UserRecord
from tests.support.time import now


class FakeUserRepository:
    """Dict-backed stub mirroring UserRepository API."""

    def __init__(self) -> None:
        self._users: dict[UUID, UserRecord] = {}

    async def get(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> UserRecord | None:
        return next((u for u in self._users.values() if u.email == email), None)

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None = None,
        locale: str = "ru",
        monthly_limit: int = 20,
    ) -> UserRecord:
        record = UserRecord(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            locale=locale,
            monthly_limit=monthly_limit,
            period_anchor=None,
            profile={},
            notify_email=True,
            created_at=now(),
        )
        self._users[record.id] = record
        return record

    async def lock_for_update(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)
