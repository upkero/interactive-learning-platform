"""Recording MetricsCollector: unit tests assert on captured metric calls."""

from dataclasses import dataclass

from src.app.interfaces.observability.metrics_collector import MetricsCollector, MetricTags


@dataclass(frozen=True)
class RecordedCounter:
    name: str
    value: int
    tags: MetricTags | None


@dataclass(frozen=True)
class RecordedHistogram:
    name: str
    value: float
    tags: MetricTags | None
    buckets: tuple[float, ...] | None


@dataclass(frozen=True)
class RecordedGauge:
    name: str
    value: float
    tags: MetricTags | None


class RecordingMetricsCollector(MetricsCollector):
    def __init__(self) -> None:
        self.counters: list[RecordedCounter] = []
        self.histograms: list[RecordedHistogram] = []
        self.gauges: list[RecordedGauge] = []

    def increment_counter(self, name: str, value: int = 1, tags: MetricTags | None = None) -> None:
        self.counters.append(RecordedCounter(name=name, value=value, tags=tags))

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.histograms.append(RecordedHistogram(name=name, value=value, tags=tags, buckets=buckets))

    def set_gauge(self, name: str, value: float, tags: MetricTags | None = None) -> None:
        self.gauges.append(RecordedGauge(name=name, value=value, tags=tags))

    def counters_named(self, name: str) -> list[RecordedCounter]:
        return [counter for counter in self.counters if counter.name == name]

    def histograms_named(self, name: str) -> list[RecordedHistogram]:
        return [histogram for histogram in self.histograms if histogram.name == name]
