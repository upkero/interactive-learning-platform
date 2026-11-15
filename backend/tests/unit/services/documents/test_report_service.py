"""Widget reporting requires access and is idempotent."""

from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason, UsageStatus, WidgetKind, WidgetStatus, WidgetUsageDraft
from src.app.core.decision_log import DecisionLog
from src.app.exceptions.widgets import WidgetNotFoundError
from src.app.services.reports.report_service import ReportService
from src.app.services.widgets.widget_search import WidgetSearch
from tests.support.fakes.repositories.widgets import (
    FakeReportRepository,
    FakeWidgetRepository,
    FakeWidgetUsageRepository,
)

pytestmark = pytest.mark.unit


async def test_reports_require_access_and_are_idempotent() -> None:
    user, outsider, part = uuid4(), uuid4(), uuid4()
    usages, reports, widgets = FakeWidgetUsageRepository(), FakeReportRepository(), FakeWidgetRepository()
    widget = (await widgets.create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="x")).id
    await usages.add_many(
        part, [WidgetUsageDraft(widget_id=widget, directive_ref="x", position=0, params=None, status=UsageStatus.READY)]
    )
    usages.accessible_parts.add((user, part))
    session = AsyncMock(spec=AsyncSession)
    decisions = Mock(spec=DecisionLog)
    service = ReportService(
        session=cast(AsyncSession, session),
        reports=reports,
        usages=usages,
        widgets=widgets,
        decision_log=decisions,
    )
    with pytest.raises(WidgetNotFoundError):
        await service.report(user_id=outsider, widget_id=widget, part_id=part, reason=ReportReason.UGLY, comment=None)
    await service.report(user_id=user, widget_id=widget, part_id=part, reason=ReportReason.UGLY, comment="bad")
    await service.report(user_id=user, widget_id=widget, part_id=part, reason=ReportReason.OTHER, comment="ignored")
    record = await reports.get_by_widget_and_user(widget, user)
    assert record is not None and record.reason is ReportReason.UGLY and record.comment == "bad"
    assert len(reports._reports) == 1
    decisions.widget_excluded.assert_not_called()


async def test_third_distinct_report_excludes_widget_after_commit() -> None:
    users, part = [uuid4() for _ in range(3)], uuid4()
    usages, reports, widgets = FakeWidgetUsageRepository(), FakeReportRepository(), FakeWidgetRepository()
    widget = (await widgets.create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="x")).id
    await usages.add_many(
        part, [WidgetUsageDraft(widget_id=widget, directive_ref="x", position=0, params=None, status=UsageStatus.READY)]
    )
    usages.accessible_parts.update((user, part) for user in users)
    session = AsyncMock(spec=AsyncSession)
    decisions = Mock(spec=DecisionLog)
    decisions.widget_excluded.side_effect = lambda **kwargs: session.commit.assert_awaited()
    service = ReportService(
        session=cast(AsyncSession, session),
        reports=reports,
        usages=usages,
        widgets=widgets,
        decision_log=decisions,
    )
    search = WidgetSearch(widgets)
    assert len(await search.search([1.0])) == 1
    for user in users:
        await service.report(user_id=user, widget_id=widget, part_id=part, reason=ReportReason.WRONG, comment=None)
    result = await widgets.get(widget)
    assert result is not None and result.status is WidgetStatus.EXCLUDED
    assert await search.search([1.0]) == []
    decisions.widget_excluded.assert_called_once_with(widget_id=widget, reporters=3, threshold=3)
