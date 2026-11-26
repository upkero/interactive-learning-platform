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
    "ReaderDepth",
    "ReaderGoal",
    "ReaderLevel",
    "ReaderProfile",
]
