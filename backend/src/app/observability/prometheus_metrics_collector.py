"""Prometheus metrics. Objects are cached by name so tags do not spawn series."""

from prometheus_client import Counter, Gauge, Histogram

from src.app.interfaces.observability.metrics_collector import MetricsCollector, MetricTags

_counters: dict[str, Counter] = {}
_histograms: dict[str, Histogram] = {}
_gauges: dict[str, Gauge] = {}


def _label_names(tags: MetricTags | None) -> list[str]:
    return sorted(tags.keys()) if tags else []


def _get_counter(name: str, tags: MetricTags | None) -> Counter:
    if name not in _counters:
        _counters[name] = Counter(name.replace(".", "_"), name, labelnames=_label_names(tags))
    return _counters[name]


def _get_histogram(
    name: str,
    tags: MetricTags | None,
    buckets: tuple[float, ...] | None,
) -> Histogram:
    if name not in _histograms:
        kwargs: dict[str, object] = {"labelnames": _label_names(tags)}
        if buckets is not None:
            kwargs["buckets"] = buckets
        _histograms[name] = Histogram(name.replace(".", "_"), name, **kwargs)  # type: ignore[arg-type]
    return _histograms[name]


def _get_gauge(name: str, tags: MetricTags | None) -> Gauge:
    if name not in _gauges:
        _gauges[name] = Gauge(name.replace(".", "_"), name, labelnames=_label_names(tags))
    return _gauges[name]


class PrometheusMetricsCollector(MetricsCollector):
    def increment_counter(self, name: str, value: int = 1, tags: MetricTags | None = None) -> None:
        counter = _get_counter(name, tags)
        (counter.labels(**tags) if tags else counter).inc(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        histogram = _get_histogram(name, tags, buckets)
        (histogram.labels(**tags) if tags else histogram).observe(value)

    def set_gauge(self, name: str, value: float, tags: MetricTags | None = None) -> None:
        gauge = _get_gauge(name, tags)
        (gauge.labels(**tags) if tags else gauge).set(value)
