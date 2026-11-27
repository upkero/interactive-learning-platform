"""Unit tests of the instrumented embedding service (story 2.3)."""

from collections.abc import Sequence

import pytest

from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.services.solver.search.instrumented_embedding_service import InstrumentedEmbeddingService
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector


class FakeService(EmbeddingServiceInterface):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.error = RuntimeError("model failed")
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            raise self.error
        return [[float(len(text))] for text in texts]


async def test_success_records_duration_without_error() -> None:
    metrics = RecordingMetricsCollector()
    service = InstrumentedEmbeddingService(service=FakeService(), metrics=metrics)

    assert await service.embed(["a", "bb"]) == [[1.0], [2.0]]

    histograms = metrics.histograms_named("embeddings.create_duration_seconds")
    assert len(histograms) == 1
    assert histograms[0].value >= 0.0
    assert metrics.counters_named("embeddings.create_errors") == []


async def test_failure_records_error_and_duration_then_reraises() -> None:
    metrics = RecordingMetricsCollector()
    underlying = FakeService(fail=True)
    service = InstrumentedEmbeddingService(service=underlying, metrics=metrics)

    with pytest.raises(RuntimeError, match="model failed") as error:
        await service.embed(["a"])

    assert error.value is underlying.error
    assert len(metrics.counters_named("embeddings.create_errors")) == 1
    assert len(metrics.histograms_named("embeddings.create_duration_seconds")) == 1
