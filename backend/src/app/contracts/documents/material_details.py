"""Material listing returned by the data layer."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MaterialDetails:
    document_id: UUID
    title: str
    source_type: str
    mime_type: str
    status: str
    role: str
    shared_by_email: str | None
    parts_total: int
    parts_published: int
    parts_failed: int
    updated_at: datetime
