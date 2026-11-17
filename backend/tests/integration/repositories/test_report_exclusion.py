"""Distinct concurrent reports exclude a widget and hide it from search."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole, PartDraft, SourceType
from src.app.contracts.widgets import ReportReason, UsageStatus, WidgetKind, WidgetStatus, WidgetUsageDraft
from src.app.core.settings.reports import ReportsSettings
from src.app.observability.decision_log import DecisionLog
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.services.reports.report_service import ReportService
from src.app.services.widgets.widget_search import WidgetSearch
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

pytestmark = pytest.mark.integration


async def test_three_concurrent_reports_exclude_widget(session_factory: async_sessionmaker[AsyncSession]) -> None:
    embedding = [1.0] + [0.0] * 1023
    async with session_factory() as session, session.begin():
        users = UserRepository(session)
        owners = [
            await users.create(email=f"report-{i}@example.com", password_hash="hash", monthly_limit=20)
            for i in range(3)
        ]
        document = await DocumentRepository(session).create(
            owner_id=owners[0].id,
            title="doc",
            source_type=SourceType.UPLOAD,
            object_key="x.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="a" * 64,
        )
        for index, user in enumerate(owners):
            await UserMaterialRepository(session).create(
                user_id=user.id,
                document_id=document.id,
                role=MaterialRole.OWNER if index == 0 else MaterialRole.SHARED,
            )
        part = (
            await DocumentPartRepository(session).add_many(
                document.id,
                [
                    PartDraft(
                        index=0, title="T", topic_ids=[], source_markdown="T", token_count=1, quota_period_start=None
                    )
                ],
            )
        )[0]
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="x")
        await WidgetUsageRepository(session).add_many(
            part.id,
            [
                WidgetUsageDraft(
                    widget_id=widget.id, directive_ref="x", position=0, params=None, status=UsageStatus.READY
                )
            ],
        )
        await WidgetDescriptionRepository(session).create(
            widget_id=widget.id,
            text="test",
            is_paraphrase=False,
            embedding=embedding,
        )
    metrics = RecordingMetricsCollector()
    decisions = DecisionLog(metrics=metrics)

    async def report(user_id: UUID) -> None:
        service = ReportService(
            session_factory=session_factory,
            reports=ReportRepository,
            usages=WidgetUsageRepository,
            widgets=WidgetRepository,
            decision_log=decisions,
            settings=ReportsSettings(exclude_threshold=3),
        )
        await service.report(
            user_id=user_id,
            widget_id=widget.id,
            part_id=part.id,
            reason=ReportReason.WRONG,
            comment=None,
        )

    async with session_factory() as session:
        assert len(await WidgetSearch(WidgetRepository(session)).search(embedding)) == 1
    await asyncio.gather(*(report(user.id) for user in owners))
    async with session_factory() as session:
        result = await WidgetRepository(session).get(widget.id)
        assert result is not None and result.status is WidgetStatus.EXCLUDED
        assert await WidgetSearch(WidgetRepository(session)).search(embedding) == []
        assert await ReportRepository(session).count_by_widget(widget.id) == 3
    assert metrics.counters == ["widgets.excluded"]
