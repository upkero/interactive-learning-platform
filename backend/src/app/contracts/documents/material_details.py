"""Material listing returned by the data layer."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
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

    @property
    def source_kind(self) -> Literal["pdf", "docx", "md", "gdocs"]:
        """The ``source_type`` value exposed to the client (story 1.4.14)."""
        if self.source_type == "gdocs":
            return "gdocs"
        if self.mime_type == "application/pdf":
            return "pdf"
        if self.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return "docx"
        return "md"
