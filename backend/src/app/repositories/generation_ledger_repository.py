"""Repository of the generation ledger."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.quota import LedgerEntry, LedgerOp
from src.app.exceptions.quota import LedgerEntryDuplicateError, QuotaIntegrityError
from src.app.interfaces.repositories.quota import GenerationLedgerRepositoryProtocol
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories._errors import constraint_name

GENERATION_LEDGER_UNIQUE: str = "uq_generation_ledger_part_id_op"


class GenerationLedgerRepository(GenerationLedgerRepositoryProtocol):
    """Append-only operations over the generation_ledger table.

    Delta semantics follow the quota ADR (story 1.6); period computation
    and business rules live in services, not here.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: GenerationLedger) -> LedgerEntry:
        return LedgerEntry(
            id=row.id,
            user_id=row.user_id,
            document_id=row.document_id,
            part_id=row.part_id,
            op=LedgerOp(row.op),
            delta=row.delta,
            period_start=row.period_start,
            created_at=row.created_at,
        )

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
        row = GenerationLedger(
            user_id=user_id,
            document_id=document_id,
            part_id=part_id,
            op=op.value,
            delta=delta,
            period_start=period_start,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Only the (part_id, op) uniqueness is a benign duplicate (the
            # watchdog racing the generation task); foreign keys must not
            # be swallowed as "already done" or quota would leak.
            if constraint_name(exc) == GENERATION_LEDGER_UNIQUE:
                raise LedgerEntryDuplicateError from exc
            raise QuotaIntegrityError from exc
        return self._to_record(row)

    async def sum_delta(self, user_id: UUID, period_start: date) -> int:
        """Sum deltas of all operations of the user since ``period_start``."""
        stmt = select(func.coalesce(func.sum(GenerationLedger.delta), 0)).where(
            GenerationLedger.user_id == user_id,
            GenerationLedger.period_start >= period_start,
        )
        return int((await self._session.scalars(stmt)).one())
