"""A progress event built inside a transaction and published after commit."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
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
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def type(self) -> str:
        return self.event_type.value

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "message": self.message,
            "ts": self.ts.isoformat(),
        }
        if self.part_id is not None:
            payload["part_id"] = str(self.part_id)
        if self.stage is not None:
            payload["stage"] = self.stage
        return payload
