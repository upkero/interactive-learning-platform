"""Read-only quota endpoint service (``GET /me/quota``)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.quota import QuotaState
from src.app.services.quota.quota_ledger import QuotaLedger


class QuotaService:
    """Opens a request-scoped session for the stateless quota ledger."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        ledger: QuotaLedger,
    ) -> None:
        self._session_factory = session_factory
        self._ledger = ledger

    async def current(self, user_id: UUID) -> QuotaState:
        async with self._session_factory() as session:
            return await self._ledger.available(session, user_id=user_id)


__all__ = ["QuotaService"]
