"""Protocols of the document aggregate repositories."""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType


class DocumentRepositoryProtocol(Protocol):
    """Public API of the documents table access."""

    async def get(self, document_id: UUID) -> DocumentRecord | None: ...

    async def get_owned(self, document_id: UUID, owner_id: UUID) -> DocumentRecord | None: ...

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
    ) -> DocumentRecord: ...

    async def set_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error: str | None = None,
    ) -> DocumentRecord | None: ...

    async def set_topic_tree(self, document_id: UUID, topic_tree: dict[str, Any]) -> DocumentRecord | None: ...

    async def count_active(self, owner_id: UUID) -> int: ...


class DocumentPartRepositoryProtocol(Protocol):
    """Public API of the document_parts table access."""

    async def get(self, part_id: UUID) -> PartRecord | None: ...

    async def list_by_document(self, document_id: UUID) -> list[PartRecord]: ...

    async def add_many(self, document_id: UUID, parts: Sequence[PartDraft]) -> list[PartRecord]: ...

    async def transition(
        self,
        part_id: UUID,
        expected: frozenset[PartStatus],
        to: PartStatus,
        *,
        error: str | None = None,
        bump_attempts: bool = False,
    ) -> bool: ...


class ImageRepositoryProtocol(Protocol):
    """Public API of the images table access."""

    async def get(self, image_id: UUID) -> ImageRecord | None: ...

    async def list_by_document(self, document_id: UUID) -> list[ImageRecord]: ...

    async def add_many(self, document_id: UUID, images: Sequence[ImageDraft]) -> list[ImageRecord]: ...


class UserMaterialRepositoryProtocol(Protocol):
    """Public API of the user_materials table access."""

    async def get_role(self, user_id: UUID, document_id: UUID) -> MaterialRole | None: ...

    async def create(
        self,
        *,
        user_id: UUID,
        document_id: UUID,
        role: MaterialRole,
        shared_by: UUID | None = None,
    ) -> MaterialRecord: ...

    async def list_by_user(self, user_id: UUID) -> list[MaterialRecord]: ...
