"""Result of checking a quiz answer."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QuizCheckResult:
    is_correct: bool
    correct_answer: Any
    explanation: Any
    option_explanations: Any
