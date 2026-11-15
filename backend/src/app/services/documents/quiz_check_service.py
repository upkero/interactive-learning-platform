"""Check and persist answers to published quizzes."""

from collections.abc import Callable, Mapping
from math import isclose
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quizzes.check_result import QuizCheckResult
from src.app.exceptions.quizzes import InvalidQuizAnswerError, QuizNotFoundError
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, UserMaterialRepositoryProtocol
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol


def check_answer(quiz: Mapping[str, object], key: Mapping[str, object], answer: object) -> QuizCheckResult:
    kind = quiz.get("type")
    correct: str | list[str] | float
    if kind == "single_choice":
        value = key.get("correct_id")
        if not isinstance(value, str):
            raise QuizNotFoundError()
        if type(answer) is not str:
            raise InvalidQuizAnswerError()
        correct = value
        is_correct = answer == correct
    elif kind in ("multiple_choice", "ordering"):
        if not isinstance(answer, list) or any(type(item) is not str for item in answer):
            raise InvalidQuizAnswerError()
        if len(set(answer)) != len(answer):
            raise InvalidQuizAnswerError()
        value = key.get("correct_order" if kind == "ordering" else "correct_ids")
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise QuizNotFoundError()
        correct = [item for item in value if isinstance(item, str)]
        is_correct = answer == correct if kind == "ordering" else set(answer) == set(correct)
    elif kind == "numeric":
        value = key.get("answer")
        if type(answer) not in (int, float):
            raise InvalidQuizAnswerError()
        if type(value) not in (int, float) or not isinstance(value, int | float):
            raise QuizNotFoundError()
        tolerance = key.get("tolerance", 0.01)
        if type(tolerance) not in (int, float) or not isinstance(tolerance, int | float) or tolerance < 0:
            raise QuizNotFoundError()
        assert isinstance(answer, int | float)
        correct = float(value)
        is_correct = isclose(answer, correct, rel_tol=tolerance, abs_tol=1e-9)
    else:
        raise InvalidQuizAnswerError()
    explanation = key.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        raise QuizNotFoundError()
    raw_explanations = (
        key.get("why_wrong") if kind in ("single_choice", "multiple_choice") else key.get("common_mistakes")
    )
    option_explanations: dict[str, str] | list[str] | None = None
    if isinstance(raw_explanations, dict):
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in raw_explanations.items()):
            raise QuizNotFoundError()
        option_explanations = {k: v for k, v in raw_explanations.items() if isinstance(k, str) and isinstance(v, str)}
    elif isinstance(raw_explanations, list):
        if any(not isinstance(item, str) for item in raw_explanations):
            raise QuizNotFoundError()
        option_explanations = [item for item in raw_explanations if isinstance(item, str)]
    elif raw_explanations is not None:
        raise QuizNotFoundError()
    return QuizCheckResult(is_correct, correct, explanation, option_explanations)


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

    async def check(self, *, user_id: UUID, part_id: UUID, quiz_key: str, answer: object) -> QuizCheckResult:
        async with self._session_factory() as session, session.begin():
            part = await self._parts(session).get(part_id)
            if part is None or await self._materials(session).get_role(user_id, part.document_id) is None:
                raise QuizNotFoundError()
            if part.status is not PartStatus.PUBLISHED or part.content is None:
                raise QuizNotFoundError()
            quiz = next((item for item in part.content.get("quizzes", []) if item.get("key") == quiz_key), None)
            key = part.content.get("answer_keys", {}).get(quiz_key)
            if quiz is None or not isinstance(key, dict):
                raise QuizNotFoundError()
            result = check_answer(quiz, key, answer)
            await self._attempts(session).create(
                user_id=user_id,
                part_id=part_id,
                quiz_key=quiz_key,
                answer={"value": answer},
                is_correct=result.is_correct,
            )
        return result
