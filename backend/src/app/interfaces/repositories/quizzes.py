"""Protocols of the quiz attempt repositories."""

from typing import Any, Protocol
from uuid import UUID

from src.app.contracts.quizzes import QuizAttemptRecord


class QuizAttemptRepositoryProtocol(Protocol):
    """Public API of the quiz_attempts table access."""

    async def create(
        self,
        *,
        user_id: UUID,
        part_id: UUID,
        quiz_key: str,
        answer: dict[str, Any],
        is_correct: bool,
    ) -> QuizAttemptRecord: ...

    async def list_by_part(self, part_id: UUID) -> list[QuizAttemptRecord]: ...
