"""Repository of quiz attempts."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.quizzes import QuizAttemptRecord
from src.app.models.quiz_attempt import QuizAttempt


class QuizAttemptRepository:
    """Access to the quiz_attempts table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: QuizAttempt) -> QuizAttemptRecord:
        return QuizAttemptRecord(
            id=row.id,
            user_id=row.user_id,
            part_id=row.part_id,
            quiz_key=row.quiz_key,
            answer=dict(row.answer),
            is_correct=row.is_correct,
            created_at=row.created_at,
        )

    async def create(
        self,
        *,
        user_id: UUID,
        part_id: UUID,
        quiz_key: str,
        answer: dict[str, Any],
        is_correct: bool,
    ) -> QuizAttemptRecord:
        row = QuizAttempt(
            user_id=user_id,
            part_id=part_id,
            quiz_key=quiz_key,
            answer=answer,
            is_correct=is_correct,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def list_by_part(self, part_id: UUID) -> list[QuizAttemptRecord]:
        rows = await self._session.scalars(
            select(QuizAttempt).where(QuizAttempt.part_id == part_id).order_by(QuizAttempt.created_at)
        )
        return [self._to_record(row) for row in rows.all()]
