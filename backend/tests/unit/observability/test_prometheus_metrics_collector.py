from uuid import uuid4

import pytest
from prometheus_client import REGISTRY

from src.app.observability.prometheus_metrics_collector import PrometheusMetricsCollector

pytestmark = pytest.mark.unit


def unique(prefix: str) -> str:
    return f"grasp_{prefix}_{uuid4().hex}"


def test_counters_are_created_by_name_and_keep_their_labels() -> None:
    name = unique("counter")
    collector = PrometheusMetricsCollector()
    collector.increment_counter(name, labels={"action": "requeued"})
    collector.increment_counter(name, labels={"action": "failed"}, by=2)
    collector.increment_counter(name, labels={"action": "failed"})
    assert REGISTRY.get_sample_value(f"{name}_total", {"action": "requeued"}) == 1
    assert REGISTRY.get_sample_value(f"{name}_total", {"action": "failed"}) == 3


def test_a_second_new_metric_name_does_not_raise() -> None:
    collector = PrometheusMetricsCollector()
    name = unique("counter")
    collector.increment_counter(name, labels={"action": "requeued"})
    collector.increment_counter(unique("counter"), labels={"action": "lost"})


def test_histograms_and_gauges_are_supported() -> None:
    histogram = unique("histogram")
    gauge = unique("gauge")
    collector = PrometheusMetricsCollector()
    collector.observe_histogram(histogram, 2.5)
    collector.set_gauge(gauge, 3)
    assert REGISTRY.get_sample_value(f"{histogram}_count") == 1
    assert REGISTRY.get_sample_value(f"{histogram}_sum") == 2.5
    assert REGISTRY.get_sample_value(gauge) == 3
