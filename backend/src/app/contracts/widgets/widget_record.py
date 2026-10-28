"""Immutable record of a widget."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.app.contracts.widgets.statuses import WidgetKind, WidgetStatus


@dataclass(frozen=True, slots=True)
class WidgetRecord:
    id: UUID
    kind: WidgetKind
    primitive_id: str | None
    mode: str | None
    params: dict[str, Any] | None
    source_tsx: str | None
    compiled_js: str | None
    status: WidgetStatus
    canonical_id: UUID | None
    version: int
    created_from_part_id: UUID | None
    created_at: datetime
