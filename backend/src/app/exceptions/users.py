"""Errors of the users area."""

from src.app.exceptions.base import BaseAppException


class UsersError(BaseAppException):
    """Base class of every users area error."""


class UsersIntegrityError(UsersError):
    """Base exception for user integrity violations."""

    error_code = "users_integrity_error"
    default_detail = "User integrity constraint violated."


class UserAlreadyExistsError(UsersIntegrityError):
    """A user with the same email already exists."""

    status_code = 409
    error_code = "user_already_exists"
    default_detail = "User with this email already exists."


class UserNotFoundError(UsersError):
    """The referenced user does not exist (a stale token or a deleted row)."""

    status_code = 401
    public = True
    error_code = "not_authenticated"
    default_detail = "Authentication required."
