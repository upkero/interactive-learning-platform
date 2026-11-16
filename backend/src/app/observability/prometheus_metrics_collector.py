"""Prometheus adapter for worker metrics (export is handled by story 1.8)."""

from collections.abc import Mapping

from prometheus_client import Counter

from src.app.interfaces.observability.metrics_collector import MetricsCollector

_WATCHDOG = Counter("watchdog_actions_total", "Watchdog recovery actions", ["action"])


class PrometheusMetricsCollector(MetricsCollector):
    """Collect the worker's supported counters in the process registry."""

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        if name == "watchdog_actions_total" and labels is not None:
            _WATCHDOG.labels(**labels).inc(by)

    def observe_histogram(self, name: str, value: float) -> None:
        raise NotImplementedError(name)

    def set_gauge(self, name: str, value: float) -> None:
        raise NotImplementedError(name)
