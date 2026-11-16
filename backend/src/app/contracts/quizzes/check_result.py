"""Result of checking a quiz answer."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuizCheckResult:
    is_correct: bool
    correct_answer: str | list[str] | float
    explanation: str | None
    option_explanations: dict[str, str] | list[str] | None
