"""Idempotent reporting of widgets in accessible parts."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason
from src.app.exceptions.widgets import WidgetNotFoundError
from src.app.interfaces.repositories.widgets import ReportRepositoryProtocol, WidgetUsageRepositoryProtocol


class ReportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        reports: ReportRepositoryProtocol,
        usages: WidgetUsageRepositoryProtocol,
    ) -> None:
        self._session = session
        self._reports = reports
        self._usages = usages

    async def report(
        self,
        *,
        user_id: UUID,
        widget_id: UUID,
        part_id: UUID | None,
        reason: ReportReason,
        comment: str | None,
    ) -> None:
        accessible_part = await self._usages.find_accessible_part(widget_id, user_id, part_id)
        if accessible_part is None:
            raise WidgetNotFoundError()
        try:
            await self._reports.create_if_not_exists(
                widget_id=widget_id,
                user_id=user_id,
                part_id=accessible_part,
                reason=reason,
                comment=comment,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
