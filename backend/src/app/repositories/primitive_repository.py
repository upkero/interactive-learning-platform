"""Repository of primitives catalog."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.widgets import PrimitiveRecord
from src.app.models.primitive import Primitive


class PrimitiveRepository:
    """Sync of the @grasp/primitives catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: Primitive) -> PrimitiveRecord:
        return PrimitiveRecord(
            id=row.id,
            version=row.version,
            description=row.description,
            modes=list(row.modes),
            params_schema=dict(row.params_schema),
            updated_at=row.updated_at,
        )

    async def get(self, primitive_id: str) -> PrimitiveRecord | None:
        row = await self._session.get(Primitive, primitive_id)
        return self._to_record(row) if row is not None else None

    async def list_all(self) -> list[PrimitiveRecord]:
        rows = await self._session.scalars(select(Primitive).order_by(Primitive.id))
        return [self._to_record(row) for row in rows.all()]

    async def upsert(
        self,
        *,
        primitive_id: str,
        version: str,
        description: str,
        modes: list[str],
        params_schema: dict[str, Any],
    ) -> PrimitiveRecord:
        row = await self._session.get(Primitive, primitive_id)
        if row is not None:
            row.version = version
            row.description = description
            row.modes = modes
            row.params_schema = params_schema
        else:
            row = Primitive(
                id=primitive_id,
                version=version,
                description=description,
                modes=modes,
                params_schema=params_schema,
            )
            self._session.add(row)
        await self._session.flush()
        return self._to_record(row)
