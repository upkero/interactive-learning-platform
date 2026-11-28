"""Public interfaces of the embedding service and its cache (story 2.3)."""

from collections.abc import Awaitable, Iterable, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol


class EmbeddingServiceInterface(Protocol):
    """What the solver depends on; the embedder model stays behind it."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class EmbeddingCachePipelineProtocol(Protocol):
    """The subset of a Redis pipeline used to populate the cache."""

    def set(self, key: str, value: bytes, *, ex: int | None = None) -> object: ...

    async def execute(self) -> object: ...


class EmbeddingCacheProtocol(Protocol):
    """The subset of Redis used by the embedding cache.

    Keeping this contract structural lets the production Redis client and
    the in-memory test double exercise the same implementation.
    """

    def mget(
        self,
        keys: bytes | str | memoryview | Iterable[bytes | str | memoryview],
        *args: bytes | bytearray | memoryview | str | int | float,
    ) -> Awaitable[Sequence[bytes | None]]: ...

    def pipeline(self, *, transaction: bool = True) -> AbstractAsyncContextManager[EmbeddingCachePipelineProtocol]: ...


__all__ = [
    "EmbeddingCachePipelineProtocol",
    "EmbeddingCacheProtocol",
    "EmbeddingServiceInterface",
]
