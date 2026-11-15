"""Widget reporting requires access and is idempotent."""

from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import ReportReason, UsageStatus, WidgetUsageDraft
from src.app.exceptions.widgets import WidgetNotFoundError
from src.app.services.reports.report_service import ReportService
from tests.support.fakes.repositories.widgets import FakeReportRepository, FakeWidgetUsageRepository

pytestmark = pytest.mark.unit


async def test_reports_require_access_and_are_idempotent() -> None:
    user, outsider, part, widget = uuid4(), uuid4(), uuid4(), uuid4()
    usages, reports = FakeWidgetUsageRepository(), FakeReportRepository()
    await usages.add_many(
        part, [WidgetUsageDraft(widget_id=widget, directive_ref="x", position=0, params=None, status=UsageStatus.READY)]
    )
    usages.accessible_parts.add((user, part))
    session = AsyncMock(spec=AsyncSession)
    service = ReportService(session=cast(AsyncSession, session), reports=reports, usages=usages)
    with pytest.raises(WidgetNotFoundError):
        await service.report(user_id=outsider, widget_id=widget, part_id=part, reason=ReportReason.UGLY, comment=None)
    await service.report(user_id=user, widget_id=widget, part_id=part, reason=ReportReason.UGLY, comment="bad")
    await service.report(user_id=user, widget_id=widget, part_id=part, reason=ReportReason.OTHER, comment="ignored")
    record = await reports.get_by_widget_and_user(widget, user)
    assert record is not None and record.reason is ReportReason.UGLY and record.comment == "bad"
    assert len(reports._reports) == 1
