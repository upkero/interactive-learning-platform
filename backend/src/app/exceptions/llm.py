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


class LLMTimeoutError(LLMGenerationError):
    """Raised when the provider does not answer within the timeout.

    Own outcome (``timeout``) on the dashboard: a timeout is a slow
    generation, not a failed one — the model might still be sound.
    """

    error_code = "llm_timeout_error"
    default_detail = "LLM provider request timed out."


class LLMOutputTruncatedError(LLMGenerationError):
    """Raised when the provider cut the reply off (stop_reason=max_tokens).

    Distinct from LLMSchemaError on purpose: a truncated reply fails the
    schema for the same reason every time, so call_structured must NOT
    retry it (the retry would pay for the same failure twice).
    """

    error_code = "llm_output_truncated_error"
    default_detail = "LLM output was truncated by the max_tokens limit."


class LLMRateLimitError(LLMError):
    """Raised when the provider returns 429 (quota/rate limit)."""

    status_code = 429
    error_code = "llm_rate_limit_error"
    default_detail = "LLM provider rate limit exceeded."


class LLMSchemaError(LLMError):
    """Raised when the model response does not match the expected schema.

    ``raw_output`` carries the unvalidated provider reply: call_structured
    feeds it back as an assistant message so the retry shows the model its
    own broken output next to the correction hint.
    """

    status_code = 502
    error_code = "llm_schema_error"
    default_detail = "LLM response does not match the expected schema."

    def __init__(self, detail: str | None = None, *, raw_output: str | None = None) -> None:
        super().__init__(detail)
        self.raw_output = raw_output
