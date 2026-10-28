"""Typed input for inserting new widget usages (replaces raw dicts)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.app.contracts.widgets.statuses import UsageStatus


@dataclass(frozen=True, slots=True)
class WidgetUsageDraft:
    """Data for a new widget_usages row; the repository owns the defaults."""

    directive_ref: str
    position: int
    widget_id: UUID | None = None
    params: dict[str, Any] | None = None
    status: UsageStatus = UsageStatus.PENDING
