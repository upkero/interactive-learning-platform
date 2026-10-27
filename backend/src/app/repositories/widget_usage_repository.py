"""Repository of widget usages."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import UsageStatus, WidgetUsageRecord
from src.app.models.widget_usage import WidgetUsage


class WidgetUsageRepository:
    """Access to the widget_usages table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: WidgetUsage) -> WidgetUsageRecord:
        return WidgetUsageRecord(
            id=row.id,
            part_id=row.part_id,
            widget_id=row.widget_id,
            directive_ref=row.directive_ref,
            params=dict(row.params) if row.params is not None else None,
            position=row.position,
            status=UsageStatus(row.status),
            created_at=row.created_at,
        )

    async def get(self, usage_id: UUID) -> WidgetUsageRecord | None:
        row = await self._session.get(WidgetUsage, usage_id)
        return self._to_record(row) if row is not None else None

    async def add_many(
        self,
        part_id: UUID,
        rows: list[dict[str, Any]],
    ) -> list[WidgetUsageRecord]:
        created = [WidgetUsage(part_id=part_id, **row) for row in rows]
        self._session.add_all(created)
        await self._session.flush()
        return [self._to_record(row) for row in created]

    async def set_status(self, usage_id: UUID, status: UsageStatus) -> None:
        row = await self._session.get(WidgetUsage, usage_id)
        if row is not None:
            row.status = status.value
            await self._session.flush()
