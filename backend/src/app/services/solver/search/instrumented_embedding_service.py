"""Metrics wrapper of the embedding service (story 2.3)."""

from collections.abc import Sequence
from time import perf_counter

from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.observability.metrics_collector import MetricsCollector

_DURATION_HISTOGRAM = "embeddings.create_duration_seconds"
_ERROR_COUNTER = "embeddings.create_errors"


class InstrumentedEmbeddingService(EmbeddingServiceInterface):
    """Records the wall time of every embed call, including cache hits."""

    def __init__(self, *, service: EmbeddingServiceInterface, metrics: MetricsCollector) -> None:
        self._service = service
        self._metrics = metrics

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        started = perf_counter()
        try:
            return await self._service.embed(texts)
        except Exception:
            self._metrics.increment_counter(_ERROR_COUNTER)
            raise
        finally:
            self._metrics.observe_histogram(_DURATION_HISTOGRAM, perf_counter() - started)


__all__ = ["InstrumentedEmbeddingService"]
