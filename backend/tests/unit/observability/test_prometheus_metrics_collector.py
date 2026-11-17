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


def test_counter_without_labels_increments_directly() -> None:
    name = unique("unlabeled")
    collector = PrometheusMetricsCollector()
    collector.increment_counter(name)
    collector.increment_counter(name, by=2)
    assert REGISTRY.get_sample_value(f"{name}_total") == 3


def test_dots_in_metric_names_are_normalized() -> None:
    name = f"{unique('widgets')}.excluded"
    normalized = name.replace(".", "_")
    collector = PrometheusMetricsCollector()
    collector.increment_counter(name)
    assert REGISTRY.get_sample_value(f"{normalized}_total") == 1


def test_invalid_metric_name_is_skipped_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    collector = PrometheusMetricsCollector()
    with caplog.at_level("WARNING"):
        collector.increment_counter(f"invalid metric {uuid4().hex}")
        collector.observe_histogram(f"invalid metric {uuid4().hex}", 1)
        collector.set_gauge(f"invalid metric {uuid4().hex}", 1)
    assert [record.message for record in caplog.records] == ["metrics.invalid_name"] * 3


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


def test_histogram_fixes_labels_and_buckets_on_first_call() -> None:
    name = unique("histogram")
    collector = PrometheusMetricsCollector()
    collector.observe_histogram(name, 1.5, labels={"purpose": "main_pass"}, buckets=(1.0, 5.0))
    collector.observe_histogram(name, 7.0, labels={"purpose": "quiz_gen"})
    assert REGISTRY.get_sample_value(f"{name}_count", {"purpose": "main_pass"}) == 1
    assert REGISTRY.get_sample_value(f"{name}_count", {"purpose": "quiz_gen"}) == 1
    # Labeled samples carry the label set, so _sum is queried per label.
    assert REGISTRY.get_sample_value(f"{name}_sum", {"purpose": "main_pass"}) == 1.5
    assert REGISTRY.get_sample_value(f"{name}_sum", {"purpose": "quiz_gen"}) == 7.0
    # 7.0 exceeds the fixed buckets, so it lands in +Inf for main_pass and
    # quiz_gen alike (le=5.0 keeps only the first call's 1.5).
    assert REGISTRY.get_sample_value(f"{name}_bucket", {"purpose": "main_pass", "le": "5.0"}) == 1


def test_histogram_with_different_buckets_logs_warning_and_keeps_the_original(
    caplog: pytest.LogCaptureFixture,
) -> None:
    name = unique("histogram")
    collector = PrometheusMetricsCollector()
    collector.observe_histogram(name, 1.0, buckets=(1.0, 5.0))
    with caplog.at_level("WARNING"):
        collector.observe_histogram(name, 2.0, buckets=(0.5, 10.0))
    assert [record.message for record in caplog.records] == ["metrics.buckets_mismatch"]
    # The observation still lands in the histogram created by the first call.
    assert REGISTRY.get_sample_value(f"{name}_count") == 2
    assert REGISTRY.get_sample_value(f"{name}_sum") == 3.0


def test_histogram_unexpected_labels_are_dropped_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    name = unique("histogram")
    collector = PrometheusMetricsCollector()
    collector.observe_histogram(name, 1.0)
    with caplog.at_level("WARNING"):
        collector.observe_histogram(name, 2.0, labels={"purpose": "main_pass"})
    assert [record.message for record in caplog.records] == ["metrics.unexpected_labels"]
    assert REGISTRY.get_sample_value(f"{name}_count") == 2
