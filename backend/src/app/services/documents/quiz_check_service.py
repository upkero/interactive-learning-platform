"""Check and persist answers to published quizzes."""

import logging
from collections.abc import Callable, Mapping
from math import isclose
from uuid import UUID

from pydantic import StrictFloat, StrictStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quizzes.check_result import QuizCheckResult
from src.app.exceptions.quizzes import InvalidQuizAnswerError, QuizIntegrityError, QuizNotFoundError
from src.app.interfaces.repositories.documents import DocumentPartRepositoryProtocol, UserMaterialRepositoryProtocol
from src.app.interfaces.repositories.quizzes import QuizAttemptRepositoryProtocol
from src.app.services.solver.quizzes.answer_keys import MultipleChoiceKey, NumericKey, OrderingKey, SingleChoiceKey

logger = logging.getLogger(__name__)

_SINGLE = TypeAdapter(SingleChoiceKey)
_MULTIPLE = TypeAdapter(MultipleChoiceKey)
_ORDERING = TypeAdapter(OrderingKey)
_NUMERIC = TypeAdapter(NumericKey)
_STRING_ANSWER = TypeAdapter(StrictStr)
_LIST_ANSWER = TypeAdapter(list[StrictStr])
_NUMBER_ANSWER = TypeAdapter(StrictFloat)


def check_answer(quiz: Mapping[str, object], key: Mapping[str, object], answer: object) -> QuizCheckResult:
    kind = quiz.get("type")
    parsed: SingleChoiceKey | MultipleChoiceKey | OrderingKey | NumericKey
    try:
        match kind:
            case "single_choice":
                parsed = _SINGLE.validate_python(key)
            case "multiple_choice":
                parsed = _MULTIPLE.validate_python(key)
            case "ordering":
                parsed = _ORDERING.validate_python(key)
            case "numeric":
                parsed = _NUMERIC.validate_python(key)
            case _:
                raise QuizIntegrityError()
    except ValidationError as exc:
        raise QuizIntegrityError() from exc

    try:
        match parsed:
            case SingleChoiceKey():
                correct = parsed.correct_id
                return QuizCheckResult(
                    _STRING_ANSWER.validate_python(answer) == correct, correct, parsed.explanation, parsed.why_wrong
                )
            case MultipleChoiceKey():
                choices = _LIST_ANSWER.validate_python(answer)
                if len(set(choices)) != len(choices):
                    raise InvalidQuizAnswerError()
                return QuizCheckResult(
                    set(choices) == set(parsed.correct_ids), parsed.correct_ids, parsed.explanation, parsed.why_wrong
                )
            case OrderingKey():
                order = _LIST_ANSWER.validate_python(answer)
                if len(set(order)) != len(order):
                    raise InvalidQuizAnswerError()
                return QuizCheckResult(
                    order == parsed.correct_order, parsed.correct_order, parsed.explanation, parsed.common_mistakes
                )
            case NumericKey():
                number = _NUMBER_ANSWER.validate_python(answer)
                return QuizCheckResult(
                    isclose(number, parsed.answer, rel_tol=parsed.tolerance, abs_tol=1e-9),
                    parsed.answer,
                    parsed.explanation,
                    parsed.common_mistakes,
                )
    except ValidationError as exc:
        raise InvalidQuizAnswerError() from exc
    raise QuizIntegrityError()


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
            quizzes = part.content.get("quizzes")
            keys = part.content.get("answer_keys")
            if not isinstance(quizzes, list):
                raise QuizNotFoundError()
            quiz = next((item for item in quizzes if isinstance(item, dict) and item.get("key") == quiz_key), None)
            if quiz is None:
                raise QuizNotFoundError()
            try:
                key = keys.get(quiz_key) if isinstance(keys, dict) else None
                if not isinstance(key, dict):
                    raise QuizIntegrityError()
                result = check_answer(quiz, key, answer)
            except QuizIntegrityError:
                logger.error(
                    "Published quiz answer key is invalid.", extra={"part_id": str(part_id), "quiz_key": quiz_key}
                )
                raise
            await self._attempts(session).create(
                user_id=user_id,
                part_id=part_id,
                quiz_key=quiz_key,
                answer={"value": answer},
                is_correct=result.is_correct,
            )
        return result
