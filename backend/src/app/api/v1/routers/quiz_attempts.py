"""Quiz checking endpoint."""

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import QuizCheckServiceDep
from src.app.schemas.quizzes import QuizAttemptIn, QuizAttemptOut

router = APIRouter(prefix="/quiz-attempts", tags=["quiz-attempts"])


@router.post("", response_model=QuizAttemptOut, status_code=200, operation_id="quiz_attempts_create")
async def create_attempt(body: QuizAttemptIn, user: CurrentUserDep, service: QuizCheckServiceDep) -> QuizAttemptOut:
    result = await service.check(user_id=user.id, part_id=body.part_id, quiz_key=body.quiz_key, answer=body.answer)
    return QuizAttemptOut(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        option_explanations=result.option_explanations,
    )
