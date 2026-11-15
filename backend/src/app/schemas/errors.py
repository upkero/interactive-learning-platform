"""Unified error response exposed to OpenAPI clients."""

from typing import Any, Literal

from pydantic import BaseModel

from src.app.contracts.documents import DocumentErrorCode

type ErrorCode = Literal[
    "request_validation_error",
    "not_authenticated",
    "invalid_credentials",
    "email_taken",
    "document_not_found",
    "part_not_found",
    "quiz_not_found",
    "document_not_ready",
    "quota_exceeded",
    "processing_limit_reached",
    "invalid_gdocs_url",
    "empty_topic_selection",
    "unknown_topic",
    "recipient_not_registered",
    "file_too_large",
    "unsupported_file_type",
    "too_many_pages",
    "http_error",
    "internal_server_error",
    "rate_limited",
    "share_with_self",
    "invalid_quiz_answer",
    "widget_not_found",
    "queue_unavailable",
]


class ErrorResponse(BaseModel):
    # Validation errors carry structured lists; domain errors carry strings.
    detail: Any
    error_code: ErrorCode
    available: int | None = None
    requested: int | None = None
    status: str | None = None
    limit: int | None = None
    reason: DocumentErrorCode | None = None
