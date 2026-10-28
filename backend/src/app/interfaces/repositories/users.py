"""Protocols of the users repositories.

Real repositories and their test fakes both conform to these protocols;
mypy strict verifies that the two never drift apart (story 1.2.7).
"""

from typing import Protocol
from uuid import UUID

from src.app.contracts.users import UserRecord


class UserRepositoryProtocol(Protocol):
    """Public API of the users table access."""

    async def get(self, user_id: UUID) -> UserRecord | None: ...

    async def get_by_email(self, email: str) -> UserRecord | None: ...

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None = None,
        locale: str = "ru",
        monthly_limit: int = 20,
    ) -> UserRecord: ...

    async def lock_for_update(self, user_id: UUID) -> UserRecord | None: ...
