"""Recording metrics collector for service tests."""

from collections.abc import Callable

from src.app.observability.noop_metrics_collector import NoopMetricsCollector


class RecordingMetricsCollector(NoopMetricsCollector):
    def __init__(self, on_increment: Callable[[], None] | None = None) -> None:
        self.counters: list[str] = []
        self.on_increment = on_increment

    def increment_counter(self, name: str) -> None:
        self.counters.append(name)
        if self.on_increment is not None:
            self.on_increment()
