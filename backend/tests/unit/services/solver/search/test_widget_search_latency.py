"""Unit tests for the widget-search latency harness assertions."""

import pytest

from tests.support.widget_search_latency import assert_p95_below, nearest_rank_percentile


def test_nearest_rank_p95_uses_ceil_rank_without_interpolation() -> None:
    samples = [float(value) for value in range(1, 101)]

    assert nearest_rank_percentile(samples, 95) == 95.0
    assert nearest_rank_percentile(samples, 99) == 99.0
    assert nearest_rank_percentile([7.0], 95) == 7.0


def test_p95_assertion_accepts_a_value_just_below_the_limit() -> None:
    samples = [49.999] * 100

    assert assert_p95_below(samples) == 49.999


def test_p95_assertion_rejects_the_exact_limit() -> None:
    samples = [50.0] * 100

    with pytest.raises(AssertionError, match=r"not below 50\.000 ms"):
        assert_p95_below(samples)


def test_p95_assertion_does_not_fail_on_an_outlier_above_the_limit() -> None:
    samples = [49.0] * 99 + [50.001]

    assert assert_p95_below(samples) == 49.0


def test_nearest_rank_percentile_rejects_an_empty_sample_set() -> None:
    with pytest.raises(ValueError, match="At least one latency sample"):
        nearest_rank_percentile([], 95)
