"""Repository of images."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.exceptions.documents import DocumentsIntegrityError
from src.app.interfaces.repositories.documents import ImageRepositoryProtocol
from src.app.models.image import Image


class ImageRepository(ImageRepositoryProtocol):
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

    async def add_many(self, document_id: UUID, images: Sequence[ImageDraft]) -> list[ImageRecord]:
        """Insert new images; only flush, never commit."""
        created = [
            Image(
                document_id=document_id,
                object_key=draft.object_key,
                page=draft.page,
                width=draft.width,
                height=draft.height,
                caption=draft.caption,
                description=draft.description,
                topic_id=draft.topic_id,
            )
            for draft in images
        ]
        self._session.add_all(created)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise DocumentsIntegrityError from exc
        return [self._to_record(row) for row in created]
