"""Search contracts of the solver (story 2.3).

SQL returns ``WidgetMatch``: one widget and the description that was
actually closest to the intent. The service enriches matches with the
widget row and its main description into ``WidgetCandidate``. ORM models
never leave the repository.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.app.contracts.widgets import WidgetKind, WidgetRecord


@dataclass(frozen=True, slots=True)
class WidgetMatch:
    """A widget and the description that matched the query vector."""

    widget_id: UUID
    matched_text: str
    distance: float


@dataclass(frozen=True, slots=True)
class WidgetWithDescription:
    """A widget row plus its main (non-paraphrase) description."""

    widget: WidgetRecord
    description: str


@dataclass(frozen=True, slots=True)
class WidgetCandidate:
    """One of the top-k widgets offered to the resolver (2.4)."""

    widget_id: UUID
    kind: WidgetKind
    primitive_id: str | None
    mode: str | None
    params: dict[str, Any] | None
    matched_text: str
    description: str
    distance: float

    @classmethod
    def from_match(cls, match: WidgetMatch, item: WidgetWithDescription) -> "WidgetCandidate":
        widget = item.widget
        return cls(
            widget_id=widget.id,
            kind=widget.kind,
            primitive_id=widget.primitive_id,
            mode=widget.mode,
            params=dict(widget.params) if widget.params is not None else None,
            matched_text=match.matched_text,
            description=item.description,
            distance=match.distance,
        )


__all__ = ["WidgetCandidate", "WidgetMatch", "WidgetWithDescription"]
