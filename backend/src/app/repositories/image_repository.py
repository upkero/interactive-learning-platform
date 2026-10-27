"""Repository of images."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.image_record import ImageRecord
from src.app.models.image import Image


class ImageRepository:
    """CRUD-style access to the images table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: Image) -> ImageRecord:
        return ImageRecord(
            id=row.id,
            document_id=row.document_id,
            object_key=row.object_key,
            page=row.page,
            width=row.width,
            height=row.height,
            caption=row.caption,
            description=row.description,
            topic_id=row.topic_id,
        )

    async def get(self, image_id: UUID) -> ImageRecord | None:
        row = await self._session.get(Image, image_id)
        return self._to_record(row) if row is not None else None

    async def list_by_document(self, document_id: UUID) -> list[ImageRecord]:
        rows = await self._session.scalars(select(Image).where(Image.document_id == document_id))
        return [self._to_record(row) for row in rows.all()]

    async def add_many(
        self,
        document_id: UUID,
        rows: list[dict[str, object]],
    ) -> list[ImageRecord]:
        created = [Image(document_id=document_id, **row) for row in rows]
        self._session.add_all(created)
        await self._session.flush()
        return [self._to_record(row) for row in created]
