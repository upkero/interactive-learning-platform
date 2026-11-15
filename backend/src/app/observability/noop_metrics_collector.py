"""No-op metrics until the observability implementation is installed."""

from src.app.interfaces.observability.metrics_collector import MetricsCollector


class NoopMetricsCollector(MetricsCollector):
    def increment_counter(self, name: str) -> None:
        pass

    def observe_histogram(self, name: str, value: float) -> None:
        pass

    def set_gauge(self, name: str, value: float) -> None:
        pass
