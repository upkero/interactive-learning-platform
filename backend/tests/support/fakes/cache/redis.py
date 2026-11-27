"""In-memory Redis double for the embedding cache tests."""

from collections.abc import Iterable
from typing import Any

from redis.exceptions import RedisError

from src.app.interfaces.embeddings.embedding_service import (
    EmbeddingCachePipelineProtocol,
    EmbeddingCacheProtocol,
)


class FakePipeline(EmbeddingCachePipelineProtocol):
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._operations: list[tuple[str, bytes, int | None]] = []

    async def __aenter__(self) -> "FakePipeline":
        if self._redis.fail_writes:
            raise RedisError("write failed")
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def set(self, key: str, value: bytes, *, ex: int | None = None) -> "FakePipeline":
        self._operations.append((key, value, ex))
        return self

    async def execute(self) -> list[bool]:
        if self._redis.fail_writes:
            raise RedisError("write failed")
        for key, value, ex in self._operations:
            self._redis.store[key] = value
            self._redis.set_calls.append((key, value, ex))
        return [True] * len(self._operations)


class FakeRedis(EmbeddingCacheProtocol):
    """Small subset of redis.asyncio used by ``EmbeddingService``."""

    def __init__(self, *, fail_reads: bool = False, fail_writes: bool = False) -> None:
        self.store: dict[str, bytes] = {}
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes
        self.mget_calls: list[list[str]] = []
        self.set_calls: list[tuple[str, bytes, int | None]] = []

    async def mget(
        self,
        keys: bytes | str | memoryview | Iterable[bytes | str | memoryview],
        *args: bytes | bytearray | memoryview | str | int | float,
    ) -> list[bytes | None]:
        del args
        decoded = [self._decode_key(key) for key in self._keys(keys)]
        self.mget_calls.append(decoded)
        if self.fail_reads:
            raise RedisError("read failed")
        return [self.store.get(key) for key in decoded]

    @staticmethod
    def _keys(
        keys: bytes | str | memoryview | Iterable[bytes | str | memoryview],
    ) -> list[bytes | str | memoryview]:
        if isinstance(keys, (bytes, str, memoryview)):
            return [keys]
        return list(keys)

    @staticmethod
    def _decode_key(key: bytes | str | memoryview) -> str:
        if isinstance(key, str):
            return key
        if isinstance(key, bytes):
            return key.decode()
        return key.tobytes().decode()

    def pipeline(self, *, transaction: bool = True) -> FakePipeline:
        del transaction
        return FakePipeline(self)

    async def aclose(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
        raise AttributeError(f"FakeRedis has no attribute {name}")


__all__ = ["FakePipeline", "FakeRedis"]
