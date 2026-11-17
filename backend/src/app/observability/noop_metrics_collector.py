"""No-op metrics until the observability implementation is installed."""

from collections.abc import Mapping

from src.app.interfaces.observability.metrics_collector import MetricsCollector


class NoopMetricsCollector(MetricsCollector):
    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        pass

    def observe_histogram(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        pass

    def set_gauge(self, name: str, value: float) -> None:
        pass
