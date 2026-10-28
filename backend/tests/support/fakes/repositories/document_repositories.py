"""In-memory fakes of the document aggregate repositories."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    ImageRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from tests.support.time import now


class FakeDocumentRepository(DocumentRepositoryProtocol):
    """Dict-backed stub mirroring DocumentRepository API."""

    def __init__(self) -> None:
        self._documents: dict[UUID, DocumentRecord] = {}

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        return self._documents.get(document_id)

    async def get_owned(self, document_id: UUID, owner_id: UUID) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None and row.owner_id == owner_id:
            return row
        return None

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
        timestamp = now()
        record = DocumentRecord(
            id=uuid4(),
            owner_id=owner_id,
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            object_key=object_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            page_count=page_count,
            checksum=checksum,
            status=DocumentStatus.UPLOADED,
            topic_tree=None,
            error=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._documents[record.id] = record
        return record

    async def set_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error: str | None = None,
    ) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None:
            updated = replace(row, status=status, error=error, updated_at=now())
            self._documents[document_id] = updated
            return updated
        return None

    async def set_topic_tree(self, document_id: UUID, topic_tree: dict[str, Any]) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None:
            updated = replace(row, topic_tree=topic_tree, updated_at=now())
            self._documents[document_id] = updated
            return updated
        return None

    async def count_active(self, owner_id: UUID) -> int:
        active = {DocumentStatus.UPLOADED, DocumentStatus.PARSING, DocumentStatus.PARSED, DocumentStatus.GENERATING}
        return sum(1 for d in self._documents.values() if d.owner_id == owner_id and d.status in active)


class FakeDocumentPartRepository(DocumentPartRepositoryProtocol):
    """Dict-backed stub with a serialized conditional transition."""

    def __init__(self) -> None:
        self._parts: dict[UUID, PartRecord] = {}

    async def get(self, part_id: UUID) -> PartRecord | None:
        return self._parts.get(part_id)

    async def list_by_document(self, document_id: UUID) -> list[PartRecord]:
        return sorted(
            (p for p in self._parts.values() if p.document_id == document_id),
            key=lambda p: p.index,
        )

    async def add_many(self, document_id: UUID, parts: Sequence[PartDraft]) -> list[PartRecord]:
        created: list[PartRecord] = []
        for draft in parts:
            record = PartRecord(
                id=uuid4(),
                document_id=document_id,
                index=draft.index,
                title=draft.title,
                topic_ids=tuple(draft.topic_ids),
                source_markdown=draft.source_markdown,
                token_count=draft.token_count,
                profile=dict(draft.profile or {}),
                content=dict(draft.content) if draft.content is not None else None,
                status=PartStatus.QUEUED,
                attempts=0,
                stage_changed_at=now(),
                error=None,
                published_at=None,
            )
            self._parts[record.id] = record
            created.append(record)
        return created

    async def transition(
        self,
        part_id: UUID,
        expected: frozenset[PartStatus],
        to: PartStatus,
        *,
        error: str | None = None,
        bump_attempts: bool = False,
    ) -> bool:
        row = self._parts.get(part_id)
        if row is None or row.status not in expected:
            return False
        updated = replace(
            row,
            status=to,
            error=error,
            stage_changed_at=now(),
            attempts=row.attempts + (1 if bump_attempts else 0),
            published_at=datetime.now(UTC) if to is PartStatus.PUBLISHED else row.published_at,
        )
        self._parts[part_id] = updated
        return True


class FakeImageRepository(ImageRepositoryProtocol):
    """Dict-backed stub mirroring ImageRepository API."""

    def __init__(self) -> None:
        self._images: dict[UUID, ImageRecord] = {}

    async def get(self, image_id: UUID) -> ImageRecord | None:
        return self._images.get(image_id)

    async def list_by_document(self, document_id: UUID) -> list[ImageRecord]:
        return [i for i in self._images.values() if i.document_id == document_id]

    async def add_many(self, document_id: UUID, images: Sequence[ImageDraft]) -> list[ImageRecord]:
        created: list[ImageRecord] = []
        for draft in images:
            record = ImageRecord(
                id=uuid4(),
                document_id=document_id,
                object_key=draft.object_key,
                page=draft.page,
                width=draft.width,
                height=draft.height,
                caption=draft.caption,
                description=draft.description,
                topic_id=draft.topic_id,
            )
            self._images[record.id] = record
            created.append(record)
        return created


class FakeUserMaterialRepository(UserMaterialRepositoryProtocol):
    """Dict-backed stub mirroring UserMaterialRepository API."""

    def __init__(self) -> None:
        self._materials: dict[tuple[UUID, UUID], MaterialRecord] = {}

    async def get_role(self, user_id: UUID, document_id: UUID) -> MaterialRole | None:
        row = self._materials.get((user_id, document_id))
        return row.role if row is not None else None

    async def create(
        self,
        *,
        user_id: UUID,
        document_id: UUID,
        role: MaterialRole,
        shared_by: UUID | None = None,
    ) -> MaterialRecord:
        record = MaterialRecord(
            user_id=user_id,
            document_id=document_id,
            role=role,
            shared_by=shared_by,
            created_at=now(),
        )
        self._materials[(user_id, document_id)] = record
        return record

    async def list_by_user(self, user_id: UUID) -> list[MaterialRecord]:
        return [m for m in self._materials.values() if m.user_id == user_id]
