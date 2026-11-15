"""Integrity errors of the quizzes area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class QuizNotFoundError(BaseAppException):
    status_code = 404
    error_code = "quiz_not_found"
    default_detail = "Quiz not found."


class InvalidQuizAnswerError(BaseAppException):
    status_code = 422
    error_code = "invalid_quiz_answer"
    default_detail = "Answer has an invalid format."


class QuizIntegrityError(BaseAppException):
    """Base exception for quiz attempt integrity violations."""

    error_code = "quiz_integrity_error"
    default_detail = "Quiz attempt integrity constraint violated."
