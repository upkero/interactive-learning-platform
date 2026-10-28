"""Integrity errors of the users area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class UsersIntegrityError(BaseAppException):
    """Base exception for user integrity violations."""

    error_code = "users_integrity_error"
    default_detail = "User integrity constraint violated."


class UserAlreadyExistsError(UsersIntegrityError):
    """A user with the same email already exists."""

    status_code = 409
    error_code = "user_already_exists"
    default_detail = "User with this email already exists."
