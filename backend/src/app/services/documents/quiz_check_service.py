"""Check and persist answers to published quizzes."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
        expected = quiz.get("correct_order", correct)
        is_correct = answer == expected if kind == "ordering" else set(answer) == set(expected or [])
    elif kind == "numeric":
        if type(answer) not in (int, float) or not isinstance(correct, int | float):
            raise InvalidQuizAnswerError()
        tolerance = quiz.get("tolerance", 0.01)
        is_correct = abs(answer - float(correct)) <= tolerance + 1e-9
    else:
        raise InvalidQuizAnswerError()
    return QuizCheckResult(is_correct, correct, quiz.get("explanation"), quiz.get("option_explanations"))


class QuizCheckService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        attempts: Callable[[AsyncSession], QuizAttemptRepositoryProtocol],
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._materials = materials
        self._attempts = attempts

    async def check(self, *, user_id: UUID, part_id: UUID, quiz_key: str, answer: Any) -> QuizCheckResult:
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).get(part_id)
            if part is None or await self._materials(session).get_role(user_id, part.document_id) is None:
                raise QuizNotFoundError()
            if part.status is not PartStatus.PUBLISHED or part.content is None:
                raise QuizNotFoundError()
            quiz = next((item for item in part.content.get("quizzes", []) if item.get("quiz_key") == quiz_key), None)
            if quiz is None:
                raise QuizNotFoundError()
            result = check_answer(quiz, answer)
            await self._attempts(session).create(
                user_id=user_id,
                part_id=part_id,
                quiz_key=quiz_key,
                answer={"value": answer},
                is_correct=result.is_correct,
            )
        return result
