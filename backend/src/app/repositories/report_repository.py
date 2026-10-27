"""Repository of widget reports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason, ReportRecord
from src.app.models.report import Report


class ReportRepository:
    """Access to the reports table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: Report) -> ReportRecord:
        return ReportRecord(
            id=row.id,
            widget_id=row.widget_id,
            user_id=row.user_id,
            part_id=row.part_id,
            reason=ReportReason(row.reason),
            comment=row.comment,
            created_at=row.created_at,
        )

    async def get_by_widget_and_user(self, widget_id: UUID, user_id: UUID) -> ReportRecord | None:
        row = (
            await self._session.scalars(select(Report).where(Report.widget_id == widget_id, Report.user_id == user_id))
        ).first()
        return self._to_record(row) if row is not None else None

    async def create_if_not_exists(
        self,
        *,
        widget_id: UUID,
        user_id: UUID,
        reason: ReportReason,
        part_id: UUID | None = None,
        comment: str | None = None,
    ) -> ReportRecord | None:
        """Insert a report unless the same user already reported the widget."""
        existing = await self.get_by_widget_and_user(widget_id, user_id)
        if existing is not None:
            return None
        row = Report(
            widget_id=widget_id,
            user_id=user_id,
            part_id=part_id,
            reason=reason.value,
            comment=comment,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)
