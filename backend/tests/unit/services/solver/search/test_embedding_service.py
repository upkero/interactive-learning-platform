"""Unit tests of the embedding service (story 2.3)."""

import hashlib
import inspect
import struct
from collections.abc import Sequence

import pytest

from src.app.core.settings.embeddings import BGE_M3_REVISION
from src.app.embeddings.base import Embedder
from src.app.exceptions.embeddings import (
    EmbeddingGenerationError,
    EmbeddingResultMismatchError,
    EmptyEmbeddingInputError,
)
from src.app.services.solver.search.embedding_service import EmbeddingService
from tests.support.fakes.cache.redis import FakeRedis
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

REVISION = BGE_M3_REVISION


class FakeEmbedder(Embedder):
    """Deterministic vector per text; records every model call."""

    model_name = "fake-model"
    dimension = 4

    def __init__(
        self,
        *,
        fail: Exception | None = None,
        vector_count: int | None = None,
        returned_dimension: int | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail
        self._vector_count = vector_count
        self._returned_dimension = returned_dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._fail is not None:
            raise self._fail
        vectors = [self._vector(text) for text in texts]
        if self._vector_count is not None:
            return vectors[: self._vector_count]
        return vectors

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        dimension = self._returned_dimension or self.dimension
        return [float(byte) for byte in digest[:dimension]]


def _service(
    *,
    embedder: FakeEmbedder | None = None,
    redis: FakeRedis | None = None,
    metrics: RecordingMetricsCollector | None = None,
    revision: str = REVISION,
    batch_size: int = 32,
    ttl_seconds: int = 30 * 24 * 3600,
) -> tuple[EmbeddingService, FakeEmbedder, FakeRedis, RecordingMetricsCollector]:
    model = embedder or FakeEmbedder()
    cache = redis or FakeRedis()
    collector = metrics or RecordingMetricsCollector()
    service = EmbeddingService(
        embedder=model,
        redis=cache,
        metrics=collector,
        revision=revision,
        batch_size=batch_size,
        ttl_seconds=ttl_seconds,
    )
    return service, model, cache, collector


def _key(text: str, revision: str = REVISION) -> str:
    return f"emb:fake-model:{revision}:{hashlib.sha256(text.encode()).hexdigest()}"


async def test_duplicate_texts_are_embedded_once_and_cached() -> None:
    service, embedder, redis, metrics = _service()

    first = await service.embed(["alpha", "beta", "alpha"])

    assert len(first) == 3
    assert first[0] == first[2]
    assert embedder.calls == [["alpha", "beta"]]
    assert len(redis.mget_calls) == 1
    assert redis.mget_calls[0] == [_key("alpha"), _key("beta")]
    assert len(redis.set_calls) == 2
    assert all(ex == 30 * 24 * 3600 for _, _, ex in redis.set_calls)
    assert redis.set_calls[0][1] == struct.pack("<4f", *first[0])
    cache_counters = metrics.counters_named("embedding_cache.requests")
    assert [(counter.labels["result"], counter.by) for counter in cache_counters] == [
        ("hit", 0),
        ("miss", 2),
    ]

    second = await service.embed(["alpha", "beta", "alpha"])

    assert second == first
    assert embedder.calls == [["alpha", "beta"]]
    assert len(redis.mget_calls) == 2
    cache_counters = metrics.counters_named("embedding_cache.requests")
    assert [(counter.labels["result"], counter.by) for counter in cache_counters[-2:]] == [
        ("hit", 2),
        ("miss", 0),
    ]


async def test_cache_key_contains_model_revision_and_sha256() -> None:
    service, _, redis, _ = _service()

    await service.embed(["hello world"])

    assert redis.mget_calls == [[_key("hello world")]]
    assert redis.set_calls[0][0] == _key("hello world")


async def test_cache_key_separates_revisions_and_same_revision_hits() -> None:
    cache = FakeRedis()
    service_a, embedder_a, _, _ = _service(redis=cache, revision="revision-a")
    service_b, embedder_b, _, _ = _service(redis=cache, revision="revision-b")

    await service_a.embed(["hello world"])
    await service_b.embed(["hello world"])
    await service_a.embed(["hello world"])

    assert embedder_a.calls == [["hello world"]]
    assert embedder_b.calls == [["hello world"]]
    assert set(cache.store) == {_key("hello world", "revision-a"), _key("hello world", "revision-b")}


def test_logger_api_has_no_duplicate_parameters() -> None:
    parameters = inspect.signature(EmbeddingService).parameters

    assert "logger" not in parameters
    assert "logger_" not in parameters


async def test_seventy_texts_with_duplicates_use_three_batches() -> None:
    texts = [f"text-{index}" for index in range(65)] + [f"text-{index}" for index in range(5)]
    service, embedder, _, _ = _service()

    vectors = await service.embed(texts)

    assert len(vectors) == 70
    assert [len(batch) for batch in embedder.calls] == [32, 32, 1]
    assert vectors[65:] == vectors[:5]
    assert len({tuple(vector) for vector in vectors}) == 65


async def test_redis_failure_is_a_cache_miss_and_does_not_fail_embedding(
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis = FakeRedis(fail_reads=True, fail_writes=True)
    service, embedder, _, _ = _service(redis=redis)

    with caplog.at_level("WARNING"):
        vectors = await service.embed(["alpha", "beta"])

    assert len(vectors) == 2
    assert embedder.calls == [["alpha", "beta"]]
    assert "cache read failed" in caplog.text
    assert "cache write failed" in caplog.text


async def test_corrupt_or_wrong_dimension_cache_value_is_a_miss() -> None:
    redis = FakeRedis()
    redis.store[_key("alpha")] = b"\x00\x01\x02"
    redis.store[_key("beta")] = struct.pack("<3f", 1.0, 2.0, 3.0)
    redis.store[_key("gamma")] = struct.pack("<4f", 1.0, 2.0, 3.0, float("nan"))
    service, embedder, _, _ = _service(redis=redis)

    vectors = await service.embed(["alpha", "beta", "gamma"])

    assert len(vectors) == 3
    assert embedder.calls == [["alpha", "beta", "gamma"]]
    assert all(len(vector) == 4 for vector in vectors)


async def test_empty_input_is_rejected_before_any_call() -> None:
    service, embedder, redis, _ = _service()

    with pytest.raises(EmptyEmbeddingInputError):
        await service.embed(["alpha", "   "])

    assert embedder.calls == []
    assert redis.mget_calls == []


async def test_empty_sequence_returns_empty_list() -> None:
    service, embedder, redis, _ = _service()

    assert await service.embed([]) == []
    assert embedder.calls == []
    assert redis.mget_calls == []


async def test_model_error_becomes_generation_error() -> None:
    service, _, _, _ = _service(embedder=FakeEmbedder(fail=RuntimeError("boom")))

    with pytest.raises(EmbeddingGenerationError) as error:
        await service.embed(["alpha"])

    assert isinstance(error.value.__cause__, RuntimeError)


async def test_wrong_vector_count_is_rejected() -> None:
    service, _, _, _ = _service(embedder=FakeEmbedder(vector_count=1))

    with pytest.raises(EmbeddingResultMismatchError):
        await service.embed(["alpha", "beta"])


async def test_wrong_vector_dimension_is_rejected() -> None:
    service, _, _, _ = _service(embedder=FakeEmbedder(returned_dimension=3))

    with pytest.raises(EmbeddingResultMismatchError):
        await service.embed(["alpha"])


async def test_vectors_are_normalised_before_embedding() -> None:
    service, embedder, _, _ = _service()

    await service.embed(["  alpha \n  beta  "])

    assert embedder.calls == [["alpha beta"]]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e100])
async def test_invalid_float32_from_model_is_rejected(value: float, monkeypatch: pytest.MonkeyPatch) -> None:
    service, embedder, redis, _ = _service()
    monkeypatch.setattr(embedder, "embed", lambda _texts: [[value, 1.0, 2.0, 3.0]])

    with pytest.raises(EmbeddingResultMismatchError):
        await service.embed(["alpha"])

    assert redis.set_calls == []


async def test_float32_output_stays_identical_on_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    service, embedder, redis, _ = _service()
    monkeypatch.setattr(embedder, "embed", lambda _texts: [[0.1, 0.2, 0.3, 0.4]])

    first = await service.embed(["alpha"])
    second = await service.embed(["alpha"])

    assert first == second
    assert len(redis.set_calls) == 1
