"""Repository of the generation ledger."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.quota import LedgerEntry, LedgerOp
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.user import User


class GenerationLedgerRepository:
    """Append-only operations over the generation_ledger table."""

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
        await self._session.flush()
        return self._to_record(row)

    async def sum_delta(self, user_id: UUID, period_start: date) -> int:
        """Sum deltas of all operations of the user since ``period_start``."""
        stmt = select(func.coalesce(func.sum(GenerationLedger.delta), 0)).where(
            GenerationLedger.user_id == user_id,
            GenerationLedger.period_start >= period_start,
        )
        return int((await self._session.scalars(stmt)).one())

    async def part_owner(self, part_id: UUID) -> UUID | None:
        """Return the owner of the document that owns the part."""
        stmt = (
            select(Document.owner_id)
            .join(DocumentPart, DocumentPart.document_id == Document.id)
            .where(DocumentPart.id == part_id)
        )
        owner = (await self._session.scalars(stmt)).first()
        return owner

    async def reserve_period(self, user_id: UUID) -> date:
        """Compute the period start for a new reserve operation."""
        anchor = (await self._session.scalars(select(User.period_anchor).where(User.id == user_id))).first()
        if anchor is not None:
            return anchor
        # Fallback: first day of the current month
        today = date.today()
        return today.replace(day=1)
