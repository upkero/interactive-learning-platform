"""Immutable document record."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.contracts.documents.topic_node import TopicNode


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: UUID
    owner_id: UUID
    title: str
    source_type: SourceType
    source_uri: str | None
    object_key: str
    mime_type: str
    size_bytes: int
    page_count: int | None
    checksum: str
    status: DocumentStatus
    topic_tree: tuple[TopicNode, ...] | None
    error_code: DocumentErrorCode | None
    created_at: datetime
    updated_at: datetime
    error_detail: str | None = None
    generation_start_index: int = 0
