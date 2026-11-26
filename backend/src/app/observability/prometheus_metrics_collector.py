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
_HISTOGRAMS: dict[str, tuple[Histogram, tuple[str, ...], tuple[float, ...] | None]] = {}
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
    """Create named metrics on first use and keep them in the default registry.

    A counter fixes its label set on the first call: later calls with extra
    labels log ``metrics.unexpected_labels`` and drop them. A histogram fixes
    its label set and buckets on the first call the same way; a later call
    with different buckets logs ``metrics.buckets_mismatch`` and observes
    into the original metric. Story 1.8 must use one stable label and bucket
    schema per metric name. Dots in names are normalized to underscores;
    names Prometheus cannot register are logged and skipped.
    """

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

    def observe_histogram(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        metric_name = _metric_name(name)
        if metric_name is None:
            return
        provided = dict(labels or {})
        histogram, label_names = self._histogram(metric_name, provided, buckets)
        unexpected = set(provided) - set(label_names)
        if unexpected:
            logger.warning("metrics.unexpected_labels", extra={"metric": name, "labels": sorted(unexpected)})
        if label_names:
            histogram.labels(**{label: provided.get(label, "") for label in label_names}).observe(value)
        else:
            histogram.observe(value)

    def set_gauge(self, name: str, value: float) -> None:
        metric_name = _metric_name(name)
        if metric_name is None:
            return
        with _REGISTRY_LOCK:
            gauge = _GAUGES.get(metric_name)
            if gauge is None:
                gauge = Gauge(metric_name, f"Grasp gauge {metric_name}", multiprocess_mode="livesum")
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

    @staticmethod
    def _histogram(
        name: str,
        labels: Mapping[str, str],
        buckets: tuple[float, ...] | None,
    ) -> tuple[Histogram, tuple[str, ...]]:
        """Get or create the histogram; label names and buckets are fixed by
        the first call, a later different buckets set is logged and ignored."""
        provided = tuple(labels)
        with _REGISTRY_LOCK:
            entry = _HISTOGRAMS.get(name)
            if entry is None:
                histogram = Histogram(
                    name,
                    f"Grasp histogram {name}",
                    provided,
                    buckets=buckets if buckets is not None else Histogram.DEFAULT_BUCKETS,
                )
                entry = (histogram, provided, buckets)
                _HISTOGRAMS[name] = entry
                return histogram, provided
        histogram, label_names, fixed_buckets = entry
        if buckets is not None and buckets != fixed_buckets:
            logger.warning("metrics.buckets_mismatch", extra={"metric": name})
        return histogram, label_names
