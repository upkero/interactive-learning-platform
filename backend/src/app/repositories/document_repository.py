"""Repository of documents."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.statuses import DocumentStatus, SourceType
from src.app.models.document import Document


class DocumentRepository:
    """CRUD-style access to the documents table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: Document) -> DocumentRecord:
        return DocumentRecord(
            id=row.id,
            owner_id=row.owner_id,
            title=row.title,
            source_type=SourceType(row.source_type),
            source_uri=row.source_uri,
            object_key=row.object_key,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            page_count=row.page_count,
            checksum=row.checksum,
            status=DocumentStatus(row.status),
            topic_tree=dict(row.topic_tree) if row.topic_tree is not None else None,
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        row = await self._session.get(Document, document_id)
        return self._to_record(row) if row is not None else None

    async def get_owned(self, document_id: UUID, owner_id: UUID) -> DocumentRecord | None:
        row = (
            await self._session.scalars(
                select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
            )
        ).first()
        return self._to_record(row) if row is not None else None

    async def create(
        self,
        *,
        owner_id: UUID,
        title: str,
        source_type: SourceType,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        checksum: str,
        source_uri: str | None = None,
        page_count: int | None = None,
    ) -> DocumentRecord:
        row = Document(
            owner_id=owner_id,
            title=title,
            source_type=source_type.value,
            object_key=object_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            page_count=page_count,
            checksum=checksum,
            source_uri=source_uri,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def set_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error: str | None = None,
    ) -> None:
        row = await self._session.get(Document, document_id)
        if row is not None:
            row.status = status.value
            row.error = error
            await self._session.flush()

    async def count_active(self, owner_id: UUID) -> int:
        """Count documents still being processed for the monthly quota."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.owner_id == owner_id,
                Document.status.in_(
                    [
                        DocumentStatus.UPLOADED.value,
                        DocumentStatus.PARSING.value,
                        DocumentStatus.PARSED.value,
                        DocumentStatus.GENERATING.value,
                    ]
                ),
            )
        )
        return int((await self._session.scalars(stmt)).one())
