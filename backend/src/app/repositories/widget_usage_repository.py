"""Repository of widget usages."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import UsageStatus, WidgetUsageDraft, WidgetUsageRecord
from src.app.exceptions.widgets import WidgetUsageDuplicateError
from src.app.interfaces.repositories.widgets import WidgetUsageRepositoryProtocol
from src.app.models.widget_usage import WidgetUsage


class WidgetUsageRepository(WidgetUsageRepositoryProtocol):
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

    async def add_many(self, part_id: UUID, usages: Sequence[WidgetUsageDraft]) -> list[WidgetUsageRecord]:
        """Insert new usages; only flush, never commit."""
        created = [
            WidgetUsage(
                part_id=part_id,
                widget_id=draft.widget_id,
                directive_ref=draft.directive_ref,
                params=draft.params,
                position=draft.position,
                status=draft.status.value,
            )
            for draft in usages
        ]
        self._session.add_all(created)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise WidgetUsageDuplicateError from exc
        return [self._to_record(row) for row in created]

    async def set_status(self, usage_id: UUID, status: UsageStatus) -> None:
        row = await self._session.get(WidgetUsage, usage_id)
        if row is not None:
            row.status = status.value
            await self._session.flush()
