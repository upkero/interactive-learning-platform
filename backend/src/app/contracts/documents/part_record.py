"""Immutable record of a document part."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.app.contracts.documents.statuses import PartStatus


@dataclass(frozen=True, slots=True)
class PartRecord:
    id: UUID
    document_id: UUID
    index: int
    title: str
    topic_ids: list[str]
    source_markdown: str
    token_count: int
    profile: dict[str, Any]
    status: PartStatus
    content: dict[str, Any] | None
    attempts: int
    stage_changed_at: datetime
    error: str | None
    published_at: datetime | None
