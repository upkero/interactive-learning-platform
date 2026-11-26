"""A progress event built inside a transaction and published after commit."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NotRequired, TypedDict
from uuid import UUID

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.contracts.progress.event_type import ProgressEventType


class ProgressPayload(TypedDict):
    type: str
    message: str
    ts: str
    part_id: NotRequired[str]
    stage: NotRequired[str]
    error_code: NotRequired[str]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Everything the notifier needs to publish one stream record."""

    document_id: UUID
    event_type: ProgressEventType
    part_id: UUID | None = None
    stage: str | None = None
    message: str = ""
    error_code: DocumentErrorCode | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> ProgressPayload:
        payload: ProgressPayload = {
            "type": self.event_type.value,
            "message": self.message,
            "ts": self.ts.isoformat(),
        }
        if self.part_id is not None:
            payload["part_id"] = str(self.part_id)
        if self.stage is not None:
            payload["stage"] = self.stage
        if self.error_code is not None:
            payload["error_code"] = self.error_code.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False)
