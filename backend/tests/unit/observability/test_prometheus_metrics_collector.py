"""PrometheusMetricsCollector unit tests against a private registry."""

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from src.app.observability.prometheus_metrics_collector import PrometheusMetricsCollector

_TAGS = {"model": "fake-model", "provider": "fake", "outcome": "success", "purpose": "main_pass"}


@pytest.mark.unit
def test_counter_and_histogram_are_exposed() -> None:
    registry = CollectorRegistry()
    collector = PrometheusMetricsCollector(registry=registry)

    collector.increment_counter("llm.complete.requests", tags=_TAGS)
    collector.observe_histogram("llm.complete.duration_seconds", 0.5, tags=_TAGS, buckets=(1.0, 2.0))
    collector.set_gauge("llm.queue.depth", 3)

    body = generate_latest(registry).decode()
    assert "llm_complete_requests_total" in body
    assert "llm_complete_duration_seconds_bucket" in body
    assert "llm_queue_depth" in body


@pytest.mark.unit
def test_same_name_with_different_label_names_raises() -> None:
    registry = CollectorRegistry()
    collector = PrometheusMetricsCollector(registry=registry)
    collector.increment_counter("llm.complete.requests", tags=_TAGS)

    with pytest.raises(ValueError, match=r"llm\.complete\.requests"):
        collector.increment_counter("llm.complete.requests", tags={"outcome": "success"})


@pytest.mark.unit
def test_repeated_tags_reuse_the_same_metric() -> None:
    registry = CollectorRegistry()
    collector = PrometheusMetricsCollector(registry=registry)

    collector.increment_counter("llm.complete.requests", tags=_TAGS)
    collector.increment_counter("llm.complete.requests", tags=_TAGS)

    value_lines = [
        line
        for line in generate_latest(registry).decode().splitlines()
        if line.startswith("llm_complete_requests_total{")
    ]
    assert len(value_lines) == 1
