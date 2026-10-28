"""Immutable record of a quiz attempt."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class QuizAttemptRecord:
    id: UUID
    user_id: UUID
    part_id: UUID
    quiz_key: str
    answer: dict[str, Any]
    is_correct: bool
    created_at: datetime
