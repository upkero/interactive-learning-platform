"""OpenAPI declarations for the errors an operation can return."""

from src.app.schemas.errors import ErrorResponse


def error_responses(*statuses: int) -> dict[int | str, dict[str, object]]:
    return {status: {"model": ErrorResponse} for status in statuses}
