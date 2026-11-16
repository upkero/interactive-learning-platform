"""Idempotent reporting of widgets in accessible parts."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.widgets import ReportReason
from src.app.core.settings.reports import ReportsSettings
from src.app.exceptions.widgets import WidgetNotFoundError
from src.app.interfaces.repositories.widgets import (
    ReportRepositoryProtocol,
    WidgetRepositoryProtocol,
    WidgetUsageRepositoryProtocol,
)
from src.app.observability.decision_log import DecisionLog


class ReportService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        reports: Callable[[AsyncSession], ReportRepositoryProtocol],
        usages: Callable[[AsyncSession], WidgetUsageRepositoryProtocol],
        widgets: Callable[[AsyncSession], WidgetRepositoryProtocol],
        decision_log: DecisionLog,
        settings: ReportsSettings,
    ) -> None:
        self._session_factory = session_factory
        self._reports = reports
        self._usages = usages
        self._widgets = widgets
        self._decision_log = decision_log
        self._settings = settings

    async def report(
        self,
        *,
        user_id: UUID,
        widget_id: UUID,
        part_id: UUID | None,
        reason: ReportReason,
        comment: str | None,
    ) -> None:
        threshold = self._settings.exclude_threshold
        excluded = False
        count = 0
        async with self._session_factory() as session, session.begin():
            accessible_part = await self._usages(session).find_accessible_part(widget_id, user_id, part_id)
            if accessible_part is None:
                raise WidgetNotFoundError()
            if await self._widgets(session).lock_for_update(widget_id) is None:
                raise WidgetNotFoundError()
            await self._reports(session).create_if_not_exists(
                widget_id=widget_id,
                user_id=user_id,
                part_id=accessible_part,
                reason=reason,
                comment=comment,
            )
            count = await self._reports(session).count_by_widget(widget_id)
            if count >= threshold:
                excluded = await self._widgets(session).exclude_if_active(widget_id)
        if excluded:
            self._decision_log.widget_excluded(widget_id=str(widget_id), reporters=count, threshold=threshold)


__all__ = ["ReportService"]
