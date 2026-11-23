"""Factory of embedders (story 2.3).

Only this module constructs concrete models. The process-wide cache keeps
one model per worker: the container calls ``get_embedder`` on first use and
every later call gets the same object. ``reset_embedder`` exists for tests
and for a future hot reload of the provider.
"""

from threading import Lock

from src.app.core.settings.embeddings import EmbeddingsSettings, get_embeddings_settings
from src.app.embeddings.base import Embedder
from src.app.embeddings.bge_m3 import BgeM3Embedder
from src.app.embeddings.voyage import VoyageEmbedder
from src.app.exceptions.embeddings import EmbeddingConfigurationError

_EMBEDDER: Embedder | None = None
_LOCK = Lock()


def create_embedder(settings: EmbeddingsSettings) -> Embedder:
    """Build a new embedder for the selected provider."""
    if settings.provider == "bge_m3":
        return BgeM3Embedder(device=settings.device)
    if settings.voyage_api_key is None:
        raise EmbeddingConfigurationError("VOYAGE_API_KEY is required for the voyage provider.")
    return VoyageEmbedder(api_key=settings.voyage_api_key)


def get_embedder(settings: EmbeddingsSettings | None = None) -> Embedder:
    """Return the process-wide embedder, creating and loading it once."""
    global _EMBEDDER
    if _EMBEDDER is None:
        with _LOCK:
            if _EMBEDDER is None:
                _EMBEDDER = create_embedder(settings or get_embeddings_settings())
    return _EMBEDDER


def reset_embedder() -> None:
    """Drop the cached model; the next call creates a fresh one."""
    global _EMBEDDER
    with _LOCK:
        _EMBEDDER = None


__all__ = ["create_embedder", "get_embedder", "reset_embedder"]
