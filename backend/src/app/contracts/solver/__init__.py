"""Immutable contracts of the solver (stories 2.2+)."""

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
from src.app.contracts.solver.widget_assembly import WidgetAssembly, WidgetPlacement
from src.app.contracts.solver.widget_candidate import WidgetCandidate, WidgetMatch, WidgetWithDescription
from src.app.contracts.solver.quiz_draft import QuizDraft, QuizType
from src.app.contracts.solver.widget_resolution import WidgetResolution

__all__ = [
    "DIRECTIVE_KINDS",
    "REF_PREFIX",
    "DirectiveKind",
    "DirectiveSpan",
    "MainPassDirective",
    "MainPassDraft",
    "MainPassInput",
    "MainPassResult",
    "PartImage",
    "QuizDraft",
    "QuizType",
    "ReaderDepth",
    "ReaderGoal",
    "ReaderLevel",
    "ReaderProfile",
    "WidgetAssembly",
    "WidgetCandidate",
    "WidgetMatch",
    "WidgetPlacement",
    "WidgetResolution",
    "WidgetWithDescription",
]
