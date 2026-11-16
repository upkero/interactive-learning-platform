"""Prometheus adapter for worker metrics (export is handled by story 1.8)."""

import logging
from collections.abc import Mapping
from threading import Lock

from prometheus_client import Counter, Gauge, Histogram

from src.app.interfaces.observability.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

_COUNTERS: dict[str, tuple[Counter, tuple[str, ...]]] = {}
_HISTOGRAMS: dict[str, Histogram] = {}
_GAUGES: dict[str, Gauge] = {}
_REGISTRY_LOCK = Lock()


class PrometheusMetricsCollector(MetricsCollector):
    """Create named metrics on first use and keep them in the default registry."""

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        provided = dict(labels or {})
        counter, label_names = self._counter(name, provided)
        unexpected = set(provided) - set(label_names)
        if unexpected:
            logger.warning("metrics.unexpected_labels", extra={"metric": name, "labels": sorted(unexpected)})
        counter.labels(**{label: provided.get(label, "") for label in label_names}).inc(by)

    def observe_histogram(self, name: str, value: float) -> None:
        with _REGISTRY_LOCK:
            histogram = _HISTOGRAMS.get(name)
            if histogram is None:
                histogram = Histogram(name, f"Grasp histogram {name}")
                _HISTOGRAMS[name] = histogram
        histogram.observe(value)

    def set_gauge(self, name: str, value: float) -> None:
        with _REGISTRY_LOCK:
            gauge = _GAUGES.get(name)
            if gauge is None:
                gauge = Gauge(name, f"Grasp gauge {name}")
                _GAUGES[name] = gauge
        gauge.set(value)

    @staticmethod
    def _counter(name: str, labels: Mapping[str, str]) -> tuple[Counter, tuple[str, ...]]:
        provided = tuple(labels)
        with _REGISTRY_LOCK:
            entry = _COUNTERS.get(name)
            if entry is None:
                entry = (Counter(name, f"Grasp counter {name}", provided), provided)
                _COUNTERS[name] = entry
            return entry
