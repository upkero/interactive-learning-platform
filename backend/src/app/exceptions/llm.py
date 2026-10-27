from src.app.exceptions.base import BaseAppException


class LLMError(BaseAppException):
    """Base exception for LLM client operations."""

    error_code = "llm_error"
    default_detail = "LLM operation failed."


class LLMConfigurationError(LLMError):
    """Raised when LLM client configuration is invalid."""

    error_code = "llm_configuration_error"


class LLMInputError(LLMError, ValueError):
    """Raised when LLM input payload is invalid."""

    status_code = 422
    error_code = "llm_input_error"


class LLMGenerationError(LLMError):
    """Raised when provider generation fails."""

    error_code = "llm_generation_error"


class LLMRateLimitError(LLMError):
    """Raised when the provider returns 429 (quota/rate limit)."""

    status_code = 429
    error_code = "llm_rate_limit_error"
    default_detail = "LLM provider rate limit exceeded."


class LLMSchemaError(LLMError):
    """Raised when the model response does not match the expected schema."""

    status_code = 502
    error_code = "llm_schema_error"
    default_detail = "LLM response does not match the expected schema."
