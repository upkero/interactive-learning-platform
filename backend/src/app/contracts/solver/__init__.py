"""Immutable contracts of the solver (stories 2.2+)."""

from src.app.contracts.solver.degradation import Degradation
from src.app.contracts.solver.main_pass import (
    DIRECTIVE_KINDS,
    REF_PREFIX,
    DirectiveKind,
    DirectiveSpan,
    MainPassDirective,
    MainPassDraft,
    MainPassInput,
    MainPassResult,
    PartImage,
    ReaderDepth,
    ReaderGoal,
    ReaderLevel,
    ReaderProfile,
)
from src.app.contracts.solver.resolve import ResolveDecision, ResolveOutcome, ResolveRequest
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.contracts.solver.widget_candidate import WidgetCandidate, WidgetMatch, WidgetWithDescription

__all__ = [
    "DIRECTIVE_KINDS",
    "REF_PREFIX",
    "Degradation",
    "DirectiveKind",
    "DirectiveSpan",
    "MainPassDirective",
    "MainPassDraft",
    "MainPassInput",
    "MainPassResult",
    "PartImage",
    "ReaderDepth",
    "ReaderGoal",
    "ReaderLevel",
    "ReaderProfile",
    "ResolveDecision",
    "ResolveOutcome",
    "ResolveRequest",
    "ValidConfig",
    "WidgetCandidate",
    "WidgetMatch",
    "WidgetWithDescription",
]
