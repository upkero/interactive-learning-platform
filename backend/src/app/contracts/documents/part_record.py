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
    # tuple keeps the record deep-immutable; the ORM row's JSONB list is
    # copied once in the repository `_to_record` mapping.
    topic_ids: tuple[str, ...]
    source_markdown: str
    token_count: int
    # dict is a defensive copy made in `_to_record`; the mapping is shared
    # deliberately (the domain never mutates profiles in place).
    profile: dict[str, Any]
    status: PartStatus
    content: dict[str, Any] | None
    attempts: int
    stage_changed_at: datetime
    error: str | None
    published_at: datetime | None
