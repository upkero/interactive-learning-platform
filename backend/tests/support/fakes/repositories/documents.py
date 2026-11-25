"""In-memory fakes of the document aggregate repositories."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import JsonValue

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_details import MaterialDetails
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_owner import PartOwner
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.shared_user_info import SharedUserInfo
from src.app.contracts.documents.statuses import (
    DocumentErrorCode,
    DocumentStatus,
    MaterialRole,
    PartStatus,
    SourceType,
)
from src.app.contracts.documents.topic_node import topic_roots
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
        self.refreshed: list[UUID] = []
        self._parts: DocumentPartRepositoryProtocol | None = None
        # minimal transaction emulation: ids created since the last
        # checkpoint (commit) are discarded by rollback()
        self._pending: list[UUID] = []

    def attach_parts(self, parts: DocumentPartRepositoryProtocol) -> None:
        """Let ``refresh_status`` aggregate the same parts the service sees."""
        self._parts = parts

    def checkpoint(self) -> None:
        self._pending.clear()

    def rollback(self) -> None:
        """Discard rows created since the last checkpoint (commit)."""
        for document_id in self._pending:
            self._documents.pop(document_id, None)
        self._pending.clear()

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        return self._documents.get(document_id)

    def store_record(self, record: DocumentRecord) -> None:
        self._documents[record.id] = record

    async def refresh_status(self, document_id: UUID) -> None:
        """Mirror the real aggregation: finish generating documents when all parts are terminal."""
        self.refreshed.append(document_id)
        document = self._documents.get(document_id)
        if document is None or document.status is not DocumentStatus.GENERATING or self._parts is None:
            return
        all_parts = await self._parts.list_by_document(document_id)
        current_parts = [p for p in all_parts if p.index >= document.generation_start_index]
        if current_parts and all(p.status in {PartStatus.PUBLISHED, PartStatus.FAILED} for p in current_parts):
            # A previous successful run keeps the document usable even when
            # every part of the current run failed. This matches the SQL
            # repository, which checks terminality for the current run but
            # publication across all runs.
            published = any(p.status is PartStatus.PUBLISHED for p in all_parts)
            self._documents[document_id] = replace(
                document,
                status=DocumentStatus.DONE if published else DocumentStatus.FAILED,
                updated_at=now(),
            )

    async def lock_stale_uploaded(self, *, older_than: timedelta, limit: int) -> list[DocumentRecord]:
        before = now() - older_than
        return sorted(
            (d for d in self._documents.values() if d.status is DocumentStatus.UPLOADED and d.updated_at < before),
            key=lambda d: (d.updated_at, d.id),
        )[:limit]

    async def touch(self, document_id: UUID) -> None:
        if document_id in self._documents:
            self._documents[document_id] = replace(self._documents[document_id], updated_at=now())

    async def update_source(
        self,
        document_id: UUID,
        *,
        object_key: str,
        title: str | None = None,
        page_count: int | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
    ) -> None:
        row = self._documents.get(document_id)
        if row is not None:
            self._documents[document_id] = replace(
                row,
                object_key=object_key,
                title=title or row.title,
                page_count=page_count if page_count is not None else row.page_count,
                mime_type=mime_type if mime_type is not None else row.mime_type,
                size_bytes=size_bytes if size_bytes is not None else row.size_bytes,
            )

    async def begin_parsing(self, document_id: UUID) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is None or row.status not in {DocumentStatus.UPLOADED, DocumentStatus.PARSING, DocumentStatus.FAILED}:
            return None
        return await self.set_status(document_id, DocumentStatus.PARSING)

    async def get_owned(self, document_id: UUID, owner_id: UUID) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None and row.owner_id == owner_id:
            return row
        return None

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
        timestamp = now()
        record = DocumentRecord(
            id=id or uuid4(),
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
            error_code=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._documents[record.id] = record
        self._pending.append(record.id)
        return record

    async def set_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error_code: DocumentErrorCode | None = None,
        error_detail: str | None = None,
    ) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None:
            updated = replace(row, status=status, error_code=error_code, error_detail=error_detail, updated_at=now())
            self._documents[document_id] = updated
            return updated
        return None

    async def set_generation_start(self, document_id: UUID, index: int) -> None:
        if document_id in self._documents:
            self._documents[document_id] = replace(self._documents[document_id], generation_start_index=index)

    async def set_topic_tree(
        self,
        document_id: UUID,
        topic_tree: Sequence[Mapping[str, Any]],
    ) -> DocumentRecord | None:
        row = self._documents.get(document_id)
        if row is not None:
            updated = replace(row, topic_tree=topic_roots(topic_tree), updated_at=now())
            self._documents[document_id] = updated
            return updated
        return None

    async def count_active(self, owner_id: UUID, *, exclude: UUID | None = None) -> int:
        active = {DocumentStatus.UPLOADED, DocumentStatus.PARSING, DocumentStatus.GENERATING}
        return sum(
            1 for d in self._documents.values() if d.owner_id == owner_id and d.status in active and d.id != exclude
        )


class FakeDocumentPartRepository(DocumentPartRepositoryProtocol):
    """Dict-backed stub with a serialized conditional transition."""

    def __init__(self) -> None:
        self._parts: dict[UUID, PartRecord] = {}
        self.drafts: dict[UUID, PartDraft] = {}
        self.owners: dict[UUID, PartOwner] = {}

    async def get(self, part_id: UUID) -> PartRecord | None:
        return self._parts.get(part_id)

    def store_record(self, record: PartRecord) -> None:
        self._parts[record.id] = record

    async def lock(self, part_id: UUID) -> PartRecord | None:
        return await self.get(part_id)

    async def part_owner(self, part_id: UUID) -> PartOwner | None:
        return self.owners.get(part_id)

    async def lock_stale(
        self, *, statuses: frozenset[PartStatus], older_than: timedelta, limit: int
    ) -> list[PartRecord]:
        before = now() - older_than
        return sorted(
            (p for p in self._parts.values() if p.status in statuses and p.stage_changed_at < before),
            key=lambda p: (p.stage_changed_at, p.id),
        )[:limit]

    async def touch(self, part_id: UUID) -> None:
        if part_id in self._parts:
            self._parts[part_id] = replace(self._parts[part_id], stage_changed_at=now())

    async def list_by_document(self, document_id: UUID) -> list[PartRecord]:
        return sorted(
            (p for p in self._parts.values() if p.document_id == document_id),
            key=lambda p: p.index,
        )

    async def has_published_since(self, document_id: UUID, start_index: int) -> bool:
        return any(
            p.document_id == document_id and p.index >= start_index and p.status is PartStatus.PUBLISHED
            for p in self._parts.values()
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
            self.drafts[record.id] = draft
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
        content: dict[str, JsonValue] | None = None,
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
            content=content if content is not None else row.content,
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

    async def get_many(self, image_ids: Sequence[UUID]) -> list[ImageRecord]:
        """Input order preserved, duplicates repeated, missing ids skipped."""
        return [record for image_id in image_ids if (record := self._images.get(image_id)) is not None]

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

    async def delete_by_document(self, document_id: UUID) -> list[ImageRecord]:
        records = await self.list_by_document(document_id)
        for record in records:
            self._images.pop(record.id, None)
        return records

    async def update_descriptions(self, document_id: UUID, descriptions: Mapping[str, str | None]) -> None:
        for image_id, record in list(self._images.items()):
            if record.document_id == document_id:
                ref = record.object_key.rsplit("/", 1)[-1].removesuffix(".png")
                if ref in descriptions:
                    self._images[image_id] = replace(record, description=descriptions[ref])


class FakeUserMaterialRepository(UserMaterialRepositoryProtocol):
    """Dict-backed stub mirroring UserMaterialRepository API."""

    def __init__(self) -> None:
        self._materials: dict[tuple[UUID, UUID], MaterialRecord] = {}
        self.details: list[MaterialDetails] = []
        # email/display_name are not part of MaterialRecord; tests register
        # the user info alongside shared materials
        self._user_info: dict[UUID, tuple[str, str | None]] = {}
        # minimal transaction emulation, see FakeDocumentRepository
        self._pending: list[tuple[UUID, UUID]] = []

    def register_user(self, user_id: UUID, email: str, display_name: str | None = None) -> None:
        self._user_info[user_id] = (email, display_name)

    def checkpoint(self) -> None:
        self._pending.clear()

    def rollback(self) -> None:
        """Discard rows created since the last checkpoint (commit)."""
        for key in self._pending:
            self._materials.pop(key, None)
        self._pending.clear()

    async def get_role(self, user_id: UUID, document_id: UUID) -> MaterialRole | None:
        row = self._materials.get((user_id, document_id))
        return row.role if row is not None else None

    async def share_if_absent(self, user_id: UUID, document_id: UUID, shared_by: UUID) -> None:
        if (user_id, document_id) not in self._materials:
            await self.create(user_id=user_id, document_id=document_id, role=MaterialRole.SHARED, shared_by=shared_by)

    async def list_details(self, user_id: UUID, role: MaterialRole) -> list[MaterialDetails]:
        return [
            detail
            for detail in self.details
            if (user_id, detail.document_id) in self._materials and detail.role == role.value
        ]

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
        self._pending.append((user_id, document_id))
        return record

    async def list_by_user(self, user_id: UUID) -> list[MaterialRecord]:
        return [m for m in self._materials.values() if m.user_id == user_id]

    async def list_shared_with(self, document_id: UUID) -> list[SharedUserInfo]:
        return [
            SharedUserInfo(
                user_id=m.user_id,
                email=self._user_info.get(m.user_id, ("", None))[0],
                display_name=self._user_info.get(m.user_id, ("", None))[1],
                shared_at=m.created_at,
            )
            for m in self._materials.values()
            if m.document_id == document_id and m.role is MaterialRole.SHARED
        ]
