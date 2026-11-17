"""Outcome of one recovery attempt, with events published only after commit."""

from dataclasses import dataclass

from src.app.contracts.progress.event import ProgressEvent


@dataclass(frozen=True, slots=True)
class RecoveryOutcome:
    """What a recovery attempt changed and which events the caller may publish."""

    requeued: bool = False
    failed: bool = False
    events: tuple[ProgressEvent, ...] = ()
