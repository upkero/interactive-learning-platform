"""In-memory fakes of the document aggregate repositories."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType
from tests.support.time import now


class FakeDocumentRepository:
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
    ) -> None:
        row = self._documents.get(document_id)
        if row is not None:
            self._documents[document_id] = DocumentRecord(
                **{
                    **{f: getattr(row, f) for f in row.__slots__},
                    "status": status,
                    "error": error,
                }
            )

    async def count_active(self, owner_id: UUID) -> int:
        active = {DocumentStatus.UPLOADED, DocumentStatus.PARSING, DocumentStatus.PARSED, DocumentStatus.GENERATING}
        return sum(1 for d in self._documents.values() if d.owner_id == owner_id and d.status in active)


class FakeDocumentPartRepository:
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

    async def add_many(
        self,
        document_id: UUID,
        rows: list[dict[str, Any]],
    ) -> list[PartRecord]:
        created: list[PartRecord] = []
        for row in rows:
            record = PartRecord(
                id=uuid4(),
                document_id=document_id,
                index=int(cast(int, row["index"])),
                title=str(row["title"]),
                topic_ids=list(cast(list[str], row["topic_ids"])),
                source_markdown=str(row["source_markdown"]),
                token_count=int(cast(int, row["token_count"])),
                profile=dict(cast(dict[str, Any], row["profile"])),
                status=PartStatus.QUEUED,
                content=None,
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
    ) -> PartRecord | None:
        row = self._parts.get(part_id)
        if row is None or row.status not in expected:
            return None
        updated = PartRecord(
            **{
                **{f: getattr(row, f) for f in row.__slots__},
                "status": to,
                "error": error,
                "attempts": row.attempts + (1 if bump_attempts else 0),
                "published_at": datetime.now(UTC) if to is PartStatus.PUBLISHED else row.published_at,
            }
        )
        self._parts[part_id] = updated
        return updated


class FakeImageRepository:
    """Dict-backed stub mirroring ImageRepository API."""

    def __init__(self) -> None:
        self._images: dict[UUID, ImageRecord] = {}

    async def get(self, image_id: UUID) -> ImageRecord | None:
        return self._images.get(image_id)

    async def list_by_document(self, document_id: UUID) -> list[ImageRecord]:
        return [i for i in self._images.values() if i.document_id == document_id]

    async def add_many(
        self,
        document_id: UUID,
        rows: list[dict[str, Any]],
    ) -> list[ImageRecord]:
        created: list[ImageRecord] = []
        for row in rows:
            record = ImageRecord(
                id=uuid4(),
                document_id=document_id,
                object_key=str(row["object_key"]),
                page=next((int(row[r]) for r in ("page",) if row.get(r) is not None), None),
                width=int(cast(int, row["width"])),
                height=int(cast(int, row["height"])),
                caption=None,
                description=None,
                topic_id=None,
            )
            self._images[record.id] = record
            created.append(record)
        return created


class FakeUserMaterialRepository:
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
