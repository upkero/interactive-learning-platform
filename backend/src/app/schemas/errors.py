"""Unified error response exposed to OpenAPI clients."""

from typing import Any, Literal

from pydantic import BaseModel

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
    "app_error",
    "widgets_integrity_error",
    "widget_constraint",
    "widget_usage_duplicate",
    "users_integrity_error",
    "user_already_exists",
    "quiz_integrity_error",
    "object_storage_error",
    "object_not_found",
    "llm_error",
    "llm_configuration_error",
    "llm_input_error",
    "llm_generation_error",
    "quota_integrity_error",
    "ledger_entry_duplicate",
    "documents_integrity_error",
    "document_part_duplicate",
    "material_access_duplicate",
    "upload_validation_error",
]


class ErrorResponse(BaseModel):
    # Validation errors carry structured lists; domain errors carry strings.
    detail: Any
    error_code: ErrorCode
    available: int | None = None
    requested: int | None = None
    status: str | None = None
    limit: int | None = None
    reason: str | None = None
