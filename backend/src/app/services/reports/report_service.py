"""Idempotent reporting of widgets in accessible parts."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason
from src.app.core.decision_log import DecisionLog
from src.app.core.settings.reports import get_reports_settings
from src.app.exceptions.widgets import WidgetNotFoundError
from src.app.interfaces.repositories.widgets import (
    ReportRepositoryProtocol,
    WidgetRepositoryProtocol,
    WidgetUsageRepositoryProtocol,
)


class ReportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        reports: ReportRepositoryProtocol,
        usages: WidgetUsageRepositoryProtocol,
        widgets: WidgetRepositoryProtocol,
        decision_log: DecisionLog,
    ) -> None:
        self._session = session
        self._reports = reports
        self._usages = usages
        self._widgets = widgets
        self._decision_log = decision_log

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
        excluded = False
        count = 0
        threshold = get_reports_settings().exclude_threshold
        try:
            if await self._widgets.lock_for_update(widget_id) is None:
                raise WidgetNotFoundError()
            await self._reports.create_if_not_exists(
                widget_id=widget_id,
                user_id=user_id,
                part_id=accessible_part,
                reason=reason,
                comment=comment,
            )
            count = await self._reports.count_by_widget(widget_id)
            if count >= threshold:
                excluded = await self._widgets.exclude_if_active(widget_id)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        if excluded:
            self._decision_log.widget_excluded(widget_id=widget_id, reporters=count, threshold=threshold)
