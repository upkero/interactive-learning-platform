"""Embedding service with a Redis cache and batching (story 2.3).

The service owns the cache and the batching contract:

- identical texts in one call are embedded once;
- cache keys are ``emb:{model}:{sha256(text)}`` and hold float32
  little-endian bytes, not JSON;
- Redis failures are a cache miss, never a failed embedding;
- model failures become ``EmbeddingGenerationError``;
- the returned list has the same length and order as the input.

The synchronous model is called through ``anyio.to_thread.run_sync`` so a
CPU-bound encode never blocks the event loop.
"""

import logging
import struct
from collections.abc import Sequence
from hashlib import sha256

import anyio.to_thread
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.app.embeddings.base import Embedder
from src.app.exceptions.embeddings import (
    EmbeddingGenerationError,
    EmbeddingResultMismatchError,
    EmptyEmbeddingInputError,
)
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.observability.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

_CACHE_COUNTER = "embedding_cache.requests"


class EmbeddingService(EmbeddingServiceInterface):
    def __init__(
        self,
        *,
        embedder: Embedder,
        redis: Redis,
        metrics: MetricsCollector,
        batch_size: int = 32,
        ttl_seconds: int = 30 * 24 * 3600,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._embedder = embedder
        self._redis = redis
        self._metrics = metrics
        self._batch_size = batch_size
        self._ttl = ttl_seconds
        self._logger = logger_ or logger

    @property
    def model_name(self) -> str:
        return self._embedder.model_name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        normalized = [" ".join(text.split()) for text in texts]
        if not normalized:
            return []
        if not all(normalized):
            raise EmptyEmbeddingInputError("Embedding input contains an empty text.")

        result: list[list[float] | None] = await self._read_cache(normalized)
        missing: dict[str, list[int]] = {}
        for index, vector in enumerate(result):
            if vector is None:
                missing.setdefault(normalized[index], []).append(index)

        hits = len(normalized) - sum(len(indices) for indices in missing.values())
        self._metrics.increment_counter(_CACHE_COUNTER, labels={"result": "hit"}, by=hits)
        self._metrics.increment_counter(_CACHE_COUNTER, labels={"result": "miss"}, by=len(missing))

        pending = list(missing)
        for start in range(0, len(pending), self._batch_size):
            batch = pending[start : start + self._batch_size]
            vectors = await self._embed(batch)
            self._validate(batch, vectors)
            for text, vector in zip(batch, vectors, strict=True):
                for index in missing[text]:
                    result[index] = vector
            await self._write_cache(dict(zip(batch, vectors, strict=True)))

        # Every slot is filled by a cache hit or by the model; the check keeps
        # mypy and a future refactor honest.
        if any(vector is None for vector in result):
            raise EmbeddingGenerationError("Embedding cache returned an incomplete result.")
        return [vector for vector in result if vector is not None]

    async def _embed(self, batch: Sequence[str]) -> list[list[float]]:
        try:
            return await anyio.to_thread.run_sync(self._embedder.embed, batch)
        except Exception as exc:
            raise EmbeddingGenerationError("Failed to generate embeddings.") from exc

    def _validate(self, batch: Sequence[str], vectors: Sequence[Sequence[float]]) -> None:
        if len(vectors) != len(batch):
            raise EmbeddingResultMismatchError("Embedder returned a different number of vectors.")
        for vector in vectors:
            if len(vector) != self._embedder.dimension:
                raise EmbeddingResultMismatchError("Embedder returned a vector of the wrong dimension.")

    def _key(self, text: str) -> str:
        return f"emb:{self._embedder.model_name}:{sha256(text.encode()).hexdigest()}"

    async def _read_cache(self, texts: Sequence[str]) -> list[list[float] | None]:
        try:
            raw = await self._redis.mget([self._key(text) for text in texts])
        except RedisError:
            self._logger.warning("Embedding cache read failed, treating as miss.", exc_info=True)
            return [None] * len(texts)
        return [self._decode(item) if item is not None else None for item in raw]

    async def _write_cache(self, vectors: dict[str, Sequence[float]]) -> None:
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                for text, vector in vectors.items():
                    pipe.set(self._key(text), _encode(vector), ex=self._ttl)
                await pipe.execute()
        except RedisError:
            self._logger.warning("Embedding cache write failed.", exc_info=True)

    def _decode(self, raw: bytes) -> list[float] | None:
        if len(raw) % 4:
            return None
        vector = list(struct.unpack(f"<{len(raw) // 4}f", raw))
        return vector if len(vector) == self._embedder.dimension else None


def _encode(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


__all__ = ["EmbeddingService"]
