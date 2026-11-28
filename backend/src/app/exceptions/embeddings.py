"""Exceptions of the embeddings layer (story 2.3)."""

from src.app.exceptions.base import BaseAppException


class EmbeddingError(BaseAppException):
    """Base exception of the embedding layer."""

    error_code = "embedding_error"
    default_detail = "Embedding operation failed."


class EmbeddingConfigurationError(EmbeddingError):
    """The selected provider cannot be created (dependency or key missing)."""

    error_code = "embedding_configuration_error"
    default_detail = "Embedding provider is not configured."


class EmbeddingGenerationError(EmbeddingError):
    """The model failed to generate vectors."""

    error_code = "embedding_generation_error"
    default_detail = "Embedding generation failed."


class EmbeddingResultMismatchError(EmbeddingGenerationError):
    """The embedder returned an invalid shape or vector value."""

    error_code = "embedding_result_mismatch"
    default_detail = "Embedder returned an invalid result."


class EmptyEmbeddingInputError(EmbeddingError, ValueError):
    """A text to embed is empty after whitespace normalisation."""

    status_code = 422
    error_code = "empty_embedding_input"
    default_detail = "Embedding input contains an empty text."


__all__ = [
    "EmbeddingConfigurationError",
    "EmbeddingError",
    "EmbeddingGenerationError",
    "EmbeddingResultMismatchError",
    "EmptyEmbeddingInputError",
]
