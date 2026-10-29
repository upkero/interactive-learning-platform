"""Immutable record of a widget description with its embedding."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WidgetDescriptionRecord:
    id: UUID
    widget_id: UUID
    text: str
    is_paraphrase: bool
    embedding: list[float]
    created_at: datetime
