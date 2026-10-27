"""Repository of document parts."""

import datetime
from uuid import UUID

from sqlalchemy import Update, and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import PartStatus
from src.app.models.document_part import DocumentPart


class DocumentPartRepository:
    """CRUD-style access to the document_parts table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: DocumentPart) -> PartRecord:
        return PartRecord(
            id=row.id,
            document_id=row.document_id,
            index=row.index,
            title=row.title,
            topic_ids=list(row.topic_ids),
            source_markdown=row.source_markdown,
            token_count=row.token_count,
            profile=dict(row.profile),
            status=PartStatus(row.status),
            content=dict(row.content) if row.content is not None else None,
            attempts=row.attempts,
            stage_changed_at=row.stage_changed_at,
            error=row.error,
            published_at=row.published_at,
        )

    async def get(self, part_id: UUID) -> PartRecord | None:
        row = await self._session.get(DocumentPart, part_id)
        return self._to_record(row) if row is not None else None

    async def list_by_document(self, document_id: UUID) -> list[PartRecord]:
        rows = await self._session.scalars(
            select(DocumentPart).where(DocumentPart.document_id == document_id).order_by(DocumentPart.index)
        )
        return [self._to_record(row) for row in rows.all()]

    async def add_many(
        self,
        document_id: UUID,
        rows: list[dict[str, object]],
    ) -> list[PartRecord]:
        """Bulk insert new parts; each row mirrors model keyword arguments."""
        created = [DocumentPart(document_id=document_id, **row) for row in rows]
        self._session.add_all(created)
        await self._session.flush()
        return [self._to_record(row) for row in created]

    async def transition(
        self,
        part_id: UUID,
        expected: frozenset[PartStatus],
        to: PartStatus,
        *,
        error: str | None = None,
        bump_attempts: bool = False,
    ) -> PartRecord | None:
        """Conditional update through the PBST pattern (compare and set).

        The state machine transition succeeds only when the current status is
        in ``expected``; a concurrent caller gets ``None`` instead of racing.
        """
        values: dict[str, object] = {"status": to.value, "error": error}
        if to is PartStatus.PUBLISHED:
            values["published_at"] = datetime.datetime.now(datetime.UTC)
        stmt: Update = (
            update(DocumentPart)
            .where(
                and_(
                    DocumentPart.id == part_id,
                    DocumentPart.status.in_([s.value for s in expected]),
                )
            )
            .values(**values)
            .returning(*DocumentPart.__table__.columns)
        )
        if bump_attempts:
            stmt = stmt.values(attempts=DocumentPart.attempts + 1)
        row = (await self._session.execute(stmt)).mappings().first()
        if row is None:
            return None
        record = PartRecord(
            id=row["id"],
            document_id=row["document_id"],
            index=row["index"],
            title=row["title"],
            topic_ids=list(row["topic_ids"]),
            source_markdown=row["source_markdown"],
            token_count=row["token_count"],
            profile=dict(row["profile"]),
            status=PartStatus(row["status"]),
            content=dict(row["content"]) if row["content"] is not None else None,
            attempts=row["attempts"],
            stage_changed_at=row["stage_changed_at"],
            error=row["error"],
            published_at=row["published_at"],
        )
        return record
