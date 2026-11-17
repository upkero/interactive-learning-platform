"""Prometheus adapter for worker metrics (export is handled by story 1.8)."""

import logging
import re
from collections.abc import Mapping
from threading import Lock

from prometheus_client import Counter, Gauge, Histogram

from src.app.interfaces.observability.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

_PROMETHEUS_NAME = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*")

_COUNTERS: dict[str, tuple[Counter, tuple[str, ...]]] = {}
_HISTOGRAMS: dict[str, Histogram] = {}
_GAUGES: dict[str, Gauge] = {}
_REGISTRY_LOCK = Lock()


def _metric_name(name: str) -> str | None:
    """Normalize dots and reject names Prometheus cannot register."""
    normalized = name.replace(".", "_")
    if _PROMETHEUS_NAME.fullmatch(normalized) is None:
        logger.warning("metrics.invalid_name", extra={"metric": name})
        return None
    return normalized


class PrometheusMetricsCollector(MetricsCollector):
    """Create named metrics on first use and keep them in the default registry."""

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        metric_name = _metric_name(name)
        if metric_name is None:
            return
        provided = dict(labels or {})
        counter, label_names = self._counter(metric_name, provided)
        if not label_names:
            if provided:
                logger.warning("metrics.unexpected_labels", extra={"metric": name, "labels": sorted(provided)})
            counter.inc(by)
            return
        unexpected = set(provided) - set(label_names)
        if unexpected:
            logger.warning("metrics.unexpected_labels", extra={"metric": name, "labels": sorted(unexpected)})
        counter.labels(**{label: provided.get(label, "") for label in label_names}).inc(by)

    def observe_histogram(self, name: str, value: float) -> None:
        metric_name = _metric_name(name)
        if metric_name is None:
            return
        with _REGISTRY_LOCK:
            histogram = _HISTOGRAMS.get(metric_name)
            if histogram is None:
                histogram = Histogram(metric_name, f"Grasp histogram {metric_name}")
                _HISTOGRAMS[metric_name] = histogram
        histogram.observe(value)

    def set_gauge(self, name: str, value: float) -> None:
        metric_name = _metric_name(name)
        if metric_name is None:
            return
        with _REGISTRY_LOCK:
            gauge = _GAUGES.get(metric_name)
            if gauge is None:
                gauge = Gauge(metric_name, f"Grasp gauge {metric_name}")
                _GAUGES[metric_name] = gauge
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
