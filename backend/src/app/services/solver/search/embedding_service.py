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
from math import isfinite

import anyio.to_thread
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.app.embeddings.base import Embedder
from src.app.exceptions.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingGenerationError,
    EmbeddingResultMismatchError,
    EmptyEmbeddingInputError,
)
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.observability.metrics_collector import MetricsCollector

_LOGGER = logging.getLogger(__name__)

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
        logger: logging.Logger | None = None,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._embedder = embedder
        self._redis = redis
        self._metrics = metrics
        self._batch_size = batch_size
        self._ttl = ttl_seconds
        self._logger = logger or logger_ or _LOGGER
        self._vector_format = struct.Struct(f"<{embedder.dimension}f")

    @property
    def model_name(self) -> str:
        return self._embedder.model_name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        normalized = [" ".join(text.split()) for text in texts]
        if not normalized:
            return []
        if not all(normalized):
            raise EmptyEmbeddingInputError("Embedding input contains an empty text.")

        unique = list(dict.fromkeys(normalized))
        cached = await self._read_cache(unique)
        result = {text: vector for text, vector in zip(unique, cached, strict=True) if vector is not None}
        pending = [text for text in unique if text not in result]

        self._metrics.increment_counter(_CACHE_COUNTER, labels={"result": "hit"}, by=len(result))
        self._metrics.increment_counter(_CACHE_COUNTER, labels={"result": "miss"}, by=len(pending))

        for start in range(0, len(pending), self._batch_size):
            batch = pending[start : start + self._batch_size]
            vectors = await self._embed(batch)
            if len(vectors) != len(batch):
                raise EmbeddingResultMismatchError("Embedder returned a different number of vectors.")
            packed: dict[str, bytes] = {}
            for text, vector in zip(batch, vectors, strict=True):
                packed[text], result[text] = self._prepare_vector(vector)
            await self._write_cache(packed)

        return [result[text] for text in normalized]

    async def _embed(self, batch: Sequence[str]) -> list[list[float]]:
        try:
            return await anyio.to_thread.run_sync(self._embedder.embed, batch)
        except EmbeddingConfigurationError:
            raise
        except Exception as exc:
            raise EmbeddingGenerationError("Failed to generate embeddings.") from exc

    def _prepare_vector(self, vector: Sequence[float]) -> tuple[bytes, list[float]]:
        if len(vector) != self._embedder.dimension:
            raise EmbeddingResultMismatchError("Embedder returned a vector of the wrong dimension.")
        try:
            packed = self._vector_format.pack(*vector)
        except (OverflowError, struct.error) as exc:
            raise EmbeddingResultMismatchError("Embedder returned a value outside float32.") from exc
        decoded = self._decode(packed)
        if decoded is None:
            raise EmbeddingResultMismatchError("Embedder returned a non-finite value.")
        return packed, decoded

    def _key(self, text: str) -> str:
        return f"emb:{self._embedder.model_name}:{sha256(text.encode()).hexdigest()}"

    async def _read_cache(self, texts: Sequence[str]) -> list[list[float] | None]:
        try:
            raw = await self._redis.mget([self._key(text) for text in texts])
        except RedisError:
            self._logger.warning("Embedding cache read failed, treating as miss.", exc_info=True)
            return [None] * len(texts)
        if len(raw) != len(texts):
            self._logger.warning("Embedding cache returned an unexpected number of values, treating all as misses.")
            return [None] * len(texts)
        return [self._decode(item) for item in raw]

    async def _write_cache(self, vectors: dict[str, bytes]) -> None:
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                for text, vector in vectors.items():
                    pipe.set(self._key(text), vector, ex=self._ttl)
                await pipe.execute()
        except RedisError:
            self._logger.warning("Embedding cache write failed.", exc_info=True)

    def _decode(self, raw: bytes | None) -> list[float] | None:
        if not isinstance(raw, bytes) or len(raw) != self._vector_format.size:
            return None
        vector = list(self._vector_format.unpack(raw))
        return vector if all(isfinite(value) for value in vector) else None


__all__ = ["EmbeddingService"]
