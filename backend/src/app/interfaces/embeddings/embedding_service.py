"""Public interface of the embedding service (story 2.3)."""

from collections.abc import Sequence
from typing import Protocol


class EmbeddingServiceInterface(Protocol):
    """What the solver depends on; the embedder model stays behind it."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


__all__ = ["EmbeddingServiceInterface"]
