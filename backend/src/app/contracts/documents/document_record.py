"""Immutable document record."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.app.contracts.documents.statuses import DocumentStatus, SourceType


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
    topic_tree: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime
