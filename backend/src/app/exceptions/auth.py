"""Authentication errors (story 1.4.2)."""

from src.app.exceptions.base import BaseAppException


class AuthError(BaseAppException):
    """Base class for authentication errors."""


class RateLimitedError(AuthError):
    status_code = 429
    error_code = "rate_limited"
    default_detail = "Too many requests."


class InvalidCredentialsError(AuthError):
    """Login failed: unknown email or wrong password.

    Both cases share one error on purpose — the response must not
    reveal whether the email is registered.
    """

    status_code = 401
    error_code = "invalid_credentials"
    default_detail = "Invalid email or password."


class NotAuthenticatedError(AuthError):
    """No session cookie, or the token is invalid or expired."""

    status_code = 401
    error_code = "not_authenticated"
    default_detail = "Authentication required."


class EmailTakenError(AuthError):
    """Registration with an email that is already registered."""

    status_code = 409
    error_code = "email_taken"
    default_detail = "This email is already registered."
