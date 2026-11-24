"""In-memory fake of UserRepository."""

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from src.app.contracts.users import UserRecord
from src.app.contracts.users.profile_update import ProfileUpdate
from src.app.exceptions.users import UserAlreadyExistsError
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from tests.support.time import now


class FakeUserRepository(UserRepositoryProtocol):
    """Dict-backed stub mirroring UserRepository API."""

    def __init__(self) -> None:
        self._users: dict[UUID, UserRecord] = {}

    async def get(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)

    async def get_locale_by_document(self, document_id: UUID) -> str:
        user = next(iter(self._users.values()), None)
        return user.locale if user is not None else "ru"

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
        # mirrors the citext unique constraint of the users table
        if await self.get_by_email(email) is not None:
            raise UserAlreadyExistsError
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

    async def save_last_answers(self, user_id: UUID, answers: dict[str, Any]) -> None:
        user = self._users[user_id]
        self._users[user_id] = replace(user, profile={**user.profile, "last_answers": answers})

    async def update_profile_fields(self, user_id: UUID, fields: ProfileUpdate) -> UserRecord | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        allowed = {
            key: getattr(fields, key)
            for key in ("display_name", "locale", "notify_email")
            if key in fields.provided and (key == "display_name" or getattr(fields, key) is not None)
        }
        updated = replace(user, **allowed)
        self._users[user_id] = updated
        return updated
