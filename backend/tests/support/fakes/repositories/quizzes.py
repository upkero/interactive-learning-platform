"""In-memory fakes of the quiz attempt repositories."""

from typing import Any
from uuid import UUID, uuid4

from src.app.contracts.quizzes import QuizAttemptRecord
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol
from tests.support.time import now


class FakeQuizAttemptRepository(QuizAttemptRepositoryProtocol):
    """Dict-backed stub mirroring QuizAttemptRepository API."""

    def __init__(self) -> None:
        self._attempts: dict[UUID, QuizAttemptRecord] = {}

    async def create(
        self,
        *,
        user_id: UUID,
        part_id: UUID,
        quiz_key: str,
        answer: dict[str, Any],
        is_correct: bool,
    ) -> QuizAttemptRecord:
        record = QuizAttemptRecord(
            id=uuid4(),
            user_id=user_id,
            part_id=part_id,
            quiz_key=quiz_key,
            answer=answer,
            is_correct=is_correct,
            created_at=now(),
        )
        self._attempts[record.id] = record
        return record

    async def list_by_part(self, part_id: UUID) -> list[QuizAttemptRecord]:
        return [a for a in self._attempts.values() if a.part_id == part_id]
