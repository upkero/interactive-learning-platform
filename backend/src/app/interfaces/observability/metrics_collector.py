"""Metrics collector interface: services never know what sits under it.

The real exporter (Prometheus exposition) arrives with story 1.9 — until
then the container wires :class:`~src.app.observability.noop_metrics_collector.NoopMetricsCollector`.
Structural typing: implementations do not need to inherit this protocol.
"""

from collections.abc import Mapping
from typing import Protocol

MetricTags = Mapping[str, str]


class MetricsCollectorProtocol(Protocol):
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        tags: MetricTags | None = None,
    ) -> None: ...

    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None: ...

    def set_gauge(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
    ) -> None: ...
