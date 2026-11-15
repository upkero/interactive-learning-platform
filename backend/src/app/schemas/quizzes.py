"""HTTP schemas for checking quiz answers."""

from uuid import UUID

from pydantic import BaseModel, Field, StrictFloat, StrictStr


class QuizAttemptRequest(BaseModel):
    part_id: UUID
    quiz_key: str = Field(min_length=1, max_length=12)
    answer: StrictStr | list[StrictStr] | StrictFloat


class QuizAttemptResponse(BaseModel):
    is_correct: bool
    correct_answer: str | list[str] | float
    explanation: str | None
    option_explanations: dict[str, str] | list[str] | None
