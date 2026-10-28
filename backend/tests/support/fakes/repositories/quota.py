"""In-memory fakes of the quota ledger repositories."""

from datetime import date
from uuid import UUID

from src.app.contracts.quota import LedgerEntry, LedgerOp
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from tests.support.time import now


class FakeGenerationLedgerRepository(GenerationLedgerRepositoryProtocol):
    """List-backed stub mirroring GenerationLedgerRepository API."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._next_id = 1

    async def add(
        self,
        *,
        user_id: UUID,
        op: LedgerOp,
        delta: int,
        period_start: date,
        document_id: UUID | None = None,
        part_id: UUID | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=self._next_id,
            user_id=user_id,
            document_id=document_id,
            part_id=part_id,
            op=op,
            delta=delta,
            period_start=period_start,
            created_at=now(),
        )
        self._next_id += 1
        self._entries.append(entry)
        return entry

    async def sum_delta(self, user_id: UUID, period_start: date) -> int:
        return sum(e.delta for e in self._entries if e.user_id == user_id and e.period_start >= period_start)
