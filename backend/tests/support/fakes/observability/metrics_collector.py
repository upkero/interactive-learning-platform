"""Recording metrics collector for service tests."""

from collections.abc import Callable, Mapping

from src.app.observability.noop_metrics_collector import NoopMetricsCollector


class RecordingMetricsCollector(NoopMetricsCollector):
    def __init__(self, on_increment: Callable[[], None] | None = None) -> None:
        self.counters: list[str] = []
        self.labeled_counters: list[tuple[str, dict[str, str], int]] = []
        self.on_increment = on_increment

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        self.counters.append(name)
        self.labeled_counters.append((name, dict(labels or {}), by))
        if self.on_increment is not None:
            self.on_increment()
