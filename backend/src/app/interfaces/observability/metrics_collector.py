"""Metrics collector interface: services never know Prometheus sits under it."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

MetricTags = Mapping[str, str]


class MetricsCollector(ABC):
    @abstractmethod
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        tags: MetricTags | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def observe_histogram(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_gauge(
        self,
        name: str,
        value: float,
        tags: MetricTags | None = None,
    ) -> None:
        raise NotImplementedError
