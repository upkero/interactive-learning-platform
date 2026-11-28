"""Factory of embedders (story 2.3).

Only this module constructs concrete models. The process-wide cache keeps
one model per worker. The container supplies a lazy embedder so the worker
thread handles both first model load and encoding.
"""

from collections.abc import Sequence
from threading import Lock

from pydantic import SecretStr

from src.app.core.settings.embeddings import EmbeddingsProvider, EmbeddingsSettings, get_embeddings_settings
from src.app.embeddings.base import Embedder
from src.app.embeddings.bge_m3 import BGE_M3_DIMENSION, BGE_M3_MODEL, BgeM3Embedder
from src.app.embeddings.voyage import VOYAGE_DIMENSION, VOYAGE_MODEL, VoyageEmbedder
from src.app.exceptions.embeddings import EmbeddingConfigurationError

_EMBEDDERS: dict[tuple[EmbeddingsProvider, str | SecretStr | None, str], Embedder] = {}
_LOCK = Lock()


class LazyEmbedder:
    """Expose cache metadata before loading the synchronous model."""

    def __init__(self, settings: EmbeddingsSettings) -> None:
        self._settings = settings

    @property
    def model_name(self) -> str:
        return BGE_M3_MODEL if self._settings.provider == "bge_m3" else VOYAGE_MODEL

    @property
    def dimension(self) -> int:
        return BGE_M3_DIMENSION if self._settings.provider == "bge_m3" else VOYAGE_DIMENSION

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return get_embedder(self._settings).embed(texts)


def create_embedder(settings: EmbeddingsSettings, *, voyage_max_retries: int | None = None) -> Embedder:
    """Build a new embedder for the selected provider."""
    if settings.provider == "bge_m3":
        return BgeM3Embedder(device=settings.device, revision=settings.revision)
    if settings.voyage_api_key is None:
        raise EmbeddingConfigurationError("VOYAGE_API_KEY is required for the voyage provider.")
    if voyage_max_retries is not None:
        return VoyageEmbedder(api_key=settings.voyage_api_key, max_retries=voyage_max_retries)
    return VoyageEmbedder(api_key=settings.voyage_api_key)


def get_embedder(settings: EmbeddingsSettings | None = None) -> Embedder:
    """Load one model per provider configuration in the process."""
    settings = settings or get_embeddings_settings()
    option = settings.device if settings.provider == "bge_m3" else settings.voyage_api_key
    key = (settings.provider, option, settings.revision)
    with _LOCK:
        existing = _EMBEDDERS.get(key)
        if existing is None:
            existing = _EMBEDDERS[key] = create_embedder(settings)
        return existing


def reset_embedder() -> None:
    """Drop cached models; the next calls create fresh ones."""
    with _LOCK:
        _EMBEDDERS.clear()


__all__ = ["LazyEmbedder", "create_embedder", "get_embedder", "reset_embedder"]
