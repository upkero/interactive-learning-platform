"""Prometheus metrics collector.

Every collector instance keeps its own metric objects (keyed by name), so
tests can use a private ``CollectorRegistry`` and never fight the global
one. Label names of a metric are fixed at first use: recording the same
name with a different tag set raises ``ValueError`` instead of silently
producing a series with mismatched labels.
"""

from collections.abc import Callable
from typing import TypeVar

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

from src.app.interfaces.observability.metrics_collector import MetricsCollector, MetricTags

M = TypeVar("M")

_Labelled = tuple[M, tuple[str, ...]]


def _label_names(tags: MetricTags | None) -> tuple[str, ...]:
    return tuple(sorted(tags.keys())) if tags else ()


class PrometheusMetricsCollector(MetricsCollector):
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or REGISTRY
        self._counters: dict[str, _Labelled[Counter]] = {}
        self._histograms: dict[str, _Labelled[Histogram]] = {}
        self._gauges: dict[str, _Labelled[Gauge]] = {}

    def _registered(
        self, cache: dict[str, _Labelled[M]], name: str, tags: MetricTags | None, factory: Callable[[], M]
    ) -> M:
        label_names = _label_names(tags)
        registered = cache.get(name)
        if registered is not None:
            metric, known_labels = registered
            if known_labels != label_names:
                raise ValueError(
                    f"Metric '{name}' is already registered with label names {list(known_labels)}, "
                    f"got {list(label_names)}"
                )
            return metric
        metric = factory()
        cache[name] = (metric, label_names)
        return metric

    def increment_counter(self, name: str, value: int = 1, tags: MetricTags | None = None) -> None:
        counter = self._registered(
            self._counters,
            name,
            tags,
            lambda: Counter(name.replace(".", "_"), name, labelnames=list(_label_names(tags)), registry=self._registry),
        )
        (counter.labels(**tags) if tags else counter).inc(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        def factory() -> Histogram:
            if buckets is None:
                return Histogram(
                    name.replace(".", "_"), name, labelnames=list(_label_names(tags)), registry=self._registry
                )
            return Histogram(
                name.replace(".", "_"),
                name,
                labelnames=list(_label_names(tags)),
                buckets=buckets,
                registry=self._registry,
            )

        histogram = self._registered(self._histograms, name, tags, factory)
        (histogram.labels(**tags) if tags else histogram).observe(value)

    def set_gauge(self, name: str, value: float, tags: MetricTags | None = None) -> None:
        gauge = self._registered(
            self._gauges,
            name,
            tags,
            lambda: Gauge(name.replace(".", "_"), name, labelnames=list(_label_names(tags)), registry=self._registry),
        )
        (gauge.labels(**tags) if tags else gauge).set(value)
