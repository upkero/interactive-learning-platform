"""Quiz checking endpoint."""

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import QuizCheckServiceDep
from src.app.api.v1.responses import error_responses
from src.app.schemas.quizzes import QuizAttemptRequest, QuizAttemptResponse

router = APIRouter(prefix="/quiz-attempts", tags=["quiz-attempts"])


@router.post(
    "",
    response_model=QuizAttemptResponse,
    status_code=200,
    operation_id="quiz_attempts_create",
    responses=error_responses(401, 404, 422, 500),
)
async def create_attempt(
    body: QuizAttemptRequest, user: CurrentUserDep, service: QuizCheckServiceDep
) -> QuizAttemptResponse:
    result = await service.check(user_id=user.id, part_id=body.part_id, quiz_key=body.quiz_key, answer=body.answer)
    return QuizAttemptResponse(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        option_explanations=result.option_explanations,
    )
