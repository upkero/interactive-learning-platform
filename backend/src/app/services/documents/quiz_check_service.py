"""Check and persist answers to published quizzes."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quizzes.check_result import QuizCheckResult
from src.app.exceptions.quizzes import InvalidQuizAnswerError, QuizNotFoundError
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, UserMaterialRepositoryProtocol
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol


def check_answer(quiz: dict[str, Any], answer: Any) -> QuizCheckResult:
    kind = quiz.get("type", "single_choice" if "correct_index" in quiz else None)
    correct = quiz.get("correct_answer", quiz.get("correct_index"))
    if kind == "single_choice":
        if type(answer) not in (str, int):
            raise InvalidQuizAnswerError()
        is_correct = answer == correct
    elif kind in ("multiple_choice", "ordering"):
        if not isinstance(answer, list) or any(type(item) not in (str, int) for item in answer):
            raise InvalidQuizAnswerError()
        if not isinstance(correct, list):
            raise InvalidQuizAnswerError()
        is_correct = set(answer) == set(correct) if kind == "multiple_choice" else answer == correct
    elif kind == "numeric":
        if type(answer) not in (int, float) or type(correct) not in (int, float):
            raise InvalidQuizAnswerError()
        assert isinstance(correct, (int, float))
        is_correct = abs(answer - correct) <= float(quiz.get("tolerance", 0))
    else:
        raise InvalidQuizAnswerError()
    return QuizCheckResult(is_correct, correct, quiz.get("explanation"), quiz.get("option_explanations"))


class QuizCheckService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        parts: DocumentPartRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        attempts: QuizAttemptRepositoryProtocol,
    ) -> None:
        self._session = session
        self._parts = parts
        self._materials = materials
        self._attempts = attempts

    async def check(self, *, user_id: UUID, part_id: UUID, quiz_key: str, answer: Any) -> QuizCheckResult:
        part = await self._parts.get(part_id)
        if part is None or await self._materials.get_role(user_id, part.document_id) is None:
            raise QuizNotFoundError()
        if part.status is not PartStatus.PUBLISHED or part.content is None:
            raise QuizNotFoundError()
        quiz = next((item for item in part.content.get("quizzes", []) if item.get("quiz_key") == quiz_key), None)
        if quiz is None:
            raise QuizNotFoundError()
        result = check_answer(quiz, answer)
        try:
            await self._attempts.create(
                user_id=user_id,
                part_id=part_id,
                quiz_key=quiz_key,
                answer={"value": answer},
                is_correct=result.is_correct,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return result
