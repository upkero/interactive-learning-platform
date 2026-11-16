"""Quota accounting over the generation ledger (story 1.6).

The balance is never stored on the user row: it is derived from the
deltas of the append-only ``generation_ledger`` table,
``available = monthly_limit + sum(delta)`` over the current period.

The ledger never owns a transaction (story 1.6): every method takes the
caller's ``session``, and every write starts with the ``users`` row lock
so parallel requests serialize on one quota balance.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.quota import LedgerOp
from src.app.core.clock import Clock
from src.app.exceptions.quota import QuotaExceededError
from src.app.exceptions.users import UserNotFoundError
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.services.quota.period import QuotaPeriod, current_period


@dataclass(frozen=True, slots=True)
class QuotaState:
    monthly_limit: int
    available: int
    period: QuotaPeriod


class QuotaLedger:
    """Read/reserve accounting; all writes lock the users row first."""

    def __init__(
        self,
        *,
        users_factory: Callable[[AsyncSession], UserRepositoryProtocol],
        ledger_factory: Callable[[AsyncSession], GenerationLedgerRepositoryProtocol],
        clock: Clock,
    ) -> None:
        self._users_factory = users_factory
        self._ledger_factory = ledger_factory
        self._clock = clock

    async def _state(self, session: AsyncSession, user_id: UUID, monthly_limit: int, anchor: date | None) -> QuotaState:
        period = current_period(self._clock.today(), anchor)
        used = await self._ledger_factory(session).sum_delta(user_id, period.start)
        # deltas: reserve is negative, refund positive (story 1.6.1)
        return QuotaState(monthly_limit=monthly_limit, available=monthly_limit + used, period=period)

    async def available(self, session: AsyncSession, *, user_id: UUID) -> QuotaState:
        """Read-only quota status: limit, remaining balance and period bounds."""
        user = await self._users_factory(session).get(user_id)
        if user is None:
            raise UserNotFoundError()
        return await self._state(session, user.id, user.monthly_limit, user.period_anchor)

    async def reserve(self, session: AsyncSession, *, user_id: UUID, document_id: UUID, parts: int) -> QuotaState:
        """Reserve quota within the caller's transaction and user-row lock."""
        user = await self._users_factory(session).lock_for_update(user_id)
        if user is None:
            raise UserNotFoundError()
        state = await self._state(session, user.id, user.monthly_limit, user.period_anchor)
        if state.available < parts:
            raise QuotaExceededError(extra={"available": state.available, "requested": parts})
        await self._ledger_factory(session).add(
            user_id=user.id,
            document_id=document_id,
            op=LedgerOp.RESERVE,
            delta=-parts,
            period_start=state.period.start,
        )
        return QuotaState(
            monthly_limit=state.monthly_limit,
            available=state.available - parts,
            period=state.period,
        )


__all__ = ["QuotaLedger", "QuotaState"]
