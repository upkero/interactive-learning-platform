"""Metrics facade shared with the observability layer."""

from abc import ABC, abstractmethod
from collections.abc import Mapping


class MetricsCollector(ABC):
    @abstractmethod
    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None: ...

    @abstractmethod
    def observe_histogram(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> None: ...

    @abstractmethod
    def set_gauge(self, name: str, value: float) -> None: ...
