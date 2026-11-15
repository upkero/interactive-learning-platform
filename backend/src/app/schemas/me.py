"""HTTP material listing schema."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MaterialOut(BaseModel):
    document_id: UUID
    title: str
    source_type: Literal["pdf", "docx", "md", "gdocs"]
    status: str
    role: Literal["owner", "shared"]
    shared_by_email: str | None
    parts_total: int
    parts_published: int
    parts_failed: int
    updated_at: datetime
