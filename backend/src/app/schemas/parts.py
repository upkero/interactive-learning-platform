"""HTTP response schemas for document parts."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartContentOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    markdown: str = ""
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    quizzes: list[dict[str, Any]] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)


class PartOut(BaseModel):
    id: UUID
    document_id: UUID
    title: str
    index: int
    status: Literal["queued", "main_pass", "resolving", "assembling", "published", "failed"]
    content: PartContentOut | None
