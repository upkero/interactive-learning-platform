"""Immutable record of an image extracted from a document."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ImageRecord:
    id: UUID
    document_id: UUID
    object_key: str
    page: int | None
    width: int
    height: int
    caption: str | None
    description: str | None
    topic_id: str | None
