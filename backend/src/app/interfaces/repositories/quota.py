"""Protocols of the quota ledger repositories."""

from datetime import date
from typing import Protocol
from uuid import UUID

from src.app.contracts.quota import LedgerEntry, LedgerOp


class GenerationLedgerRepositoryProtocol(Protocol):
    """Public API of the generation_ledger table access."""

    async def add(
        self,
        *,
        user_id: UUID,
        op: LedgerOp,
        delta: int,
        period_start: date,
        document_id: UUID | None = None,
        part_id: UUID | None = None,
    ) -> LedgerEntry: ...

    async def sum_delta(self, user_id: UUID, period_start: date) -> int: ...
