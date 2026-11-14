"""HTTP schemas of the documents area (stories 1.4.3-1.4.7).

They are the OpenAPI contract for the frontend client: statuses mirror
the DB-safe StrEnum values of ``contracts.documents.statuses``.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCreatedOut(BaseModel):
    """Body of 201 after a successful upload or import."""

    id: UUID
    status: Literal["uploaded", "parsing", "parsed", "generating", "done", "failed"]


class PartSummaryOut(BaseModel):
    id: UUID
    index: int
    title: str
    status: Literal["queued", "main_pass", "resolving", "assembling", "published", "failed"]


class SharedWithOut(BaseModel):
    display_name: str | None
    email: str
    shared_at: datetime


class DocumentOut(BaseModel):
    """Body of ``GET /documents/{id}``."""

    id: UUID
    title: str
    status: Literal["uploaded", "parsing", "parsed", "generating", "done", "failed"]
    # parse_failed, gdocs_not_public, … (story 1.9)
    error_code: str | None = None
    page_count: int | None
    role: Literal["owner", "shared"]
    source_url: str | None = Field(description="Presigned URL of the source file; for gdocs — the original link.")
    parts: list[PartSummaryOut]
    shared_with: list[SharedWithOut] = Field(
        default_factory=list,
        description="Filled only for the owner; shared users see an empty list.",
    )


class TopicNodeOut(BaseModel):
    """Recursive node of ``GET /documents/{id}/topics`` (story 1.4.5)."""

    id: str
    title: str
    level: int
    tokens: int = Field(description="Token sum of the whole subtree.")
    children: list["TopicNodeOut"]


class TopicTreeOut(BaseModel):
    topics: list[TopicNodeOut]
