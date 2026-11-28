"""Output contracts of the widget resolver (story 2.4).

The resolver turns a widget directive into a concrete WidgetUsage row.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from src.app.contracts.solver.degradation import Degradation
from src.app.contracts.solver.main_pass import MainPassDirective

ResolveDecision = Literal["reused", "configured", "generated", "fallback"]


@dataclass(frozen=True, slots=True)
class ResolveRequest:
    """One widget directive with context needed for resolution."""

    part_id: UUID
    directive: MainPassDirective


@dataclass(frozen=True, slots=True)
class ResolveOutcome:
    """Result of resolving one widget directive."""

    directive_ref: str
    decision: ResolveDecision
    status: Literal["ready", "fallback"]
    widget_id: UUID | None
    params: dict[str, object]
    degradations: tuple[Degradation, ...] = ()


__all__ = ["ResolveDecision", "ResolveOutcome", "ResolveRequest"]
