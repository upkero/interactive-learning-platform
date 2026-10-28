"""Repository of widget descriptions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import WidgetDescriptionRecord
from src.app.exceptions.widgets import WidgetsIntegrityError
from src.app.interfaces.repositories.widgets import WidgetDescriptionRepositoryProtocol
from src.app.models.widget_description import WidgetDescription


class WidgetDescriptionRepository(WidgetDescriptionRepositoryProtocol):
    """Access to the widget_descriptions table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: WidgetDescription) -> WidgetDescriptionRecord:
        return WidgetDescriptionRecord(
            id=row.id,
            widget_id=row.widget_id,
            text=row.text,
            is_paraphrase=row.is_paraphrase,
            embedding=list(row.embedding),
            created_at=row.created_at,
        )

    async def create(
        self,
        *,
        widget_id: UUID,
        text: str,
        is_paraphrase: bool,
        embedding: list[float],
    ) -> WidgetDescriptionRecord:
        row = WidgetDescription(
            widget_id=widget_id,
            text=text,
            is_paraphrase=is_paraphrase,
            embedding=embedding,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise WidgetsIntegrityError from exc
        return self._to_record(row)

    async def list_by_widget(self, widget_id: UUID) -> list[WidgetDescriptionRecord]:
        rows = await self._session.scalars(select(WidgetDescription).where(WidgetDescription.widget_id == widget_id))
        return [self._to_record(row) for row in rows.all()]
