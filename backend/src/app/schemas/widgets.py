"""HTTP schemas for widget reports."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WidgetReportIn(BaseModel):
    part_id: UUID | None = None
    reason: Literal["wrong", "broken", "ugly", "other"]
    comment: str | None = Field(default=None, max_length=500)


class WidgetReportOut(BaseModel):
    status: Literal["ok"] = "ok"
