"""Metrics facade shared with the observability layer."""

from abc import ABC, abstractmethod


class MetricsCollector(ABC):
    @abstractmethod
    def increment_counter(self, name: str) -> None: ...

    @abstractmethod
    def observe_histogram(self, name: str, value: float) -> None: ...

    @abstractmethod
    def set_gauge(self, name: str, value: float) -> None: ...
