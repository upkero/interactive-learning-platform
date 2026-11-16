"""HTTP material listing schema."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LastAnswersOut(BaseModel):
    level: Literal["novice", "intermediate", "advanced"]
    goal: Literal["exam", "understand", "refresh"]
    depth: Literal["overview", "standard", "deep"]


class MeOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    locale: Literal["ru", "en"]
    notify_email: bool
    last_answers: LastAnswersOut | None


class MePatch(BaseModel):
    notify_email: bool | None = None
    locale: Literal["ru", "en"] | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class QuotaOut(BaseModel):
    monthly_limit: int
    available: int
    period_start: date
    period_end: date = Field(description="Exclusive bound: the first day of the next period.")


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
