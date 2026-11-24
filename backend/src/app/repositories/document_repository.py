"""Repository of documents."""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, PartStatus, SourceType
from src.app.contracts.documents.topic_node import topic_roots
from src.app.exceptions.documents import DocumentsIntegrityError
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart


class DocumentRepository(DocumentRepositoryProtocol):
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
            topic_tree=topic_roots(row.topic_tree) if row.topic_tree is not None else None,
            error_code=DocumentErrorCode(row.error_code) if row.error_code is not None else None,
            error_detail=row.error_detail,
            created_at=row.created_at,
            updated_at=row.updated_at,
            generation_start_index=row.generation_start_index,
        )

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        row = await self._session.get(Document, document_id)
        return self._to_record(row) if row is not None else None

    async def refresh_status(self, document_id: UUID) -> None:
        """Finish a generation when all parts are terminal; any publication makes it done."""
        stmt = select(Document).where(Document.id == document_id).with_for_update()
        document = (await self._session.scalars(stmt)).first()
        if document is None or document.status != DocumentStatus.GENERATING.value:
            return
        aggregate = select(
            func.bool_and(DocumentPart.status.in_([PartStatus.PUBLISHED.value, PartStatus.FAILED.value])),
            func.bool_or(DocumentPart.status == PartStatus.PUBLISHED.value),
        ).where(DocumentPart.document_id == document_id, DocumentPart.index >= document.generation_start_index)
        all_terminal, _any_published_current = (await self._session.execute(aggregate)).one()
        any_published = await self._session.scalar(
            select(func.bool_or(DocumentPart.status == PartStatus.PUBLISHED.value)).where(
                DocumentPart.document_id == document_id
            )
        )
        if all_terminal:
            document.status = DocumentStatus.DONE.value if any_published else DocumentStatus.FAILED.value
            await self._session.flush()

    async def lock_stale_uploaded(self, *, older_than: timedelta, limit: int) -> list[DocumentRecord]:
        stmt = (
            select(Document)
            .where(Document.status == DocumentStatus.UPLOADED.value, Document.updated_at < func.now() - older_than)
            .order_by(Document.updated_at, Document.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [self._to_record(row) for row in (await self._session.scalars(stmt)).all()]

    async def touch(self, document_id: UUID) -> None:
        await self._session.execute(update(Document).where(Document.id == document_id).values(updated_at=func.now()))

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
        id: UUID | None = None,
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
            id=id or uuid4(),
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
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise DocumentsIntegrityError from exc
        return self._to_record(row)

    async def set_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error_code: DocumentErrorCode | None = None,
        error_detail: str | None = None,
    ) -> DocumentRecord | None:
        """Update the status of a document and return the fresh record."""
        row = await self._session.get(Document, document_id)
        if row is None:
            return None
        row.status = status.value
        row.error_code = error_code.value if error_code is not None else None
        row.error_detail = error_detail
        await self._session.flush()
        return self._to_record(row)

    async def set_generation_start(self, document_id: UUID, index: int) -> None:
        row = await self._session.get(Document, document_id)
        if row is not None:
            row.generation_start_index = index
            await self._session.flush()

    async def set_topic_tree(
        self,
        document_id: UUID,
        topic_tree: Sequence[Mapping[str, Any]],
    ) -> DocumentRecord | None:
        """Store the parsed topic tree (a list of root nodes) and return the record."""
        row = await self._session.get(Document, document_id)
        if row is None:
            return None
        row.topic_tree = [dict(node) for node in topic_tree]
        await self._session.flush()
        return self._to_record(row)

    async def count_active(self, owner_id: UUID, *, exclude: UUID | None = None) -> int:
        """Count documents of an owner that are still in processing.

        Processing means the pipeline still has to do something with the
        document: ``uploaded`` (not taken by the worker yet), ``parsing``
        or ``generating`` (story 1.4.13). A parsed document waits idle
        for the user's plan/generate and does not hold pipeline capacity,
        so it does not count.

        ``exclude`` skips the document that is being started right now:
        it may already be ``generating`` from a previous start.
        """
        conditions = [
            Document.owner_id == owner_id,
            Document.status.in_(
                [
                    DocumentStatus.UPLOADED.value,
                    DocumentStatus.PARSING.value,
                    DocumentStatus.GENERATING.value,
                ]
            ),
        ]
        if exclude is not None:
            conditions.append(Document.id != exclude)
        stmt = select(func.count()).select_from(Document).where(*conditions)
        return int((await self._session.scalars(stmt)).one())
