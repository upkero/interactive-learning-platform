"""HTTP schemas for checking quiz answers."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QuizAttemptIn(BaseModel):
    part_id: UUID
    quiz_key: str = Field(min_length=1, max_length=12)
    answer: Any


class QuizAttemptOut(BaseModel):
    is_correct: bool
    correct_answer: Any
    explanation: Any
    option_explanations: Any
