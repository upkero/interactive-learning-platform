"""Repository of widgets."""

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import WidgetKind, WidgetRecord, WidgetStatus
from src.app.exceptions.widgets import WidgetConstraintError, WidgetsIntegrityError
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol
from src.app.models.widget import Widget
from src.app.repositories._errors import constraint_name

WIDGET_KIND_FIELDS_CHECK: str = "ck_widgets_kind_fields"


class WidgetRepository(WidgetRepositoryProtocol):
    """Access to the widgets table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: Widget) -> WidgetRecord:
        return WidgetRecord(
            id=row.id,
            kind=WidgetKind(row.kind),
            primitive_id=row.primitive_id,
            mode=row.mode,
            params=dict(row.params) if row.params is not None else None,
            source_tsx=row.source_tsx,
            compiled_js=row.compiled_js,
            status=WidgetStatus(row.status),
            canonical_id=row.canonical_id,
            version=row.version,
            created_from_part_id=row.created_from_part_id,
            created_at=row.created_at,
        )

    async def get(self, widget_id: UUID) -> WidgetRecord | None:
        row = await self._session.get(Widget, widget_id)
        return self._to_record(row) if row is not None else None

    async def create(
        self,
        *,
        kind: WidgetKind,
        primitive_id: str | None = None,
        mode: str | None = None,
        params: dict[str, Any] | None = None,
        source_tsx: str | None = None,
        compiled_js: str | None = None,
        created_from_part_id: UUID | None = None,
    ) -> WidgetRecord:
        row = Widget(
            kind=kind.value,
            primitive_id=primitive_id,
            mode=mode,
            params=params,
            source_tsx=source_tsx,
            compiled_js=compiled_js,
            created_from_part_id=created_from_part_id,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if constraint_name(exc) == WIDGET_KIND_FIELDS_CHECK:
                raise WidgetConstraintError from exc
            raise WidgetsIntegrityError from exc
        return self._to_record(row)

    async def set_status(self, widget_id: UUID, status: WidgetStatus) -> None:
        row = await self._session.get(Widget, widget_id)
        if row is not None:
            row.status = status.value
            await self._session.flush()
