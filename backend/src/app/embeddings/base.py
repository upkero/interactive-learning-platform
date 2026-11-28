"""Synchronous embedder interface (story 2.3).

An embedder is a model wrapper, not a service: it is synchronous, has no
cache and no metrics. Only ``embeddings/factory.py`` constructs concrete
models; the rest of the app sees ``EmbeddingServiceInterface``.
"""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Model wrapper: one call, vectors in the same order as texts."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


__all__ = ["Embedder"]
