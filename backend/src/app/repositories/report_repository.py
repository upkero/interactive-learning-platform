"""Repository of widget reports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason, ReportRecord
from src.app.exceptions.widgets import WidgetsIntegrityError
from src.app.interfaces.repositories.widgets import ReportRepositoryProtocol
from src.app.models.report import Report


class ReportRepository(ReportRepositoryProtocol):
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
    ) -> ReportRecord | None:
        """Insert a report unless the same user already reported the widget.

        Uses ``INSERT ... ON CONFLICT DO NOTHING`` so two concurrent requests
        cannot both pass a pre-check; the loser simply gets ``None``.
        """
        stmt = (
            insert(Report)
            .values(
                widget_id=widget_id,
                user_id=user_id,
                part_id=part_id,
                reason=reason.value,
            )
            .on_conflict_do_nothing(index_elements=[Report.widget_id, Report.user_id])
            .returning(Report)
        )
        try:
            row = (await self._session.scalars(stmt)).first()
        except IntegrityError as exc:
            # ON CONFLICT covers only the (widget_id, user_id) duplicate;
            # FK violations of widget/user/part still surface as an error.
            raise WidgetsIntegrityError from exc
        return self._to_record(row) if row is not None else None
