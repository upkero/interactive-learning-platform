"""Noop collector: for tests and local runs without metrics export."""

from src.app.interfaces.observability.metrics_collector import MetricsCollector, MetricTags


class NoopMetricsCollector(MetricsCollector):
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        tags: MetricTags | None = None,
    ) -> None:
        return None

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        return None

    def set_gauge(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
    ) -> None:
        return None
