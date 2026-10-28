"""Repository of document parts."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import PartStatus
from src.app.exceptions.documents import DocumentPartDuplicateError
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol
from src.app.models.document_part import DocumentPart


class DocumentPartRepository(DocumentPartRepositoryProtocol):
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
            topic_ids=tuple(row.topic_ids),
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

    async def add_many(self, document_id: UUID, parts: Sequence[PartDraft]) -> list[PartRecord]:
        """Insert new parts from the splitting plan; only flush, never commit."""
        created = [
            DocumentPart(
                document_id=document_id,
                index=draft.index,
                title=draft.title,
                topic_ids=list(draft.topic_ids),
                source_markdown=draft.source_markdown,
                token_count=draft.token_count,
                profile=draft.profile or {},
                content=draft.content,
                status="queued",
            )
            for draft in parts
        ]
        self._session.add_all(created)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise DocumentPartDuplicateError from exc
        return [self._to_record(row) for row in created]

    async def transition(
        self,
        part_id: UUID,
        expected: frozenset[PartStatus],
        to: PartStatus,
        *,
        error: str | None = None,
        bump_attempts: bool = False,
    ) -> bool:
        """Compare-and-set status change: ``UPDATE ... WHERE status IN (...) RETURNING id``.

        The transition succeeds only when the current status is in ``expected``;
        ``False`` means a concurrent caller (e.g. the watchdog) won the race.
        """
        values: dict[str, object] = {
            "status": to.value,
            "stage_changed_at": func.now(),
            "error": error,
        }
        if to is PartStatus.PUBLISHED:
            values["published_at"] = func.now()
        if bump_attempts:
            values["attempts"] = DocumentPart.attempts + 1
        stmt = (
            update(DocumentPart)
            .where(DocumentPart.id == part_id, DocumentPart.status.in_([s.value for s in expected]))
            .values(**values)
            .returning(DocumentPart.id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
