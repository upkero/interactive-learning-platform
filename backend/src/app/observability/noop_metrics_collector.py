"""No-op metrics collector: drops everything.

Placeholder until the metrics export story (1.9) brings the real
collector; the LLM metrics themselves are already exercised by the
InstrumentedLLMClient unit tests on RecordingMetricsCollector.
"""

from src.app.interfaces.observability.metrics_collector import MetricTags


class NoopMetricsCollector:
    def increment_counter(self, name: str, value: int = 1, tags: MetricTags | None = None) -> None:
        return

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        return

    def set_gauge(self, name: str, value: float, tags: MetricTags | None = None) -> None:
        return
