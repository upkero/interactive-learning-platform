"""Integrity errors of the quizzes area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class QuizIntegrityError(BaseAppException):
    """Base exception for quiz attempt integrity violations."""

    error_code = "quiz_integrity_error"
    default_detail = "Quiz attempt integrity constraint violated."
