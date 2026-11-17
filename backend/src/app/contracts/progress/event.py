"""A progress event built inside a transaction and published after commit."""

from dataclasses import dataclass
from uuid import UUID

from src.app.contracts.progress.event_type import ProgressEventType


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Everything the notifier needs to publish one stream record."""

    document_id: UUID
    event_type: ProgressEventType
    part_id: UUID | None = None
    stage: str | None = None
    message: str = ""
