"""Recording metrics collector for service tests."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from src.app.observability.noop_metrics_collector import NoopMetricsCollector


@dataclass(frozen=True)
class RecordedCounter:
    name: str
    labels: dict[str, str]
    by: int


@dataclass(frozen=True)
class RecordedHistogram:
    name: str
    value: float
    labels: dict[str, str]
    buckets: tuple[float, ...] | None


@dataclass(frozen=True)
class RecordedGauge:
    name: str
    value: float


class RecordingMetricsCollector(NoopMetricsCollector):
    def __init__(self, on_increment: Callable[[], None] | None = None) -> None:
        self.counters: list[str] = []
        self.labeled_counters: list[tuple[str, dict[str, str], int]] = []
        self.histograms: list[RecordedHistogram] = []
        self.gauges: list[RecordedGauge] = []
        self.on_increment = on_increment

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        self.counters.append(name)
        self.labeled_counters.append((name, dict(labels or {}), by))
        if self.on_increment is not None:
            self.on_increment()

    def observe_histogram(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.histograms.append(RecordedHistogram(name=name, value=value, labels=dict(labels or {}), buckets=buckets))

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges.append(RecordedGauge(name=name, value=value))

    def counters_named(self, name: str) -> list[RecordedCounter]:
        return [RecordedCounter(name=n, labels=labels, by=by) for n, labels, by in self.labeled_counters if n == name]

    def histograms_named(self, name: str) -> list[RecordedHistogram]:
        return [histogram for histogram in self.histograms if histogram.name == name]

    def gauges_named(self, name: str) -> list[RecordedGauge]:
        return [gauge for gauge in self.gauges if gauge.name == name]
