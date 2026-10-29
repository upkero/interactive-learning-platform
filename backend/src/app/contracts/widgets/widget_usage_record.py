"""Immutable record of a widget placement on a document part page."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.app.contracts.widgets.statuses import UsageStatus


@dataclass(frozen=True, slots=True)
class WidgetUsageRecord:
    id: UUID
    part_id: UUID
    widget_id: UUID | None
    directive_ref: str
    params: dict[str, Any] | None
    position: int
    status: UsageStatus
    created_at: datetime
