"""Repository of widgets."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.solver.widget_candidate import WidgetWithDescription
from src.app.contracts.widgets import WidgetKind, WidgetRecord, WidgetStatus
from src.app.exceptions.widgets import WidgetConstraintError, WidgetsIntegrityError
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol
from src.app.models.widget import Widget
from src.app.models.widget_description import WidgetDescription
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

    async def get_many(self, widget_ids: Sequence[UUID]) -> list[WidgetRecord]:
        """All existing widgets of the ids in one statement; order preserved."""
        if not widget_ids:
            return []
        rows = await self._session.scalars(select(Widget).where(Widget.id.in_(widget_ids)))
        by_id = {row.id: self._to_record(row) for row in rows.all()}
        return [by_id[widget_id] for widget_id in dict.fromkeys(widget_ids) if widget_id in by_id]

    async def lock_for_update(self, widget_id: UUID) -> WidgetRecord | None:
        row = (await self._session.scalars(select(Widget).where(Widget.id == widget_id).with_for_update())).first()
        return self._to_record(row) if row is not None else None

    async def exclude_if_active(self, widget_id: UUID) -> bool:
        stmt = (
            update(Widget)
            .where(Widget.id == widget_id, Widget.status == WidgetStatus.ACTIVE.value)
            .values(status=WidgetStatus.EXCLUDED.value)
            .returning(Widget.id)
        )
        return (await self._session.scalars(stmt)).first() is not None

    async def search_active(self, embedding: list[float], limit: int) -> list[WidgetRecord]:
        distance = WidgetDescription.embedding.cosine_distance(embedding)
        stmt = (
            select(Widget)
            .join(WidgetDescription, WidgetDescription.widget_id == Widget.id)
            .where(Widget.status == WidgetStatus.ACTIVE.value)
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self._session.scalars(stmt)).all()
        return [self._to_record(row) for row in rows]

    async def get_many_with_main_description(
        self,
        widget_ids: Sequence[UUID],
    ) -> dict[UUID, WidgetWithDescription]:
        """Active widgets with their main description in one statement.

        Select one description per widget before loading the widget row.
        Prefer the main description and retain the earliest paraphrase for data
        without a main description.
        """
        if not widget_ids:
            return {}
        description = (
            select(WidgetDescription.widget_id, WidgetDescription.text)
            .where(WidgetDescription.widget_id.in_(widget_ids))
            .ext(distinct_on(WidgetDescription.widget_id))
            .order_by(
                WidgetDescription.widget_id,
                WidgetDescription.is_paraphrase,
                WidgetDescription.created_at,
                WidgetDescription.id,
            )
            .subquery()
        )
        stmt = (
            select(Widget, description.c.text)
            .join(description, description.c.widget_id == Widget.id)
            .where(Widget.status == WidgetStatus.ACTIVE.value)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row.id: WidgetWithDescription(widget=self._to_record(row), description=text) for row, text in rows}

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

    async def create_config(
        self,
        *,
        primitive_id: str,
        mode: str,
        params: dict[str, Any],
        version: int,
        created_from_part_id: UUID,
    ) -> UUID:
        """Create a config widget with version from primitive."""
        row = Widget(
            kind=WidgetKind.CONFIG.value,
            primitive_id=primitive_id,
            mode=mode,
            params=params,
            version=version,
            created_from_part_id=created_from_part_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def list_active_configs(self, primitive_id: str, mode: str) -> list[WidgetRecord]:
        """List active config widgets for a primitive+mode (for deduplication)."""
        stmt = select(Widget).where(
            Widget.kind == WidgetKind.CONFIG.value,
            Widget.primitive_id == primitive_id,
            Widget.mode == mode,
            Widget.status == WidgetStatus.ACTIVE.value,
        )
        rows = (await self._session.scalars(stmt)).all()
        return [self._to_record(row) for row in rows]
