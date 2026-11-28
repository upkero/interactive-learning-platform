"""Voyage API embedder (story 2.3).

The embedding is symmetric (``input_type=None``): an intent and a widget
description are both short behaviour descriptions, so they share one
vector space and one cache key format
``emb:{model}:{revision}:{sha256(text)}``.
"""

from collections.abc import Sequence

from pydantic import SecretStr

from src.app.exceptions.embeddings import EmbeddingConfigurationError

VOYAGE_MODEL = "voyage-3.5"
VOYAGE_DIMENSION = 1024


class VoyageEmbedder:
    """Thin wrapper around the synchronous Voyage client."""

    def __init__(self, *, api_key: SecretStr, model_name: str = VOYAGE_MODEL, max_retries: int | None = None) -> None:
        try:
            from voyageai.client import Client
        except ImportError as exc:  # pragma: no cover - depends on the install extra
            raise EmbeddingConfigurationError(
                "voyageai is not installed; install the embeddings-voyage extra."
            ) from exc
        self._model_name = model_name
        self._total_tokens = 0
        if max_retries is None:
            self._client = Client(api_key=api_key.get_secret_value())
        else:
            self._client = Client(api_key=api_key.get_secret_value(), max_retries=max_retries)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return VOYAGE_DIMENSION

    @property
    def total_tokens(self) -> int:
        """Total usage reported in successful API responses for this instance."""
        return self._total_tokens

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._client.embed(
            list(texts),
            model=self._model_name,
            input_type=None,
            output_dimension=self.dimension,
        )
        self._total_tokens += result.total_tokens
        return [[float(value) for value in vector] for vector in result.embeddings]


__all__ = ["VOYAGE_DIMENSION", "VOYAGE_MODEL", "VoyageEmbedder"]
