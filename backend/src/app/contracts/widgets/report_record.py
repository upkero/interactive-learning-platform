"""Immutable record of a user report against a widget."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.app.contracts.widgets.statuses import ReportReason


@dataclass(frozen=True, slots=True)
class ReportRecord:
    id: UUID
    widget_id: UUID
    user_id: UUID
    part_id: UUID | None
    reason: ReportReason
    created_at: datetime
