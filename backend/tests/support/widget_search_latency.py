"""Assertions for the optional widget-search latency harness."""

import math
from collections.abc import Sequence

LATENCY_LIMIT_MS = 50.0


def nearest_rank_percentile(samples: Sequence[float], percentile: float) -> float:
    """Return a nearest-rank percentile without interpolation."""
    if not samples:
        raise ValueError("At least one latency sample is required.")
    if not 0.0 < percentile <= 100.0:
        raise ValueError("Percentile must be in the (0, 100] range.")
    ordered = sorted(samples)
    rank = math.ceil(percentile / 100.0 * len(ordered))
    return ordered[rank - 1]


def assert_p95_below(samples: Sequence[float], limit_ms: float = LATENCY_LIMIT_MS) -> float:
    """Fail when the nearest-rank p95 is not strictly below ``limit_ms``."""
    p95 = nearest_rank_percentile(samples, 95)
    if not p95 < limit_ms:
        raise AssertionError(f"widget search p95 {p95:.3f} ms is not below {limit_ms:.3f} ms")
    return p95


__all__ = ["LATENCY_LIMIT_MS", "assert_p95_below", "nearest_rank_percentile"]
